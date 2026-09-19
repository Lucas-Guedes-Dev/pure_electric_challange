# Backend · Desafio Técnico Pure Eletric

API REST em **Python 3.12 + FastAPI**, organizada em **MVC por módulo**, com **DTOs Pydantic** tipando tudo o que entra e sai das controllers.

> 📘 **A API tem documentação interativa (Swagger).** Com o backend rodando, acesse **http://localhost:8000/api/docs** para ver todas as rotas, os DTOs de entrada e saída e testar as chamadas pelo navegador ("Try it out"). A raiz `http://localhost:8000/` redireciona para lá. Detalhes em [Documentação (Swagger / OpenAPI)](#documentação-swagger--openapi).

| Tecnologia        | Uso                                             |
|-------------------|-------------------------------------------------|
| FastAPI           | framework web / rotas / OpenAPI (Swagger)       |
| Pydantic v2       | DTOs de request/response e validação            |
| pydantic-settings | configuração via variáveis de ambiente          |
| SQLAlchemy 2      | ORM (models)                                    |
| Alembic           | migrations do banco                             |
| Strawberry        | GraphQL (queries, mutation e subscription em /api/graphql) |
| PostgreSQL 17     | banco de dados (via psycopg 3)                  |
| pytest + httpx    | testes (SQLite em memória, sem depender do Postgres) |

## Estrutura de pastas

```
backend/
├── app/
│   ├── main.py                 # ponto de entrada: create_app() monta CORS, docs, handlers de erro e rotas
│   ├── core/                   # infraestrutura da aplicação
│   │   ├── config.py           # Settings: lê variáveis de ambiente / .env
│   │   ├── database.py         # engine, SessionLocal, get_db() e o tipo DbSession
│   │   ├── openapi.py          # descrição da API, tags e configuração do Swagger UI
│   │   ├── rate_limit.py       # limiter (slowapi) por IP + resposta 429
│   │   ├── graphql.py          # schema GraphQL (junta os módulos) + router /api/graphql
│   │   └── graphql_context.py  # contexto dos resolvers: banco, login, erros com `code`
│   ├── cli.py                  # comandos de administração (create-user, export-graphql-schema)
│   ├── shared/                 # código reutilizado por todos os módulos
│   │   ├── model.py            # Base declarativa do SQLAlchemy + TimestampMixin
│   │   ├── dtos.py             # BaseDTO, PageDTO[T], PaginationParamsDTO, ErrorResponseDTO
│   │   ├── repository.py       # BaseRepository[Model]: CRUD genérico
│   │   └── exceptions.py       # AppException, NotFound, Conflict + handler HTTP
│   └── modules/                # um diretório por domínio de negócio
│       ├── __init__.py         # api_router (registro dos routers) + import_all_models()
│       ├── health/             # healthcheck da API e do banco
│       │   ├── controller.py
│       │   └── dtos.py
│       ├── users/              # tabela de usuários (model, dtos, repository)
│       ├── auth/               # login e sessão (ver "Autenticação e sessão")
│       │   ├── model.py        # UserSession: sessões guardadas no banco
│       │   ├── dtos.py         # LoginRequestDTO, AuthSessionResponseDTO, eventos SSE
│       │   ├── controller.py   # /login, /logout, /me, /refresh, /events
│       │   ├── service.py      # regras: validar credenciais, expirar, renovar
│       │   ├── repository.py
│       │   ├── dependencies.py # CurrentUser / CurrentAdmin para proteger rotas
│       │   ├── events.py       # stream SSE que avisa o navegador
│       │   ├── security.py     # bcrypt + token opaco
│       │   ├── cookies.py      # cookie HttpOnly de sessão
│       │   └── exceptions.py   # erros 401/403 com `code`
│       ├── orders/             # pedidos: webhook, fila, worker (ver "Pedidos")
│       │   ├── model.py        # Order (também é a fila) + OrderAttempt (histórico) + estados
│       │   ├── dtos.py         # contrato em camelCase (externalId...)
│       │   ├── controller.py   # POST /orders (webhook), GET /orders, /stats, /{id}
│       │   ├── service.py      # recebimento idempotente e consultas
│       │   ├── repository.py   # consultas + reserva da fila (FOR UPDATE SKIP LOCKED)
│       │   ├── processor.py    # consumer: reserva, envia, aplica resultado, retentativas
│       │   ├── internal_client.py # client HTTP do sistema interno + classificação dos erros
│       │   ├── worker.py       # processo do worker (python -m app.modules.orders.worker)
│       │   ├── events.py       # eventos em tempo real: pg_notify, LISTEN e broker
│       │   ├── graphql.py      # tipos, queries, mutation e subscription GraphQL
│       │   └── webhook_auth.py # checagem da chave X-Webhook-Key (REST e GraphQL)
│       └── <modulo>/           # cada módulo novo segue o padrão abaixo
│           ├── model.py
│           ├── dtos.py
│           ├── controller.py
│           ├── service.py
│           └── repository.py
├── schema.graphql              # contrato GraphQL exportado (um teste garante que está atualizado)
├── internal_system/            # sistema interno MOCKADO (outro serviço, porta 9000)
│   └── main.py                 # cenários de sucesso e falha
├── alembic/                    # migrations
│   ├── env.py                  # lê a URL do banco do config e descobre os models
│   └── versions/               # arquivos de migration
├── tests/                      # testes (conftest.py sobe o app com SQLite em memória)
├── alembic.ini
├── entrypoint.sh               # roda "alembic upgrade head" antes de subir o servidor
├── Dockerfile
├── requirements.txt            # dependências de produção
└── requirements-dev.txt        # + dependências de teste
```

