import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../../api/httpClient'
import { authService } from '../../services/authService'
import { logout, updateSession, useSession } from '../../utils/session'
import { Button, Heading, Stack, Text } from '../ui'
import { Actions, Countdown, Dialog } from './style'

function formatRemaining(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000))
  const minutes = Math.floor(total / 60)
  const seconds = String(total % 60).padStart(2, '0')
  return `${minutes}:${seconds}`
}

/** Conteúdo do aviso. Só é montado com o aviso aberto, então a contagem começa certa. */
function ExpiringContent({ expiresAt }: { expiresAt: string }) {
  const [now, setNow] = useState(() => Date.now())
  const [renewing, setRenewing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  async function handleContinue() {
    setRenewing(true)
    setError(null)
    try {
      const { session } = await authService.refresh()
      updateSession({ expiresAt: session.expires_at, expiring: false })
    } catch (err) {
      // 401 de sessão já desloga pelo SessionProvider; aqui só sobra falha de rede
      if (!(err instanceof ApiError && err.status === 401)) {
        setError('Não foi possível renovar a sessão. Verifique sua conexão.')
      }
    } finally {
      setRenewing(false)
    }
  }

  return (
    <>
      <Stack $gap="sm">
        <Heading level={4} id="session-expiring-title">
          Sua sessão vai expirar
        </Heading>
        <Text id="session-expiring-text">
          Por segurança, você será desconectado em{' '}
          <Countdown>{formatRemaining(new Date(expiresAt).getTime() - now)}</Countdown> por inatividade.
        </Text>
        {error && (
          <Text $tone="danger" $size="sm" role="alert">
            {error}
          </Text>
        )}
      </Stack>
      <Actions>
        <Button variant="ghost" onClick={() => void logout()}>
          Sair
        </Button>
        <Button variant="accent" onClick={() => void handleContinue()} disabled={renewing} autoFocus>
          {renewing ? 'Renovando…' : 'Continuar conectado'}
        </Button>
      </Actions>
    </>
  )
}

/**
 * Aviso exibido quando o backend manda o evento `expiring`. "Continuar conectado"
 * renova a sessão (POST /api/auth/refresh); se ninguém fizer nada, o backend
 * manda o `logout` no prazo e o app volta para o login.
 */
export default function SessionExpiringDialog() {
  const { expiring, expiresAt } = useSession()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const open = expiring && expiresAt !== null

  // <dialog> nativo: showModal() prende o foco e deixa o resto da página inerte
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <Dialog
      ref={dialogRef}
      aria-labelledby="session-expiring-title"
      aria-describedby="session-expiring-text"
      // Esc não fecha: a decisão é continuar ou sair
      onCancel={(event) => event.preventDefault()}
    >
      {open && <ExpiringContent expiresAt={expiresAt} />}
    </Dialog>
  )
}
