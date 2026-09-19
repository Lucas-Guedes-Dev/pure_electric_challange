import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { OrderStatus } from '../graphql/generated/graphql'
import { ORDER_STATUSES } from '../utils/orderStatus'

export interface OrderFilters {
  status: OrderStatus | null
  search: string
  page: number
}

function parse(params: URLSearchParams): OrderFilters {
  const status = params.get('status')
  const page = Number(params.get('pagina'))
  return {
    status: ORDER_STATUSES.includes(status as OrderStatus) ? (status as OrderStatus) : null,
    search: params.get('busca') ?? '',
    page: Number.isInteger(page) && page > 0 ? page : 1,
  }
}

/**
 * Filtros da lista guardados na URL (?status=FAILED&busca=ana&pagina=2): o link pode ser
 * compartilhado e o botão voltar do navegador desfaz o filtro.
 */
export function useOrderFilters() {
  const [params, setParams] = useSearchParams()
  const filters = useMemo(() => parse(params), [params])

  const setFilters = useCallback(
    (patch: Partial<OrderFilters>, options: { replace?: boolean } = {}) => {
      setParams(
        (previous) => {
          const current = parse(previous)
          // Mudou status ou busca: volta para a 1ª página
          const resetPage = patch.page === undefined && ('status' in patch || 'search' in patch)
          const next = { ...current, ...patch, page: resetPage ? 1 : (patch.page ?? current.page) }
          const search = new URLSearchParams()
          if (next.status) search.set('status', next.status)
          if (next.search.trim()) search.set('busca', next.search)
          if (next.page > 1) search.set('pagina', String(next.page))
          return search
        },
        { replace: options.replace },
      )
    },
    [setParams],
  )

  return { filters, setFilters }
}
