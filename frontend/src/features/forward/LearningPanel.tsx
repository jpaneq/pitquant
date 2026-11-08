import { Card, CardBody, CardHeader } from '../../components/ui/primitives'

type Interval = { mean: number; low90: number; high90: number; clusters: number }
type Arm = { n: number; accuracy: number; brier: number; logloss: number; mean_p_up: number; gain_vs_base_rate: Interval; signal_verdict: string }
type Exam = {
  window: { first_decision: string; last_decision: string; last_target: string }
  n: number; months: number; tickers: string[]; base_rate_p: number
  always_up_accuracy: number; momentum_accuracy: number; base_rate_logloss: number
  arms: { A_FROZEN_V1: Arm; B_LEARNING: Arm }
  learning_minus_frozen_gain: Interval; policy: string
}
type Refit = { model_id: string; version: string; trained_at: string; train_n: number; train_target_end: string; tickers: number }
export type Learning = {
  market: string
  exam: Exam | null
  policy_history: { policy: string; reason: string; decided_at: string }[]
  champion: { model_id: string; version: string; family: string } | null
  refits: Refit[]
  forward: { pairs: number; dates: number; v1_logloss?: number; learning_logloss?: number; learning_gain?: Interval }
}

const pct = (n: number) => `${(n * 100).toFixed(1)}%`
const num = (n: number) => n.toFixed(4)
const range = (i: Interval) => `${(i.mean * 1000).toFixed(1)} (90%: ${(i.low90 * 1000).toFixed(1)} a ${(i.high90 * 1000).toFixed(1)})`
const VERDICT: Record<string, string> = {
  EVIDENCE_OF_SIGNAL: 'Hay señal: mejora a la tasa base con un intervalo que no toca cero',
  NO_EVIDENCE: 'Sin evidencia de señal: no se distingue de la tasa base',
  WORSE_THAN_BASE_RATE: 'Peor que la tasa base',
}

export function LearningPanel({ items }: { items: Learning[] }) {
  if (!items.some(i => i.exam || i.refits.length)) return null
  return <Card>
    <CardHeader title="Aprendizaje continuo" sub="Examen único sobre lo que V1 nunca vio, reentreno mensual y regla de cambio fijada de antemano (ADR-0064)." />
    <CardBody>
      <div className="grid gap-6 lg:grid-cols-2">{items.map(item => <LearningMarket key={item.market} item={item} />)}</div>
      <p className="mt-4 text-xs text-muted">Pérdida logarítmica (log loss): cuanto más baja, mejores probabilidades. Las mejoras se muestran en milésimas de log loss. Intervalos por remuestreo de meses completos, porque los horizontes se solapan. Universo de grandes compañías actuales: tiene sesgo de supervivencia. Costes no modelados; no se abren órdenes.</p>
    </CardBody>
  </Card>
}

function LearningMarket({ item }: { item: Learning }) {
  const exam = item.exam
  const policy = item.policy_history.at(-1)
  const title = item.market === 'BTC' ? 'Bitcoin · 30 días' : 'Acciones EE. UU. · 20 sesiones'
  return <section aria-label={`Aprendizaje ${item.market}`} className="space-y-3 text-sm">
    <h3 className="text-base font-semibold">{title}</h3>
    {policy && <p className="rounded border border-border p-2">
      <b>{policy.policy === 'LEARNING' ? 'Aprendiendo' : 'Modelo fijo V1'}</b>
      {' · '}campeón: {item.champion?.version ?? '—'}
      {' · '}{policy.reason === 'EXAM' ? 'decidido por el examen' : 'cambiado por la regla de pronósticos reales'} ({policy.decided_at.slice(0, 10)})
    </p>}
    {exam ? <>
      <p>Examen: {exam.n.toLocaleString()} decisiones de {exam.window.first_decision} a {exam.window.last_decision} ({exam.months} meses, {exam.tickers.length} activos).</p>
      <table className="num w-full text-left text-xs [&_td]:pr-3 [&_th]:pr-3">
        <thead><tr><th>Método</th><th>Acierto</th><th>Log loss</th><th>Mejora vs tasa base</th></tr></thead>
        <tbody>
          <tr className="border-t border-border"><td className="py-1">V1 fijo</td><td>{pct(exam.arms.A_FROZEN_V1.accuracy)}</td><td>{num(exam.arms.A_FROZEN_V1.logloss)}</td><td>{range(exam.arms.A_FROZEN_V1.gain_vs_base_rate)}</td></tr>
          <tr className="border-t border-border"><td className="py-1">Reentreno mensual</td><td>{pct(exam.arms.B_LEARNING.accuracy)}</td><td>{num(exam.arms.B_LEARNING.logloss)}</td><td>{range(exam.arms.B_LEARNING.gain_vs_base_rate)}</td></tr>
          <tr className="border-t border-border"><td className="py-1">Siempre sube</td><td>{pct(exam.always_up_accuracy)}</td><td>—</td><td>—</td></tr>
          <tr className="border-t border-border"><td className="py-1">Momentum 20</td><td>{pct(exam.momentum_accuracy)}</td><td>—</td><td>—</td></tr>
          <tr className="border-t border-border"><td className="py-1">Tasa base ({pct(exam.base_rate_p)})</td><td>—</td><td>{num(exam.base_rate_logloss)}</td><td>0</td></tr>
        </tbody>
      </table>
      <p>V1 fijo: {VERDICT[exam.arms.A_FROZEN_V1.signal_verdict] ?? exam.arms.A_FROZEN_V1.signal_verdict}.</p>
      <p>Reentreno mensual: {VERDICT[exam.arms.B_LEARNING.signal_verdict] ?? exam.arms.B_LEARNING.signal_verdict}.</p>
      <p>Reentreno frente a V1: {range(exam.learning_minus_frozen_gain)} milésimas → política <b>{exam.policy === 'LEARNING' ? 'aprender' : 'V1 fijo'}</b>.</p>
    </> : <p className="text-muted">Examen pendiente: necesita el modelo V1 y precios completos.</p>}
    {!!item.refits.length && <p>Reentrenos: {item.refits.map(r => `${r.version} (${r.train_n.toLocaleString()} obs., hasta ${r.train_target_end})`).join(' · ')}</p>}
    <p className="text-xs text-muted">Pronósticos reales comparables V1 vs reentreno: {item.forward.pairs} pares en {item.forward.dates} fechas
      {item.forward.learning_gain ? `; mejora del reentreno ${range(item.forward.learning_gain)}` : ''}. La política cambia sola con ≥200 pares en ≥20 fechas y un intervalo del 90% que no toque cero.</p>
  </section>
}
