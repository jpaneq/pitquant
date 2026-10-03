import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { Summary } from '../api/types'
import { InsightsPage } from '../features/simulations/InsightsPage'
import { PlanComparison } from '../features/simulations/PlanComparison'
import { PostMortemPanel } from '../features/simulations/PostMortemPanel'
import { SimulateTrade } from '../features/simulations/SimulateTrade'
import { SimulationDetail } from '../features/simulations/SimulationDetail'
import { SimulationsPage } from '../features/simulations/SimulationsPage'
import type { Comparison, SimDetail } from '../features/simulations/types'

vi.mock('../features/simulations/SimChart', () => ({ SimChart: ({ bars }: { bars: unknown[] }) => <div data-testid="sim-chart-stub">{bars.length} bars</div> }))

const json = (b: unknown) => Promise.resolve(new Response(JSON.stringify(b), { status: 200, headers: { 'Content-Type': 'application/json' } }))
const wrap = (ui: React.ReactNode, path = '/') => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter></QueryClientProvider>)
afterEach(() => vi.restoreAllMocks())

const summary = { quote: { status: 'OK', price: 100 }, summary: { trend: 'UPTREND', valuation: 'FAIR', data_quality: 'OK' }, simulation: { enabled: true, reason: null } } as unknown as Summary

describe('create form (wizard)', () => {
  const open = () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({ status: 'NO_VALID_SETUP', setups: [] }))
    wrap(<SimulateTrade sec="SYNX" summary={summary} />)
    fireEvent.click(screen.getByTestId('simulate-open'))
    fireEvent.click(screen.getByTestId('wizard-next'))
    fireEvent.click(screen.getByTestId('wizard-next'))
  }
  it('previews stop distance, R:R and position size, and validates before submission', () => {
    open()
    const set = (l: string, v: string) => fireEvent.change(screen.getByLabelText(l, { exact: true }), { target: { value: v } })
    expect(screen.getByTestId('simulate-submit')).toBeDisabled() // nothing filled: fails closed
    set('Stop loss', '95'); set('Target 1', '110'); set('Target 2', '120')
    fireEvent.click(screen.getByText('Back')); set('Entry zone low', '98'); set('Entry zone high', '100'); fireEvent.click(screen.getByTestId('wizard-next'))
    expect(screen.getByTestId('rr-preview')).toHaveTextContent('Stop distance 5.00% · R:R TP1 +2.00R · TP2 +4.00R')
    expect(screen.getByTestId('size-preview')).toHaveTextContent('200 shares · notional 20,000.00 · capital at risk 1,000.00')
    expect(screen.getByTestId('simulate-submit')).toBeEnabled()
  })
  it('refuses a stop above the entry and unordered fractions with a visible reason', () => {
    open()
    fireEvent.click(screen.getByText('Back'))
    fireEvent.change(screen.getByLabelText('Entry zone low', { exact: true }), { target: { value: '98' } })
    fireEvent.change(screen.getByLabelText('Entry zone high', { exact: true }), { target: { value: '100' } })
    fireEvent.click(screen.getByTestId('wizard-next'))
    fireEvent.change(screen.getByLabelText('Stop loss', { exact: true }), { target: { value: '101' } })
    fireEvent.change(screen.getByLabelText('Target 1', { exact: true }), { target: { value: '110' } })
    expect(screen.getByTestId('plan-errors')).toHaveTextContent(/stop/i)
    expect(screen.getByTestId('simulate-submit')).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Exit policy'), { target: { value: 'PARTIAL_FRACTIONS' } })
    fireEvent.change(screen.getByLabelText('TP1 fraction'), { target: { value: '0.8' } })
    fireEvent.change(screen.getByLabelText('TP2 fraction'), { target: { value: '0.5' } })
    expect(screen.getByTestId('plan-errors')).toHaveTextContent('exit fractions must sum to at most 1')
  })
})

