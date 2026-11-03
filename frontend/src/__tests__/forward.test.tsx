import { afterEach, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ForwardPage } from '../features/forward/ForwardPage'

const evidence = {
  markets: [{ market: 'BTC', model_id: 'm1', model: { version: 'v1', train_n: 500, train_target_end: '2025-09-29', universe: ['BTC'] }, n: 1, mature: 0, pending: 1, hits: 0, failures: 0, accuracy: null, brier: null, logloss: null, always_up_accuracy: null, momentum_accuracy: null, nonoverlap_n: 1, abstentions: 0, paper: { open: 0, closed: 0, metrics_available: false, mean_win: null, mean_loss: null, worst_trade_drawdown: null, mean_excess_vs_benchmark: null, items: [] } }],
  predictions: [{ id: 'p1', market: 'BTC', ticker: 'BTC', version: 'v1', generated_at: '2026-11-03T12:00:00Z', feature_date: '2026-11-02', reference_price: 100, due_at: '2026-12-03T00:00:00Z', p_up: .48 }],
  reviews: [], outcomes: [], gaps: [], replays: [],
}
const wrap = () => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><ForwardPage /></MemoryRouter></QueryClientProvider>
afterEach(() => vi.unstubAllGlobals())

it('keeps pending outcomes unscored and does not open a trade on page load', async () => {
  const fetcher = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(evidence)))
  vi.stubGlobal('fetch', fetcher)
  render(wrap())
  expect(await screen.findByText(/probabilidades sin calibración/)).toBeInTheDocument()
  expect(screen.getByText('48.0%')).toBeInTheDocument()
  expect(screen.getByText(/al menos 10 operaciones cerradas/)).toBeInTheDocument()
  expect(fetcher.mock.calls.every(call => call.length < 2 || !(call[1] as RequestInit)?.method)).toBe(true)
})

it('opens a linked simulation only after explicit manual action', async () => {
  const requests: { url: string; body: string }[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') {
      requests.push({url: String(url), body: String(init.body)})
      return new Response(JSON.stringify({ simulation_id: 's1' }))
    }
    return new Response(JSON.stringify(evidence))
  }))
  render(wrap())
  await screen.findByText('48.0%')
  await userEvent.click(screen.getByRole('button', { name: /^Simular$/ }))
  expect(await screen.findByRole('link', { name: 'Ver simulación creada' })).toHaveAttribute('href', '/bitcoin')
  expect(requests).toHaveLength(1)
  expect(requests[0].url).toContain('/forward-pilots/simulate')
  expect(JSON.parse(requests[0].body)).toEqual({ prediction_id: 'p1', notional: 1000 })
})
