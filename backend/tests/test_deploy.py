"""Suporte ao deploy (Railway + Vercel): ticket do WebSocket e DATABASE_URL."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.modules.auth.exceptions import NotAuthenticatedException
from app.modules.auth.ws_ticket import issue_ticket, read_ticket

PROTOCOL = ["graphql-transport-ws"]


# ---------- ticket ----------


def test_ticket_roundtrip() -> None:
    assert read_ticket(issue_ticket(42)) == 42


def test_tampered_ticket_is_rejected() -> None:
    payload, _, signature = issue_ticket(42).partition(".")
    other_payload = issue_ticket(43).partition(".")[0]

    for ticket in (f"{other_payload}.{signature}", f"{payload}.x{signature}", "lixo", ""):
        with pytest.raises(NotAuthenticatedException):
            read_ticket(ticket)


def test_expired_ticket_is_rejected() -> None:
    ticket = issue_ticket(42, now=1_000)

    assert read_ticket(ticket, now=1_010) == 42
    with pytest.raises(NotAuthenticatedException):
        read_ticket(ticket, now=1_000 + 3600)


def test_ticket_endpoint_requires_login(client: TestClient) -> None:
    response = client.post("/api/auth/ws-ticket")

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


# ---------- WebSocket com ticket (API em outro domínio que o cookie) ----------


def open_with_ticket(client: TestClient, ticket: str | None):
    ws = client.websocket_connect("/api/graphql", subprotocols=PROTOCOL)
    return ws, {"type": "connection_init", "payload": {"ticket": ticket} if ticket else {}}


def test_websocket_accepts_ticket_without_cookie(logged_client: TestClient) -> None:
    body = logged_client.post("/api/auth/ws-ticket").json()
    assert body["expires_in_seconds"] > 0
    logged_client.cookies.clear()  # como o navegador falando direto com o domínio da API

    ws, init = open_with_ticket(logged_client, body["ticket"])
    with ws:
        ws.send_json(init)
        assert ws.receive_json()["type"] == "connection_ack"


def test_websocket_rejects_invalid_ticket(client: TestClient) -> None:
    ws, init = open_with_ticket(client, "ticket-falso")
    with pytest.raises(WebSocketDisconnect) as closed:
        with ws:
            ws.send_json(init)
            ws.receive_json()
    assert closed.value.code == 4403


def test_websocket_rejects_ticket_of_ended_session(logged_client: TestClient) -> None:
    ticket = logged_client.post("/api/auth/ws-ticket").json()["ticket"]
    logged_client.post("/api/auth/logout")

    ws, init = open_with_ticket(logged_client, ticket)
    with pytest.raises(WebSocketDisconnect) as closed:
        with ws:
            ws.send_json(init)
            ws.receive_json()
    assert closed.value.code == 4403


# ---------- DATABASE_URL (Postgres do Railway) ----------


@pytest.mark.parametrize("scheme", ["postgres", "postgresql"])
def test_database_url_env_is_used_with_psycopg_driver(monkeypatch: pytest.MonkeyPatch, scheme: str) -> None:
    monkeypatch.setenv("DATABASE_URL", f"{scheme}://user:pass@db.railway.internal:5432/railway")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@db.railway.internal:5432/railway"
    assert settings.psycopg_conninfo == "postgresql://user:pass@db.railway.internal:5432/railway"


def test_without_database_url_uses_postgres_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "db")

    assert Settings(_env_file=None).database_url.startswith("postgresql+psycopg://postgres:postgres@db:5432/")
