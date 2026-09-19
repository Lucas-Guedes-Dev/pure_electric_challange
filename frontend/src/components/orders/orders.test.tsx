import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { ThemeProvider } from 'styled-components'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { theme } from '../../styles/theme'
import { AttemptsTable } from './AttemptsTable'
import { ReprocessPanel } from './ReprocessPanel'
import { StatsCards } from './StatsCards'
import { StatusBadge } from './StatusBadge'
import { StatusTimeline } from './StatusTimeline'

const withTheme = (ui: ReactNode) => render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>)

const mocks = vi.hoisted(() => ({
  isAdmin: true,
  reprocess: vi.fn(),
}))

vi.mock('../../utils/session', () => ({
  useSession: () => ({ isAdmin: mocks.isAdmin }),
}))

vi.mock('../../hooks/useOrders', () => ({
  useReprocessOrder: () => ({ reprocessing: false, reprocess: mocks.reprocess }),
}))

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

describe('StatusTimeline (reprocessado)', () => {
  it('mostra a rodada quando o pedido foi reprocessado', () => {
    withTheme(<StatusTimeline status="RECEIVED" attempts={3} cycle={2} retryIn={null} />)
    expect(screen.getByText('Reprocessado · rodada 2')).toBeTruthy()
  })
})

describe('AttemptsTable', () => {
  const attempt = (number: number, cycle: number, outcome: 'SUCCESS' | 'PERMANENT_ERROR') => ({
    number,
    cycle,
    outcome,
    startedAt: '2026-09-19T12:00:00Z',
    finishedAt: '2026-09-19T12:00:01Z',
    durationMs: 180,
    message: outcome === 'SUCCESS' ? null : 'Pedido recusado (HTTP 422)',
  })

  it('sem reprocessamento não mostra rodadas', () => {
    withTheme(<AttemptsTable attempts={[attempt(1, 1, 'SUCCESS')]} />)
    expect(screen.queryByText(/Rodada/)).toBeNull()
  })

  it('separa as tentativas por rodada, com quem reprocessou e o motivo', () => {
    withTheme(
      <AttemptsTable
        attempts={[attempt(1, 1, 'PERMANENT_ERROR'), attempt(2, 2, 'SUCCESS')]}
        reprocesses={[
          {
            number: 1,
            cycle: 2,
            requestedBy: 'Admin',
            reason: 'Cadastro liberado',
            previousError: 'Pedido recusado (HTTP 422)',
            createdAt: '2026-09-19T12:05:00Z',
          },
        ]}
      />,
    )
    expect(screen.getByText('Rodada 1')).toBeTruthy()
    expect(screen.getByText(/Rodada 2 · reprocessado por Admin em .* · Motivo: Cadastro liberado/)).toBeTruthy()
  })
})

describe('ReprocessPanel', () => {
  beforeEach(() => {
    mocks.isAdmin = true
    mocks.reprocess.mockReset()
  })

  it('só aparece para administrador e com o pedido em FAILED', () => {
    const { rerender } = withTheme(<ReprocessPanel orderId="1" externalId="FAIL-1" status="PROCESSED" />)
    expect(screen.queryByRole('button', { name: 'Reprocessar pedido' })).toBeNull()

    mocks.isAdmin = false
    rerender(
      <ThemeProvider theme={theme}>
        <ReprocessPanel orderId="1" externalId="FAIL-1" status="FAILED" />
      </ThemeProvider>,
    )
    expect(screen.queryByRole('button', { name: 'Reprocessar pedido' })).toBeNull()
  })

  it('pede confirmação e envia o motivo', async () => {
    mocks.reprocess.mockResolvedValue({ data: { reprocessOrder: { id: '1' } } })
    withTheme(<ReprocessPanel orderId="1" externalId="FAIL-1" status="FAILED" />)

    fireEvent.click(screen.getByRole('button', { name: 'Reprocessar pedido' }))
    fireEvent.change(screen.getByLabelText('Motivo (opcional)'), { target: { value: '  Cadastro liberado ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar reprocessamento' }))

    await waitFor(() => expect(mocks.reprocess).toHaveBeenCalledWith({ id: '1', reason: 'Cadastro liberado' }))
  })

  it('mostra o erro do backend (ex.: já reprocessado por outra pessoa)', async () => {
    mocks.reprocess.mockResolvedValue({
      error: { graphQLErrors: [{ message: 'Só pedidos com falha (FAILED) podem ser reprocessados' }] },
    })
    withTheme(<ReprocessPanel orderId="1" externalId="FAIL-1" status="FAILED" />)

    fireEvent.click(screen.getByRole('button', { name: 'Reprocessar pedido' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar reprocessamento' }))

    expect(await screen.findByText('Só pedidos com falha (FAILED) podem ser reprocessados')).toBeTruthy()
  })
})
