import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { Badge, Card, CardBody, CardHeader, PanelError, Skeleton } from '../../components/ui/primitives'
import { fmtPct } from '../../lib/format'
import { fmtR, stateLabel, stateTone } from '../../lib/simulation'
import { PaperBanner } from './Banner'
import type { SimRow, SimSummary } from './types'

const GROUPS = [['OPEN', 'Open'], ['WAITING_ENTRY', 'Waiting entry'], ['CLOSED', 'Closed'], ['STOPPED', 'Stopped'], ['TARGETS_REACHED', 'Targets reached'], ['EXPIRED', 'Expired'], ['AMBIGUOUS_INTRABAR', 'Ambiguous']] as const
const dash = (x: number | null | undefined) => (x === null || x === undefined ? '—' : x.toFixed(2))

/** Cumulative realised R of the closed, entered paper trades in creation order (N shown; no extrapolation). */
function RCurve({ rows }: { rows: SimRow[] }) {
  const pts = rows.filter((r) => r.outcome?.is_closed && r.outcome.realized_r !== null && r.outcome.entry_date).reverse()
  const ys = pts.reduce<number[]>((a, r) => [...a, (a.at(-1) ?? 0) + (r.outcome?.realized_r ?? 0)], [])
  if (ys.length < 2) return <p data-testid="r-curve-empty" className="text-xs text-muted">Cumulative R needs at least two closed, entered trades (now {ys.length}).</p>
  const lo = Math.min(0, ...ys), hi = Math.max(0, ...ys), W = 400, H = 90
  const y = (v: number) => H - ((v - lo) / (hi - lo || 1)) * (H - 10) - 5
  return <svg data-testid="r-curve" role="img" aria-label={`Cumulative realised R over ${ys.length} trades`} viewBox={`0 0 ${W} ${H}`} className="w-full max-w-md"><line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="currentColor" className="text-border" /><polyline fill="none" stroke="currentColor" className="text-accent" strokeWidth="1.5" points={ys.map((v, i) => `${(i / (ys.length - 1)) * (W - 8) + 4},${y(v)}`).join(' ')} /></svg>
}

