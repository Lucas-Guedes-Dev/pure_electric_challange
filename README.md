# Desafio Técnico · Pure Eletric

Recebimento e processamento assíncrono de pedidos. Os pedidos chegam por webhook e são gravados; um worker separado os envia a um sistema interno simulado; o status pode ser consultado por API ou pela interface, com atualização em tempo real.

**Stack:** Python 3.12 · FastAPI · PostgreSQL 17 · React 19 + TypeScript · Docker Compose

## Como rodar

**Pré-requisito:** Docker Desktop rodando. A stack completa inclui Elasticsearch e Kibana, que usam cerca de 2,5 GB de RAM. No Windows, reserve pelo menos 6 GB para o Docker (arquivo `%UserProfile%\.wslconfig` com `[wsl2]` e `memory=6GB`, depois `wsl --shutdown`).

**1. Subir a aplicação**

```bash
docker compose up --build
```

Com pouca memória, dá para subir sem Elasticsearch e Kibana. A aplicação funciona igual; só os logs ficam no console:

```bash
docker compose up --build db backend worker internal-system frontend
```

As migrations rodam sozinhas quando o backend sobe, e o worker só inicia depois disso.

**2. Criar um usuário** (para entrar na interface e consultar pedidos). A senha é pedida no terminal:

```bash
docker compose exec backend python -m app.cli create-user --username admin --email admin@exemplo.com --admin
```

**3. Acessar**

| O quê | Endereço |
|-------|----------|
| Interface (login, pedidos, simulador) | http://localhost:5173 |
| API REST + documentação (Swagger) | http://localhost:8000/api/docs |
| GraphQL (GraphiQL) | http://localhost:8000/api/graphql |
| Sistema interno simulado | http://localhost:9000/docs |
| Logs (Kibana, só na stack completa) | http://localhost:5601 |

**4. Enviar pedidos**

- **Pela interface:** entre em **Pedidos → Simular pedidos**, escolha um cenário (sucesso, instável, recusado, sem resposta ou aleatório) e acompanhe o status mudar ao vivo.
- **Pelo webhook**, como um sistema externo:

  ```bash
  curl -i -X POST http://localhost:8000/api/orders \
    -H "Content-Type: application/json" -H "X-Webhook-Key: dev-webhook-key" \
    -d '{ "externalId": "ORDER-123", "customer": "Cliente Exemplo", "amount": 150.00 }'
  ```

  O prefixo do `externalId` escolhe como o sistema interno responde: `FAIL-…` recusa, `FLAKY-…` falha 2 vezes e depois aceita, `TIMEOUT-…` não responde a tempo, `OUTAGE-…` fica fora do ar nas 3 tentativas (termina `FAILED`) e volta depois, para demonstrar o reprocessamento. Qualquer outro prefixo é aceito.

> O sistema interno simulado também **falha ao acaso em 20% das chamadas**, para mostrar as retentativas. Raramente, um pedido comum termina `FAILED` depois de 3 tentativas. Para um comportamento 100% previsível, crie um arquivo `.env` na raiz com `INTERNAL_SYSTEM_FAILURE_RATE=0` antes de subir.

**5. Rodar os testes**

```bash
docker compose exec backend pytest        # backend
docker compose exec frontend npm test     # frontend
```

**6. Parar**

```bash
docker compose down        # para tudo
docker compose down -v     # para tudo e apaga os dados do banco
```

Documentação técnica detalhada: [backend/README.md](backend/README.md) e [frontend/README.md](frontend/README.md).

## Requisitos obrigatórios

Todos os 12 requisitos são cumpridos. Os testes automatizados passam: 128 no backend (94 deles das regras de pedidos) e 25 no frontend.

