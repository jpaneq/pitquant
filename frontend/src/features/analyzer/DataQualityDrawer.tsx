import { useDataQuality } from '../../api/hooks'
import { Badge, Button, PanelError, Skeleton } from '../../components/ui/primitives'

export function DataQualityDrawer({ sec, open, onClose }: { sec: string; open: boolean; onClose: () => void }) {
  const q = useDataQuality(sec, open)
  if (!open) return null
  const d = q.data
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/40" onClick={onClose}>
      <aside role="dialog" aria-label="Data quality" aria-modal className="h-full w-full max-w-md overflow-auto border-l border-border bg-surface p-4" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Data quality</h2>
          <Button onClick={onClose}>Close</Button>
        </div>
        {q.isPending ? <Skeleton className="h-40" /> : q.isError ? <PanelError what="Data quality" error={q.error} onRetry={() => q.refetch()} /> : d ? (
          <div className="space-y-4 text-xs">
            <div>Overall: <Badge tone={d.overall.label === 'High' ? 'up' : d.overall.label === 'Low' ? 'warn' : 'info'}>{d.overall.label}</Badge>{d.overall.warnings.map((w) => <div key={w} className="mt-1 text-warn">{w}</div>)}</div>
            {Object.entries(d.panels).map(([name, p]) => (
              <section key={name} className="rounded-md border border-border p-3">
                <div className="mb-1 flex items-center justify-between"><b className="capitalize">{name}</b>{p.quality ? <Badge>{String(p.quality)}</Badge> : null}</div>
                <pre className="num whitespace-pre-wrap break-words text-[11px] text-muted">{JSON.stringify(Object.fromEntries(Object.entries(p).filter(([k]) => k !== 'quality')), null, 1)}</pre>
              </section>
            ))}
            <section className="rounded-md border border-border p-3">
              <b>Corporate actions applied</b>
              {d.corporate_actions.length === 0 ? <div className="text-muted">none in range</div> : d.corporate_actions.map((a) => <div key={a.date + a.kind} className="num">{a.date} · {a.kind}{a.ratio ? ` ×${a.ratio}` : ''}{a.cash ? ` ${a.cash}` : ''} · {a.tier}</div>)}
            </section>
            <section className="rounded-md border border-border p-3">
              <b>Providers</b>
              {d.providers.map((p) => <div key={p.provider} className="flex justify-between"><span>{p.provider}{p.env_var ? <code className="num ml-1 text-muted">{p.env_var}</code> : null}</span><Badge tone={p.configured ? 'up' : 'neutral'}>{p.configured ? 'configured' : 'not set'}</Badge></div>)}
            </section>
          </div>
        ) : null}
      </aside>
    </div>
  )
}
