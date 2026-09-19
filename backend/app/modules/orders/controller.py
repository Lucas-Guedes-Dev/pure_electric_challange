from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Response, status
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.modules.auth.dependencies import CurrentAdmin, CurrentUser
from app.modules.orders.dtos import (
    OrderCreateDTO,
    OrderDetailDTO,
    OrderListParamsDTO,
    OrderReprocessRequestDTO,
    OrderResponseDTO,
    OrderStatsDTO,
)
from app.modules.orders.service import OrderServiceDep
from app.modules.orders.webhook_auth import WEBHOOK_KEY_HEADER, check_webhook_key
from app.shared.dtos import ErrorResponseDTO, PageDTO

router = APIRouter(prefix="/orders", tags=["Orders"])

webhook_key_scheme = APIKeyHeader(
    name=WEBHOOK_KEY_HEADER,
    auto_error=False,
    description="Chave compartilhada com o sistema que envia os pedidos (`ORDERS_WEBHOOK_KEY`).",
)


def verify_webhook_key(key: Annotated[str | None, Depends(webhook_key_scheme)]) -> None:
    check_webhook_key(key)


UNAUTHENTICATED = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponseDTO, "description": "Sem sessão de login"}
}


@router.post(
    "",
    response_model=OrderResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receber pedido (webhook)",
    description=(
        "Recebe um pedido de um sistema externo, valida, grava em `RECEIVED` e responde na hora. "
        "O processamento acontece depois, no worker "
        "(`RECEIVED → PROCESSING → PROCESSED` ou `FAILED`).\n\n"
        "**Idempotente pelo `externalId`:** reenviar o mesmo pedido responde `200` com o pedido "
        "já existente (header `Idempotent-Replayed: true`), sem criar outro nem processar de novo. "
        "O mesmo `externalId` com cliente ou valor diferentes responde `409`.\n\n"
        "Autenticação: header `X-Webhook-Key`."
    ),
    responses={
        status.HTTP_200_OK: {
            "model": OrderResponseDTO,
            "description": "Pedido já recebido antes (reenvio); nada novo foi criado",
        },
        status.HTTP_202_ACCEPTED: {"description": "Pedido novo aceito; será processado de forma assíncrona"},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponseDTO, "description": "`INVALID_WEBHOOK_KEY`"},
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponseDTO,
            "description": "`EXTERNAL_ID_CONFLICT`: externalId já usado com outros dados",
        },
    },
    dependencies=[Depends(verify_webhook_key)],
)
def receive_order(
    payload: OrderCreateDTO, service: OrderServiceDep, response: Response
) -> OrderResponseDTO:
    result = service.receive(payload)
    response.headers["Location"] = f"{settings.api_prefix}/orders/{result.order.id}"
    if not result.created:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return result.order


@router.get(
    "",
    response_model=PageDTO[OrderResponseDTO],
    summary="Listar pedidos",
    description="Lista paginada, do mais recente para o mais antigo. Filtros opcionais por "
    "`status` e busca por `externalId`/cliente.",
    responses=UNAUTHENTICATED,
)
def list_orders(
    _: CurrentUser,
    service: OrderServiceDep,
    params: Annotated[OrderListParamsDTO, Query()],
) -> PageDTO[OrderResponseDTO]:
    return service.list(params)


@router.get(
    "/stats",
    response_model=OrderStatsDTO,
    summary="Totais por status",
    responses=UNAUTHENTICATED,
)
def order_stats(_: CurrentUser, service: OrderServiceDep) -> OrderStatsDTO:
    return service.stats()


@router.get(
    "/{order_id}",
    response_model=OrderDetailDTO,
    summary="Consultar pedido",
    description="Pedido com status atual e o histórico de cada envio ao sistema interno.",
    responses={
        **UNAUTHENTICATED,
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponseDTO, "description": "Pedido não encontrado"},
    },
)
def get_order(order_id: int, _: CurrentUser, service: OrderServiceDep) -> OrderDetailDTO:
    return service.get(order_id)


@router.post(
    "/{order_id}/reprocess",
    response_model=OrderResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reprocessar pedido com falha",
    description=(
        "Devolve à fila um pedido em `FAILED`, com uma rodada nova de tentativas "
        "(`FAILED → RECEIVED`); o worker processa de novo com as mesmas regras de retry e "
        "backoff. O histórico das tentativas anteriores é mantido e o reprocessamento fica "
        "registrado (quem pediu, quando, motivo e o erro anterior).\n\n"
        "Só `FAILED`: pedidos `PROCESSED` já foram aceitos pelo sistema interno e pedidos "
        "`RECEIVED`/`PROCESSING` já estão na fila (`409`). Pedidos simultâneos para o mesmo "
        "pedido geram um único reprocessamento.\n\n"
        "Exige login de administrador."
    ),
    responses={
        status.HTTP_202_ACCEPTED: {"description": "Pedido de volta na fila; será processado de forma assíncrona"},
        **UNAUTHENTICATED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponseDTO, "description": "Usuário não é administrador"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponseDTO, "description": "Pedido não encontrado"},
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponseDTO,
            "description": "`ORDER_NOT_REPROCESSABLE`: o pedido não está em FAILED",
        },
    },
)
def reprocess_order(
    order_id: int,
    admin: CurrentAdmin,
    service: OrderServiceDep,
    payload: Annotated[OrderReprocessRequestDTO | None, Body()] = None,
) -> OrderResponseDTO:
    return service.reprocess(order_id, admin, payload or OrderReprocessRequestDTO())
