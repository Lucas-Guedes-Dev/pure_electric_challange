import styled, { css } from 'styled-components'
import type { OrderStatus, OrderStatsQuery } from '../../graphql/generated/graphql'
import { ORDER_STATUSES, STATUS_META, toneColor } from '../../utils/orderStatus'
import type { BadgeVariant } from '../ui'

type Stats = OrderStatsQuery['orderStats']

const COUNT_FIELD: Record<OrderStatus, keyof Stats> = {
  RECEIVED: 'received',
  PROCESSING: 'processing',
  PROCESSED: 'processed',
  FAILED: 'failed',
}

const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: ${({ theme }) => theme.space.md};
`

const StatButton = styled.button<{ $active: boolean; $tone: BadgeVariant }>`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.xs};
  padding: ${({ theme }) => theme.space.md};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-top: 4px solid ${({ theme, $tone }) => toneColor(theme, $tone)};
  border-radius: ${({ theme }) => theme.radii.sm};
  background: ${({ theme }) => theme.colors.background};
  text-align: left;
  cursor: pointer;
  transition: background ${({ theme }) => theme.transitions.fast};

  &:hover {
    background: ${({ theme }) => theme.colors.surfaceHover};
  }

  ${({ $active, theme }) =>
    $active &&
    css`
      background: ${theme.colors.surface};
      border-color: ${theme.colors.heading};
    `}
`

const Count = styled.span`
  font-size: ${({ theme }) => theme.fontSizes.h3};
  font-weight: ${({ theme }) => theme.fontWeights.black};
  line-height: ${({ theme }) => theme.lineHeights.tight};
  color: ${({ theme }) => theme.colors.heading};
  font-variant-numeric: tabular-nums;
`

const Label = styled.span`
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: ${({ theme }) => theme.fontWeights.bold};
  letter-spacing: ${({ theme }) => theme.letterSpacings.wide};
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.muted};
`

interface StatsCardsProps {
  stats: Stats | null
  /** Status filtrado agora (o card fica destacado) */
  active?: OrderStatus | null
  /** Clique no card: filtra por aquele status (clicar de novo limpa) */
  onSelect: (status: OrderStatus | null) => void
}

export function StatsCards({ stats, active = null, onSelect }: StatsCardsProps) {
  return (
    <Grid role="group" aria-label="Totais por status">
      {ORDER_STATUSES.map((status) => {
        const meta = STATUS_META[status]
        const selected = active === status
        return (
          <StatButton
            key={status}
            type="button"
            $active={selected}
            $tone={meta.variant}
            aria-pressed={selected}
            onClick={() => onSelect(selected ? null : status)}
          >
            <Count>{stats ? stats[COUNT_FIELD[status]] : '–'}</Count>
            <Label>{meta.label}</Label>
          </StatButton>
        )
      })}
    </Grid>
  )
}
