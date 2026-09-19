"""Client do sistema interno (fora desta API). O worker usa para encaminhar os pedidos.

Classifica cada resposta para o worker decidir o que fazer:
    SUCCESS          2xx                               -> PROCESSED
    TRANSIENT_ERROR  timeout, erro de rede, 408/429/5xx -> tenta de novo mais tarde
    PERMANENT_ERROR  demais 4xx (pedido recusado)       -> FAILED sem repetir
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

import httpx

from app.modules.orders.model import AttemptOutcome

TRANSIENT_STATUS = {408, 425, 429}


@dataclass(frozen=True)
class OrderDispatch:
    """O que o worker envia ao sistema interno."""

    order_id: int
    external_id: str
    customer: str
    amount: Decimal
    attempt: int


@dataclass(frozen=True)
class DispatchResult:
    outcome: AttemptOutcome
    message: str | None = None
    reference: str | None = None


class InternalSystem(Protocol):
    def send(self, order: OrderDispatch) -> DispatchResult: ...


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict) and isinstance(body.get("detail"), str):
        return body["detail"]
    return str(body)[:200]


class InternalSystemClient:
    def __init__(self, base_url: str, timeout_seconds: float, http: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.http = http or httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def send(self, order: OrderDispatch) -> DispatchResult:
        try:
            response = self.http.post(
                "/internal/orders",
                json={
                    "orderId": order.order_id,
                    "externalId": order.external_id,
                    "customer": order.customer,
                    "amount": str(order.amount),
                },
                # Se o worker cair depois do envio e o pedido for reenviado, o sistema
                # interno reconhece a chave e não processa duas vezes
                headers={"Idempotency-Key": order.external_id, "X-Attempt": str(order.attempt)},
            )
        except httpx.TimeoutException:
            return DispatchResult(
                AttemptOutcome.TRANSIENT_ERROR,
                f"Sistema interno não respondeu em {self.timeout_seconds:g}s (timeout)",
            )
        except httpx.HTTPError as exc:
            return DispatchResult(
                AttemptOutcome.TRANSIENT_ERROR,
                f"Falha de comunicação com o sistema interno ({exc.__class__.__name__})",
            )

        if response.is_success:
            reference = None
            try:
                reference = response.json().get("reference")
            except (ValueError, AttributeError):
                pass
            return DispatchResult(AttemptOutcome.SUCCESS, reference=reference)

        status = response.status_code
        if status >= 500 or status in TRANSIENT_STATUS:
            return DispatchResult(
                AttemptOutcome.TRANSIENT_ERROR,
                f"Sistema interno indisponível (HTTP {status}): {_detail(response)}",
            )
        return DispatchResult(
            AttemptOutcome.PERMANENT_ERROR,
            f"Pedido recusado pelo sistema interno (HTTP {status}): {_detail(response)}",
        )
