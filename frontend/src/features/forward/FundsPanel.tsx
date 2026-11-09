import clsx from 'clsx'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { api, apiPost } from '../../api/client'
import { Button, Card, CardBody, CardHeader } from '../../components/ui/primitives'

type Candidate = { isin: string; symbol: string; name: string; currency: string | null }
export type Fund = {
  isin: string; symbol: string; name: string; currency: string | null
  forecasts: number; matured: number; hits: number; accuracy: number | null; always_up_accuracy: number | null
  latest: { p_up: number; feature_date: string; reference_nav: number; target_date: string; version: string; last_step: number; last_return: number | null } | null
  history: { date: string; p_up: number; return: number; hit: boolean }[]
}

const pct = (n: number, d = 0) => `${(n * 100).toFixed(d)}%`
const day = (iso: string) => new Date(iso).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })
const ISIN = /^[A-Z]{2}[A-Z0-9]{9}[0-9]$/

export function FundsPanel({ funds }: { funds: Fund[] }) {
  const client = useQueryClient()
  const [isin, setIsin] = useState('')
  const refresh = () => client.invalidateQueries({ queryKey: ['forward-pilots'] })
  const find = useMutation({ mutationFn: (code: string) => api<Candidate[]>(`/forward-pilots/funds/search?isin=${encodeURIComponent(code)}`) })
  const add = useMutation({ mutationFn: (c: Candidate) => apiPost('/forward-pilots/funds', c), onSuccess: () => { find.reset(); setIsin(''); refresh() } })
  const drop = useMutation({ mutationFn: (code: string) => apiPost('/forward-pilots/funds/remove', { isin: code }), onSuccess: refresh })
  const code = isin.trim().toUpperCase()
  const submit = (e: FormEvent) => { e.preventDefault(); if (ISIN.test(code)) find.mutate(code) }
  const known = new Set(funds.map(f => f.isin))
  return <Card>
    <CardHeader title="Mis fondos" sub="Fondos de inversión que tú eliges. Cada noche el modelo campeón apuesta si su valor liquidativo estará más alto dentro de 20 sesiones (≈ 1 mes)." />
    <CardBody className="space-y-4">
      <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="fund-isin">ISIN del fondo</label>
        <input id="fund-isin" value={isin} onChange={e => setIsin(e.target.value)} placeholder="ISIN, p. ej. ES0119199000" maxLength={12}
          className="num w-56 rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm uppercase placeholder:normal-case" />
        <Button type="submit" variant="solid" disabled={!ISIN.test(code) || find.isPending}>{find.isPending ? 'Buscando…' : 'Buscar'}</Button>
        {code.length === 12 && !ISIN.test(code) && <span className="text-xs text-warn">Un ISIN son 2 letras + 10 caracteres.</span>}
      </form>
      {find.isError && <p role="alert" className="text-xs text-warn">{find.error.message.includes('INVALID_ISIN') ? 'Ese ISIN no es válido (falla el dígito de control).' : `No se pudo buscar: ${find.error.message}`}</p>}
      {find.data && (find.data.length === 0
        ? <p className="text-sm text-muted">No he encontrado valores liquidativos para {code}. Prueba con otra clase del fondo (otro ISIN).</p>
        : <ul className="space-y-2">{find.data.map(c => <li key={c.symbol} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-surface-2/60 px-3 py-2 text-sm">
            <span><b>{c.name}</b> <span className="num text-xs text-muted">{c.isin} · {c.currency ?? '—'}</span></span>
            <Button variant="solid" disabled={known.has(c.isin) || add.isPending} onClick={() => add.mutate(c)}>{known.has(c.isin) ? 'Ya está' : add.isPending ? 'Añadiendo y descargando…' : 'Añadir'}</Button>
          </li>)}</ul>)}
      {add.isError && <p role="alert" className="text-xs text-warn">No se pudo añadir: {add.error.message}</p>}

      {funds.length === 0 ? <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted">Aún no has añadido fondos. Escribe el ISIN de uno (lo encuentras en la ficha del fondo o en tu banco) y pulsa Buscar.</p>
        : <ul className="divide-y divide-border">{funds.map(f => <FundRow key={f.isin} f={f} onRemove={() => { if (window.confirm(`¿Quitar ${f.name}? Su historial de pronósticos se conserva.`)) drop.mutate(f.isin) }} />)}</ul>}

      <p className="text-xs text-muted">El modelo se entrenó con acciones, no con fondos: aquí se mide si también le sirve. Los fondos se evalúan aparte y no cambian el modelo. Un fondo necesita al menos 201 valores liquidativos (≈ 10 meses) para tener pronóstico. Datos de Yahoo (Morningstar), no oficiales.</p>
    </CardBody>
  </Card>
}

function FundRow({ f, onRemove }: { f: Fund; onRemove: () => void }) {
  const l = f.latest
  const off = l ? (l.p_up - 0.5) * 2 : 0
  return <li className="grid gap-3 py-3 text-sm md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-center">
    <div className="min-w-0"><b className="block truncate">{f.name}</b><span className="num text-xs text-muted">{f.isin} · {f.currency ?? ''}</span></div>
    {l ? <div>
      <div className="flex items-center gap-2">
        <span className="relative h-3 flex-1 rounded bg-surface-2" aria-label={`Probabilidad de subida ${pct(l.p_up)}`}>
          <span className="absolute inset-y-0 left-1/2 w-px bg-muted" />
          <span className={clsx('absolute inset-y-0', off >= 0 ? 'left-1/2 rounded-r bg-up/70' : 'right-1/2 rounded-l bg-down/70')} style={{ width: `${Math.abs(off) * 50}%` }} />
        </span>
        <b className={clsx('num w-10 text-right', off >= 0 ? 'text-up' : 'text-down')}>{pct(l.p_up)}</b>
      </div>
      <span className="num text-xs text-muted">VL {l.reference_nav.toFixed(2)} del {day(l.feature_date)} · revisión {l.last_step}/20{l.last_return != null ? ` · ${l.last_return >= 0 ? '+' : ''}${pct(l.last_return, 1)}` : ''} · vence {day(l.target_date)}</span>
    </div> : <span className="text-xs text-warn">Sin pronóstico: historia corta o datos desactualizados.</span>}
    <div className="text-xs">
      {f.matured ? <>
        <b className="num text-sm">{f.hits}/{f.matured}</b> aciertos ({pct(f.accuracy ?? 0)})<br />
        <span className="text-muted">«siempre sube»: {pct(f.always_up_accuracy ?? 0)}</span>
        <div className="mt-1 flex gap-0.5" aria-label="Últimos resultados">{f.history.slice(-20).map(h => <span key={h.date} title={`${h.date}: ${h.hit ? 'acierto' : 'fallo'} (${pct(h.return, 1)})`} className={clsx('h-2.5 w-2.5 rounded-sm', h.hit ? 'bg-up' : 'bg-down')} />)}</div>
      </> : <span className="text-muted">{f.forecasts} pronóstico{f.forecasts === 1 ? '' : 's'} esperando su fecha</span>}
    </div>
    <button onClick={onRemove} className="justify-self-start text-xs text-muted underline hover:text-down md:justify-self-end">Quitar</button>
  </li>
}
