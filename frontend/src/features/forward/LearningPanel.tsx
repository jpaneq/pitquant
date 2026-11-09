import clsx from 'clsx'
import { useState, type ReactNode } from 'react'
import { Badge, Card, CardBody, CardHeader, Segmented } from '../../components/ui/primitives'
import { CalibrationChart, CompareBars, Legend, LineChart } from './charts'

type Interval = { mean: number; low90: number; high90: number; clusters: number }
type Arm = { n: number; accuracy: number; brier: number; logloss: number; mean_p_up: number; gain_vs_base_rate: Interval; signal_verdict: string }
type Exam = {
  window: { first_decision: string; last_decision: string; last_target: string }
  n: number; months: number; tickers: string[]; base_rate_p: number
  always_up_accuracy: number; momentum_accuracy: number; base_rate_logloss: number
  arms: { A_FROZEN_V1: Arm; B_LEARNING: Arm }
  learning_minus_frozen_gain: Interval; policy: string
}
type Monthly = { month: string; n: number; up_rate: number; acc_v1: number; acc_learning: number; gain_v1: number; gain_learning: number }
type Calib = { p_mean: number; up_rate: number; n: number }
type LivePoint = { date: string; n: number; accuracy: number; up_rate: number; gain: number }
type Forecast = { id: string; ticker: string; p_up: number; feature_date: string; reference_price: number; due_at: string; horizon: number; last_step: number; last_return: number | null; final_hit: boolean | null }
export type Learning = {
  market: string
  exam: Exam | null
  exam_series?: { monthly: Monthly[]; calibration: { v1: Calib[]; learning: Calib[] } } | null
  live?: { series: { v1: LivePoint[]; learning: LivePoint[]; v3?: LivePoint[] }; matured: number; pending: number; next_maturity: string | null }
  latest?: Forecast[]
  policy_history: { policy: string; reason: string; decided_at: string }[]
  champion: { model_id: string; version: string; family: string } | null
  refits: { model_id: string; version: string; trained_at: string; train_n: number; train_target_end: string; tickers: number }[]
  forward: { pairs: number; dates: number; v1_logloss?: number; learning_logloss?: number; learning_gain?: Interval }
}
export type Activity = { last_activity: string | null; schedule_installed: boolean }

const C1 = 'var(--series-1)'
const C2 = 'var(--series-2)'
const MUTED = 'var(--muted)'
const pct = (n: number, d = 1) => `${(n * 100).toFixed(d)}%`
const pp = (n: number) => `${n >= 0 ? '+' : ''}${(n * 100).toFixed(1)} pp`
const day = (iso: string) => new Date(iso).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })
const NAME: Record<string, string> = { EQUITY: 'Acciones', BTC: 'Bitcoin' }
const HORIZON: Record<string, string> = { EQUITY: '20 sesiones (≈ 1 mes)', BTC: '30 días' }
const policyOf = (l: Learning) => l.policy_history.at(-1)?.policy

function ago(iso: string | null) {
  if (!iso) return null
  const h = (Date.now() - new Date(iso).getTime()) / 3_600_000
  return { hours: h, text: h < 1 ? 'hace menos de 1 h' : h < 48 ? `hace ${Math.round(h)} h` : `hace ${Math.round(h / 24)} días` }
}

function Tile({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: 'up' | 'warn' | 'down' | 'info' }) {
  return <div className={clsx('rounded-lg border bg-surface p-4', tone === 'warn' ? 'border-warn/40' : tone === 'down' ? 'border-down/40' : 'border-border')}>
    <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">{label}</div>
    <div className={clsx('mt-1 text-lg font-semibold', tone === 'up' && 'text-up', tone === 'warn' && 'text-warn', tone === 'down' && 'text-down', tone === 'info' && 'text-info')}>{value}</div>
    {sub ? <div className="mt-0.5 text-xs text-muted">{sub}</div> : null}
  </div>
}

/* ------------------------------------------------------------------ estado */

