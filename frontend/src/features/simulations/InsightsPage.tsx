import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { Badge, Card, CardBody, CardHeader, PanelError, Segmented, Skeleton } from '../../components/ui/primitives'
import { fmtPct } from '../../lib/format'
import { fmtR } from '../../lib/simulation'
import { PaperBanner } from './Banner'
import type { Insights } from './types'

const med = (x?: { mean: number | null; median: number | null }, pct = true) => (x ? `${pct ? fmtPct(x.mean, 1) : fmtR(x.mean)} / ${pct ? fmtPct(x.median, 1) : fmtR(x.median)}` : '—')

/** Descriptive segmentation of the paper trades. No recommendation, no model feedback; a small segment shows INSUFFICIENT_SAMPLE instead of numbers. */
export function InsightsPage() {
  const [by, setBy] = useState('setup_type')
  const q = useQuery({ queryKey: ['sim-insights', by], queryFn: ({ signal }) => api<Insights>(`/simulations/insights?by=${by}`, signal) })
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PaperBanner />
      <div className="flex items-center gap-3"><h1 className="text-xl font-semibold">Simulation insights</h1><Link className="text-xs text-accent underline" to="/simulations">← Dashboard</Link></div>
      <p className="text-xs text-muted">Descriptive statistics of paper trades. Not a recommendation, not a validation of the algorithm, never a training label.</p>
      {q.isPending ? <Skeleton className="h-40" /> : q.isError ? <PanelError what="Insights" error={q.error} onRetry={() => q.refetch()} /> : (
        <>
          <Segmented label="Segment by" value={by} options={q.data.available_segmentations} onChange={setBy} />
          <Card><CardHeader title={`By ${by.replaceAll('_', ' ')}`} sub={`statistics need at least ${q.data.min_n} entered trades per segment`} /><CardBody className="overflow-x-auto p-0">
            {q.data.segments.length === 0 ? <p data-testid="insights-empty" className="p-4 text-xs text-muted">No simulation yet.</p> : (
              <table data-testid="insights-table" className="w-full text-xs">
                <thead><tr>{['Segment', 'N', 'Entered', 'Return mean / median', 'R mean / median', 'MAE mean / median', 'MFE mean / median', 'Stop rate', 'Target-touch rate', 'Expiration', 'Ambiguous'].map((h) => <th key={h} className="px-3 py-2 text-left font-medium text-muted">{h}</th>)}</tr></thead>
                <tbody>{q.data.segments.map((r) => (
                  <tr key={r.segment} className="border-t border-border" data-sample={r.sample}>
                    <td className="px-3 py-2">{r.segment}</td><td className="num px-3 py-2">{r.n}</td><td className="num px-3 py-2">{r.n_entered}</td>
                    {r.sample === 'OK' ? (<>
                      <td className="num px-3 py-2">{med(r.return)}</td><td className="num px-3 py-2">{med(r.r, false)}</td><td className="num px-3 py-2">{med(r.mae_pct)}</td><td className="num px-3 py-2">{med(r.mfe_pct)}</td>
                      <td className="num px-3 py-2">{fmtPct(r.stop_rate, 0)}</td><td className="num px-3 py-2">{fmtPct(r.target_touch_rate, 0)}</td><td className="num px-3 py-2">{fmtPct(r.expiration_rate, 0)}</td><td className="num px-3 py-2">{fmtPct(r.ambiguous_rate, 0)}</td>
                    </>) : <td colSpan={8} className="px-3 py-2"><Badge tone="neutral">INSUFFICIENT SAMPLE</Badge></td>}
                  </tr>))}</tbody>
              </table>)}
          </CardBody></Card>
        </>
      )}
    </div>
  )
}
