"""Consumer/worker: processamento assíncrono, estados, retentativas e falhas."""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.orders.dtos import OrderCreateDTO
from app.modules.orders.internal_client import DispatchResult, OrderDispatch
from app.modules.orders.model import (
    AttemptOutcome,
    InvalidStatusTransition,
    Order,
    OrderStatus,
)
from app.modules.orders.processor import OrderProcessor, retry_delay
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderService
from app.shared.clock import as_utc, utcnow
from tests.conftest import TestingSessionLocal

SUCCESS = DispatchResult(AttemptOutcome.SUCCESS, reference="INT-0001")
TRANSIENT = DispatchResult(AttemptOutcome.TRANSIENT_ERROR, "Sistema interno indisponível (HTTP 503)")
PERMANENT = DispatchResult(AttemptOutcome.PERMANENT_ERROR, "Pedido recusado (HTTP 422)")


class FakeInternalSystem:
    """Sistema interno falso: devolve os resultados na ordem e registra as chamadas."""

    def __init__(self, *results: DispatchResult) -> None:
        self.results = list(results)
        self.calls: list[OrderDispatch] = []

    def send(self, order: OrderDispatch) -> DispatchResult:
        self.calls.append(order)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def receive(db: Session):
    def _receive(external_id: str = "ORDER-1", amount: str = "150.00") -> int:
        payload = OrderCreateDTO(externalId=external_id, customer="Cliente", amount=Decimal(amount))
        return OrderService(OrderRepository(db)).receive(payload).order.id

    return _receive


def reload(db: Session, order_id: int) -> Order:
    db.expire_all()
    return db.get(Order, order_id)


def make_due(db: Session, order_id: int) -> None:
    """Simula a passagem do tempo até a próxima tentativa."""
    order = reload(db, order_id)
    order.next_attempt_at = utcnow() - timedelta(seconds=1)
    db.commit()


def processor(*results: DispatchResult) -> tuple[OrderProcessor, FakeInternalSystem]:
    fake = FakeInternalSystem(*results)
    return OrderProcessor(TestingSessionLocal, fake), fake


# ---------- fluxo feliz ----------


def test_received_order_is_processed(db: Session, receive) -> None:
    order_id = receive()
    worker, fake = processor(SUCCESS)

    assert worker.run_once() == 1

    order = reload(db, order_id)
    assert order.status == OrderStatus.PROCESSED
    assert order.internal_reference == "INT-0001"
    assert order.attempts == 1
    assert order.finished_at is not None
    assert order.locked_until is None and order.lease_token is None
    assert [a.outcome for a in order.processing_attempts] == [AttemptOutcome.SUCCESS]
    assert fake.calls[0].external_id == "ORDER-1"
    assert fake.calls[0].amount == Decimal("150.00")


def test_claim_moves_to_processing_before_calling_internal_system(db: Session, receive) -> None:
    order_id = receive()
    worker, _ = processor()

    claimed = worker.claim_batch()

    assert len(claimed) == 1
    order = reload(db, order_id)
    assert order.status == OrderStatus.PROCESSING
    assert order.attempts == 1
    assert as_utc(order.locked_until) > utcnow()


# ---------- falhas ----------


def test_permanent_error_fails_without_retry(db: Session, receive) -> None:
    order_id = receive()
    worker, fake = processor(PERMANENT)

    worker.run_once()

    order = reload(db, order_id)
    assert order.status == OrderStatus.FAILED
    assert order.last_error == "Pedido recusado (HTTP 422)"
    assert order.finished_at is not None
    assert worker.run_once() == 0  # não volta para a fila
    assert len(fake.calls) == 1


def test_transient_error_schedules_retry_with_backoff(db: Session, receive) -> None:
    order_id = receive()
    worker, _ = processor(TRANSIENT)

    worker.run_once()

    order = reload(db, order_id)
    assert order.status == OrderStatus.PROCESSING
    assert order.attempts == 1
    assert order.last_error == TRANSIENT.message
    assert order.locked_until is None
    delay = (as_utc(order.next_attempt_at) - utcnow()).total_seconds()
    assert settings.order_retry_base_seconds - 1 < delay <= settings.order_retry_base_seconds
    # Antes do prazo, o worker não pega de novo
    assert worker.run_once() == 0


def test_transient_error_then_success(db: Session, receive) -> None:
    order_id = receive()
    worker, fake = processor(TRANSIENT, SUCCESS)

    worker.run_once()
    make_due(db, order_id)
    worker.run_once()

    order = reload(db, order_id)
    assert order.status == OrderStatus.PROCESSED
    assert order.attempts == 2
    assert order.last_error is None
    assert [a.outcome for a in order.processing_attempts] == [
        AttemptOutcome.TRANSIENT_ERROR,
        AttemptOutcome.SUCCESS,
    ]
    assert [call.attempt for call in fake.calls] == [1, 2]


