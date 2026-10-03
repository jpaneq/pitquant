import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { Badge, Card, CardBody, CardHeader, PanelError, Skeleton } from '../../components/ui/primitives'
import { fmtPct } from '../../lib/format'
import { PaperBanner } from './Banner'
import type { SimRow, SimSummary } from './types'

const GROUPS = ['OPEN', 'CLOSED', 'WAITING_ENTRY', 'STOPPED', 'TP1', 'TP2'] as const
const dash = (x: number | null) => (x === null || x === undefined ? '—' : x.toFixed(2))

export function SimulationsPage() {
  const sum = useQuery({ queryKey: ['sim-summary'], queryFn: ({ signal }) => api<SimSummary>('/simulations/summary', signal) })
  const list = useQuery({ queryKey: ['sim-list'], queryFn: ({ signal }) => api<SimRow[]>('/simulations', signal) })
  const ev = sum.data?.evidence
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PaperBanner />
      <div><h1 className="text-xl font-semibold">Simulations</h1><p className="text-xs text-muted">Paper trading and forward validation. Nothing here feeds a model, a dataset or the Champion.</p></div>
      {sum.isPending ? <Skeleton className="h-24" /> : sum.isError ? <PanelError what="Simulation summary" error={sum.error} onRetry={() => sum.refetch()} /> : (
        <Card>
          <CardHeader title="Summary" sub="Only simulated trades that were really entered and closed count in the statistics" />
          <CardBody>
            <div className="flex flex-wrap gap-2">{GROUPS.map((g) => <Badge key={g} tone="neutral">{g.replace('_', ' ')} {sum.data.groups[g] ?? 0}</Badge>)}</div>
            {ev?.stats_available ? (
              <dl data-testid="sim-stats" className="num mt-3 grid grid-cols-3 gap-3 text-xs sm:grid-cols-6">
                <div><dt className="text-muted">Hit rate</dt><dd>{fmtPct(ev.hit_rate, 0)}</dd></div>
                <div><dt className="text-muted">Mean R</dt><dd>{dash(ev.mean_r)}</dd></div>
                <div><dt className="text-muted">Mean return</dt><dd>{fmtPct(ev.mean_return, 1)}</dd></div>
                <div><dt className="text-muted">Mean excess</dt><dd>{fmtPct(ev.mean_excess_return, 1)}</dd></div>
                <div><dt className="text-muted">Mean MAE</dt><dd>{fmtPct(ev.mean_mae, 1)}</dd></div>
                <div><dt className="text-muted">Mean MFE</dt><dd>{fmtPct(ev.mean_mfe, 1)}</dd></div>
              </dl>
            ) : (
              <p data-testid="sim-insufficient" className="mt-3 text-xs text-muted">No statistics yet: {ev?.n_entered_closed ?? 0} entered and closed paper trades, at least {ev?.min_n ?? 10} are needed. Nothing is shown rather than a number from a handful of trades.</p>
            )}
          </CardBody>
        </Card>
      )}
      {list.isPending ? <Skeleton className="h-40" /> : list.isError ? <PanelError what="Simulations" error={list.error} onRetry={() => list.refetch()} /> : list.data.length === 0 ? (
        <Card><CardBody data-testid="sim-empty" className="text-sm text-muted">No paper trades yet. Open a security in the Analyzer and press «Simulate trade».</CardBody></Card>
      ) : (
        <Card><CardBody className="overflow-x-auto p-0">
          <table className="w-full text-xs">
            <thead><tr>{['Created', 'State', 'Plan', 'Entry zone', 'Stop', 'Target 1', 'R', 'Return'].map((h) => <th key={h} className="px-3 py-2 text-left font-medium text-muted">{h}</th>)}</tr></thead>
            <tbody>{list.data.map((s) => (
              <tr key={s.simulation_id} className="border-t border-border">
                <td className="px-3 py-2"><Link className="text-accent underline" to={`/simulations/${s.simulation_id}`}>{s.created_at.slice(0, 16)}</Link></td>
                <td className="px-3 py-2"><Badge tone="neutral">{s.state}</Badge></td>
                <td className="px-3 py-2">{s.plan_origin}</td>
                <td className="num px-3 py-2">{s.entry_zone[0].toFixed(2)}–{s.entry_zone[1].toFixed(2)}</td>
                <td className="num px-3 py-2">{s.stop_loss.toFixed(2)}</td>
                <td className="num px-3 py-2">{s.target_1.toFixed(2)}</td>
                <td className="num px-3 py-2">{dash(s.outcome?.realized_r ?? null)}</td>
                <td className="num px-3 py-2">{fmtPct(s.outcome?.realized_return ?? null, 1)}</td>
              </tr>
            ))}</tbody>
          </table>
        </CardBody></Card>
      )}
    </div>
  )
}
