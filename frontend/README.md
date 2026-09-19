# Frontend · Desafio Técnico Pure Eletric

SPA em **React 19 + Vite + TypeScript**, que consome a API do backend com **DTOs tipados** espelhados dos DTOs Pydantic.

| Tecnologia  | Uso                                   |
|-------------|---------------------------------------|
| React 19    | UI                                    |
| Vite 8      | dev server, proxy da API e build      |
| TypeScript  | tipagem (modo estrito do template Vite) |
| styled-components 6 | estilos + tema (design system em `src/components/ui`) |
| Work Sans (@fontsource) | fonte do tema, empacotada no build (funciona offline) |
| urql + graphcache | cliente GraphQL com cache normalizado (pedidos atualizam sozinhos) |
| graphql-ws  | subscriptions GraphQL por WebSocket (tempo real) |
| GraphQL Code Generator | tipos TypeScript gerados do `backend/schema.graphql` |
| Vitest + Testing Library | testes (`npm test`) |
| oxlint      | lint                                  |
| nginx       | serve o build em produção (Dockerfile, estágio `prod`) |

> Requer **Node ≥ 20.19 ou ≥ 22.12**, exigência do Vite 8.

## Estrutura de pastas

```
frontend/
├── src/
│   ├── main.tsx              # ponto de entrada: AppThemeProvider + BrowserRouter + SessionProvider + GraphQLProvider + rotas
│   ├── routes/               # react-router-dom
│   │   ├── index.tsx         # todas as rotas da aplicação (inclui /login)
│   │   ├── private-routes.tsx  # PrivateRoute: exige sessão; sem ela vai para /login
│   │   └── admin-route.tsx   # AdminRoute: exige perfil admin
│   ├── graphql/              # GraphQL (pedidos)
│   │   ├── client.ts         # urql + graphcache + graphql-ws; erros de sessão deslogam
│   │   ├── GraphQLProvider.tsx  # um cliente por sessão (descartado no logout)
│   │   ├── liveStatus.ts     # estado do WebSocket (indicador "Ao vivo")
│   │   ├── orders.ts         # queries, mutations e subscriptions de pedidos
│   │   └── generated/        # tipos gerados pelo codegen (não editar; versionado)
│   ├── utils/
│   │   ├── session.ts        # estado da sessão (vindo do backend) + useSession() + loadSession/logout
│   │   ├── format.ts         # moeda, datas, "há 2 minutos", duração, contagem
│   │   ├── orderStatus.ts    # rótulo/cor de cada status e resultado de tentativa
│   │   └── orders.ts         # regra de filtro (pedido novo entra no aviso?)
│   ├── vite-env.d.ts         # tipagem das variáveis VITE_*
│   ├── styles/               # tema do styled-components
│   │   ├── theme.ts          # tokens: cores, fontes, espaçamentos, raios, breakpoints + media
│   │   ├── styled.d.ts       # tipa o `theme` (DefaultTheme) em todos os styled components
│   │   ├── GlobalStyle.ts    # reset + estilos base (body, títulos, foco, seleção) + fonte
│   │   └── AppThemeProvider.tsx  # ThemeProvider + GlobalStyle
│   ├── api/
│   │   └── httpClient.ts     # wrapper do fetch tipado + ApiError
│   ├── dtos/                 # contratos da API (espelham backend/app/**/dtos.py)
│   │   ├── common.dto.ts     # PageDTO<T>, PaginationParamsDTO, ErrorResponseDTO, DecimalString
│   │   ├── auth.dto.ts       # login, usuário, sessão e eventos SSE
│   │   └── health.dto.ts     # HealthResponseDTO
│   ├── services/             # uma função por endpoint, agrupadas por recurso
│   │   ├── authService.ts    # login, logout, me, refresh, events (EventSource)
│   │   └── healthService.ts
│   ├── hooks/                # estado + chamadas à API para as telas
│   │   ├── useOrders.ts      # lista ao vivo, totais, detalhe, simulador, reprocessamento
│   │   ├── useOrderFilters.ts  # filtros da lista guardados na URL
│   │   ├── useCountdown.ts   # "próxima tentativa em 0:08"
│   │   └── useNow.ts         # relógio para textos relativos
│   ├── components/
│   │   ├── ui/               # design system: Button, TextField, Card, Badge, Table, Heading...
│   │   ├── layout/           # sidebar + navbar + <Outlet /> (página da rota)
│   │   ├── sidebar/          # menu lateral; itens em sidebar/menu.ts
│   │   ├── navbar/           # barra superior (menu no mobile, status da API, usuário e Sair)
│   │   ├── session-provider/ # sincroniza a sessão com o backend (me + stream SSE + 401)
│   │   ├── session-expiring-dialog/ # aviso "sua sessão vai expirar" + continuar conectado
│   │   ├── session-loading/  # "Verificando sessão…" enquanto o /me responde
│   │   ├── orders/           # StatusBadge, StatsCards, OrdersTable, StatusTimeline,
│   │   │                     # AttemptsTable, ReprocessPanel, SimulatorPanel, LiveIndicator
│   │   └── HealthBadge.tsx   # componentes de domínio (usam os de ui/)
│   └── pages/                # telas (compõem hooks + components)
│       ├── LoginPage.tsx     # /login
│       ├── HomePage.tsx      # /inicio: boas-vindas + resumo dos pedidos
│       ├── OrdersPage.tsx    # /pedidos: totais, filtros, lista ao vivo, simulador
│       ├── OrderDetailPage.tsx  # /pedidos/:id: linha do tempo + histórico de tentativas
│       └── NotFoundPage.tsx  # 404
├── public/                   # arquivos estáticos (favicon)
├── index.html
├── codegen.ts                # GraphQL Code Generator (lê ../backend/schema.graphql)
├── vite.config.ts            # proxy /api (HTTP + WebSocket) → backend; config do Vitest
├── nginx.conf                # config do nginx para produção (SPA + proxy /api)
├── Dockerfile                # estágios: dev (Vite) → build → prod (nginx)
└── .env.example
```

