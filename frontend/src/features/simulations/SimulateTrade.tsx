import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiPost, ApiError } from '../../api/client'
import { useTradePlan } from '../../api/hooks'
import type { Summary } from '../../api/types'
import { Badge, Button } from '../../components/ui/primitives'
import { fmtNum, fmtPct } from '../../lib/format'
import { fmtR, positionSize, riskReward, validatePlan, type PlanDraft } from '../../lib/simulation'

type Origin = 'PITQUANT' | 'USER_MODIFIED' | 'USER_DEFINED'
type EntryType = 'MARKET_REFERENCE' | 'LIMIT' | 'ENTRY_ZONE'
const FIELDS = [
  ['entry_zone_low', 'Entry zone low'],
  ['entry_zone_high', 'Entry zone high'],
  ['stop_loss', 'Stop loss'],
  ['invalidation_level', 'Invalidation'],
  ['target_1', 'Target 1'],
  ['target_2', 'Target 2'],
  ['target_3_optional', 'Target 3 (optional)'],
] as const
const ENTRY_LABEL: Record<EntryType, string> = { MARKET_REFERENCE: 'Market reference (price shown now)', LIMIT: 'Limit price', ENTRY_ZONE: 'Entry zone' }

/** «Simulate trade»: a 3-step wizard (setup → entry → risk) that opens a PAPER trade (no real money). Disabled, with its reason, without price data. */
export function SimulateTrade({ sec, summary }: { sec: string; summary: Summary }) {
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(1)
  const [origin, setOrigin] = useState<Origin>('USER_DEFINED')
  const [entryType, setEntryType] = useState<EntryType>('ENTRY_ZONE')
  const [entryPrice, setEntryPrice] = useState('')
  const [v, setV] = useState<Record<string, string>>({})
  const [policy, setPolicy] = useState<'TRACK_TARGETS_ONLY' | 'PARTIAL_FRACTIONS'>('TRACK_TARGETS_ONLY')
  const [fr, setFr] = useState<string[]>(['', '', ''])
  const [sizing, setSizing] = useState<'RISK_BASED' | 'FIXED_NOTIONAL'>('RISK_BASED')
  const [capital, setCapital] = useState('100000')
  const [riskPct, setRiskPct] = useState('1')
  const [notional, setNotional] = useState('10000')
  const [horizon, setHorizon] = useState('20')
  const plan = useTradePlan(sec)
  const enabled = summary.simulation?.enabled ?? summary.quote.status === 'OK'
  const reason = summary.simulation?.reason ?? (enabled ? null : 'PRICE_DATA_REQUIRED')
  const base = plan.data?.setups?.find((s) => s.profile === 'BASE') ?? plan.data?.setups?.[0]
  const num = (k: string) => (v[k] !== undefined && v[k] !== '' ? Number(v[k]) : undefined)
  const fractions = fr.map((x) => (x === '' ? 0 : Number(x)))
  const draft: PlanDraft = { entryType, entry: entryType === 'MARKET_REFERENCE' ? Number(summary.quote.price) : entryPrice !== '' ? Number(entryPrice) : undefined, zoneLow: num('entry_zone_low'), zoneHigh: num('entry_zone_high'), stop: num('stop_loss'), targets: [num('target_1'), num('target_2'), num('target_3_optional')] }
  const rr = riskReward(draft)
  const errors = origin === 'PITQUANT' ? [] : validatePlan(draft, policy === 'PARTIAL_FRACTIONS' ? fractions : undefined)
  const entryRef = entryType === 'ENTRY_ZONE' ? draft.zoneHigh : draft.entry
  const size = entryRef !== undefined && draft.stop !== undefined ? positionSize(sizing === 'RISK_BASED' ? { mode: 'RISK_BASED', portfolio: Number(capital), riskPercent: Number(riskPct) } : { mode: 'FIXED_NOTIONAL', notional: Number(notional) }, entryRef, draft.stop) : null
  const create = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { security: sec, plan_origin: origin, horizon_sessions: Number(horizon), sizing_mode: sizing, capital: Number(capital), risk_pct: Number(riskPct), notional: sizing === 'FIXED_NOTIONAL' ? Number(notional) : null }
      if (origin === 'PITQUANT') body.plan = {}
      else body.plan = { ...Object.fromEntries(FIELDS.map(([k]) => [k, num(k) ?? null])), entry_type: entryType, entry_price: entryType === 'LIMIT' ? draft.entry ?? null : null, exit_policy: policy, exit_fractions: policy === 'PARTIAL_FRACTIONS' ? fractions : null }
      return apiPost<{ simulation_id: string }>('/simulations', body)
    },
    onSuccess: (r) => nav(`/simulations/${r.simulation_id}`),
  })
  const fill = () => {
    if (!base) return
    setV({ entry_zone_low: String(base.entry_zone.lower), entry_zone_high: String(base.entry_zone.upper), stop_loss: String(base.stop), invalidation_level: String(base.invalidation_level), target_1: String(base.target_1 ?? ''), target_2: String(base.target_2 ?? '') })
  }
  if (!enabled) {
    return (
      <span className="inline-flex items-center gap-2">
        <Button disabled aria-disabled title={reason ?? ''} data-testid="simulate-disabled">Simulate trade</Button>
        <Badge tone="neutral">{reason}</Badge>
      </span>
    )
  }
  const input = (k: (typeof FIELDS)[number][0], label: string) => (
    <label key={k} className="flex flex-col gap-1">{label}
      <input aria-label={label} inputMode="decimal" value={v[k] ?? ''} onChange={(e) => setV({ ...v, [k]: e.target.value })} className="num rounded border border-border bg-surface-2 px-2 py-1" />
    </label>
  )
  return (
    <div className="inline-block">
      <Button variant="solid" onClick={() => setOpen((o) => !o)} data-testid="simulate-open">Simulate trade</Button>
      {open ? (
        <div role="dialog" aria-label="Simulate trade" className="mt-2 w-full max-w-xl space-y-3 rounded-lg border border-border bg-surface p-4 text-xs">
          <div className="font-semibold text-warn">PAPER TRADE — NO REAL MONEY</div>
          <div className="flex gap-1" aria-label="Steps">{['1 Setup', '2 Entry', '3 Risk plan'].map((s, i) => <Badge key={s} tone={step === i + 1 ? 'accent' : 'neutral'}>{s}</Badge>)}</div>
          {step === 1 ? (
            <div className="space-y-2" data-testid="wizard-setup">
              <p className="num text-muted">Current price {fmtNum(Number(summary.quote.price))} · trend {summary.summary.trend ?? '—'} · valuation {summary.summary.valuation ?? '—'} · data quality {summary.summary.data_quality ?? '—'} · plan setup {base ? `${String((base as { setup_type?: string }).setup_type ?? '')} ${base.profile}` : 'none available'}</p>
              <label className="flex items-center gap-2">Plan
                <select value={origin} onChange={(e) => { setOrigin(e.target.value as Origin); if (e.target.value !== 'USER_DEFINED') fill() }} className="rounded border border-border bg-surface-2 px-2 py-1">
                  <option value="PITQUANT" disabled={!base}>Use the PITQuant plan exactly {base ? '' : '(none available)'}</option>
                  <option value="USER_MODIFIED" disabled={!base}>Modify the PITQuant plan</option>
                  <option value="USER_DEFINED">Define my own levels</option>
                </select>
              </label>
              <p className="text-muted">Side: LONG (SHORT is not validated by the Trade Plan and stays disabled).</p>
            </div>
          ) : null}
          {step === 2 && origin !== 'PITQUANT' ? (
            <div className="space-y-2" data-testid="wizard-entry">
              <label className="flex items-center gap-2">Entry type
                <select aria-label="Entry type" value={entryType} onChange={(e) => setEntryType(e.target.value as EntryType)} className="rounded border border-border bg-surface-2 px-2 py-1">{(Object.keys(ENTRY_LABEL) as EntryType[]).map((t) => <option key={t} value={t}>{ENTRY_LABEL[t]}</option>)}</select></label>
              {entryType === 'LIMIT' ? <label className="flex flex-col gap-1">Entry price<input aria-label="Entry price" inputMode="decimal" value={entryPrice} onChange={(e) => setEntryPrice(e.target.value)} className="num rounded border border-border bg-surface-2 px-2 py-1" /></label> : null}
              {entryType === 'ENTRY_ZONE' ? <div className="grid grid-cols-2 gap-2">{input('entry_zone_low', 'Entry zone low')}{input('entry_zone_high', 'Entry zone high')}</div> : null}
              {entryType === 'MARKET_REFERENCE' ? <p className="text-muted">Enters at the price shown now ({fmtNum(Number(summary.quote.price))}), stored at creation: it is never replaced by a later close.</p> : null}
            </div>
          ) : null}
          {step === 3 && origin !== 'PITQUANT' ? (
            <div className="space-y-2" data-testid="wizard-risk">
              <div className="grid grid-cols-2 gap-2">{input('stop_loss', 'Stop loss')}{input('invalidation_level', 'Invalidation')}{input('target_1', 'Target 1')}{input('target_2', 'Target 2')}{input('target_3_optional', 'Target 3 (optional)')}
                <label className="flex flex-col gap-1">Horizon (sessions)<input aria-label="Horizon (sessions)" inputMode="numeric" value={horizon} onChange={(e) => setHorizon(e.target.value)} className="num rounded border border-border bg-surface-2 px-2 py-1" /></label></div>
              <p data-testid="rr-preview" className="num text-muted">Stop distance {fmtPct(rr.stopPct, 2)} · R:R TP1 {fmtR(rr.rr[0])} · TP2 {fmtR(rr.rr[1])} · TP3 {fmtR(rr.rr[2])}</p>
              <label className="flex items-center gap-2">Exit policy
                <select aria-label="Exit policy" value={policy} onChange={(e) => setPolicy(e.target.value as typeof policy)} className="rounded border border-border bg-surface-2 px-2 py-1"><option value="TRACK_TARGETS_ONLY">Track targets only (no partial sale assumed)</option><option value="PARTIAL_FRACTIONS">Explicit partial exits</option></select></label>
              {policy === 'PARTIAL_FRACTIONS' ? <div className="grid grid-cols-3 gap-2">{['TP1', 'TP2', 'TP3'].map((l, i) => <label key={l} className="flex flex-col gap-1">{l} fraction<input aria-label={`${l} fraction`} inputMode="decimal" value={fr[i]} onChange={(e) => setFr(fr.map((x, j) => (j === i ? e.target.value : x)))} className="num rounded border border-border bg-surface-2 px-2 py-1" /></label>)}</div> : null}
              <label className="flex items-center gap-2">Position size
                <select aria-label="Sizing mode" value={sizing} onChange={(e) => setSizing(e.target.value as typeof sizing)} className="rounded border border-border bg-surface-2 px-2 py-1"><option value="RISK_BASED">Risk based</option><option value="FIXED_NOTIONAL">Fixed notional</option></select></label>
              {sizing === 'RISK_BASED' ? <div className="grid grid-cols-2 gap-2"><label className="flex flex-col gap-1">Simulated portfolio<input aria-label="Simulated portfolio" value={capital} onChange={(e) => setCapital(e.target.value)} className="num rounded border border-border bg-surface-2 px-2 py-1" /></label><label className="flex flex-col gap-1">Risk %<input aria-label="Risk percent" value={riskPct} onChange={(e) => setRiskPct(e.target.value)} className="num rounded border border-border bg-surface-2 px-2 py-1" /></label></div>
                : <label className="flex flex-col gap-1">Simulated notional<input aria-label="Simulated notional" value={notional} onChange={(e) => setNotional(e.target.value)} className="num rounded border border-border bg-surface-2 px-2 py-1" /></label>}
              <p data-testid="size-preview" className="num text-muted">{size ? `${size.shares} shares · notional ${fmtNum(size.notional)} · capital at risk ${fmtNum(size.capitalAtRisk)}` : 'position size not computable yet'}</p>
              {errors.length ? <ul role="alert" data-testid="plan-errors" className="text-down">{errors.map((e) => <li key={e}>{e}</li>)}</ul> : null}
            </div>
          ) : null}
          {origin === 'PITQUANT' && step > 1 ? <p className="text-muted" data-testid="wizard-pitquant">The PITQuant plan is used exactly as shown in the Trade Plan; it is frozen at creation.</p> : null}
          <p className="text-muted">The Trade Plan stays «{plan.data?.label ?? 'rule-based · not yet backtest validated'}». Prediction: NOT_YET_VALIDATED, no probability is attached.</p>
          {create.isError ? <p role="alert" className="text-down">{(create.error as ApiError).message}</p> : null}
          <div className="flex gap-2">
            {step > 1 ? <Button onClick={() => setStep(step - 1)}>Back</Button> : null}
            {step < 3 ? <Button onClick={() => setStep(step + 1)} data-testid="wizard-next">Next</Button> : null}
            <Button variant="solid" onClick={() => create.mutate()} disabled={create.isPending || errors.length > 0} data-testid="simulate-submit">Open paper trade</Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
