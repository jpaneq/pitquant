import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import { Badge, Card, CardBody, CardHeader, PanelError, Segmented, Skeleton } from '../../components/ui/primitives'

type DevStatus = {
  components: Record<string, { status: string; gaps: string[] }>
  research: { flags: Record<string, boolean>; status: Record<string, string>; reasons: Record<string, string[]>; metrics: Record<string, unknown> }
  holdout: { state: string; start: string; end: string; outcomes_exposed: boolean }
}
type LabStatus = { holdout: string; holdout_range: string[]; flags: Record<string, boolean | null>; reasons: Record<string, string[]> }
type Row = Record<string, unknown>
const TABS = ['Overview', 'Experiments', 'Dataset', 'Features', 'Models', 'Backtests', 'Audit'] as const
type Tab = (typeof TABS)[number]

function useLab<T>(path: string) {
  return useQuery({ queryKey: ['research', path], queryFn: ({ signal }) => api<T>(path, signal), staleTime: 60_000 })
}

function Empty({ what, why }: { what: string; why: string }) {
  return (
    <Card><CardBody className="text-sm text-muted" data-testid="empty-state">
      <b className="text-fg">No {what} yet.</b> {why} Nothing is shown rather than invented.
    </CardBody></Card>
  )
}

function Table({ rows, cols }: { rows: Row[]; cols: string[] }) {
  return (
    <Card><CardBody className="overflow-x-auto p-0">
      <table className="w-full text-xs">
        <thead><tr>{cols.map((c) => <th key={c} className="px-3 py-2 text-left font-medium text-muted">{c}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={i} className="border-t border-border">{cols.map((c) => <td key={c} className="px-3 py-2 font-mono">{String(r[c] ?? '—')}</td>)}</tr>
        ))}</tbody>
      </table>
    </CardBody></Card>
  )
}

function Section<T>({ path, what, why, render }: { path: string; what: string; why: string; render: (d: T) => React.ReactNode }) {
  const q = useLab<T>(path)
  if (q.isPending) return <Skeleton className="h-40" />
  if (q.isError) return <PanelError what={what} error={q.error} onRetry={() => q.refetch()} />
  return <>{render(q.data) ?? <Empty what={what} why={why} />}</>
}

function Experiments() {
  return <Section<Row[]> path="/research/experiments" what="experiments" why="No experiment has been defined: the data gates are still closed." render={(d) => d.length ? <Table rows={d} cols={['name', 'status', 'commit_sha', 'dataset_hash', 'window_kind', 'purge_months', 'embargo_months', 'seed']} /> : null} />
}
function Dataset() {
  return <Section<Row[]> path="/research/datasets" what="dataset versions" why="The Dataset Builder has not produced a persisted dataset." render={(d) => d.length ? <Table rows={d} cols={['dataset_hash', 'universe', 'start_date', 'end_date', 'n_rows', 'n_eligible', 'holdout_dates_excluded']} /> : null} />
}
function Features() {
  return <Section<{ catalog: string[]; feature_sets: Row[]; labels: Row[] }> path="/research/features" what="feature sets" why="" render={(d) => (
    <div className="space-y-3">
      <Card>
        <CardHeader title="Raw feature catalog" sub={`${d.catalog.length} features · raw, point-in-time. Human-analysis labels are never features.`} />
        <CardBody className="flex flex-wrap gap-1.5">{d.catalog.map((f) => <Badge key={f} tone="neutral">{f}</Badge>)}</CardBody>
      </Card>
      {d.labels.length ? <Table rows={d.labels} cols={['label_version', 'horizon_months', 'target_kind', 'benchmark', 'benchmark_type']} /> : <Empty what="label definitions" why="None has been registered." />}
    </div>
  )} />
}
function Models() {
  return <Section<{ predefined_baselines: Row[]; registered: Row[] }> path="/research/models" what="models" why="" render={(d) => (
    <div className="space-y-3">
      <Card><CardHeader title="Predefined baselines" sub="Fixed grids, defined in advance. Not trained: there is no data to train on." /></Card>
      <Table rows={d.predefined_baselines.map((b) => ({ ...b, trained: 'no' }))} cols={['kind', 'target', 'horizons', 'config_hash', 'trained']} />
      {d.registered.length === 0 && <Empty what="registered models or champion" why="No model has been trained or promoted." />}
    </div>
  )} />
}
function Backtests() {
  return <Section<{ folds: Row[]; metric_sets: Row[] }> path="/research/backtests" what="backtests" why="No walk-forward run exists; `pitquant research-dry-run` only plans folds." render={(d) => d.folds.length || d.metric_sets.length ? <Table rows={d.metric_sets} cols={['metric_set_id', 'experiment_id', 'kind']} /> : null} />
}
function Audit() {
  return <Section<{ holdout: string; holdout_range: string[]; gates: string[]; rules: string[] }> path="/research/audit" what="audit" why="" render={(d) => (
    <div className="space-y-3">
      <Card><CardHeader title="Holdout" right={<Badge tone="up">{d.holdout}</Badge>} sub={`${d.holdout_range.join(' → ')} · never read by any experiment, dashboard or API`} /></Card>
      <Card><CardHeader title="Rules enforced" /><CardBody><ul className="list-disc space-y-1 pl-5 text-xs">{d.rules.map((r) => <li key={r}>{r}</li>)}</ul></CardBody></Card>
      <Card><CardHeader title="Open data gates" sub="FEATURE_RESEARCH_READY_US" /><CardBody><ul className="list-disc space-y-1 pl-5 text-xs text-muted">{d.gates.map((g) => <li key={g}>{g}</li>)}</ul></CardBody></Card>
    </div>
  )} />
}

