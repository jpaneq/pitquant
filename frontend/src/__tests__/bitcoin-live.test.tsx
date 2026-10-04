import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BitcoinPage } from '../features/bitcoin/BitcoinPage'
import { LiveHeader, ModelBar, type LiveMarketData } from '../features/bitcoin/LiveMarket'
import { PredictionFollowUp } from '../features/bitcoin/PredictionFollowUp'

vi.mock('lightweight-charts', () => ({
  ColorType: { Solid: 'solid' }, LineSeries: {},
  createChart: () => ({ addSeries: () => ({ setData: vi.fn() }), remove: vi.fn(), timeScale: () => ({ fitContent: vi.fn() }) }),
}))

const base: LiveMarketData = {
  retrieved_at: '2026-10-04T12:00:05+00:00',
  quote: { price: 61234.5, retrieved_at: '2026-10-04T12:00:05+00:00', status: 'LIVE', source: 'BINANCE_SPOT', timestamp_kind: 'RETRIEVED_AT' },
  rolling_24h: { change: -50, change_pct: -1.25, high: 62000, low: 60000, volume_btc: 1234.5, volume_usdt: 75000000 },
  last_closed_daily_bar: { open_time: '2026-10-03T00:00:00+00:00', close_time: '2026-10-03T23:59:59.999000+00:00', open: 60000, high: 61000, low: 59000, close: 60500, volume: 900, number_of_trades: 12345 },
}
const wrap = (ui: React.ReactElement) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>

describe('BTC live header', () => {
  it('shows the live price, freshness badge, 24h state and source', () => {
    render(<LiveHeader data={base} failed={false} />)
    expect(screen.getByLabelText('BTC price')).toHaveTextContent('$61,234.50')
    expect(screen.getByLabelText('Quote freshness')).toHaveTextContent('LIVE')
    expect(screen.getByText(/-1\.25%/)).toBeInTheDocument()
    expect(screen.getByText(/Source: Binance Spot/)).toBeInTheDocument()
    expect(screen.getByText(/Last updated/)).toBeInTheDocument()
    expect(screen.getByText(/24H ROLLING/)).toBeInTheDocument()
    expect(screen.queryByText(/SYNTHETIC/)).toBeNull()
  })
  it('does not hide a stale quote', () => {
    render(<LiveHeader data={{ ...base, quote: { ...base.quote!, status: 'STALE' } }} failed={false} />)
    expect(screen.getByLabelText('Quote freshness')).toHaveTextContent('STALE')
  })
  it('says real data is unavailable instead of inventing a price', () => {
    render(<LiveHeader data={{ retrieved_at: null, quote: { price: null, retrieved_at: null, status: 'UNAVAILABLE', source: 'BINANCE_SPOT', timestamp_kind: 'RETRIEVED_AT' }, reason: 'REAL DATA UNAVAILABLE: x' }} failed={false} />)
    expect(screen.getByText('REAL DATA UNAVAILABLE')).toBeInTheDocument()
    expect(screen.queryByLabelText('BTC price')).toBeNull()
    expect(screen.queryByText(/SYNTHETIC/)).toBeNull()
  })
  it('labels fixture data only when the backend says it is synthetic', () => {
    render(<LiveHeader data={{ ...base, data_mode: 'SYNTHETIC_TEST_DATA' }} failed={false} />)
    expect(screen.getByText(/SYNTHETIC TEST DATA/)).toBeInTheDocument()
  })
})

describe('BTC model bar', () => {
  it('is separate from the live quote and states the closed bar', () => {
    render(<><LiveHeader data={base} failed={false} /><ModelBar bar={base.last_closed_daily_bar} /></>)
    const bar = screen.getByLabelText('Model bar')
    expect(within(bar).getByText('MODEL BAR — 1D UTC')).toBeInTheDocument()
    expect(within(bar).getByText('$60,500.00')).toBeInTheDocument()
    expect(within(bar).getByText(/2026-10-03 23:59 UTC/)).toBeInTheDocument()
    expect(within(bar).getByText('Predictions use closed daily bars, not the live quote.')).toBeInTheDocument()
    expect(within(bar).queryByText('$61,234.50')).toBeNull()
  })
})

describe('BTC page wiring', () => {
  it('renders the live quote and the model bar from /btc/market/live', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(String(url).includes('/btc/snapshots') || String(url).includes('/btc/simulations') || String(url).includes('/positions') ? [] : String(url).includes('/btc/trade-plan') ? { as_of_bar: '2026-10-03T00:00:00+00:00', label: 'RULE_BASED', plan: { status: 'BLOCKED_BY_DATA', reason: 'sin datos' } } : String(url).includes('/btc/market/live') ? base : String(url).includes('market/bars') ? { bars: [] } : String(url).includes('/btc/evaluation') ? { items: [], horizons: {}, next_maturity: null, counts: {}, warning: 'NOT_VALIDATED' } : { readiness: { status: 'BLOCKED_BY_DATA', blockers: [] }, strategies: {}, availability: {}, missing_reasons: {}, provenance: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    render(wrap(<BitcoinPage />))
    expect(await screen.findByLabelText('BTC price')).toHaveTextContent('$61,234.50')
    expect(screen.getByLabelText('Model bar')).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
})

describe('Prediction follow-up', () => {
  it('shows pending predictions with their maturity instead of an error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      counts: { PENDING: 1, EVALUATED: 0 }, next_maturity: '2026-10-11T00:00:00+00:00', warning: 'NOT_VALIDATED: descriptive', horizons: {},
      items: [{ prediction_id: 'p1', decision_at: '2026-10-04T00:00:00+00:00', horizon: 7, target_at: '2026-10-11T00:00:00+00:00', state: 'PENDING', days_remaining: 3.5, predicted: 0.02, p_up: 0.6 }],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    render(wrap(<PredictionFollowUp cohort="FORWARD_PAPER" />))
    expect(await screen.findByText('Pendiente')).toBeInTheDocument()
    expect(screen.getByText(/en 3.5 d/)).toBeInTheDocument()
    expect(screen.queryByText(/LABEL_NOT_MATURE/)).toBeNull()
    vi.unstubAllGlobals()
  })
})
