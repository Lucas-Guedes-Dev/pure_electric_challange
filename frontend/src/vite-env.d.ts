/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL base da API. Padrão: "/api" (proxy do Vite) */
  readonly VITE_API_URL?: string
  /** URL do WebSocket do GraphQL. Padrão: derivada de VITE_API_URL (mesma origem) */
  readonly VITE_GRAPHQL_WS_URL?: string
  /** "false" libera as rotas privadas sem login. Padrão: login exigido */
  readonly VITE_AUTH_ENABLED?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