## As camadas

A dependência entre as camadas vai em um só sentido:

```
pages ──► hooks ──► services ──► api/httpClient ──► backend (/api)
  │                    │
  └──► components      └── tipados por ──► dtos
```

| Camada        | Responsabilidade |
|---------------|------------------|
| `dtos/`       | Interfaces TypeScript com o **mesmo formato** dos DTOs do backend. É o único lugar onde se define o formato dos dados da API. |
| `api/`        | O `httpClient` monta a URL, faz o `fetch`, trata o 204 e lança `ApiError` com a mensagem do backend (`detail`) em caso de erro. |
| `services/`   | Uma função por endpoint, com os tipos de entrada e saída explícitos. Os componentes não chamam o `fetch` diretamente. |
| `hooks/`      | Estado de tela: loading, erro, paginação e recarregar depois de criar, editar ou excluir. |
| `components/` | Componentes visuais que recebem dados e callbacks por props. Não conhecem a API. Os de `ui/` são genéricos (design system); os demais são de domínio. |
| `pages/`      | Montam a tela juntando hooks e components. |

### Exemplo de chamada tipada

```ts
// services/compraService.ts
import { httpClient } from '../api/httpClient'
import type { PageDTO, PaginationParamsDTO } from '../dtos/common.dto'
import type { CompraCreateDTO, CompraResponseDTO } from '../dtos/compra.dto'

export const compraService = {
  list: (params: PaginationParamsDTO = {}) =>
    httpClient.get<PageDTO<CompraResponseDTO>>('/compras', { ...params }),

  get: (id: number) => httpClient.get<CompraResponseDTO>(`/compras/${id}`),

  create: (payload: CompraCreateDTO) =>
    httpClient.post<CompraResponseDTO, CompraCreateDTO>('/compras', payload),
}
```

Quando um DTO mudar no backend, atualize o arquivo correspondente em `src/dtos/`. O TypeScript passa a apontar todos os lugares afetados.

> Os campos `Decimal` do backend chegam como **string** (tipo `DecimalString`). Converta com `Number()` só na hora de exibir.

## Tema e design system (styled-components)

