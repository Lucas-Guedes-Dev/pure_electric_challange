"""Dependências para proteger rotas de qualquer módulo:

    from app.modules.auth.dependencies import CurrentUser, CurrentAdmin

    @router.get("")
    def listar(user: CurrentUser) -> ...: ...
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie

from app.core.config import settings
from app.modules.auth.exceptions import ForbiddenException
from app.modules.auth.model import UserSession
from app.modules.auth.service import AuthServiceDep
from app.modules.users.model import User, UserRole

# Só lê o cookie; também faz o Swagger mostrar o cadeado nas rotas protegidas
session_cookie_scheme = APIKeyCookie(
    name=settings.session_cookie_name,
    auto_error=False,
    description="Cookie HttpOnly criado pelo POST /api/auth/login. "
    "No Swagger, basta fazer o login: o navegador envia o cookie sozinho.",
)

SessionToken = Annotated[str | None, Depends(session_cookie_scheme)]


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: UserSession


def get_auth_context(request: Request, service: AuthServiceDep, token: SessionToken) -> AuthContext:
    """Valida a sessão e registra atividade (renova os 30 min de inatividade)."""
    user, session = service.authenticate(token, touch=True)
    # Lido pelo RequestLoggingMiddleware para mostrar o usuário (user.id) nos logs
    request.state.user_id = user.id
    return AuthContext(user=user, session=session)


CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


def get_current_user(auth: CurrentAuth) -> User:
    return auth.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise ForbiddenException("Acesso restrito ao administrador")
    return user


CurrentAdmin = Annotated[User, Depends(get_current_admin)]
