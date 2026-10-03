import { changeRows, comparePlanRows, describeEvent, fmtR, isClosedState, positionSize, riskReward, snapFromCurrent, snapFromObservation, snapFromT0, stateLabel, stateTone, validatePlan, type PlanDraft } from '../lib/simulation'

const plan: PlanDraft = { entryType: 'ENTRY_ZONE', zoneLow: 98, zoneHigh: 100, stop: 95, targets: [110, 120, 130] }

describe('plan arithmetic (preview of the backend formulas)', () => {
  it('computes risk, stop distance and R:R per target from the entry reference', () => {
    const r = riskReward(plan)
    expect(r.risk).toBe(5)
    expect(r.stopPct).toBeCloseTo(0.05)
    expect(r.rr).toEqual([2, 4, 6])
    expect(r.targetPct[0]).toBeCloseTo(0.1)
  })
  it('uses the single price for LIMIT and MARKET_REFERENCE', () => {
    expect(riskReward({ entryType: 'LIMIT', entry: 50, stop: 45, targets: [60] }).rr).toEqual([2])
  })
  it('gives null R:R when stop is not below the entry or a target is not above it', () => {
    expect(riskReward({ ...plan, stop: 101 }).risk).toBeNull()
    expect(riskReward({ ...plan, targets: [99, 120] }).rr).toEqual([null, 4])
  })
})

describe('plan validation fails closed', () => {
  it('accepts a coherent plan', () => expect(validatePlan(plan, [0.5, 0.5, 0])).toEqual([]))
  it('rejects stop at/above entry, targets below entry or unordered, bad fractions', () => {
    expect(validatePlan({ ...plan, stop: 99 })).toContain('stop must be below the entry')
    expect(validatePlan({ ...plan, targets: [99] })).toContain('target 1 must be above the entry')
    expect(validatePlan({ ...plan, targets: [110, 105] })).toContain('target 2 must be above target 1')
    expect(validatePlan(plan, [0.8, 0.5, 0])).toContain('exit fractions must sum to at most 1')
    expect(validatePlan(plan, [-0.1, 0.5, 0])).toContain('exit fractions must be between 0 and 1')
  })
})

describe('position size', () => {
  it('RISK_BASED = floor(capital at risk / risk per share)', () => {
    expect(positionSize({ mode: 'RISK_BASED', portfolio: 100000, riskPercent: 1 }, 100, 95)).toEqual({ shares: 200, notional: 20000, capitalAtRisk: 1000 })
  })
  it('FIXED_NOTIONAL = floor(notional / entry); refuses sizes below one share', () => {
    expect(positionSize({ mode: 'FIXED_NOTIONAL', notional: 10050 }, 100, 95)?.shares).toBe(100)
    expect(positionSize({ mode: 'FIXED_NOTIONAL', notional: 50 }, 100, 95)).toBeNull()
  })
})

describe('state badges and formatting', () => {
  it('uses neutral wording, never win/loss', () => {
    expect(stateLabel('TP1')).toBe('TARGET 1 REACHED')
    expect(stateLabel('STOPPED')).toBe('STOPPED')
    for (const s of ['TP1', 'STOPPED', 'EXPIRED', 'AMBIGUOUS_INTRABAR']) expect(stateLabel(s)).not.toMatch(/win|loss/i)
    expect(stateTone('STOPPED')).toBe('down')
    expect(stateTone('TP2')).toBe('up')
    expect(stateTone('AMBIGUOUS_INTRABAR')).toBe('warn')
    expect(isClosedState('EXPIRED')).toBe(true)
    expect(isClosedState('ENTERED')).toBe(false)
  })
  it('formats R with a sign', () => {
    expect(fmtR(1.234)).toBe('+1.23R')
    expect(fmtR(-0.5)).toBe('-0.50R')
    expect(fmtR(null)).toBe('—')
  })
})

describe('timeline from the event log', () => {
  const ev = (type: string, payload: Record<string, unknown>) => ({ sequence: 1, type, date: '2017-01-04', payload })
  it('describes events and hides raw bars', () => {
    expect(describeEvent(ev('BAR_PROCESSED', {}))).toBeNull()
    expect(describeEvent(ev('EXIT_FILLED', { fraction: 1, price: 95 }))).toBeNull() // the stop/expiry/manual event already says it
    expect(describeEvent(ev('ENTRY_FILLED', { price: 99, fill_method: 'FIRST_ZONE_TOUCH' }))).toBe('Entry filled @ 99.00 · FIRST_ZONE_TOUCH')
    expect(describeEvent(ev('TP1_TOUCHED', { target: 110, exit_fraction: 0 }))).toContain('position unchanged')
    expect(describeEvent(ev('PARTIAL_EXIT', { fraction: 0.5, price: 110, fill_method: 'TARGET_LIMIT', remaining: 0.5 }))).toContain('remaining 50%')
    expect(describeEvent(ev('AMBIGUOUS_INTRABAR', { kind: 'STOP_AND_TARGET_SAME_BAR' }))).toContain('unknowable')
  })
})

