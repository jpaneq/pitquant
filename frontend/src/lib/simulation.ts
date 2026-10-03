// Pure display/validation helpers for the Simulation Lab. The authoritative calculations (fills, R, MAE/MFE) live in the backend engine;
// these only PREVIEW the plan arithmetic before submission (same formulas as the spec) and format what the API returns.
export type PlanDraft = { entryType: 'MARKET_REFERENCE' | 'LIMIT' | 'ENTRY_ZONE'; entry?: number; zoneLow?: number; zoneHigh?: number; stop?: number; targets: (number | null | undefined)[] }

/** The reference entry used for the preview: the single price, or the top of the zone (the conservative fill). */
export function entryReference(p: PlanDraft): number | null {
  const v = p.entryType === 'ENTRY_ZONE' ? p.zoneHigh : p.entry
  return v !== undefined && Number.isFinite(v) ? (v as number) : null
}

export function riskReward(p: PlanDraft): { risk: number | null; stopPct: number | null; rr: (number | null)[]; targetPct: (number | null)[] } {
  const e = entryReference(p)
  if (e === null || p.stop === undefined || !Number.isFinite(p.stop) || e - p.stop <= 0) return { risk: null, stopPct: null, rr: p.targets.map(() => null), targetPct: p.targets.map(() => null) }
  const risk = e - p.stop
  return { risk, stopPct: risk / e, rr: p.targets.map((t) => (t && t > e ? (t - e) / risk : null)), targetPct: p.targets.map((t) => (t && t > e ? t / e - 1 : null)) }
}

/** Fail closed, same rules as the engine: stop < entry (<= zone high) < target_1 < target_2 < target_3; fractions in [0,1] summing to <= 1. */
export function validatePlan(p: PlanDraft, fractions?: number[]): string[] {
  const errs: string[] = []
  const e = entryReference(p)
  if (e === null) errs.push('entry price required')
  if (p.entryType === 'ENTRY_ZONE' && p.zoneLow !== undefined && p.zoneHigh !== undefined && p.zoneLow > p.zoneHigh) errs.push('zone low must not exceed zone high')
  if (p.stop === undefined || !Number.isFinite(p.stop)) errs.push('stop loss required')
  else if (e !== null && p.stop >= (p.entryType === 'ENTRY_ZONE' ? (p.zoneLow ?? e) : e)) errs.push('stop must be below the entry')
  const ts = p.targets.filter((t): t is number => typeof t === 'number' && Number.isFinite(t))
  if (ts.length === 0) errs.push('target 1 required')
  else if (e !== null && ts[0] <= e) errs.push('target 1 must be above the entry')
  for (let i = 1; i < ts.length; i++) if (ts[i] <= ts[i - 1]) errs.push(`target ${i + 1} must be above target ${i}`)
  if (fractions) {
    if (fractions.some((f) => f < 0 || f > 1)) errs.push('exit fractions must be between 0 and 1')
    if (fractions.reduce((a, b) => a + b, 0) > 1 + 1e-9) errs.push('exit fractions must sum to at most 1')
  }
  return errs
}

export type Sizing = { mode: 'FIXED_NOTIONAL'; notional: number } | { mode: 'RISK_BASED'; portfolio: number; riskPercent: number }
/** shares = floor(capital_at_risk / (entry - stop)) for RISK_BASED, floor(notional / entry) for FIXED_NOTIONAL (equities: whole shares). */
export function positionSize(s: Sizing, entry: number, stop: number): { shares: number; notional: number; capitalAtRisk: number } | null {
  const risk = entry - stop
  if (!(entry > 0) || !(risk > 0)) return null
  const shares = s.mode === 'FIXED_NOTIONAL' ? Math.floor(s.notional / entry) : Math.floor((s.portfolio * (s.riskPercent / 100)) / risk)
  if (!(shares >= 1)) return null
  return { shares, notional: shares * entry, capitalAtRisk: shares * risk }
}

export const fmtR = (x: number | null | undefined): string => (x === null || x === undefined || Number.isNaN(x) ? '—' : `${x > 0 ? '+' : ''}${x.toFixed(2)}R`)

const CLOSED = new Set(['TP1', 'TP2', 'TP3', 'STOPPED', 'INVALIDATED', 'EXPIRED', 'CLOSED_MANUAL', 'AMBIGUOUS_INTRABAR', 'CANCELLED'])
/** Badge tone for a state. Neutral wording only: no WIN / LOSS. */
export function stateTone(state: string): 'neutral' | 'up' | 'down' | 'warn' | 'info' {
  if (state === 'STOPPED' || state === 'INVALIDATED') return 'down'
  if (state.startsWith('TP')) return 'up'
  if (state === 'AMBIGUOUS_INTRABAR') return 'warn'
  if (state === 'ENTERED' || state === 'PARTIAL_TP') return 'info'
  return 'neutral'
}
export const stateLabel = (state: string): string => ({ TP1: 'TARGET 1 REACHED', TP2: 'TARGET 2 REACHED', TP3: 'TARGET 3 REACHED', PARTIAL_TP: 'PARTIAL EXIT', WAITING_ENTRY: 'WAITING ENTRY', CLOSED_MANUAL: 'CLOSED (MANUAL)', AMBIGUOUS_INTRABAR: 'AMBIGUOUS INTRABAR' })[state] ?? state
export const isClosedState = (state: string): boolean => CLOSED.has(state)

