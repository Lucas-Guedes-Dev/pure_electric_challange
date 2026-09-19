"""Integração com o sistema interno: o client HTTP e o próprio mock."""

from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from app.modules.orders.internal_client import InternalSystemClient, OrderDispatch
from app.modules.orders.model import AttemptOutcome
from internal_system import main as internal_system

DISPATCH = OrderDispatch(order_id=1, external_id="ORDER-1", customer="Cliente", amount=Decimal("150.00"), attempt=1)


def client_returning(handler) -> InternalSystemClient:
    http = httpx.Client(base_url="http://internal", transport=httpx.MockTransport(handler))
    return InternalSystemClient("http://internal", timeout_seconds=5, http=http)


# ---------- client: classificação das respostas ----------


def test_client_sends_order_with_idempotency_key() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        seen["json"] = request.read().decode()
        return httpx.Response(200, json={"reference": "INT-1"})

    result = client_returning(handler).send(DISPATCH)

    assert result.outcome == AttemptOutcome.SUCCESS
    assert result.reference == "INT-1"
    assert seen["headers"]["Idempotency-Key"] == "ORDER-1"
    assert '"amount":"150.00"' in seen["json"]


@pytest.mark.parametrize("status", [500, 502, 503, 504, 429, 408])
def test_server_errors_are_transient(status: int) -> None:
    result = client_returning(lambda _: httpx.Response(status, json={"detail": "fora"})).send(DISPATCH)
    assert result.outcome == AttemptOutcome.TRANSIENT_ERROR
    assert f"HTTP {status}" in result.message


@pytest.mark.parametrize("status", [400, 404, 409, 422])
def test_client_errors_are_permanent(status: int) -> None:
    result = client_returning(lambda _: httpx.Response(status, json={"detail": "recusado"})).send(DISPATCH)
    assert result.outcome == AttemptOutcome.PERMANENT_ERROR
    assert "recusado" in result.message


@pytest.mark.parametrize(
    "exception", [httpx.ReadTimeout("t"), httpx.ConnectError("c"), httpx.RemoteProtocolError("p")]
)
def test_network_failures_are_transient(exception: Exception) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise exception

    result = client_returning(handler).send(DISPATCH)
    assert result.outcome == AttemptOutcome.TRANSIENT_ERROR


# ---------- mock do sistema interno ----------


@pytest.fixture
def mock_system(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(internal_system, "MIN_LATENCY_MS", 0)
    monkeypatch.setattr(internal_system, "MAX_LATENCY_MS", 0)
    monkeypatch.setattr(internal_system, "FAILURE_RATE", 0)
    internal_system.accepted.clear()
    internal_system.calls.clear()
    return TestClient(internal_system.app)


def send(mock: TestClient, external_id: str, amount: str = "150.00") -> httpx.Response:
    return mock.post(
        "/internal/orders",
        json={"orderId": 1, "externalId": external_id, "customer": "Cliente", "amount": amount},
        headers={"Idempotency-Key": external_id},
    )


def test_mock_accepts_and_is_idempotent(mock_system: TestClient) -> None:
    first = send(mock_system, "ORDER-1")
    again = send(mock_system, "ORDER-1")

    assert first.status_code == 200
    assert first.json()["reference"].startswith("INT-")
    assert again.json()["reference"] == first.json()["reference"]
    assert again.headers["Idempotent-Replayed"] == "true"


def test_mock_scenarios(mock_system: TestClient) -> None:
    assert send(mock_system, "FAIL-1").status_code == 422
    assert send(mock_system, "ORDER-2", amount="100000.01").status_code == 422
    assert [send(mock_system, "FLAKY-1").status_code for _ in range(3)] == [503, 503, 200]


def test_mock_outage_lasts_a_full_round_of_attempts(mock_system: TestClient) -> None:
    # 3 falhas (a rodada inteira de tentativas) e depois volta: é o cenário do reprocessamento
    assert [send(mock_system, "OUTAGE-1").status_code for _ in range(4)] == [503, 503, 503, 200]
