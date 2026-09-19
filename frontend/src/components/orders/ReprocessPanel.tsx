import { useState, type FormEvent } from 'react'
import styled from 'styled-components'
import type { OrderStatus } from '../../graphql/generated/graphql'
import { useReprocessOrder } from '../../hooks/useOrders'
import { useSession } from '../../utils/session'
import { Alert, Button, Card, Heading, Stack, Text, TextField } from '../ui'

const REASON_MAX_LENGTH = 500

const Actions = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.space.sm};
`

interface ReprocessPanelProps {
  orderId: string
  externalId: string
  status: OrderStatus
}

/**
 * Reprocessamento manual de um pedido FAILED: pede confirmação (com motivo opcional) e
 * devolve o pedido à fila. Só aparece para administrador; o backend confere de novo.
 */
export function ReprocessPanel({ orderId, externalId, status }: ReprocessPanelProps) {
  const { isAdmin } = useSession()
  const { reprocessing, reprocess } = useReprocessOrder()
  const [confirming, setConfirming] = useState(false)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  // Depois do sucesso o pedido sai de FAILED; o aviso continua na tela
  if (!isAdmin || (status !== 'FAILED' && !done)) return null

  function cancel() {
    setConfirming(false)
    setReason('')
    setError(null)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    const result = await reprocess({ id: orderId, reason: reason.trim() || null })
    if (result.error) {
      setError(result.error.graphQLErrors[0]?.message ?? 'Não foi possível reprocessar o pedido.')
      return
    }
    setConfirming(false)
    setReason('')
    setDone(true)
  }

  return (
    <Card $tone="surface">
      <Stack $gap="sm">
        <Heading level={4}>Reprocessamento</Heading>

        {status === 'FAILED' && !confirming && (
          <>
            <Text $tone="muted" $size="sm">
              Devolve o pedido à fila com uma rodada nova de tentativas. O histórico atual é mantido.
            </Text>
            <div>
              <Button
                variant="accent"
                onClick={() => {
                  setDone(false)
                  setConfirming(true)
                }}
              >
                Reprocessar pedido
              </Button>
            </div>
          </>
        )}

        {status === 'FAILED' && confirming && (
          <form onSubmit={(event) => void handleSubmit(event)}>
            <Stack $gap="sm">
              <Text $size="sm">
                Reprocessar o pedido <strong>{externalId}</strong>? Ele volta para a fila e o worker tenta
                enviá-lo de novo ao sistema interno.
              </Text>
              <TextField
                label="Motivo (opcional)"
                hint="Fica registrado no histórico do pedido."
                value={reason}
                maxLength={REASON_MAX_LENGTH}
                onChange={(event) => setReason(event.target.value)}
                disabled={reprocessing}
                autoFocus
              />
              <Actions>
                <Button type="submit" variant="accent" disabled={reprocessing}>
                  {reprocessing ? 'Reprocessando…' : 'Confirmar reprocessamento'}
                </Button>
                <Button type="button" variant="ghost" onClick={cancel} disabled={reprocessing}>
                  Cancelar
                </Button>
              </Actions>
            </Stack>
          </form>
        )}

        {error && <Alert tone="danger">{error}</Alert>}
        {done && status !== 'FAILED' && (
          <Alert tone="success">
            Pedido de volta na fila. O andamento aparece abaixo em tempo real.
          </Alert>
        )}
      </Stack>
    </Card>
  )
}
