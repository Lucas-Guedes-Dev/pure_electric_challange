import { useEffect, type ReactNode } from 'react'
import { setUnauthorizedHandler } from '../../api/httpClient'
import type { LogoutEventDTO, SessionEventDTO } from '../../dtos/auth.dto'
import { authService } from '../../services/authService'
import {
  clearSession,
  getSession,
  isAuthEnabled,
  loadSession,
  updateSession,
  useSession,
} from '../../utils/session'
import SessionExpiringDialog from '../session-expiring-dialog'

function parse<T>(event: Event): T {
  return JSON.parse((event as MessageEvent<string>).data) as T
}

/**
 * Mantém o estado da sessão sincronizado com o backend:
 * 1. ao abrir o app, consulta /api/auth/me;
 * 2. logado, escuta o stream /api/auth/events (session / expiring / logout);
 * 3. qualquer 401 de sessão em qualquer chamada da API desloga o usuário.
 *
 * Ao deslogar, o PrivateRoute redireciona para /login sozinho.
 */
export default function SessionProvider({ children }: { children: ReactNode }) {
  const { status } = useSession()

  useEffect(() => {
    if (isAuthEnabled()) void loadSession()
  }, [])

  useEffect(() => {
    setUnauthorizedHandler((error) => {
      if (getSession().status === 'authenticated') clearSession(error.message)
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  useEffect(() => {
    if (status !== 'authenticated') return

    const events = authService.events()

    events.addEventListener('session', (event) => {
      updateSession({ expiresAt: parse<SessionEventDTO>(event).expires_at, expiring: false })
    })
    events.addEventListener('expiring', (event) => {
      updateSession({ expiresAt: parse<SessionEventDTO>(event).expires_at, expiring: true })
    })
    events.addEventListener('logout', (event) => {
      events.close()
      clearSession(parse<LogoutEventDTO>(event).detail)
    })
    events.onerror = () => {
      // Queda de rede: o EventSource reconecta sozinho. Se ele desistiu (ex.: 204
      // porque o cookie sumiu), confirma com o backend se a sessão ainda existe.
      if (events.readyState === EventSource.CLOSED) void loadSession()
    }

    return () => events.close()
  }, [status])

  return (
    <>
      {children}
      <SessionExpiringDialog />
    </>
  )
}
