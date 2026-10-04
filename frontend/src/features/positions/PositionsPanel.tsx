import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiPost } from '../../api/client'
import { InfoTip } from '../../components/ui/primitives'
import { GLOSSARY } from '../../lib/glossary'

type Rule = { id: string; label: string; value: unknown; contribution: number; text: string }
type Review = {
  recommendation: 'ADD' | 'HOLD' | 'SELL'; reason: string; score: number; horizon_bucket: string; label: string; disclaimer: string; rules: Rule[]; missing_rules: string[]
  position: { avg_cost: number; quantity: number; price: number; pnl_pct: number; pnl_value: number; months_elapsed: number; months_remaining: number; horizon_months: number; target_return: number | null; target_met: boolean; stop_price: number | null }
  price_source: string; price_freshness: string | null
}
type View = { position_id: string; asset_type: string; status: string; reason?: string; quantity: number; avg_cost: number; realized_pnl: number; horizon_months: number; stop_rule: string; is_synthetic: boolean; review: Review | null }

const LABEL = { ADD: 'AMPLIAR', HOLD: 'MANTENER', SELL: 'VENDER' } as const
const TONE = { ADD: 'border-up text-up', HOLD: 'border-border text-fg', SELL: 'border-down text-down' } as const
const HORIZONS = [1, 3, 6, 12, 24, 36] as const
const money = (v: number) => v.toLocaleString('en-US', { maximumFractionDigits: 2 })
const pct = (v: number) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(2)}%`
const signed = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`

