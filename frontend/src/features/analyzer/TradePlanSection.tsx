import { useState } from 'react'
import { usePositionSize, useTradePlan } from '../../api/hooks'
import type { Setup } from '../../api/types'
import { Badge, Button, Card, CardBody, CardHeader, Metric, PanelError, Segmented, Skeleton } from '../../components/ui/primitives'
import { ExplainDetails } from './ExplainDetails'
import { fmtNum, fmtPct } from '../../lib/format'

const PROFILES = ['AGGRESSIVE', 'BASE', 'CONSERVATIVE'] as const
export function TradePlanSection({ sec }: { sec: string }) {
  const q = useTradePlan(sec)
  const [type, setType] = useState<string>('')
  const [profile, setProfile] = useState<(typeof PROFILES)[number]>('BASE')
  const setups = q.data?.setups ?? []
  const types = [...new Set(setups.map((s) => s.type))]
  const activeType = type && types.includes(type) ? type : types[0]
  const s: Setup | undefined = setups.find((x) => x.type === activeType && x.profile === profile)
  return (
    <Card>
      <CardHeader title="Trade plan (long)" sub="Market structure + ATR only. Fundamentals never shape the stop." right={<Badge tone="warn">Rule-based · not yet backtest validated</Badge>} />
      <CardBody>
        {q.isPending ? <Skeleton className="h-40" /> : q.isError ? <PanelError what="Trade plan" error={q.error} onRetry={() => q.refetch()} /> : q.data?.status !== 'SETUPS_AVAILABLE' ? (
          <div className="text-sm"><Badge tone="neutral">{q.data?.status ?? 'NO_DATA'}</Badge> <span className="ml-2 text-muted">{q.data?.reason ?? 'No valid setup.'}</span></div>
        ) : (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-3">
              {types.length > 1 ? <Segmented label="Setup" value={activeType as string} options={types} onChange={setType} /> : <Badge tone="accent">{activeType?.replace('_', ' ')}</Badge>}
              <Segmented label="Profile" value={profile} options={PROFILES} onChange={setProfile} />
              <span className="text-[11px] text-muted">Trend context: {q.data.trend_context?.state?.replace('_', ' ').toLowerCase()}</span>
            </div>
            {s ? <SetupView sec={sec} s={s} /> : null}
            <ExplainDetails sec={sec} panel="trade-plan" />
          </>
        )}
      </CardBody>
    </Card>
  )
}

function SetupView({ sec, s }: { sec: string; s: Setup }) {
  const [capital, setCapital] = useState('100000')
  const [risk, setRisk] = useState('1')
  const [ask, setAsk] = useState<{ capital: number; risk: number; entry: number; stop: number } | null>(null)
  const ps = usePositionSize(sec, ask)
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 lg:col-span-1">
        <Metric label="Entry zone" value={`${fmtNum(s.entry_zone.lower)}–${fmtNum(s.entry_zone.upper)}`} />
        <Metric label={`Entry (${s.profile.toLowerCase()})`} value={fmtNum(s.entry)} />
        <Metric label="Invalidation level" value={fmtNum(s.invalidation_level)} />
        <Metric label="Stop" value={fmtNum(s.stop)} tone="text-down" context={`${fmtPct(s.stop_distance_pct, 1)} · ${s.stop_distance_atr.toFixed(2)} ATR`} />
        <Metric label="Risk / share" value={fmtNum(s.risk_per_share)} />
        {s.structural_target ? <Metric label="Structural target" value={fmtNum(s.structural_target.price)} context={`${fmtPct(s.structural_target.potential_pct, 1, true)} · ${s.structural_target.r_multiple.toFixed(1)}R`} /> : <Metric label="Structural target" value="—" reason="no resistance above" />}
      </div>
      <div className="lg:col-span-1">
        <div className="mb-1 text-[11px] uppercase tracking-[0.08em] text-muted">Scenario targets <Badge>not forecasts</Badge></div>
        <table className="w-full text-xs">
          <tbody>
            {s.r_targets.map((t) => (
              <tr key={t.r_multiple} className="border-t border-border"><td className="py-1.5">{t.r_multiple}R</td><td className="num">{fmtNum(t.price)}</td><td className="num text-up">{fmtPct(t.potential_pct, 1, true)}</td></tr>
            ))}
          </tbody>
        </table>
        <div className="mt-3 text-[11px] text-muted">Conditions</div>
        <ul className="list-disc pl-4 text-xs">{s.conditions.map((c) => <li key={c}>{c}</li>)}</ul>
        {s.confluence.length ? <><div className="mt-2 text-[11px] text-muted">Confluence</div><ul className="list-disc pl-4 text-xs">{s.confluence.map((c) => <li key={c}>{c}</li>)}</ul></> : null}
        {s.warnings.map((w) => <div key={w} className="mt-1 text-[11px] text-warn">{w}</div>)}
      </div>
      <div className="rounded-md border border-border p-3 lg:col-span-1">
        <div className="mb-2 text-[11px] uppercase tracking-[0.08em] text-muted">Position size</div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <label className="flex flex-col gap-1">Capital (USD)<input aria-label="Capital" className="num rounded border border-border bg-surface-2 px-2 py-1" value={capital} onChange={(e) => setCapital(e.target.value)} /></label>
          <label className="flex flex-col gap-1">Risk per trade (%)<input aria-label="Risk percent" className="num rounded border border-border bg-surface-2 px-2 py-1" value={risk} onChange={(e) => setRisk(e.target.value)} /></label>
        </div>
        <Button className="mt-2" onClick={() => setAsk({ capital: Number(capital), risk: Number(risk), entry: s.entry, stop: s.stop })}>Compute</Button>
        {ps.data ? (ps.data.status === 'OK' ? (
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Metric label="Max shares" value={String(ps.data.shares)} />
            <Metric label="Notional" value={fmtNum(ps.data.notional)} context={`${fmtPct(ps.data.notional_pct_of_capital, 1)} of capital`} />
            <Metric label="Risk amount" value={fmtNum(ps.data.risk_amount)} />
            <Metric label="Actual risk" value={fmtNum(ps.data.actual_risk)} />
            {ps.data.capped_by_capital_no_leverage ? <div className="col-span-2 text-[11px] text-warn">Capped by capital (no leverage).</div> : null}
          </div>
        ) : <div className="mt-2 text-xs text-warn">{ps.data.reason}</div>) : null}
        {ps.isError ? <div className="mt-2 text-xs text-warn">Could not compute.</div> : null}
      </div>
    </div>
  )
}
