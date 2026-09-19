import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.graphql import graphql_router
from app.core.logger import setup_logging
from app.core.openapi import DESCRIPTION, SWAGGER_UI_PARAMETERS, TAGS_METADATA
from app.core.rate_limit import register_rate_limit
from app.core.request_logging import RequestLoggingMiddleware
from app.modules import api_router
from app.modules.auth.exceptions import register_auth_exception_handlers
from app.modules.orders.events import listen_order_events
from app.shared.exceptions import register_exception_handlers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Na subida da API, começa a ouvir os eventos de pedidos do Postgres (LISTEN),
    que alimentam a subscription GraphQL `orderUpdated`."""
    listener: asyncio.Task | None = None
    if settings.order_events_listener_enabled:
        if sys.platform == "win32" and isinstance(asyncio.get_running_loop(), asyncio.ProactorEventLoop):
            # O psycopg assíncrono não roda no event loop padrão do Windows. No Docker (Linux) funciona.
            logger.warning("Eventos em tempo real desligados: rode a API no Docker/Linux para usar a subscription")
        else:
            listener = asyncio.create_task(listen_order_events(), name="order-events-listener")
    yield
    if listener is not None:
        listener.cancel()
        with suppress(asyncio.CancelledError):
            await listener


def create_app() -> FastAPI:
    setup_logging()

    def docs_path(path: str) -> str | None:
        return f"{settings.api_prefix}{path}" if settings.docs_enabled else None

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
        docs_url=docs_path("/docs"),
        redoc_url=docs_path("/redoc"),
        openapi_url=docs_path("/openapi.json"),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Permite ao frontend ler o id do request (útil para achar o log no Kibana)
        expose_headers=["X-Request-ID"],
    )
    # Registrado por último = middleware mais externo: loga todo request, inclusive
    # preflights de CORS e respostas de erro
    app.add_middleware(RequestLoggingMiddleware)

    register_exception_handlers(app)
    register_auth_exception_handlers(app)
    register_rate_limit(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(graphql_router, prefix=settings.api_prefix)  # /api/graphql

    if settings.docs_enabled:

        @app.get("/", include_in_schema=False)
        def redirect_to_docs() -> RedirectResponse:
            return RedirectResponse(url=f"{settings.api_prefix}/docs")

    return app


app = create_app()
