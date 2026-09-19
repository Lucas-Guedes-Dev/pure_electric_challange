import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useCountdown } from './useCountdown'
import { useOrderFilters } from './useOrderFilters'

describe('useCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-19T12:00:00Z'))
  })
  afterEach(() => vi.useRealTimers())

  it('conta os segundos até o alvo e para em zero', () => {
    const { result } = renderHook(() => useCountdown('2026-09-19T12:00:03Z'))
    expect(result.current).toBe(3)

    act(() => vi.advanceTimersByTime(2000))
    expect(result.current).toBe(1)

    act(() => vi.advanceTimersByTime(5000))
    expect(result.current).toBe(0)
  })

  it('sem alvo devolve null', () => {
    const { result } = renderHook(() => useCountdown(null))
    expect(result.current).toBeNull()
  })
})

describe('useOrderFilters (filtros na URL)', () => {
  function setup(initial: string) {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <MemoryRouter initialEntries={[initial]}>{children}</MemoryRouter>
    )
    return renderHook(() => ({ ...useOrderFilters(), location: useLocation() }), { wrapper })
  }

  it('lê status, busca e página da URL, ignorando valores inválidos', () => {
    expect(setup('/pedidos?status=FAILED&busca=ana&pagina=2').result.current.filters).toEqual({
      status: 'FAILED',
      search: 'ana',
      page: 2,
    })
    expect(setup('/pedidos?status=QUALQUER&pagina=-1').result.current.filters).toEqual({
      status: null,
      search: '',
      page: 1,
    })
  })

  it('mudar o status volta para a 1ª página; mudar a página mantém os filtros', () => {
    const { result } = setup('/pedidos?busca=ana&pagina=3')

    act(() => result.current.setFilters({ status: 'PROCESSED' }))
    expect(result.current.location.search).toBe('?status=PROCESSED&busca=ana')

    act(() => result.current.setFilters({ page: 2 }))
    expect(result.current.location.search).toBe('?status=PROCESSED&busca=ana&pagina=2')
  })
})