export function StatusStrip({ items, activity }: { items: Learning[]; activity?: Activity }) {
  const last = ago(activity?.last_activity ?? null)
  const stale = last != null && last.hours > 36
  const next = items.map(i => i.live?.next_maturity).filter((d): d is string => !!d).sort()[0]
  const pending = items.reduce((n, i) => n + (i.live?.pending ?? 0), 0)
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
    <Tile label="¿Funciona solo?" tone={!activity?.schedule_installed || stale ? 'warn' : 'up'}
      value={activity?.schedule_installed ? (stale ? 'Parado' : 'Sí, cada noche') : 'No programado'}
      sub={last ? `Última ejecución ${last.text}` : 'Todavía no se ha ejecutado'} />
    {items.map(i => {
      const p = policyOf(i)
      return <Tile key={i.market} label={NAME[i.market] ?? i.market} tone="info"
        value={p === 'LEARNING_V3' ? 'Aprende con resultados' : p === 'LEARNING' ? 'Aprendiendo' : p === 'FROZEN_V1' ? 'Modelo fijo' : 'Sin examen'}
        sub={i.champion ? `Usa el modelo ${i.champion.version}` : 'Sin modelo'} />
    })}
    <Tile label="Próximo resultado" value={next ? day(next) : '—'} sub={`${pending} pronósticos esperando su fecha`} />
  </div>
}

/* ------------------------------------------------------------------ qué hacer */

export function TodoList({ items, activity }: { items: Learning[]; activity?: Activity }) {
  const installed = !!activity?.schedule_installed
  const next = items.map(i => i.live?.next_maturity).filter((d): d is string => !!d).sort()[0]
  const steps: { done: boolean; title: string; body: ReactNode }[] = [
    { done: installed, title: 'Programa el ciclo diario', body: <>Haz doble clic en <code className="rounded bg-surface-2 px-1">Instalar_aprendizaje_diario.command</code> (carpeta del proyecto). Cada noche a las 23:30 descarga precios, revisa los pronósticos que vencen y emite los nuevos. Una vez al mes se reentrena solo.</> },
    { done: false, title: 'Deja el Mac encendido', body: 'Si está dormido a las 23:30, la tarea se ejecuta al despertar. Si está apagado varios días, esos días se quedan sin pronóstico (no se rellenan después).' },
    { done: false, title: 'Mira esta página una vez por semana', body: 'La sección «¿Va mejorando?» es la única que importa para decidir. El resto es contexto.' },
    { done: false, title: 'Ten paciencia con el veredicto', body: <>El primer resultado real llega el {next ? day(next) : '—'}. Para un veredicto fiable hacen falta al menos 200 pares de pronósticos maduros en 20 fechas distintas: unas 4–6 semanas después.</> },
  ]
  return <Card>
    <CardHeader title="Qué tienes que hacer" />
    <CardBody>
      <ol className="space-y-3">{steps.map((s, i) => <li key={s.title} className="flex gap-3">
        <span aria-hidden className={clsx('mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold', s.done ? 'border-up bg-up/15 text-up' : 'border-border text-muted')}>{s.done ? '✓' : i + 1}</span>
        <div className="text-sm"><b className={clsx(s.done && 'text-muted line-through')}>{s.title}</b><p className="text-muted">{s.body}</p></div>
      </li>)}</ol>
    </CardBody>
  </Card>
}

/* ------------------------------------------------------------------ ¿va mejorando? */

export function LiveProgress({ items }: { items: Learning[] }) {
  return <Card>
    <CardHeader title="¿Va mejorando?" sub="Solo pronósticos reales, emitidos antes de conocer el resultado. Es la prueba que cuenta." />
    <CardBody className="grid gap-6 lg:grid-cols-2">{items.map(i => <LiveMarket key={i.market} item={i} />)}</CardBody>
  </Card>
}

