from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.shared.dtos import ErrorResponseDTO


class AppException(Exception):
    """Exceção de domínio. Services lançam; o handler converte em resposta HTTP."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str | None = None

    def __init__(self, detail: str, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT


def error_response(exc: AppException) -> JSONResponse:
    body = ErrorResponseDTO(detail=exc.detail, code=exc.code)
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


async def app_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppException)
    return error_response(exc)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
