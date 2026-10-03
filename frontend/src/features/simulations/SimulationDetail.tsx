import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api, apiPost } from '../../api/client'
import { Badge, Button, Card, CardBody, CardHeader, PanelError, Skeleton } from '../../components/ui/primitives'
import { fmtPct } from '../../lib/format'
import { PaperBanner } from './Banner'
import type { Bar, SimDetail } from './types'

function Chart({ bars, levels }: { bars: Bar[]; levels: { label: string; y: number; cls: string }[] }) {
  if (bars.length < 2) return <p className="text-xs text-muted">No bars after the decision yet: the chart starts when the first session closes.</p>
  const ys = [...bars.map((b) => b.close), ...levels.map((l) => l.y)]
  const lo = Math.min(...ys), hi = Math.max(...ys), W = 640, H = 220
  const y = (v: number) => H - ((v - lo) / (hi - lo || 1)) * (H - 20) - 10
  const x = (i: number) => (i / (bars.length - 1)) * (W - 10) + 5
  return (
    <svg role="img" aria-label="Price since the decision with the plan levels" viewBox={`0 0 ${W} ${H}`} className="w-full">
      {levels.map((l) => (
        <g key={l.label}><line x1={0} x2={W} y1={y(l.y)} y2={y(l.y)} className={l.cls} strokeDasharray="4 3" /><text x={4} y={y(l.y) - 2} fontSize="9" className="fill-current text-muted">{l.label} {l.y.toFixed(2)}</text></g>
      ))}
      <polyline fill="none" stroke="currentColor" strokeWidth="1.5" className="text-accent" points={bars.map((b, i) => `${x(i)},${y(b.close)}`).join(' ')} />
    </svg>
  )
}

export function SimulationDetail() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['sim', id], queryFn: ({ signal }) => api<SimDetail>(`/simulations/${id}`, signal) })
  const refresh = () => qc.invalidateQueries({ queryKey: ['sim', id] })
  const evaluate = useMutation({ mutationFn: () => apiPost(`/simulations/${id}/evaluate`, {}), onSuccess: refresh })
  const snapshot = useMutation({ mutationFn: () => apiPost(`/simulations/${id}/snapshot`, {}), onSuccess: refresh })
  if (q.isPending) return <Skeleton className="h-96" />
  if (q.isError) return <PanelError what="Simulation" error={q.error} onRetry={() => q.refetch()} />
  const { simulation: s, outcomes, observations, postmortems, bars } = q.data
  const last = outcomes[outcomes.length - 1]
  const sr = s.support_resistance_snapshot
  const levels = [
    { label: 'Entry high', y: s.entry_zone_high, cls: 'stroke-current text-accent' }, { label: 'Entry low', y: s.entry_zone_low, cls: 'stroke-current text-accent' },
    { label: 'Stop', y: s.stop_loss, cls: 'stroke-current text-down' }, { label: 'Target 1', y: s.target_1, cls: 'stroke-current text-up' },
    ...(s.target_2 ? [{ label: 'Target 2', y: s.target_2, cls: 'stroke-current text-up' }] : []),
    ...(sr.supports ?? []).slice(0, 1).map((z) => ({ label: 'Support (T0)', y: z.lower, cls: 'stroke-current text-muted' })),
    ...(sr.resistances ?? []).slice(0, 1).map((z) => ({ label: 'Resistance (T0)', y: z.upper, cls: 'stroke-current text-muted' })),
  ]
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PaperBanner />
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold">Paper trade</h1>
        <Badge tone="neutral">{last?.state ?? 'CREATED'}</Badge><Badge tone="warn">{s.trade_plan_snapshot.label ?? 'RULE_BASED · NOT YET BACKTEST VALIDATED'}</Badge>
        <Badge tone="neutral">Prediction {s.prediction_status}</Badge><Badge tone="neutral">{s.plan_origin}</Badge>
        <span className="ml-auto flex gap-2"><Button onClick={() => evaluate.mutate()} disabled={evaluate.isPending}>Evaluate now</Button><Button onClick={() => snapshot.mutate()} disabled={snapshot.isPending}>Thesis snapshot</Button></span>
      </div>
      <Card><CardHeader title="Price since the decision" sub={`decision_at ${s.decision_at} · levels fixed at T0`} /><CardBody><Chart bars={bars} levels={levels} /></CardBody></Card>
      <Card><CardHeader title="Outcome" sub={last ? `evaluated ${last.evaluated_at}` : 'not evaluated yet'} />
        <CardBody>{last ? (
          <dl className="num grid grid-cols-2 gap-3 text-xs sm:grid-cols-5">
            {([['Return', fmtPct(last.realized_return, 1)], ['Excess vs benchmark', fmtPct(last.excess_return_vs_benchmark, 1)], ['R', last.realized_r?.toFixed(2) ?? '—'], ['MFE', fmtPct(last.mfe, 1)], ['MAE', fmtPct(last.mae, 1)], ['Max drawdown', fmtPct(last.max_drawdown, 1)], ['Days to entry', last.days_to_entry ?? '—'], ['Holding (days)', last.holding_period ?? '—'], ['Direction correct', last.prediction_direction_correct === null ? 'n/a (no validated model)' : String(last.prediction_direction_correct)], ['Plan execution correct', last.trade_plan_execution_correct === null ? 'n/a (no validated model)' : String(last.trade_plan_execution_correct)]] as [string, string | number][]).map(([k, val]) => <div key={k}><dt className="text-muted">{k}</dt><dd>{val}</dd></div>)}
          </dl>) : <p className="text-xs text-muted">Press «Evaluate now» to apply the daily bars since the decision.</p>}
        </CardBody></Card>
      <Card><CardHeader title="Timeline" /><CardBody><ol className="space-y-1 text-xs">{(last?.timeline ?? []).map((t, i) => <li key={i}><span className="num text-muted">{t.date}</span> <Badge tone="neutral">{t.state}</Badge> {t.note}</li>)}</ol></CardBody></Card>
      <Card><CardHeader title="Plan" sub="original PITQuant plan vs the simulated one" /><CardBody className="grid gap-3 text-xs md:grid-cols-2">
        <pre className="overflow-x-auto rounded bg-surface-2 p-2">{JSON.stringify(s.original_pitquant_plan ?? 'none (user-defined)', null, 1)}</pre>
        <pre className="overflow-x-auto rounded bg-surface-2 p-2">{JSON.stringify(s.final_simulated_plan, null, 1)}</pre></CardBody></Card>
      <Card><CardHeader title="Thesis evolution" sub="analysis at entry (T0, immutable) vs later snapshots" /><CardBody className="space-y-2 text-xs">
        {observations.filter((o) => o.kind === 'THESIS_SNAPSHOT').length === 0 ? <p className="text-muted">No later snapshot yet.</p> : observations.filter((o) => o.kind === 'THESIS_SNAPSHOT').map((o) => <pre key={o.observation_id} className="overflow-x-auto rounded bg-surface-2 p-2">{o.observed_at}: {JSON.stringify(o.payload.comparison)}</pre>)}</CardBody></Card>
      <Card><CardHeader title="Post-mortem" /><CardBody className="text-xs">{postmortems.length ? postmortems.map((p, i) => <div key={i}><b>{p.primary_cause}</b> {p.secondary_causes.join(', ')} — classified by {p.classified_by}{p.notes ? `: ${p.notes}` : ''}</div>) : <p className="text-muted">Not classified. A post-mortem is recorded explicitly by a person for a CLOSED simulation; no automatic verdict is generated.</p>}</CardBody></Card>
    </div>
  )
}
