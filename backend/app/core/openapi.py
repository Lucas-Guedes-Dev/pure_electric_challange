"""Metadados do OpenAPI / Swagger UI, usados em main.create_app()."""

from typing import Any

DESCRIPTION = """
API REST do desafio técnico **Pure Eletric**.

## Convenções

- Todas as rotas ficam sob o prefixo `/api`.
- Listagens são paginadas com `?page=` e `?size=` e respondem `{ items, total, page, size }`.
- Campos monetários (`Decimal`) trafegam como **string** (ex.: `"199.90"`) para não perder precisão.

## Autenticação

Sessão controlada pelo servidor, com cookie **HttpOnly**. Faça `POST /api/auth/login` aqui
mesmo no Swagger: o navegador guarda o cookie e passa a enviá-lo sozinho nas rotas com cadeado.
A sessão expira após 30 minutos sem requisições; o backend avisa pelo stream
`GET /api/auth/events`.

## Erros

Os erros de negócio respondem `{ "detail": "...", "code": "..." }`. O `code` é estável e
serve para o frontend decidir o que fazer.

| Status | `code` | Quando |
|--------|--------|--------|
| 401 | `INVALID_CREDENTIALS` | usuário ou senha inválidos |
| 401 | `NOT_AUTHENTICATED` | rota protegida chamada sem sessão |
| 401 | `SESSION_EXPIRED` | a sessão expirou ou foi encerrada: ir para o login |
| 401 | `INVALID_WEBHOOK_KEY` | webhook de pedidos sem o header `X-Webhook-Key` correto |
| 403 | `USER_INACTIVE` / `FORBIDDEN` | usuário inativo / sem permissão |
| 404 | — | recurso não encontrado |
| 409 | `EXTERNAL_ID_CONFLICT` | `externalId` de pedido já usado com outros dados |
| 422 | — | payload ou parâmetros inválidos (erros de validação do Pydantic) |
| 429 | `RATE_LIMITED` | muitas tentativas de login |
"""

TAGS_METADATA: list[dict[str, Any]] = [
    {
        "name": "Health",
        "description": "Verifica se a API está no ar e se o banco de dados responde.",
    },
    {
        "name": "Auth",
        "description": "Login, logout, usuário logado e eventos da sessão (SSE). "
        "Sessão guardada no servidor, cookie HttpOnly, expira após 30 min de inatividade.",
    },
    {
        "name": "Orders",
        "description": "Recebimento de pedidos por webhook (idempotente por `externalId`) e consulta. "
        "O processamento é assíncrono, feito pelo worker, que envia cada pedido ao sistema "
        "interno: `RECEIVED → PROCESSING → PROCESSED` ou `FAILED`.",
    },
    {
        "name": "GraphQL",
        "description": "Endpoint GraphQL em `/api/graphql` (queries, mutation `receiveOrder` e "
        "subscription `orderUpdated` via WebSocket). Explore pelo GraphiQL: abra "
        "`/api/graphql` no navegador. Schema completo em `backend/schema.graphql`.",
    },
]

# https://swagger.io/docs/open-source-tools/swagger-ui/usage/configuration/
SWAGGER_UI_PARAMETERS: dict[str, Any] = {
    "docExpansion": "list",
    "defaultModelsExpandDepth": 0,
    "displayRequestDuration": True,
    "filter": True,
    "tryItOutEnabled": True,
    "persistAuthorization": True,
}
