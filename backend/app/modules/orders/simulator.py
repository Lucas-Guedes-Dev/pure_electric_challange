"""Simulador de pedidos: faz o papel do sistema externo que envia pedidos, para demonstrar
o fluxo pela interface sem precisar de curl.

Os pedidos entram pelo MESMO `OrderService.receive` do webhook (mesma validação, mesma
idempotência, mesmo worker). O cenário é escolhido pelo prefixo do externalId, que o
sistema interno mockado interpreta (ver backend/internal_system/main.py).

Só funciona com ORDER_SIMULATOR_ENABLED=true e com usuário logado. A chave do webhook
nunca sai do servidor.
"""

import enum
import random
import secrets
from decimal import Decimal

from fastapi import status
from pydantic import Field

from app.core.config import settings
from app.modules.orders.dtos import OrderCreateDTO
from app.modules.orders.service import OrderService, ReceiveResult
from app.shared.clock import utcnow
from app.shared.dtos import BaseDTO
from app.shared.exceptions import AppException, NotFoundException


class SimulationScenario(str, enum.Enum):
    SUCCESS = "SUCCESS"  # aceito pelo sistema interno -> PROCESSED
    REJECTED = "REJECTED"  # recusado (422) -> FAILED sem retentativa
    UNSTABLE = "UNSTABLE"  # 503 nas 2 primeiras chamadas -> PROCESSED na 3ª tentativa
    TIMEOUT = "TIMEOUT"  # não responde a tempo -> retentativas e FAILED
    OUTAGE = "OUTAGE"  # fora do ar nas 3 primeiras chamadas -> FAILED; reprocessado -> PROCESSED
    RANDOM = "RANDOM"  # mistura dos cenários acima


PREFIXES = {
    SimulationScenario.SUCCESS: "ORDER",
    SimulationScenario.REJECTED: "FAIL",
    SimulationScenario.UNSTABLE: "FLAKY",
    SimulationScenario.TIMEOUT: "TIMEOUT",
    SimulationScenario.OUTAGE: "OUTAGE",
}

CUSTOMERS = [
    "Ana Souza", "Bruno Lima", "Carla Mendes", "Diego Rocha", "Elisa Martins",
    "Felipe Araújo", "Gabriela Nunes", "Henrique Alves", "Isabela Costa", "João Pereira",
]

MAX_ORDERS_PER_SIMULATION = 20


class SimulateOrdersDTO(BaseDTO):
    scenario: SimulationScenario
    count: int = Field(default=1, ge=1, le=MAX_ORDERS_PER_SIMULATION)


class SimulatorDisabledException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "SIMULATOR_DISABLED"


def ensure_simulator_enabled() -> None:
    if not settings.order_simulator_enabled:
        raise SimulatorDisabledException(
            "Simulador de pedidos desligado (ORDER_SIMULATOR_ENABLED=false)"
        )


class OrderSimulator:
    def __init__(self, service: OrderService) -> None:
        self.service = service

    def simulate(self, request: SimulateOrdersDTO) -> list[ReceiveResult]:
        ensure_simulator_enabled()
        stamp = utcnow().strftime("%H%M%S")
        concrete = list(PREFIXES)
        results = []
        for _ in range(request.count):
            scenario = random.choice(concrete) if request.scenario == SimulationScenario.RANDOM else request.scenario
            payload = OrderCreateDTO(
                externalId=f"{PREFIXES[scenario]}-SIM-{stamp}-{secrets.token_hex(2).upper()}",
                customer=random.choice(CUSTOMERS),
                amount=Decimal(random.randint(5_000, 500_000)) / 100,  # R$ 50,00 a R$ 5.000,00
            )
            results.append(self.service.receive(payload))
        return results

    def resend(self, order_id: int) -> ReceiveResult:
        """Reenvia um pedido existente com os mesmos dados, como um sistema externo que
        repete o webhook. Demonstra a idempotência: nada novo é criado nem reprocessado."""
        ensure_simulator_enabled()
        order = self.service.repository.get_by_id(order_id)
        if order is None:
            raise NotFoundException(f"Pedido {order_id} não encontrado")
        payload = OrderCreateDTO(externalId=order.external_id, customer=order.customer, amount=order.amount)
        return self.service.receive(payload)
