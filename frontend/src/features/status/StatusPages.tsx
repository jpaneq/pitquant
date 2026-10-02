import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { useTheme } from '../../hooks/useTheme'
import { Badge, Button, Card, CardBody, CardHeader, PanelError, Skeleton } from '../../components/ui/primitives'

type St = { as_of: string; providers: { provider: string; env_var: string | null; configured: boolean; note?: string }[]; data_notice: { live_reference: string; required_env: string | null; mode: string }; engine_versions: Record<string, string>; holdout: { state: string; start: string; end: string } }

export function StatusPage() {
  const q = useQuery({ queryKey: ['analyzer-status-page'], queryFn: ({ signal }) => api<St>('/analyzer/status', signal) })
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-xl font-semibold">Data Status</h1>
      {q.isPending ? <Skeleton className="h-48" /> : q.isError ? <PanelError what="Status" error={q.error} onRetry={() => q.refetch()} /> : (
        <>
          <Card><CardHeader title="Live reference" right={<Badge tone={q.data.data_notice.live_reference === 'CONFIGURED' ? 'up' : 'warn'}>{q.data.data_notice.live_reference}</Badge>} sub={q.data.data_notice.mode} /></Card>
          <Card>
            <CardHeader title="Providers" sub="Credentials are read from the environment; values are never shown." />
            <CardBody className="p-0"><table className="w-full text-xs"><tbody>
              {q.data.providers.map((p) => <tr key={p.provider} className="border-t border-border first:border-0"><td className="px-4 py-2">{p.provider}</td><td className="font-mono text-muted">{p.env_var ?? ''}</td><td className="px-4 py-2 text-right"><Badge tone={p.configured ? 'up' : 'neutral'}>{p.configured ? 'configured' : 'not set'}</Badge></td></tr>)}
            </tbody></table></CardBody>
          </Card>
          <Card><CardHeader title="Engine versions" /><CardBody className="num text-xs text-muted">{Object.entries(q.data.engine_versions).map(([k, v]) => <div key={k}>{k}: {v}</div>)}</CardBody></Card>
        </>
      )}
    </div>
  )
}

export function SettingsPage() {
  const { dark, toggle } = useTheme()
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-xl font-semibold">Settings</h1>
      <Card><CardBody className="flex items-center justify-between text-sm"><span>Theme</span><Button onClick={toggle}>{dark ? 'Switch to light' : 'Switch to dark'}</Button></CardBody></Card>
    </div>
  )
}
