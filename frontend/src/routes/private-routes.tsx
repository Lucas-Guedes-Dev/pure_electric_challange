import type { ReactElement } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { SessionLoading } from '../components/session-loading'
import { useSession } from '../utils/session'

interface PrivateRouteProps {
  children: ReactElement
}

/**
 * Exige sessão válida. Sem ela, manda para /login guardando a página de origem.
 * Reage na hora ao sinal de logout do backend (sessão expirada, logout em outra aba...).
 */
export default function PrivateRoute({ children }: PrivateRouteProps) {
  const location = useLocation()
  const { status, isAuthenticated } = useSession()

  // Ainda perguntando ao backend se há sessão: não redireciona antes da resposta
  if (status === 'loading') return <SessionLoading />

  return isAuthenticated ? children : <Navigate to="/login" replace state={{ from: location }} />
}
