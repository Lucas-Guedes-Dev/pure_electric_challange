import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Navbar from '../navbar'
import Sidebar from '../sidebar'
import { Container, Content, LayoutContainer } from './style'

function Layout() {
  const { pathname } = useLocation()
  // Controla a gaveta da sidebar no mobile; no desktop ela fica sempre visível
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [lastPathname, setLastPathname] = useState(pathname)

  // Fecha a gaveta ao navegar
  if (pathname !== lastPathname) {
    setLastPathname(pathname)
    setSidebarOpen(false)
  }

  useEffect(() => {
    if (!sidebarOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSidebarOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [sidebarOpen])

  return (
    <LayoutContainer>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <Container>
        <Navbar sidebarOpen={sidebarOpen} onToggleSidebar={() => setSidebarOpen((open) => !open)} />
        <Content>
          <Outlet />
        </Content>
      </Container>
    </LayoutContainer>
  )
}

export default Layout