const row = (over: object) => ({ simulation_id: 'a1', created_at: '2017-01-02T00:00:00Z', security_id: 's', security: 'SYN SIM CO (FIXTURE)', decision_at: '2016-12-30', plan_origin: 'USER_DEFINED', mode: 'MANUAL_SIMULATION', setup_type: 'USER_DEFINED', state: 'STOPPED', outcome: { is_closed: true, entry_date: '2017-01-04', entry_price: 99, realized_r: -1, realized_return: -0.04, holding_period: 3 }, mae_pct: -0.05, mfe_pct: 0.03, entry_zone: [98, 100], stop_loss: 95, target_1: 110, target_2: null, banner: 'x', ...over })
describe('dashboard', () => {
  it('shows neutral state badges (never win/loss), N, filters and the insufficient-sample note', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((u) => json(String(u).includes('/summary') ? { banner: 'x', groups: { OPEN: 0, STOPPED: 1, CLOSED: 1 }, evidence: { n_simulations: 1, n_closed: 1, n_entered_closed: 1, by_state: {}, stats_available: false, min_n: 10, note: '' } } : [row({}), row({ simulation_id: 'a2', state: 'TP1', plan_origin: 'PITQUANT' })]))
    wrap(<SimulationsPage />)
    const table = await screen.findByTestId('sim-table')
    expect(within(table).getByText('STOPPED')).toBeInTheDocument()
    expect(within(table).getByText('TARGET 1 REACHED')).toBeInTheDocument()
    expect(table.textContent ?? '').not.toMatch(/\bwin\b|\bloss\b/i)
    expect(screen.getByText('PREDICTION ENGINE NOT YET VALIDATED')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Filter origin'), { target: { value: 'PITQUANT' } })
    expect(within(screen.getByTestId('sim-table')).queryByText('STOPPED')).toBeNull()
    expect(screen.getByTestId('r-curve')).toHaveAttribute('aria-label', 'Cumulative realised R over 2 trades')
  })
})

