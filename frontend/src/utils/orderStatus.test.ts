import { describe, expect, it } from 'vitest'
import { orderStatusMeta } from './orderStatus'
import { matchesFilters } from './orders'

describe('orderStatusMeta', () => {
  it('traduz cada status', () => {
    expect(orderStatusMeta({ status: 'RECEIVED' }).label).toBe('Recebido')
    expect(orderStatusMeta({ status: 'PROCESSED' }).variant).toBe('success')
    expect(orderStatusMeta({ status: 'FAILED' }).variant).toBe('danger')
  })

  it('PROCESSING com próxima tentativa agendada = aguardando retentativa', () => {
    expect(orderStatusMeta({ status: 'PROCESSING', nextAttemptAt: null }).label).toBe('Processando')
    expect(orderStatusMeta({ status: 'PROCESSING', nextAttemptAt: '2026-09-19T12:00:05Z' }).label).toBe(
      'Aguardando retentativa',
    )
  })
})

describe('matchesFilters (pedidos novos entram no aviso só se apareceriam na lista)', () => {
  const order = { externalId: 'FLAKY-SIM-1', customer: 'Ana Souza', status: 'RECEIVED' as const }

  it('sem filtros, qualquer pedido serve', () => {
    expect(matchesFilters(order, { status: null, search: '' })).toBe(true)
  })

  it('respeita o status filtrado', () => {
    expect(matchesFilters(order, { status: 'RECEIVED', search: '' })).toBe(true)
    expect(matchesFilters(order, { status: 'FAILED', search: '' })).toBe(false)
  })

  it('busca por externalId ou cliente, sem diferenciar maiúsculas', () => {
    expect(matchesFilters(order, { status: null, search: 'flaky' })).toBe(true)
    expect(matchesFilters(order, { status: null, search: 'SOUZA' })).toBe(true)
    expect(matchesFilters(order, { status: null, search: 'bruno' })).toBe(false)
  })
})
