# Deploy: Railway (backend) + Vercel (frontend) + Elastic Cloud (logs)

Um repositório só. Cada plataforma usa uma pasta:

```
Vercel   frontend/   → build do Vite; /api/* é repassado para a API no Railway
Railway  backend/    → 3 serviços da mesma imagem (api, worker, internal-system) + Postgres
Elastic  —           → recebe os logs da api e do worker (Kibana no Elastic Cloud)
```

```
navegador ──► https://SEU-APP.vercel.app            (páginas)
          ──► https://SEU-APP.vercel.app/api/*      ──rewrite──► api no Railway   (REST, GraphQL, SSE: cookie no domínio do Vercel)
          ──► wss://pure-eletric-api.up.railway.app/api/graphql                    (WebSocket direto: autentica com ticket)

api ──► Postgres ◄── worker ──(rede privada)──► internal-system
api, worker ──► Elastic Cloud (logs)
```

**Por que o rewrite:** com o `/api` passando pelo próprio Vercel, o cookie de sessão fica no domínio do frontend (primeira parte). Sem ele, o cookie seria de outro site (`railway.app`) e o Safari e as janelas anônimas o bloqueariam.

**Por que o ticket:** o Vercel não repassa WebSocket, então as subscriptions vão direto ao Railway, onde o navegador não manda aquele cookie. O frontend pede um ticket de 60 s em `POST /api/auth/ws-ticket` (pelo rewrite, com o cookie) e o envia na abertura do WebSocket. Detalhes em [backend/app/modules/auth/ws_ticket.py](backend/app/modules/auth/ws_ticket.py).

Faça na ordem: **1. Elastic Cloud → 2. Railway → 3. Vercel → 4. voltar ao Railway (CORS)**.

Antes de tudo, o código precisa estar num repositório no GitHub (as duas plataformas fazem o deploy a partir dele).

---

## 1. Elastic Cloud (teste grátis de 14 dias)

1. Crie a conta em https://cloud.elastic.co/registration (não pede cartão).
2. Crie um **projeto Observability** (Serverless) ou um **deployment** (Hosted). Os dois servem.
3. Pegue a **URL do Elasticsearch**: na página do projeto/deployment, em *Connection details* / *Endpoints*, copie o endpoint do **Elasticsearch** (não o do Kibana). Algo como `https://xxxx.es.us-east-1.aws.elastic.cloud:443`.
4. Crie uma **chave de API**: no Kibana, *Stack Management › API keys › Create API key* (no Serverless: *Project settings › Management › API keys*).
   - Nome: `pure-eletric-logs`.
   - Recomendado: restrinja os privilégios (*Control security privileges*) ao data stream dos logs:

     ```json
     {
       "pure-eletric-logs": {
         "indices": [
           {
             "names": ["logs-pure_eletric.*"],
             "privileges": ["auto_configure", "create_index", "create_doc", "view_index_metadata"]
           }
         ]
       }
     }
     ```

   - Copie o valor **Encoded** (base64). Ele aparece uma vez só.
5. Guarde a URL e a chave: vão nas variáveis `ELASTICSEARCH_URL` e `ELASTICSEARCH_API_KEY` da api e do worker (passo 2).
6. Depois que a api subir, crie o data view no Kibana: *Discover › Create data view*
   - Index pattern: `logs-pure_eletric.api-*`
   - Timestamp: `@timestamp`

   Filtros úteis: `labels.order_id : 42`, `labels.external_id : "ORDER-123"`, `service.name : "pure-eletric-worker"`, `log.level : "ERROR"`.

**Quando o teste acabar (14 dias):** o cluster é desligado. Apague `ELASTICSEARCH_URL` da api e do worker: os logs continuam no console, visíveis na aba *Logs* de cada serviço do Railway. Enquanto a variável existir e o Elastic não responder, a aplicação segue normal: o envio de logs só avisa no console (no máximo 1 vez por minuto) e descarta o excedente.

---

## 2. Railway (backend)

Custo: o Railway não tem plano gratuito permanente. O crédito de teste (ou o plano Hobby) cobre estes 4 serviços pequenos com folga por algumas semanas.

