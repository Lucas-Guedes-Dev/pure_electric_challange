/** Rótulos, cores e textos dos estados de pedido e dos resultados de tentativa. */
import type { BadgeVariant } from '../components/ui'
import type { AttemptOutcome, OrderStatus } from '../graphql/generated/graphql'
import type { AppTheme } from '../styles/theme'

export interface StatusMeta {
  label: string
  variant: BadgeVariant
  description: string
}

export const ORDER_STATUSES: OrderStatus[] = ['RECEIVED', 'PROCESSING', 'PROCESSED', 'FAILED']

export const STATUS_META: Record<OrderStatus, StatusMeta> = {
  RECEIVED: { label: 'Recebido', variant: 'neutral', description: 'Gravado, aguardando o worker' },
  PROCESSING: { label: 'Processando', variant: 'accent', description: 'Sendo enviado ao sistema interno' },
  PROCESSED: { label: 'Processado', variant: 'success', description: 'Aceito pelo sistema interno' },
  FAILED: { label: 'Falhou', variant: 'danger', description: 'Recusado ou tentativas esgotadas' },
}

const WAITING_RETRY: StatusMeta = {
  label: 'Aguardando retentativa',
  variant: 'accent',
  description: 'Falha temporária; o worker vai tentar de novo',
}

/** Status para exibir. PROCESSING com próxima tentativa agendada = aguardando retentativa. */
export function orderStatusMeta(order: { status: OrderStatus; nextAttemptAt?: string | null }): StatusMeta {
  if (order.status === 'PROCESSING' && order.nextAttemptAt) return WAITING_RETRY
  return STATUS_META[order.status]
}

export const OUTCOME_META: Record<AttemptOutcome, { label: string; variant: BadgeVariant }> = {
  SUCCESS: { label: 'Sucesso', variant: 'success' },
  TRANSIENT_ERROR: { label: 'Falha temporária', variant: 'accent' },
  PERMANENT_ERROR: { label: 'Recusado', variant: 'danger' },
}

/** Cor do tema equivalente a cada variante de badge (ex.: faixa dos cards de totais). */
export function toneColor(theme: AppTheme, tone: BadgeVariant): string {
  return {
    neutral: theme.colors.border,
    accent: theme.colors.accent,
    success: theme.colors.success,
    danger: theme.colors.danger,
    info: theme.colors.info,
  }[tone]
}