const detail = (over: object = {}): SimDetail => ({
  banner: 'x',
  simulation: { simulation_id: 'abcdef012345', stop_loss: 95, target_1: 110, target_2: 120, target_3_optional: null, entry_zone_low: 98, entry_zone_high: 100, invalidation_level: null, plan_origin: 'USER_DEFINED', decision_at: '2016-12-30T23:00:00Z', created_at: '2026-10-03T00:00:00Z', entry_type: 'ENTRY_ZONE', prediction_status: 'NOT_YET_VALIDATED', rules_version: 'trade-plan-v0.1', analyzer_version: 'analyzer-v0', feature_version: 'v0.2', support_resistance_snapshot: {}, original_pitquant_plan: null, final_simulated_plan: {}, trade_plan_snapshot: { label: 'RULE_BASED · NOT YET BACKTEST VALIDATED' }, price_snapshot: { price: 100 }, fundamental_snapshot: {}, technical_snapshot: {}, valuation_snapshot: {}, data_quality: {}, snapshot_hash: 'f'.repeat(64) },
  outcomes: [{ outcome_id: 'o', evaluated_at: 'now', state: 'STOPPED', is_closed: true, entry_date: '2017-01-04', entry_price: 99, exit_date: '2017-01-09', realized_return: -0.0404, excess_return_vs_benchmark: null, realized_r: -1, mfe: 0.05, mae: 0.05, max_drawdown: 0.08, days_to_entry: 5, days_to_stop: 10, days_to_tp1: 7, days_to_tp2: null, holding_period: 5, prediction_direction_correct: null, trade_plan_execution_correct: null, execution_outcome: 'STOP_HIT', prediction_outcome: null, timeline: [], details: { metrics_extra: { mae_pct: -0.0505, mfe_pct: 0.0505, mae_r: -1.25, mfe_r: 1.25 }, targets_touched: [1], position_remaining: 0, fills: { entry: { price: 99, method: 'FIRST_ZONE_TOUCH' } } } }],
  observations: [], postmortems: [], bars: [{ date: '2017-01-03', open: 100, high: 101, low: 99, close: 100 }], analysis_now: {},
  events: [{ sequence: 0, type: 'SIMULATION_CREATED', date: '2016-12-30', payload: {} }, { sequence: 1, type: 'BAR_PROCESSED', date: '2017-01-03', payload: {} }, { sequence: 2, type: 'ENTRY_FILLED', date: '2017-01-04', payload: { price: 99, fill_method: 'FIRST_ZONE_TOUCH' } }, { sequence: 3, type: 'TP1_TOUCHED', date: '2017-01-06', payload: { target: 110, exit_fraction: 0 } }, { sequence: 4, type: 'STOP_TRIGGERED', date: '2017-01-09', payload: { price: 95, fill_method: 'STOP_LEVEL' } }],
  comparison: { plan_origin: 'USER_DEFINED', pitquant_original: null, user_plan: null, real: null, counterfactual: null },
  explain: { snapshot_hash: 'f'.repeat(64), snapshot_verified: true, provenance: { price: { source: 'SYN' } }, versions: { analyzer: 'analyzer-v0', prediction_status: 'NOT_YET_VALIDATED' }, exit_policy: 'TRACK_TARGETS_ONLY', events: 5, banner: 'x' },
  plan_levels: { exit_policy: 'TRACK_TARGETS_ONLY', risk_reward: null, sizing: null },
  ...over,
})
describe('simulation detail', () => {
  const mount = () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json(detail()))
    wrap(<Routes><Route path="/simulations/:id" element={<SimulationDetail />} /></Routes>, '/simulations/abcdef012345')
  }
  it('builds the timeline from the event log (no raw bars), shows MAE/MFE/R and neutral state wording', async () => {
    mount()
    const tl = await screen.findByTestId('sim-timeline')
    expect(within(tl).getAllByRole('listitem')).toHaveLength(4) // BAR_PROCESSED is not shown
    expect(tl).toHaveTextContent('Entry filled @ 99.00 · FIRST_ZONE_TOUCH')
    expect(tl).toHaveTextContent('position unchanged (track targets only)')
    const perf = screen.getByTestId('sim-performance')
    expect(perf).toHaveTextContent('-1.25R') // MAE in R
    expect(perf).toHaveTextContent('+1.25R') // MFE in R
    expect(screen.getByTestId('sim-state')).toHaveTextContent('STOPPED')
    expect(perf).toHaveTextContent('n/a (NOT_YET_VALIDATED)')
  })
  it('keeps the T0 snapshot tab and the provenance tab (explain) reachable', async () => {
    mount()
    expect(await screen.findByTestId('tab-t0')).toHaveTextContent('never changes after creation')
    fireEvent.click(screen.getByText('Provenance'))
    expect(screen.getByTestId('tab-provenance')).toHaveTextContent('verified: true')
    fireEvent.click(screen.getByText('Changes'))
    expect(screen.getByTestId('tab-changes')).toBeInTheDocument()
  })
})

describe('plan comparison', () => {
  const o = { entry_zone: [98, 100] as [number, number], stop_loss: 95, target_1: 110, target_2: 120, expected_r_tp1: 2, expected_r_tp2: 4 }
  it('marks the levels the user moved and labels the counterfactual as not real', () => {
    const c: Comparison = { plan_origin: 'USER_MODIFIED', pitquant_original: o, user_plan: { ...o, stop_loss: 92, expected_r_tp1: 1.25 }, real: { state: 'STOPPED', triggered: true, entry_price: 99, realized_r: -1, mae_pct: -0.05, mfe_pct: 0.03, targets_touched: [], label: 'REAL SIMULATION' }, counterfactual: { state: 'ENTERED', triggered: true, entry_price: 99, realized_r: 0.4, mae_pct: -0.05, mfe_pct: 0.03, targets_touched: [1], last_bar: '2017-01-09', label: 'COUNTERFACTUAL — NOT THE REAL OUTCOME' } }
    wrap(<PlanComparison c={c} />)
    expect(screen.getByText('COUNTERFACTUAL')).toBeInTheDocument()
    expect(screen.getByTestId('counterfactual-line')).toHaveTextContent('ENTERED')
    expect(document.querySelectorAll('[data-changed="true"]')).toHaveLength(2) // the stop and the expected R of TP1
  })
  it('says there is nothing to compare for a PITQuant plan', () => {
    wrap(<PlanComparison c={{ plan_origin: 'PITQUANT', pitquant_original: o, user_plan: o, real: null, counterfactual: null }} />)
    expect(screen.getByTestId('plan-same')).toBeInTheDocument()
  })
})

