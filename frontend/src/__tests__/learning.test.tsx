import { expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LearningPanel, type Learning } from '../features/forward/LearningPanel'

const interval = (mean: number, low90: number, high90: number) => ({ mean, low90, high90, clusters: 49 })
const arm = (accuracy: number, logloss: number, verdict: string) => ({ n: 100, accuracy, brier: .24, logloss, mean_p_up: .6, gain_vs_base_rate: interval(.001, -.001, .003), signal_verdict: verdict })
const equity: Learning = {
  market: 'EQUITY',
  exam: {
    window: { first_decision: '2022-10-03', last_decision: '2026-10-09', last_target: '2026-11-06' },
    n: 55495, months: 49, tickers: ['AAPL', 'MSFT'], base_rate_p: .614,
    always_up_accuracy: .5702, momentum_accuracy: .4962, base_rate_logloss: .6873,
    arms: { A_FROZEN_V1: arm(.5704, .6876, 'NO_EVIDENCE'), B_LEARNING: arm(.5699, .6859, 'NO_EVIDENCE') },
    learning_minus_frozen_gain: interval(.0017, .0004, .0031), policy: 'LEARNING',
  },
  policy_history: [{ policy: 'LEARNING', reason: 'EXAM', decided_at: '2026-11-08T10:00:00Z' }],
  champion: { model_id: 'm', version: '2026-11', family: 'forward-logistic-price-v2-learning' },
  refits: [{ model_id: 'm', version: '2026-11', trained_at: '2026-11-08T10:00:00Z', train_n: 160000, train_target_end: '2026-11-06', tickers: 55 }],
  forward: { pairs: 0, dates: 0 },
}

it('shows the exam honestly: no signal is reported as no signal', () => {
  render(<LearningPanel items={[equity, { ...equity, market: 'BTC', exam: null, refits: [], policy_history: [], champion: null }]} />)
  expect(screen.getByText('Aprendiendo')).toBeInTheDocument()
  expect(screen.getAllByText(/Sin evidencia de señal/)).toHaveLength(2)
  expect(screen.getByText(/55,495|55\.495/)).toBeInTheDocument()
  expect(screen.getByText(/Examen pendiente/)).toBeInTheDocument()
  expect(screen.getAllByText(/≥200 pares/)).toHaveLength(2)
})

it('renders nothing before any exam or refit exists', () => {
  const { container } = render(<LearningPanel items={[{ ...equity, exam: null, refits: [] }]} />)
  expect(container).toBeEmptyDOMElement()
})