## As camadas de um módulo

Cada módulo em `app/modules/<nome>/` é autocontido. Os arquivos têm papéis bem definidos:

| Arquivo          | Camada     | Responsabilidade |
|------------------|------------|------------------|
| `model.py`       | **Model**  | Entidade SQLAlchemy, ou seja, a tabela no banco. Herda de `Base` (e de `TimestampMixin` para ter `created_at`/`updated_at`). |
| `dtos.py`        | **View**   | O contrato da API: DTOs de entrada (`XxxCreateDTO`, `XxxUpdateDTO`) e de saída (`XxxResponseDTO`). O model **nunca** sai direto na resposta. |
| `controller.py`  | **Controller** | Rotas FastAPI. Recebe um DTO, chama o service e devolve um DTO. Sem regra de negócio e sem acesso ao banco. |
| `service.py`     | Regra de negócio | Validações de domínio (ex.: registro duplicado → 409), orquestra o repository e converte model → DTO. Também expõe a dependência `XxxServiceDep` usada pela controller. |
| `repository.py`  | Acesso a dados | Herda o CRUD do `BaseRepository` e adiciona as queries específicas do módulo. |

### Fluxo de um request

```
HTTP ──► controller.py ──► service.py ──► repository.py ──► banco
          (DTO entrada)        │                                │
                               ◄──────────── model ◄────────────┘
HTTP ◄── controller.py ◄── service.py
          (DTO saída)      (model → DTO)
```

### Regras dos DTOs

- Toda rota declara o DTO que recebe e o que devolve, tanto no `response_model` quanto no tipo de retorno.
- O **payload inválido** é rejeitado pelo Pydantic com **422**, antes de chegar ao service.
- Os **erros de negócio** são lançados no service (`NotFoundException`, `ConflictException`) e o handler em `shared/exceptions.py` os converte para `ErrorResponseDTO` (`{"detail": "..."}`) com o status correto.
- As listagens retornam `PageDTO[XxxResponseDTO]`: `{ items, total, page, size }`.
- Campos `Decimal` são serializados como **string** no JSON, para não perder precisão.

## Criando um módulo novo (ex.: `compras`)

### 1. Crie os arquivos em `app/modules/compras/`

Esqueleto mínimo de cada arquivo (inclua também um `__init__.py` vazio):

**`model.py`**: a tabela
```python
from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.model import Base, TimestampMixin


class Compra(TimestampMixin, Base):
    __tablename__ = "compras"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    descricao: Mapped[str] = mapped_column(String(120), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
```

**`dtos.py`**: o contrato da API
```python
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.shared.dtos import BaseDTO


class CompraCreateDTO(BaseDTO):
    descricao: str = Field(min_length=1, max_length=120, examples=["Carregador"])
    valor: Decimal = Field(ge=0, max_digits=12, decimal_places=2, examples=["199.90"])


class CompraResponseDTO(BaseDTO):
    id: int
    descricao: str
    valor: Decimal
    created_at: datetime
    updated_at: datetime
```

**`repository.py`**: acesso a dados (o CRUD básico vem do `BaseRepository`)
```python
from app.modules.compras.model import Compra
from app.shared.repository import BaseRepository


class CompraRepository(BaseRepository[Compra]):
    model = Compra
```

**`service.py`**: regras de negócio e injeção de dependência
```python
from typing import Annotated

from fastapi import Depends

from app.core.database import DbSession
from app.modules.compras.dtos import CompraCreateDTO, CompraResponseDTO
from app.modules.compras.model import Compra
from app.modules.compras.repository import CompraRepository
from app.shared.dtos import PageDTO, PaginationParamsDTO
from app.shared.exceptions import NotFoundException


class CompraService:
    def __init__(self, repository: CompraRepository) -> None:
        self.repository = repository

    def list(self, pagination: PaginationParamsDTO) -> PageDTO[CompraResponseDTO]:
        compras = self.repository.list(offset=pagination.offset, limit=pagination.size)
        return PageDTO[CompraResponseDTO](
            items=[CompraResponseDTO.model_validate(c) for c in compras],
            total=self.repository.count(),
            page=pagination.page,
            size=pagination.size,
        )

    def get(self, compra_id: int) -> CompraResponseDTO:
        compra = self.repository.get_by_id(compra_id)
        if compra is None:
            raise NotFoundException(f"Compra {compra_id} não encontrada")
        return CompraResponseDTO.model_validate(compra)

    def create(self, payload: CompraCreateDTO) -> CompraResponseDTO:
        compra = self.repository.add(Compra(**payload.model_dump()))
        return CompraResponseDTO.model_validate(compra)


def get_compra_service(db: DbSession) -> CompraService:
    return CompraService(CompraRepository(db))


CompraServiceDep = Annotated[CompraService, Depends(get_compra_service)]
```

