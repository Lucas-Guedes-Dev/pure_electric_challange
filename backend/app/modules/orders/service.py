import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy.exc import IntegrityError

from app.core.database import DbSession
from app.modules.orders.dtos import (
    OrderAttemptDTO,
    OrderCreateDTO,
    OrderDetailDTO,
    OrderListParamsDTO,
    OrderResponseDTO,
    OrderStatsDTO,
)
from app.modules.orders.events import publish_order_event
from app.modules.orders.model import Order, OrderStatus
from app.modules.orders.repository import OrderRepository
from app.shared.clock import as_utc, utcnow
from app.shared.dtos import PageDTO
from app.shared.exceptions import ConflictException, NotFoundException

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReceiveResult:
    order: OrderResponseDTO
    # False quando o externalId já existia (reenvio do mesmo pedido)
    created: bool


def to_response(order: Order) -> OrderResponseDTO:
    dto = OrderResponseDTO.model_validate(order)
    # `next_attempt_at` só interessa enquanto o pedido aguarda uma retentativa
    waiting_retry = (
        order.status == OrderStatus.PROCESSING and order.locked_until is None and order.attempts > 0
    )
    return dto.model_copy(
        update={"next_attempt_at": as_utc(order.next_attempt_at) if waiting_retry else None}
    )


def to_detail(order: Order) -> OrderDetailDTO:
    history = [OrderAttemptDTO.model_validate(attempt) for attempt in order.processing_attempts]
    return OrderDetailDTO.model_validate({**to_response(order).model_dump(), "history": history})


class OrderService:
    def __init__(self, repository: OrderRepository) -> None:
        self.repository = repository

    def receive(self, payload: OrderCreateDTO) -> ReceiveResult:
        """Grava o pedido em RECEIVED; o worker o processa em seguida.

        Idempotente pelo `externalId`: reenviar o mesmo pedido devolve o que já existe,
        sem criar outro nem processar de novo. Se o reenvio vier com dados diferentes,
        é um conflito (409), porque não dá para saber qual versão vale."""
        existing = self.repository.get_by_external_id(payload.external_id)
        if existing is not None:
            return self._replay(existing, payload)

        order = Order(
            external_id=payload.external_id,
            customer=payload.customer,
            amount=payload.amount,
            status=OrderStatus.RECEIVED,
            attempts=0,
            next_attempt_at=utcnow(),
        )
        db = self.repository.db
        try:
            db.add(order)
            db.flush()  # a constraint UNIQUE é checada aqui
            publish_order_event(db, order)  # sai junto com o commit do pedido
            db.commit()
            db.refresh(order)  # valores como o banco gravou (ex.: amount 150.00, datas)
        except IntegrityError:
            # Duas requisições simultâneas com o mesmo externalId: a constraint UNIQUE
            # barrou a segunda. Ela responde como reenvio do pedido que venceu.
            db.rollback()
            existing = self.repository.get_by_external_id(payload.external_id)
            if existing is None:
                raise
            return self._replay(existing, payload)

        logger.info(
            "Pedido %s recebido (id=%s)",
            order.external_id,
            order.id,
            extra={"ecs": {"labels": {"order_id": order.id, "external_id": order.external_id}}},
        )
        return ReceiveResult(order=to_response(order), created=True)

    def _replay(self, existing: Order, payload: OrderCreateDTO) -> ReceiveResult:
        if existing.customer != payload.customer or existing.amount != payload.amount:
            raise ConflictException(
                f"O pedido {payload.external_id} já foi recebido com dados diferentes "
                "(cliente ou valor). Use outro externalId para um pedido novo.",
                code="EXTERNAL_ID_CONFLICT",
            )
        logger.info(
            "Pedido %s reenviado; nenhum pedido novo criado",
            existing.external_id,
            extra={"ecs": {"labels": {"order_id": existing.id, "external_id": existing.external_id}}},
        )
        return ReceiveResult(order=to_response(existing), created=False)

    # (antes de `list`: dentro da classe, o método `list` esconderia o list() do Python)
    def get_by_external_id(self, external_id: str) -> OrderResponseDTO | None:
        order = self.repository.get_by_external_id(external_id.strip())
        return to_response(order) if order is not None else None

    def get_summary(self, order_id: int) -> OrderResponseDTO | None:
        """Pedido sem o histórico (o GraphQL carrega o histórico sob demanda)."""
        order = self.repository.get_by_id(order_id)
        return to_response(order) if order is not None else None

    def history_by_order_ids(self, order_ids: list[int]) -> dict[int, list[OrderAttemptDTO]]:
        """Histórico de vários pedidos numa consulta só (DataLoader do GraphQL)."""
        attempts = self.repository.attempts_by_order_ids(order_ids)
        return {
            order_id: [OrderAttemptDTO.model_validate(a) for a in items]
            for order_id, items in attempts.items()
        }

    def list(self, params: OrderListParamsDTO) -> PageDTO[OrderResponseDTO]:
        orders, total = self.repository.search(
            status=params.status, search=params.search, offset=params.offset, limit=params.size
        )
        return PageDTO[OrderResponseDTO](
            items=[to_response(order) for order in orders],
            total=total,
            page=params.page,
            size=params.size,
        )

    def get(self, order_id: int) -> OrderDetailDTO:
        order = self.repository.get_with_history(order_id)
        if order is None:
            raise NotFoundException(f"Pedido {order_id} não encontrado")
        return to_detail(order)

    def stats(self) -> OrderStatsDTO:
        counts = self.repository.count_by_status()
        return OrderStatsDTO(
            received=counts.get(OrderStatus.RECEIVED, 0),
            processing=counts.get(OrderStatus.PROCESSING, 0),
            processed=counts.get(OrderStatus.PROCESSED, 0),
            failed=counts.get(OrderStatus.FAILED, 0),
            total=sum(counts.values()),
        )


def get_order_service(db: DbSession) -> OrderService:
    return OrderService(OrderRepository(db))


OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]
