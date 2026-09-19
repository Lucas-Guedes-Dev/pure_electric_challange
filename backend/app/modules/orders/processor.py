"""Consumer: regras de processamento dos pedidos, usadas pelo worker.

Cada ciclo:
1. `claim_batch`: numa transação curta, reserva os pedidos prontos (FOR UPDATE SKIP LOCKED),
   passa para PROCESSING, soma a tentativa e grava uma reserva (`locked_until` + `lease_token`).
2. `process`: fora de transação, envia cada pedido ao sistema interno e grava o resultado,
   mas só se a reserva ainda for deste worker.

Se o worker morrer entre 1 e 2, a reserva vence e outro worker retoma o pedido.

O limite de tentativas e o backoff contam só a rodada atual (`cycle_attempts`): um pedido
reprocessado ganha tentativas novas. `attempts` é o total e numera o histórico.
"""

import logging
import time
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.modules.orders.events import publish_order_event
from app.modules.orders.internal_client import DispatchResult, InternalSystem, OrderDispatch
from app.modules.orders.model import AttemptOutcome, Order, OrderAttempt, OrderStatus
from app.modules.orders.repository import OrderRepository
from app.shared.clock import utcnow

logger = logging.getLogger(__name__)


def retry_delay(attempt: int) -> timedelta:
    """Backoff exponencial pela tentativa da rodada: base, 2x base, 4x base..."""
    return timedelta(seconds=settings.order_retry_base_seconds * 2 ** (attempt - 1))


def _labels(order_id: int, external_id: str, **extra: object) -> dict:
    return {"ecs": {"labels": {"order_id": order_id, "external_id": external_id, **extra}}}


class OrderProcessor:
    def __init__(self, session_factory: sessionmaker[Session], internal_system: InternalSystem) -> None:
        self.session_factory = session_factory
        self.internal_system = internal_system

    def claim_batch(self) -> list[tuple[OrderDispatch, str]]:
        """Reserva até `worker_batch_size` pedidos. Devolve (dados do envio, token da reserva)."""
        now = utcnow()
        claimed: list[tuple[OrderDispatch, str]] = []
        with self.session_factory() as db:
            for order in OrderRepository(db).lock_ready_for_processing(now, settings.worker_batch_size):
                if order.cycle_attempts >= settings.order_max_attempts:
                    # Só acontece se um worker morreu durante a última tentativa
                    self._finish(order, OrderStatus.FAILED, now)
                    order.last_error = (
                        f"Processamento interrompido na tentativa {order.cycle_attempts} "
                        f"(de {settings.order_max_attempts}); tentativas esgotadas"
                    )
                    logger.error("Pedido %s falhou: tentativas esgotadas", order.external_id,
                                 extra=_labels(order.id, order.external_id))
                    publish_order_event(db, order)
                    continue

                order.transition_to(OrderStatus.PROCESSING)
                order.attempts += 1
                order.cycle_attempts += 1
                order.locked_until = now + timedelta(seconds=settings.order_lease_seconds)
                order.lease_token = str(uuid.uuid4())
                publish_order_event(db, order)
                claimed.append((
                    OrderDispatch(
                        order_id=order.id,
                        external_id=order.external_id,
                        customer=order.customer,
                        amount=order.amount,
                        attempt=order.attempts,
                        cycle=order.cycle,
                    ),
                    order.lease_token,
                ))
            db.commit()
        return claimed

    def process(self, dispatch: OrderDispatch, lease_token: str) -> None:
        started_at = utcnow()
        start = time.perf_counter()
        result = self.internal_system.send(dispatch)
        duration_ms = int((time.perf_counter() - start) * 1000)
        finished_at = utcnow()

        with self.session_factory() as db:
            order = db.get(Order, dispatch.order_id, with_for_update=True)
            if order is None or order.lease_token != lease_token:
                # A reserva venceu e outro worker assumiu: ele é quem grava o resultado
                logger.warning("Reserva do pedido %s perdida; resultado descartado", dispatch.external_id,
                               extra=_labels(dispatch.order_id, dispatch.external_id))
                return

            db.add(OrderAttempt(
                order_id=order.id,
                number=dispatch.attempt,
                cycle=dispatch.cycle,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                outcome=result.outcome,
                message=result.message,
            ))
            self._apply_result(order, result, finished_at)
            publish_order_event(db, order)
            db.commit()

    def _apply_result(self, order: Order, result: DispatchResult, now) -> None:
        labels = _labels(
            order.id, order.external_id, attempt=order.attempts, cycle=order.cycle, outcome=result.outcome.value
        )

        if result.outcome == AttemptOutcome.SUCCESS:
            self._finish(order, OrderStatus.PROCESSED, now)
            order.internal_reference = result.reference
            order.last_error = None
            logger.info("Pedido %s processado (%s)", order.external_id, result.reference, extra=labels)
            return

        order.last_error = result.message
        can_retry = (
            result.outcome == AttemptOutcome.TRANSIENT_ERROR
            and order.cycle_attempts < settings.order_max_attempts
        )
        if can_retry:
            order.transition_to(OrderStatus.PROCESSING)
            order.next_attempt_at = now + retry_delay(order.cycle_attempts)
            order.locked_until = None
            order.lease_token = None
            logger.warning("Pedido %s: falha temporária na tentativa %s, nova tentativa em %s",
                           order.external_id, order.attempts, order.next_attempt_at.isoformat(), extra=labels)
            return

        if result.outcome == AttemptOutcome.TRANSIENT_ERROR:
            order.last_error = f"{result.message}. Tentativas esgotadas ({order.cycle_attempts})"
        self._finish(order, OrderStatus.FAILED, now)
        logger.error("Pedido %s falhou: %s", order.external_id, order.last_error, extra=labels)

    @staticmethod
    def _finish(order: Order, status: OrderStatus, now) -> None:
        order.transition_to(status)
        order.finished_at = now
        order.locked_until = None
        order.lease_token = None

    def run_once(self) -> int:
        """Um ciclo do worker. Devolve quantos pedidos foram pegos."""
        claimed = self.claim_batch()
        for dispatch, lease_token in claimed:
            try:
                self.process(dispatch, lease_token)
            except Exception:
                # Erro inesperado (ex.: banco caiu): o pedido fica reservado até a reserva
                # vencer e então é retomado. Os demais pedidos do lote seguem.
                logger.exception("Erro inesperado ao processar o pedido %s", dispatch.external_id,
                                 extra=_labels(dispatch.order_id, dispatch.external_id))
        return len(claimed)
