import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { InfoTip } from '../../components/ui/primitives'
import { GLOSSARY } from '../../lib/glossary'

type Plan = { status: string; reason?: string; entry_zone_low?: number; stop_loss?: number; target_1?: number; target_2?: number; rule?: string; risk_reward?: { tp1: number; tp2: number } }
type Resp = { as_of_bar: string; plan: Plan; label: string; price_basis: string }
const n = (v?: number) => (v == null ? '—' : v.toLocaleString('en-US', { maximumFractionDigits: 2 }))

/** Plan de operación de BTC sobre la última vela diaria cerrada: no hace falta congelar nada para verlo. */
export function BtcLivePlan() {
  const q = useQuery({ queryKey: ['btc-live-plan'], queryFn: () => api<Resp>('/btc/trade-plan'), refetchInterval: 5 * 60_000, retry: false })
  return (
    <section aria-label="Plan de operación BTC" className="rounded-lg border border-border bg-surface p-4">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">Plan de operación BTC (largo)<InfoTip term={GLOSSARY['trade plan (long)']} /></h2>
      <p className="my-1 text-xs text-warn">{q.data?.label ?? 'RULE_BASED · NOT BACKTEST VALIDATED'} · calculado con la última vela diaria cerrada{q.data ? ` (${q.data.as_of_bar.slice(0, 10)})` : ''}</p>
      {q.isError ? <p role="status" className="text-xs text-warn">Plan no disponible: faltan datos diarios reales archivados.</p> : null}
      {q.data?.plan.status === 'BLOCKED_BY_DATA' ? <p className="text-xs text-warn">Sin plan: {q.data.plan.reason}</p> : null}
      {q.data && q.data.plan.status !== 'BLOCKED_BY_DATA' ? (
        <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-5">
          {[['Entrada', q.data.plan.entry_zone_low], ['Stop', q.data.plan.stop_loss], ['Objetivo 1 (1R)', q.data.plan.target_1], ['Objetivo 2 (2R)', q.data.plan.target_2]].map(([k, v]) => <div key={String(k)}><dt className="text-xs text-muted">{k}</dt><dd className="num">{n(v as number | undefined)}</dd></div>)}
          <div><dt className="text-xs text-muted">Regla</dt><dd className="text-xs">{q.data.plan.rule}</dd></div>
        </dl>
      ) : null}
    </section>
  )
}
