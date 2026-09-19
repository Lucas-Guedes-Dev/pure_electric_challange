"""Configuração de logging da API.

Todo log (da aplicação, do uvicorn e do interceptor de requests) sai no console e, se
ELASTICSEARCH_URL estiver definido, também vai para o Elasticsearch (Kibana).

Para logar num módulo:

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Pedido criado", extra={"ecs": {"labels": {"pedido_id": pedido.id}}})

Logs emitidos durante um request levam o `http.request.id` automaticamente, então no
Kibana dá para filtrar tudo o que aconteceu num request específico.
"""

import logging
import sys
from contextvars import ContextVar

from app.core.config import settings
from app.core.elasticsearch_handler import ElasticsearchLogHandler

# Preenchido pelo RequestLoggingMiddleware no início de cada request
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Marcador colocado nas exceções já registradas pelo interceptor
LOGGED_EXCEPTION_ATTR = "_request_logged"

_configured = False


class RequestContextFilter(logging.Filter):
    """Anexa o id do request atual a todo registro de log."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


class SkipAlreadyLoggedFilter(logging.Filter):
    """Evita duplicar no Kibana a exceção que o interceptor já registrou e que o
    uvicorn loga de novo ao devolver o 500 ("Exception in ASGI application")."""

    def filter(self, record: logging.LogRecord) -> bool:
        exc = record.exc_info[1] if record.exc_info else None
        return not getattr(exc, LOGGED_EXCEPTION_ATTR, False)


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    context_filter = RequestContextFilter()

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s [%(name)s] [%(request_id)s] %(message)s"))
    console.addFilter(context_filter)
    root.addHandler(console)

    if not settings.elasticsearch_url:
        return

    elastic = ElasticsearchLogHandler(
        settings.elasticsearch_url,
        settings.elasticsearch_logs_data_stream,
        service_name=settings.service_name,
        service_version=settings.app_version,
        environment=settings.environment,
    )
    elastic.addFilter(context_filter)
    elastic.addFilter(SkipAlreadyLoggedFilter())
    root.addHandler(elastic)

    # Os loggers do uvicorn não propagam para o root. "uvicorn" cobre também o
    # "uvicorn.error" (startup, shutdown, exceções). O "uvicorn.access" fica de fora:
    # o RequestLoggingMiddleware já registra cada request com mais detalhes.
    logging.getLogger("uvicorn").addHandler(elastic)