export function ResearchPage() {
  const [tab, setTab] = useState<Tab>('Overview')
  const dev = useQuery({ queryKey: ['dev-status'], queryFn: ({ signal }) => api<DevStatus>('/dev/status', signal), staleTime: 60_000, enabled: tab === 'Overview' })
  const lab = useLab<LabStatus>('/research/status')
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Research Lab</h1>
          <p className="text-xs text-muted">Point-in-time research, backtests and model governance. Same engines as the Analyzer.</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="up">HOLDOUT SEALED</Badge>
          <Segmented label="Research section" value={tab} options={TABS} onChange={setTab} />
        </div>
      </div>
      {tab === 'Experiments' && <Experiments />}
      {tab === 'Dataset' && <Dataset />}
      {tab === 'Features' && <Features />}
      {tab === 'Models' && <Models />}
      {tab === 'Backtests' && <Backtests />}
      {tab === 'Audit' && <Audit />}
      {tab === 'Overview' && (
        <>
          <Card>
            <CardHeader title="Lab vs data" sub="Software exists; data readiness is a separate, derived fact" />
            <CardBody className="flex flex-wrap gap-2 text-xs">
              {lab.data && Object.entries(lab.data.flags).map(([k, v]) => <span key={k} className="flex items-center gap-1"><span className="font-mono">{k}</span><Badge tone={v ? 'up' : 'neutral'}>{String(v)}</Badge></span>)}
            </CardBody>
          </Card>
          {dev.isPending ? <Skeleton className="h-40" /> : dev.isError ? <PanelError what="Research status" error={dev.error} onRetry={() => dev.refetch()} /> : (
            <Card>
              <CardHeader title="Research readiness gates" sub="Derived from the database, never set by hand" />
              <CardBody className="p-0">
                <table className="w-full text-xs"><tbody>
                  {Object.entries(dev.data.research.flags).map(([k, v]) => (
                    <tr key={k} className="border-t border-border first:border-0 align-top">
                      <td className="px-4 py-2 font-mono">{k}</td>
                      <td className="px-2 py-2"><Badge tone={v ? 'up' : 'neutral'}>{String(v)}</Badge></td>
                      <td className="px-2 py-2 text-muted">{dev.data.research.status[k] ?? ''}</td>
                      <td className="px-4 py-2 text-muted">{(dev.data.research.reasons[k] ?? []).slice(0, 2).join(' · ')}</td>
                    </tr>
                  ))}
                </tbody></table>
              </CardBody>
            </Card>
          )}
          <p className="text-xs text-muted">Time Machine, feature inspector and S&amp;P 500 universe explorer: <a className="text-accent underline" href="/dev/">/dev/</a>.</p>
        </>
      )}
    </div>
  )
}
