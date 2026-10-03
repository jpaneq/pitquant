import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { Summary } from '../api/types'
import { SimulateTrade } from '../features/simulations/SimulateTrade'
import { SimulationsPage } from '../features/simulations/SimulationsPage'

const json = (b: unknown) => Promise.resolve(new Response(JSON.stringify(b), { status: 200, headers: { 'Content-Type': 'application/json' } }))
const ev = (over: object) => ({ n_simulations: 3, n_closed: 3, n_entered_closed: 3, by_state: {}, stats_available: false, hit_rate: null, mean_r: null, mean_return: null, mean_excess_return: null, mean_mae: null, mean_mfe: null, min_n: 10, note: 'x', ...over })
const mock = (evidence: object, rows: unknown[] = []) => vi.spyOn(globalThis, 'fetch').mockImplementation((u) => json(String(u).includes('/summary') ? { banner: 'PAPER TRADE — NO REAL MONEY', groups: { OPEN: 1, CLOSED: 2 }, evidence } : String(u).startsWith('/simulations') ? rows : { status: 'NO_VALID_SETUP', setups: [] }))
const wrap = (ui: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>)
afterEach(() => vi.restoreAllMocks())

describe('Simulation Lab UI', () => {
  it('always says PAPER TRADE and shows no statistics with insufficient N', async () => {
    mock(ev({}))
    wrap(<SimulationsPage />)
    expect(await screen.findByTestId('paper-banner')).toHaveTextContent('PAPER TRADE — NO REAL MONEY')
    expect(await screen.findByTestId('sim-insufficient')).toBeInTheDocument()
    expect(screen.queryByTestId('sim-stats')).toBeNull()
    expect(await screen.findByTestId('sim-empty')).toBeInTheDocument()
  })
  it('shows the aggregate metrics only when N is sufficient', async () => {
    mock(ev({ stats_available: true, n_entered_closed: 12, hit_rate: 0.58, mean_r: 0.4, mean_return: 0.02, mean_excess_return: 0.01, mean_mae: 0.03, mean_mfe: 0.06 }))
    wrap(<SimulationsPage />)
    expect(await screen.findByTestId('sim-stats')).toHaveTextContent(/Win rate \(N=12\)/)
    expect(screen.queryByTestId('sim-insufficient')).toBeNull()
  })
  it('disables «Simulate trade» with PRICE_DATA_REQUIRED for a security without prices', () => {
    mock(ev({}))
    const summary = { quote: { status: 'NO_DATA' }, simulation: { enabled: false, reason: 'PRICE_DATA_REQUIRED' } } as unknown as Summary
    wrap(<SimulateTrade sec="KO" summary={summary} />)
    expect(screen.getByTestId('simulate-disabled')).toBeDisabled()
    expect(screen.getByText('PRICE_DATA_REQUIRED')).toBeInTheDocument()
  })
})
