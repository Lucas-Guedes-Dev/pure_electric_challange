import type { OrderStatus } from '../graphql/generated/graphql'

interface FilterableOrder {
  externalId: string
  customer: string
  status: OrderStatus
}

/** O pedido apareceria na lista com estes filtros? (mesma regra da busca do backend) */
export function matchesFilters(order: FilterableOrder, filters: { status: OrderStatus | null; search: string }): boolean {
  if (filters.status && order.status !== filters.status) return false
  const term = filters.search.trim().toLowerCase()
  if (!term) return true
  return order.externalId.toLowerCase().includes(term) || order.customer.toLowerCase().includes(term)
}
