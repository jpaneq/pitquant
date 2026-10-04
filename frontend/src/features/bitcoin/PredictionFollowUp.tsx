import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiPost } from '../../api/client'

type Item = { prediction_id: string; decision_at: string; horizon: number; target_at: string; state: string; days_remaining: number; predicted: number | null; p_up: number | null; actual?: number; error?: number | null; direction_correct?: boolean; hist_percentile_of_actual?: number | null }
type Horizon = { n_evaluated: number; n_scored: number; flags: string[]; mae?: number; bias?: number; direction_hit_rate?: number; always_up_hit_rate?: number; skill_vs_zero?: number | null; skill_vs_hist_mean?: number | null; brier_p_up?: number | null; beats_baselines?: boolean | null }
type Evaluation = { items: Item[]; horizons: Record<string, Horizon>; next_maturity: string | null; counts: Record<string, number>; warning: string }
const pct = (v?: number | null, d = 2) => v == null ? '—' : `${(v * 100).toFixed(d)}%`
const STATE: Record<string, string> = { PENDING: 'Pendiente', EVALUATED: 'Evaluada', AWAITING_TARGET_BAR: 'Madura, falta la vela objetivo' }

/** Follow-up of frozen predictions: when each one matures, how it did, and how it compares with history. Descriptive only; nothing is promoted. */
export function PredictionFollowUp({ cohort }: { cohort: string }) {
  const client = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const { data } = useQuery({ queryKey: ['btc-evaluation', cohort], queryFn: () => api<Evaluation>(`/btc/evaluation?cohort=${cohort}`), refetchInterval: 60000 })
  const check = async () => {
    setBusy(true)
    try {
      const r = await apiPost<{ revealed: string[]; awaiting_target_bar: unknown[]; pending_not_mature: number }>(`/btc/evaluation/run?cohort=${cohort}`, {})
      setMessage(`${r.revealed.length} evaluadas ahora · ${r.pending_not_mature} aún no maduras · ${r.awaiting_target_bar.length} esperando la vela objetivo`)
      await client.invalidateQueries({ queryKey: ['btc-evaluation'] })
    } catch (e) { setMessage(String(e)) } finally { setBusy(false) }
  }
  const horizons = Object.entries(data?.horizons ?? {})
  return <section aria-label="Seguimiento de predicciones" className="space-y-3 rounded-lg border border-border bg-surface p-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">Seguimiento de predicciones</h2><button disabled={busy} onClick={check} className="rounded border border-border px-3 py-2 text-xs">Comprobar predicciones maduras ahora</button></div>
    <p className="text-xs text-muted">Cada predicción se comprueba sola cuando vence su horizonte (rutina diaria). Pendientes {data?.counts.PENDING ?? 0} · evaluadas {data?.counts.EVALUATED ?? 0} · próxima madurez {data?.next_maturity ? new Date(data.next_maturity).toLocaleString() : '—'}</p>
    {message && <p role="status" className="text-xs">{message}</p>}
    {horizons.length > 0 && <table className="w-full text-xs"><thead><tr className="text-left text-muted"><th>Horizonte</th><th>N</th><th>Error medio abs.</th><th>Sesgo</th><th>Aciertos dir.</th><th>«Siempre sube»</th><th>Mejora vs 0</th><th>Mejora vs media histórica</th><th>Avisos</th></tr></thead><tbody>{horizons.map(([h, s]) => <tr key={h} className="border-t border-border/50"><td>{h}D</td><td>{s.n_scored}</td><td>{pct(s.mae)}</td><td>{pct(s.bias)}</td><td>{pct(s.direction_hit_rate, 0)}</td><td>{pct(s.always_up_hit_rate, 0)}</td><td>{pct(s.skill_vs_zero, 0)}</td><td>{pct(s.skill_vs_hist_mean, 0)}</td><td className="text-warn">{s.flags.join(' · ')}</td></tr>)}</tbody></table>}
    <div className="max-h-80 overflow-auto"><table className="w-full text-xs"><thead><tr className="text-left text-muted"><th>Generada para</th><th>Horizonte</th><th>Vence</th><th>Estado</th><th>Previsto</th><th>Real</th><th>Error</th><th>Dirección</th><th>Percentil histórico</th></tr></thead><tbody>{(data?.items ?? []).map(i => <tr key={i.prediction_id} className="border-t border-border/50"><td>{i.decision_at.slice(0, 10)}</td><td>{i.horizon}D</td><td>{i.target_at.slice(0, 10)}{i.state === 'PENDING' && ` (en ${i.days_remaining} d)`}</td><td>{STATE[i.state] ?? i.state}</td><td>{pct(i.predicted)}</td><td>{pct(i.actual)}</td><td>{pct(i.error)}</td><td>{i.direction_correct == null ? '—' : i.direction_correct ? 'Acierto' : 'Fallo'}</td><td>{pct(i.hist_percentile_of_actual, 0)}</td></tr>)}</tbody></table></div>
    <p className="text-xs text-muted">{data?.warning} · Las muestras pequeñas no prueban nada; horizontes solapados no son observaciones independientes; la historia se descargó hoy (no es PIT).</p>
  </section>
}
