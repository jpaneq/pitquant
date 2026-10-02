import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'

type Explain = { nature: string; decision_at: string; engine_versions: Record<string, string>; market_data: { sources: string[]; bars: number; last_session: string | null; series: string } }

/** Provenance on demand: fetched only when opened, never part of the first paint. */
export function ExplainDetails({ sec, panel }: { sec: string; panel: 'analysis' | 'trade-plan' }) {
  const [open, setOpen] = useState(false)
  const q = useQuery({ queryKey: ['explain', sec, panel], queryFn: ({ signal }) => api<Explain>(`/analyzer/${encodeURIComponent(sec)}/explain?panel=${panel}`, signal), enabled: open, staleTime: 60_000 })
  return (
    <details className="mt-3 text-xs" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className="cursor-pointer text-accent">Why? Provenance of this {panel === 'analysis' ? 'analysis' : 'plan'}</summary>
      {q.isPending && open ? <p className="mt-2 text-muted">Loading…</p> : q.isError ? <p className="mt-2 text-down">Provenance unavailable.</p> : q.data ? (
        <div className="mt-2 space-y-1 text-muted">
          <p>{q.data.nature}</p>
          <p>Decision at <span className="font-mono">{q.data.decision_at}</span> · {q.data.market_data.bars} completed bars (last {q.data.market_data.last_session ?? '—'}) from {q.data.market_data.sources.join(', ') || 'no source'}.</p>
          <p>{q.data.market_data.series}.</p>
          <p className="font-mono">{Object.entries(q.data.engine_versions).map(([k, v]) => `${k}=${v}`).join(' · ')}</p>
        </div>
      ) : null}
    </details>
  )
}
