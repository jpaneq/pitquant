import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PositionsPanel } from '../features/positions/PositionsPanel'

const view = (reco: 'ADD' | 'HOLD' | 'SELL') => ({
  position_id: 'p1', asset_type: 'EQUITY', status: 'OPEN', quantity: 10, avg_cost: 100, realized_pnl: 0, horizon_months: 6, stop_rule: 'ATR14_2X_AT_OPEN', is_synthetic: false,
  review: { recommendation: reco, reason: 'motivo de prueba', score: 2.9, horizon_bucket: 'MEDIUM', label: 'RULE_BASED · NOT A PREDICTION', disclaimer: 'Reglas descriptivas con pesos sin validar.', missing_rules: ['valuation'], price_source: 'EOD_CLOSE', price_freshness: 'STALE',
    rules: [{ id: 'trend', label: 'Tendencia', value: 'UPTREND', contribution: 0.75, text: 'Tendencia alcista' }],
    position: { avg_cost: 100, quantity: 10, price: 110, pnl_pct: 0.1, pnl_value: 100, months_elapsed: 1, months_remaining: 5, horizon_months: 6, target_return: 0.2, target_met: false, stop_price: 95 } },
})
const wrap = (ui: React.ReactElement) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>
const stub = (reco: 'ADD' | 'HOLD' | 'SELL') => vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([view(reco)]), { status: 200, headers: { 'Content-Type': 'application/json' } })))

describe('PositionsPanel', () => {
  it.each([['ADD', 'AMPLIAR'], ['HOLD', 'MANTENER'], ['SELL', 'VENDER']] as const)('shows %s as %s with the reason, the rules and the not-a-prediction notice', async (reco, label) => {
    stub(reco)
    render(wrap(<PositionsPanel asset="EQUITY" security="AAPL" />))
    expect(await screen.findByLabelText('Recomendación')).toHaveTextContent(label)
    expect(screen.getByText('motivo de prueba')).toBeInTheDocument()
    expect(screen.getByText(/Reglas descriptivas con pesos sin validar/)).toBeInTheDocument()
    expect(screen.getByText(/Sin datos para: valuation/)).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
  it('offers a horizon in months and lets the user simulate a purchase', async () => {
    stub('HOLD')
    render(wrap(<PositionsPanel asset="BTC" />))
    const horizon = screen.getByLabelText('Horizonte en meses')
    await userEvent.selectOptions(horizon, '12')
    expect((horizon as HTMLSelectElement).value).toBe('12')
    expect(screen.getByRole('button', { name: 'Simular compra' })).toBeEnabled()
    expect(screen.getByText(/Dinero simulado: no hay broker/)).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
  it('disables add/sell until a quantity is typed', async () => {
    stub('ADD')
    render(wrap(<PositionsPanel asset="EQUITY" security="AAPL" />))
    await screen.findByLabelText('Recomendación')
    expect(screen.getByRole('button', { name: 'Simular ampliar' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Cantidad a ampliar o vender'), '3')
    expect(screen.getByRole('button', { name: 'Simular ampliar' })).toBeEnabled()
    vi.unstubAllGlobals()
  })
})
