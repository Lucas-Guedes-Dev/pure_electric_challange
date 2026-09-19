import { useState } from 'react'
import { logout, useSession } from '../../utils/session'
import { HealthBadge } from '../HealthBadge'
import { Button } from '../ui'
import { Actions, Bar, MenuButton, UserInfo, UserName, UserRole } from './style'

interface NavbarProps {
  sidebarOpen: boolean
  onToggleSidebar: () => void
}

function Navbar({ sidebarOpen, onToggleSidebar }: NavbarProps) {
  const { user } = useSession()
  const [leaving, setLeaving] = useState(false)

  async function handleLogout() {
    setLeaving(true)
    // Ao limpar a sessão, o PrivateRoute leva para /login
    await logout().catch(() => setLeaving(false))
  }

  return (
    <Bar>
      <MenuButton
        type="button"
        aria-label={sidebarOpen ? 'Fechar menu' : 'Abrir menu'}
        aria-expanded={sidebarOpen}
        aria-controls="sidebar"
        onClick={onToggleSidebar}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </MenuButton>
      <Actions>
        <HealthBadge />
        {user && (
          <>
            <UserInfo>
              <UserName>{user.full_name ?? user.username}</UserName>
              <UserRole>{user.role === 'ADMIN' ? 'Administrador' : 'Usuário'}</UserRole>
            </UserInfo>
            <Button size="sm" variant="secondary" onClick={() => void handleLogout()} disabled={leaving}>
              {leaving ? 'Saindo…' : 'Sair'}
            </Button>
          </>
        )}
      </Actions>
    </Bar>
  )
}

export default Navbar
