import { SimulateTrade } from '../simulations/SimulateTrade'
import { ExplainDetails } from './ExplainDetails'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useSummary } from '../../api/hooks'
import { ErrorBoundary } from '../../components/ErrorBoundary'
import { Button, PanelError, Skeleton } from '../../components/ui/primitives'
import { DataQualityDrawer } from './DataQualityDrawer'
import { FundamentalHistory } from './FundamentalHistory'
import { MarketChart } from './MarketChart'
import { AnalysisSummary, FilingsPanel, FundamentalsCard, PredictionPanel, RiskCard, TechnicalDetail, TechnicalsCard, ValuationCard } from './Panels'
import { ReportButton } from './ReportButton'
import { SecurityHeader } from './SecurityHeader'
import { TradePlanSection } from './TradePlanSection'

const Safe = ({ what, children }: { what: string; children: React.ReactNode }) => <ErrorBoundary what={what}>{children}</ErrorBoundary>

export function AnalyzerPage() {
  const { id = '' } = useParams()
  const q = useSummary(id)
  const [dq, setDq] = useState(false)
  if (q.isPending) return <div className="space-y-4"><Skeleton className="h-16" /><Skeleton className="h-[460px]" /><Skeleton className="h-24" /></div>
  if (q.isError) {
    const detail = (q.error as { detail?: { message?: string; suggestions?: { ticker: string; name: string }[] } }).detail
    return (
      <div className="mx-auto max-w-xl space-y-3">
        <PanelError what={`Analyzer for “${id}”`} error={q.error} onRetry={() => q.refetch()} />
        {detail?.suggestions?.length ? <div className="text-sm">Did you mean: {detail.suggestions.map((s) => <a key={s.ticker} className="mr-3 text-accent underline" href={`/analyzer/${s.ticker}`}>{s.ticker} — {s.name}</a>)}</div> : null}
      </div>
    )
  }
  const s = q.data
  const special = s.security.profile_type !== 'STANDARD_CORPORATE'
  const noPrice = s.quote.status !== 'OK'
  return (
    <div className="mx-auto max-w-[1500px] space-y-4">
      <Safe what="Security header"><SecurityHeader summary={s} sec={id} onDataQuality={() => setDq(true)} /></Safe>
      <Safe what="Simulate"><SimulateTrade sec={id} summary={s} /></Safe>
      {s.warnings.length ? <div role="status" className="space-y-1 rounded-md border border-warn/30 bg-warn/5 px-3 py-2 text-xs text-warn">{s.warnings.map((w) => <div key={w}>{w}</div>)}</div> : null}
      <Safe what="Price chart">{noPrice ? <div className="rounded-lg border border-border bg-surface p-8 text-center text-sm text-muted">No price chart: no market-data source has bars for {s.security.ticker}. Fundamentals below are real SEC data.</div> : <MarketChart sec={id} />}</Safe>
      <Safe what="Analysis summary"><AnalysisSummary summary={s} /><ExplainDetails sec={id} panel="analysis" /></Safe>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Safe what="Fundamentals"><FundamentalsCard sec={id} special={special} /></Safe>
        <Safe what="Technicals"><TechnicalsCard sec={id} /></Safe>
        <Safe what="Valuation"><ValuationCard sec={id} /></Safe>
        <Safe what="Risk"><RiskCard sec={id} /></Safe>
      </div>
      <Safe what="Fundamental history"><FundamentalHistory sec={id} /></Safe>
      <Safe what="Technical detail"><TechnicalDetail sec={id} /></Safe>
      <Safe what="Trade plan"><TradePlanSection sec={id} /></Safe>
      <Safe what="Prediction"><PredictionPanel sec={id} /></Safe>
      <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
        <Safe what="Filings"><FilingsPanel sec={id} /></Safe>
        <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">Data quality & export</div>
          <Button onClick={() => setDq(true)}>Open data quality</Button>
          <ReportButton sec={id} />
          <div className="num text-[10px] leading-relaxed text-muted">{Object.entries(s.engine_versions).map(([k, v]) => <div key={k}>{k}: {v}</div>)}</div>
        </div>
      </div>
      <DataQualityDrawer sec={id} open={dq} onClose={() => setDq(false)} />
    </div>
  )
}
