"""Recebimento (webhook), validação, idempotência e consulta de pedidos."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.orders.model import Order, OrderStatus
from app.modules.orders.repository import OrderRepository

VALID = {"externalId": "ORDER-123", "customer": "Cliente Exemplo", "amount": 150.00}


def count_orders(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Order))


# ---------- 2.1 recebimento ----------


def test_receive_order_returns_202_and_stores_as_received(client: TestClient, db: Session) -> None:
    response = client.post("/api/orders", json=VALID)

    assert response.status_code == 202
    body = response.json()
    assert body["externalId"] == "ORDER-123"
    assert body["customer"] == "Cliente Exemplo"
    assert body["amount"] == "150.00"
    assert body["status"] == "RECEIVED"
    assert body["attempts"] == 0
    assert response.headers["Location"] == f"/api/orders/{body['id']}"
    assert "Idempotent-Replayed" not in response.headers

    order = db.get(Order, body["id"])
    assert order.status == OrderStatus.RECEIVED
    assert count_orders(db) == 1


def test_receive_trims_text_and_ignores_extra_fields(client: TestClient) -> None:
    response = client.post(
        "/api/orders",
        json={"externalId": "  ORDER-9  ", "customer": "  Maria  ", "amount": "10.5", "extra": "x"},
    )
    assert response.status_code == 202
    assert response.json()["externalId"] == "ORDER-9"
    assert response.json()["customer"] == "Maria"
    assert response.json()["amount"] == "10.50"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"customer": "Cliente", "amount": 10}, "externalId"),
        ({**VALID, "externalId": ""}, "externalId"),
        ({**VALID, "externalId": "ORDER 123"}, "externalId"),
        ({**VALID, "externalId": "X" * 101}, "externalId"),
        ({**VALID, "customer": "   "}, "customer"),
        ({"externalId": "ORDER-1", "amount": 10}, "customer"),
        ({**VALID, "amount": 0}, "amount"),
        ({**VALID, "amount": -5}, "amount"),
        ({**VALID, "amount": 10.123}, "amount"),
        ({**VALID, "amount": "abc"}, "amount"),
        ({**VALID, "amount": 10**13}, "amount"),
        ({"externalId": "ORDER-1", "customer": "Cliente"}, "amount"),
    ],
)
def test_invalid_payload_returns_422(client: TestClient, db: Session, payload: dict, field: str) -> None:
    response = client.post("/api/orders", json=payload)

    assert response.status_code == 422
    assert any(error["loc"][-1] == field for error in response.json()["detail"])
    assert count_orders(db) == 0


# ---------- 2.2 idempotência ----------


def test_same_external_id_twice_does_not_duplicate(client: TestClient, db: Session) -> None:
    first = client.post("/api/orders", json=VALID)
    second = client.post("/api/orders", json={**VALID, "amount": "150"})  # mesmo valor, outro formato

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.headers["Idempotent-Replayed"] == "true"
    assert second.json()["id"] == first.json()["id"]
    assert count_orders(db) == 1


def test_same_external_id_with_different_data_returns_409(client: TestClient, db: Session) -> None:
    client.post("/api/orders", json=VALID)

    response = client.post("/api/orders", json={**VALID, "amount": 999})

    assert response.status_code == 409
    assert response.json()["code"] == "EXTERNAL_ID_CONFLICT"
    assert count_orders(db) == 1


def test_concurrent_duplicate_is_caught_by_unique_constraint(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simula duas requisições simultâneas: a segunda não vê o pedido na busca inicial,
    tenta inserir e é barrada pela constraint UNIQUE."""
    client.post("/api/orders", json=VALID)
    original = OrderRepository.get_by_external_id
    calls = {"n": 0}

    def not_found_first_time(self: OrderRepository, external_id: str):
        calls["n"] += 1
        return None if calls["n"] == 1 else original(self, external_id)

    monkeypatch.setattr(OrderRepository, "get_by_external_id", not_found_first_time)

    response = client.post("/api/orders", json=VALID)

    assert response.status_code == 200
    assert response.headers["Idempotent-Replayed"] == "true"
    assert count_orders(db) == 1


# ---------- autenticação do webhook ----------


def test_webhook_key_is_required_when_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "orders_webhook_key", "segredo-do-webhook")

    missing = client.post("/api/orders", json=VALID)
    wrong = client.post("/api/orders", json=VALID, headers={"X-Webhook-Key": "errada"})
    right = client.post("/api/orders", json=VALID, headers={"X-Webhook-Key": "segredo-do-webhook"})

    assert missing.status_code == 401
    assert missing.json()["code"] == "INVALID_WEBHOOK_KEY"
    assert wrong.status_code == 401
    assert right.status_code == 202


# ---------- 2.4 consulta ----------


def test_queries_require_login(client: TestClient) -> None:
    assert client.get("/api/orders").status_code == 401
    assert client.get("/api/orders/stats").status_code == 401
    assert client.get("/api/orders/1").status_code == 401


def test_list_orders_with_filters(logged_client: TestClient, db: Session) -> None:
    for external_id, customer in [("A-1", "Ana"), ("B-2", "Bruno"), ("C-3", "Ana Paula")]:
        logged_client.post("/api/orders", json={"externalId": external_id, "customer": customer, "amount": 10})
    db.get(Order, 2).status = OrderStatus.PROCESSING
    db.commit()

    everything = logged_client.get("/api/orders").json()
    assert everything["total"] == 3
    assert [o["externalId"] for o in everything["items"]] == ["C-3", "B-2", "A-1"]  # mais recente primeiro

    processing = logged_client.get("/api/orders", params={"status": "PROCESSING"}).json()
    assert [o["externalId"] for o in processing["items"]] == ["B-2"]

    by_customer = logged_client.get("/api/orders", params={"search": "ana"}).json()
    assert by_customer["total"] == 2

    paged = logged_client.get("/api/orders", params={"size": 2, "page": 2}).json()
    assert [o["externalId"] for o in paged["items"]] == ["A-1"]

    assert logged_client.get("/api/orders", params={"status": "INVALIDO"}).status_code == 422


def test_order_detail_and_404(logged_client: TestClient) -> None:
    created = logged_client.post("/api/orders", json=VALID).json()

    detail = logged_client.get(f"/api/orders/{created['id']}")

    assert detail.status_code == 200
    assert detail.json()["externalId"] == "ORDER-123"
    assert detail.json()["history"] == []
    assert logged_client.get("/api/orders/999").status_code == 404


def test_stats_counts_by_status(logged_client: TestClient, db: Session) -> None:
    for i in range(3):
        logged_client.post("/api/orders", json={**VALID, "externalId": f"ORDER-{i}"})
    db.get(Order, 1).status = OrderStatus.PROCESSING
    db.get(Order, 2).status = OrderStatus.FAILED
    db.commit()

    assert logged_client.get("/api/orders/stats").json() == {
        "received": 1,
        "processing": 1,
        "processed": 0,
        "failed": 1,
        "total": 3,
    }
