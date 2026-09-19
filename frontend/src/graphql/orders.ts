/**
 * Operações GraphQL de pedidos. Os tipos de cada uma são gerados pelo codegen
 * (`npm run codegen`) a partir do backend/schema.graphql.
 */
import { graphql } from './generated'

export const ORDER_SUMMARY_FRAGMENT = graphql(`
  fragment OrderSummary on Order {
    id
    externalId
    customer
    amount
    status
    attempts
    cycle
    nextAttemptAt
    lastError
    internalReference
    createdAt
    updatedAt
    finishedAt
  }
`)

export const ORDER_HISTORY_FRAGMENT = graphql(`
  fragment OrderHistory on Order {
    history {
      number
      cycle
      startedAt
      finishedAt
      durationMs
      outcome
      message
    }
  }
`)

export const ORDER_REPROCESSES_FRAGMENT = graphql(`
  fragment OrderReprocesses on Order {
    reprocesses {
      number
      cycle
      requestedBy
      reason
      previousError
      createdAt
    }
  }
`)

export const ORDERS_QUERY = graphql(`
  query Orders($status: OrderStatus, $search: String, $page: Int!, $size: Int!) {
    orders(status: $status, search: $search, page: $page, size: $size) {
      total
      page
      size
      items {
        ...OrderSummary
      }
    }
  }
`)

export const ORDER_STATS_QUERY = graphql(`
  query OrderStats {
    orderStats {
      received
      processing
      processed
      failed
      total
    }
  }
`)

export const ORDER_DETAIL_QUERY = graphql(`
  query OrderDetail($id: ID!) {
    order(id: $id) {
      ...OrderSummary
      ...OrderHistory
      ...OrderReprocesses
    }
  }
`)

/** Todos os pedidos (lista): sem histórico, para cada evento sair barato */
export const ORDERS_UPDATED_SUBSCRIPTION = graphql(`
  subscription OrdersUpdated {
    orderUpdated {
      ...OrderSummary
    }
  }
`)

/** Um pedido (detalhe): com histórico e reprocessamentos, para a tabela de tentativas atualizar ao vivo */
export const ORDER_UPDATED_SUBSCRIPTION = graphql(`
  subscription OrderUpdated($id: ID!) {
    orderUpdated(id: $id) {
      ...OrderSummary
      ...OrderHistory
      ...OrderReprocesses
    }
  }
`)

export const SIMULATOR_ENABLED_QUERY = graphql(`
  query OrderSimulatorEnabled {
    orderSimulatorEnabled
  }
`)

export const SIMULATE_ORDERS_MUTATION = graphql(`
  mutation SimulateOrders($input: SimulateOrdersInput!) {
    simulateOrders(input: $input) {
      created
      order {
        ...OrderSummary
      }
    }
  }
`)

export const RESEND_ORDER_MUTATION = graphql(`
  mutation ResendOrder($id: ID!) {
    resendOrder(id: $id) {
      created
      order {
        ...OrderSummary
      }
    }
  }
`)

/** Devolve um pedido FAILED à fila (só administrador). Traz o histórico e os
 * reprocessamentos para o detalhe atualizar na hora, antes do primeiro evento. */
export const REPROCESS_ORDER_MUTATION = graphql(`
  mutation ReprocessOrder($id: ID!, $reason: String) {
    reprocessOrder(id: $id, reason: $reason) {
      ...OrderSummary
      ...OrderHistory
      ...OrderReprocesses
    }
  }
`)
