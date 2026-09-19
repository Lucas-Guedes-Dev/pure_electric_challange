import type { OrderDetailQuery } from '../../graphql/generated/graphql'
import { formatDuration, formatTime } from '../../utils/format'
import { OUTCOME_META } from '../../utils/orderStatus'
import { Badge, Table, TableWrapper, Td, Text, Th, Tr } from '../ui'

type Attempt = NonNullable<OrderDetailQuery['order']>['history'][number]

export function AttemptsTable({ attempts }: { attempts: Attempt[] }) {
  if (attempts.length === 0) {
    return <Text $tone="muted">Nenhum envio ao sistema interno ainda.</Text>
  }

  return (
    <TableWrapper>
      <Table>
        <thead>
          <tr>
            <Th $align="right">#</Th>
            <Th>Início</Th>
            <Th $align="right">Duração</Th>
            <Th>Resultado</Th>
            <Th>Mensagem</Th>
          </tr>
        </thead>
        <tbody>
          {attempts.map((attempt) => {
            const outcome = OUTCOME_META[attempt.outcome]
            return (
              <Tr key={attempt.number}>
                <Td $align="right">{attempt.number}</Td>
                <Td>{formatTime(attempt.startedAt)}</Td>
                <Td $align="right">{formatDuration(attempt.durationMs)}</Td>
                <Td>
                  <Badge $variant={outcome.variant}>{outcome.label}</Badge>
                </Td>
                <Td>{attempt.message ?? '—'}</Td>
              </Tr>
            )
          })}
        </tbody>
      </Table>
    </TableWrapper>
  )
}