export function SimulationsPage() {
  const [state, setState] = useState('ALL')
  const [origin, setOrigin] = useState('ALL')
  const sum = useQuery({ queryKey: ['sim-summary'], queryFn: ({ signal }) => api<SimSummary>('/simulations/summary', signal) })
  const list = useQuery({ queryKey: ['sim-list'], queryFn: ({ signal }) => api<SimRow[]>('/simulations', signal) })
  const ev = sum.data?.evidence
  const shown = useMemo(() => (list.data ?? []).filter((r) => (state === 'ALL' || r.state === state) && (origin === 'ALL' || r.plan_origin === origin)), [list.data, state, origin])
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PaperBanner />
      <div className="flex flex-wrap items-center gap-2">
        <div><h1 className="text-xl font-semibold">Simulation Lab</h1><p className="text-xs text-muted">Forward-testing &amp; paper trading. Nothing here feeds a model, a dataset or the Champion.</p></div>
        <Badge tone="warn">PAPER TRADING</Badge><Badge tone="warn">PREDICTION ENGINE NOT YET VALIDATED</Badge><Badge tone="warn">TRADE PLAN RULE-BASED · NOT YET BACKTEST VALIDATED</Badge>
        <Link className="ml-auto text-xs text-accent underline" to="/simulations/insights" data-testid="insights-link">Insights →</Link>
      </div>
      {sum.isPending ? <Skeleton className="h-24" /> : sum.isError ? <PanelError what="Simulation summary" error={sum.error} onRetry={() => sum.refetch()} /> : (
        <Card>
          <CardHeader title="Summary" sub="Only simulated trades that were really entered and closed count in the statistics" />
          <CardBody>
            <div className="flex flex-wrap gap-2">{GROUPS.map(([g, l]) => <Badge key={g} tone="neutral" data-testid={`card-${g}`}>{l} {sum.data.groups[g] ?? 0}</Badge>)}<Badge tone="neutral">N {ev?.n_simulations ?? 0}</Badge></div>
            {ev?.stats_available ? (
              <dl data-testid="sim-stats" className="num mt-3 grid grid-cols-3 gap-3 text-xs sm:grid-cols-6">
                <div><dt className="text-muted">Win rate (N={ev.n_entered_closed})</dt><dd>{fmtPct(ev.hit_rate, 0)}</dd></div>
                <div><dt className="text-muted">Mean R</dt><dd>{dash(ev.mean_r)}</dd></div>
                <div><dt className="text-muted">Mean return</dt><dd>{fmtPct(ev.mean_return, 1)}</dd></div>
                <div><dt className="text-muted">Mean excess</dt><dd>{fmtPct(ev.mean_excess_return, 1)}</dd></div>
                <div><dt className="text-muted">Mean MAE</dt><dd>{fmtPct(ev.mean_mae, 1)}</dd></div>
                <div><dt className="text-muted">Mean MFE</dt><dd>{fmtPct(ev.mean_mfe, 1)}</dd></div>
              </dl>
            ) : (
              <p data-testid="sim-insufficient" className="mt-3 text-xs text-muted">No statistics yet: {ev?.n_entered_closed ?? 0} entered and closed paper trades, at least {ev?.min_n ?? 10} are needed. Nothing is shown rather than a number from a handful of trades.</p>
            )}
            <div className="mt-3"><RCurve rows={list.data ?? []} /></div>
          </CardBody>
        </Card>
      )}
      {list.isPending ? <Skeleton className="h-40" /> : list.isError ? <PanelError what="Simulations" error={list.error} onRetry={() => list.refetch()} /> : list.data.length === 0 ? (
        <Card><CardBody data-testid="sim-empty" className="text-sm text-muted">No paper trades yet. Open a security in the Analyzer and press «Simulate trade».</CardBody></Card>
      ) : (
        <Card>
          <div className="flex flex-wrap gap-3 border-b border-border px-3 py-2 text-xs">
            <label>State <select aria-label="Filter state" value={state} onChange={(e) => setState(e.target.value)} className="rounded border border-border bg-surface-2 px-1 py-0.5"><option>ALL</option>{[...new Set(list.data.map((r) => r.state))].map((s) => <option key={s}>{s}</option>)}</select></label>
            <label>Origin <select aria-label="Filter origin" value={origin} onChange={(e) => setOrigin(e.target.value)} className="rounded border border-border bg-surface-2 px-1 py-0.5"><option>ALL</option><option>PITQUANT</option><option>USER_MODIFIED</option><option>USER_DEFINED</option></select></label>
            <span className="text-muted">{shown.length} of {list.data.length}</span>
          </div>
          <CardBody className="overflow-x-auto p-0">
            <table className="w-full text-xs" data-testid="sim-table">
              <thead><tr>{['Security', 'Created', 'Origin', 'Setup', 'Entry', 'Return', 'R', 'MAE', 'MFE', 'State', 'Days'].map((h) => <th key={h} className="px-3 py-2 text-left font-medium text-muted">{h}</th>)}</tr></thead>
              <tbody>{shown.map((s) => (
                <tr key={s.simulation_id} className="border-t border-border">
                  <td className="px-3 py-2"><Link className="text-accent underline" to={`/simulations/${s.simulation_id}`}>{s.security ?? s.security_id.slice(0, 8)}</Link></td>
                  <td className="num px-3 py-2">{s.created_at.slice(0, 10)}</td>
                  <td className="px-3 py-2">{s.plan_origin}</td>
                  <td className="px-3 py-2">{s.setup_type ?? '—'}</td>
                  <td className="num px-3 py-2">{s.outcome?.entry_price !== null && s.outcome?.entry_price !== undefined ? s.outcome.entry_price.toFixed(2) : `${s.entry_zone[0].toFixed(2)}–${s.entry_zone[1].toFixed(2)}`}</td>
                  <td className="num px-3 py-2">{fmtPct(s.outcome?.realized_return ?? null, 1)}</td>
                  <td className="num px-3 py-2">{fmtR(s.outcome?.realized_r ?? null)}</td>
                  <td className="num px-3 py-2">{fmtPct(s.mae_pct ?? null, 1)}</td>
                  <td className="num px-3 py-2">{fmtPct(s.mfe_pct ?? null, 1)}</td>
                  <td className="px-3 py-2"><Badge tone={stateTone(s.state)}>{stateLabel(s.state)}</Badge></td>
                  <td className="num px-3 py-2">{s.outcome?.holding_period ?? '—'}</td>
                </tr>
              ))}</tbody>
            </table>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