| Requisito | Status | Como é cumprido | Onde no código |
|-----------|:------:|-----------------|----------------|
| Recebimento do pedido via API/webhook | ✅ | `POST /api/orders`, autenticado pelo header `X-Webhook-Key`. Também pela mutation GraphQL `receiveOrder` | `backend/app/modules/orders/controller.py` |
| Validação básica do payload | ✅ | `externalId` (1 a 100 caracteres, sem espaços), `customer` obrigatório, `amount` maior que 0 com até 2 casas. Erro responde `422` indicando o campo | `orders/dtos.py` → `OrderCreateDTO` |
| Persistência dos pedidos | ✅ | Postgres: tabela `orders` e o histórico de cada envio em `order_attempts` | migration `backend/alembic/versions/0002_…` |
| Garantia de idempotência | ✅ | `externalId` único no banco. Reenvio igual responde `200` com o pedido original; dados diferentes respondem `409`. Testado com 10 envios simultâneos: 1 pedido gravado. O worker também envia `Idempotency-Key` ao sistema interno | `orders/service.py` → `OrderService.receive` |
| Processamento assíncrono | ✅ | A API só grava o pedido e responde `202`; o processamento acontece depois, fora da requisição | `orders/processor.py` |
| Consumer/worker | ✅ | Container `worker` separado da API. Pode rodar com várias cópias (`--scale worker=3`), sem que dois workers processem o mesmo pedido (`FOR UPDATE SKIP LOCKED`) | `orders/worker.py` + `orders/processor.py` |
| Simulação do envio para um sistema interno separado, com sucesso e falha | ✅ | Container `internal-system` separado, com cenários de sucesso, recusa (422), instável (503) e timeout, além de falhas aleatórias. Na interface, o **simulador** envia pedidos em cada cenário | `backend/internal_system/main.py` |
| Controle dos estados RECEIVED, PROCESSING, PROCESSED e FAILED | ✅ | Transições validadas: uma transição inválida, como `PROCESSED → PROCESSING`, é rejeitada. `FAILED → RECEIVED` só por reprocessamento manual | `orders/model.py` → `OrderStatus` + `ALLOWED_TRANSITIONS` |
| Tratamento básico de falhas | ✅ | Nova tentativa com espera crescente (5 s e depois 10 s) para falhas temporárias; `FAILED` direto quando o sistema interno recusa; se o worker cair, outro retoma o pedido quando a reserva vence; histórico de cada tentativa; reprocessamento manual de pedidos `FAILED` (`POST /api/orders/{id}/reprocess`, mutation `reprocessOrder` e botão no detalhe do pedido) | `orders/processor.py` + `orders/internal_client.py` + `OrderService.reprocess` |
| Consulta dos pedidos e respectivos status | ✅ | REST (`GET /api/orders`, `/api/orders/{id}`, `/api/orders/stats`), GraphQL (queries e subscription em tempo real) e a interface em http://localhost:5173/pedidos | `orders/controller.py`, `orders/graphql.py`, `frontend/src/pages/OrdersPage.tsx` |
| Testes das principais regras de negócio | ✅ | Validação, idempotência (inclusive concorrente), estados, retentativas, falhas, retomada após queda do worker, reprocessamento, integração com o mock, GraphQL e simulador | `backend/tests/test_orders_*.py`, `test_order_reprocess.py`, `test_graphql_*.py`, `test_order_simulator.py`; `frontend/src/**/*.test.ts(x)` |
| README com instruções, decisões técnicas e respostas | ✅ | Este arquivo: como rodar, esta tabela e as respostas às perguntas do desafio (idempotência, indisponibilidade, evolução, decisões técnicas, trade-offs e pendências) | [Perguntas do desafio](#perguntas-do-desafio) |

## Perguntas do desafio

### Idempotência: como o mesmo `externalId` não é processado duas vezes?

A garantia existe em três momentos:

1. **No recebimento, pelo banco.** A coluna `external_id` é `UNIQUE`. Antes de gravar, a API procura o `externalId`:
   - já existe com os mesmos dados: responde `200` com o pedido original (header `Idempotent-Replayed: true`), sem criar nada;
   - já existe com cliente ou valor diferentes: responde `409 EXTERNAL_ID_CONFLICT`, porque não dá para saber qual versão vale;
   - duas requisições simultâneas passam juntas pela busca: a constraint barra a segunda no `INSERT`, e ela é respondida como reenvio. Testado com 10 envios simultâneos: 1 × `202`, 9 × `200`, 1 pedido gravado.
2. **No processamento, pela fila.** O worker reserva pedidos com `SELECT … FOR UPDATE SKIP LOCKED`: dois workers nunca pegam o mesmo pedido. A reserva tem um `lease_token`; se ela vencer e outro worker assumir, o resultado do worker antigo é descartado. `PROCESSED` e `FAILED` são estados finais e nunca voltam para a fila.
3. **Na integração, pelo sistema interno.** O worker envia o header `Idempotency-Key: <externalId>`. Se ele cair *depois* de o sistema interno aceitar e *antes* de gravar `PROCESSED`, o reenvio é reconhecido e o sistema interno não processa de novo.

Na interface, o botão **Reenviar pedido** (detalhe do pedido) demonstra a idempotência.

### Indisponibilidade e lentidão: o que acontece se o sistema interno cair ou ficar lento?

- **O recebimento não é afetado.** A API só grava o pedido e responde `202`; ela nunca chama o sistema interno. Pedidos continuam entrando normalmente mesmo com ele fora do ar.
- **Lentidão vira timeout.** O worker espera no máximo 5 s (`INTERNAL_SYSTEM_TIMEOUT_SECONDS`). Acima disso, a tentativa conta como falha temporária.
- **Falhas temporárias** (timeout, erro de rede, HTTP 5xx, 408, 425 e 429) geram uma nova tentativa com espera crescente: 5 s e depois 10 s (`ORDER_RETRY_BASE_SECONDS`). Enquanto espera, o pedido fica `PROCESSING` e aparece como "Aguardando retentativa", com contagem regressiva na interface. Depois de 3 tentativas (`ORDER_MAX_ATTEMPTS`), vira `FAILED` com a mensagem "Tentativas esgotadas".
- **Recusas** (demais HTTP 4xx) viram `FAILED` na hora, sem repetir, porque tentar de novo não mudaria a resposta.
- **Worker que cai no meio do envio:** a reserva do pedido vence em 60 s e outro worker o retoma.
- **Queda mais longa que as retentativas:** o pedido termina `FAILED`, mas não se perde. Quando o sistema interno voltar, um administrador o **reprocessa** (botão no detalhe do pedido, `POST /api/orders/{id}/reprocess` ou mutation `reprocessOrder`). O pedido volta para `RECEIVED` com uma rodada nova de 3 tentativas; o histórico anterior é mantido e fica registrado quem reprocessou, quando, o motivo e o erro anterior. O `Idempotency-Key` enviado ao sistema interno continua o mesmo: se uma tentativa antiga tiver sido processada lá apesar do timeout, o reprocessamento recebe o mesmo protocolo em vez de duplicar o pedido.
- **Diagnóstico:** cada tentativa fica registrada em `order_attempts`, com duração, resultado e mensagem, e também vai para os logs (Kibana).

Os cenários `FLAKY-…` (instável), `TIMEOUT-…` (sem resposta) e `OUTAGE-…` (fora do ar, para reprocessar depois) do simulador reproduzem esses casos.

### Evolução da arquitetura: como integrar ERP, transportadora e gateway de pagamento?

1. **Um envio por destino.** Hoje cada pedido tem um único envio. Com vários sistemas, a fila passaria a ser de envios: uma tabela `order_dispatches(order_id, target, status, attempts, next_attempt_at, lease_token…)`, com a mesma lógica atual de reserva, retentativas e histórico, mas separada por destino. O status do pedido passaria a ser derivado dos envios (ex.: `PROCESSED` quando todos os obrigatórios concluírem).
2. **Um adaptador por sistema.** O worker já depende de uma interface (`InternalSystem.send()`), e não do HTTP diretamente. Cada integração ganharia o seu adaptador (`ErpClient`, `CarrierClient`, `PaymentGatewayClient`), que traduz o formato e classifica os erros como temporários ou definitivos, com timeout, número de tentativas e limite de chamadas próprios.
3. **Ordem e compensação.** Quando há dependência (ex.: só chamar a transportadora depois de o pagamento ser aprovado), uma saga coordena as etapas e define compensações para quando algo falha no meio (ex.: estornar o pagamento se o ERP recusar).
4. **Broker de mensagens.** Com vários consumidores e mais volume, eu trocaria a fila no Postgres por **outbox transacional + broker** (RabbitMQ, Kafka ou SQS). O pedido e o evento `order.received` continuam sendo gravados na mesma transação, e cada integração consome o evento na sua própria fila, com fila de mensagens mortas (DLQ) e possibilidade de reprocessar.
5. **Isolamento.** Workers separados por destino e *circuit breaker* por integração: um ERP lento não pode atrasar os pagamentos.
6. **Retornos desses sistemas** (pagamento aprovado, código de rastreio) chegariam por webhooks de entrada, com o mesmo padrão idempotente do recebimento de pedidos e assinatura HMAC de cada provedor.

### Decisões técnicas: principais escolhas

| Área | Escolha | Por quê |
|------|---------|---------|
| Backend | **FastAPI + Pydantic + SQLAlchemy 2 + Alembic**, MVC por módulo | Tipagem de ponta a ponta: DTOs validam a entrada e documentam a API (Swagger) sem código extra |
| Banco | **PostgreSQL** | Transações, `UNIQUE` para a idempotência, `SKIP LOCKED` para a fila e `LISTEN/NOTIFY` para o tempo real |
| Fila | **A própria tabela `orders`** (`FOR UPDATE SKIP LOCKED`) | Gravar o pedido e enfileirá-lo é uma única transação: sem o risco de gravar e não publicar, que um broker exigiria tratar com outbox |
| Worker | **Processo e container separados**, com reserva e espera crescente | Processamento fora da requisição, escalável (`--scale worker=3`) e que se recupera se um worker cair |
| Sistema interno | **Serviço HTTP mockado em container próprio** | Integração real por rede, com timeouts e erros de verdade, e cenários reproduzíveis pelo prefixo do `externalId` |
| Tempo real | **GraphQL (Strawberry) + subscription por WebSocket**, alimentada por `LISTEN/NOTIFY` | A interface vê cada mudança de status na hora, sem ficar consultando a API |
| Frontend | **React + Vite + TypeScript**, urql com cache normalizado, tipos gerados do schema | A tela se atualiza sozinha e os tipos acompanham o contrato do backend |
| Autenticação | **Sessão no servidor + cookie HttpOnly**; webhook com chave própria | Sessão revogável e invisível ao JavaScript; sistemas externos e pessoas autenticam de formas diferentes |
| Operação | **Docker Compose**; logs estruturados no Elasticsearch/Kibana | Um comando sobe tudo; cada log de pedido leva `order_id` e `external_id` |

Detalhes em [backend/README.md › Decisões técnicas](backend/README.md#decisões-técnicas) e [› GraphQL](backend/README.md#graphql).

### Trade-offs: o que foi simplificado de propósito pelo limite de tempo

- **Fila no Postgres, e não num broker.** Resolve bem o volume do desafio, mas o worker consulta a fila a cada 1 s (não é por push) e ela não tem DLQ.
- **Worker processa o lote um pedido por vez.** A escala é horizontal (mais workers). Num mesmo worker, um pedido que dá timeout atrasa os outros do lote.
- **Política de retentativa única para todos:** 3 tentativas, espera fixa e sem variação aleatória (*jitter*), e sem *circuit breaker*.
- **Webhook autenticado por chave compartilhada**, sem assinatura HMAC nem proteção contra reenvio malicioso (*replay*) por timestamp.
- **Mock do sistema interno com estado em memória:** as chaves de idempotência dele se perdem quando o container reinicia.
- **Testes automatizados em SQLite.** O `SKIP LOCKED` e o `LISTEN/NOTIFY`, que dependem do Postgres, foram verificados manualmente na stack real, e não por teste automático.
- **Usuários criados pelo terminal** (`python -m app.cli create-user`), sem tela de cadastro, e perfis simples (ADMIN/USER).
- **Padrões de desenvolvimento no compose:** chave do webhook fixa, simulador ligado e Elasticsearch/Kibana sem autenticação.

### Pendências: o que ficou de fora e como seria feito

| Pendência | Como eu implementaria |
|-----------|-----------------------|
| Reprocessamento em lote e automático | Hoje o reprocessamento é manual, um pedido por vez. Evolução: reprocessar vários de uma vez (ex.: todos os `FAILED` por indisponibilidade de hoje) e uma política automática, como uma DLQ com nova rodada agendada |
| Testes contra Postgres real e E2E | pytest com Postgres em container (testcontainers) para concorrência da fila e `LISTEN/NOTIFY`; Playwright para os fluxos da interface |
| CI | GitHub Actions rodando lint, testes, checagem do schema/codegen e build das imagens |
| Resiliência | *Circuit breaker* por integração, *jitter* na espera e envios concorrentes dentro do worker (cliente HTTP assíncrono) |
| Segurança do webhook | Assinatura HMAC do corpo com timestamp, janela de validade e rotação de chaves |
| Escala | Outbox + broker com DLQ quando o volume ou o número de consumidores crescer |
| Métricas e alertas | OpenTelemetry/Prometheus: tamanho da fila, idade do pedido mais antigo em `RECEIVED`, taxa de falha e tempo de processamento |
| Manutenção de dados | Rotina para apagar sessões expiradas e arquivar pedidos antigos |
| Mock com estado durável | Guardar as chaves de idempotência do mock em Redis |
| Produção | Segredos fora do compose, HTTPS com `SESSION_COOKIE_SECURE=true`, simulador desligado e Elasticsearch com autenticação |
