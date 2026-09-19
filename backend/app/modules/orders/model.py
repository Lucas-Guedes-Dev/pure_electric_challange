import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.model import Base, TimestampMixin


class OrderStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"  # gravado, aguardando o worker
    PROCESSING = "PROCESSING"  # com o worker (ou aguardando nova tentativa após falha temporária)
    PROCESSED = "PROCESSED"  # sistema interno aceitou (final)
    FAILED = "FAILED"  # sistema interno recusou ou as tentativas acabaram (final)


# Transições permitidas. PROCESSING -> PROCESSING é a retentativa após falha temporária.
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.RECEIVED: {OrderStatus.PROCESSING},
    OrderStatus.PROCESSING: {OrderStatus.PROCESSING, OrderStatus.PROCESSED, OrderStatus.FAILED},
    OrderStatus.PROCESSED: set(),
    OrderStatus.FAILED: set(),
}


class InvalidStatusTransition(Exception):
    def __init__(self, current: OrderStatus, target: OrderStatus) -> None:
        super().__init__(f"Transição inválida: {current.value} -> {target.value}")


class Order(TimestampMixin, Base):
    """Pedido recebido pelo webhook. A tabela também funciona como fila do worker:
    pedidos em RECEIVED/PROCESSING com `next_attempt_at` vencido e sem reserva
    ativa (`locked_until`) são os próximos a processar."""

    __tablename__ = "orders"
    __table_args__ = (
        # Índice da consulta do worker (claim)
        Index("ix_orders_queue", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # UNIQUE: é o que garante a idempotência mesmo com requisições simultâneas
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    customer: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), nullable=False, default=OrderStatus.RECEIVED
    )

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Reserva do worker: enquanto no futuro, nenhum outro worker pega o pedido
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Identifica a reserva atual; o worker só grava o resultado se ainda for o dono dela
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Protocolo devolvido pelo sistema interno em caso de sucesso
    internal_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    processing_attempts: Mapped[list["OrderAttempt"]] = relationship(
        back_populates="order", order_by="OrderAttempt.number", cascade="all, delete-orphan"
    )

    def transition_to(self, target: OrderStatus) -> None:
        if target not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStatusTransition(self.status, target)
        self.status = target


class AttemptOutcome(str, enum.Enum):
    SUCCESS = "SUCCESS"
    TRANSIENT_ERROR = "TRANSIENT_ERROR"  # timeout, indisponibilidade: tenta de novo
    PERMANENT_ERROR = "PERMANENT_ERROR"  # recusado pelo sistema interno: não adianta repetir


class OrderAttempt(Base):
    """Histórico de cada envio ao sistema interno (auditoria e diagnóstico de falhas)."""

    __tablename__ = "order_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[AttemptOutcome] = mapped_column(
        Enum(AttemptOutcome, name="order_attempt_outcome"), nullable=False
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[Order] = relationship(back_populates="processing_attempts")
