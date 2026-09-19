import io
import json
import logging
import time
import urllib.error
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.elasticsearch_handler import ElasticsearchLogHandler
from app.modules.users.model import User
from tests.conftest import PASSWORD


def _request_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "app.request"]


def test_response_has_generated_request_id(client: TestClient) -> None:
    response = client.get("/api/health")
    assert len(response.headers["X-Request-ID"]) == 32


def test_incoming_request_id_is_kept_and_invalid_one_replaced(client: TestClient) -> None:
    assert client.get("/api/health", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"] == "abc-123"
    replaced = client.get("/api/health", headers={"X-Request-ID": "bad id\nwith newline"})
    assert replaced.headers["X-Request-ID"] != "bad id\nwith newline"


def test_request_is_logged_with_ecs_fields(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"):
        response = client.get("/api/health?verbose=1", headers={"User-Agent": "pytest"})

    [record] = _request_records(caplog)
    assert record.levelno == logging.INFO
    assert record.request_id == response.headers["X-Request-ID"]
    fields = record.ecs
    assert fields["http"]["request"]["method"] == "GET"
    assert fields["http"]["response"]["status_code"] == 200
    assert fields["http"]["route"] == "/api/health"
    assert fields["url"] == {"path": "/api/health", "query": "verbose=1"}
    assert fields["user_agent"]["original"] == "pytest"
    assert fields["event"]["outcome"] == "success"
    assert fields["event"]["duration"] > 0


def test_client_errors_are_warnings(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/api/nao-existe")

    [record] = _request_records(caplog)
    assert record.levelno == logging.WARNING
    assert record.ecs["event"]["outcome"] == "failure"


def test_login_body_is_never_logged(
    client: TestClient, make_user: Callable[..., User], caplog: pytest.LogCaptureFixture
) -> None:
    user = make_user()
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.post("/api/auth/login", json={"username": user.username, "password": PASSWORD})
        client.get("/api/auth/me")

    assert PASSWORD not in caplog.text
    login_record, me_record = _request_records(caplog)
    assert PASSWORD not in json.dumps(login_record.ecs)
    # rota autenticada registra o usuário
    assert me_record.ecs["user"]["id"] == str(user.id)


# --- ElasticsearchLogHandler ------------------------------------------------------------


class FakeResponse:
    status = 200

    def __init__(self, body: dict[str, Any]) -> None:
        self._body = json.dumps(body).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _make_handler(**kwargs: Any) -> ElasticsearchLogHandler:
    return ElasticsearchLogHandler(
        "http://elasticsearch:9200/",
        "logs-test-default",
        service_name="api",
        service_version="1.0.0",
        environment="test",
        flush_interval=0.05,
        retry_delay=0.05,
        **kwargs,
    )


def _record(message: str, **extra: Any) -> logging.LogRecord:
    record = logging.LogRecord("app.test", logging.ERROR, __file__, 1, message, None, None)
    record.__dict__.update(extra)
    return record


def test_handler_builds_ecs_document() -> None:
    handler = _make_handler()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _record("falhou", request_id="req-1", ecs={"user": {"id": "7"}})
        record.exc_info = sys.exc_info()
    document = handler.to_document(record)
    handler.close()

    assert document["message"] == "falhou"
    assert document["log"]["level"] == "ERROR"
    assert document["service"] == {"name": "api", "version": "1.0.0", "environment": "test"}
    assert document["http"]["request"]["id"] == "req-1"
    assert document["user"]["id"] == "7"
    assert document["error"]["type"] == "ValueError"
    assert "boom" in document["error"]["stack_trace"]


def _http_error(url: str, code: int, body: dict[str, Any]) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "erro", {}, io.BytesIO(json.dumps(body).encode()))  # type: ignore[arg-type]


def test_handler_waits_for_elasticsearch_and_data_stream_before_sending(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simula o ES subindo: primeiro fora do ar, depois sem o template de logs instalado
    (não dá para criar o data stream) e por fim pronto. Nenhum log pode ir para o _bulk
    antes de o data stream existir, senão o ES cria um índice comum no lugar."""
    calls: list[tuple[str, str]] = []
    state = {"down": True, "template_installed": False, "data_stream": False}
    bulk_bodies: list[bytes] = []

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        method, url = request.get_method(), request.full_url
        calls.append((method, url))
        if state["down"]:
            state["down"] = False
            raise urllib.error.URLError("connection refused")
        if url.endswith("/_data_stream/logs-test-default"):
            if method == "GET":
                if not state["data_stream"]:
                    raise _http_error(url, 404, {"error": {"type": "index_not_found_exception"}})
                return FakeResponse({"data_streams": [{}]})
            if not state["template_installed"]:
                state["template_installed"] = True  # instalado a tempo da próxima tentativa
                raise _http_error(url, 400, {"error": {"type": "illegal_argument_exception"}})
            state["data_stream"] = True
            return FakeResponse({"acknowledged": True})
        assert state["data_stream"], "enviou logs antes de o data stream existir"
        bulk_bodies.append(request.data)
        return FakeResponse({"errors": False})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    handler = _make_handler()
    handler.emit(_record("primeiro"))
    handler.emit(_record("segundo"))
    deadline = time.monotonic() + 5
    while not bulk_bodies and time.monotonic() < deadline:
        time.sleep(0.02)
    handler.close()

    assert ("PUT", "http://elasticsearch:9200/_data_stream/logs-test-default") in calls
    assert calls[-1] == ("POST", "http://elasticsearch:9200/logs-test-default/_bulk")
    [body] = bulk_bodies
    lines = body.decode().strip().split("\n")
    assert lines[0] == '{"create":{}}'
    assert [json.loads(line)["message"] for line in lines[1::2]] == ["primeiro", "segundo"]


def test_unhandled_exception_is_logged_once_as_error(caplog: pytest.LogCaptureFixture) -> None:
    from fastapi import FastAPI

    from app.core.logger import SkipAlreadyLoggedFilter
    from app.core.request_logging import RequestLoggingMiddleware

    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("falha inesperada")

    with caplog.at_level(logging.INFO, logger="app.request"):
        response = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 500
    [record] = _request_records(caplog)
    assert record.levelno == logging.ERROR
    assert record.ecs["http"]["response"]["status_code"] == 500
    assert record.exc_info is not None
    # o log repetido do uvicorn ("Exception in ASGI application") é filtrado do Kibana
    uvicorn_record = logging.LogRecord("uvicorn.error", logging.ERROR, __file__, 1, "x", None, record.exc_info)
    assert SkipAlreadyLoggedFilter().filter(uvicorn_record) is False
