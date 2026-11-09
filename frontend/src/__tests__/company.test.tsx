import { expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Factsheet, type Sheet } from '../features/companies/CompanyPage'

const comp = (metric: string, label: string, value: number) => ({ metric, label, value, own_median: .04, peer_median: .04, own_pct: 5, peer_pct: 20 })
const apple: Sheet = {
  ticker: 'AAPL', name: 'Apple Inc.', sector: 'Electronic Computers', sector_supported: true, currency: 'USD',
  price: 342.37, price_date: '2026-11-06', latest_period: '2026-09-26', latest_filing_at: '2026-11-03T13:20:15+00:00',
  ttm: { revenue: 478.8e9, net_income: 132.2e9, fcf: 136.1e9 },
  profitability: { net_margin: .276, operating_margin: .33, roa: .346, fcf_margin: .284 },
  growth: { revenue_yoy: .151, revenue_cagr5: .055, net_income_yoy: .18, fcf_yoy: .378 },
  balance: { net_debt: 41.8e9, debt_to_assets: .19, cash: 36.3e9 },
  capital_allocation: { shareholder_yield: .02, dividend_yield: .003, buyback_yield: .017, shares_growth1: -.017 },
  valuation: { market_cap: 4.98e12, pe: 37.6 },
  history: [{ period: '2025-12-27', revenue: 4e11, net_income: 1e11, fcf: 1e11, operating_margin: .31, net_margin: .25, debt_to_assets: .2 }, { period: '2026-09-26', revenue: 4.79e11, net_income: 1.32e11, fcf: 1.36e11, operating_margin: .33, net_margin: .276, debt_to_assets: .19 }],
  valuation_history: [],
  cheapness: { label: 'MUY_CARA', score: 12, vs_own_history: 4, vs_peers: 20, peers_n: 50, components: [comp('earnings_yield', 'Beneficio / precio', .0266)] },
}

it('renders the factsheet with the expensive/cheap verdict and plain-language figures', () => {
  render(<Factsheet s={apple} />)
  expect(screen.getAllByText('Muy cara')[0]).toHaveClass('text-3xl')
  expect(screen.getByLabelText('Puntuación 12 de 100')).toBeInTheDocument()
  expect(screen.getByText('4/100')).toBeInTheDocument()
  expect(screen.getByText('Frente a las otras 50 empresas')).toBeInTheDocument()
  expect(screen.getByText('478.8 mil M$')).toBeInTheDocument()
  expect(screen.getByText('2.7%')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Ventas y beneficio' })).toBeInTheDocument()
})

it('says when the indicator does not apply (banks)', () => {
  render(<Factsheet s={{ ...apple, sector: 'National Commercial Banks', cheapness: { label: 'NO_APLICABLE', reason: 'UNSUPPORTED_SECTOR', components: [] } }} />)
  expect(screen.getByText(/Bancos y aseguradoras se valoran con otras métricas/)).toBeInTheDocument()
})