export type SimEvent = { sequence: number; type: string; date: string; payload: Record<string, unknown>; engine_version?: string }
const n = (v: unknown, d = 2) => (typeof v === 'number' ? v.toFixed(d) : '—')
/** One readable line per event of the log (the timeline is built from the event store, never from mutable state). BAR_PROCESSED is not shown. */
export function describeEvent(e: SimEvent): string | null {
  const p = e.payload
  switch (e.type) {
    case 'SIMULATION_CREATED': return 'Simulation created (paper trade, T0 snapshot frozen)'
    case 'ENTRY_TRIGGERED': return `Entry level reached (${n(p.level)})`
    case 'ENTRY_FILLED': return `Entry filled @ ${n(p.price)} · ${String(p.fill_method)}`
    case 'TP1_TOUCHED': case 'TP2_TOUCHED': case 'TP3_TOUCHED': return `${e.type.slice(0, 3)} touched @ ${n(p.target)}${Number(p.exit_fraction) > 0 ? '' : ' · position unchanged (track targets only)'}`
    case 'PARTIAL_EXIT': return `Partial exit ${(Number(p.fraction) * 100).toFixed(0)}% @ ${n(p.price)} · ${String(p.fill_method)} · remaining ${(Number(p.remaining) * 100).toFixed(0)}%`
    case 'STOP_GAP': return `Gap through the stop: opened ${n(p.open)} below ${n(p.stop)}`
    case 'STOP_TRIGGERED': return `Stopped @ ${n(p.price)} · ${String(p.fill_method)}`
    case 'EXIT_FILLED': return null // redundant with the specific event that caused the exit (stop, expiry, invalidation, manual close, target)
    case 'INVALIDATED': return `Thesis invalidated: ${String(p.reason ?? '')}`
    case 'EXPIRED': return `Expired: ${String(p.reason ?? 'horizon reached')}`
    case 'MANUAL_CLOSE': return `Closed manually @ ${n(p.price)}`
    case 'CANCELLED': return 'Cancelled before the entry'
    case 'AMBIGUOUS_INTRABAR': return `Ambiguous intrabar (${String(p.kind)}): order unknowable with daily bars`
    case 'OBSERVATION_RECORDED': return `${String(p.horizon)} observation · close ${n(p.close)}${typeof p.return_since_entry === 'number' ? ` · ${(p.return_since_entry * 100).toFixed(1)}% since entry` : ''}`
    default: return null
  }
}

export type PlanView = { entry_zone: [number | null, number | null]; stop_loss: number | null; target_1: number | null; target_2: number | null; expected_r_tp1: number | null; expected_r_tp2: number | null } | null
/** Rows for the PITQuant-vs-user comparison; ``changed`` marks the levels the user moved. */
export function comparePlanRows(original: PlanView, user: PlanView): { label: string; original: number | null; user: number | null; changed: boolean }[] {
  const rows: [string, (p: NonNullable<PlanView>) => number | null][] = [
    ['Entry low', (p) => p.entry_zone[0]], ['Entry high', (p) => p.entry_zone[1]], ['Stop', (p) => p.stop_loss], ['Target 1', (p) => p.target_1], ['Target 2', (p) => p.target_2],
    ['Expected R (TP1)', (p) => p.expected_r_tp1], ['Expected R (TP2)', (p) => p.expected_r_tp2],
  ]
  return rows.map(([label, f]) => { const a = original ? f(original) : null, b = user ? f(user) : null; return { label, original: a, user: b, changed: a !== b && !(a === null && b === null) } })
}

const at = (o: unknown, path: string): unknown => path.split('.').reduce<unknown>((a, k) => (a && typeof a === 'object' ? (a as Record<string, unknown>)[k] : undefined), o)
const num = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null)
export type ChangeRow = { metric: string; t0: number | string | null; current: number | string | null; change: number | null; kind: 'num' | 'pct' | 'text' }
/** T0 (frozen) vs a later reading of the same quantities. T0 is never altered by the later reading. */
export function changeRows(t0: Record<string, unknown>, now: Record<string, unknown> | undefined): ChangeRow[] {
  const spec: [string, string, string, string, 'num' | 'pct' | 'text'][] = [
    ['Price', 'price_snapshot.price', 'quote.price', 'price', 'num'],
    ['RSI 14', 'technical_snapshot.indicators.rsi14', 'technical.indicators.rsi14', 'tech', 'num'],
    ['ATR 14 (% of price)', 'technical_snapshot.risk.atr14_pct', 'technical.risk.atr14_pct', 'tech', 'pct'],
    ['Trend state', 'technical_snapshot.trend.state', 'technical.trend.state', 'tech', 'text'],
    ['P/E', 'valuation_snapshot.current.pe', 'valuation.current.pe', 'val', 'num'],
    ['Market cap', 'valuation_snapshot.market_cap', 'valuation.market_cap', 'val', 'num'],
    ['Net margin', 'fundamental_snapshot.profitability.net_margin.value', 'fundamental.profitability.net_margin.value', 'fund', 'pct'],
    ['Latest fundamental period', 'fundamental_snapshot.latest_period', 'fundamental.latest_period', 'fund', 'text'],
  ]
  return spec.map(([metric, a, b, , kind]) => {
    const x = at(t0, a), y = now ? at(now, b) : undefined
    const nx = kind === 'text' ? (typeof x === 'string' ? x : null) : num(x), ny = kind === 'text' ? (typeof y === 'string' ? y : null) : num(y)
    return { metric, t0: nx, current: ny, change: typeof nx === 'number' && typeof ny === 'number' ? ny - nx : null, kind }
  })
}