O tema padrão (`src/styles/theme.ts`) segue a identidade visual de [pureelectric.com.br](https://pureelectric.com.br):

| Token                    | Valor            | Uso |
|--------------------------|------------------|-----|
| `colors.heading`         | `#121212`        | títulos e botão primário (preto) |
| `colors.text`            | `#363636`        | texto corrido |
| `colors.muted`           | `#595959`        | legendas e textos secundários |
| `colors.accent`          | `#ff8000`        | destaque laranja (hover `#ffa64d`) |
| `colors.surface`         | `#f3f3f3`        | fundos de seção e cards |
| `colors.border`          | `#cacaca`        | bordas e divisórias |
| `colors.inverse.*`       | `#121212` / `#1e1e1e` | áreas escuras (cabeçalho, banners) |
| `fonts.body/heading`     | Work Sans        | títulos em peso 900 e caixa alta |
| `radii.pill`             | `100px`          | botões em formato pílula |

### Regras

1. **Nada de cor, fonte ou espaçamento fixo no código.** Use sempre o tema:
   ```ts
   const Box = styled.div`
     padding: ${({ theme }) => theme.space.md};
     color: ${({ theme }) => theme.colors.text};
     ${media.md} { padding: ${({ theme }) => theme.space.lg}; }
   `
   ```
2. **Use os componentes de `components/ui` antes de criar estilos novos.** Importe pelo índice:
   ```tsx
   import { Button, Card, Heading, Highlight, TextField } from '../components/ui'

   <Heading level={1}>Seu dia muda <Highlight>de lugar.</Highlight></Heading>
   <Button variant="accent">Adicionar</Button>
   ```
3. **Props só de estilo levam `$`** (transient props, ex.: `$variant`, `$gap`), para não irem parar no DOM. Componentes com wrapper React (`Button`, `Heading`, `TextField`) recebem props normais (`variant`, `level`, `label`).
4. **Um token novo entra primeiro em `theme.ts`.** O `styled.d.ts` faz o TypeScript reconhecer o token automaticamente.

### Componentes disponíveis

| Componente       | Variações |
|------------------|-----------|
| `Button`         | `variant`: `primary`, `secondary`, `accent`, `ghost`, `danger` · `size`: `sm`, `md`, `lg` · `fullWidth` |
| `TextField` / `Input` | `label`, `hint`, `error` (ligados por `aria-describedby`) |
| `Heading`        | `level`: 1–4 (caixa alta, peso 900) |
| `Highlight`, `Eyebrow`, `Text` | destaque laranja, rótulo pequeno, texto (`$tone`, `$size`, `$weight`) |
| `Card`           | `$tone`: `default`, `surface`, `inverse` · `$padding` |
| `Alert`          | `tone`: `info`, `success`, `warning`, `danger` · `action` (botão à direita) |
| `Pagination`     | `page`, `size`, `total`, `onChange` |
| `SelectField` / `Select` | `label` + `<option>`s |
| `Badge`          | `$variant`: `neutral`, `accent`, `success`, `danger`, `info` |
| `Table`, `Th`, `Td`, `Tr`, `TableWrapper` | `$align` nas células |
| `Container`, `Stack` | layout: largura máxima / flex com `$direction`, `$gap`, `$align`, `$justify`, `$wrap` |

## Criando uma tela para um módulo novo (ex.: `compras`)

1. `src/dtos/compra.dto.ts`: espelhe os DTOs de `backend/app/modules/compras/dtos.py`.
2. `src/services/compraService.ts`: uma função por endpoint, usando o `httpClient`.
3. `src/hooks/useCompras.ts`: estado da tela (se precisar).
4. `src/components/…` e `src/pages/ComprasPage.tsx`, montados com os componentes de `components/ui`.
5. Registre a rota em `src/routes/index.tsx` (dentro do `<Route element={<Layout />}>`, envolvida em `<PrivateRoute>`) e o link em `src/components/sidebar/menu.ts`.

## Rotas e menu

- `/` redireciona para `/inicio`. Rotas desconhecidas caem no `NotFoundPage`.
- Menu atual: **Início** e **Pedidos**. O mecanismo de administração (`AdminRoute` e `adminOnly` no menu) continua disponível para telas futuras, como um cadastro de usuários.
- As páginas internas ficam dentro do `Layout` (sidebar + navbar) e cada uma é envolvida em `<PrivateRoute>`; as de administração também em `<AdminRoute>`.
- A sidebar é montada a partir de `MENU` em `components/sidebar/menu.ts`. Seções com `title` são retráteis, itens com `children` viram subseções retráteis (podem ser aninhadas), e `adminOnly` esconde a seção de quem não é admin.
- A seção/subseção que contém a página atual abre sozinha. No mobile a sidebar vira uma gaveta aberta pelo botão da navbar (fecha ao navegar, no Esc ou clicando fora).
- Com `VITE_AUTH_ENABLED=false`, `PrivateRoute` e `AdminRoute` liberam tudo, sem login (só para desenvolver telas). Esconder rotas no frontend é conveniência: quem autoriza de verdade é o backend.

## Login e sessão

A sessão é **controlada pelo backend** (veja [backend/README.md › Autenticação e sessão](../backend/README.md#autenticação-e-sessão)). O token fica num cookie **HttpOnly**, que o JavaScript não lê, e o `fetch` o envia sozinho. O frontend **não guarda token nem role no `localStorage`**: tudo fica em memória e vem do backend.

### Fluxo

1. **Ao abrir o app**, o `SessionProvider` chama `GET /api/auth/me`. Enquanto isso, o `PrivateRoute` mostra "Verificando sessão…". Com sessão, o usuário entra direto; sem sessão, vai para `/login`, e a página de origem fica guardada.
2. **No login** (`POST /api/auth/login`), o backend grava o cookie. O `startSession()` preenche o estado e a `LoginPage` leva de volta à página de origem. O login aceita usuário ou e-mail.
3. **Logado**, o `SessionProvider` abre o stream `GET /api/auth/events`, pelo qual o backend avisa:
   - `session`: o prazo foi renovado (qualquer chamada à API renova os 30 min de inatividade);
   - `expiring`: faltam 2 minutos. Abre o aviso **"Sua sessão vai expirar"**, com contagem e **Continuar conectado** (`POST /api/auth/refresh`);
   - `logout`: a sessão acabou (inatividade, tempo máximo, **Sair em outra aba**, usuário desativado). O estado é limpo, o `PrivateRoute` manda para `/login`, e a tela de login mostra o motivo.
4. **Qualquer chamada da API** que receba `401` com `SESSION_EXPIRED` ou `NOT_AUTHENTICATED` também desloga, pelo `setUnauthorizedHandler` do `httpClient`.
5. **Sair** (navbar) chama `POST /api/auth/logout` e volta para o login.

### Usando a sessão em componentes

```tsx
import { useSession } from '../utils/session'

const { user, isAuthenticated, isAdmin, status } = useSession()
// user: { id, username, email, full_name, role, is_active } | null
// status: 'loading' | 'authenticated' | 'anonymous'
```

O `useSession()` re-renderiza o componente quando a sessão muda, inclusive quando o backend manda o `logout`. Fora de componentes, use `getSession()`, `isAuthenticated()` e `isAdmin()`.

## Pedidos (GraphQL + tempo real)

As telas de pedidos usam o **GraphQL** do backend (`/api/graphql`). O login continua no REST.

| Tela | O que tem |
|------|-----------|
| `/inicio` | boas-vindas com o nome do usuário e o resumo dos pedidos por status (ao vivo; clicar leva à lista filtrada) |
| `/pedidos` | totais por status (clicáveis), busca por externalId ou cliente, filtro por status, lista paginada ao vivo e o **simulador** |
| `/pedidos/:id` | dados do pedido, linha do tempo `Recebido → Processando → Processado/Falhou`, contagem até a próxima tentativa, último erro, protocolo interno, histórico de tentativas e o **teste de idempotência** |

### Tempo real

- **Subscription `orderUpdated` por WebSocket.** O indicador **Ao vivo** mostra o estado da conexão. Se ela cair, reconecta sozinha, esperando cada vez mais entre as tentativas.
- **Cache normalizado (graphcache).** Cada pedido fica guardado pelo `id`, então a linha na lista e a tela de detalhe mudam sozinhas quando o evento chega. A linha também pisca rapidamente para chamar atenção.
- **Pedidos novos não bagunçam a tabela.** Um pedido novo que entraria na lista atual aparece no aviso "N pedidos novos · Mostrar", e a pessoa decide quando recarregar.
- **Totais:** atualizam no máximo 1 vez por segundo, mesmo com rajadas de eventos.
- **Filtros na URL** (`/pedidos?status=FAILED&busca=ana&pagina=2`): o link pode ser compartilhado e o voltar do navegador funciona.

### Simulador

O botão **Simular pedidos** faz o papel do sistema externo. Ele envia pedidos pelo mesmo fluxo do webhook, usando a mutation `simulateOrders`, e dá para escolher como o sistema interno simulado vai responder: sucesso, instável, recusado, sem resposta, fora do ar (termina `FAILED` e dá certo ao reprocessar) ou aleatório.
- **Onde fica a lógica:** o simulador roda **no backend**. A chave do webhook nunca vai para o navegador; a tela só precisa estar logada.
- **Quando aparece:** só com `ORDER_SIMULATOR_ENABLED=true` no backend. No compose de desenvolvimento ela já vem ligada.
- **Reenviar pedido** (na tela de detalhe): reenvia o mesmo pedido e mostra que nada novo foi criado nem processado de novo.

### Reprocessamento

No detalhe de um pedido `FAILED`, administradores veem o botão **Reprocessar pedido** (mutation `reprocessOrder`). Ele pede confirmação, aceita um motivo opcional e devolve o pedido à fila; o andamento aparece ao vivo pela subscription. O histórico de tentativas passa a mostrar as rodadas separadas, com quem reprocessou, quando e o motivo. O botão é só conveniência: o backend confere se o usuário é administrador e se o pedido está em `FAILED`.

### Tipos garantidos pelo schema

As operações ficam em `src/graphql/orders.ts`, e os tipos delas são **gerados** do contrato do backend:

```bash
npm run codegen   # depois de mudar uma operação ou o backend/schema.graphql
```

Se o backend mudar um campo, o `npm run build` quebra em todos os lugares afetados. Os arquivos gerados ficam versionados porque o container do frontend não enxerga `../backend`.

### Sessão

- **Um cliente GraphQL por sessão:** ao sair ou trocar de usuário, cache e WebSocket são descartados.
- **Erro de sessão:** um erro GraphQL `SESSION_EXPIRED` ou `NOT_AUTHENTICATED`, ou o WebSocket recusado com 4403, desloga como qualquer 401 do REST.
- **Só POST:** o cliente usa POST também nas queries, porque o backend recusa GraphQL por GET.

## Comunicação com a API

O frontend sempre chama caminhos relativos `/api/...`:

- **Em desenvolvimento**, o Vite faz proxy de `/api` para `VITE_PROXY_TARGET`. Por isso não há problema de CORS.
- **Em produção** (imagem `prod`), o nginx faz o mesmo proxy para `http://backend:8000`.
- **No Vercel**, o [`vercel.json`](vercel.json) repassa `/api/*` para a API no Railway (rewrite) e manda as demais rotas para o `index.html`. O WebSocket vai direto ao Railway (`VITE_GRAPHQL_WS_URL`), autenticado por um ticket de curta duração (`POST /api/auth/ws-ticket`), porque o Vercel não repassa WebSocket. Passo a passo em [DEPLOY.md](../DEPLOY.md).

| Variável            | Padrão                   | Descrição |
|---------------------|--------------------------|-----------|
| `VITE_API_URL`      | `/api`                   | URL base usada pelo `httpClient` |
| `VITE_GRAPHQL_WS_URL` | derivada de `VITE_API_URL` | WebSocket das subscriptions. No Vercel: `wss://<api no railway>/api/graphql` |
| `VITE_PROXY_TARGET` | `http://localhost:8000`  | para onde o Vite encaminha `/api` (no Docker: `http://backend:8000`) |
| `VITE_USE_POLLING`  | —                        | `true` para ativar o polling de arquivos (hot reload no Docker/Windows) |
| `VITE_AUTH_ENABLED` | `true`                   | `false` libera as rotas sem login (só para desenvolver telas sem backend) |

## Rodando

Com Docker, a partir da raiz do projeto:

```bash
docker compose up --build frontend
```

> O `node_modules` do container fica num volume próprio. Sempre que adicionar uma dependência no `package.json`, recrie o volume com `docker compose up -d --build -V frontend`, ou instale direto no container com `docker compose exec frontend npm install`.

Sem Docker (com o backend rodando em `localhost:8000`):

```bash
npm install
npm run dev
```

Acesse **http://localhost:5173**.

## Scripts

| Comando           | O que faz                                  |
|-------------------|--------------------------------------------|
| `npm run dev`     | servidor de desenvolvimento com hot reload |
| `npm run build`   | checagem de tipos (`tsc -b`) + build em `dist/` |
| `npm run preview` | serve o build localmente                   |
| `npm run lint`    | lint com oxlint                            |
| `npm test`        | testes (Vitest): formatação, status, filtros, contagem, componentes |
| `npm run codegen` | gera os tipos GraphQL a partir de `../backend/schema.graphql` |