describe('PITQuant vs user plan', () => {
  it('marks only the moved levels', () => {
    const o = { entry_zone: [98, 100] as [number, number], stop_loss: 95, target_1: 110, target_2: 120, expected_r_tp1: 2, expected_r_tp2: 4 }
    const rows = comparePlanRows(o, { ...o, stop_loss: 92, expected_r_tp1: 1.25 })
    expect(rows.filter((r) => r.changed).map((r) => r.label)).toEqual(['Stop', 'Expected R (TP1)'])
  })
})

describe('T0 vs observation vs current', () => {
  const t0 = { decision_at: '2016-06-30T23:00:00Z', price_snapshot: { price: 210 }, support_resistance_snapshot: { supports: [{ lower: 200 }], resistances: [{ upper: 230 }] }, technical_snapshot: { indicators: { rsi14: 54 }, trend: { state: 'UPTREND' }, risk: { atr14_pct: 0.02, vol63: 0.2 }, support_resistance: { supports: [{ lower: 200 }], resistances: [{ upper: 230 }] } }, valuation_snapshot: { current: { pe: 20 } }, fundamental_snapshot: { ttm: { revenue: { value: 1000 } }, latest_period: '2015-12-31' }, market_regime_snapshot: { trend: { state: 'UPTREND' } }, data_quality: { overall: 'OK' } }
  const obs = { horizon_label: 'T+20', observed_at: '2016-07-29T20:00:00Z', payload: { price: 221, return_since_entry: 0.052, benchmark_return: 0.01, technical_snapshot: { indicators: { rsi14: 67 }, trend: { state: 'DOWNTREND' }, risk: { atr14_pct: 0.03, vol63: 0.3 } }, valuation_snapshot: { current: { pe: 21 } }, fundamental_snapshot: { ttm: { revenue: { value: 1100 } }, latest_period: '2016-03-31' }, market_regime_snapshot: { trend: { state: 'DOWNTREND' } }, data_quality_snapshot: { overall: 'WARN' } } }
  it('compares T0 with a RECORDED observation, each side read from its own source', () => {
    const rows = changeRows(snapFromT0(t0), snapFromObservation(obs))
    const by = Object.fromEntries(rows.map((r) => [r.metric, r]))
    expect(by.Price).toMatchObject({ from: 210, to: 221, change: 11 })
    expect(by['RSI 14'].change).toBe(13)
    expect(by['Trend state']).toMatchObject({ from: 'UPTREND', to: 'DOWNTREND', change: null })
    expect(by['Revenue TTM'].change).toBe(100)
    expect(by['Return since entry']).toMatchObject({ from: null, to: 0.052 }) // T0 has no return: the cell stays empty, nothing is invented
    expect(by['Benchmark return'].to).toBe(0.01)
    expect(by['Data quality']).toMatchObject({ from: 'OK', to: 'WARN' })
    expect(by['Nearest support (lower)']).toMatchObject({ from: 200, to: null })
  })
  it('omits a metric that exists on neither side', () => {
    const rows = changeRows(snapFromT0(t0), snapFromObservation(obs))
    expect(rows.find((r) => r.metric === 'FCF TTM')).toBeUndefined()
    expect(rows.find((r) => r.metric === 'P/S')).toBeUndefined()
  })
  it('labels the sources so CURRENT is never presented as known at an earlier date', () => {
    expect(snapFromT0(t0).source).toBe('T0')
    expect(snapFromObservation(obs).label).toBe('T+20 · 2016-07-29')
    const cur = snapFromCurrent({ quote: { price: 250, as_of: '2026-10-03T00:00:00Z' }, technical: { trend: { state: 'UPTREND' } } })
    expect(cur?.source).toBe('CURRENT')
    expect(cur?.label).toMatch(/not historical/)
    expect(snapFromCurrent({ status: 'UNAVAILABLE' })).toBeNull()
    expect(changeRows(snapFromT0(t0), null).every((r) => r.to === null)).toBe(true)
  })
})

describe('PITQuant vs user plan', () => {
  it('marks only the moved levels', () => {
    const o = { entry_zone: [98, 100] as [number, number], stop_loss: 95, target_1: 110, target_2: 120, expected_r_tp1: 2, expected_r_tp2: 4 }
    const rows = comparePlanRows(o, { ...o, stop_loss: 92, expected_r_tp1: 1.25 })
    expect(rows.filter((r) => r.changed).map((r) => r.label)).toEqual(['Stop', 'Expected R (TP1)'])
  })
})
