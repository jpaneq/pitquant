import { comparePlanRows, describeEvent, fmtR, isClosedState, positionSize, riskReward, stateLabel, stateTone, validatePlan, type PlanDraft } from '../lib/simulation'

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

describe('T0 vs current', () => {
  it('reads both sides from their own source and never mixes them', async () => {
    const { changeRows } = await import('../lib/simulation')
    const t0 = { price_snapshot: { price: 210 }, technical_snapshot: { indicators: { rsi14: 54 }, trend: { state: 'UPTREND' } }, valuation_snapshot: { current: { pe: 20 } } }
    const now = { quote: { price: 221 }, technical: { indicators: { rsi14: 67 }, trend: { state: 'DOWNTREND' } }, valuation: { current: { pe: 21 } } }
    const rows = changeRows(t0, now)
    expect(rows.find((r) => r.metric === 'Price')).toMatchObject({ t0: 210, current: 221, change: 11 })
    expect(rows.find((r) => r.metric === 'RSI 14')?.change).toBe(13)
    expect(rows.find((r) => r.metric === 'Trend state')).toMatchObject({ t0: 'UPTREND', current: 'DOWNTREND', change: null })
    expect(rows.find((r) => r.metric === 'Market cap')).toMatchObject({ t0: null, current: null })
    expect(changeRows(t0, undefined).every((r) => r.current === null)).toBe(true)
  })
})
