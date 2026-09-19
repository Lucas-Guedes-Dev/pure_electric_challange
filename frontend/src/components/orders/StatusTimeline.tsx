import styled, { css } from 'styled-components'
import type { OrderStatus } from '../../graphql/generated/graphql'
import { formatCountdown } from '../../utils/format'

type StepState = 'done' | 'current' | 'pending' | 'failed'

const List = styled.ol`
  display: flex;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.space.sm};
  margin: 0;
  padding: 0;
  list-style: none;
`

const Step = styled.li<{ $state: StepState }>`
  flex: 1 1 160px;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.xxs};
  padding-top: ${({ theme }) => theme.space.sm};
  border-top: 4px solid ${({ theme }) => theme.colors.border};
  color: ${({ theme }) => theme.colors.muted};

  ${({ $state, theme }) =>
    ({
      done: css`
        border-color: ${theme.colors.heading};
        color: ${theme.colors.heading};
      `,
      current: css`
        border-color: ${theme.colors.accent};
        color: ${theme.colors.heading};
      `,
      failed: css`
        border-color: ${theme.colors.danger};
        color: ${theme.colors.danger};
      `,
      pending: css``,
    })[$state]}
`

const StepTitle = styled.span`
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: ${({ theme }) => theme.fontWeights.bold};
  letter-spacing: ${({ theme }) => theme.letterSpacings.wide};
  text-transform: uppercase;
`

const StepDetail = styled.span`
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.muted};
`

interface StatusTimelineProps {
  status: OrderStatus
  attempts: number
  /** Segundos até a próxima tentativa (quando aguardando retentativa) */
  retryIn: number | null
}

/** RECEBIDO → PROCESSANDO → PROCESSADO / FALHOU, com a etapa atual destacada. */
export function StatusTimeline({ status, attempts, retryIn }: StatusTimelineProps) {
  const processingState: StepState =
    status === 'RECEIVED' ? 'pending' : status === 'PROCESSING' ? 'current' : 'done'
  const finalState: StepState =
    status === 'PROCESSED' ? 'done' : status === 'FAILED' ? 'failed' : 'pending'

  let processingDetail = 'Aguardando o worker'
  if (status === 'PROCESSING') {
    processingDetail =
      retryIn !== null
        ? `Tentativa ${attempts} falhou · nova tentativa em ${formatCountdown(retryIn)}`
        : `Tentativa ${attempts} em andamento`
  } else if (status !== 'RECEIVED') {
    processingDetail = `${attempts} ${attempts === 1 ? 'tentativa' : 'tentativas'}`
  }

  return (
    <List aria-label="Andamento do pedido">
      <Step $state="done" aria-current={status === 'RECEIVED' ? 'step' : undefined}>
        <StepTitle>Recebido</StepTitle>
        <StepDetail>Gravado pela API</StepDetail>
      </Step>
      <Step $state={processingState} aria-current={status === 'PROCESSING' ? 'step' : undefined}>
        <StepTitle>Processando</StepTitle>
        <StepDetail>{processingDetail}</StepDetail>
      </Step>
      <Step $state={finalState} aria-current={finalState !== 'pending' ? 'step' : undefined}>
        <StepTitle>{status === 'FAILED' ? 'Falhou' : 'Processado'}</StepTitle>
        <StepDetail>
          {status === 'PROCESSED' && 'Aceito pelo sistema interno'}
          {status === 'FAILED' && 'Não foi processado'}
          {finalState === 'pending' && 'Aguardando o resultado'}
        </StepDetail>
      </Step>
    </List>
  )
}
