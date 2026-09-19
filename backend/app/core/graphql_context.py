"""Contexto e utilitários compartilhados pelos resolvers GraphQL de todos os módulos.

Regras que os resolvers seguem:
- Toda chamada a service passa por `ctx.run(...)`: abre uma sessão de banco própria e roda
  numa thread. O service é síncrono; chamá-lo direto travaria o event loop (e todas as
  outras requisições) enquanto o banco responde.
- As chamadas de um mesmo request são feitas uma por vez (os campos de uma query rodam em
  paralelo): uma query com muitos campos não ocupa várias conexões do pool de uma vez.
- Erros de negócio (`AppException`) viram erros GraphQL com `extensions.code`, os mesmos
  códigos do REST (`SESSION_EXPIRED`, `EXTERNAL_ID_CONFLICT`...).
"""

import asyncio
import time
from collections.abc import Callable
from typing import Any, TypeVar

from graphql import GraphQLError
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from strawberry.dataloader import DataLoader
from strawberry.fastapi import BaseContext

from app.core.config import settings
from app.modules.auth.cookies import delete_session_cookie
from app.modules.auth.exceptions import AuthException, ForbiddenException
from app.modules.auth.model import UserSession
from app.modules.auth.repository import SessionRepository
from app.modules.auth.service import AuthService
from app.modules.users.model import User, UserRole
from app.modules.users.repository import UserRepository
from app.shared.exceptions import AppException

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)

DEFAULT_CODES = {400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT"}


class GraphQLContext(BaseContext):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        super().__init__()
        self.session_factory = session_factory
        self._user: User | None = None
        self._loaders: dict[str, DataLoader] = {}
        self._session_checked_at = 0.0
        self._db_lock = asyncio.Lock()
        self._auth_lock = asyncio.Lock()
        # Sessão do ticket de conexão do WebSocket (ver auth/ws_ticket.py). Sem ticket, vale o cookie.
        self.ws_session_id: int | None = None

    # ---------- banco ----------

    async def run(self, fn: Callable[[Session], T]) -> T:
        """Executa `fn(db)` numa thread, com uma sessão de banco só para ela."""

        def call() -> T:
            with self.session_factory() as db:
                return fn(db)

        try:
            async with self._db_lock:
                return await run_in_threadpool(call)
        except AppException as exc:
            raise self.to_graphql_error(exc) from exc

    def loader(self, name: str, factory: Callable[[], DataLoader]) -> DataLoader:
        """DataLoader único por contexto (por request no HTTP)."""
        if name not in self._loaders:
            self._loaders[name] = factory()
        return self._loaders[name]

    # ---------- autenticação (mesma sessão/cookie do REST) ----------

    @property
    def session_token(self) -> str | None:
        return self.request.cookies.get(settings.session_cookie_name) if self.request else None

    def header(self, name: str) -> str | None:
        return self.request.headers.get(name) if self.request else None

    async def require_user(self) -> User:
        """Exige login e registra atividade (renova os 30 min), como qualquer rota REST.
        Validado uma vez por request, mesmo que vários campos da query peçam."""
        async with self._auth_lock:
            if self._user is None:
                user, _ = await self._authenticate(touch=True)
                self._user = user
                if isinstance(self.request, Request):
                    self.request.state.user_id = user.id  # aparece nos logs do request
        return self._user

    async def require_admin(self) -> User:
        """Como `require_user`, mas só para administradores (FORBIDDEN para os demais)."""
        user = await self.require_user()
        if user.role != UserRole.ADMIN:
            raise self.to_graphql_error(ForbiddenException("Acesso restrito ao administrador"))
        return user

    async def check_session_alive(self, *, min_interval: float = 0) -> None:
        """Confere a sessão SEM renovar (WebSocket: ficar conectado não conta como atividade).
        Levanta SESSION_EXPIRED se acabou. `min_interval` evita consultar o banco a cada evento."""
        now = time.monotonic()
        if min_interval and now - self._session_checked_at < min_interval:
            return
        await self._authenticate(touch=False)
        self._session_checked_at = now

    async def _authenticate(self, *, touch: bool) -> tuple[User, UserSession]:
        token, session_id = self.session_token, self.ws_session_id

        def check(db: Session) -> tuple[User, UserSession]:
            service = AuthService(UserRepository(db), SessionRepository(db))
            if session_id is not None:
                return service.authenticate_session_id(session_id, touch=touch)
            return service.authenticate(token, touch=touch)

        return await self.run(check)

    # ---------- erros ----------

    def to_graphql_error(self, exc: AppException) -> GraphQLError:
        if isinstance(exc, AuthException) and exc.clear_cookie and self.response is not None:
            delete_session_cookie(self.response)
        code = exc.code or DEFAULT_CODES.get(exc.status_code, "BAD_REQUEST")
        return GraphQLError(exc.detail, extensions={"code": code})


def validate_input(model: type[M], data: dict[str, Any]) -> M:
    """Valida argumentos com o mesmo DTO do REST. Erro -> BAD_USER_INPUT com os campos."""
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        fields = [
            {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
            for error in exc.errors()
        ]
        raise GraphQLError(
            "Dados inválidos: " + "; ".join(f"{f['field']}: {f['message']}" for f in fields),
            extensions={"code": "BAD_USER_INPUT", "fields": fields},
        ) from exc


def parse_id(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise GraphQLError(f"ID inválido: {value!r}", extensions={"code": "BAD_USER_INPUT"}) from None
