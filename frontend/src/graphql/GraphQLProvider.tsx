import { useEffect, useMemo, type ReactNode } from 'react'
import { Provider } from 'urql'
import { useSession } from '../utils/session'
import { createGraphQLClient, type AppGraphQLClient } from './client'

// Descarte adiado: o StrictMode desmonta e remonta na hora; se o mesmo cliente voltar,
// o descarte é cancelado. Só uma troca de verdade (outra sessão) fecha o WebSocket.
const pendingDispose = new WeakMap<AppGraphQLClient, ReturnType<typeof setTimeout>>()

/**
 * Um cliente GraphQL por sessão: ao entrar outro usuário (ou sair), o cliente antigo é
 * descartado junto com o cache e o WebSocket, e nada do usuário anterior fica em memória.
 */
export function GraphQLProvider({ children }: { children: ReactNode }) {
  const { status, user } = useSession()
  const sessionKey = status === 'authenticated' ? `user-${user?.id}` : 'anonymous'

  const graphql = useMemo(() => {
    void sessionKey // novo cliente a cada sessão
    return createGraphQLClient()
  }, [sessionKey])

  useEffect(() => {
    clearTimeout(pendingDispose.get(graphql))
    return () => {
      pendingDispose.set(graphql, setTimeout(graphql.dispose, 0))
    }
  }, [graphql])

  return <Provider value={graphql.client}>{children}</Provider>
}
