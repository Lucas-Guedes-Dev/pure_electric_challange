"""GraphQL de pedidos: outra porta de entrada para as MESMAS regras do REST.

Os resolvers só traduzem GraphQL <-> DTOs e chamam o OrderService. Validação,
idempotência, estados e worker são exatamente os mesmos do REST.
"""

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from decimal import Decimal

import strawberry
from sqlalchemy.orm import Session
from strawberry.dataloader import DataLoader
from strawberry.types import Info

from app.core.config import settings
from app.core.graphql_context import GraphQLContext, parse_id, validate_input
from app.modules.orders.dtos import (
    OrderAttemptDTO,
    OrderCreateDTO,
    OrderListParamsDTO,
    OrderReprocessDTO,
    OrderReprocessRequestDTO,
    OrderResponseDTO,
)
from app.modules.orders.events import order_event_broker
from app.modules.orders.model import AttemptOutcome, OrderStatus
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderService, ReceiveResult
from app.modules.orders.simulator import OrderSimulator, SimulateOrdersDTO, SimulationScenario
from app.modules.orders.webhook_auth import WEBHOOK_KEY_HEADER, check_webhook_key
from app.shared.exceptions import AppException

Ctx = Info[GraphQLContext, None]

strawberry.enum(OrderStatus, name="OrderStatus", description="Estado do pedido")
strawberry.enum(AttemptOutcome, name="AttemptOutcome", description="Resultado de um envio ao sistema interno")
strawberry.enum(
    SimulationScenario,
    name="SimulationScenario",
    description="Cenário do simulador: define como o sistema interno (mock) vai responder",
)


def service(db: Session) -> OrderService:
    return OrderService(OrderRepository(db))


def simulator(db: Session) -> OrderSimulator:
    return OrderSimulator(service(db))


# ---------- tipos ----------


@strawberry.type(name="OrderAttempt", description="Um envio do pedido ao sistema interno")
class OrderAttemptType:
    number: int
    cycle: int = strawberry.field(description="Rodada de processamento (1 = original, 2+ = reprocessamentos)")
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    outcome: AttemptOutcome
    message: str | None

    @classmethod
    def from_dto(cls, dto: OrderAttemptDTO) -> "OrderAttemptType":
        return cls(
            number=dto.number,
            cycle=dto.cycle,
            started_at=dto.started_at,
            finished_at=dto.finished_at,
            duration_ms=dto.duration_ms,
            outcome=dto.outcome,
            message=dto.message,
        )


def history_loader(ctx: GraphQLContext) -> DataLoader[int, list[OrderAttemptType]]:
    """Carrega o histórico de TODOS os pedidos pedidos numa consulta só (evita N+1).
    Sem cache: numa subscription o mesmo pedido volta várias vezes com histórico novo."""

    async def load(order_ids: list[int]) -> list[list[OrderAttemptType]]:
        ids = list(order_ids)
        by_order = await ctx.run(lambda db: service(db).history_by_order_ids(ids))
        return [[OrderAttemptType.from_dto(a) for a in by_order.get(order_id, [])] for order_id in ids]

    return ctx.loader("order_history", lambda: DataLoader(load_fn=load, cache=False))


@strawberry.type(name="OrderReprocess", description="Um reprocessamento manual do pedido")
class OrderReprocessType:
    number: int = strawberry.field(description="1 = primeiro reprocessamento")
    cycle: int = strawberry.field(description="Rodada que este reprocessamento abriu")
    requested_by: str | None = strawberry.field(description="Quem pediu")
    reason: str | None
    previous_error: str | None = strawberry.field(description="Erro que o pedido tinha antes")
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: OrderReprocessDTO) -> "OrderReprocessType":
        return cls(
            number=dto.number,
            cycle=dto.cycle,
            requested_by=dto.requested_by,
            reason=dto.reason,
            previous_error=dto.previous_error,
            created_at=dto.created_at,
        )


def reprocesses_loader(ctx: GraphQLContext) -> DataLoader[int, list[OrderReprocessType]]:
    """Reprocessamentos de todos os pedidos pedidos numa consulta só (mesma ideia do histórico)."""

    async def load(order_ids: list[int]) -> list[list[OrderReprocessType]]:
        ids = list(order_ids)
        by_order = await ctx.run(lambda db: service(db).reprocesses_by_order_ids(ids))
        return [[OrderReprocessType.from_dto(r) for r in by_order.get(order_id, [])] for order_id in ids]

    return ctx.loader("order_reprocesses", lambda: DataLoader(load_fn=load, cache=False))


