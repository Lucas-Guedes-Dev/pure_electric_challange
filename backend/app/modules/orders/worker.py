"""Worker (consumer) de pedidos. Roda como processo separado da API:

    python -m app.modules.orders.worker

No Docker é o serviço `worker`. Pode ter várias réplicas (`docker compose up --scale worker=3`):
o FOR UPDATE SKIP LOCKED garante que dois workers nunca pegam o mesmo pedido.
"""

import logging
import signal
import threading

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logger import setup_logging
from app.modules import import_all_models
from app.modules.orders.internal_client import InternalSystemClient
from app.modules.orders.processor import OrderProcessor

logger = logging.getLogger("app.worker")


def main() -> None:
    setup_logging()
    # O processor já registra cada envio com o resultado; o log por request do httpx só duplicaria
    logging.getLogger("httpx").setLevel(logging.WARNING)
    import_all_models()

    processor = OrderProcessor(
        SessionLocal,
        InternalSystemClient(settings.internal_system_url, settings.internal_system_timeout_seconds),
    )

    stop = threading.Event()

    def request_stop(signum: int, _frame: object) -> None:
        logger.info("Sinal %s recebido; encerrando após o ciclo atual", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    logger.info(
        "Worker de pedidos iniciado (sistema interno: %s, lote: %s, intervalo: %ss)",
        settings.internal_system_url,
        settings.worker_batch_size,
        settings.worker_poll_seconds,
    )
    while not stop.is_set():
        try:
            handled = processor.run_once()
        except Exception:
            # Ex.: banco fora do ar. Espera e tenta de novo, sem derrubar o worker.
            logger.exception("Erro no ciclo do worker")
            handled = 0
        if handled == 0:
            stop.wait(settings.worker_poll_seconds)
    logger.info("Worker de pedidos encerrado")


if __name__ == "__main__":
    main()
