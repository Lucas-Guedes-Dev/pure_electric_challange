/**
 * Cliente GraphQL (urql) de /api/graphql.
 *
 * - graphcache guarda cada pedido pelo `id`: quando a subscription entrega um pedido
 *   atualizado, a linha da lista e a tela de detalhe mudam sozinhas.
 * - As subscriptions vão por WebSocket (graphql-ws), que reconecta sozinho com espera
 *   crescente. Recusa 4403 = sem sessão: não reconecta e confere a sessão com o backend.
 * - Erro SESSION_EXPIRED / NOT_AUTHENTICATED em qualquer operação desloga (igual ao REST).
 */
import { cacheExchange } from '@urql/exchange-graphcache'
import { createClient as createWsClient, type Client as WsClient } from 'graphql-ws'
import { Client, fetchExchange, mapExchange, subscriptionExchange } from 'urql'
import { apiUrl } from '../api/httpClient'
import { clearSession, getSession, loadSession } from '../utils/session'
import { setLiveStatus } from './liveStatus'

const SESSION_ERROR_CODES = new Set(['SESSION_EXPIRED', 'NOT_AUTHENTICATED'])
const WS_UNAUTHORIZED = 4403

/** URL do WebSocket a partir da URL da API (relativa, como "/api", ou absoluta). */
export function graphqlWsUrl(httpUrl: string = apiUrl('/graphql'), location: Location = window.location): string {
  const absolute = new URL(httpUrl, location.href)
  absolute.protocol = absolute.protocol === 'https:' ? 'wss:' : 'ws:'
  return absolute.toString()
}

function createWs(): WsClient {
  let connectedOnce = false
  return createWsClient({
    url: graphqlWsUrl(),
    lazy: true, // só conecta quando alguma tela assina um evento
    retryAttempts: Infinity,
    shouldRetry: (event) => !(event instanceof CloseEvent && event.code === WS_UNAUTHORIZED),
    retryWait: async (retries) => {
      await new Promise((resolve) => setTimeout(resolve, Math.min(1000 * 2 ** retries, 15_000)))
    },
    on: {
      connecting: () => setLiveStatus(connectedOnce ? 'reconnecting' : 'connecting'),
      connected: () => {
        connectedOnce = true
        setLiveStatus('connected')
      },
      closed: (event) => {
        setLiveStatus(connectedOnce ? 'reconnecting' : 'idle')
        // Backend recusou por sessão: confirma com /me (se acabou, o app vai para o login)
        if (event instanceof CloseEvent && event.code === WS_UNAUTHORIZED) void loadSession()
      },
    },
  })
}

export interface AppGraphQLClient {
  client: Client
  dispose: () => void
}

export function createGraphQLClient(): AppGraphQLClient {
  const ws = createWs()

  const client = new Client({
    url: apiUrl('/graphql'),
    fetchOptions: { credentials: 'include' },
    // O backend só aceita POST no GraphQL (queries por GET poderiam ser disparadas por links
    // de outros sites com o cookie do usuário). O urql usaria GET por padrão para queries.
    preferGetMethod: false,
    requestPolicy: 'cache-and-network',
    exchanges: [
      mapExchange({
        onError(error) {
          const sessionError = error.graphQLErrors.find((e) =>
            SESSION_ERROR_CODES.has(String(e.extensions?.code)),
          )
          if (sessionError && getSession().status === 'authenticated') clearSession(sessionError.message)
        },
      }),
      cacheExchange({
        // Tipos sem id próprio ficam embutidos em quem os contém
        keys: {
          OrderPage: () => null,
          OrderStats: () => null,
          OrderAttempt: () => null,
          ReceiveOrderPayload: () => null,
        },
      }),
      fetchExchange,
      subscriptionExchange({
        forwardSubscription(request) {
          const input = { ...request, query: request.query ?? '' }
          return {
            subscribe(sink) {
              const unsubscribe = ws.subscribe(input, sink)
              return { unsubscribe }
            },
          }
        },
      }),
    ],
  })

  return {
    client,
    dispose: () => {
      void ws.dispose()
      setLiveStatus('idle')
    },
  }
}
