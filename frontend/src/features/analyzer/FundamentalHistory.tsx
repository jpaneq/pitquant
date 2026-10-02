import { useState } from 'react'
import { useFundamentalHistory } from '../../api/hooks'
import { Card, CardBody, CardHeader, PanelError, Segmented, Skeleton } from '../../components/ui/primitives'
import { SeriesChart } from './SeriesChart'

const CHARTS: [string, string, 'bar' | 'line', boolean?][] = [
  ['revenue', 'Revenue', 'bar'], ['operating_income', 'Operating income', 'bar'], ['net_income', 'Net income', 'bar'], ['fcf', 'Free cash flow', 'bar'],
  ['operating_margin', 'Operating margin', 'line', true], ['fcf_margin', 'FCF margin', 'line', true], ['shares_outstanding', 'Shares outstanding', 'line'], ['total_debt', 'Debt', 'line'], ['cash', 'Cash', 'line'],
]
export function FundamentalHistory({ sec }: { sec: string }) {
  const [period, setPeriod] = useState<'quarterly' | 'annual'>('quarterly')
  const q = useFundamentalHistory(sec, period)
  return (
    <Card>
      <CardHeader title="Fundamental history" sub={q.data?.status === 'OK' ? 'SEC · discrete quarters derived from YTD facts · latest revision known' : undefined} right={<Segmented label="Period" value={period} options={['quarterly', 'annual'] as const} onChange={setPeriod} />} />
      <CardBody>
        {q.isPending ? <Skeleton className="h-48" /> : q.isError ? <PanelError what="Fundamental history" error={q.error} onRetry={() => q.refetch()} /> : q.data?.status !== 'OK' ? <div className="text-sm text-muted">No SEC history for this security.</div> : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {CHARTS.map(([k, t, kind, pct]) => <SeriesChart key={k} title={t} points={q.data!.series[k] ?? []} kind={kind} percent={pct} />)}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