**`controller.py`**: rotas tipadas por DTO
```python
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.modules.compras.dtos import CompraCreateDTO, CompraResponseDTO
from app.modules.compras.service import CompraServiceDep
from app.shared.dtos import ErrorResponseDTO, PageDTO, PaginationParamsDTO

router = APIRouter(prefix="/compras", tags=["Compras"])


@router.get("", response_model=PageDTO[CompraResponseDTO], summary="Listar compras")
def list_compras(
    service: CompraServiceDep, pagination: Annotated[PaginationParamsDTO, Query()]
) -> PageDTO[CompraResponseDTO]:
    return service.list(pagination)


@router.get(
    "/{compra_id}",
    response_model=CompraResponseDTO,
    summary="Consultar compra",
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponseDTO}},
)
def get_compra(compra_id: int, service: CompraServiceDep) -> CompraResponseDTO:
    return service.get(compra_id)


@router.post(
    "",
    response_model=CompraResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Criar compra",
)
def create_compra(payload: CompraCreateDTO, service: CompraServiceDep) -> CompraResponseDTO:
    return service.create(payload)
```

### 2. Registre o módulo

Em `app/modules/__init__.py`:
```python
from app.modules.compras.controller import router as compras_router
api_router.include_router(compras_router)
```

Em `app/core/openapi.py`, adicione a tag em `TAGS_METADATA`, para ela aparecer descrita no Swagger:
```python
{"name": "Compras", "description": "Cadastro e consulta de compras."},
```

### 3. Gere e aplique a migration

```bash
docker compose exec backend alembic revision --autogenerate -m "create compras"
docker compose exec backend alembic upgrade head
```

Você não precisa registrar o `model.py` em lugar nenhum: o `import_all_models()` encontra o model de cada módulo sozinho, tanto para o Alembic quanto para os testes. Confira sempre o arquivo gerado em `alembic/versions/` antes de aplicar.

### 4. Escreva os testes

Crie `tests/test_compras.py` usando a fixture `client` do `conftest.py`. O banco dos testes é criado a partir dos models, então não depende das migrations.

## Endpoints

Todas as rotas ficam sob o prefixo `/api`.

### Documentação (Swagger / OpenAPI)

| URL                                   | O que é                                   |
|---------------------------------------|-------------------------------------------|
| http://localhost:8000/api/docs        | Swagger UI (testar as rotas pelo browser) |
| http://localhost:8000/api/redoc       | ReDoc (documentação só de leitura)        |
| http://localhost:8000/api/openapi.json| schema OpenAPI 3 (para gerar clientes)    |
| http://localhost:8000/                | redireciona para o Swagger UI             |

A configuração fica em `app/core/openapi.py`: descrição geral da API, descrição de cada tag e parâmetros do Swagger UI (filtro, "Try it out" ligado, tempo de resposta). Cada rota declara `summary`, `description` e os erros possíveis (`responses=`), e os DTOs trazem `description` e `examples` nos `Field`, que viram o exemplo de payload no Swagger.

Para esconder a documentação (ex.: em produção), use `DOCS_ENABLED=false`.

### Rotas atuais

