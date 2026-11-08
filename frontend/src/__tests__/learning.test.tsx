import { expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExamView, LiveProgress, StatusStrip, TodayForecasts, TodoList, type Learning } from '../features/forward/LearningPanel'

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
  exam_series: {
    monthly: [
      { month: '2022-10', n: 10, up_rate: .8, acc_v1: .8, acc_learning: .8, gain_v1: 0, gain_learning: 0 },
      { month: '2022-11', n: 10, up_rate: .4, acc_v1: .4, acc_learning: .4, gain_v1: 0, gain_learning: 0 },
    ],
    calibration: { v1: [], learning: [{ p_mean: .58, up_rate: .56, n: 2000 }] },
  },
  live: { series: { v1: [], learning: [] }, matured: 0, pending: 65, next_maturity: '2026-12-07T21:00:00+00:00' },
  latest: [
    { id: 'a', ticker: 'CAT', p_up: .65, feature_date: '2026-11-06', reference_price: 558, due_at: '2026-12-07T21:00:00Z', horizon: 20, last_step: 0, last_return: null, final_hit: null },
    { id: 'b', ticker: 'KO', p_up: .45, feature_date: '2026-11-06', reference_price: 70, due_at: '2026-12-07T21:00:00Z', horizon: 20, last_step: 5, last_return: .012, final_hit: null },
  ],
  policy_history: [{ policy: 'LEARNING', reason: 'EXAM', decided_at: '2026-11-08T10:00:00Z' }],
  champion: { model_id: 'm', version: '2026-11', family: 'forward-logistic-price-v2-learning' },
  refits: [{ model_id: 'm', version: '2026-11', trained_at: '2026-11-08T10:00:00Z', train_n: 160000, train_target_end: '2026-11-06', tickers: 55 }],
  forward: { pairs: 0, dates: 0 },
}

it('says plainly when there is no edge over "always up"', () => {
  render(<ExamView items={[equity]} />)
  expect(screen.getByText('Sin ventaja demostrada')).toBeInTheDocument()
  expect(screen.getByText(/Acierta lo mismo que decir siempre/)).toBeInTheDocument()
  expect(screen.getByText(/55\.495|55,495/)).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Acierto mensual' })).toBeInTheDocument()
})

it('shows an empty state with the first maturity date before any result exists', () => {
  render(<LiveProgress items={[equity]} />)
  expect(screen.getByText(/Aún no ha vencido ningún pronóstico/)).toBeInTheDocument()
  expect(screen.getByText('0/200 pares · 0/20 fechas')).toBeInTheDocument()
})

it('compares matured forecasts against the always-up reference', () => {
  const live = { ...equity, live: { ...equity.live!, series: { v1: [], learning: [{ date: '2026-12-07', n: 55, accuracy: .6, up_rate: .55, gain: .01 }] } } }
  render(<LiveProgress items={[live]} />)
  expect(screen.getByText('+5.0 pp')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Acierto acumulado EQUITY' })).toBeInTheDocument()
})

it('flags the missing schedule and ticks it once installed', () => {
  const { rerender } = render(<><StatusStrip items={[equity]} activity={{ last_activity: null, schedule_installed: false }} /><TodoList items={[equity]} activity={{ last_activity: null, schedule_installed: false }} /></>)
  expect(screen.getByText('No programado')).toBeInTheDocument()
  expect(screen.getByText('Aprendiendo')).toBeInTheDocument()
  const recent = new Date().toISOString()
  rerender(<><StatusStrip items={[equity]} activity={{ last_activity: recent, schedule_installed: true }} /><TodoList items={[equity]} activity={{ last_activity: recent, schedule_installed: true }} /></>)
  expect(screen.getByText('Sí, cada noche')).toBeInTheDocument()
  expect(screen.getByText('✓')).toBeInTheDocument()
})

it('lists today\'s forecasts with direction and checkpoint progress', () => {
  render(<TodayForecasts items={[equity]} />)
  expect(screen.getByText('65%')).toBeInTheDocument()
  expect(screen.getByText('45%')).toBeInTheDocument()
  expect(screen.getByText('5/20 · 1.2%')).toBeInTheDocument()
})
