"""Schema GraphQL da aplicação, montado a partir dos módulos, e o router em /api/graphql.

Para expor um módulo novo: crie `app/modules/<modulo>/graphql.py` com as classes
Query/Mutation/Subscription e adicione-as nas tuplas abaixo.
"""

import logging
from urllib.parse import urlsplit

import strawberry
from graphql import GraphQLError
from strawberry.exceptions import ConnectionRejectionError
from strawberry.extensions import (
    DisableIntrospection,
    MaskErrors,
    MaxAliasesLimiter,
    MaxTokensLimiter,
    QueryDepthLimiter,
)
from strawberry.fastapi import GraphQLRouter
from strawberry.tools import merge_types
from strawberry.types.unset import UNSET, UnsetType

from app.core.config import settings
from app.core.database import SessionFactory
from app.core.graphql_context import GraphQLContext
from app.modules.orders.graphql import OrderMutation, OrderQuery, OrderSubscription

logger = logging.getLogger("app.graphql")

Query = merge_types("Query", (OrderQuery,))
Mutation = merge_types("Mutation", (OrderMutation,))
Subscription = merge_types("Subscription", (OrderSubscription,))


def _should_mask(error: GraphQLError) -> bool:
    """Esconde do cliente só os erros inesperados (bugs), que são registrados no log.
    Erros de negócio (com `code`) e de validação da query passam como estão."""
    original = error.original_error
    if original is None or isinstance(original, GraphQLError):
        return False
    logger.error("Erro inesperado no GraphQL (%s)", error.path, exc_info=original)
    return True


class AppSchema(strawberry.Schema):
    def process_errors(self, errors, execution_context=None) -> None:  # type: ignore[override]
        # O padrão registra TODO erro como ERROR (inclusive "sem login"). Os inesperados
        # já são registrados em _should_mask; os demais são respostas normais da API.
        return None


def _extensions() -> list:
    extensions = [
        QueryDepthLimiter(max_depth=settings.graphql_max_depth),
        MaxAliasesLimiter(max_alias_count=settings.graphql_max_aliases),
        MaxTokensLimiter(max_token_count=settings.graphql_max_tokens),
        MaskErrors(should_mask_error=_should_mask, error_message="Erro interno ao processar a requisição."),
    ]
    introspection = settings.graphql_introspection
    if introspection is None:
        introspection = settings.docs_enabled
    if not introspection:
        extensions.append(DisableIntrospection())
    return extensions


schema = AppSchema(query=Query, mutation=Mutation, subscription=Subscription, extensions=_extensions())


def _origin_allowed(origin: str | None, host: str | None) -> bool:
    """WebSocket não passa por CORS: sem essa checagem, outro site poderia abrir a conexão
    usando o cookie do usuário. Aceita a própria origem e as de CORS_ORIGINS."""
    if not origin:
        return True  # clientes que não são navegador (ex.: scripts, testes)
    if origin in settings.cors_origins_list:
        return True
    return urlsplit(origin).netloc == host


class AppGraphQLRouter(GraphQLRouter):
    async def on_ws_connect(self, context: GraphQLContext) -> UnsetType | dict[str, object] | None:
        ws = context.request
        if ws is None or not _origin_allowed(ws.headers.get("origin"), ws.headers.get("host")):
            raise ConnectionRejectionError({"code": "FORBIDDEN_ORIGIN", "message": "Origem não permitida"})
        try:
            await context.check_session_alive()
        except GraphQLError as exc:
            raise ConnectionRejectionError(
                {"code": (exc.extensions or {}).get("code"), "message": exc.message}
            ) from exc
        return UNSET


async def get_graphql_context(factory: SessionFactory) -> GraphQLContext:
    return GraphQLContext(factory)


graphql_router = AppGraphQLRouter(
    schema,
    path="/graphql",
    context_getter=get_graphql_context,
    graphql_ide="graphiql" if settings.docs_enabled else None,
    # Só POST: queries por GET poderiam ser disparadas por links de outros sites
    allow_queries_via_get=False,
    tags=["GraphQL"],
)
