import { Fragment } from 'react'
import styled from 'styled-components'
import type { OrderDetailQuery } from '../../graphql/generated/graphql'
import { formatDateTime, formatDuration, formatTime } from '../../utils/format'
import { OUTCOME_META } from '../../utils/orderStatus'
import { Badge, Table, TableWrapper, Td, Text, Th, Tr } from '../ui'

type OrderDetail = NonNullable<OrderDetailQuery['order']>
type Attempt = OrderDetail['history'][number]
type Reprocess = OrderDetail['reprocesses'][number]

const RoundCell = styled(Td)`
  background: ${({ theme }) => theme.colors.surface};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.muted};

  strong {
    color: ${({ theme }) => theme.colors.heading};
  }
`

function roundTitle(reprocess: Reprocess | undefined, cycle: number): string {
  if (!reprocess) return `Rodada ${cycle}`
  const who = reprocess.requestedBy ? ` por ${reprocess.requestedBy}` : ''
  const why = reprocess.reason ? ` · Motivo: ${reprocess.reason}` : ''
  return `Rodada ${cycle} · reprocessado${who} em ${formatDateTime(reprocess.createdAt)}${why}`
}

interface AttemptsTableProps {
  attempts: Attempt[]
  /** Reprocessamentos manuais: separam as tentativas em rodadas */
  reprocesses?: Reprocess[]
}

export function AttemptsTable({ attempts, reprocesses = [] }: AttemptsTableProps) {
  if (attempts.length === 0 && reprocesses.length === 0) {
    return <Text $tone="muted">Nenhum envio ao sistema interno ainda.</Text>
  }

  const lastCycle = Math.max(1, ...attempts.map((a) => a.cycle), ...reprocesses.map((r) => r.cycle))
  const cycles = Array.from({ length: lastCycle }, (_, index) => index + 1)
  const showRounds = lastCycle > 1

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
          {cycles.map((cycle) => {
            const inCycle = attempts.filter((attempt) => attempt.cycle === cycle)
            const reprocess = reprocesses.find((r) => r.cycle === cycle)
            return (
              <Fragment key={cycle}>
                {showRounds && (
                  <tr>
                    <RoundCell colSpan={5}>
                      <strong>{roundTitle(reprocess, cycle)}</strong>
                    </RoundCell>
                  </tr>
                )}
                {inCycle.length === 0 && showRounds && (
                  <Tr>
                    <Td colSpan={5}>
                      <Text $tone="muted" $size="sm">
                        Nenhum envio concluído nesta rodada ainda.
                      </Text>
                    </Td>
                  </Tr>
                )}
                {inCycle.map((attempt) => {
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
              </Fragment>
            )
          })}
        </tbody>
      </Table>
    </TableWrapper>
  )
}
