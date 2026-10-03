import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, apiPost, ApiError } from '../../api/client'
import { Badge, Button, Card, CardBody, CardHeader, PanelError, Segmented, Skeleton } from '../../components/ui/primitives'
import { fmtNum, fmtPct } from '../../lib/format'
import { changeRows, describeEvent, fmtR, isClosedState, snapFromCurrent, snapFromObservation, snapFromT0, stateLabel, stateTone } from '../../lib/simulation'
import { PaperBanner } from './Banner'
import { PlanComparison } from './PlanComparison'
import { PostMortemPanel } from './PostMortemPanel'
import { SimChart, type Level } from './SimChart'
import type { SimDetail } from './types'

const TABS = ['Decision snapshot', 'Recorded observations', 'Changes', 'Current analysis', 'Plan comparison', 'Post-mortem', 'Provenance'] as const
type Tab = (typeof TABS)[number]
const dl = (rows: [string, string | number | null | undefined][]) => (
  <dl className="num grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">{rows.map(([k, v]) => <div key={k}><dt className="text-muted">{k}</dt><dd>{v === null || v === undefined ? '—' : v}</dd></div>)}</dl>
)

export function SimulationDetail() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('Decision snapshot')
  const [closePx, setClosePx] = useState('')
  const [fromKey, setFromKey] = useState('T0')
  const [toKey, setToKey] = useState('LATEST')
  const q = useQuery({ queryKey: ['sim', id], queryFn: ({ signal }) => api<SimDetail>(`/simulations/${id}`, signal) })
  const refresh = () => { qc.invalidateQueries({ queryKey: ['sim', id] }); qc.invalidateQueries({ queryKey: ['sim-pm', id] }); qc.invalidateQueries({ queryKey: ['sim-summary'] }); qc.invalidateQueries({ queryKey: ['sim-list'] }) }
  const update = useMutation({ mutationFn: () => apiPost<{ new_events: number }>(`/simulations/${id}/update`, {}), onSuccess: refresh })
  const snapshot = useMutation({ mutationFn: () => apiPost(`/simulations/${id}/snapshot`, {}), onSuccess: refresh })
  const cancel = useMutation({ mutationFn: () => apiPost(`/simulations/${id}/cancel`, {}), onSuccess: refresh })
  const close = useMutation({ mutationFn: () => apiPost(`/simulations/${id}/close`, { price: Number(closePx), reason: 'manual close from the UI' }), onSuccess: () => { setClosePx(''); refresh() } })
  const replay = useMutation({ mutationFn: () => api<{ match: boolean; differences: string[]; n_events: number }>(`/simulations/${id}/replay`) })
  const levels = useMemo<Level[]>(() => {
    const s = q.data?.simulation
    if (!s) return []
    const sr = s.support_resistance_snapshot
    return [
      { label: 'Entry high', price: s.entry_zone_high, kind: 'entry' }, ...(s.entry_zone_low !== s.entry_zone_high ? [{ label: 'Entry low', price: s.entry_zone_low, kind: 'entry' } as Level] : []),
      { label: 'Stop', price: s.stop_loss, kind: 'stop' }, { label: 'Target 1', price: s.target_1, kind: 'target' },
      ...(s.target_2 ? [{ label: 'Target 2', price: s.target_2, kind: 'target' } as Level] : []), ...(s.target_3_optional ? [{ label: 'Target 3', price: s.target_3_optional, kind: 'target' } as Level] : []),
      ...(s.invalidation_level ? [{ label: 'Invalidation', price: s.invalidation_level, kind: 'invalidation' } as Level] : []),
      ...(sr.supports ?? []).slice(0, 1).map((z) => ({ label: 'Support (T0)', price: z.lower, kind: 'sr' }) as Level), ...(sr.resistances ?? []).slice(0, 1).map((z) => ({ label: 'Resistance (T0)', price: z.upper, kind: 'sr' }) as Level),
    ]
  }, [q.data])
  if (q.isPending) return <Skeleton className="h-96" />
  if (q.isError) return <PanelError what="Simulation" error={q.error} onRetry={() => q.refetch()} />
  const { simulation: s, outcomes, observations, bars, events, comparison, explain } = q.data
  const last = outcomes[outcomes.length - 1]
  const state = last?.state ?? 'CREATED'
  const closed = isClosedState(state)
  const ex = last?.details?.metrics_extra ?? {}
  const entered = !!last?.entry_date
  const timeline = events.map((e) => ({ e, text: describeEvent(e) })).filter((x) => x.text !== null)
  const recorded = observations.filter((o) => o.kind === 'PERIODIC')
  const snaps = new Map<string, ReturnType<typeof snapFromT0>>([['T0', snapFromT0(s as unknown as Record<string, unknown>)]])
  for (const o of recorded) snaps.set(o.observation_id, snapFromObservation({ horizon_label: o.horizon_label, observed_at: o.observed_at, payload: o.payload }))
  const cur = snapFromCurrent(q.data.current)
  if (cur) snaps.set('CURRENT', cur)
  const latestKey = recorded.length ? recorded[recorded.length - 1].observation_id : cur ? 'CURRENT' : 'T0'
  const pick = (k: string) => snaps.get(k === 'LATEST' ? latestKey : k) ?? snaps.get('T0')!
  const fromSnap = pick(fromKey), toSnap = pick(toKey)
  const rows = changeRows(fromSnap, toSnap)
  const evolution = q.data.thesis_evolution ?? []
  const shownFacts = evolution.find((e) => e.observation_id === (toKey === 'LATEST' ? latestKey : toKey))?.facts ?? []
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PaperBanner />
      <div className="flex flex-wrap items-center gap-2" data-testid="sim-header">
        <h1 className="text-xl font-semibold">Simulation <span className="num text-sm text-muted">#{s.simulation_id.slice(0, 8)}</span></h1>
        <Badge tone={stateTone(state)} data-testid="sim-state">{stateLabel(state)}</Badge>
        <Badge tone="warn">PAPER TRADE</Badge>
        <Badge tone="info" data-testid="engine-badge">Engine {s.simulation_engine_version ?? 'v1'}</Badge>
        <Badge tone="warn">PREDICTION ENGINE NOT YET VALIDATED</Badge>
        <Badge tone="warn">{s.trade_plan_snapshot.label ?? 'TRADE PLAN RULE-BASED · NOT YET BACKTEST VALIDATED'}</Badge>
        <Badge tone="neutral">Prediction {s.prediction_status}</Badge>
      </div>
      <p className="num text-xs text-muted">created {s.created_at} · decision_at {s.decision_at} · plan origin <b>{s.plan_origin}</b> · rules {s.rules_version} · analyzer {s.analyzer_version} · features {s.feature_version} · exit policy {q.data.plan_levels.exit_policy}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => update.mutate()} disabled={update.isPending} data-testid="sim-update">Update now</Button>
        <Button onClick={() => snapshot.mutate()} disabled={snapshot.isPending}>Thesis snapshot</Button>
        <Button onClick={() => replay.mutate()} data-testid="sim-replay">Replay from events</Button>
        {!entered && !closed ? <Button onClick={() => cancel.mutate()} disabled={cancel.isPending} data-testid="sim-cancel">Cancel</Button> : null}
        {entered && !closed ? <span className="inline-flex gap-1"><input aria-label="Manual close price" inputMode="decimal" value={closePx} onChange={(e) => setClosePx(e.target.value)} className="num w-24 rounded border border-border bg-surface-2 px-2 py-1 text-xs" /><Button onClick={() => close.mutate()} disabled={!(Number(closePx) > 0) || close.isPending} data-testid="sim-close">Close manually</Button></span> : null}
        {update.isSuccess ? <span data-testid="update-result" className="text-xs text-muted">{update.data.new_events} new events</span> : null}
        {replay.isSuccess ? <span data-testid="replay-result" className={`text-xs ${replay.data.match ? 'text-up' : 'text-down'}`}>{replay.data.match ? `MATCH (${replay.data.n_events} events)` : `DIFFERENCES: ${replay.data.differences.join('; ')}`}</span> : null}
        {[update, cancel, close].some((m) => m.isError) ? <span role="alert" className="text-xs text-down">{((([update, cancel, close].find((m) => m.isError)?.error) ?? new Error('failed')) as ApiError).message}</span> : null}
      </div>
      <Card><CardHeader title="Price since the decision" sub={`levels fixed at T0 · ${bars.length} completed bars`} /><CardBody>
        <SimChart bars={bars} levels={levels} />
        <ul data-testid="sim-levels" className="num mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">{levels.map((l) => <li key={l.label}>{l.label} {fmtNum(l.price)}</li>)}</ul>
      </CardBody></Card>
      <Card><CardHeader title="Performance" sub={last ? `evaluated ${last.evaluated_at} · ${last.details?.return_basis ?? ''}` : 'not evaluated yet'} /><CardBody data-testid="sim-performance">{last ? dl([
        ['Return', fmtPct(last.realized_return, 1)], ['Excess vs benchmark', fmtPct(last.excess_return_vs_benchmark, 1)], ['R', fmtR(last.realized_r)], ['MAE', `${fmtPct(ex.mae_pct, 1)} · ${fmtR(ex.mae_r)}`],
        ['MFE', `${fmtPct(ex.mfe_pct, 1)} · ${fmtR(ex.mfe_r)}`], ['Max drawdown', fmtPct(last.max_drawdown, 1)], ['Days waiting entry', last.days_to_entry], ['Bars to entry', last.bars_to_entry ?? '—'], ['Holding (days)', last.holding_period],
        ['Entry', last.entry_price !== null ? `${fmtNum(last.entry_price)} · ${last.details?.fills?.entry.method ?? ''}` : 'not entered'], ['Targets touched', last.details?.targets_touched?.length ? last.details.targets_touched.join(', ') : 'none'],
        ['Position remaining', last.details?.position_remaining !== undefined && last.details.position_remaining !== null ? fmtPct(last.details.position_remaining, 0) : '—'], ['Execution outcome', last.execution_outcome ?? '—'],
        ['Prediction outcome', last.prediction_outcome ?? 'n/a (NOT_YET_VALIDATED)'],
      ]) : <p className="text-xs text-muted">Press «Update now» to apply the daily bars since the decision.</p>}
      {last?.details?.ambiguity ? <p data-testid="ambiguity" className="mt-2 text-xs text-warn">AMBIGUOUS INTRABAR ({last.details.ambiguity.kind}): the order inside the daily bar cannot be known. Readings kept: {last.details.ambiguity.scenarios.map((x) => `${x.order} ${fmtR(x.realized_r)}`).join(' · ')}</p> : null}
      </CardBody></Card>
      <Card><CardHeader title="Timeline" sub="from the append-only event log" /><CardBody><ol data-testid="sim-timeline" className="space-y-1 text-xs">{timeline.map(({ e, text }) => <li key={e.sequence}><span className="num text-muted">{e.date}</span> <span className="text-[10px] text-muted">#{e.sequence}</span> {text}</li>)}</ol></CardBody></Card>
      <Card><CardHeader title="Analysis" right={<Segmented label="Analysis tab" value={tab} options={TABS} onChange={setTab} />} /><CardBody className="space-y-3">
        {tab === 'Decision snapshot' ? (
          <div data-testid="tab-t0" className="space-y-3 text-xs">
            <p className="text-muted">Exactly what PITQuant knew at {s.decision_at}. It never changes after creation (hash {s.snapshot_hash?.slice(0, 12) ?? 'n/a'}…).</p>
            {dl([['Price', fmtNum(s.price_snapshot.price as number)], ['Trend', String(((s.technical_snapshot as { trend?: { state?: string } }).trend?.state) ?? '—')], ['Fundamentals', String(s.fundamental_snapshot.status ?? '—')], ['Valuation', String(s.valuation_snapshot.status ?? '—')], ['Data quality', String(s.data_quality.overall ?? '—')], ['Prediction', 'NOT YET VALIDATED']])}
            <details><summary className="cursor-pointer text-muted">Raw frozen snapshots</summary><pre className="overflow-x-auto rounded bg-surface-2 p-2">{JSON.stringify({ technical: s.technical_snapshot, fundamental: s.fundamental_snapshot, valuation: s.valuation_snapshot, support_resistance: s.support_resistance_snapshot, trade_plan: s.trade_plan_snapshot }, null, 1)}</pre></details>
          </div>) : null}
        {tab === 'Recorded observations' ? (
          <div data-testid="tab-observations" className="space-y-2 text-xs">
            <p className="text-muted">HISTORICAL and immutable: each one is the analysis as known at that bar date (point in time), recorded with the versions that produced it. They are never recomputed.</p>
            {evolution.length === 0 ? <p data-testid="obs-empty" className="text-muted">No observation recorded yet (cadence: T+1, T+5, T+20, every 20 bars, key events and the final state). Press «Update now».</p> : evolution.map((e) => (
              <div key={e.observation_id} data-testid="obs-row" className="rounded border border-border p-2">
                <div><b>{e.label}</b> · bar {e.bar_date} · schema {e.observation_schema_version ?? '—'} · analyzer {e.analyzer_version ?? '—'} · features {e.feature_version ?? '—'}</div>
                <div className="mt-1 flex flex-wrap gap-1">{e.facts.length ? e.facts.map((f) => <Badge key={f.fact} tone="neutral" title={f.definition}>{f.fact}</Badge>) : <span className="text-muted">no descriptive fact vs T0</span>}</div>
              </div>))}
          </div>) : null}
        {tab === 'Changes' ? (
          <div data-testid="tab-changes" className="space-y-2 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <label>From <select aria-label="Changes from" value={fromKey} onChange={(e) => setFromKey(e.target.value)} className="rounded border border-border bg-surface-2 px-1 py-0.5">{[...snaps.entries()].map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
              <label>To <select aria-label="Changes to" value={toKey} onChange={(e) => setToKey(e.target.value)} className="rounded border border-border bg-surface-2 px-1 py-0.5"><option value="LATEST">Latest ({snaps.get(latestKey)?.label})</option>{[...snaps.entries()].map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
              <Badge tone={toSnap.source === 'CURRENT' ? 'warn' : 'info'} data-testid="to-source">{toSnap.source === 'CURRENT' ? 'CURRENT — not known on any earlier date' : toSnap.source === 'T0' ? 'T0 — frozen' : 'RECORDED — historical'}</Badge>
            </div>
            <table className="w-full"><thead><tr>{['Metric', fromSnap.source === 'T0' ? 'T0' : fromSnap.label, toSnap.label, 'Change'].map((h, i) => <th key={i} className="py-1 text-left font-medium text-muted">{h}</th>)}</tr></thead><tbody>{rows.map((r) => <tr key={r.metric} className="border-t border-border"><td className="py-1">{r.metric}</td>{[r.from, r.to].map((v, i) => <td key={i} className="num">{v === null ? '—' : r.kind === 'pct' && typeof v === 'number' ? fmtPct(v, 2) : typeof v === 'number' ? fmtNum(v) : v}</td>)}<td className="num">{r.change === null ? '—' : r.kind === 'pct' ? fmtPct(r.change, 2, true) : r.change.toFixed(2)}</td></tr>)}</tbody></table>
            <div data-testid="thesis-facts" className="space-y-1">{shownFacts.length ? shownFacts.map((f) => <div key={f.fact}><Badge tone="neutral">{f.fact}</Badge> <span className="text-muted">{f.definition} — descriptive evidence, not a cause</span></div>) : <span className="text-muted">No descriptive fact for this pair.</span>}</div>
          </div>) : null}
        {tab === 'Current analysis' ? (
          <div data-testid="tab-current" className="space-y-2">
            <p className="text-xs font-semibold text-warn">CURRENT ANALYSIS — computed now with today&apos;s Analyzer. It was NOT known on any earlier date and is never stored as a historical observation.</p>
            <pre className="overflow-x-auto rounded bg-surface-2 p-2 text-xs">{JSON.stringify(q.data.analysis_now, null, 1)}</pre>
          </div>) : null}
        {tab === 'Plan comparison' ? <PlanComparison c={comparison} /> : null}
        {tab === 'Post-mortem' ? <PostMortemPanel id={id} closed={closed} /> : null}
        {tab === 'Provenance' ? (
          <div data-testid="tab-provenance" className="space-y-2 text-xs">
            <div data-testid="engine-provenance" className="flex gap-6 rounded border border-border p-2"><div><div className="text-muted">Simulation Engine</div><div className="num text-base font-semibold">{s.simulation_engine_version ?? explain.versions.simulation_engine ?? 'v1'}</div></div><div><div className="text-muted">Event Schema</div><div className="num text-base font-semibold">{explain.versions.event_schema ?? '1'}</div></div><p className="text-muted">Pinned at creation; it never changes. A future engine only applies to NEW simulations.</p></div>
            <p>Explain Simulation: every source and version behind these numbers. Snapshot hash <span className="num">{explain.snapshot_hash ?? 'n/a'}</span> · verified: <b>{String(explain.snapshot_verified)}</b> · {explain.events} events.</p>
            {dl(Object.entries(explain.versions).map(([k, v]) => [k.replaceAll('_', ' '), v] as [string, string | null]))}
            <pre className="overflow-x-auto rounded bg-surface-2 p-2">{JSON.stringify(explain.provenance, null, 1)}</pre>
          </div>) : null}
      </CardBody></Card>
    </div>
  )
}