function LiveMarket({ item }: { item: Learning }) {
  const policy = policyOf(item)
  const champ = policy === 'LEARNING_V3' ? 'v3' : policy === 'LEARNING' ? 'learning' : 'v1'
  const main = item.live?.series[champ] ?? []
  const other = item.live?.series[champ === 'v1' ? 'learning' : 'v1'] ?? []
  const pairs = item.forward.pairs
  const last = main.at(-1)
  return <section aria-label={`Progreso ${item.market}`} className="space-y-3">
    <h3 className="font-semibold">{NAME[item.market]} <span className="text-xs font-normal text-muted">· {HORIZON[item.market]}</span></h3>
    {last ? <>
      <div className="grid grid-cols-3 gap-3">
        <Tile label="Acierta" value={pct(last.accuracy)} sub={`${last.n} resultados`} />
        <Tile label="«Siempre sube»" value={pct(last.up_rate)} sub="la referencia a batir" />
        <Tile label="Ventaja" value={pp(last.accuracy - last.up_rate)} tone={last.accuracy > last.up_rate ? 'up' : 'down'} sub="sobre la referencia" />
      </div>
      <LineChart label={`Acierto acumulado ${item.market}`} x={main.map(p => p.date)} yMin={0.3} yMax={0.8} format={v => pct(v, 0)}
        series={[
          { key: 'champ', label: 'Campeón', color: C1, values: main.map(p => p.accuracy) },
          { key: 'base', label: 'Siempre sube', color: MUTED, dashed: true, values: main.map(p => p.up_rate) },
          ...(other.length ? [{ key: 'other', label: champ === 'v1' ? 'Reentreno' : 'V1 fijo', color: C2, values: main.map(p => other.find(o => o.date === p.date)?.accuracy ?? null) }] : []),
        ]} />
      <Legend items={[{ label: 'Campeón', color: C1 }, { label: 'Siempre sube', color: MUTED, dashed: true }, ...(other.length ? [{ label: champ === 'v1' ? 'Reentreno' : 'V1 fijo', color: C2 }] : [])]} />
    </> : <div className="rounded-lg border border-dashed border-border bg-surface-2/50 p-5 text-sm">
      <p className="font-medium">Aún no ha vencido ningún pronóstico.</p>
      <p className="mt-1 text-muted">{item.live?.next_maturity ? <>El primero vence el <b className="text-fg">{day(item.live.next_maturity)}</b>.</> : 'Sin pronósticos pendientes.'} Desde ese día verás aquí una línea azul (acierto del algoritmo) y otra gris discontinua (acierto de decir siempre «sube»). <b className="text-fg">Si la azul va por encima de forma sostenida, el algoritmo aporta algo.</b></p>
    </div>}
    <div className="text-xs">
      <div className="mb-1 flex justify-between text-muted"><span>Hacia el veredicto (reentreno vs V1)</span><span className="num">{pairs}/200 pares · {item.forward.dates}/20 fechas</span></div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-2"><div className="h-2 rounded-full bg-accent" style={{ width: `${Math.min(100, (pairs / 200) * 100)}%` }} /></div>
    </div>
  </section>
}

/* ------------------------------------------------------------------ hoy */

export function TodayForecasts({ items }: { items: Learning[] }) {
  const [market, setMarket] = useState(items[0]?.market ?? 'EQUITY')
  const [all, setAll] = useState(false)
  const item = items.find(i => i.market === market)
  const rows = item?.latest ?? []
  const shown = all ? rows : rows.slice(0, 12)
  return <Card>
    <CardHeader title="Lo que dice hoy" sub={rows[0] ? `Cierre del ${day(rows[0].feature_date)} · horizonte ${HORIZON[market]}` : undefined}
      right={<Segmented label="Mercado" value={NAME[market]} options={items.map(i => NAME[i.market])} onChange={v => { setMarket(items.find(i => NAME[i.market] === v)?.market ?? market); setAll(false) }} />} />
    <CardBody>
      {!rows.length ? <p className="text-sm text-muted">Sin pronósticos todavía.</p> : <>
        <p className="mb-3 text-xs text-muted">Probabilidad de que el precio esté más alto al final del horizonte. 50% = no sabe. El modelo casi siempre se inclina por «sube» porque, históricamente, las acciones suben más veces de las que bajan; lo interesante es si sus 65% aciertan más que sus 55%.</p>
        <div className="mb-1 grid grid-cols-[4rem_1fr_3.5rem_6.5rem] gap-3 text-[10px] text-muted"><span /><span className="flex justify-between"><span>0% · baja seguro</span><span>50%</span><span>sube seguro · 100%</span></span><span className="text-right">P(sube)</span><span className="text-right">Revisión</span></div>
        <ul className="space-y-1.5">{shown.map(r => <ForecastRow key={r.id} r={r} />)}</ul>
        {rows.length > 12 && <button className="mt-3 text-xs text-accent underline" onClick={() => setAll(a => !a)}>{all ? 'Ver menos' : `Ver los ${rows.length}`}</button>}
      </>}
    </CardBody>
  </Card>
}

