import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, apiPost, ApiError } from '../../api/client'
import { Badge, Button, PanelError, Skeleton } from '../../components/ui/primitives'
import { fmtPct } from '../../lib/format'
import { fmtR } from '../../lib/simulation'
import type { PostMortemFacts } from './types'

const CAUSES = ['MODEL_DIRECTION_ERROR', 'MODEL_MAGNITUDE_ERROR', 'TIMING_ERROR', 'ENTRY_ERROR', 'STOP_TOO_TIGHT', 'STOP_TOO_WIDE', 'TARGET_TOO_AGGRESSIVE', 'VALUATION_ERROR', 'FUNDAMENTAL_DETERIORATION', 'TECHNICAL_BREAKDOWN', 'VOLATILITY_UNDERESTIMATED', 'REGIME_CHANGE', 'CORPORATE_ACTION', 'DATA_QUALITY', 'UNEXPECTED_EVENT', 'NO_CLEAR_ERROR'] as const

/** Objective facts first (no verdict), then an explicit human classification, then an optional ResearchHypothesis (UNTESTED). */
export function PostMortemPanel({ id, closed }: { id: string; closed: boolean }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['sim-pm', id], queryFn: ({ signal }) => api<PostMortemFacts>(`/simulations/${id}/postmortem`, signal), enabled: closed })
  const [primary, setPrimary] = useState<string>('NO_CLEAR_ERROR')
  const [secondary, setSecondary] = useState<string[]>([])
  const [notes, setNotes] = useState('')
  const [by, setBy] = useState('')
  const [hyp, setHyp] = useState('')
  const save = useMutation({ mutationFn: () => apiPost(`/simulations/${id}/postmortem`, { primary_cause: primary, secondary_causes: secondary, notes, classified_by: by }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['sim-pm', id] }); qc.invalidateQueries({ queryKey: ['sim', id] }) } })
  const hypo = useMutation({ mutationFn: () => apiPost(`/simulations/${id}/hypothesis`, { statement: hyp, created_by: by }), onSuccess: () => setHyp('') })
  if (!closed) return <p className="text-xs text-muted" data-testid="pm-open">A post-mortem is available once the simulation is CLOSED. No automatic verdict is ever generated.</p>
  if (q.isPending) return <Skeleton className="h-24" />
  if (q.isError) return <PanelError what="Post-mortem" error={q.error} onRetry={() => q.refetch()} />
  const f = q.data.facts
  const m = f.metrics
  return (
    <div className="space-y-3 text-xs" data-testid="postmortem">
      <h3 className="font-semibold">What happened?</h3>
      <dl className="num grid grid-cols-2 gap-3 sm:grid-cols-4">
        {([['Execution outcome', f.execution_outcome ?? '—'], ['Prediction outcome', f.prediction_outcome ?? `n/a (${f.prediction_status})`], ['Realised R', fmtR(m.realized_r)], ['Return', fmtPct(m.realized_return, 1)], ['MAE', fmtPct(m.mae_pct, 1)], ['MFE', fmtPct(m.mfe_pct, 1)], ['Stop distance (ATR, T0)', f.stop_quality.stop_distance_atr === null || f.stop_quality.stop_distance_atr === undefined ? '—' : Number(f.stop_quality.stop_distance_atr).toFixed(2)], ['Entry method', String(f.entry_quality.entry_method ?? '—')]] as [string, string][]).map(([k, v]) => <div key={k}><dt className="text-muted">{k}</dt><dd>{v}</dd></div>)}
      </dl>
      <div data-testid="diagnostic-flags">{f.diagnostic_flags.length ? f.diagnostic_flags.map((d) => <div key={d.flag}><Badge tone="warn">{d.flag}</Badge> <span className="text-muted">{d.definition}</span></div>) : <span className="text-muted">No diagnostic fact flagged.</span>}</div>
      <p className="text-muted">{f.note}</p>
      <fieldset className="space-y-2 rounded border border-border p-3">
        <legend className="px-1 font-semibold">Classification (a person decides)</legend>
        <label className="flex items-center gap-2">Primary cause
          <select aria-label="Primary cause" value={primary} onChange={(e) => setPrimary(e.target.value)} className="rounded border border-border bg-surface-2 px-2 py-1">{CAUSES.map((c) => <option key={c}>{c}</option>)}</select></label>
        <label className="flex items-center gap-2">Secondary causes
          <select aria-label="Secondary causes" multiple value={secondary} onChange={(e) => setSecondary(Array.from(e.target.selectedOptions, (o) => o.value))} className="h-20 rounded border border-border bg-surface-2 px-2 py-1">{CAUSES.filter((c) => c !== primary).map((c) => <option key={c}>{c}</option>)}</select></label>
        <label className="flex flex-col gap-1">Notes<textarea aria-label="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} className="rounded border border-border bg-surface-2 px-2 py-1" /></label>
        <label className="flex items-center gap-2">Classified by<input aria-label="Classified by" value={by} onChange={(e) => setBy(e.target.value)} className="rounded border border-border bg-surface-2 px-2 py-1" /></label>
        {save.isError ? <p role="alert" className="text-down">{(save.error as ApiError).message}</p> : null}
        <Button variant="solid" disabled={!by.trim() || save.isPending} onClick={() => save.mutate()} data-testid="pm-save">Save classification</Button>
      </fieldset>
      {q.data.classifications.map((p, i) => <div key={i} data-testid="pm-saved"><b>{p.primary_cause}</b> {p.secondary_causes.join(', ')} — {p.classified_by}{p.notes ? `: ${p.notes}` : ''}</div>)}
      <fieldset className="space-y-2 rounded border border-border p-3">
        <legend className="px-1 font-semibold">Research hypothesis</legend>
        <textarea aria-label="Hypothesis statement" value={hyp} onChange={(e) => setHyp(e.target.value)} placeholder="e.g. pullback setups with a stop under 1 ATR may stop out despite positive 6M outcomes" className="w-full rounded border border-border bg-surface-2 px-2 py-1" />
        {hypo.isSuccess ? <p data-testid="hyp-created" className="text-up">Hypothesis created as UNTESTED. It changes no model, dataset or champion.</p> : null}
        <Button disabled={!hyp.trim() || !by.trim() || hypo.isPending} onClick={() => hypo.mutate()} data-testid="hyp-create">Create research hypothesis</Button>
      </fieldset>
    </div>
  )
}
