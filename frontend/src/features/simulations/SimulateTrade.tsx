import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiPost, ApiError } from '../../api/client'
import { useTradePlan } from '../../api/hooks'
import type { Summary } from '../../api/types'
import { Badge, Button } from '../../components/ui/primitives'

type Origin = 'PITQUANT' | 'USER_MODIFIED' | 'USER_DEFINED'
const FIELDS = [
  ['entry_zone_low', 'Entry zone low'],
  ['entry_zone_high', 'Entry zone high'],
  ['stop_loss', 'Stop loss'],
  ['invalidation_level', 'Invalidation'],
  ['target_1', 'Target 1'],
  ['target_2', 'Target 2'],
] as const

/** «Simulate trade»: opens a PAPER trade (no real money). Disabled, with its reason, when the security has no price data. */
export function SimulateTrade({ sec, summary }: { sec: string; summary: Summary }) {
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [origin, setOrigin] = useState<Origin>('USER_DEFINED')
  const [v, setV] = useState<Record<string, string>>({})
  const plan = useTradePlan(sec)
  const enabled = summary.simulation?.enabled ?? summary.quote.status === 'OK'
  const reason = summary.simulation?.reason ?? (enabled ? null : 'PRICE_DATA_REQUIRED')
  const base = plan.data?.setups?.find((s) => s.profile === 'BASE') ?? plan.data?.setups?.[0]
  const create = useMutation({
    mutationFn: () => {
      const num = (k: string) => (v[k] !== undefined && v[k] !== '' ? Number(v[k]) : null)
      const body = { security: sec, plan_origin: origin, plan: Object.fromEntries(FIELDS.map(([k]) => [k, num(k)])) }
      if (origin === 'PITQUANT') body.plan = {} as typeof body.plan
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
  return (
    <div className="inline-block">
      <Button variant="solid" onClick={() => setOpen((o) => !o)} data-testid="simulate-open">Simulate trade</Button>
      {open ? (
        <div role="dialog" aria-label="Simulate trade" className="mt-2 w-full max-w-xl space-y-3 rounded-lg border border-border bg-surface p-4 text-xs">
          <div className="font-semibold text-warn">PAPER TRADE — NO REAL MONEY</div>
          <label className="flex items-center gap-2">Plan
            <select value={origin} onChange={(e) => { setOrigin(e.target.value as Origin); if (e.target.value !== 'USER_DEFINED') fill() }} className="rounded border border-border bg-surface-2 px-2 py-1">
              <option value="PITQUANT" disabled={!base}>Use the PITQuant plan exactly {base ? '' : '(none available)'}</option>
              <option value="USER_MODIFIED" disabled={!base}>Modify the PITQuant plan</option>
              <option value="USER_DEFINED">Define my own levels</option>
            </select>
          </label>
          {origin !== 'PITQUANT' ? (
            <div className="grid grid-cols-2 gap-2">
              {FIELDS.map(([k, label]) => (
                <label key={k} className="flex flex-col gap-1">{label}
                  <input aria-label={label} inputMode="decimal" value={v[k] ?? ''} onChange={(e) => setV({ ...v, [k]: e.target.value })} className="num rounded border border-border bg-surface-2 px-2 py-1" />
                </label>
              ))}
            </div>
          ) : null}
          <p className="text-muted">The Trade Plan stays «{plan.data?.label ?? 'rule-based · not yet backtest validated'}». Prediction: NOT_YET_VALIDATED, no probability is attached.</p>
          {create.isError ? <p role="alert" className="text-down">{(create.error as ApiError).message}</p> : null}
          <Button variant="solid" onClick={() => create.mutate()} disabled={create.isPending} data-testid="simulate-submit">Open paper trade</Button>
        </div>
      ) : null}
    </div>
  )
}