@strawberry.type(name="Order", description="Pedido recebido e seu estado de processamento")
class OrderType:
    id: strawberry.ID
    external_id: str
    customer: str
    amount: Decimal = strawberry.field(description="Valor com 2 casas, como string (ex.: \"150.00\")")
    status: OrderStatus
    attempts: int = strawberry.field(description="Envios já feitos ao sistema interno")
    cycle: int = strawberry.field(description="Rodada de processamento atual (soma 1 a cada reprocessamento)")
    next_attempt_at: datetime | None = strawberry.field(description="Próxima tentativa (aguardando retentativa)")
    last_error: str | None
    internal_reference: str | None = strawberry.field(description="Protocolo do sistema interno")
    created_at: datetime = strawberry.field(description="Quando o pedido foi recebido")
    updated_at: datetime
    finished_at: datetime | None
    pk: strawberry.Private[int]

    @strawberry.field(description="Cada envio ao sistema interno, em ordem")
    async def history(self, info: Ctx) -> list[OrderAttemptType]:
        return await history_loader(info.context).load(self.pk)

    @strawberry.field(description="Reprocessamentos manuais, em ordem")
    async def reprocesses(self, info: Ctx) -> list[OrderReprocessType]:
        return await reprocesses_loader(info.context).load(self.pk)

    @classmethod
    def from_dto(cls, dto: OrderResponseDTO) -> "OrderType":
        return cls(
            id=strawberry.ID(str(dto.id)),
            pk=dto.id,
            external_id=dto.external_id,
            customer=dto.customer,
            amount=dto.amount,
            status=dto.status,
            attempts=dto.attempts,
            cycle=dto.cycle,
            next_attempt_at=dto.next_attempt_at,
            last_error=dto.last_error,
            internal_reference=dto.internal_reference,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
            finished_at=dto.finished_at,
        )


@strawberry.type(name="OrderPage")
class OrderPageType:
    items: list[OrderType]
    total: int
    page: int
    size: int


@strawberry.type(name="OrderStats", description="Quantidade de pedidos em cada status")
class OrderStatsType:
    received: int
    processing: int
    processed: int
    failed: int
    total: int


@strawberry.input(name="ReceiveOrderInput", description="Mesmo payload do webhook REST")
class ReceiveOrderInput:
    external_id: str = strawberry.field(description="Chave de idempotência do pedido")
    customer: str
    amount: Decimal = strawberry.field(description="Maior que zero, até 2 casas decimais")


@strawberry.type(name="ReceiveOrderPayload")
class ReceiveOrderPayload:
    order: OrderType
    created: bool = strawberry.field(
        description="false quando o externalId já existia (reenvio): nada novo foi criado"
    )

    @classmethod
    def from_result(cls, result: ReceiveResult) -> "ReceiveOrderPayload":
        return cls(order=OrderType.from_dto(result.order), created=result.created)


@strawberry.input(name="SimulateOrdersInput")
class SimulateOrdersInput:
    scenario: SimulationScenario
    count: int = strawberry.field(default=1, description="Quantidade de pedidos (1 a 20)")


# ---------- operações ----------


