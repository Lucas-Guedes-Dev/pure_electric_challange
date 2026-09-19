"""Tempo real: broker de eventos e subscription `orderUpdated` via WebSocket."""

import asyncio
import threading
import time
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.modules.auth.model import UserSession
from app.modules.orders.dtos import OrderCreateDTO
from app.modules.orders.events import OrderEvent, OrderEventBroker, order_event_broker
from app.modules.orders.model import Order, OrderStatus
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderService
from app.shared.clock import utcnow

PROTOCOL = ["graphql-transport-ws"]


# ---------- broker ----------


def test_event_json_roundtrip() -> None:
    event = OrderEvent(order_id=7, external_id="ORDER-7", status=OrderStatus.PROCESSED)
    assert OrderEvent.from_json(event.to_json()) == event


def test_broker_delivers_to_all_subscribers_even_from_other_threads() -> None:
    broker = OrderEventBroker()
    event = OrderEvent(order_id=1, external_id="ORDER-1", status=OrderStatus.RECEIVED)

    async def scenario() -> list[OrderEvent]:
        async with broker.subscribe() as first, broker.subscribe() as second:
            assert broker.subscriber_count == 2
            # O listener do Postgres e os testes publicam de outras threads
            threading.Thread(target=broker.publish, args=(event,)).start()
            return [await asyncio.wait_for(q.get(), 1) for q in (first, second)]

    assert asyncio.run(scenario()) == [event, event]
    assert broker.subscriber_count == 0  # saiu do `async with`, desinscreveu


def test_slow_subscriber_drops_events_without_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    broker = OrderEventBroker()
    monkeypatch.setattr(OrderEventBroker, "QUEUE_SIZE", 2)

    async def scenario() -> int:
        async with broker.subscribe() as queue:
            for i in range(5):
                broker.publish(OrderEvent(order_id=i, external_id=f"O-{i}", status=OrderStatus.RECEIVED))
            await asyncio.sleep(0.05)
            return queue.qsize()

    assert asyncio.run(scenario()) == 2


# ---------- subscription via WebSocket ----------


def create_order(db: Session, external_id: str) -> int:
    payload = OrderCreateDTO(externalId=external_id, customer="Cliente", amount=Decimal("10"))
    return OrderService(OrderRepository(db)).receive(payload).order.id


def publish_when_subscribed(event: OrderEvent) -> None:
    """A subscription se registra no broker de forma assíncrona: espera ela entrar."""
    deadline = time.monotonic() + 3
    while order_event_broker.subscriber_count == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    order_event_broker.publish(event)


def connect(client: TestClient, **headers: str):
    return client.websocket_connect("/api/graphql", subprotocols=PROTOCOL, headers=headers)


def start(ws, query: str, variables: dict | None = None) -> None:
    ws.send_json({"type": "connection_init"})
    assert ws.receive_json()["type"] == "connection_ack"
    ws.send_json({"id": "1", "type": "subscribe", "payload": {"query": query, "variables": variables or {}}})


def test_subscription_pushes_order_updates(logged_client: TestClient, db: Session) -> None:
    order_id = create_order(db, "ORDER-1")
    order = db.get(Order, order_id)
    order.status = OrderStatus.PROCESSED
    order.internal_reference = "INT-1"
    db.commit()

    with connect(logged_client) as ws:
        start(ws, "subscription { orderUpdated { id externalId status internalReference history { number } } }")
        publish_when_subscribed(OrderEvent(order_id=order_id, external_id="ORDER-1", status=OrderStatus.PROCESSED))

        message = ws.receive_json()

    assert message["type"] == "next"
    assert message["payload"]["data"]["orderUpdated"] == {
        "id": str(order_id),
        "externalId": "ORDER-1",
        "status": "PROCESSED",  # estado lido do banco, não do evento
        "internalReference": "INT-1",
        "history": [],
    }


def test_subscription_filters_by_id(logged_client: TestClient, db: Session) -> None:
    first, second = create_order(db, "ORDER-1"), create_order(db, "ORDER-2")

    with connect(logged_client) as ws:
        start(ws, "subscription($id: ID) { orderUpdated(id: $id) { externalId } }", {"id": str(second)})
        publish_when_subscribed(OrderEvent(order_id=first, external_id="ORDER-1", status=OrderStatus.RECEIVED))
        order_event_broker.publish(OrderEvent(order_id=second, external_id="ORDER-2", status=OrderStatus.RECEIVED))

        message = ws.receive_json()

    assert message["payload"]["data"]["orderUpdated"]["externalId"] == "ORDER-2"


def test_subscription_requires_login(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as closed:
        with connect(client) as ws:
            ws.send_json({"type": "connection_init"})
            ws.receive_json()
    assert closed.value.code == 4403


def test_subscription_rejects_foreign_origin(logged_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as closed:
        with connect(logged_client, origin="https://site-malicioso.com") as ws:
            ws.send_json({"type": "connection_init"})
            ws.receive_json()
    assert closed.value.code == 4403


def test_subscription_ends_when_session_expires(
    logged_client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "session_events_poll_seconds", 0.05)

    with connect(logged_client) as ws:
        start(ws, "subscription { orderUpdated { id } }")
        deadline = time.monotonic() + 3
        while order_event_broker.subscriber_count == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        session = db.scalars(select(UserSession)).first()
        session.last_activity_at = utcnow() - timedelta(minutes=settings.session_idle_timeout_minutes + 1)
        db.commit()

        message = ws.receive_json()

    assert message["type"] in ("next", "error")
    errors = message["payload"]["errors"] if message["type"] == "next" else message["payload"]
    assert errors[0]["extensions"]["code"] == "SESSION_EXPIRED"
