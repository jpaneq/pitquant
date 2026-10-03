import { Badge, Card, CardBody, CardHeader } from '../../components/ui/primitives'
import { fmtNum } from '../../lib/format'
import { comparePlanRows, fmtR } from '../../lib/simulation'
import type { Comparison } from './types'

const cell = (x: number | null, r = false) => (x === null ? '—' : r ? fmtR(x) : fmtNum(x))

/** PITQuant ORIGINAL plan vs the USER plan (both frozen at T0) and, when bars exist, the COUNTERFACTUAL of the original plan next to the real outcome. */
export function PlanComparison({ c }: { c: Comparison }) {
  if (c.plan_origin !== 'USER_MODIFIED' || !c.pitquant_original) {
    return <p className="text-xs text-muted" data-testid="plan-same">The simulated plan is the {c.plan_origin === 'PITQUANT' ? 'PITQuant plan exactly' : 'user-defined plan'}: there is nothing to compare.</p>
  }
  const rows = comparePlanRows(c.pitquant_original, c.user_plan)
  const res = (x: Comparison['real'] | Comparison['counterfactual']) => (x ? `${x.state}${x.triggered ? '' : ' · not entered'} · ${fmtR(x.realized_r)} · TP touched ${x.targets_touched?.length ? x.targets_touched.join(',') : 'none'}` : '—')
  return (
    <div className="space-y-3 text-xs" data-testid="plan-comparison">
      <table className="w-full">
        <thead><tr><th className="py-1 text-left font-medium text-muted">Level</th><th className="text-right font-medium text-muted">PITQuant original</th><th className="text-right font-medium text-muted">User plan</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.label} className="border-t border-border"><td className="py-1">{r.label}</td><td className="num text-right">{cell(r.original, r.label.startsWith('Expected'))}</td><td className={`num text-right ${r.changed ? 'font-semibold text-accent' : ''}`} data-changed={r.changed}>{cell(r.user, r.label.startsWith('Expected'))}</td></tr>)}</tbody>
      </table>
      <Card><CardHeader title="Same bars, two plans" sub="the counterfactual is NOT the real outcome and never feeds training" /><CardBody className="space-y-1">
        <div><Badge tone="info">REAL SIMULATION</Badge> <span className="num">{res(c.real)}</span></div>
        <div><Badge tone="warn">COUNTERFACTUAL</Badge> <span className="num" data-testid="counterfactual-line">{res(c.counterfactual)}</span></div>
      </CardBody></Card>
    </div>
  )
}
