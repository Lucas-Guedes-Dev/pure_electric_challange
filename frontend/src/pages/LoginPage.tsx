import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, type Location } from 'react-router-dom'
import styled from 'styled-components'
import { ApiError } from '../api/httpClient'
import { SessionLoading } from '../components/session-loading'
import { Button, Eyebrow, Heading, Highlight, Stack, Text, TextField } from '../components/ui'
import { authService } from '../services/authService'
import { media } from '../styles/theme'
import { startSession, useSession } from '../utils/session'

const Page = styled.main`
  display: grid;
  min-height: 100vh;
  min-height: 100dvh;
  background: ${({ theme }) => theme.colors.background};

  ${media.md} {
    grid-template-columns: 1fr 1fr;
  }
`

const BrandPanel = styled.section`
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: ${({ theme }) => theme.space.xl};
  padding: ${({ theme }) => theme.space.lg};
  background: ${({ theme }) => theme.colors.inverse.background};
  color: ${({ theme }) => theme.colors.inverse.text};

  h1 {
    color: ${({ theme }) => theme.colors.inverse.heading};
  }

  ${media.md} {
    padding: ${({ theme }) => theme.space.xxl};
  }
`

const Logo = styled.span`
  font-size: ${({ theme }) => theme.fontSizes.lg};
  letter-spacing: ${({ theme }) => theme.letterSpacings.logo};
  color: ${({ theme }) => theme.colors.inverse.heading};

  strong {
    font-weight: ${({ theme }) => theme.fontWeights.bold};
  }
  span {
    font-weight: ${({ theme }) => theme.fontWeights.light};
  }
`

const Tagline = styled(Stack)`
  display: none;

  ${media.md} {
    display: flex;
  }
`

const InverseText = styled(Text)`
  color: ${({ theme }) => theme.colors.inverse.muted};
`

const FormPanel = styled.section`
  display: grid;
  place-items: center;
  padding: ${({ theme }) => `${theme.space.xl} ${theme.space.md}`};
`

const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.md};
  width: 100%;
  max-width: 380px;
`

const Notice = styled.p<{ $tone: 'info' | 'danger' }>`
  margin: 0;
  padding: ${({ theme }) => `${theme.space.sm} ${theme.space.md}`};
  border-radius: ${({ theme }) => theme.radii.xs};
  border-left: 3px solid
    ${({ theme, $tone }) => ($tone === 'danger' ? theme.colors.danger : theme.colors.accent)};
  background: ${({ theme, $tone }) => ($tone === 'danger' ? theme.colors.dangerSoft : theme.colors.accentSoft)};
  color: ${({ theme }) => theme.colors.heading};
  font-size: ${({ theme }) => theme.fontSizes.sm};
`

interface LocationState {
  from?: Location
}

export function LoginPage() {
  const location = useLocation()
  const { status, isAuthenticated, endReason } = useSession()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const from = (location.state as LocationState | null)?.from
  const redirectTo = from ? `${from.pathname}${from.search}${from.hash}` : '/inicio'

  if (status === 'loading') return <SessionLoading />
  // Logado (ou acabou de logar): volta para a página que pediu o login
  if (isAuthenticated) return <Navigate to={redirectTo} replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      startSession(await authService.login({ username: username.trim(), password }))
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Não foi possível conectar ao servidor. Tente novamente em instantes.',
      )
      setPassword('')
      setSubmitting(false)
    }
  }

  return (
    <Page>
      <BrandPanel>
        <Logo aria-label="Pure Electric">
          <strong>PURE</strong> <span>ELECTRIC</span>
        </Logo>
        <Tagline $gap="sm">
          <Eyebrow>Sistema interno</Eyebrow>
          <Heading level={1}>
            Bem-vindo de <Highlight>volta.</Highlight>
          </Heading>
          <InverseText>Entre com seu usuário para continuar.</InverseText>
        </Tagline>
      </BrandPanel>

      <FormPanel>
        <Form onSubmit={handleSubmit}>
          <Stack $gap="xs">
            <Heading level={2}>Entrar</Heading>
            <Text $tone="muted" $size="sm">
              Por segurança, a sessão encerra após um período sem uso.
            </Text>
          </Stack>

          {error ? (
            <Notice $tone="danger" role="alert">
              {error}
            </Notice>
          ) : (
            endReason && (
              <Notice $tone="info" role="status">
                {endReason}
              </Notice>
            )
          )}

          <TextField
            label="Usuário ou e-mail"
            name="username"
            autoComplete="username"
            autoFocus
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <TextField
            label="Senha"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button type="submit" variant="accent" size="lg" fullWidth disabled={submitting}>
            {submitting ? 'Entrando…' : 'Entrar'}
          </Button>
        </Form>
      </FormPanel>
    </Page>
  )
}
