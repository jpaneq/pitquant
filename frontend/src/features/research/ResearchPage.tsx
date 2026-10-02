import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import { Badge, Card, CardBody, CardHeader, PanelError, Segmented, Skeleton } from '../../components/ui/primitives'

type DevStatus = {
  components: Record<string, { status: string; gaps: string[] }>
  research: { flags: Record<string, boolean>; status: Record<string, string>; reasons: Record<string, string[]>; metrics: Record<string, unknown> }
  holdout: { state: string; start: string; end: string; outcomes_exposed: boolean }
}
const TABS = ['Overview', 'Backtests', 'Models', 'Universes', 'Audit', 'PIT Explorer'] as const

export function ResearchPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>('Overview')
  const q = useQuery({ queryKey: ['dev-status'], queryFn: ({ signal }) => api<DevStatus>('/dev/status', signal), staleTime: 60_000 })
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex items-center justify-between">
        <div><h1 className="text-xl font-semibold">Research Lab</h1><p className="text-xs text-muted">Point-in-time research, backtests and model governance. Uses the same engines as the Analyzer.</p></div>
        <Segmented label="Research section" value={tab} options={TABS} onChange={setTab} />
      </div>
      {tab !== 'Overview' ? (
        <Card><CardBody className="text-sm text-muted">
          {tab === 'PIT Explorer' ? <>Time Machine, feature inspector and S&amp;P 500 universe explorer live in the developer tool: <a className="text-accent underline" href="/dev/">open /dev/</a>.</> : <>{tab}: scaffold only. No backtest, model or champion exists yet; nothing is shown rather than invented.</>}
        </CardBody></Card>
      ) : q.isPending ? <Skeleton className="h-64" /> : q.isError ? <PanelError what="Research status" error={q.error} onRetry={() => q.refetch()} /> : (
        <>
          <Card>
            <CardHeader title="Holdout" right={<Badge tone="up">{q.data.holdout.state}</Badge>} sub={`${q.data.holdout.start} → ${q.data.holdout.end} · outcomes exposed: ${String(q.data.holdout.outcomes_exposed)}`} />
          </Card>
          <Card>
            <CardHeader title="Research readiness gates" sub="Derived from the database, never set by hand" />
            <CardBody className="p-0">
              <table className="w-full text-xs"><tbody>
                {Object.entries(q.data.research.flags).map(([k, v]) => (
                  <tr key={k} className="border-t border-border first:border-0 align-top">
                    <td className="px-4 py-2 font-mono">{k}</td>
                    <td className="px-2 py-2"><Badge tone={v ? 'up' : 'neutral'}>{String(v)}</Badge></td>
                    <td className="px-2 py-2 text-muted">{q.data.research.status[k] ?? ''}</td>
                    <td className="px-4 py-2 text-muted">{(q.data.research.reasons[k] ?? []).slice(0, 2).join(' · ')}</td>
                  </tr>
                ))}
              </tbody></table>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}