| Método | Rota                | Entrada           | Saída                       | Protegida |
|--------|---------------------|-------------------|-----------------------------|-----------|
| GET    | `/api/health`       | —                 | `HealthResponseDTO`         | não |
| POST   | `/api/auth/login`   | `LoginRequestDTO` | `AuthSessionResponseDTO` + cookie | não |
| POST   | `/api/auth/logout`  | —                 | 204 + apaga cookie          | não (idempotente) |
| GET    | `/api/auth/me`      | —                 | `AuthSessionResponseDTO`    | sim |
| POST   | `/api/auth/refresh` | —                 | `AuthSessionResponseDTO`    | sim |
| GET    | `/api/auth/events`  | —                 | stream SSE                  | cookie |
| POST   | `/api/orders`       | `OrderCreateDTO`  | `OrderResponseDTO` (202 novo / 200 reenvio) | header `X-Webhook-Key` |
| GET    | `/api/orders`       | `?status=&search=&page=&size=` | `PageDTO[OrderResponseDTO]` | sim |
| GET    | `/api/orders/stats` | —                 | `OrderStatsDTO`             | sim |
| GET    | `/api/orders/{id}`  | —                 | `OrderDetailDTO` (com histórico) | sim |
| POST   | `/api/graphql`      | query / mutation GraphQL | JSON GraphQL        | por operação (ver [GraphQL](#graphql)) |
| WS     | `/api/graphql`      | subscription (`graphql-transport-ws`) | eventos      | sim |

## Pedidos (desafio técnico)

### Visão geral

```
 sistema externo                      API (backend)                          worker (consumer)               sistema interno (mock)
 ───────────────    POST /api/orders  ───────────────   INSERT status=RECEIVED  ─────────────────   HTTP POST   ──────────────────────
  webhook       ──────────────────►  valida + grava  ──────────────────────►  orders (Postgres)  ◄── reserva ──  /internal/orders
                ◄──── 202 / 200 ───  (idempotente)                            é a própria fila   ───────────►  sucesso | 4xx | 5xx | timeout
                                                                              ◄── grava resultado + histórico
```

Três processos separados, cada um com seu container: `backend` (API), `worker` (consumer) e `internal-system` (mock). Eles se comunicam só pelo banco (API → worker) e por HTTP (worker → sistema interno).

### Estados

```
RECEIVED ──► PROCESSING ──► PROCESSED
                 │ ▲
                 │ └── falha temporária: nova tentativa com backoff (continua PROCESSING)
                 └──► FAILED   (recusa definitiva ou tentativas esgotadas)
```

As transições ficam em `ALLOWED_TRANSITIONS` (`orders/model.py`), e `Order.transition_to()` rejeita qualquer outra (ex.: `PROCESSED → PROCESSING`). `PROCESSED` e `FAILED` são finais.

### Como testar na mão

Com o `docker compose up` rodando:

```bash
# pedido do enunciado -> 202, status RECEIVED (em ~1s o worker processa)
curl -i -X POST http://localhost:8000/api/orders \
  -H "Content-Type: application/json" -H "X-Webhook-Key: dev-webhook-key" \
  -d '{ "externalId": "ORDER-123", "customer": "Cliente Exemplo", "amount": 150.00 }'
```

Repita o mesmo comando: a resposta é `200` com o mesmo pedido e o header `Idempotent-Replayed: true`. Mude o `amount` e mantenha o `externalId`: a resposta é `409 EXTERNAL_ID_CONFLICT`.

Para consultar, faça login (crie um usuário antes, ver [Criando usuários](#criando-usuários)):

```bash
curl -c cookies.txt -H "Content-Type: application/json" -d '{"username":"admin","password":"SUA_SENHA"}' http://localhost:8000/api/auth/login
curl -b cookies.txt "http://localhost:8000/api/orders?status=FAILED"
curl -b cookies.txt http://localhost:8000/api/orders/1        # detalhe + histórico de tentativas
curl -b cookies.txt http://localhost:8000/api/orders/stats
```

Pelo Swagger (http://localhost:8000/api/docs) é mais simples: faça o login em `POST /api/auth/login`, clique em **Authorize** e informe a chave `dev-webhook-key` para o webhook.

### Cenários do sistema interno (mock)

O cenário é escolhido pelo prefixo do `externalId`:

| `externalId`   | O que o mock faz | Resultado esperado |
|----------------|------------------|--------------------|
| qualquer outro | aceita e devolve um protocolo (`INT-…`) | `PROCESSED` na 1ª tentativa* |
| `FAIL-…`       | recusa com HTTP 422 | `FAILED` na 1ª tentativa, sem repetir |
| `FLAKY-…`      | HTTP 503 nas 2 primeiras chamadas | `PROCESSED` na 3ª tentativa |
| `TIMEOUT-…`    | demora 30s (o worker desiste em 5s) | 3 tentativas e depois `FAILED` (tentativas esgotadas) |
| valor > 100000 | recusa com HTTP 422 | `FAILED` na 1ª tentativa |

\* `INTERNAL_SYSTEM_FAILURE_RATE` (padrão `0.2` no compose) faz 20% das chamadas falharem ao acaso com 503. Isso exercita as retentativas também nos pedidos comuns. Use `0` para um comportamento 100% determinístico.

O histórico (`GET /api/orders/{id}` → `history`) mostra cada tentativa com duração, resultado e mensagem.

### Decisões técnicas

**Fila no próprio Postgres, sem broker.** A tabela `orders` é a fila. O worker reserva pedidos com `SELECT … FOR UPDATE SKIP LOCKED`.
- **Atomicidade:** gravar o pedido e enfileirá-lo é **a mesma transação**. Com um broker (RabbitMQ, SQS), seria preciso gravar no banco *e* publicar a mensagem, e uma das duas pode falhar sozinha. Isso exigiria o padrão *transactional outbox* para não perder pedidos.
- **Concorrência:** o `SKIP LOCKED` permite **vários workers em paralelo** (`docker compose up -d --scale worker=3`) sem que dois peguem o mesmo pedido.
- **Menos infraestrutura:** nada novo para subir ou monitorar. Para volumes bem maiores, o caminho seria outbox + broker, mantendo o mesmo `OrderProcessor`.

**Idempotência em três camadas:**
1. **Recebimento:** `UNIQUE(external_id)` no banco. É o que vale de verdade, inclusive com requisições simultâneas. O service primeiro busca o pedido; se duas requisições passarem juntas pela busca, a constraint barra a segunda (`IntegrityError`), que é respondida como reenvio. Testado com 10 envios simultâneos: 1 × `202`, 9 × `200`, 1 pedido gravado.
2. **Processamento:** um pedido só é reservado quando está pendente e sem reserva ativa. `PROCESSED`/`FAILED` nunca voltam para a fila.
3. **Integração:** o worker envia `Idempotency-Key: <externalId>` ao sistema interno. Se o worker morrer *depois* de o sistema interno aceitar e *antes* de gravar `PROCESSED`, o reenvio é reconhecido e não gera um segundo processamento lá.

**Reenvio com dados diferentes = `409`, não `200`:** o mesmo `externalId` com cliente ou valor diferentes indica erro na origem. Aceitar em silêncio esconderia o problema.

**Tratamento de falhas:**

| Falha | Tratamento |
|-------|------------|
| Timeout, erro de rede, HTTP 5xx/408/429 | **temporária**: nova tentativa com backoff exponencial (5s, 10s, 20s…), até `ORDER_MAX_ATTEMPTS` (3). Depois, `FAILED` |
| Demais HTTP 4xx (pedido recusado) | **definitiva**: `FAILED` na hora, sem repetir |
| Worker morre no meio do envio | a reserva (`locked_until`, 60s) vence e outro worker retoma o pedido. Se o antigo "voltar", o `lease_token` impede que ele sobrescreva o resultado |
| Worker morre na última tentativa | ao retomar, o pedido vira `FAILED` (tentativas esgotadas) |
| Erro inesperado num pedido | é registrado no log; o pedido fica reservado até a reserva vencer e é retomado; o resto do lote segue |
| Banco fora do ar | o worker registra o erro e tenta de novo no próximo ciclo, sem cair |
| Falha ao gravar no recebimento | a API responde 5xx e o sistema externo reenvia; a idempotência torna o reenvio seguro |

Cada envio fica registrado em `order_attempts`. Os logs do worker (serviço `pure-eletric-worker` no Kibana) levam `order_id` e `external_id` nos labels.

**Webhook autenticado por chave:** o header `X-Webhook-Key` é comparado em tempo constante (`hmac.compare_digest`). As consultas usam a sessão de login dos usuários. O webhook é para sistemas, a consulta é para pessoas.

**Contrato em camelCase:** o enunciado define o payload como `externalId`, então o módulo de pedidos usa camelCase na entrada e na saída. O `amount` sai como string (`"150.00"`) para não perder precisão, como todos os `Decimal` da API.

**Por que o worker consulta a fila (polling):** o worker consulta a fila a cada 1s quando ela está vazia (`WORKER_POLL_SECONDS`). É simples e robusto a quedas de conexão, e a latência é de no máximo 1s. O `LISTEN/NOTIFY` do Postgres é usado no sentido oposto: para a API avisar a interface em tempo real (ver [GraphQL](#graphql)).

## GraphQL

O GraphQL é **outra porta de entrada para as mesmas regras**. Os resolvers só traduzem GraphQL para os DTOs e chamam o mesmo `OrderService` do REST. Validação, idempotência, estados e worker são os mesmos. O REST continua existindo: o webhook de pedidos é consumido por sistemas externos, que quase sempre falam REST.

```
            REST  /api/orders ──┐
                                ├──► OrderService ──► Postgres (fila) ──► worker ──► sistema interno
 GraphQL  /api/graphql ─────────┘          ▲                                  │
      ▲                                    │                                  │ pg_notify na mesma transação
      └── subscription orderUpdated ◄── LISTEN (API) ◄────────────────────────┘
```

- **Endpoint:** `POST /api/graphql`. Abrindo no navegador aparece o **GraphiQL**, a tela para montar e testar queries (só com `DOCS_ENABLED=true`).
- **Contrato:** [`schema.graphql`](schema.graphql). Depois de mudar o schema, rode `python -m app.cli export-graphql-schema`. Um teste falha se o arquivo estiver desatualizado.
- **Biblioteca:** [Strawberry](https://strawberry.rocks). O schema é definido em Python, com tipos por anotação.

### Operações

| Operação | Tipo | Autenticação |
|----------|------|--------------|
| `orders(status, search, page, size)` | query | login (cookie) |
| `order(id)` / `orderByExternalId(externalId)` | query | login |
| `orderStats` | query | login |
| `receiveOrder(input)` | mutation | header `X-Webhook-Key` (igual ao webhook REST) |
| `orderUpdated(id)` | subscription (WebSocket) | login |
| `simulateOrders(input)` / `resendOrder(id)` | mutation (simulador) | login + `ORDER_SIMULATOR_ENABLED=true` |
| `orderSimulatorEnabled` | query | login |

```graphql
# Lista com o histórico de cada pedido (o histórico vem em 1 consulta só, via DataLoader)
{
  orders(status: FAILED, size: 10) {
    total
    items { externalId customer amount status lastError history { number outcome durationMs } }
  }
  orderStats { received processing processed failed total }
}

# Mesmo efeito do POST /api/orders (idempotente; created=false no reenvio)
mutation {
  receiveOrder(input: { externalId: "ORDER-123", customer: "Cliente Exemplo", amount: "150.00" }) {
    created
    order { id status }
  }
}

# Tempo real: recebe o pedido a cada mudança de status (sem id = todos os pedidos)
subscription {
  orderUpdated { externalId status attempts lastError internalReference }
}
```

Com `curl` (a mutation usa a chave do webhook; as queries usam o cookie do login):

```bash
curl -H "Content-Type: application/json" -H "X-Webhook-Key: dev-webhook-key" \
  -d '{"query":"mutation { receiveOrder(input: {externalId: \"ORDER-9\", customer: \"Ana\", amount: \"10.00\"}) { created order { id status } } }"}' \
  http://localhost:8000/api/graphql
```

### Tempo real (subscription)

1. Toda mudança de status (recebido, reservado pelo worker, falha com retentativa, processado, falhou) executa `pg_notify('order_events', {id, status})` **na mesma transação** da mudança. O Postgres só entrega o aviso se o commit acontecer, então nunca chega aviso de um status que não foi gravado.
2. A API mantém uma conexão com `LISTEN order_events`, aberta na subida (`lifespan`), que se reconecta sozinha se cair, e repassa cada aviso ao `OrderEventBroker`.
3. Cada subscription recebe o aviso, **lê o pedido atualizado do banco** e o envia ao cliente. O evento só diz "este pedido mudou"; os dados vêm sempre do banco.

Testado de ponta a ponta com um pedido `FLAKY-…` passando pelo proxy do Vite. As 7 mudanças chegaram ao vivo: `RECEIVED`, `PROCESSING` (1ª tentativa), falha com retentativa agendada, 2ª tentativa depois de 5s, falha, 3ª tentativa depois de 10s e o resultado final.

**Segurança do WebSocket:**
- a conexão só é aceita com sessão de login válida (código `4403` caso contrário);
- a origem precisa ser a própria API ou estar em `CORS_ORIGINS`, porque WebSocket não passa pelo CORS;
- ficar conectado **não** renova a sessão, igual ao stream SSE do login;
- quando a sessão acaba, a subscription termina com `SESSION_EXPIRED`.

Se nenhuma aba estiver ouvindo, os avisos simplesmente se perdem, e está tudo bem: o estado oficial está no banco. Um assinante lento tem uma fila de 100 eventos; o excedente é descartado sem travar os outros.

### Decisões e proteções

- **Resolvers assíncronos, service síncrono:** toda chamada ao service passa por `ctx.run()`, que abre uma sessão de banco própria e roda numa thread. Chamar o service direto travaria o servidor inteiro enquanto o banco responde. As chamadas de um mesmo request são feitas uma por vez, então uma query com muitos campos não ocupa várias conexões do pool.
- **Sem N+1:** o `history` usa DataLoader. Uma lista de 20 pedidos faz 1 consulta de tentativas, não 20; um teste conta as consultas SQL para garantir.
- **Mesmos erros do REST:** os erros de negócio saem com `extensions.code` (`NOT_AUTHENTICATED`, `SESSION_EXPIRED`, `EXTERNAL_ID_CONFLICT`, `INVALID_WEBHOOK_KEY`). Entrada inválida sai como `BAD_USER_INPUT`, com a lista de campos em `extensions.fields`. Erros inesperados aparecem ao cliente só como "Erro interno…" e ficam registrados no log.
- **Limites contra queries abusivas:** profundidade máxima (`GRAPHQL_MAX_DEPTH`), número de aliases (`GRAPHQL_MAX_ALIASES`) e tamanho da query (`GRAPHQL_MAX_TOKENS`). A introspection (consultar o schema) segue `DOCS_ENABLED`, ou `GRAPHQL_INTROSPECTION`.
- **Só POST:** queries por GET estão desligadas, para que links de outros sites não disparem consultas com o cookie do usuário.
- **Login:** é a mesma sessão do REST, com o mesmo cookie. As queries renovam os 30 minutos, como qualquer rota.
- **Rodando a API fora do Docker no Windows:** o tempo real fica desligado, porque o driver assíncrono do Postgres não funciona no event loop padrão do Windows. Queries e mutation funcionam normalmente. No Docker (Linux) funciona tudo.

## Autenticação e sessão

A sessão é **controlada inteiramente pelo backend**. Ele guarda as sessões no banco, decide quando cada uma expira e avisa o navegador quando é hora de deslogar.

### Como funciona

1. `POST /api/auth/login` com `{ "username": "...", "password": "..." }`. O `username` também aceita o e-mail.
2. O backend confere a senha (bcrypt), cria uma linha em `user_sessions` e devolve um **cookie `pe_session` HttpOnly** com um token aleatório de 256 bits.
   - O token **não** vai no corpo da resposta, e o JavaScript do navegador não consegue lê-lo. Isso protege a sessão contra roubo por XSS.
   - O banco guarda só o **hash SHA-256** do token. Se o banco vazar, as sessões não podem ser sequestradas.
3. A cada request autenticado, o backend confere a sessão no banco e **renova o prazo de inatividade**.
4. A sessão termina, e fica registrada com `ended_at` e `end_reason`, quando acontece uma destas situações:

| `end_reason`       | Quando |
|--------------------|--------|
| `idle_timeout`     | **30 minutos sem nenhuma requisição autenticada** (`SESSION_IDLE_TIMEOUT_MINUTES`) |
| `absolute_timeout` | 8 horas desde o login, mesmo com uso contínuo (`SESSION_ABSOLUTE_TIMEOUT_MINUTES`) |
| `logout`           | o usuário saiu (em qualquer aba) ou fez login de novo no mesmo navegador |
| `revoked`          | o usuário foi desativado |

> Para deslogar **30 minutos após o login**, mesmo com uso contínuo, use `SESSION_ABSOLUTE_TIMEOUT_MINUTES=30`.

### O sinal de logout (SSE)

O frontend abre um stream **Server-Sent Events** em `GET /api/auth/events`. Por ele, o backend avisa o navegador:

| Evento     | Quando | `data` |
|------------|--------|--------|
| `session`  | ao conectar e sempre que o prazo é renovado | `{ "expires_at", "remaining_seconds" }` |
| `expiring` | faltam 2 minutos para expirar (`SESSION_WARNING_SECONDS`) | `{ "expires_at", "remaining_seconds" }` |
| `logout`   | a sessão acabou, por qualquer um dos motivos acima | `{ "reason", "detail" }` |

- Ficar conectado no stream **não** conta como atividade, então não mantém a sessão viva sozinho.
- O stream confere a sessão a cada 5 segundos e também **no instante exato da expiração**. O logout feito em outra aba chega em até 5 segundos.
- Sem cookie, a rota responde `204`, e o `EventSource` para de tentar reconectar.

Exemplo de uso no frontend:

```ts
const events = new EventSource('/api/auth/events')

events.addEventListener('expiring', () => {
  // mostrar aviso "sua sessão vai expirar" com um botão que chama POST /api/auth/refresh
})

events.addEventListener('logout', (e) => {
  const { detail } = JSON.parse((e as MessageEvent).data)
  events.close()
  // limpar o estado do app e navegar para /login mostrando `detail`
})
```

Além do stream, qualquer rota protegida responde **401 com `code: "SESSION_EXPIRED"`** (e apaga o cookie) quando a sessão acabou. O frontend deve tratar isso da mesma forma que o evento `logout`.

### Protegendo rotas de outros módulos

```python
from app.modules.auth.dependencies import CurrentAdmin, CurrentUser

@router.get("")
def listar(user: CurrentUser) -> ...:        # qualquer usuário logado
    ...

@router.delete("/{id}")
def remover(id: int, admin: CurrentAdmin) -> ...:  # só perfil ADMIN (403 para os demais)
    ...
```

Toda rota com `CurrentUser` aparece com cadeado no Swagger e renova a sessão.

### Outras proteções

- **Limite de tentativas:** 5 logins por minuto por IP (`LOGIN_RATE_LIMIT`). Acima disso, a resposta é `429`. Atrás de proxy, o IP real vem do `X-Forwarded-For`, aceito só dos IPs em `FORWARDED_ALLOW_IPS`.
- **Mesma resposta para usuário inexistente e senha errada** (`401 INVALID_CREDENTIALS`). O tempo de resposta também é o mesmo, para não revelar quais usuários existem.
- **Cookie `SameSite=Lax`:** o navegador não envia o cookie em POSTs vindos de outros sites (proteção contra CSRF). Em produção, use HTTPS com `SESSION_COOKIE_SECURE=true`.

### Criando usuários

Ainda não há tela de cadastro. Crie pelo terminal. Sem `--password`, a senha é digitada sem aparecer na tela:

```bash
docker compose exec backend python -m app.cli create-user --username admin --email admin@exemplo.com --admin
```

## Configuração

As variáveis são lidas por `app/core/config.py`. Fora do Docker, copie `.env.example` para `.env`.

| Variável            | Padrão                  |
|---------------------|-------------------------|
| `POSTGRES_USER`     | `postgres`              |
| `POSTGRES_PASSWORD` | `postgres`              |
| `POSTGRES_DB`       | `pure_eletric`          |
| `POSTGRES_HOST`     | `localhost` (no Docker: `db`) |
| `POSTGRES_PORT`     | `5432`                  |
| `CORS_ORIGINS`      | `http://localhost:5173` (lista separada por vírgula) |
| `DEBUG`             | `false` (quando `true`, loga o SQL) |
| `DOCS_ENABLED`      | `true` (quando `false`, desliga Swagger, ReDoc e `/openapi.json`) |
| `SESSION_IDLE_TIMEOUT_MINUTES` | `30` (desloga após N minutos sem requisições) |
| `SESSION_ABSOLUTE_TIMEOUT_MINUTES` | `480` (tempo máximo de vida da sessão) |
| `SESSION_WARNING_SECONDS` | `120` (antecedência do evento `expiring`) |
| `SESSION_EVENTS_POLL_SECONDS` | `5` (intervalo de checagem do stream SSE) |
| `SESSION_COOKIE_NAME` | `pe_session` |
| `SESSION_COOKIE_SECURE` | `false` (use `true` em produção com HTTPS) |
| `SESSION_COOKIE_SAMESITE` | `lax` |
| `LOGIN_RATE_LIMIT`  | `5/minute` (por IP) |
| `RATE_LIMIT_ENABLED` | `true` |
| `PASSWORD_HASH_ROUNDS` | `12` (custo do bcrypt) |
| `FORWARDED_ALLOW_IPS` | lido pelo uvicorn: de quais IPs aceitar `X-Forwarded-For` (no compose: `*`) |
| `LOG_LEVEL`         | `INFO` |
| `ENVIRONMENT`       | `development` (vira `service.environment` nos logs) |
| `ELASTICSEARCH_URL` | vazio = só console (no compose: `http://elasticsearch:9200`) |
| `ELASTICSEARCH_LOGS_DATA_STREAM` | `logs-pure_eletric.api-default` |
| `ORDERS_WEBHOOK_KEY` | vazio = webhook aberto (só dev). No compose: `dev-webhook-key` |
| `INTERNAL_SYSTEM_URL` | `http://localhost:9000` (no compose: `http://internal-system:9000`) |
| `INTERNAL_SYSTEM_TIMEOUT_SECONDS` | `5` (acima disso o envio conta como falha temporária) |
| `ORDER_MAX_ATTEMPTS` | `3` (1ª tentativa + retentativas) |
| `ORDER_RETRY_BASE_SECONDS` | `5` (backoff: 5s, 10s, 20s…) |
| `ORDER_LEASE_SECONDS` | `60` (reserva do worker; precisa ser maior que o timeout) |
| `WORKER_POLL_SECONDS` | `1` (intervalo de consulta da fila quando vazia) |
| `WORKER_BATCH_SIZE` | `10` (pedidos reservados por ciclo) |
| `INTERNAL_SYSTEM_FAILURE_RATE` | só do mock: fração de falhas aleatórias (no compose: `0.2`) |
| `ORDER_SIMULATOR_ENABLED` | `false` (no compose: `true`). Liga o simulador de pedidos da interface |
| `ORDER_EVENTS_LISTENER_ENABLED` | `true` (ouve o `LISTEN` do Postgres para a subscription) |
| `ORDER_EVENTS_CHANNEL` | `order_events` |
| `GRAPHQL_MAX_DEPTH` | `8` (profundidade máxima de uma query) |
| `GRAPHQL_MAX_ALIASES` | `15` |
| `GRAPHQL_MAX_TOKENS` | `2000` (tamanho máximo da query) |
| `GRAPHQL_INTROSPECTION` | vazio = segue `DOCS_ENABLED` |

## Logs (Elasticsearch + Kibana)

Todo log da API sai no console e, com `ELASTICSEARCH_URL` definido, também vai para o Elasticsearch. Para ver, abra o **Kibana em http://localhost:5601 > Discover**; o data view *API Pure Eletric - logs* é criado sozinho pelo serviço `kibana-setup` do compose.

| Arquivo | Papel |
|---------|-------|
| `app/core/request_logging.py` | **Interceptor**: um log por request com método, rota, status, duração, IP, user agent e usuário logado. Gera o `X-Request-ID` (devolvido no header da resposta). |
| `app/core/logger.py` | `setup_logging()`: console + Elasticsearch, e anexa o id do request a todo log emitido durante ele. |
| `app/core/elasticsearch_handler.py` | Envia os logs em lotes, numa thread separada, para o data stream `logs-pure_eletric.api-default` (formato ECS). Se o Elasticsearch estiver fora, guarda e reenvia; nunca trava nem derruba a API. |

Nível do log por status: `INFO` (2xx/3xx), `WARNING` (4xx) e `ERROR` (5xx, com stack trace em `error.stack_trace`). Por segurança, **corpo de request/response, cookies e headers de autenticação nunca são registrados**.

Filtros úteis no Discover (KQL):

```
log.level : "ERROR"                      # só erros
http.response.status_code >= 400          # respostas com erro
http.request.id : "<X-Request-ID>"        # tudo o que aconteceu num request
user.id : "1"                             # requests de um usuário
event.duration > 500000000                # requests acima de 500 ms (nanossegundos)
```

Para logar no seu módulo, use o `logging` padrão; os logs vão para o Kibana com o id do request:

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Compra criada", extra={"ecs": {"labels": {"compra_id": compra.id}}})
```

## Rodando

Com Docker, a partir da raiz do projeto:

```bash
docker compose up --build backend
```

O Postgres sobe junto. As migrations rodam sozinhas pelo `entrypoint.sh`.
Depois que subir, abra o Swagger em **http://localhost:8000/api/docs** para testar a API.

Sem Docker (precisa de um Postgres acessível):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

O Swagger fica no mesmo endereço: **http://localhost:8000/api/docs**.

## Testes

```bash
pytest
```

O `tests/conftest.py` troca a sessão do banco por um **SQLite em memória**, então os testes não precisam do Postgres. Dentro do Docker:

```bash
docker compose exec backend pytest
```

## Migrations: comandos úteis

```bash
alembic revision --autogenerate -m "descricao"   # gera migration a partir dos models
alembic upgrade head                             # aplica tudo
alembic downgrade -1                             # desfaz a última
alembic history                                  # lista as migrations
```

No Docker, prefixe com `docker compose exec backend`.