/** Compras simuladas (sin dinero real) con horizonte en meses y revisión por reglas: ampliar, mantener o vender. No es una predicción. */
export function PositionsPanel({ asset, security }: { asset: 'EQUITY' | 'BTC'; security?: string }) {
  const client = useQueryClient()
  const key = ['positions', asset, security ?? '']
  const q = useQuery({ queryKey: key, queryFn: () => api<View[]>(`/positions?asset_type=${asset}${security ? `&security=${encodeURIComponent(security)}` : ''}`), refetchInterval: 30000 })
  const [notional, setNotional] = useState(asset === 'BTC' ? 1000 : 5000)
  const [months, setMonths] = useState<number>(6)
  const [target, setTarget] = useState('')
  const [qty, setQty] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const unit = asset === 'BTC' ? 'BTC' : 'acciones'
  const run = async (work: () => Promise<unknown>, ok: string) => {
    setBusy(true)
    setMsg('')
    try { await work(); setMsg(ok); await client.invalidateQueries({ queryKey: ['positions'] }) } catch (e) { setMsg(String((e as Error).message ?? e)) } finally { setBusy(false) }
  }
  const buy = () => run(() => apiPost('/positions', { asset_type: asset, security, horizon_months: months, notional, target_return: target ? Number(target) / 100 : null }), 'Compra simulada registrada.')
  const event = (id: string, type: string, quantity?: number) => run(() => apiPost(`/positions/${id}/events`, { type, quantity }), type === 'ADD' ? 'Ampliación simulada registrada.' : type === 'REDUCE' ? 'Venta parcial simulada registrada.' : 'Posición cerrada (simulada).')
  return (
    <section aria-label="Posiciones simuladas" className="space-y-3 rounded-lg border border-border bg-surface p-4">
      <header>
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">Mis compras simuladas<InfoTip term={GLOSSARY['posiciones simuladas']} /></h2>
        <p className="mt-1 text-xs text-muted">Dinero simulado: no hay broker. Elige un horizonte en meses y el algoritmo revisa, con reglas visibles, si conviene <b>ampliar</b>, <b>mantener</b> o <b>vender</b>. {GLOSSARY['posiciones simuladas'].c}</p>
      </header>
      <div className="flex flex-wrap items-end gap-3 text-xs">
        <label>Importe ({asset === 'BTC' ? 'USDT' : 'USD'})<input aria-label="Importe de la compra" type="number" min="1" value={notional} onChange={(e) => setNotional(Number(e.target.value))} className="ml-2 w-28 rounded border border-border bg-surface-2 p-1.5" /></label>
        <label>Horizonte<InfoTip term={GLOSSARY['horizonte (meses)']} /><select aria-label="Horizonte en meses" value={months} onChange={(e) => setMonths(Number(e.target.value))} className="ml-2 rounded border border-border bg-surface-2 p-1.5">{HORIZONS.map((m) => <option key={m} value={m}>{m} {m === 1 ? 'mes' : 'meses'}</option>)}</select></label>
        <label>Objetivo % (opcional)<input aria-label="Objetivo de rentabilidad" type="number" min="1" placeholder="p. ej. 15" value={target} onChange={(e) => setTarget(e.target.value)} className="ml-2 w-20 rounded border border-border bg-surface-2 p-1.5" /></label>
        <button disabled={busy || notional <= 0} onClick={buy} className="rounded bg-accent px-3 py-2 text-xs font-medium text-white disabled:opacity-40">Simular compra</button>
      </div>
      {msg ? <p role="status" className="text-xs text-warn">{msg}</p> : null}
      {q.isPending ? <p className="text-xs text-muted">Cargando posiciones…</p> : null}
      {Array.isArray(q.data) && q.data.length === 0 ? <p className="text-xs text-muted">Aún no tienes compras simuladas aquí.</p> : null}
      {(Array.isArray(q.data) ? q.data : []).map((v) => {
        const r = v.review
        return (
          <article key={v.position_id} aria-label="Posición simulada" className="space-y-2 rounded-md border border-border p-3 text-xs">
            {v.is_synthetic ? <p className="font-semibold text-warn">SYNTHETIC TEST DATA</p> : null}
            {r ? (
              <>
                <div className="flex flex-wrap items-center gap-3">
                  <span aria-label="Recomendación" className={`rounded border px-2 py-1 text-sm font-semibold ${TONE[r.recommendation]}`}>{LABEL[r.recommendation]}</span>
                  <span className="text-muted">horizonte {r.position.horizon_months} m ({r.horizon_bucket.toLowerCase()}) · quedan {r.position.months_remaining.toFixed(1)} m · puntuación {signed(r.score)}</span>
                  <InfoTip term={GLOSSARY['puntuación de reglas']} />
                </div>
                <p>{r.reason}</p>
                <dl className="grid grid-cols-2 gap-2 md:grid-cols-6">
                  {[['Cantidad', `${money(v.quantity)} ${unit}`], ['Coste medio', money(v.avg_cost)], ['Precio', money(r.position.price)], ['Resultado', `${pct(r.position.pnl_pct)} (${signed(r.position.pnl_value)})`], ['Stop protector', r.position.stop_price ? money(r.position.stop_price) : '—'], ['Objetivo', r.position.target_return ? `${(r.position.target_return * 100).toFixed(0)} %${r.position.target_met ? ' ✔' : ''}` : '—']].map(([k, val]) => <div key={k}><dt className="text-muted">{k}</dt><dd className="num">{val}</dd></div>)}
                </dl>
                <details>
                  <summary className="cursor-pointer text-accent">Reglas que han decidido</summary>
                  <table className="mt-1 w-full"><thead><tr className="text-left text-muted"><th>Regla</th><th>Valor</th><th>Aporta</th><th>Qué dice</th></tr></thead><tbody>{r.rules.map((x) => <tr key={x.id} className="border-t border-border/50"><td>{x.label}</td><td className="num">{String(x.value)}</td><td className={x.contribution >= 0 ? 'text-up' : 'text-down'}>{signed(x.contribution)}</td><td>{x.text}</td></tr>)}</tbody></table>
                  {r.missing_rules.length ? <p className="mt-1 text-muted">Sin datos para: {r.missing_rules.join(', ')} (no se adivinan).</p> : null}
                </details>
                <p className="text-muted">Precio {r.price_source}{r.price_freshness ? ` · ${r.price_freshness}` : ''}. {r.disclaimer}</p>
                <div className="flex flex-wrap items-center gap-2">
                  <input aria-label="Cantidad a ampliar o vender" type="number" min="0" step="any" placeholder={`cantidad (${unit})`} value={qty} onChange={(e) => setQty(e.target.value)} className="w-32 rounded border border-border bg-surface-2 p-1.5" />
                  <button disabled={busy || !Number(qty)} onClick={() => event(v.position_id, 'ADD', Number(qty))} className="rounded border border-border px-2 py-1">Simular ampliar</button>
                  <button disabled={busy || !Number(qty)} onClick={() => event(v.position_id, 'REDUCE', Number(qty))} className="rounded border border-border px-2 py-1">Simular vender parte</button>
                  <button disabled={busy} onClick={() => event(v.position_id, 'CLOSE')} className="rounded border border-border px-2 py-1">Cerrar posición</button>
                  <button disabled={busy} onClick={() => run(() => apiPost(`/positions/${v.position_id}/review`, {}), 'Revisión guardada.')} className="rounded border border-border px-2 py-1">Guardar esta revisión</button>
                </div>
              </>
            ) : <p className="text-warn">{v.reason ?? 'Revisión no disponible.'}</p>}
          </article>
        )
      })}
    </section>
  )
}
