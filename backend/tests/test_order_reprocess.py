"""Reprocessamento manual de pedidos que terminaram em FAILED (REST e GraphQL)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.orders.dtos import OrderCreateDTO
from app.modules.orders.internal_client import DispatchResult, OrderDispatch
from app.modules.orders.model import AttemptOutcome, Order, OrderStatus
from app.modules.orders.processor import OrderProcessor
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderService
from app.modules.users.model import UserRole
from app.shared.clock import as_utc, utcnow
from tests.conftest import PASSWORD, TestingSessionLocal

SUCCESS = DispatchResult(AttemptOutcome.SUCCESS, reference="INT-0001")
TRANSIENT = DispatchResult(AttemptOutcome.TRANSIENT_ERROR, "Sistema interno indisponível (HTTP 503)")
PERMANENT = DispatchResult(AttemptOutcome.PERMANENT_ERROR, "Pedido recusado (HTTP 422)")

GRAPHQL_URL = "/api/graphql"
REPROCESS = """
mutation Reprocess($id: ID!, $reason: String) {
  reprocessOrder(id: $id, reason: $reason) { id status cycle attempts lastError }
}
"""
DETAIL = """
query Detail($id: ID!) {
  order(id: $id) {
    status cycle
    history { number cycle outcome }
    reprocesses { number cycle requestedBy reason previousError }
  }
}
"""


class FakeInternalSystem:
    def __init__(self, *results: DispatchResult) -> None:
        self.results = list(results)
        self.calls: list[OrderDispatch] = []

    def send(self, order: OrderDispatch) -> DispatchResult:
        self.calls.append(order)
        return self.results.pop(0)


def receive(db: Session, external_id: str = "ORDER-1") -> int:
    payload = OrderCreateDTO(externalId=external_id, customer="Cliente", amount=Decimal("150.00"))
    return OrderService(OrderRepository(db)).receive(payload).order.id


def reload(db: Session, order_id: int) -> Order:
    db.expire_all()
    return db.get(Order, order_id)


def make_due(db: Session, order_id: int) -> None:
    order = reload(db, order_id)
    order.next_attempt_at = utcnow() - timedelta(seconds=1)
    db.commit()


def run_until_done(db: Session, order_id: int, worker: OrderProcessor) -> None:
    """Roda o worker até o pedido chegar a PROCESSED ou FAILED (sem esperar o backoff)."""
    for _ in range(settings.order_max_attempts + 1):
        worker.run_once()
        if reload(db, order_id).status in (OrderStatus.PROCESSED, OrderStatus.FAILED):
            return
        make_due(db, order_id)


def failed_order(db: Session, external_id: str = "ORDER-1", result: DispatchResult = PERMANENT) -> int:
    order_id = receive(db, external_id)
    run_until_done(db, order_id, OrderProcessor(TestingSessionLocal, FakeInternalSystem(result)))
    assert reload(db, order_id).status == OrderStatus.FAILED
    return order_id


def gql(client: TestClient, query: str, variables: dict) -> dict:
    response = client.post(GRAPHQL_URL, json={"query": query, "variables": variables})
    assert response.status_code == 200, response.text
    return response.json()


def error_codes(body: dict) -> list[str]:
    return [error.get("extensions", {}).get("code") for error in body.get("errors", [])]


# ---------- REST ----------


def test_failed_order_goes_back_to_the_queue(logged_client: TestClient, db: Session) -> None:
    order_id = failed_order(db)

    response = logged_client.post(
        f"/api/orders/{order_id}/reprocess", json={"reason": "Cadastro do cliente liberado"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "RECEIVED"
    assert body["cycle"] == 2
    assert body["attempts"] == 1  # total de envios é mantido
    assert body["lastError"] is None
    assert body["finishedAt"] is None

    detail = logged_client.get(f"/api/orders/{order_id}").json()
    assert len(detail["history"]) == 1  # histórico anterior preservado
    [reprocess] = detail["reprocesses"]
    assert reprocess["number"] == 1
    assert reprocess["cycle"] == 2
    assert reprocess["requestedBy"] == "Admin"
    assert reprocess["reason"] == "Cadastro do cliente liberado"
    assert reprocess["previousError"] == PERMANENT.message


def test_reason_is_optional(logged_client: TestClient, db: Session) -> None:
    order_id = failed_order(db)

    assert logged_client.post(f"/api/orders/{order_id}/reprocess").status_code == 202

    [reprocess] = logged_client.get(f"/api/orders/{order_id}").json()["reprocesses"]
    assert reprocess["reason"] is None


def test_blank_reason_is_stored_as_none(logged_client: TestClient, db: Session) -> None:
    order_id = failed_order(db)

    logged_client.post(f"/api/orders/{order_id}/reprocess", json={"reason": "   "})

    [reprocess] = logged_client.get(f"/api/orders/{order_id}").json()["reprocesses"]
    assert reprocess["reason"] is None


def test_reason_is_limited(logged_client: TestClient, db: Session) -> None:
    order_id = failed_order(db)

    response = logged_client.post(f"/api/orders/{order_id}/reprocess", json={"reason": "x" * 501})

    assert response.status_code == 422
    assert reload(db, order_id).status == OrderStatus.FAILED


@pytest.mark.parametrize("status", [OrderStatus.RECEIVED, OrderStatus.PROCESSING, OrderStatus.PROCESSED])
def test_only_failed_orders_can_be_reprocessed(
    logged_client: TestClient, db: Session, status: OrderStatus
) -> None:
    order_id = receive(db)
    order = reload(db, order_id)
    order.status = status
    db.commit()

    response = logged_client.post(f"/api/orders/{order_id}/reprocess")

    assert response.status_code == 409
    assert response.json()["code"] == "ORDER_NOT_REPROCESSABLE"
    order = reload(db, order_id)
    assert order.status == status
    assert order.reprocesses == []


def test_second_request_does_not_reprocess_again(logged_client: TestClient, db: Session) -> None:
    # Dois cliques: o primeiro devolve à fila, o segundo já encontra RECEIVED
    order_id = failed_order(db)

    first = logged_client.post(f"/api/orders/{order_id}/reprocess")
    second = logged_client.post(f"/api/orders/{order_id}/reprocess")

    assert first.status_code == 202
    assert second.status_code == 409
    order = reload(db, order_id)
    assert order.cycle == 2
    assert len(order.reprocesses) == 1


def test_unknown_order_is_404(logged_client: TestClient) -> None:
    response = logged_client.post("/api/orders/999/reprocess")

    assert response.status_code == 404


def test_reprocess_requires_login(client: TestClient, db: Session) -> None:
    order_id = failed_order(db)

    assert client.post(f"/api/orders/{order_id}/reprocess").status_code == 401
    assert reload(db, order_id).status == OrderStatus.FAILED


def test_reprocess_requires_admin(client: TestClient, db: Session, make_user) -> None:
    order_id = failed_order(db)
    make_user("operador", role=UserRole.USER)
    client.post("/api/auth/login", json={"username": "operador", "password": PASSWORD})

    response = client.post(f"/api/orders/{order_id}/reprocess")

    assert response.status_code == 403
    assert reload(db, order_id).status == OrderStatus.FAILED


# ---------- worker depois do reprocessamento ----------


def test_reprocessed_order_gets_a_new_round_of_attempts(logged_client: TestClient, db: Session) -> None:
    # Rodada 1: tentativas esgotadas por indisponibilidade
    order_id = receive(db)
    first_round = FakeInternalSystem(*[TRANSIENT] * settings.order_max_attempts)
    run_until_done(db, order_id, OrderProcessor(TestingSessionLocal, first_round))
    order = reload(db, order_id)
    assert order.status == OrderStatus.FAILED
    assert order.attempts == settings.order_max_attempts

    logged_client.post(f"/api/orders/{order_id}/reprocess")
    # Rodada 2: mais uma falha temporária e depois sucesso
    fake = FakeInternalSystem(TRANSIENT, SUCCESS)
    run_until_done(db, order_id, OrderProcessor(TestingSessionLocal, fake))

    order = reload(db, order_id)
    assert order.status == OrderStatus.PROCESSED
    assert order.cycle == 2
    assert order.cycle_attempts == 2
    assert order.attempts == settings.order_max_attempts + 2
    # Histórico continua numerado e separado por rodada
    history = [(a.number, a.cycle) for a in order.processing_attempts]
    round_one = [(n, 1) for n in range(1, settings.order_max_attempts + 1)]
    assert history == round_one + [(settings.order_max_attempts + 1, 2), (settings.order_max_attempts + 2, 2)]
    assert [call.attempt for call in fake.calls] == [settings.order_max_attempts + 1, settings.order_max_attempts + 2]
    assert all(call.cycle == 2 for call in fake.calls)


def test_reprocessed_order_can_fail_again(logged_client: TestClient, db: Session) -> None:
    order_id = failed_order(db)

    logged_client.post(f"/api/orders/{order_id}/reprocess")
    run_until_done(db, order_id, OrderProcessor(TestingSessionLocal, FakeInternalSystem(PERMANENT)))

    order = reload(db, order_id)
    assert order.status == OrderStatus.FAILED
    assert order.last_error == PERMANENT.message
    # E pode ser reprocessado de novo
    assert logged_client.post(f"/api/orders/{order_id}/reprocess").json()["cycle"] == 3


def test_backoff_counts_only_the_current_round(logged_client: TestClient, db: Session) -> None:
    order_id = receive(db)
    run_until_done(
        db, order_id, OrderProcessor(TestingSessionLocal, FakeInternalSystem(*[TRANSIENT] * settings.order_max_attempts))
    )
    logged_client.post(f"/api/orders/{order_id}/reprocess")

    OrderProcessor(TestingSessionLocal, FakeInternalSystem(TRANSIENT)).run_once()

    order = reload(db, order_id)
    assert order.status == OrderStatus.PROCESSING
    assert order.cycle_attempts == 1
    # 1ª tentativa da rodada nova: espera o tempo base, não o de uma 4ª tentativa
    delay = (as_utc(order.next_attempt_at) - utcnow()).total_seconds()
    assert settings.order_retry_base_seconds - 1 < delay <= settings.order_retry_base_seconds


# ---------- GraphQL ----------


def test_reprocess_mutation(logged_client: TestClient, db: Session) -> None:
    order_id = failed_order(db)

    body = gql(logged_client, REPROCESS, {"id": str(order_id), "reason": "Teste"})

    assert "errors" not in body
    assert body["data"]["reprocessOrder"] == {
        "id": str(order_id), "status": "RECEIVED", "cycle": 2, "attempts": 1, "lastError": None
    }
    detail = gql(logged_client, DETAIL, {"id": str(order_id)})["data"]["order"]
    assert detail["history"] == [{"number": 1, "cycle": 1, "outcome": "PERMANENT_ERROR"}]
    assert detail["reprocesses"] == [{
        "number": 1, "cycle": 2, "requestedBy": "Admin", "reason": "Teste", "previousError": PERMANENT.message
    }]


def test_reprocess_mutation_uses_rest_error_codes(logged_client: TestClient, db: Session) -> None:
    order_id = receive(db)  # ainda RECEIVED

    assert error_codes(gql(logged_client, REPROCESS, {"id": str(order_id)})) == ["ORDER_NOT_REPROCESSABLE"]
    assert error_codes(gql(logged_client, REPROCESS, {"id": "999"})) == ["NOT_FOUND"]


def test_reprocess_mutation_requires_admin(client: TestClient, db: Session, make_user) -> None:
    order_id = failed_order(db)
    assert error_codes(gql(client, REPROCESS, {"id": str(order_id)})) == ["NOT_AUTHENTICATED"]

    make_user("operador", role=UserRole.USER)
    client.post("/api/auth/login", json={"username": "operador", "password": PASSWORD})

    assert error_codes(gql(client, REPROCESS, {"id": str(order_id)})) == ["FORBIDDEN"]
    assert reload(db, order_id).status == OrderStatus.FAILED
