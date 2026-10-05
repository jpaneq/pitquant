import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../../api/client'
import { Badge, Card, CardBody, CardHeader, PanelError, Skeleton } from '../../components/ui/primitives'
import { TradeChart, type TradePayload } from './TradeChart'

type Row = { ref: string; kind: string; date: string; market: string; ticker: string; horizon_months: number | null; decision: string; recommendation: string | null; score: number | null }
const pct = (v: number | null) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)
const STATE: Record<string, string> = { IN_PROGRESS: 'en curso', TARGET_HIT: 'objetivo cumplido', STOP_HIT: 'stop tocado', EXPIRED: 'vencida', AMBIGUOUS_INTRABAR: 'ambigua', NOT_EVALUATED_YET: 'sin evaluar aún', CREATED: 'creada' }

/** Visor visual de operaciones: cada decisión de la rutina (compra o no compra) y cada simulación, con velas, tendencia, entrada, objetivo, stop y salida. */
export function OperacionesPage() {
  const [params, setParams] = useSearchParams()
  const [market, setMarket] = useState('TODOS')
  const [only, setOnly] = useState<'TODAS' | 'COMPRAS' | 'NO COMPRAS'>('TODAS')
  const list = useQuery({ queryKey: ['trades'], queryFn: ({ signal }) => api<Row[]>('/trades?days=365', signal) })
  const ref = params.get('ref') ?? ''
  const chart = useQuery({ queryKey: ['trade-chart', ref], queryFn: ({ signal }) => api<TradePayload>(`/trades/chart?ref=${encodeURIComponent(ref)}`, signal), enabled: !!ref })
  const rows = useMemo(() => (list.data ?? []).filter((r) => (market === 'TODOS' || r.market === market) && (only === 'TODAS' || (only === 'COMPRAS') === (r.decision === 'BUY' || r.decision === 'SIMULATED'))), [list.data, market, only])
  const markets = useMemo(() => ['TODOS', ...Array.from(new Set((list.data ?? []).map((r) => r.market)))], [list.data])
  return (
    <section aria-label="Operaciones" className="mx-auto max-w-7xl space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Operaciones: qué se planteó y qué pasó</h1>
        <p className="text-sm text-muted">Pulsa una fila para verla en el gráfico: velas, tendencia (medias de 50 y 200 sesiones), la <b>entrada</b> planteada, el <b>objetivo</b>, el <b>stop</b> y la <b>salida</b> si ya ocurrió. Las compras abren una posición simulada; las «no compra» muestran qué habría pasado. Dinero simulado, reglas sin validar.</p>
      </header>
      <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
        <Card>
          <CardHeader title="Decisiones" sub={`${rows.length} de ${list.data?.length ?? 0}`} />
          <CardBody className="space-y-3">
            <div className="flex flex-wrap gap-2 text-xs">
              <select aria-label="Mercado" value={market} onChange={(e) => setMarket(e.target.value)} className="rounded border border-border bg-surface-2 p-1.5">{markets.map((m) => <option key={m}>{m}</option>)}</select>
              <select aria-label="Tipo" value={only} onChange={(e) => setOnly(e.target.value as typeof only)} className="rounded border border-border bg-surface-2 p-1.5">{['TODAS', 'COMPRAS', 'NO COMPRAS'].map((m) => <option key={m}>{m}</option>)}</select>
            </div>
            {list.isPending ? <Skeleton className="h-40" /> : list.isError ? <PanelError what="Operaciones" error={list.error} onRetry={() => list.refetch()} /> : rows.length === 0 ? <p className="text-xs text-muted">Aún no hay decisiones. Ejecuta la rutina de hoy en «Rutina diaria».</p> : (
              <ul className="max-h-[34rem] space-y-1 overflow-auto">
                {rows.map((r) => (
                  <li key={r.ref}>
                    <button onClick={() => setParams({ ref: r.ref })} aria-current={r.ref === ref} className={`w-full rounded border px-2 py-1.5 text-left text-xs ${r.ref === ref ? 'border-accent bg-accent/10' : 'border-border hover:bg-surface-2'}`}>
                      <div className="flex items-center justify-between gap-2"><b>{r.market} · {r.ticker}</b><Badge tone={r.decision === 'BUY' || r.decision === 'SIMULATED' ? 'up' : 'neutral'}>{r.decision === 'BUY' ? 'COMPRA' : r.decision === 'NO_ORDER' ? 'NO COMPRA' : 'SIMULACIÓN'}</Badge></div>
                      <div className="text-muted">{r.date}{r.horizon_months ? ` · ${r.horizon_months} meses` : ''}{r.recommendation ? ` · ${r.recommendation} (${r.score?.toFixed(1)})` : ''}</div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
        <div className="space-y-4">
          {!ref ? <Card><CardBody><p className="text-sm text-muted">Elige una decisión de la lista para ver su gráfico.</p></CardBody></Card> : chart.isPending ? <Skeleton className="h-[30rem]" /> : chart.isError ? <PanelError what="Gráfico" error={chart.error} onRetry={() => chart.refetch()} /> : (
            <>
              <Card>
                <CardHeader title={chart.data.title} sub={`Decidida ${chart.data.decision_date} · horizonte hasta ${chart.data.horizon_end}`} right={<Badge tone={chart.data.outcome.state === 'TARGET_HIT' ? 'up' : chart.data.outcome.state === 'STOP_HIT' ? 'down' : 'neutral'}>{STATE[chart.data.outcome.state] ?? chart.data.outcome.state} · {pct(chart.data.outcome.return_pct)}</Badge>} />
                <CardBody>
                  <TradeChart t={chart.data} />
                  <p className="mt-2 text-[11px] text-muted"><span className="text-[#e0a030]">━ SMA50</span> · <span className="text-[#6a8cff]">━ SMA200</span> (tendencia) · línea azul = entrada, verde = objetivo, roja = stop · flecha ↑ entrada, flecha ↓ salida, círculo = decisión de no comprar.</p>
                </CardBody>
              </Card>
              <Card>
                <CardHeader title="Qué se planteó y qué ha pasado" />
                <CardBody><ul className="space-y-1.5 text-sm">{chart.data.explanation.map((l, i) => <li key={i}>{l}</li>)}</ul><p className="mt-3 text-[11px] text-warn">{chart.data.disclaimer}</p></CardBody>
              </Card>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
