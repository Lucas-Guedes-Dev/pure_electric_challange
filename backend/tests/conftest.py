from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db, get_session_factory
from app.core.rate_limit import limiter
from app.main import app
from app.modules import import_all_models
from app.modules.auth.security import hash_password
from app.modules.users.model import User, UserRole
from app.shared.model import Base

import_all_models()

# bcrypt no custo mínimo: os testes fazem muitos logins
settings.password_hash_rounds = 4
# Testes não dependem do ambiente (no container ORDERS_WEBHOOK_KEY vem preenchido).
# O teste da chave do webhook a configura explicitamente.
settings.orders_webhook_key = None
# Sem Postgres nos testes: nada de LISTEN (a subscription é testada publicando direto no broker)
settings.order_events_listener_enabled = False

# Banco em memória para testes rápidos, sem depender do Postgres
engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_session_factory] = lambda: TestingSessionLocal
    limiter.enabled = False
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    limiter.enabled = settings.rate_limit_enabled
    limiter.reset()


PASSWORD = "senha-forte-123"


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    def _make_user(
        username: str = "admin",
        password: str = PASSWORD,
        role: UserRole = UserRole.ADMIN,
        is_active: bool = True,
    ) -> User:
        user = User(
            username=username,
            email=f"{username}@pureelectric.com.br",
            full_name=username.title(),
            hashed_password=hash_password(password),
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        return user

    return _make_user


@pytest.fixture
def logged_client(client: TestClient, make_user: Callable[..., User]) -> TestClient:
    """Cliente com sessão de login (cookie) para as rotas protegidas."""
    make_user()
    response = client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD})
    assert response.status_code == 200
    return client
