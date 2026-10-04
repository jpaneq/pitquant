import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BitcoinPage } from '../features/bitcoin/BitcoinPage'

vi.mock('lightweight-charts', () => ({
  ColorType: { Solid: 'solid' }, LineSeries: {},
  createChart: () => ({ addSeries: () => ({ setData: vi.fn() }), remove: vi.fn(), timeScale: () => ({ fitContent: vi.fn() }) }),
}))

describe('Bitcoin audit workspace', () => {
  it('keeps prediction outputs absent and reveal disabled before freeze', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      readiness: { status: 'BLOCKED_BY_DATA', blockers: ['NO_PIT_HISTORY'] },
      strategies: { PREDICTION_ONLY: 'DISABLED', HYBRID: 'DISABLED' },
      availability: {}, missing_reasons: {}, provenance: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/bitcoin/predictions']}><BitcoinPage /></MemoryRouter></QueryClientProvider>)
    expect(screen.getByText('PAPER TRADE — NO REAL MONEY')).toBeInTheDocument()
    expect(screen.getAllByText('NOT_YET_VALIDATED')).toHaveLength(5)
    expect(screen.getByRole('button', { name: 'Reveal Outcome' })).toBeDisabled()
    expect(screen.getByRole('heading', { name: '365D' })).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
})
