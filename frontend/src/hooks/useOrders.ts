/**
 * Dados das telas de pedidos (GraphQL). O graphcache guarda cada pedido pelo `id`: quando a
 * subscription entrega um pedido atualizado, toda tela que o mostra re-renderiza sozinha.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useSubscription } from 'urql'
import {
  ORDER_DETAIL_QUERY,
  ORDER_STATS_QUERY,
  ORDER_UPDATED_SUBSCRIPTION,
  ORDERS_QUERY,
  ORDERS_UPDATED_SUBSCRIPTION,
  REPROCESS_ORDER_MUTATION,
  RESEND_ORDER_MUTATION,
  SIMULATE_ORDERS_MUTATION,
  SIMULATOR_ENABLED_QUERY,
} from '../graphql/orders'
import type { OrderStatus } from '../graphql/generated/graphql'
import { matchesFilters } from '../utils/orders'
import type { OrderFilters } from './useOrderFilters'

export const PAGE_SIZE = 20
const HIGHLIGHT_MS = 1600
const STATS_REFRESH_MS = 1000

/** Executa `fn` no máximo uma vez a cada `ms` (a última chamada da rajada sempre roda). */
function useThrottled(fn: () => void, ms: number): () => void {
  const fnRef = useRef(fn)
  const last = useRef(0)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    fnRef.current = fn
  })
  useEffect(() => () => window.clearTimeout(timer.current), [])

  return useCallback(() => {
    const wait = last.current + ms - Date.now()
    if (wait <= 0) {
      last.current = Date.now()
      fnRef.current()
    } else if (timer.current === undefined) {
      timer.current = window.setTimeout(() => {
        timer.current = undefined
        last.current = Date.now()
        fnRef.current()
      }, wait)
    }
  }, [ms])
}

/** Totais por status, atualizados pelos eventos em tempo real. */
export function useOrderStats() {
  const [result, reexecute] = useQuery({ query: ORDER_STATS_QUERY })
  const refresh = useThrottled(() => reexecute({ requestPolicy: 'network-only' }), STATS_REFRESH_MS)
  return { stats: result.data?.orderStats ?? null, error: result.error, refresh }
}

export interface OrderEvent {
  id: string
  externalId: string
  customer: string
  status: OrderStatus
}

/** Assina a mudança de qualquer pedido. */
export function useOrderEvents(onOrder: (order: OrderEvent) => void) {
  const handler = useRef(onOrder)
  useEffect(() => {
    handler.current = onOrder
  })
  useSubscription({ query: ORDERS_UPDATED_SUBSCRIPTION }, (_previous, data) => {
    handler.current(data.orderUpdated)
    return data
  })
}

/**
 * Lista com filtros + tempo real:
 * - pedidos já na tela mudam sozinhos (cache) e piscam para chamar atenção;
 * - pedidos novos que entrariam nesta lista viram o aviso "N pedidos novos", em vez de
 *   embaralhar a tabela enquanto a pessoa lê;
 * - os totais são atualizados no máximo 1x por segundo, mesmo com rajadas de eventos.
 */
export function useOrderList(filters: OrderFilters) {
  const variables = useMemo(
    () => ({ status: filters.status, search: filters.search.trim() || null, page: filters.page, size: PAGE_SIZE }),
    [filters.status, filters.search, filters.page],
  )
  const [result, reexecute] = useQuery({ query: ORDERS_QUERY, variables })
  const stats = useOrderStats()

  const filtersKey = `${variables.status}|${variables.search}|${variables.page}`
  const [pending, setPending] = useState<{ key: string; ids: Set<string> }>({ key: filtersKey, ids: new Set() })
  const newIds = pending.key === filtersKey ? pending.ids : new Set<string>()
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set())

  const items = result.data?.orders.items
  const latest = useRef({ ids: new Set<string>(), filters, filtersKey })
  useEffect(() => {
    latest.current = { ids: new Set(items?.map((order) => order.id)), filters, filtersKey }
  })

  useOrderEvents((order) => {
    const { ids, filters: current, filtersKey: key } = latest.current
    if (ids.has(order.id)) {
      setHighlighted((previous) => new Set(previous).add(order.id))
      window.setTimeout(() => {
        setHighlighted((previous) => {
          const next = new Set(previous)
          next.delete(order.id)
          return next
        })
      }, HIGHLIGHT_MS)
    } else if (matchesFilters(order, current)) {
      setPending((previous) => ({
        key,
        ids: new Set(previous.key === key ? previous.ids : []).add(order.id),
      }))
    }
    stats.refresh()
  })

  const refresh = useCallback(() => {
    setPending({ key: filtersKey, ids: new Set() })
    reexecute({ requestPolicy: 'network-only' })
    stats.refresh()
  }, [filtersKey, reexecute, stats])

  return {
    page: result.data?.orders ?? null,
    fetching: result.fetching,
    error: result.error,
    stats: stats.stats,
    newCount: newIds.size,
    highlighted,
    refresh,
  }
}

/** Um pedido + histórico, atualizado ao vivo pela subscription desse pedido. */
export function useOrderDetail(id: string) {
  const [result, reexecute] = useQuery({ query: ORDER_DETAIL_QUERY, variables: { id } })
  // O resultado da subscription entra no cache e atualiza a query acima sozinho
  useSubscription({ query: ORDER_UPDATED_SUBSCRIPTION, variables: { id } })
  return {
    order: result.data?.order ?? null,
    fetching: result.fetching,
    error: result.error,
    notFound: result.data !== undefined && result.data.order === null,
    retry: () => reexecute({ requestPolicy: 'network-only' }),
  }
}

/** Simulador de pedidos (só aparece se o backend estiver com ele ligado). */
export function useOrderSimulator() {
  const [enabled] = useQuery({ query: SIMULATOR_ENABLED_QUERY })
  const [simulation, simulate] = useMutation(SIMULATE_ORDERS_MUTATION)
  const [resending, resend] = useMutation(RESEND_ORDER_MUTATION)
  return {
    enabled: enabled.data?.orderSimulatorEnabled === true,
    simulation,
    simulate,
    resending,
    resend,
  }
}

/** Reprocessamento de pedido FAILED (só administrador; o backend confere). */
export function useReprocessOrder() {
  const [state, reprocess] = useMutation(REPROCESS_ORDER_MUTATION)
  return { reprocessing: state.fetching, reprocess }
}