@strawberry.type
class OrderQuery:
    @strawberry.field(description="Pedidos do mais recente para o mais antigo. Exige login.")
    async def orders(
        self,
        info: Ctx,
        status: OrderStatus | None = None,
        search: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> OrderPageType:
        ctx = info.context
        await ctx.require_user()
        params = validate_input(
            OrderListParamsDTO, {"status": status, "search": search, "page": page, "size": size}
        )
        result = await ctx.run(lambda db: service(db).list(params))
        return OrderPageType(
            items=[OrderType.from_dto(order) for order in result.items],
            total=result.total,
            page=result.page,
            size=result.size,
        )

    @strawberry.field(description="Pedido pelo id. Exige login.")
    async def order(self, info: Ctx, id: strawberry.ID) -> OrderType | None:
        ctx = info.context
        await ctx.require_user()
        order_id = parse_id(id)
        dto = await ctx.run(lambda db: service(db).get_summary(order_id))
        return OrderType.from_dto(dto) if dto else None

    @strawberry.field(description="Pedido pelo externalId. Exige login.")
    async def order_by_external_id(self, info: Ctx, external_id: str) -> OrderType | None:
        ctx = info.context
        await ctx.require_user()
        dto = await ctx.run(lambda db: service(db).get_by_external_id(external_id))
        return OrderType.from_dto(dto) if dto else None

    @strawberry.field(description="Totais por status. Exige login.")
    async def order_stats(self, info: Ctx) -> OrderStatsType:
        ctx = info.context
        await ctx.require_user()
        stats = await ctx.run(lambda db: service(db).stats())
        return OrderStatsType(**stats.model_dump(by_alias=False))

    @strawberry.field(description="Se o simulador de pedidos está ligado neste ambiente. Exige login.")
    async def order_simulator_enabled(self, info: Ctx) -> bool:
        await info.context.require_user()
        return settings.order_simulator_enabled


@strawberry.type
class OrderMutation:
    @strawberry.mutation(
        description="Recebe um pedido (equivalente ao POST /api/orders). Idempotente pelo "
        "externalId. Exige o header X-Webhook-Key."
    )
    async def receive_order(self, info: Ctx, input: ReceiveOrderInput) -> ReceiveOrderPayload:
        ctx = info.context
        try:
            check_webhook_key(ctx.header(WEBHOOK_KEY_HEADER))
        except AppException as exc:
            raise ctx.to_graphql_error(exc) from exc
        payload = validate_input(
            OrderCreateDTO,
            {"externalId": input.external_id, "customer": input.customer, "amount": input.amount},
        )
        result = await ctx.run(lambda db: service(db).receive(payload))
        return ReceiveOrderPayload.from_result(result)

    @strawberry.mutation(
        description="Simulador: cria pedidos como se viessem do sistema externo, pelo mesmo fluxo "
        "do webhook. Exige login e ORDER_SIMULATOR_ENABLED=true."
    )
    async def simulate_orders(self, info: Ctx, input: SimulateOrdersInput) -> list[ReceiveOrderPayload]:
        ctx = info.context
        await ctx.require_user()
        request = validate_input(SimulateOrdersDTO, {"scenario": input.scenario, "count": input.count})
        results = await ctx.run(lambda db: simulator(db).simulate(request))
        return [ReceiveOrderPayload.from_result(result) for result in results]

    @strawberry.mutation(
        description="Simulador: reenvia um pedido existente com os mesmos dados (teste de "
        "idempotência: created=false, nada é criado nem reprocessado)."
    )
    async def resend_order(self, info: Ctx, id: strawberry.ID) -> ReceiveOrderPayload:
        ctx = info.context
        await ctx.require_user()
        order_id = parse_id(id)
        result = await ctx.run(lambda db: simulator(db).resend(order_id))
        return ReceiveOrderPayload.from_result(result)


    @strawberry.mutation(
        description="Reprocessa um pedido em FAILED (equivalente ao POST /api/orders/{id}/reprocess): "
        "volta para RECEIVED com uma rodada nova de tentativas. Outros status: "
        "ORDER_NOT_REPROCESSABLE. Exige login de administrador."
    )
    async def reprocess_order(self, info: Ctx, id: strawberry.ID, reason: str | None = None) -> OrderType:
        ctx = info.context
        user = await ctx.require_admin()
        order_id = parse_id(id)
        request = validate_input(OrderReprocessRequestDTO, {"reason": reason})
        dto = await ctx.run(lambda db: service(db).reprocess(order_id, user, request))
        return OrderType.from_dto(dto)


@strawberry.type
class OrderSubscription:
    @strawberry.subscription(
        description="Envia o pedido atualizado a cada mudança de status (recebido, em "
        "processamento, retentativa, processado, falhou). Sem `id`, acompanha todos. "
        "Exige login; termina com SESSION_EXPIRED quando a sessão acaba."
    )
    async def order_updated(
        self, info: Ctx, id: strawberry.ID | None = None
    ) -> AsyncGenerator[OrderType, None]:
        ctx = info.context
        await ctx.check_session_alive()
        wanted = parse_id(id) if id is not None else None

        async with order_event_broker.subscribe() as queue:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=settings.session_events_poll_seconds)
                except TimeoutError:
                    event = None
                # Sem renovar a sessão; se ela acabou, o erro encerra a subscription
                await ctx.check_session_alive(min_interval=settings.session_events_poll_seconds)
                if event is None or (wanted is not None and event.order_id != wanted):
                    continue
                order_id = event.order_id
                dto = await ctx.run(lambda db: service(db).get_summary(order_id))
                if dto is not None:
                    yield OrderType.from_dto(dto)
