"""Eventos de pedidos em tempo real.

    worker/API ──(pg_notify na MESMA transação da mudança de status)──► Postgres
    Postgres ──(LISTEN, conexão assíncrona na API)──► OrderEventBroker ──► subscriptions GraphQL

O NOTIFY só é entregue quando a transação faz commit: nunca se avisa um status que acabou
não sendo gravado. Se ninguém estiver ouvindo, o evento se perde (e tudo bem: o estado
oficial está no banco; o evento é só um "aviso de que mudou").
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.orders.model import Order, OrderStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderEvent:
    order_id: int
    external_id: str
    status: OrderStatus

    def to_json(self) -> str:
        return json.dumps({"id": self.order_id, "externalId": self.external_id, "status": self.status.value})

    @classmethod
    def from_json(cls, payload: str) -> "OrderEvent":
        data = json.loads(payload)
        return cls(order_id=int(data["id"]), external_id=data["externalId"], status=OrderStatus(data["status"]))


def publish_order_event(db: Session, order: Order) -> None:
    """Agenda o aviso de mudança do pedido. Chame ANTES do commit da transação que mudou o status.

    Fora do Postgres (ex.: SQLite dos testes) não faz nada."""
    if db.get_bind().dialect.name != "postgresql":
        return
    event = OrderEvent(order_id=order.id, external_id=order.external_id, status=order.status)
    db.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": settings.order_events_channel, "payload": event.to_json()},
    )


class OrderEventBroker:
    """Distribui os eventos para as subscriptions ativas deste processo.

    `publish` pode ser chamado de qualquer thread: a entrega é agendada no event loop de
    cada assinante. Um assinante lento não trava os outros: se a fila dele encher, os
    eventos excedentes são descartados (ele continua podendo consultar o estado atual)."""

    QUEUE_SIZE = 100

    def __init__(self) -> None:
        self._subscribers: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue[OrderEvent]]] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[OrderEvent]]:
        entry = (asyncio.get_running_loop(), asyncio.Queue[OrderEvent](maxsize=self.QUEUE_SIZE))
        self._subscribers.add(entry)
        try:
            yield entry[1]
        finally:
            self._subscribers.discard(entry)

    def publish(self, event: OrderEvent) -> None:
        for loop, queue in list(self._subscribers):
            loop.call_soon_threadsafe(self._deliver, queue, event)

    @staticmethod
    def _deliver(queue: asyncio.Queue[OrderEvent], event: OrderEvent) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Assinante lento: evento do pedido %s descartado", event.external_id)


order_event_broker = OrderEventBroker()


async def listen_order_events(broker: OrderEventBroker = order_event_broker) -> None:
    """Fica escutando o canal do Postgres e repassa ao broker. Reconecta sozinho se a
    conexão cair. Roda como tarefa de fundo durante a vida da API (lifespan)."""
    import psycopg  # import tardio: só a API precisa, o worker não

    delay = 1.0
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(
                settings.psycopg_conninfo, autocommit=True
            ) as conn:
                await conn.execute(f'LISTEN "{settings.order_events_channel}"')
                logger.info("Ouvindo eventos de pedidos no canal %s", settings.order_events_channel)
                delay = 1.0
                async for notify in conn.notifies():
                    try:
                        broker.publish(OrderEvent.from_json(notify.payload))
                    except (ValueError, KeyError):
                        logger.warning("Evento de pedido inválido ignorado: %r", notify.payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Listener de eventos de pedidos caiu; reconectando em %.0fs", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
