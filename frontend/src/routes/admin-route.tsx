import type { ReactElement } from 'react'
import { Navigate } from 'react-router-dom'
import { useSession } from '../utils/session'

interface AdminRouteProps {
  children: ReactElement
}

/**
 * Esconde a área de administração de quem não é admin.
 *
 * É só conveniência de navegação: o `role` vem do /api/auth/me e fica em
 * memória. Quem barra de verdade é o backend (CurrentAdmin nas rotas).
 */
export default function AdminRoute({ children }: AdminRouteProps) {
  const { isAdmin } = useSession()
  return isAdmin ? children : <Navigate to="/inicio" replace />
}
