import { describe, expect, it } from 'vitest'
import { formatCountdown, formatCurrency, formatDuration, formatRelative } from './format'

describe('formatCurrency', () => {
  it('formata o Decimal (string) em reais', () => {
    expect(formatCurrency('150.00')).toMatch(/^R\$\s150,00$/)
    expect(formatCurrency('1234.5')).toMatch(/^R\$\s1\.234,50$/)
  })
})

describe('formatRelative', () => {
  const now = Date.parse('2026-09-19T12:00:00Z')

  it.each([
    ['2026-09-19T11:59:55Z', 'agora'],
    ['2026-09-19T11:59:30Z', 'há 30 segundos'],
    ['2026-09-19T11:58:00Z', 'há 2 minutos'],
    ['2026-09-19T09:00:00Z', 'há 3 horas'],
    ['2026-09-18T12:00:00Z', 'ontem'],
  ])('%s -> %s', (iso, expected) => {
    expect(formatRelative(iso, now)).toBe(expected)
  })

  it('nunca mostra tempo no futuro (pedido mais novo que o relógio da tela)', () => {
    expect(formatRelative('2026-09-19T12:00:15Z', now)).toBe('agora')
  })
})

describe('formatDuration', () => {
  it('usa ms abaixo de 1 segundo e segundos com vírgula acima', () => {
    expect(formatDuration(175)).toBe('175 ms')
    expect(formatDuration(5012)).toBe('5,0 s')
  })
})

describe('formatCountdown', () => {
  it('formata como m:ss e nunca fica negativo', () => {
    expect(formatCountdown(68)).toBe('1:08')
    expect(formatCountdown(5)).toBe('0:05')
    expect(formatCountdown(-3)).toBe('0:00')
  })
})
