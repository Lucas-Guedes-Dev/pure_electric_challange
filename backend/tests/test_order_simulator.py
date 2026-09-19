"""Simulador de pedidos (mutations simulateOrders / resendOrder)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.orders.model import Order
from tests.test_graphql_orders import error_codes, gql

SIMULATE = """
mutation($input: SimulateOrdersInput!) {
  simulateOrders(input: $input) { created order { id externalId customer amount status } }
}
"""
RESEND = "mutation($id: ID!) { resendOrder(id: $id) { created order { id externalId } } }"


@pytest.fixture
def simulator_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "order_simulator_enabled", True)


def count_orders(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Order))


@pytest.mark.parametrize(
    ("scenario", "prefix"),
    [("SUCCESS", "ORDER-SIM-"), ("REJECTED", "FAIL-SIM-"), ("UNSTABLE", "FLAKY-SIM-"), ("TIMEOUT", "TIMEOUT-SIM-")],
)
def test_simulate_creates_orders_for_the_scenario(
    logged_client: TestClient, db: Session, simulator_on: None, scenario: str, prefix: str
) -> None:
    body = gql(logged_client, SIMULATE, {"input": {"scenario": scenario, "count": 3}})

    results = body["data"]["simulateOrders"]
    assert len(results) == 3
    assert all(r["created"] and r["order"]["status"] == "RECEIVED" for r in results)
    assert all(r["order"]["externalId"].startswith(prefix) for r in results)
    assert len({r["order"]["externalId"] for r in results}) == 3  # ids únicos
    assert all(50 <= float(r["order"]["amount"]) <= 5000 for r in results)
    assert count_orders(db) == 3


def test_random_scenario_uses_known_prefixes(logged_client: TestClient, simulator_on: None) -> None:
    body = gql(logged_client, SIMULATE, {"input": {"scenario": "RANDOM", "count": 20}})

    prefixes = {r["order"]["externalId"].split("-")[0] for r in body["data"]["simulateOrders"]}
    assert prefixes <= {"ORDER", "FAIL", "FLAKY", "TIMEOUT"}


def test_count_is_limited(logged_client: TestClient, simulator_on: None) -> None:
    for count in (0, 21):
        body = gql(logged_client, SIMULATE, {"input": {"scenario": "SUCCESS", "count": count}})
        assert error_codes(body) == ["BAD_USER_INPUT"]


def test_resend_is_idempotent(logged_client: TestClient, db: Session, simulator_on: None) -> None:
    created = gql(logged_client, SIMULATE, {"input": {"scenario": "SUCCESS"}})["data"]["simulateOrders"][0]

    body = gql(logged_client, RESEND, {"id": created["order"]["id"]})

    assert body["data"]["resendOrder"] == {"created": False, "order": {
        "id": created["order"]["id"], "externalId": created["order"]["externalId"],
    }}
    assert count_orders(db) == 1
    assert error_codes(gql(logged_client, RESEND, {"id": "999"})) == ["NOT_FOUND"]


def test_simulator_disabled_by_default(logged_client: TestClient, db: Session) -> None:
    body = gql(logged_client, SIMULATE, {"input": {"scenario": "SUCCESS"}})

    assert error_codes(body) == ["SIMULATOR_DISABLED"]
    assert gql(logged_client, "{ orderSimulatorEnabled }")["data"]["orderSimulatorEnabled"] is False
    assert count_orders(db) == 0


def test_simulator_requires_login(client: TestClient, simulator_on: None) -> None:
    body = gql(client, SIMULATE, {"input": {"scenario": "SUCCESS"}})
    assert error_codes(body) == ["NOT_AUTHENTICATED"]