function ForecastRow({ r }: { r: Forecast }) {
  const off = (r.p_up - 0.5) * 2 // −1..1
  const up = off >= 0
  return <li className="grid grid-cols-[4rem_1fr_3.5rem_6.5rem] items-center gap-3 text-xs">
    <b>{r.ticker}</b>
    <span className="relative h-3 rounded bg-surface-2" aria-label={`Probabilidad de subida ${pct(r.p_up)}`}>
      <span className="absolute inset-y-0 left-1/2 w-px bg-muted" />
      <span className={clsx('absolute inset-y-0', up ? 'left-1/2 rounded-r bg-up/70' : 'right-1/2 rounded-l bg-down/70')} style={{ width: `${Math.abs(off) * 50}%` }} />
    </span>
    <span className={clsx('num text-right font-medium', up ? 'text-up' : 'text-down')}>{pct(r.p_up, 0)}</span>
    <span className="num text-right text-muted">{r.final_hit == null ? `${r.last_step}/${r.horizon} · ${r.last_return == null ? 'esperando' : pct(r.last_return)}` : r.final_hit ? '✓ acierto' : '✗ fallo'}</span>
  </li>
}

/* ------------------------------------------------------------------ examen */

export function ExamView({ items }: { items: Learning[] }) {
  const ready = items.filter(i => i.exam)
  const [market, setMarket] = useState(ready[0]?.market ?? 'EQUITY')
  const item = ready.find(i => i.market === market)
  if (!item?.exam) return null
  const e = item.exam
  const learning = e.policy === 'LEARNING'
  const best = learning ? e.arms.B_LEARNING : e.arms.A_FROZEN_V1
  const signal = [e.arms.A_FROZEN_V1, e.arms.B_LEARNING].some(a => a.signal_verdict === 'EVIDENCE_OF_SIGNAL')
  const monthly = item.exam_series?.monthly ?? []
  // Groups with very few cases are noise, not calibration: keep those with ≥ 1 % of the exam.
  const calib = (item.exam_series?.calibration[learning ? 'learning' : 'v1'] ?? []).filter(p => p.n >= Math.max(30, e.n * 0.01))
  const edge = monthly.flatMap(m => [m.acc_learning - m.up_rate, m.acc_v1 - m.up_rate])
  const span = Math.max(0.05, Math.ceil(Math.max(...edge.map(Math.abs), 0) * 20) / 20)
  return <Card>
    <CardHeader title="El examen" sub={`Una sola vez, sobre ${e.months} meses que el modelo original nunca vio (${e.window.first_decision} → ${e.window.last_decision}).`}
      right={<Segmented label="Mercado del examen" value={NAME[market]} options={ready.map(i => NAME[i.market])} onChange={v => setMarket(ready.find(i => NAME[i.market] === v)?.market ?? market)} />} />
    <CardBody className="space-y-6">
      <div className={clsx('rounded-lg border p-4', signal ? 'border-up/40 bg-up/5' : 'border-warn/40 bg-warn/5')}>
        <Badge tone={signal ? 'up' : 'warn'}>{signal ? 'Hay señal' : 'Sin ventaja demostrada'}</Badge>
        <p className="mt-2 text-base font-semibold">{signal
          ? 'El algoritmo acierta más de lo que acertaría el azar informado.'
          : `Acierta lo mismo que decir siempre «sube» (${pct(best.accuracy)} frente a ${pct(e.always_up_accuracy)}).`}</p>
        <p className="mt-1 text-sm text-muted">{e.n.toLocaleString('es-ES')} pronósticos de {e.tickers.length} {e.tickers.length === 1 ? 'activo' : 'activos'}. {learning
          ? 'Reentrenar cada mes fue algo mejor que el modelo fijo, así que ahora el sistema se reentrena solo.'
          : 'Reentrenar no mejoró al modelo fijo, así que se queda el modelo fijo (y el reentreno sigue compitiendo en paralelo).'}</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-3 text-sm font-semibold">Tasa de acierto</h3>
          <CompareBars rows={[
            { label: 'Reentreno mensual', value: e.arms.B_LEARNING.accuracy, color: C1 },
            { label: 'V1 fijo (2022)', value: e.arms.A_FROZEN_V1.accuracy, color: C2 },
            { label: 'Decir siempre «sube»', value: e.always_up_accuracy, color: MUTED },
            { label: 'Seguir la tendencia', value: e.momentum_accuracy, color: MUTED, note: 'Momentum: sube si subió las últimas 20 sesiones' },
          ]} />
        </div>
        {calib.length > 0 && <div>
          <h3 className="text-sm font-semibold">¿Sus probabilidades son de fiar?</h3>
          <p className="mb-1 text-xs text-muted">Cada punto agrupa pronósticos con una probabilidad parecida. Sobre la diagonal = cuando dice 60%, sube el 60%. Puntos más grandes = más casos.</p>
          <CalibrationChart label="Calibración" points={calib} color={learning ? C1 : C2} />
        </div>}
      </div>
      {monthly.length > 1 && <div>
        <h3 className="text-sm font-semibold">Ventaja mes a mes sobre «siempre sube»</h3>
        <p className="mb-2 text-xs text-muted">Por encima de la línea del 0 = ese mes acertó más que decir siempre «sube»; por debajo = menos. Un algoritmo útil pasaría casi todo el tiempo por encima. Pasa el ratón para ver cada mes.</p>
        <LineChart label="Acierto mensual" x={monthly.map(m => m.month)} yMin={-span} yMax={span} zero={0} format={pp}
          series={[
            { key: 'learn', label: 'Reentreno', color: C1, values: monthly.map(m => m.acc_learning - m.up_rate) },
            { key: 'v1', label: 'V1 fijo', color: C2, values: monthly.map(m => m.acc_v1 - m.up_rate) },
          ]} />
        <Legend items={[{ label: 'Reentreno mensual', color: C1 }, { label: 'V1 fijo', color: C2 }]} />
      </div>}
      <details className="text-xs text-muted">
        <summary className="cursor-pointer">Cifras técnicas</summary>
        <p className="mt-2">Log loss (más bajo = mejores probabilidades): V1 {e.arms.A_FROZEN_V1.logloss.toFixed(4)} · reentreno {e.arms.B_LEARNING.logloss.toFixed(4)} · tasa base {e.base_rate_logloss.toFixed(4)}. Mejora del reentreno sobre V1: {(e.learning_minus_frozen_gain.mean * 1000).toFixed(1)} milésimas (intervalo 90%: {(e.learning_minus_frozen_gain.low90 * 1000).toFixed(1)} a {(e.learning_minus_frozen_gain.high90 * 1000).toFixed(1)}). Intervalos por meses completos porque los horizontes se solapan. Universo de grandes compañías actuales (sesgo de supervivencia). Costes no modelados.</p>
        {item.refits.length > 0 && <p className="mt-1">Reentrenos: {item.refits.map(r => `${r.version} (${r.train_n.toLocaleString('es-ES')} observaciones hasta ${r.train_target_end})`).join(' · ')}.</p>}
      </details>
    </CardBody>
  </Card>
}

