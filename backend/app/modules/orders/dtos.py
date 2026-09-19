"""Contrato da API de pedidos.

Segue o formato do enunciado (camelCase: `externalId`), tanto na entrada quanto na saída.
Os nomes em Python continuam em snake_case; a conversão é feita pelo alias.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.modules.orders.model import AttemptOutcome, OrderStatus
from app.shared.dtos import BaseDTO, PaginationParamsDTO


class CamelDTO(BaseDTO):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        str_strip_whitespace=True,
    )


class OrderCreateDTO(CamelDTO):
    """Payload do webhook. Campos extras são ignorados."""

    external_id: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:\-]*$",
        description="Identificador do pedido no sistema de origem. Chave de idempotência: "
        "o mesmo valor nunca gera dois pedidos.",
        examples=["ORDER-123"],
    )
    customer: str = Field(min_length=1, max_length=255, examples=["Cliente Exemplo"])
    amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Valor do pedido, maior que zero, com até 2 casas decimais",
        examples=[150.00],
    )


class OrderAttemptDTO(CamelDTO):
    number: int = Field(examples=[1])
    cycle: int = Field(description="Rodada de processamento (1 = original, 2+ = reprocessamentos)", examples=[1])
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(examples=[182])
    outcome: AttemptOutcome
    message: str | None = Field(default=None, examples=["Sistema interno indisponível (HTTP 503)"])


class OrderResponseDTO(CamelDTO):
    id: int = Field(examples=[1])
    external_id: str = Field(examples=["ORDER-123"])
    customer: str = Field(examples=["Cliente Exemplo"])
    amount: Decimal = Field(examples=["150.00"])
    status: OrderStatus
    attempts: int = Field(description="Envios já feitos ao sistema interno", examples=[1])
    cycle: int = Field(
        description="Rodada de processamento atual (1 = original; soma 1 a cada reprocessamento)", examples=[1]
    )
    next_attempt_at: datetime | None = Field(
        default=None, description="Próxima tentativa (só enquanto aguarda retentativa)"
    )
    last_error: str | None = Field(default=None, description="Último erro do processamento")
    internal_reference: str | None = Field(
        default=None, description="Protocolo do sistema interno (quando PROCESSED)", examples=["INT-8F3A2C"]
    )
    created_at: datetime = Field(description="Quando o pedido foi recebido")
    updated_at: datetime
    finished_at: datetime | None = Field(default=None, description="Quando chegou a PROCESSED ou FAILED")


class OrderReprocessDTO(CamelDTO):
    """Um reprocessamento manual do pedido."""

    number: int = Field(description="1 = primeiro reprocessamento", examples=[1])
    cycle: int = Field(description="Rodada que este reprocessamento abriu", examples=[2])
    requested_by: str | None = Field(
        default=None, description="Quem pediu (nome ou usuário)", examples=["Administrador"]
    )
    reason: str | None = Field(default=None, examples=["Cadastro do cliente liberado no sistema interno"])
    previous_error: str | None = Field(
        default=None, description="Erro que o pedido tinha antes de ser reprocessado"
    )
    created_at: datetime


class OrderDetailDTO(OrderResponseDTO):
    history: list[OrderAttemptDTO] = Field(description="Cada envio ao sistema interno, em ordem")
    reprocesses: list[OrderReprocessDTO] = Field(
        default_factory=list, description="Reprocessamentos manuais, em ordem"
    )


class OrderReprocessRequestDTO(CamelDTO):
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Motivo do reprocessamento (opcional; fica registrado no pedido)",
        examples=["Cadastro do cliente liberado no sistema interno"],
    )


class OrderListParamsDTO(PaginationParamsDTO):
    status: OrderStatus | None = Field(default=None, description="Filtra por status")
    search: str | None = Field(
        default=None, max_length=100, description="Busca parcial por externalId ou cliente"
    )


class OrderStatsDTO(CamelDTO):
    """Quantidade de pedidos em cada status."""

    received: int
    processing: int
    processed: int
    failed: int
    total: int
