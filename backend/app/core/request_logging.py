"""Interceptor de requests: registra um log por request com método, rota, status,
duração, IP, user agent e usuário logado, no formato ECS usado pelo Kibana.

É um middleware ASGI puro (não BaseHTTPMiddleware) para não interferir em respostas
em streaming, como o SSE de /api/auth/events.

Por segurança, NUNCA registra corpo de request/response, cookies ou headers de
autenticação (o login trafega senha no corpo e a sessão vai no cookie).
"""

import logging
import re
import time
import uuid
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logger import LOGGED_EXCEPTION_ATTR, request_id_var

logger = logging.getLogger("app.request")

REQUEST_ID_HEADER = "X-Request-ID"
# Aceita o id vindo do cliente/proxy só se for "bem comportado" (evita log injection)
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _resolve_request_id(headers: Headers) -> str:
    incoming = headers.get(REQUEST_ID_HEADER)
    if incoming and _VALID_REQUEST_ID.match(incoming):
        return incoming
    return uuid.uuid4().hex


def _route_template(scope: Scope) -> str | None:
    """Rota "genérica" do request (ex.: /api/users/{user_id}), boa para agrupar no Kibana.

    Routers incluídos com prefixo guardam a rota relativa ao prefixo ("/users/{user_id}"),
    então o prefixo é recuperado a partir do path real do request."""
    route = scope.get("route")
    template = getattr(route, "path_format", None) or getattr(route, "path", None)
    if not template:
        return None
    concrete = template
    for name, value in scope.get("path_params", {}).items():
        concrete = concrete.replace("{" + name + "}", str(value))
    path: str = scope["path"]
    if path.endswith(concrete):
        return path[: len(path) - len(concrete)] + template
    return template


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = _resolve_request_id(headers)
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            self._log(scope, headers, 500, start, exc)
            try:
                setattr(exc, LOGGED_EXCEPTION_ATTR, True)
            except AttributeError:
                pass
            raise
        else:
            self._log(scope, headers, status_code, start)
        finally:
            request_id_var.reset(token)

    @staticmethod
    def _log(
        scope: Scope,
        headers: Headers,
        status_code: int,
        start: float,
        exc: Exception | None = None,
    ) -> None:
        duration = time.perf_counter() - start
        method = scope["method"]
        path = scope["path"]
        client = scope.get("client")
        # Preenchidos durante o request: rota do FastAPI e usuário (dependency de auth)
        route = _route_template(scope)
        user_id = scope.get("state", {}).get("user_id")

        if status_code >= 500:
            level = logging.ERROR
        elif status_code >= 400:
            level = logging.WARNING
        else:
            level = logging.INFO

        fields: dict[str, Any] = {
            "event": {
                "kind": "event",
                "category": ["web"],
                "type": ["access"],
                "outcome": "failure" if status_code >= 400 else "success",
                "duration": int(duration * 1_000_000_000),  # ECS: nanossegundos
            },
            "http": {
                "request": {"method": method},
                "response": {"status_code": status_code},
                "route": route,
            },
            "url": {"path": path, "query": scope.get("query_string", b"").decode("latin-1") or None},
            "client": {"ip": client[0] if client else None},
            "user_agent": {"original": headers.get("user-agent")},
        }
        if user_id is not None:
            fields["user"] = {"id": str(user_id)}

        logger.log(
            level,
            "%s %s %s %.1fms",
            method,
            path,
            status_code,
            duration * 1000,
            exc_info=exc,
            extra={"ecs": fields},
        )
