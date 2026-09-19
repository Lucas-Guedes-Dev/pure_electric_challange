import json
from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.modules.auth.model import SessionEndReason, UserSession
from app.modules.auth.security import hash_session_token
from app.modules.auth.service import utcnow
from app.modules.users.model import User
from tests.conftest import PASSWORD

COOKIE = settings.session_cookie_name


def login(client: TestClient, username: str = "admin", password: str = PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def current_session(db: Session) -> UserSession:
    return db.scalars(select(UserSession).order_by(UserSession.id.desc())).first()


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if line.startswith(("event", "data")))
        if "event" in lines:
            events.append((lines["event"], json.loads(lines["data"])))
    return events


# ---------- login ----------


def test_login_sets_httponly_cookie_and_returns_session(client: TestClient, make_user) -> None:
    make_user()
    response = login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "admin"
    assert body["user"]["role"] == "ADMIN"
    assert "hashed_password" not in body["user"]
    assert body["session"]["idle_timeout_minutes"] == 30
    assert 1790 <= body["session"]["remaining_seconds"] <= 1800

    set_cookie = response.headers["set-cookie"].lower()
    assert set_cookie.startswith(f"{COOKIE}=")
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "token" not in json.dumps(body)  # token nunca vai no corpo


def test_login_accepts_email(client: TestClient, make_user) -> None:
    make_user()
    assert login(client, username="ADMIN@pureelectric.com.br").status_code == 200


def test_session_token_is_stored_hashed(client: TestClient, db: Session, make_user) -> None:
    make_user()
    login(client)
    token = client.cookies[COOKIE]
    session = current_session(db)
    assert session.token_hash != token
    assert session.token_hash == hash_session_token(token)


@pytest.mark.parametrize(
    ("username", "password"), [("admin", "senha-errada"), ("nao-existe", PASSWORD)]
)
def test_invalid_credentials(client: TestClient, make_user, username: str, password: str) -> None:
    make_user()
    response = login(client, username, password)
    assert response.status_code == 401
    assert response.json() == {"detail": "Usuário ou senha inválidos", "code": "INVALID_CREDENTIALS"}
    assert COOKIE not in client.cookies


def test_inactive_user_cannot_login(client: TestClient, make_user) -> None:
    make_user(is_active=False)
    response = login(client)
    assert response.status_code == 403
    assert response.json()["code"] == "USER_INACTIVE"


def test_new_login_ends_previous_session_of_same_browser(
    client: TestClient, db: Session, make_user
) -> None:
    make_user()
    login(client)
    first = current_session(db)
    login(client)
    assert first.end_reason == SessionEndReason.LOGOUT
    assert current_session(db).id != first.id


def test_login_rate_limit(client: TestClient, make_user) -> None:
    make_user()
    limiter.enabled = True
    statuses = [login(client, password="errada").status_code for _ in range(6)]
    assert statuses == [401] * 5 + [429]
    assert login(client).json()["code"] == "RATE_LIMITED"


# ---------- sessão ----------


