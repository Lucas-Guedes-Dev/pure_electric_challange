import type { OrderStatus } from '../../graphql/generated/graphql'
import { orderStatusMeta } from '../../utils/orderStatus'
import { Badge } from '../ui'

interface StatusBadgeProps {
  status: OrderStatus
  nextAttemptAt?: string | null
}

export function StatusBadge({ status, nextAttemptAt }: StatusBadgeProps) {
  const meta = orderStatusMeta({ status, nextAttemptAt })
  return (
    <Badge $variant={meta.variant} title={meta.description}>
      {meta.label}
    </Badge>
  )
}