### 2.1 Projeto e banco

1. https://railway.com › *New Project* › *Deploy from GitHub repo* › escolha o repositório. Isso cria o 1º serviço: renomeie para **`api`** (*Settings › Service name*).
2. No projeto: *Create › Database › PostgreSQL*. O serviço se chama `Postgres`.

### 2.2 Serviço `api`

*Settings*:

| Campo | Valor |
|---|---|
| Root Directory | `/backend` |
| Config file (Config-as-code › *Railway config file*) | `/backend/railway/api.json` |
| Networking › *Generate Domain* | nome **`pure-eletric-api`** → `pure-eletric-api.up.railway.app` |

> Se `pure-eletric-api` já estiver em uso, escolha outro nome e troque o domínio em **dois lugares** do frontend: [frontend/vercel.json](frontend/vercel.json) (`destination`) e a variável `VITE_GRAPHQL_WS_URL` no Vercel.

*Variables* (o botão *Raw Editor* aceita colar tudo de uma vez):

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
ENVIRONMENT=production
SECRET_KEY=<gere: python -c "import secrets; print(secrets.token_urlsafe(48))">
ORDERS_WEBHOOK_KEY=<outra chave aleatória: quem envia pedidos manda no header X-Webhook-Key>
SESSION_COOKIE_SECURE=true
# Atualize no passo 4 com a URL do Vercel
CORS_ORIGINS=https://SEU-APP.vercel.app
# O Railway fica na frente da API: aceita o X-Forwarded-For (IP real no limite de logins)
FORWARDED_ALLOW_IPS=*
# Para a avaliação: simulador na interface e Swagger ligados
ORDER_SIMULATOR_ENABLED=true
DOCS_ENABLED=true
ELASTICSEARCH_URL=<URL do passo 1>
ELASTICSEARCH_API_KEY=<chave Encoded do passo 1>
```

O que acontece no deploy: a imagem é o [backend/Dockerfile](backend/Dockerfile); o `entrypoint.sh` aplica as migrations e sobe o uvicorn na porta `$PORT` do Railway. O healthcheck é `/api/health`.

### 2.3 Serviço `internal-system` (mock do sistema interno)

*Create › GitHub Repo* › mesmo repositório › renomeie para **`internal-system`** (o nome importa: o worker o encontra por ele).

| Campo | Valor |
|---|---|
| Root Directory | `/backend` |
| Config file | `/backend/railway/internal-system.json` |
| Networking | **não** gere domínio público: só o worker fala com ele, pela rede privada |

```env
RUN_MIGRATIONS=false
PORT=9000
INTERNAL_SYSTEM_FAILURE_RATE=0.2
```

### 2.4 Serviço `worker`

*Create › GitHub Repo* › mesmo repositório › renomeie para **`worker`**.

| Campo | Valor |
|---|---|
| Root Directory | `/backend` |
| Config file | `/backend/railway/worker.json` |
| Networking | sem domínio (não recebe requisições) |

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
RUN_MIGRATIONS=false
ENVIRONMENT=production
SERVICE_NAME=pure-eletric-worker
INTERNAL_SYSTEM_URL=http://${{internal-system.RAILWAY_PRIVATE_DOMAIN}}:9000
ELASTICSEARCH_URL=<URL do passo 1>
ELASTICSEARCH_API_KEY=<chave Encoded do passo 1>
```

Para escalar, aumente as réplicas do worker (*Settings › Replicas*): a fila usa `FOR UPDATE SKIP LOCKED`, então não há processamento duplicado.

### 2.5 Criar o usuário administrador

