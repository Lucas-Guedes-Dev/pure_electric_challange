"""GraphQL de pedidos: queries, mutation, erros, limites e N+1."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.orders.dtos import OrderCreateDTO
from app.modules.orders.internal_client import DispatchResult
from app.modules.orders.model import AttemptOutcome
from app.modules.orders.processor import OrderProcessor
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderService
from tests.conftest import TestingSessionLocal, engine

URL = "/api/graphql"

RECEIVE = """
mutation Receive($input: ReceiveOrderInput!) {
  receiveOrder(input: $input) { created order { id externalId customer amount status } }
}
"""


def gql(client: TestClient, query: str, variables: dict | None = None, headers: dict | None = None) -> dict:
    response = client.post(URL, json={"query": query, "variables": variables or {}}, headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()


def error_codes(body: dict) -> list[str]:
    return [error.get("extensions", {}).get("code") for error in body.get("errors", [])]


def create_order(db: Session, external_id: str, amount: str = "10.00") -> int:
    payload = OrderCreateDTO(externalId=external_id, customer=f"Cliente {external_id}", amount=Decimal(amount))
    return OrderService(OrderRepository(db)).receive(payload).order.id


class ScriptedSystem:
    def __init__(self, *results: DispatchResult) -> None:
        self.results = list(results)

    def send(self, _order) -> DispatchResult:
        return self.results.pop(0)


# ---------- mutation (recebimento) ----------


def test_receive_order_mutation_is_idempotent(client: TestClient) -> None:
    variables = {"input": {"externalId": "ORDER-123", "customer": "Cliente Exemplo", "amount": "150.00"}}

    first = gql(client, RECEIVE, variables)["data"]["receiveOrder"]
    again = gql(client, RECEIVE, variables)["data"]["receiveOrder"]

    assert first["created"] is True
    assert first["order"] == {
        "id": first["order"]["id"],
        "externalId": "ORDER-123",
        "customer": "Cliente Exemplo",
        "amount": "150.00",
        "status": "RECEIVED",
    }
    assert again["created"] is False
    assert again["order"]["id"] == first["order"]["id"]


def test_receive_order_accepts_numeric_amount(client: TestClient) -> None:
    body = gql(client, RECEIVE, {"input": {"externalId": "ORDER-1", "customer": "Ana", "amount": 150.0}})
    assert body["data"]["receiveOrder"]["order"]["amount"] == "150.00"


def test_receive_order_conflict_uses_same_code_as_rest(client: TestClient) -> None:
    gql(client, RECEIVE, {"input": {"externalId": "ORDER-1", "customer": "Ana", "amount": "10"}})

    body = gql(client, RECEIVE, {"input": {"externalId": "ORDER-1", "customer": "Ana", "amount": "99"}})

    assert body["data"] is None
    assert error_codes(body) == ["EXTERNAL_ID_CONFLICT"]


def test_receive_order_validation_error_lists_fields(client: TestClient) -> None:
    body = gql(client, RECEIVE, {"input": {"externalId": "com espaço", "customer": " ", "amount": "-1"}})

    assert error_codes(body) == ["BAD_USER_INPUT"]
    fields = {f["field"] for f in body["errors"][0]["extensions"]["fields"]}
    assert fields == {"externalId", "customer", "amount"}


def test_receive_order_requires_webhook_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "orders_webhook_key", "segredo")
    variables = {"input": {"externalId": "ORDER-1", "customer": "Ana", "amount": "10"}}

    assert error_codes(gql(client, RECEIVE, variables)) == ["INVALID_WEBHOOK_KEY"]
    ok = gql(client, RECEIVE, variables, headers={"X-Webhook-Key": "segredo"})
    assert ok["data"]["receiveOrder"]["created"] is True


# ---------- queries ----------


def test_queries_require_login(client: TestClient) -> None:
    body = gql(client, "{ orders { total } orderStats { total } }")
    assert body["data"] is None
    assert "NOT_AUTHENTICATED" in error_codes(body)


def test_orders_query_with_filters_and_pagination(logged_client: TestClient, db: Session) -> None:
    for external_id in ("A-1", "B-2", "C-3"):
        create_order(db, external_id)

    body = gql(
        logged_client,
        """
        query($search: String) {
          all: orders { total items { externalId } }
          page2: orders(page: 2, size: 2) { page size items { externalId } }
          filtered: orders(search: $search) { total }
          received: orders(status: RECEIVED) { total }
          none: orders(status: FAILED) { total }
        }
        """,
        {"search": "b-2"},
    )["data"]

    assert [o["externalId"] for o in body["all"]["items"]] == ["C-3", "B-2", "A-1"]
    assert body["page2"] == {"page": 2, "size": 2, "items": [{"externalId": "A-1"}]}
    assert body["filtered"]["total"] == 1
    assert body["received"]["total"] == 3
    assert body["none"]["total"] == 0


def test_order_by_id_and_external_id(logged_client: TestClient, db: Session) -> None:
    order_id = create_order(db, "ORDER-9")

    body = gql(
        logged_client,
        """
        query($id: ID!) {
          byId: order(id: $id) { externalId status history { number } }
          byExternal: orderByExternalId(externalId: "ORDER-9") { id }
          missing: order(id: "999") { id }
        }
        """,
        {"id": str(order_id)},
    )["data"]

    assert body["byId"] == {"externalId": "ORDER-9", "status": "RECEIVED", "history": []}
    assert body["byExternal"]["id"] == str(order_id)
    assert body["missing"] is None


def test_invalid_id_is_bad_user_input(logged_client: TestClient) -> None:
    assert error_codes(gql(logged_client, '{ order(id: "abc") { id } }')) == ["BAD_USER_INPUT"]


def test_page_size_limit_is_enforced(logged_client: TestClient) -> None:
    body = gql(logged_client, "{ orders(size: 1000) { total } }")
    assert error_codes(body) == ["BAD_USER_INPUT"]


def test_order_stats(logged_client: TestClient, db: Session) -> None:
    create_order(db, "A-1")
    create_order(db, "FAIL-1")
    OrderProcessor(TestingSessionLocal, ScriptedSystem(
        DispatchResult(AttemptOutcome.SUCCESS, reference="INT-1"),
        DispatchResult(AttemptOutcome.PERMANENT_ERROR, "recusado"),
    )).run_once()

    body = gql(logged_client, "{ orderStats { received processing processed failed total } }")

    assert body["data"]["orderStats"] == {
        "received": 0, "processing": 0, "processed": 1, "failed": 1, "total": 2,
    }


def test_history_is_loaded_in_a_single_query(logged_client: TestClient, db: Session) -> None:
    """DataLoader: 5 pedidos com histórico = 1 consulta em order_attempts, não 5 (N+1)."""
    for i in range(5):
        create_order(db, f"ORDER-{i}")
    OrderProcessor(TestingSessionLocal, ScriptedSystem(
        *[DispatchResult(AttemptOutcome.SUCCESS, reference=f"INT-{i}") for i in range(5)]
    )).run_once()

    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        body = gql(logged_client, "{ orders { items { externalId history { number outcome } } } }")
    finally:
        event.remove(engine, "before_cursor_execute", record)

    items = body["data"]["orders"]["items"]
    assert len(items) == 5
    assert all(item["history"] == [{"number": 1, "outcome": "SUCCESS"}] for item in items)
    assert sum("FROM order_attempts" in s for s in statements) == 1


# ---------- erros e proteções ----------


def test_unexpected_errors_are_masked(logged_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(self) -> None:
        raise RuntimeError("detalhe interno que não pode vazar")

    monkeypatch.setattr(OrderService, "stats", boom)

    body = gql(logged_client, "{ orderStats { total } }")

    assert body["errors"][0]["message"] == "Erro interno ao processar a requisição."
    assert "vazar" not in str(body)


def test_too_many_aliases_are_rejected(logged_client: TestClient) -> None:
    aliases = " ".join(f"a{i}: orderStats {{ total }}" for i in range(settings.graphql_max_aliases + 1))
    body = gql(logged_client, f"{{ {aliases} }}")
    assert body["data"] is None
    assert "aliases" in body["errors"][0]["message"].lower()


def test_queries_via_get_are_disabled(client: TestClient) -> None:
    response = client.get(URL, params={"query": "{ orderStats { total } }"}, headers={"Accept": "application/json"})
    assert response.status_code in (400, 404, 405)


def test_introspection_is_available_in_dev(client: TestClient) -> None:
    body = gql(client, "{ __schema { queryType { name } } }")
    assert body["data"]["__schema"]["queryType"]["name"] == "Query"
