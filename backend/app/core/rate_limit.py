"""Rate limiting (slowapi). Chave = IP do cliente.

Atrás de proxy (Vite em dev, nginx em produção) o IP real vem do X-Forwarded-For,
que o uvicorn só aceita de IPs listados em FORWARDED_ALLOW_IPS.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings
from app.shared.dtos import ErrorResponseDTO

limiter = Limiter(key_func=get_remote_address, enabled=settings.rate_limit_enabled)


async def rate_limit_exceeded_handler(_: Request, __: Exception) -> JSONResponse:
    body = ErrorResponseDTO(
        detail="Muitas tentativas. Aguarde um instante e tente novamente.",
        code="RATE_LIMITED",
    )
    return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content=body.model_dump())


def register_rate_limit(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