def test_me_requires_session(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


def test_me_returns_user_and_renews_idle_timeout(
    client: TestClient, db: Session, make_user
) -> None:
    make_user()
    login(client)
    session = current_session(db)
    session.last_activity_at = utcnow() - timedelta(minutes=20)
    session.expires_at = utcnow() + timedelta(minutes=10)
    db.commit()

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "admin"
    assert response.json()["session"]["remaining_seconds"] >= 1790  # voltou para ~30 min


def test_session_expires_after_30_minutes_of_inactivity(
    client: TestClient, db: Session, make_user
) -> None:
    make_user()
    login(client)
    session = current_session(db)
    session.last_activity_at = utcnow() - timedelta(minutes=30, seconds=1)
    db.commit()

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_EXPIRED"
    assert "inatividade" in response.json()["detail"]
    assert COOKIE not in client.cookies  # a resposta apagou o cookie
    assert session.end_reason == SessionEndReason.IDLE_TIMEOUT
    assert session.ended_at is not None


def test_session_has_absolute_lifetime(client: TestClient, db: Session, make_user) -> None:
    make_user()
    login(client)
    session = current_session(db)
    session.created_at = utcnow() - timedelta(minutes=settings.session_absolute_timeout_minutes + 1)
    db.commit()

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert session.end_reason == SessionEndReason.ABSOLUTE_TIMEOUT


def test_deactivated_user_loses_session(client: TestClient, db: Session, make_user) -> None:
    user: User = make_user()
    login(client)
    user.is_active = False
    db.commit()

    assert client.get("/api/auth/me").status_code == 401
    assert current_session(db).end_reason == SessionEndReason.REVOKED


def test_logout_ends_session_and_clears_cookie(client: TestClient, db: Session, make_user) -> None:
    make_user()
    login(client)
    token = client.cookies[COOKIE]

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert COOKIE not in client.cookies
    assert current_session(db).end_reason == SessionEndReason.LOGOUT
    # O mesmo token não vale mais, mesmo que alguém o tenha guardado
    client.cookies.set(COOKIE, token)
    assert client.get("/api/auth/me").json()["code"] == "SESSION_EXPIRED"


def test_logout_without_session_is_idempotent(client: TestClient) -> None:
    assert client.post("/api/auth/logout").status_code == 204


def test_refresh_renews_session(client: TestClient, db: Session, make_user) -> None:
    make_user()
    login(client)
    session = current_session(db)
    session.last_activity_at = utcnow() - timedelta(minutes=29)
    db.commit()

    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    assert response.json()["session"]["remaining_seconds"] >= 1790


# ---------- eventos (SSE) ----------


def test_events_without_cookie_returns_204(client: TestClient) -> None:
    assert client.get("/api/auth/events").status_code == 204


def test_events_warn_and_signal_logout_when_session_expires(
    client: TestClient, make_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_user()
    monkeypatch.setattr(settings, "session_idle_timeout_minutes", 0.02)  # 1,2 s
    monkeypatch.setattr(settings, "session_warning_seconds", 120)
    monkeypatch.setattr(settings, "session_events_poll_seconds", 0.1)
    login(client)

    # O stream termina sozinho quando a sessão expira
    response = client.get("/api/auth/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.startswith("retry: ")
    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["session", "expiring", "logout"]
    assert events[-1][1]["reason"] == "idle_timeout"
    assert "inatividade" in events[-1][1]["detail"]


def test_events_signal_logout_for_ended_session_and_clear_cookie(
    client: TestClient, make_user
) -> None:
    make_user()
    login(client)
    token = client.cookies[COOKIE]
    client.post("/api/auth/logout")  # ex.: logout feito em outra aba
    client.cookies.set(COOKIE, token)

    response = client.get("/api/auth/events")

    assert parse_sse(response.text) == [
        ("logout", {"reason": "logout", "detail": "Sessão encerrada. Faça login novamente."})
    ]
    # A resposta manda o navegador apagar o cookie; a reconexão chega sem cookie e recebe 204
    set_cookie = response.headers["set-cookie"].lower()
    assert set_cookie.startswith(f'{COOKIE}=""') and "max-age=0" in set_cookie


def test_events_do_not_renew_session(client: TestClient, db: Session, make_user, monkeypatch) -> None:
    make_user()
    monkeypatch.setattr(settings, "session_idle_timeout_minutes", 0.01)
    monkeypatch.setattr(settings, "session_events_poll_seconds", 0.05)
    login(client)
    before = current_session(db).last_activity_at

    client.get("/api/auth/events")

    db.expire_all()
    assert current_session(db).last_activity_at == before


def test_protected_routes_show_lock_in_swagger(client: TestClient) -> None:
    schema = client.get("/api/openapi.json").json()
    assert schema["components"]["securitySchemes"]["APIKeyCookie"]["in"] == "cookie"
    assert schema["paths"]["/api/auth/me"]["get"]["security"] == [{"APIKeyCookie": []}]
    assert {tag["name"] for tag in schema["tags"]} >= {"Health", "Auth"}
