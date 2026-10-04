import type { UseQueryResult } from '@tanstack/react-query'
import type { Signals } from '../../api/types'
import { fmtNum, fmtPct } from '../../lib/format'

const STATE: Record<string, string> = { TP1: 'TP1', TP2: 'TP2', STOPPED: 'Stop', INVALIDATED: 'Invalidada', EXPIRED: 'Caducada', WAITING_ENTRY: 'Sin entrada', ENTERED: 'Abierta', PARTIAL_TP: 'Parcial' }

/** What the rule-based plan WOULD have done (R) and the user's real paper trades (F). Descriptive: not a forecast, not validated. */
export function SignalsPanel({ q, retro }: { q: UseQueryResult<Signals>; retro: boolean }) {
  if (q.isPending) return <p className="border-t border-border px-3 py-2 text-xs text-muted">Calculando señales históricas…</p>
  if (q.isError || !q.data) return <p role="alert" className="border-t border-border px-3 py-2 text-xs text-bad">No se pudieron calcular las señales.</p>
  const r = q.data.retrospective
  const sm = r.summary
  const filled = r.trades.filter((t) => t.entry_date)
  return (
    <section aria-label="Señales del algoritmo" className="space-y-2 border-t border-border px-3 py-2 text-xs">
      <p className="font-medium text-warn">{retro ? `${r.label ?? 'RETROSPECTIVE'} · R = repetición con datos conocidos en cada fecha; F = tus pruebas paper reales. No es una predicción ni un backtest validado.` : 'F = tus pruebas paper reales.'}</p>
      {retro && sm ? (
        <>
          <p>
            {sm.n_decisions} decisiones · {sm.n_filled} entradas · {sm.n_closed} cerradas · sin entrada {sm.n_not_filled} · sin plan {sm.no_plan} · en posición {sm.skipped_in_position} · holdout omitido {sm.holdout_skipped}
          </p>
          {sm.hit_rate !== undefined ? (
            <p>
              Aciertos {fmtPct(sm.hit_rate, 0)} · retorno medio por operación {fmtPct(sm.mean_return, 2, true)} · R medio {fmtNum(sm.mean_r ?? undefined)}
              {sm.buy_and_hold_return_same_span !== null ? ` · comprar y mantener en el mismo tramo ${fmtPct(sm.buy_and_hold_return_same_span, 0, true)}` : ''}
            </p>
          ) : (
            <p className="text-warn">Muestra insuficiente (menos de 10 operaciones cerradas): no se muestra ninguna tasa.</p>
          )}
          <p className="text-muted">{sm.flags.join(' · ')}</p>
          {filled.length > 0 ? (
            <div className="max-h-48 overflow-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-muted"><th>Decisión</th><th>Entrada</th><th>Salida</th><th>Estado</th><th>Retorno</th><th>R</th></tr>
                </thead>
                <tbody>
                  {filled.map((t) => (
                    <tr key={t.decision_date} className="border-t border-border/50">
                      <td>{t.decision_date}</td>
                      <td>{t.entry_date} @ {fmtNum(t.entry_price_chart)}</td>
                      <td>{t.exit_date ?? '—'}</td>
                      <td>{STATE[t.state] ?? t.state}</td>
                      <td>{fmtPct(t.realized_return ?? undefined, 2, true)}</td>
                      <td>{fmtNum(t.realized_r ?? undefined)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : null}
      {q.data.forward.length > 0 ? <p>Pruebas paper reales en el gráfico: {q.data.forward.filter((m) => m.kind === 'PLAN').length}</p> : null}
      <p className="text-muted">Precios en unidades del gráfico (ajustados por splits). {q.data.holdout?.note}</p>
    </section>
  )
}
