import { fireEvent, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { ThemeProvider } from 'styled-components'
import { describe, expect, it, vi } from 'vitest'
import { theme } from '../../styles/theme'
import { StatsCards } from './StatsCards'
import { StatusBadge } from './StatusBadge'
import { StatusTimeline } from './StatusTimeline'

const withTheme = (ui: ReactNode) => render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>)

describe('StatusBadge', () => {
  it('mostra "Aguardando retentativa" quando há próxima tentativa', () => {
    withTheme(<StatusBadge status="PROCESSING" nextAttemptAt="2026-09-19T12:00:05Z" />)
    expect(screen.getByText('Aguardando retentativa')).toBeTruthy()
  })
})

describe('StatsCards', () => {
  const stats = { received: 2, processing: 1, processed: 38, failed: 3, total: 44 }

  it('mostra os totais e filtra ao clicar (clicar de novo limpa)', () => {
    const onSelect = vi.fn()
    const { rerender } = withTheme(<StatsCards stats={stats} onSelect={onSelect} />)

    expect(screen.getByRole('button', { name: /38\s*Processado/ })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /3\s*Falhou/ }))
    expect(onSelect).toHaveBeenLastCalledWith('FAILED')

    rerender(
      <ThemeProvider theme={theme}>
        <StatsCards stats={stats} active="FAILED" onSelect={onSelect} />
      </ThemeProvider>,
    )
    const active = screen.getByRole('button', { name: /3\s*Falhou/ })
    expect(active.getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(active)
    expect(onSelect).toHaveBeenLastCalledWith(null)
  })
})

describe('StatusTimeline', () => {
  it('mostra a contagem até a próxima tentativa', () => {
    withTheme(<StatusTimeline status="PROCESSING" attempts={1} retryIn={8} />)
    expect(screen.getByText('Tentativa 1 falhou · nova tentativa em 0:08')).toBeTruthy()
  })

  it('pedido que falhou marca a etapa final como falha', () => {
    withTheme(<StatusTimeline status="FAILED" attempts={3} retryIn={null} />)
    expect(screen.getByText('Falhou')).toBeTruthy()
    expect(screen.getByText('3 tentativas')).toBeTruthy()
  })
})
