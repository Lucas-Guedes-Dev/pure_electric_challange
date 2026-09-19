from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import selectinload

from app.modules.orders.model import Order, OrderAttempt, OrderReprocess, OrderStatus
from app.shared.repository import BaseRepository


class OrderRepository(BaseRepository[Order]):
    model = Order

    def get_by_external_id(self, external_id: str) -> Order | None:
        return self.db.scalars(select(Order).where(Order.external_id == external_id)).first()

    def get_with_history(self, order_id: int) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.processing_attempts),
                selectinload(Order.reprocesses).selectinload(OrderReprocess.requested_by),
            )
        )
        return self.db.scalars(stmt).first()

    def get_for_update(self, order_id: int) -> Order | None:
        """Pedido travado (FOR UPDATE) até o fim da transação: duas ações simultâneas
        sobre o mesmo pedido acontecem uma depois da outra, vendo o estado já atualizado."""
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.db.scalars(stmt).first()

    def _filtered(self, stmt: Select, status: OrderStatus | None, search: str | None) -> Select:
        if status is not None:
            stmt = stmt.where(Order.status == status)
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(func.lower(Order.external_id).like(pattern), func.lower(Order.customer).like(pattern))
            )
        return stmt

    def search(
        self, *, status: OrderStatus | None, search: str | None, offset: int, limit: int
    ) -> tuple[Sequence[Order], int]:
        items_stmt = self._filtered(select(Order), status, search)
        items_stmt = items_stmt.order_by(Order.created_at.desc(), Order.id.desc()).offset(offset).limit(limit)
        count_stmt = self._filtered(select(func.count()).select_from(Order), status, search)
        return self.db.scalars(items_stmt).all(), self.db.scalar(count_stmt) or 0

    def attempts_by_order_ids(self, order_ids: list[int]) -> dict[int, list[OrderAttempt]]:
        result: dict[int, list[OrderAttempt]] = {order_id: [] for order_id in order_ids}
        stmt = (
            select(OrderAttempt)
            .where(OrderAttempt.order_id.in_(order_ids))
            .order_by(OrderAttempt.order_id, OrderAttempt.number)
        )
        for attempt in self.db.scalars(stmt):
            result[attempt.order_id].append(attempt)
        return result

    def reprocesses_by_order_ids(self, order_ids: list[int]) -> dict[int, list[OrderReprocess]]:
        result: dict[int, list[OrderReprocess]] = {order_id: [] for order_id in order_ids}
        stmt = (
            select(OrderReprocess)
            .where(OrderReprocess.order_id.in_(order_ids))
            .options(selectinload(OrderReprocess.requested_by))
            .order_by(OrderReprocess.order_id, OrderReprocess.number)
        )
        for reprocess in self.db.scalars(stmt):
            result[reprocess.order_id].append(reprocess)
        return result

    def count_by_status(self) -> dict[OrderStatus, int]:
        rows = self.db.execute(select(Order.status, func.count()).group_by(Order.status)).all()
        return {status: count for status, count in rows}

    def lock_ready_for_processing(self, now: datetime, limit: int) -> Sequence[Order]:
        """Pedidos prontos para o worker, travados com FOR UPDATE SKIP LOCKED:
        vários workers podem rodar ao mesmo tempo sem pegar o mesmo pedido.

        Pronto = RECEIVED ou PROCESSING (retentativa / worker que morreu), com
        `next_attempt_at` vencido e sem reserva ativa."""
        stmt = (
            select(Order)
            .where(
                Order.status.in_([OrderStatus.RECEIVED, OrderStatus.PROCESSING]),
                Order.next_attempt_at <= now,
                or_(Order.locked_until.is_(None), Order.locked_until < now),
            )
            .order_by(Order.next_attempt_at, Order.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return self.db.scalars(stmt).all()
