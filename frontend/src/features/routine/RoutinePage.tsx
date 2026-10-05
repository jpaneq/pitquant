import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiPost } from '../../api/client'
import { Card, CardBody, CardHeader, InfoTip } from '../../components/ui/primitives'
import { GLOSSARY } from '../../lib/glossary'

type RunResult = { run: { run_date: string; markets: { market: string; status: string; ticker?: string; bought?: number[]; unavailable?: Record<string, string> }[] }; evaluation: { week: string; evaluations_written: number; closed: number; virtual_evaluations_written: number } }

async function fetchText(path: string): Promise<string> {
  const res = await fetch(path, { headers: { Accept: 'text/plain' } })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.text()
}

/** Rutina diaria de compras simuladas: ejecuta el paso de hoy y muestra el informe en texto plano para copiarlo. */
export function RoutinePage() {
  const client = useQueryClient()
  const report = useQuery({ queryKey: ['routine-report'], queryFn: () => fetchText('/routine/report?days=30') })
  const backtest = useQuery({ queryKey: ['routine-backtest'], queryFn: () => fetchText('/routine/backtest-report') })
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [last, setLast] = useState<RunResult | null>(null)
  const run = async () => {
    setBusy(true)
    setMsg('')
    try {
      setLast(await apiPost<RunResult>('/routine/run?force=true', {}))
      await client.invalidateQueries({ queryKey: ['routine-report'] })
      setMsg('Rutina ejecutada.')
    } catch (e) { setMsg(String((e as Error).message ?? e)) } finally { setBusy(false) }
  }
  const copy = async () => {
    try { await navigator.clipboard.writeText(report.data ?? ''); setMsg('Informe copiado al portapapeles.') } catch { setMsg('No se pudo copiar: selecciona el texto manualmente.') }
  }
  return (
    <section aria-label="Rutina diaria" className="mx-auto max-w-5xl space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Rutina diaria de compras simuladas<InfoTip term={GLOSSARY['rutina diaria']} /></h1>
        <p className="text-sm text-muted">Cada día analiza <b>una empresa del IBEX, una del S&amp;P 500, una del MSCI World y Bitcoin</b>. Para cada horizonte (1, 3, 6, 12 y 24 meses) abre o no una compra simulada con precio de entrada, objetivo y stop; cada semana comprueba si se cumplen. Dinero simulado, reglas sin validar. <Link className="text-accent underline" to="/ayuda#rutina">Cómo funciona</Link>.</p>
      </header>
      <div className="flex flex-wrap items-center gap-3">
        <button disabled={busy} onClick={run} className="rounded bg-accent px-3 py-2 text-sm font-medium text-white disabled:opacity-40">Ejecutar rutina de hoy</button>
        <Link to="/operaciones" className="rounded border border-accent px-3 py-2 text-sm text-accent">Ver en gráfico (entrada, salida, tendencia)</Link>
        <button disabled={!report.data} onClick={copy} className="rounded border border-border px-3 py-2 text-sm">Copiar informe</button>
        {report.data ? <a download="informe_rutina.txt" href={`data:text/plain;charset=utf-8,${encodeURIComponent(report.data)}`} className="rounded border border-border px-3 py-2 text-sm">Descargar .txt</a> : null}
        {msg ? <span role="status" className="text-xs text-warn">{msg}</span> : null}
      </div>
      {last ? (
        <Card>
          <CardHeader title="Resultado de esta ejecución" sub={`${last.run.run_date} · semana ${last.evaluation.week}: ${last.evaluation.evaluations_written} evaluaciones, ${last.evaluation.closed} cerradas`} />
          <CardBody>
            <ul className="space-y-1 text-xs">{last.run.markets.map((m) => <li key={m.market}><b>{m.market}</b>: {m.status === 'MARKET_CLOSED' ? 'bolsa cerrada ahora' : m.status === 'ANALYZED' ? `${m.ticker} · compras simuladas a ${m.bought?.length ? m.bought.join(', ') + ' meses' : 'ningún horizonte'}` : m.status === 'NO_DATA' ? `sin datos utilizables (${Object.keys(m.unavailable ?? {}).slice(0, 3).join(', ')}…)` : 'ya analizado hoy'}</li>)}</ul>
          </CardBody>
        </Card>
      ) : null}
      <Card>
        <CardHeader title="Informe (texto plano)" sub="Pégame este texto para reajustar los parámetros que no se cumplan" />
        <CardBody>
          {report.isPending ? <p className="text-xs text-muted">Generando informe…</p> : null}
          {report.isError ? <p role="alert" className="text-xs text-bad">No se pudo generar el informe.</p> : null}
          <pre aria-label="Informe de la rutina" className="max-h-[70vh] overflow-auto whitespace-pre rounded bg-surface-2 p-3 text-[11px] leading-snug">{report.data}</pre>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Backtest histórico (último informe)" sub="¿Acertaba la regla en subida y bajada? Retrospectivo, sin mirar el futuro, holdout intacto · se genera con: python -m pitquant.cli backtest-run" />
        <CardBody>
          <pre aria-label="Informe de backtest" className="max-h-[70vh] overflow-auto whitespace-pre rounded bg-surface-2 p-3 text-[11px] leading-snug">{backtest.data}</pre>
        </CardBody>
      </Card>
    </section>
  )
}
