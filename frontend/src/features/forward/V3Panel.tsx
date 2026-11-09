import clsx from 'clsx'
import { Badge, Card, CardBody, CardHeader } from '../../components/ui/primitives'
import { CompareBars, Legend, LineChart } from './charts'

type Interval = { mean: number; low90: number; high90: number }
type Arm = { accuracy: number; logloss: number; signal_verdict: string; gain_vs_base_rate: Interval }
export type V3 = {
  family: string
  features: string[]
  exam: null | {
    window: { first_decision: string; last_decision: string }
    n: number; months: number; tickers: string[]; always_up_accuracy: number
    fundamental_coverage: Record<string, number>
    arms: { B_PRICE_V2: Arm; C_PRICE_FUND_V3: Arm }
    v3_minus_v2_gain: Interval; policy: string
    monthly: { month: string; n: number; up_rate: number; acc_v2: number; acc_v3: number }[]
  }
  refits: { version: string; train_n: number; trained_at: string }[]
  forward: { pairs: number; dates: number; v3_gain?: Interval }
}

const C1 = 'var(--series-1)'
const C2 = 'var(--series-2)'
const MUTED = 'var(--muted)'
const pct = (n: number, d = 1) => `${(n * 100).toFixed(d)}%`
const pp = (n: number) => `${n >= 0 ? '+' : ''}${(n * 100).toFixed(1)} pp`
const PLAIN: Record<string, string> = {
  fund_operating_margin: 'Margen operativo: cuánto gana de cada euro que vende',
  fund_roa: 'Rentabilidad sobre activos: cuánto gana con lo que tiene',
  fund_revenue_yoy: 'Crecimiento de ventas frente a hace un año',
  fund_debt_to_assets: 'Deuda sobre activos: cuánto está endeudada',
  val_earnings_yield: 'Rentabilidad por beneficios: beneficio / precio (alto = barata)',
  val_fcf_yield: 'Rentabilidad por caja: caja libre / precio (alto = barata)',
}

export function V3Panel({ v3 }: { v3?: V3 }) {
  if (!v3) return null
  const e = v3.exam
  return <Card>
    <CardHeader title="¿Ayudan los resultados de las empresas?" sub="Versión v3: los mismos 10 datos de precio + 6 datos de las cuentas que las empresas publican en la SEC. Se descargan solos cada noche." />
    <CardBody className="space-y-5">
      <div>
        <h3 className="mb-2 text-sm font-semibold">Qué mira de cada empresa</h3>
        <ul className="grid gap-x-6 gap-y-1 text-sm md:grid-cols-2">{v3.features.map(f => <li key={f} className="flex items-start gap-2">
          <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
          <span>{PLAIN[f] ?? f}{e ? <span className="num text-xs text-muted"> · disponible en el {pct(e.fundamental_coverage[f] ?? 0, 0)} de los casos</span> : null}</span>
        </li>)}</ul>
        <p className="mt-2 text-xs text-muted">Cada dato cuenta desde el momento exacto en que la empresa lo presentó, nunca antes. Bancos y aseguradoras no tienen estos ratios: para ellos el modelo usa valores neutros.</p>
      </div>
      {!e ? <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted">Examen pendiente: se hace solo en la próxima ejecución diaria, cuando estén descargados los resultados de las empresas.</p> : <V3Exam e={e} />}
      {!!v3.refits.length && <p className="text-xs text-muted">Reentrenos v3: {v3.refits.map(r => `${r.version} (${r.train_n.toLocaleString('es-ES')} obs.)`).join(' · ')}. Pronósticos reales comparables v2 vs v3: {v3.forward.pairs} pares en {v3.forward.dates} fechas.</p>}
    </CardBody>
  </Card>
}

function V3Exam({ e }: { e: NonNullable<V3['exam']> }) {
  const b = e.arms.B_PRICE_V2
  const c = e.arms.C_PRICE_FUND_V3
  const better = e.v3_minus_v2_gain.mean > 0
  const signal = c.signal_verdict === 'EVIDENCE_OF_SIGNAL'
  const edge = e.monthly.flatMap(m => [m.acc_v3 - m.up_rate, m.acc_v2 - m.up_rate])
  const span = Math.max(0.05, Math.ceil(Math.max(...edge.map(Math.abs), 0) * 20) / 20)
  return <>
    <div className={clsx('rounded-lg border p-4', signal ? 'border-up/40 bg-up/5' : better ? 'border-info/40 bg-info/5' : 'border-warn/40 bg-warn/5')}>
      <Badge tone={signal ? 'up' : better ? 'info' : 'warn'}>{signal ? 'Hay señal' : better ? 'Mejora, sin ventaja demostrada' : 'No mejora'}</Badge>
      <p className="mt-2 text-base font-semibold">{signal
        ? `Con los resultados de las empresas supera a «siempre sube»: ${pct(c.accuracy)} frente a ${pct(e.always_up_accuracy)}.`
        : better
          ? `Con los resultados de las empresas mejora algo las probabilidades, pero acierta lo mismo que «siempre sube» (${pct(c.accuracy)} frente a ${pct(e.always_up_accuracy)}).`
          : `Añadir los resultados de las empresas no mejora al modelo de solo precio (${pct(c.accuracy)} frente a ${pct(b.accuracy)}).`}</p>
      <p className="mt-1 text-sm text-muted">Examen único sobre {e.n.toLocaleString('es-ES')} pronósticos ({e.window.first_decision} → {e.window.last_decision}). {e.policy === 'LEARNING_V3' ? 'Por eso v3 pasa a ser el campeón de acciones.' : 'El campeón no cambia; v3 sigue compitiendo con pronósticos reales y puede ganar el puesto más adelante.'}</p>
    </div>
    <div className="space-y-6">
      <div className="max-w-xl">
        <h3 className="mb-3 text-sm font-semibold">Tasa de acierto</h3>
        <CompareBars rows={[
          { label: 'v3: precio + resultados', value: c.accuracy, color: C1 },
          { label: 'v2: solo precio', value: b.accuracy, color: C2 },
          { label: 'Decir siempre «sube»', value: e.always_up_accuracy, color: MUTED },
        ]} />
      </div>
      <div>
        <h3 className="text-sm font-semibold">Ventaja mes a mes sobre «siempre sube»</h3>
        <LineChart label="Ventaja mensual v3" x={e.monthly.map(m => m.month.slice(0, 7))} yMin={-span} yMax={span} zero={0} format={pp}
          series={[
            { key: 'v3', label: 'v3', color: C1, values: e.monthly.map(m => m.acc_v3 - m.up_rate) },
            { key: 'v2', label: 'v2', color: C2, values: e.monthly.map(m => m.acc_v2 - m.up_rate) },
          ]} />
        <Legend items={[{ label: 'v3: precio + resultados', color: C1 }, { label: 'v2: solo precio', color: C2 }]} />
      </div>
    </div>
    <details className="text-xs text-muted">
      <summary className="cursor-pointer">Cifras técnicas</summary>
      <p className="mt-2">Log loss v2 {b.logloss.toFixed(4)} · v3 {c.logloss.toFixed(4)}. Mejora de v3 sobre v2: {(e.v3_minus_v2_gain.mean * 1000).toFixed(1)} milésimas (intervalo 90%: {(e.v3_minus_v2_gain.low90 * 1000).toFixed(1)} a {(e.v3_minus_v2_gain.high90 * 1000).toFixed(1)}). Esta ventana ya se usó en el primer examen: los 6 datos se eligieron antes, de la literatura, y no se ha ajustado nada; aun así es una prueba menos virgen que la primera.</p>
    </details>
  </>
}