describe('post-mortem form', () => {
  it('is locked while the simulation is open', () => {
    wrap(<PostMortemPanel id="x" closed={false} />)
    expect(screen.getByTestId('pm-open')).toHaveTextContent('No automatic verdict')
  })
  it('shows facts first, needs a human classifier, and creates an UNTESTED hypothesis', async () => {
    const calls: string[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation((u, init) => {
      calls.push(`${init?.method ?? 'GET'} ${String(u)}`)
      if (String(u).endsWith('/hypothesis')) return json({ status: 'UNTESTED' })
      return json({ facts: { prediction_outcome: null, prediction_status: 'NOT_YET_VALIDATED', execution_outcome: 'STOP_HIT', state: 'STOPPED', entry_quality: { entry_method: 'FIRST_ZONE_TOUCH' }, stop_quality: { stop_distance_atr: 0.7 }, target_quality: {}, metrics: { realized_r: -1, mae_pct: -0.05, mfe_pct: 0.03 }, diagnostic_flags: [{ flag: 'STOP_HIT_BEFORE_LATER_TP', definition: 'stopped, then a later bar reached target 1' }], note: 'facts only' }, classifications: [] })
    })
    wrap(<PostMortemPanel id="x" closed />)
    expect(await screen.findByTestId('postmortem')).toHaveTextContent('n/a (NOT_YET_VALIDATED)')
    expect(screen.getByTestId('diagnostic-flags')).toHaveTextContent('STOP_HIT_BEFORE_LATER_TP')
    expect(screen.getAllByText('STOP_TOO_TIGHT', { selector: 'option' }).length).toBeGreaterThan(0) // a choice for the HUMAN; never inferred from the 0.7 ATR
    expect(screen.getByTestId('pm-save')).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Classified by'), { target: { value: 'tester' } })
    expect(screen.getByTestId('pm-save')).toBeEnabled()
    fireEvent.change(screen.getByLabelText('Hypothesis statement'), { target: { value: 'tight stops stop out' } })
    fireEvent.click(screen.getByTestId('hyp-create'))
    expect(await screen.findByTestId('hyp-created')).toHaveTextContent('UNTESTED')
    expect(calls.some((c) => c.startsWith('POST') && c.endsWith('/hypothesis'))).toBe(true)
  })
})

describe('insights', () => {
  it('shows INSUFFICIENT SAMPLE instead of numbers for a small segment and never recommends', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({ by: 'setup_type', min_n: 10, note: 'descriptive statistics of paper trades: no recommendation, never a training label', available_segmentations: ['setup_type', 'origin'], segments: [{ segment: 'BASE_PULLBACK', n: 4, n_entered: 3, sample: 'INSUFFICIENT_SAMPLE' }, { segment: 'USER_DEFINED', n: 20, n_entered: 14, sample: 'OK', return: { mean: 0.02, median: 0.01 }, r: { mean: 0.3, median: 0.1 }, mae_pct: { mean: -0.03, median: -0.02 }, mfe_pct: { mean: 0.05, median: 0.04 }, stop_rate: 0.4, target_touch_rate: 0.5, expiration_rate: 0.1, ambiguous_rate: 0 }] }))
    wrap(<InsightsPage />)
    const t = await screen.findByTestId('insights-table')
    const small = t.querySelector('[data-sample="INSUFFICIENT_SAMPLE"]') as HTMLElement
    expect(small).toHaveTextContent('INSUFFICIENT SAMPLE')
    expect(small.textContent).not.toMatch(/%/)
    expect(t.querySelector('[data-sample="OK"]')).toHaveTextContent('+0.30R')
  })
})