Com a [CLI do Railway](https://docs.railway.com/guides/cli) instalada e logada (`railway login`, `railway link` na pasta do projeto):

```bash
railway ssh --service api
```

E, dentro do container:

```bash
python -m app.cli create-user --username admin --email voce@exemplo.com --admin
```

(A senha é pedida no terminal.)

### 2.6 Conferir

- `https://pure-eletric-api.up.railway.app/api/health` → `{"status":"ok","database":"up",...}`
- Swagger: `https://pure-eletric-api.up.railway.app/api/docs`
- *Logs* do `api`: `Ouvindo eventos de pedidos no canal order_events` (tempo real via `LISTEN/NOTIFY` ligado)

---

## 3. Vercel (frontend)

1. https://vercel.com › *Add New › Project* › importe o repositório.
2. **Root Directory: `frontend`**. O resto vem do [frontend/vercel.json](frontend/vercel.json) (Vite, `npm run build`, saída `dist`, rewrites).
3. *Environment Variables* (Production):

   ```env
   VITE_GRAPHQL_WS_URL=wss://pure-eletric-api.up.railway.app/api/graphql
   ```

   `VITE_API_URL` não precisa: o padrão `/api` já passa pelo rewrite.
4. *Deploy*. Anote a URL de produção (ex.: `https://pure-eletric.vercel.app`).

O `vercel.json` faz duas coisas:
- `/api/*` → `https://pure-eletric-api.up.railway.app/api/*` (mesma origem para o navegador: cookie e CORS sem complicação);
- qualquer outra rota → `index.html`, para recarregar `/pedidos/42` sem dar 404.

---

## 4. De volta ao Railway: liberar a origem do Vercel

No serviço `api`, troque `CORS_ORIGINS` pela URL real do Vercel (sem barra no final) e deixe o Railway fazer o redeploy:

```env
CORS_ORIGINS=https://pure-eletric.vercel.app
```

É o que autoriza o WebSocket vindo do frontend (WebSocket não passa pelo CORS; a API confere a origem na mão). Deployments de *preview* do Vercel têm outras URLs: para usá-los, acrescente-as na lista, separadas por vírgula.

---

## 5. Checklist final

1. Abra a URL do Vercel, faça login com o usuário do passo 2.5.
2. Em **Pedidos**, o indicador deve ficar **Ao vivo** (WebSocket com ticket funcionando).
3. Use o **simulador**: os pedidos mudam de status sozinhos (worker + internal-system + tempo real).
4. Recarregue a página em `/pedidos`: continua logado e não dá 404.
5. No Kibana (Elastic Cloud), *Discover* com o data view `logs-pure_eletric.api-*`: aparecem os logs da api e do worker.
6. Webhook de fora (como um sistema externo enviaria):

   ```bash
   curl -i -X POST https://pure-eletric.vercel.app/api/orders \
     -H "Content-Type: application/json" -H "X-Webhook-Key: SUA_ORDERS_WEBHOOK_KEY" \
     -d '{ "externalId": "ORDER-123", "customer": "Cliente Exemplo", "amount": 150.00 }'
   ```

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| Login funciona, mas "Pedidos" não fica **Ao vivo** | `CORS_ORIGINS` sem a URL exata do Vercel, ou `VITE_GRAPHQL_WS_URL` com o domínio errado (lembre de fazer redeploy no Vercel ao mudar variável `VITE_*`: elas entram no build) |
| Todas as chamadas `/api` dão 404 no Vercel | Domínio do Railway diferente do que está no `vercel.json` |
| Login não "pega" (volta para a tela de login) | `SESSION_COOKIE_SECURE=true` exige HTTPS; confira se está acessando pela URL `https://` do Vercel |
| Pedidos ficam em `RECEIVED` para sempre | Worker parado ou sem `DATABASE_URL`; veja os *Logs* do `worker` |
| Pedidos falham com "Falha de comunicação com o sistema interno" | `INTERNAL_SYSTEM_URL` errada, ou o serviço não se chama `internal-system` |
| Kibana vazio | `ELASTICSEARCH_URL` apontando para o Kibana em vez do Elasticsearch, ou chave sem os privilégios; os *Logs* do `api` mostram `[elasticsearch-log-handler] ...` com o motivo |
| O aviso de sessão expirando demora ou cai de vez em quando | O stream de eventos da sessão (SSE) passa pelo rewrite do Vercel, que pode encerrar conexões longas; o navegador reconecta sozinho em 5 s e a expiração continua sendo aplicada pelo backend |
