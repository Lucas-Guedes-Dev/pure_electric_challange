import { useRef, useState } from 'react'
import styled from 'styled-components'
import { LiveIndicator, OrdersTable, SimulatorPanel, StatsCards } from '../components/orders'
import { Alert, Button, Eyebrow, Heading, Pagination, SelectField, Stack, Text, TextField } from '../components/ui'
import type { OrderStatus } from '../graphql/generated/graphql'
import { useNow } from '../hooks/useNow'
import { useOrderFilters } from '../hooks/useOrderFilters'
import { PAGE_SIZE, useOrderList, useOrderSimulator } from '../hooks/useOrders'
import { media } from '../styles/theme'
import { ORDER_STATUSES, STATUS_META } from '../utils/orderStatus'

const Header = styled.div`
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: ${({ theme }) => theme.space.md};
`

const Filters = styled.div`
  display: grid;
  gap: ${({ theme }) => theme.space.md};

  ${media.md} {
    grid-template-columns: 2fr 1fr;
  }
`

const SEARCH_DEBOUNCE_MS = 300

export function OrdersPage() {
  const { filters, setFilters } = useOrderFilters()
  const { page, fetching, error, stats, newCount, highlighted, refresh } = useOrderList(filters)
  const simulator = useOrderSimulator()
  const [simulatorOpen, setSimulatorOpen] = useState(false)
  const now = useNow()

  // O campo mostra o que a pessoa digita; a URL (e a busca) só muda após uma pausa
  const [draft, setDraft] = useState<string | null>(null)
  const debounce = useRef<number | undefined>(undefined)
  function handleSearch(value: string) {
    setDraft(value)
    window.clearTimeout(debounce.current)
    debounce.current = window.setTimeout(() => {
      setFilters({ search: value }, { replace: true })
      setDraft(null)
    }, SEARCH_DEBOUNCE_MS)
  }

  const filtered = Boolean(filters.status || filters.search)

  return (
    <Stack $gap="lg">
      <Header>
        <div>
          <Eyebrow>Operação</Eyebrow>
          <Heading level={1}>Pedidos</Heading>
          <LiveIndicator />
        </div>
        {simulator.enabled && (
          <Button variant={simulatorOpen ? 'secondary' : 'accent'} onClick={() => setSimulatorOpen((open) => !open)}>
            {simulatorOpen ? 'Fechar simulador' : 'Simular pedidos'}
          </Button>
        )}
      </Header>

      {simulator.enabled && simulatorOpen && <SimulatorPanel onSimulated={refresh} />}

      <StatsCards stats={stats} active={filters.status} onSelect={(status) => setFilters({ status })} />

      <Filters>
        <TextField
          label="Buscar"
          type="search"
          placeholder="externalId ou cliente"
          value={draft ?? filters.search}
          onChange={(event) => handleSearch(event.target.value)}
        />
        <SelectField
          label="Status"
          value={filters.status ?? ''}
          onChange={(event) => setFilters({ status: (event.target.value || null) as OrderStatus | null })}
        >
          <option value="">Todos</option>
          {ORDER_STATUSES.map((status) => (
            <option key={status} value={status}>
              {STATUS_META[status].label}
            </option>
          ))}
        </SelectField>
      </Filters>

      {newCount > 0 && (
        <Alert
          tone="info"
          action={
            <Button size="sm" variant="secondary" onClick={refresh}>
              Mostrar
            </Button>
          }
        >
          {newCount === 1 ? '1 pedido novo' : `${newCount} pedidos novos`} desde a última atualização.
        </Alert>
      )}

      {error && (
        <Alert
          tone="danger"
          action={
            <Button size="sm" variant="secondary" onClick={refresh}>
              Tentar de novo
            </Button>
          }
        >
          Não foi possível carregar os pedidos. {error.graphQLErrors[0]?.message ?? 'Verifique sua conexão.'}
        </Alert>
      )}

      {!page && fetching && <Text $tone="muted">Carregando pedidos…</Text>}

      {page && page.items.length === 0 && (
        <Text $tone="muted">
          {filtered
            ? 'Nenhum pedido com esses filtros.'
            : simulator.enabled
              ? 'Nenhum pedido recebido ainda. Use "Simular pedidos" para enviar alguns.'
              : 'Nenhum pedido recebido ainda.'}
        </Text>
      )}

      {page && page.items.length > 0 && (
        <Stack $gap="md">
          <OrdersTable orders={page.items} highlighted={highlighted} now={now} />
          <Pagination
            page={page.page}
            size={PAGE_SIZE}
            total={page.total}
            onChange={(next) => setFilters({ page: next })}
          />
        </Stack>
      )}
    </Stack>
  )
}