describe('historical observations, changes and provenance (ADR-0037)', () => {
  const obs = (id: string, label: string, bar: string, over: object = {}) => ({ observation_id: id, observed_at: `${bar}T20:00:00Z`, kind: 'PERIODIC', horizon_label: label, source_bar_date: bar, observation_schema_version: 1, analyzer_version: 'analyzer-v0', feature_version: 'v0.2', payload: { price: 105, return_since_entry: 0.05, benchmark_return: 0.01, technical_snapshot: { trend: { state: 'DOWNTREND' }, indicators: { rsi14: 61 } }, valuation_snapshot: {}, fundamental_snapshot: {}, market_regime_snapshot: { trend: { state: 'DOWNTREND' } }, data_quality_snapshot: { overall: 'OK' }, ...over }, comparison: undefined })
  const withObs = () => detail({
    simulation: { ...detail().simulation, simulation_engine_version: 'v1', technical_snapshot: { trend: { state: 'UPTREND' }, indicators: { rsi14: 50 } }, market_regime_snapshot: { trend: { state: 'UPTREND' } }, data_quality: { overall: 'OK' } },
    observations: [obs('o1', 'T+1', '2017-01-03'), obs('o2', 'T+5', '2017-01-09', { price: 110 })],
    thesis_evolution: [{ observation_id: 'o1', label: 'T+1', bar_date: '2017-01-03', observed_at: '2017-01-03T20:00:00Z', observation_schema_version: 1, analyzer_version: 'analyzer-v0', feature_version: 'v0.2', facts: [] }, { observation_id: 'o2', label: 'T+5', bar_date: '2017-01-09', observed_at: '2017-01-09T20:00:00Z', observation_schema_version: 1, analyzer_version: 'analyzer-v0', feature_version: 'v0.2', facts: [{ fact: 'trend_changed', definition: 'the trend state differs from T0', t0: 'UPTREND', observed: 'DOWNTREND', source_observation_id: 'o2' }] }],
    current: { quote: { price: 250, as_of: '2026-10-03T00:00:00Z' }, technical: { trend: { state: 'UPTREND' } } },
    explain: { snapshot_hash: 'f'.repeat(64), snapshot_verified: true, provenance: {}, versions: { simulation_engine: 'v1', event_schema: '1' }, exit_policy: 'TRACK_TARGETS_ONLY', events: 5, banner: 'x' },
  } as unknown as Partial<SimDetail>)
  const mount = (d: SimDetail) => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json(d))
    wrap(<Routes><Route path="/simulations/:id" element={<SimulationDetail />} /></Routes>, '/simulations/abcdef012345')
  }
  it('shows the pinned engine in the header and in Provenance (engine and event schema)', async () => {
    mount(withObs())
    expect(await screen.findByTestId('engine-badge')).toHaveTextContent('Engine v1')
    fireEvent.click(screen.getByText('Provenance'))
    expect(screen.getByTestId('engine-provenance')).toHaveTextContent('Simulation Engine')
    expect(screen.getByTestId('engine-provenance')).toHaveTextContent('v1')
    expect(screen.getByTestId('engine-provenance')).toHaveTextContent('Event Schema')
  })
  it('lists the recorded observations with their versions and descriptive facts (never causes)', async () => {
    mount(withObs())
    await screen.findByTestId('engine-badge')
    fireEvent.click(screen.getByText('Recorded observations'))
    const rows = screen.getAllByTestId('obs-row')
    expect(rows).toHaveLength(2)
    expect(rows[1]).toHaveTextContent('T+5')
    expect(rows[1]).toHaveTextContent('analyzer analyzer-v0')
    expect(rows[1]).toHaveTextContent('trend_changed')
    expect(screen.getByTestId('tab-observations')).toHaveTextContent('never recomputed')
  })
  it('says there is no observation yet instead of inventing one', async () => {
    mount(detail())
    await screen.findByTestId('sim-header')
    fireEvent.click(screen.getByText('Recorded observations'))
    expect(screen.getByTestId('obs-empty')).toBeInTheDocument()
  })
  it('Changes compares T0 with the latest RECORDED observation by default and lets the user pick another pair', async () => {
    mount(withObs())
    await screen.findByTestId('engine-badge')
    fireEvent.click(screen.getByText('Changes'))
    expect(screen.getByTestId('to-source')).toHaveTextContent('RECORDED — historical')
    const t = screen.getByTestId('tab-changes')
    expect(t).toHaveTextContent('Price') // T0 100 -> 110 (latest = T+5)
    expect(t.textContent).toMatch(/110\.00/)
    expect(t).toHaveTextContent('Return since entry')
    expect(screen.getByTestId('thesis-facts')).toHaveTextContent('trend_changed')
    expect(screen.getByTestId('thesis-facts')).toHaveTextContent('not a cause')
    fireEvent.change(screen.getByLabelText('Changes to'), { target: { value: 'o1' } })
    expect(screen.getByTestId('tab-changes').textContent).toMatch(/105\.00/)
    expect(screen.getByTestId('thesis-facts')).toHaveTextContent('No descriptive fact')
  })
  it('CURRENT is clearly labelled as not historical, and the Current analysis tab says it was not known earlier', async () => {
    mount(withObs())
    await screen.findByTestId('engine-badge')
    fireEvent.click(screen.getByText('Changes'))
    fireEvent.change(screen.getByLabelText('Changes to'), { target: { value: 'CURRENT' } })
    expect(screen.getByTestId('to-source')).toHaveTextContent('CURRENT — not known on any earlier date')
    fireEvent.click(screen.getByText('Current analysis'))
    expect(screen.getByTestId('tab-current')).toHaveTextContent('NOT known on any earlier date')
  })
  it('Changes omits metrics that exist on neither side', async () => {
    mount(withObs())
    await screen.findByTestId('engine-badge')
    fireEvent.click(screen.getByText('Changes'))
    const t = screen.getByTestId('tab-changes')
    expect(t).not.toHaveTextContent('FCF TTM')
    expect(t).not.toHaveTextContent('P/S')
  })
})

describe('insights by engine', () => {
  it('warns when segments mix engines and shows N per engine', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({ by: 'origin', min_n: 10, note: 'descriptive', available_segmentations: ['simulation_engine_version', 'origin'], engines: { v1: 12, v2: 3 }, mixed_engines: true, segments: [] }))
    wrap(<InsightsPage />)
    expect(await screen.findByTestId('mixed-engines')).toHaveTextContent('DIFFERENT simulation engines')
    expect(screen.getByTestId('engines-note')).toHaveTextContent('engine v1 N=12')
    expect(screen.getByTestId('engines-note')).toHaveTextContent('engine v2 N=3')
  })
  it('shows no warning when segmenting by engine', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({ by: 'simulation_engine_version', min_n: 10, note: 'descriptive', available_segmentations: ['simulation_engine_version'], engines: { v1: 12 }, mixed_engines: false, segments: [{ segment: 'engine v1', n: 12, n_entered: 4, sample: 'INSUFFICIENT_SAMPLE' }] }))
    wrap(<InsightsPage />)
    expect(await screen.findByText('engine v1')).toBeInTheDocument()
    expect(screen.queryByTestId('mixed-engines')).toBeNull()
  })
})