def test_fails_after_max_attempts(db: Session, receive) -> None:
    order_id = receive()
    worker, fake = processor(*[TRANSIENT] * settings.order_max_attempts)

    for _ in range(settings.order_max_attempts):
        worker.run_once()
        make_due(db, order_id)

    order = reload(db, order_id)
    assert order.status == OrderStatus.FAILED
    assert order.attempts == settings.order_max_attempts
    assert "Tentativas esgotadas" in order.last_error
    assert len(order.processing_attempts) == settings.order_max_attempts
    assert worker.run_once() == 0
    assert len(fake.calls) == settings.order_max_attempts


def test_retry_delay_is_exponential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "order_retry_base_seconds", 5)
    assert [retry_delay(n).total_seconds() for n in (1, 2, 3)] == [5, 10, 20]


def test_unexpected_error_keeps_order_reserved_and_worker_alive(db: Session, receive) -> None:
    first, second = receive("ORDER-1"), receive("ORDER-2")
    fake = FakeInternalSystem(RuntimeError("bug"), SUCCESS)  # type: ignore[arg-type]
    worker = OrderProcessor(TestingSessionLocal, fake)

    assert worker.run_once() == 2  # não levanta a exceção

    assert reload(db, first).status == OrderStatus.PROCESSING  # reservado até a reserva vencer
    assert reload(db, second).status == OrderStatus.PROCESSED  # o resto do lote seguiu


# ---------- sem processamento duplicado ----------


def test_processed_order_is_never_sent_again(db: Session, receive) -> None:
    receive()
    worker, fake = processor(SUCCESS)

    worker.run_once()
    worker.run_once()
    worker.run_once()

    assert len(fake.calls) == 1


def test_reserved_order_is_not_claimed_twice(receive) -> None:
    receive()
    worker_a, _ = processor()
    worker_b, _ = processor()

    assert len(worker_a.claim_batch()) == 1
    assert worker_b.claim_batch() == []


def test_order_is_recovered_when_worker_dies(db: Session, receive) -> None:
    order_id = receive()
    dead_worker, _ = processor()
    [(dispatch, old_token)] = dead_worker.claim_batch()  # pegou e "morreu" sem responder

    order = reload(db, order_id)
    order.locked_until = utcnow() - timedelta(seconds=1)  # reserva venceu
    db.commit()

    new_worker, fake = processor(SUCCESS)
    assert new_worker.run_once() == 1

    # Se o worker antigo "voltar", o resultado dele é descartado
    dead_worker.internal_system = FakeInternalSystem(PERMANENT)
    dead_worker.process(dispatch, old_token)

    order = reload(db, order_id)
    assert order.status == OrderStatus.PROCESSED
    assert order.attempts == 2
    assert [a.number for a in order.processing_attempts] == [2]


def test_worker_dying_on_last_attempt_fails_the_order(db: Session, receive) -> None:
    order_id = receive()
    order = reload(db, order_id)
    order.status = OrderStatus.PROCESSING
    order.attempts = settings.order_max_attempts
    order.locked_until = utcnow() - timedelta(seconds=1)
    db.commit()
    worker, fake = processor()

    assert worker.run_once() == 0

    order = reload(db, order_id)
    assert order.status == OrderStatus.FAILED
    assert "tentativas esgotadas" in order.last_error
    assert fake.calls == []


# ---------- máquina de estados ----------


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.RECEIVED, OrderStatus.PROCESSED),
        (OrderStatus.RECEIVED, OrderStatus.FAILED),
        (OrderStatus.PROCESSED, OrderStatus.PROCESSING),
        (OrderStatus.PROCESSED, OrderStatus.FAILED),
        (OrderStatus.FAILED, OrderStatus.PROCESSING),
        (OrderStatus.FAILED, OrderStatus.PROCESSED),
    ],
)
def test_invalid_transitions_are_rejected(current: OrderStatus, target: OrderStatus) -> None:
    order = Order(status=current)
    with pytest.raises(InvalidStatusTransition):
        order.transition_to(target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.RECEIVED, OrderStatus.PROCESSING),
        (OrderStatus.PROCESSING, OrderStatus.PROCESSED),
        (OrderStatus.PROCESSING, OrderStatus.FAILED),
        (OrderStatus.PROCESSING, OrderStatus.PROCESSING),
    ],
)
def test_valid_transitions(current: OrderStatus, target: OrderStatus) -> None:
    order = Order(status=current)
    order.transition_to(target)
    assert order.status == target


def test_detail_shows_history_and_next_attempt(logged_client, db: Session, receive) -> None:
    order_id = receive()
    worker, _ = processor(TRANSIENT)
    worker.run_once()

    body = logged_client.get(f"/api/orders/{order_id}").json()

    assert body["status"] == "PROCESSING"
    assert body["nextAttemptAt"] is not None
    assert body["lastError"] == TRANSIENT.message
    assert body["history"][0]["outcome"] == "TRANSIENT_ERROR"
    assert body["history"][0]["number"] == 1
