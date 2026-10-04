import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export type Tracking = {
  status: string; expected?: number | null; actual?: number | null; error?: number | null
  outcome_status?: string; plan_status?: string; forecast_correct?: boolean | null
  validation_status?: string
  frozen?: { prediction_id: string; prediction_hash: string; horizon_days: number; target_at: string; payload: Record<string, unknown> }
}
const percentage = (v?: number | null) => v == null ? '—' : `${(v * 100).toFixed(2)}%`
export function ForecastTracking({ tracking }: { tracking: Tracking }) {
  return <div aria-label="Frozen forecast tracking" className="my-4 rounded border border-border p-4"><h3 className="font-semibold">Predicción registrada al lanzar la operación</h3><p className="my-2 text-xs">{tracking.frozen?.horizon_days}D · {tracking.validation_status ?? tracking.status} · modelo y objetivos originales conservados</p><dl className="grid gap-3 md:grid-cols-3">{[['Retorno previsto', tracking.expected], ['Retorno real del horizonte', tracking.actual], ['Error previsto − real', tracking.error]].map(([label,v]) => <div key={String(label)}><dt className="text-xs text-muted">{label}</dt><dd>{percentage(v as number | null)}</dd></div>)}</dl><p className="mt-3 text-sm">Acierto direccional: {tracking.forecast_correct == null ? 'Pendiente / no evaluable' : tracking.forecast_correct ? 'Sí' : 'No'}</p><p className="text-xs">Horizonte: {tracking.outcome_status ?? 'Sin vínculo'} · Plan: {tracking.plan_status ?? 'Pendiente'}</p><details className="mt-2 text-xs"><summary>Predicción original y hash</summary><pre className="overflow-auto">{JSON.stringify(tracking.frozen, null, 2)}</pre></details></div>
}

type HistoricalEvidence = { status: string; n_raw?: number; mae?: number; direction_hit_rate?: number; holdout_start?: string; always_up_hit_rate?: number; nonoverlap_cohorts?: number; oos?: { decision_at: string; p_up: number; expected: number; actual: number; error: number }[] }
export function RetrospectiveEvidence({ horizon }: { horizon: number }) {
  const { data } = useQuery({ queryKey: ['btc-retrospective', horizon], queryFn: () => api<HistoricalEvidence>(`/btc/experimental/history?horizon=${horizon}`) })
  return <div className="rounded-lg border border-border p-4"><h2 className="font-semibold">Prueba retrospectiva con cotizaciones antiguas</h2><p className="my-2 text-xs text-warn">RETROSPECTIVE — precios descargados hoy; no se acredita PIT histórico. Holdout {data?.holdout_start ?? '2025-10-01'} excluido del entrenamiento y de estas métricas.</p><p className="text-sm">{horizon}D · {data?.status ?? 'Cargando'} · N bruto {data?.n_raw ?? 0} · error absoluto medio {percentage(data?.mae)} · aciertos direccionales {percentage(data?.direction_hit_rate)}</p><p className="my-2 text-xs">Benchmark «siempre sube»: {percentage(data?.always_up_hit_rate)} · cohortes no solapadas reportadas: {data?.nonoverlap_cohorts ?? '—'}. Los horizontes solapan; N bruto no equivale a N independiente. Ningún modelo se promueve automáticamente.</p><div className="max-h-80 overflow-auto"><table className="w-full text-xs"><thead><tr><th>Fecha</th><th>P(up)</th><th>Previsto</th><th>Real</th><th>Error</th></tr></thead><tbody>{data?.oos?.map(p => <tr key={p.decision_at}><td>{p.decision_at.slice(0,10)}</td><td>{percentage(p.p_up)}</td><td>{percentage(p.expected)}</td><td>{percentage(p.actual)}</td><td>{percentage(p.error)}</td></tr>)}</tbody></table></div></div>
}