/* ------------------------------------------------------------------ glosario */

const TERMS: [string, string][] = [
  ['Pronóstico', 'Una probabilidad de que el precio esté más alto dentro de 20 sesiones (acciones) o 30 días (bitcoin). Se guarda con fecha y hora antes de saber qué pasa, y no se puede modificar.'],
  ['Revisión', 'Cada pronóstico se mira a mitad de camino (acciones: sesiones 1, 5, 10; bitcoin: días 1, 7, 14) solo para seguir su evolución. El acierto se decide al final del horizonte.'],
  ['V1 fijo', 'El modelo original que entrenó Codex con datos hasta 2022. No cambia nunca; sirve de referencia.'],
  ['Reentreno mensual', 'El mismo tipo de modelo, reentrenado el día 1 de cada mes con todo lo ocurrido hasta entonces. Es «el algoritmo que aprende».'],
  ['Campeón', 'El modelo que se usa como principal. Lo decidió el examen y lo puede cambiar una regla fijada de antemano si los pronósticos reales dicen lo contrario.'],
  ['Siempre sube', 'La referencia a batir: decir «sube» siempre. Como las acciones suben más a menudo de lo que bajan, ya acierta en torno al 55–60%. Un algoritmo que no la supera no aporta.'],
  ['Examen', 'Prueba única sobre 2022–2026, años que el modelo original no vio. Se hizo una sola vez y con reglas escritas antes de ver resultados, para no engañarnos.'],
  ['Calibración', 'Si cuando dice 60% sube el 60% de las veces, sus probabilidades son de fiar aunque no acierte mucho más.'],
  ['Señal', 'Información útil para predecir. Hoy el modelo solo mira precios pasados y no encuentra señal; el siguiente paso sería darle datos de empresa (beneficios, valoración).'],
]

export function Glossary() {
  return <Card>
    <CardHeader title="Qué significa cada cosa" />
    <CardBody className="grid gap-x-8 gap-y-3 md:grid-cols-2">{TERMS.map(([t, d]) => <div key={t} className="text-sm"><b>{t}</b><p className="text-muted">{d}</p></div>)}</CardBody>
  </Card>
}
