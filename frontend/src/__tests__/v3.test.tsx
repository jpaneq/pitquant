import { expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { V3Panel, type V3 } from '../features/forward/V3Panel'

const iv = (mean: number, low90: number, high90: number) => ({ mean, low90, high90 })
const arm = (accuracy: number, logloss: number, verdict: string) => ({ accuracy, logloss, signal_verdict: verdict, gain_vs_base_rate: iv(0, -.001, .001) })
const features = ['fund_operating_margin', 'fund_roa', 'fund_revenue_yoy', 'fund_debt_to_assets', 'val_earnings_yield', 'val_fcf_yield']
const base: V3 = { family: 'forward-logistic-pricefund-v3', features, exam: null, refits: [], forward: { pairs: 0, dates: 0 } }

it('explains each company indicator and waits for the exam', () => {
  render(<V3Panel v3={base} />)
  expect(screen.getByText(/Margen operativo/)).toBeInTheDocument()
  expect(screen.getByText(/beneficio \/ precio/)).toBeInTheDocument()
  expect(screen.getByText(/Examen pendiente/)).toBeInTheDocument()
})

it('reports a v3 that does not beat price-only plainly', () => {
  const exam = {
    window: { first_decision: '2022-10-03', last_decision: '2026-10-09' }, n: 50000, months: 49, tickers: ['AAPL'], always_up_accuracy: .57,
    fundamental_coverage: Object.fromEntries(features.map(f => [f, .8])),
    arms: { B_PRICE_V2: arm(.57, .686, 'NO_EVIDENCE'), C_PRICE_FUND_V3: arm(.565, .688, 'NO_EVIDENCE') },
    v3_minus_v2_gain: iv(-.002, -.004, 0), policy: 'LEARNING',
    monthly: [{ month: '2022-10', n: 10, up_rate: .6, acc_v2: .6, acc_v3: .58 }, { month: '2022-11', n: 10, up_rate: .5, acc_v2: .5, acc_v3: .52 }],
  }
  render(<V3Panel v3={{ ...base, exam }} />)
  expect(screen.getByText('No mejora')).toBeInTheDocument()
  expect(screen.getByText(/El campeón no cambia/)).toBeInTheDocument()
  expect(screen.getAllByText(/disponible en el 80%/)).toHaveLength(6)
})
