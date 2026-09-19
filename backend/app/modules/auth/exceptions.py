from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.auth.cookies import delete_session_cookie
from app.modules.auth.model import SessionEndReason
from app.shared.exceptions import AppException, error_response

END_REASON_MESSAGES: dict[SessionEndReason, str] = {
    SessionEndReason.LOGOUT: "Sessão encerrada. Faça login novamente.",
    SessionEndReason.IDLE_TIMEOUT: "Sua sessão expirou por inatividade. Faça login novamente.",
    SessionEndReason.ABSOLUTE_TIMEOUT: "Sua sessão atingiu o tempo máximo. Faça login novamente.",
    SessionEndReason.REVOKED: "Sua sessão foi encerrada. Faça login novamente.",
}


class AuthException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    # Quando true, a resposta também apaga o cookie de sessão do navegador
    clear_cookie = False


class InvalidCredentialsException(AuthException):
    code = "INVALID_CREDENTIALS"

    def __init__(self) -> None:
        super().__init__("Usuário ou senha inválidos")


class InactiveUserException(AuthException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "USER_INACTIVE"

    def __init__(self) -> None:
        super().__init__("Usuário inativo. Procure o administrador.")


class NotAuthenticatedException(AuthException):
    code = "NOT_AUTHENTICATED"
    clear_cookie = True

    def __init__(self) -> None:
        super().__init__("Você precisa estar logado para acessar este recurso")


class SessionExpiredException(AuthException):
    code = "SESSION_EXPIRED"
    clear_cookie = True

    def __init__(self, reason: SessionEndReason) -> None:
        super().__init__(END_REASON_MESSAGES[reason])
        self.reason = reason


class ForbiddenException(AuthException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"

    def __init__(self, detail: str = "Você não tem permissão para acessar este recurso") -> None:
        super().__init__(detail)


async def auth_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AuthException)
    response = error_response(exc)
    if exc.clear_cookie:
        delete_session_cookie(response)
    return response


def register_auth_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AuthException, auth_exception_handler)
