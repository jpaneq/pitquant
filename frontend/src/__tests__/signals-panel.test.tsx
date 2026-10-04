import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { UseQueryResult } from '@tanstack/react-query'
import { SignalsPanel } from '../features/analyzer/SignalsPanel'
import type { Signals } from '../api/types'

const base: Signals = {
  retrospective: {
    status: 'OK', label: 'RETROSPECTIVE · RULE_BASED · NOT BACKTEST VALIDATED', markers: [],
    trades: [{ decision_date: '2019-03-01', setup_type: 'PULLBACK', state: 'TP2', entry_date: '2019-03-04', entry_price_chart: 41.5, exit_date: '2019-03-20', realized_return: 0.05, realized_r: 1.4, exits: [], closed: true, stop: 40, target_1: 45 }],
    summary: { n_decisions: 20, n_filled: 1, n_closed: 1, n_not_filled: 3, holdout_skipped: 2, no_plan: 4, skipped_in_position: 10, buy_and_hold_return_same_span: 0.2, span: ['2019-03-04', '2019-03-20'], flags: ['RETROSPECTIVE_NOT_PIT', 'INSUFFICIENT_SAMPLE'] },
  },
  forward: [{ time: '2026-09-30', kind: 'PLAN', origin: 'MANUAL_SIMULATION', price: 100, text: 'plan' }],
  holdout: { sealed: true, note: 'decisions and trades touching the holdout are skipped' },
}
const q = (data?: Signals, state: 'pending' | 'error' | 'success' = 'success') => ({ data, isPending: state === 'pending', isError: state === 'error' }) as unknown as UseQueryResult<Signals>

describe('SignalsPanel', () => {
  it('labels the replay as retrospective and not validated, and quotes no rate on a small sample', () => {
    render(<SignalsPanel q={q(base)} retro />)
    expect(screen.getAllByText(/RETROSPECTIVE/).length).toBeGreaterThan(0)
    expect(screen.getByText(/No es una predicción ni un backtest validado/)).toBeInTheDocument()
    expect(screen.getByText(/Muestra insuficiente/)).toBeInTheDocument()
    expect(screen.queryByText(/Aciertos/)).toBeNull()
    expect(screen.getByText(/holdout omitido 2/)).toBeInTheDocument()
    expect(screen.getByText('2019-03-04 @ 41.50')).toBeInTheDocument()
  })
  it('shows forward paper trades separately and hides the replay table when only they are on', () => {
    render(<SignalsPanel q={q(base)} retro={false} />)
    expect(screen.getByText(/Pruebas paper reales en el gráfico: 1/)).toBeInTheDocument()
    expect(screen.queryByText('Decisión')).toBeNull()
  })
  it('handles loading and error states', () => {
    const { rerender } = render(<SignalsPanel q={q(undefined, 'pending')} retro />)
    expect(screen.getByText(/Calculando/)).toBeInTheDocument()
    rerender(<SignalsPanel q={q(undefined, 'error')} retro />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})
