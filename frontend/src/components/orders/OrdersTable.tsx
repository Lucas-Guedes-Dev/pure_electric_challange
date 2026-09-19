import { Link } from 'react-router-dom'
import styled, { css, keyframes } from 'styled-components'
import type { OrdersQuery } from '../../graphql/generated/graphql'
import { formatCurrency, formatDateTime, formatRelative } from '../../utils/format'
import { Table, TableWrapper, Td, Th, Tr } from '../ui'
import { StatusBadge } from './StatusBadge'

type OrderRow = OrdersQuery['orders']['items'][number]

const flash = keyframes`
  from { background: var(--flash-color); }
  to { background: transparent; }
`

const Row = styled(Tr)<{ $highlight: boolean }>`
  --flash-color: ${({ theme }) => theme.colors.accentSoft};
  ${({ $highlight }) =>
    $highlight &&
    css`
      animation: ${flash} 1.6s ease-out;
    `}
`

const OrderLink = styled(Link)`
  font-weight: ${({ theme }) => theme.fontWeights.medium};
  color: ${({ theme }) => theme.colors.heading};
  text-decoration: none;

  &:hover {
    color: ${({ theme }) => theme.colors.accent};
    text-decoration: underline;
  }
`

const Muted = styled.span`
  color: ${({ theme }) => theme.colors.muted};
`

interface OrdersTableProps {
  orders: OrderRow[]
  /** Pedidos que acabaram de mudar (piscam) */
  highlighted: Set<string>
  now: number
}

export function OrdersTable({ orders, highlighted, now }: OrdersTableProps) {
  return (
    <TableWrapper>
      <Table>
        <thead>
          <tr>
            <Th>Pedido</Th>
            <Th>Cliente</Th>
            <Th $align="right">Valor</Th>
            <Th>Status</Th>
            <Th $align="right">Tentativas</Th>
            <Th>Recebido</Th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <Row key={order.id} $highlight={highlighted.has(order.id)}>
              <Td>
                <OrderLink to={`/pedidos/${order.id}`}>{order.externalId}</OrderLink>
              </Td>
              <Td>{order.customer}</Td>
              <Td $align="right">{formatCurrency(order.amount)}</Td>
              <Td>
                <StatusBadge status={order.status} nextAttemptAt={order.nextAttemptAt} />
              </Td>
              <Td $align="right">{order.attempts}</Td>
              <Td title={formatDateTime(order.createdAt)}>
                <Muted>{formatRelative(order.createdAt, now)}</Muted>
              </Td>
            </Row>
          ))}
        </tbody>
      </Table>
    </TableWrapper>
  )
}
