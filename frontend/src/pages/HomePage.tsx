import { useNavigate } from 'react-router-dom'
import { StatsCards } from '../components/orders'
import { Button, Card, Eyebrow, Heading, Highlight, Stack, Text } from '../components/ui'
import { useOrderEvents, useOrderStats } from '../hooks/useOrders'
import { useSession } from '../utils/session'

function greeting(hour: number): string {
  if (hour < 12) return 'Bom dia'
  if (hour < 18) return 'Boa tarde'
  return 'Boa noite'
}

export function HomePage() {
  const { user } = useSession()
  const navigate = useNavigate()
  const { stats, refresh } = useOrderStats()
  useOrderEvents(refresh) // totais ao vivo

  const firstName = (user?.full_name ?? user?.username ?? '').split(' ')[0]

  return (
    <Stack $gap="xl">
      <Stack $gap="sm">
        <Eyebrow>Pure Electric</Eyebrow>
        <Heading level={1}>
          {greeting(new Date().getHours())}
          {firstName && (
            <>
              , <Highlight>{firstName}.</Highlight>
            </>
          )}
        </Heading>
        <Text $tone="muted">
          Bem-vindo ao painel de pedidos. Aqui você acompanha, em tempo real, cada pedido recebido e
          o resultado do envio ao sistema interno.
        </Text>
      </Stack>

      <Stack $gap="md">
        <Heading level={4}>Resumo dos pedidos</Heading>
        <StatsCards stats={stats} onSelect={(status) => navigate(status ? `/pedidos?status=${status}` : '/pedidos')} />
      </Stack>

      <Card $tone="inverse">
        <Stack $gap="md" $align="flex-start">
          <Heading level={3}>
            Acompanhe seus <Highlight>pedidos.</Highlight>
          </Heading>
          <Text>Filtre por status, veja o histórico de tentativas e simule novos pedidos.</Text>
          <Button variant="accent" onClick={() => navigate('/pedidos')}>
            Ver pedidos
          </Button>
        </Stack>
      </Card>
    </Stack>
  )
}
