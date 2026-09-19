import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import styled from 'styled-components'
import { AttemptsTable, LiveIndicator, StatusBadge, StatusTimeline } from '../components/orders'
import { Alert, Button, Card, Eyebrow, Heading, Stack, Text } from '../components/ui'
import { useCountdown } from '../hooks/useCountdown'
import { useOrderDetail, useOrderSimulator } from '../hooks/useOrders'
import { formatCurrency, formatDateTime } from '../utils/format'

const BackLink = styled(Link)`
  align-self: flex-start;
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.muted};
  text-decoration: none;

  &:hover {
    color: ${({ theme }) => theme.colors.heading};
  }
`

const Header = styled.div`
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.space.md};
`

const Facts = styled.dl`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: ${({ theme }) => theme.space.md};
  margin: 0;

  dt {
    font-size: ${({ theme }) => theme.fontSizes.xs};
    font-weight: ${({ theme }) => theme.fontWeights.bold};
    letter-spacing: ${({ theme }) => theme.letterSpacings.wide};
    text-transform: uppercase;
    color: ${({ theme }) => theme.colors.muted};
  }
  dd {
    margin: ${({ theme }) => theme.space.xxs} 0 0;
    color: ${({ theme }) => theme.colors.heading};
    font-variant-numeric: tabular-nums;
  }
`

export function OrderDetailPage() {
  const { id = '' } = useParams()
  const { order, fetching, error, notFound, retry } = useOrderDetail(id)
  const simulator = useOrderSimulator()
  const [resendInfo, setResendInfo] = useState<string | null>(null)

  const waitingRetry = order?.status === 'PROCESSING' && order.nextAttemptAt ? order.nextAttemptAt : null
  const retryIn = useCountdown(waitingRetry)

  async function handleResend() {
    setResendInfo(null)
    const result = await simulator.resend({ id })
    if (result.error) {
      setResendInfo(result.error.graphQLErrors[0]?.message ?? 'Não foi possível reenviar.')
    } else if (result.data && !result.data.resendOrder.created) {
      setResendInfo('Reenviado com os mesmos dados: nenhum pedido novo foi criado nem processado de novo (idempotência).')
    }
  }

  return (
    <Stack $gap="lg">
      <BackLink to="/pedidos">← Pedidos</BackLink>

      {error && (
        <Alert
          tone="danger"
          action={
            <Button size="sm" variant="secondary" onClick={retry}>
              Tentar de novo
            </Button>
          }
        >
          Não foi possível carregar o pedido. {error.graphQLErrors[0]?.message ?? ''}
        </Alert>
      )}
      {!order && fetching && <Text $tone="muted">Carregando pedido…</Text>}
      {notFound && <Alert tone="warning">Pedido não encontrado.</Alert>}

      {order && (
        <>
          <Header>
            <div>
              <Eyebrow>Pedido #{order.id}</Eyebrow>
              <Heading level={1}>{order.externalId}</Heading>
              <LiveIndicator />
            </div>
            <StatusBadge status={order.status} nextAttemptAt={order.nextAttemptAt} />
          </Header>

          <Card>
            <Facts>
              <div>
                <dt>Cliente</dt>
                <dd>{order.customer}</dd>
              </div>
              <div>
                <dt>Valor</dt>
                <dd>{formatCurrency(order.amount)}</dd>
              </div>
              <div>
                <dt>Recebido em</dt>
                <dd>{formatDateTime(order.createdAt)}</dd>
              </div>
              <div>
                <dt>Finalizado em</dt>
                <dd>{order.finishedAt ? formatDateTime(order.finishedAt) : '—'}</dd>
              </div>
              <div>
                <dt>Protocolo interno</dt>
                <dd>{order.internalReference ?? '—'}</dd>
              </div>
            </Facts>
          </Card>

          <StatusTimeline status={order.status} attempts={order.attempts} retryIn={retryIn} />

          {order.lastError && (
            <Alert tone={order.status === 'FAILED' ? 'danger' : 'warning'}>{order.lastError}</Alert>
          )}

          <Stack $gap="sm">
            <Heading level={3}>Histórico de tentativas</Heading>
            <AttemptsTable attempts={order.history} />
          </Stack>

          {simulator.enabled && (
            <Card $tone="surface">
              <Stack $gap="sm">
                <Heading level={4}>Teste de idempotência</Heading>
                <Text $tone="muted" $size="sm">
                  Reenvia este pedido com os mesmos dados, como um sistema externo que repete o webhook.
                </Text>
                <div>
                  <Button variant="secondary" onClick={() => void handleResend()} disabled={simulator.resending.fetching}>
                    {simulator.resending.fetching ? 'Reenviando…' : 'Reenviar pedido'}
                  </Button>
                </div>
                {resendInfo && <Alert tone="success">{resendInfo}</Alert>}
              </Stack>
            </Card>
          )}
        </>
      )}
    </Stack>
  )
}
