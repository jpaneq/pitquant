import { useState } from 'react'
import { useAnalysis, useFilings, useFundamentals, usePrediction, useTechnicals, useValuation } from '../../api/hooks'
import type { Label, MetricGroup, Metric as MetricT, Summary, Zone } from '../../api/types'
import { Badge, Card, CardBody, CardHeader, Metric, PanelError, Skeleton } from '../../components/ui/primitives'
import { fmtCompact, fmtDate, fmtMult, fmtNum, fmtPct, signClass } from '../../lib/format'

const asM = (g: MetricGroup | undefined, k: string): MetricT => (g?.[k] as MetricT | undefined) ?? { value: null }

// ───────────────────────────── Analysis summary strip ────────────────────────────────────────────
const ORDER: [string, string][] = [
  ['fundamentals', 'Fundamentals'], ['growth', 'Growth'], ['valuation', 'Valuation'], ['trend', 'Trend'],
  ['momentum', 'Momentum'], ['relative_strength', 'Relative strength'], ['risk', 'Risk'], ['data_quality', 'Data quality'],
]
function labelTone(k: string, l: string): 'up' | 'down' | 'warn' | 'info' | 'neutral' {
  if (l === 'Insufficient' || l === '—') return 'neutral'
  if (k === 'valuation') return l === 'Expensive' ? 'warn' : l === 'Cheap' ? 'info' : 'neutral'
  if (k === 'risk') return l === 'High' ? 'warn' : l === 'Low' ? 'info' : 'neutral'
  if (k === 'data_quality') return l === 'High' ? 'info' : l === 'Low' ? 'warn' : 'neutral'
  return /Strong|Positive|Uptrend|Outperforming/.test(l) ? 'info' : /Weak|Negative|Downtrend|Underperforming/.test(l) ? 'warn' : 'neutral'
}
export function AnalysisSummary({ summary }: { summary: Summary }) {
  return (
    <Card>
      <div className="grid grid-cols-2 divide-border sm:grid-cols-4 lg:grid-cols-8 lg:divide-x">
        {ORDER.map(([k, name]) => {
          const d: Label | undefined = summary.summary_detail[k]
          const l = d?.label ?? '—'
          return (
            <div key={k} className="px-3 py-2.5" title={d?.note ?? (d?.reference_type ? `Reference: ${d.reference_type}` : undefined)}>
              <div className="text-[10px] uppercase tracking-[0.08em] text-muted">{name}</div>
              <div className="mt-1 flex items-center gap-1.5">
                <Badge tone={labelTone(k, l)}>{l}</Badge>
                {d?.coverage ? <span className="num text-[10px] text-muted">{d.coverage}</span> : null}
              </div>
            </div>
          )
        })}
      </div>
      <div className="grid gap-px border-t border-border bg-border md:grid-cols-2">
        <ReasonList title="Positives" items={summary.positives} tone="info" />
        <ReasonList title="Risks" items={summary.risks} tone="warn" />
      </div>
      <p className="border-t border-border px-4 py-1.5 text-[10px] text-muted">
        Analysis Engine V0 · rule-based structured analysis from real data · <b>not a prediction</b> · no BUY/HOLD/SELL
      </p>
    </Card>
  )
}
function ReasonList({ title, items, tone }: { title: string; items: Summary['positives']; tone: 'info' | 'warn' }) {
  return (
    <div className="bg-surface px-4 py-2.5">
      <div className="text-[10px] uppercase tracking-[0.08em] text-muted">{title}</div>
      {items.length === 0 ? <div className="mt-1 text-xs text-muted">None flagged by the V0 rules.</div> : null}
      <ul className="mt-1 space-y-1">
        {items.map((r) => (
          <li key={r.reason_code} className="flex items-start gap-2 text-xs" title={`${r.reason_code}: ${r.metric} = ${r.value} (ref ${r.reference})`}>
            <Badge tone={tone}>{tone === 'info' ? '+' : '!'}</Badge>
            <span>{r.rendered_text}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ───────────────────────────── four main cards ───────────────────────────────────────────────────
function CardShell({ title, sub, q, children, expandable }: { title: string; sub?: string; q: { isPending: boolean; isError: boolean; error: unknown; refetch: () => unknown }; children: React.ReactNode; expandable?: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <Card className="flex flex-col">
      <CardHeader title={title} sub={sub} right={expandable ? <button className="text-[11px] text-accent" onClick={() => setOpen((o) => !o)} aria-expanded={open}>{open ? 'Less' : 'Details'}</button> : undefined} />
      <CardBody className="grow">
        {q.isPending ? <div className="grid grid-cols-2 gap-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div> : q.isError ? <PanelError what={title} error={q.error} onRetry={() => q.refetch()} /> : children}
        {open && expandable ? <div className="mt-4 border-t border-border pt-3">{expandable}</div> : null}
      </CardBody>
    </Card>
  )
}

export function FundamentalsCard({ sec, special }: { sec: string; special: boolean }) {
  const q = useFundamentals(sec)
  const f = q.data
  const m = (g: string, k: string) => asM(f?.[g as keyof typeof f] as MetricGroup | undefined, k)
  const yoy = (k: string) => m('growth', k)
  return (
    <CardShell title="Fundamentals" sub={f?.latest_period ? `TTM to ${fmtDate(f.latest_period)} · SEC` : 'SEC EDGAR'} q={q} expandable={f?.status === 'OK' ? <FundamentalDetail f={f} /> : undefined}>
      {special ? <div className="mb-2 text-[11px] text-warn">SPECIALIZED FUNDAMENTAL PROFILE NOT YET SUPPORTED — industrial metrics withheld.</div> : null}
      {f?.status !== 'OK' ? <div className="text-sm text-muted">No SEC fundamentals known for this security.</div> : special ? null : (
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          <Metric label="Revenue TTM" value={fmtCompact(m('ttm', 'revenue').value, '$')} context={`${fmtPct(yoy('revenue_yoy').value, 1, true)} YoY`} reason={m('ttm', 'revenue').reason} />
          <Metric label="Operating income TTM" value={fmtCompact(m('ttm', 'operating_income').value, '$')} context={`${fmtPct(yoy('operating_income_yoy').value, 1, true)} YoY`} reason={m('ttm', 'operating_income').reason} />
          <Metric label="Net income TTM" value={fmtCompact(m('ttm', 'net_income').value, '$')} context={`${fmtPct(yoy('net_income_yoy').value, 1, true)} YoY`} reason={m('ttm', 'net_income').reason} />
          <Metric label="Free cash flow TTM" value={fmtCompact(m('ttm', 'fcf').value, '$')} context={yoy('fcf_yoy').value === null ? undefined : `${fmtPct(yoy('fcf_yoy').value, 1, true)} YoY`} reason={m('ttm', 'fcf').reason} />
          <Metric label="Operating margin" value={fmtPct(m('profitability', 'operating_margin').value)} reason={m('profitability', 'operating_margin').reason} />
          <Metric label="FCF margin" value={fmtPct(m('profitability', 'fcf_margin').value)} reason={m('profitability', 'fcf_margin').reason} />
        </div>
      )}
      {f?.coverage ? <div className="num mt-3 text-[10px] text-muted">coverage {f.coverage.available}/{f.coverage.expected} metrics</div> : null}
    </CardShell>
  )
}
const GROUPS: [string, string, 'pct' | 'money' | 'x' | 'num'][] = [
  ['profitability', 'roa', 'pct'], ['profitability', 'roe', 'pct'], ['profitability', 'gross_profitability', 'pct'], ['quality', 'cfo_to_net_income', 'x'], ['quality', 'accruals_to_assets', 'pct'],
  ['growth', 'revenue_cagr3', 'pct'], ['growth', 'operating_income_cagr3', 'pct'], ['growth', 'fcf_cagr3', 'pct'], ['investment', 'asset_growth1', 'pct'], ['investment', 'capex_to_assets', 'pct'],
  ['balance', 'total_debt', 'money'], ['balance', 'net_debt', 'money'], ['balance', 'debt_to_equity', 'x'], ['balance', 'current_ratio', 'x'], ['balance', 'interest_coverage', 'x'],
  ['capital_allocation', 'shares_growth1', 'pct'], ['capital_allocation', 'dividend_yield', 'pct'], ['capital_allocation', 'buyback_yield', 'pct'], ['capital_allocation', 'shareholder_yield', 'pct'],
]
function FundamentalDetail({ f }: { f: NonNullable<ReturnType<typeof useFundamentals>['data']> }) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-3">
      {GROUPS.map(([g, k, kind]) => {
        const v = asM(f[g as 'ttm'], k)
        const text = kind === 'pct' ? fmtPct(v.value, 1) : kind === 'money' ? fmtCompact(v.value, '$') : kind === 'x' ? fmtMult(v.value, 2) : fmtNum(v.value)
        return <Metric key={`${g}.${k}`} label={k.replace(/_/g, ' ')} value={text} reason={v.reason} />
      })}
    </div>
  )
}

export function TechnicalsCard({ sec }: { sec: string }) {
  const q = useTechnicals(sec)
  const t = q.data
  const i = t?.indicators ?? {}
  const trend = t?.trend?.state ?? '—'
  return (
    <CardShell title="Technicals" sub={t?.last_session ? `as of session ${t.last_session} · split-adjusted` : undefined} q={q}>
      {t?.status !== 'OK' ? <div className="text-sm text-muted">{t?.warnings?.[0] ?? 'No price history.'}</div> : (
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          <Metric label="Trend" value={trend.replace('_', ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase())} context={`evidence score ${t.trend?.score}/${t.trend?.items_available}`} />
          <Metric label="RSI 14" value={fmtNum(i.rsi14, 1)} context="context only (no signal)" />
          <Metric label="vs SMA200" value={fmtPct(i.close_vs_sma200, 1, true)} tone={signClass(i.close_vs_sma200)} />
          <Metric label="vs SMA50" value={fmtPct(i.close_vs_sma50, 1, true)} tone={signClass(i.close_vs_sma50)} />
          <Metric label="ATR 14" value={fmtNum(i.atr14)} context={fmtPct(i.atr14_pct, 2)} />
          <Metric label="ADX 14" value={fmtNum(i.adx14, 1)} context="strength, not direction" />
          <Metric label="MACD hist" value={fmtNum(i.macd_hist)} />
          <Metric label="12M momentum" value={fmtPct(t.momentum?.mom_12m, 1, true)} tone={signClass(t.momentum?.mom_12m)} />
        </div>
      )}
    </CardShell>
  )
}

const OWN: [string, string, boolean][] = [['pe', 'P/E', false], ['price_to_sales', 'P/S', false], ['price_to_book', 'P/B', false], ['fcf_yield', 'FCF yield', true]]
export function ValuationCard({ sec }: { sec: string }) {
  const q = useValuation(sec)
  const v = q.data
  const c = v?.current ?? {}
  const own = v?.own_history ?? {}
  const pctx = (k: string) => (own[k]?.percentile != null ? `${own[k].percentile!.toFixed(0)}th pct of own ${own[k].window_years}y` : undefined)
  return (
    <CardShell title="Valuation" sub={v?.price_date ? `price ${fmtNum(v.price)} on ${v.price_date}` : undefined} q={q}>
      {v?.status !== 'OK' ? <div className="text-sm text-muted">{v?.warnings?.[0] ?? 'Valuation unavailable.'}</div> : (
        <>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            <Metric label="Market cap" value={fmtCompact(c.market_cap, '$')} />
            {OWN.map(([k, name, pct]) => (
              <Metric key={k} label={name} value={pct ? fmtPct(c[k], 2) : fmtMult(c[k])} context={pctx(k)} reason={c[k] == null ? 'denominator_invalid' : undefined} help={c[k] == null ? 'Not meaningful (non-positive earnings/equity)' : undefined} />
            ))}
            <Metric label="EV / Sales" value={fmtMult(c.ev_to_sales)} />
          </div>
          <p className="mt-3 text-[10px] text-muted">Context: own 5-year history. {v.peer_context?.reason ?? ''}</p>
        </>
      )}
    </CardShell>
  )
}

export function RiskCard({ sec }: { sec: string }) {
  const q = useTechnicals(sec)
  const a = useAnalysis(sec)
  const r = q.data?.risk ?? {}
  const lab = a.data?.labels.risk
  return (
    <CardShell title="Risk" sub={lab?.label ? `V0 label: ${lab.label}` : undefined} q={q}>
      {q.data?.status !== 'OK' ? <div className="text-sm text-muted">No price history.</div> : (
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          <Metric label="Volatility 63d" value={fmtPct(r.vol63)} context={`20d ${fmtPct(r.vol20)} · 252d ${fmtPct(r.vol252)}`} />
          <Metric label="Downside vol 63d" value={fmtPct(r.downside_vol63)} />
          <Metric label="Max drawdown 12M" value={fmtPct(r.max_drawdown252, 1)} tone="text-down" />
          <Metric label="Beta 252d" value={fmtNum(r.beta252)} context={String(q.data.relative_strength?.benchmark ?? '') ? `vs ${q.data.relative_strength?.benchmark} (ETF proxy)` : 'no benchmark'} reason={r.beta252 == null ? 'insufficient_history' : undefined} />
          <Metric label="ATR %" value={fmtPct(r.atr14_pct, 2)} />
          <Metric label="52w-high distance" value={fmtPct(q.data.momentum?.distance_52w_high, 1)} />
        </div>
      )}
    </CardShell>
  )
}

// ───────────────────────────── technical detail ──────────────────────────────────────────────────
export function TechnicalDetail({ sec }: { sec: string }) {
  const q = useTechnicals(sec)
  const t = q.data
  if (q.isPending) return <Skeleton className="h-48" />
  if (q.isError) return <PanelError what="Technical detail" error={q.error} onRetry={() => q.refetch()} />
  if (!t || t.status !== 'OK') return null
  const rs = t.relative_strength ?? {}
  const zrow = (z: Zone) => (
    <tr key={z.kind + z.midpoint} className="border-t border-border">
      <td className="py-1.5 pr-2">{z.kind === 'SUPPORT' ? 'Support' : 'Resistance'}</td>
      <td className="num pr-2">{fmtNum(z.lower)}–{fmtNum(z.upper)}</td>
      <td className="num pr-2">{z.touches}</td>
      <td className="num pr-2">{z.strength.toFixed(0)}</td>
      <td className={`num pr-2 ${signClass(z.distance_pct)}`}>{fmtPct(z.distance_pct, 1, true)}</td>
      <td className="num pr-2">{z.distance_atr.toFixed(1)} ATR</td>
      <td className="text-[10px] text-muted">{fmtDate(z.first_touch)} → {fmtDate(z.last_touch)}</td>
    </tr>
  )
  return (
    <Card>
      <CardHeader title="Technical detail" sub={`engine ${t.engine_version} · trend rules are deterministic, not a forecast`} />
      <CardBody className="grid gap-6 lg:grid-cols-3">
        <div>
          <h3 className="mb-2 text-[11px] uppercase tracking-[0.08em] text-muted">Trend evidence</h3>
          <ul className="space-y-1 text-xs">
            {t.trend?.evidence.map((e) => (
              <li key={e.code} className="flex items-center gap-2">
                <Badge tone={!e.available ? 'neutral' : e.positive ? 'up' : 'down'}>{!e.available ? 'n/a' : e.positive ? '+' : '−'}</Badge>
                {e.text}
                {e.metric !== undefined ? <span className="num text-muted">({fmtPct(e.metric, 1, true)})</span> : null}
              </li>
            ))}
          </ul>
          <h3 className="mb-2 mt-4 text-[11px] uppercase tracking-[0.08em] text-muted">Momentum (total return)</h3>
          <div className="grid grid-cols-3 gap-2">
            {(['ret21', 'ret63', 'ret126', 'ret252', 'mom_12_1', 'distance_52w_high'] as const).map((k) => (
              <Metric key={k} label={k.replace('ret', 'ret ').replace(/_/g, ' ')} value={fmtPct(t.momentum?.[k], 1, true)} tone={signClass(t.momentum?.[k])} />
            ))}
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-[11px] uppercase tracking-[0.08em] text-muted">Relative strength vs {String(rs.benchmark ?? 'benchmark')} <Badge>ETF proxy</Badge></h3>
          {rs.benchmark ? (
            <div className="grid grid-cols-4 gap-2">
              {(['21', '63', '126', '252'] as const).map((k) => <Metric key={k} label={`${k}d`} value={fmtPct(rs[k] as number | null, 1, true)} tone={signClass(rs[k] as number | null)} />)}
            </div>
          ) : <div className="text-xs text-muted">Benchmark prices unavailable.</div>}
          <h3 className="mb-2 mt-4 text-[11px] uppercase tracking-[0.08em] text-muted">Volume & stretch</h3>
          <div className="grid grid-cols-3 gap-2">
            <Metric label="Avg vol 20d" value={fmtCompact(t.volume?.avg20)} />
            <Metric label="Vol ratio 20" value={fmtMult(t.volume?.ratio20, 2)} />
            <Metric label="Vol z-score" value={fmtNum(t.volume?.zscore20)} />
            <Metric label="$ volume" value={fmtCompact(t.volume?.dollar_volume, '$')} />
            <Metric label="vs SMA20 (ATR)" value={fmtNum(t.overextension?.distance_from_sma20_atr)} />
            <Metric label="vs SMA50 (ATR)" value={fmtNum(t.overextension?.distance_from_sma50_atr)} />
          </div>
          <h3 className="mb-2 mt-4 text-[11px] uppercase tracking-[0.08em] text-muted">Indicators</h3>
          <div className="grid grid-cols-3 gap-2">
            {(['sma20', 'sma50', 'sma200', 'ema20', 'ema50', 'macd', 'macd_signal', 'bollinger_upper', 'bollinger_lower'] as const).map((k) => <Metric key={k} label={k.replace(/_/g, ' ')} value={fmtNum(t.indicators?.[k])} />)}
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-[11px] uppercase tracking-[0.08em] text-muted">Support / resistance zones (V1)</h3>
          {(t.support_resistance?.supports.length ?? 0) + (t.support_resistance?.resistances.length ?? 0) === 0 ? <div className="text-xs text-muted">No confirmed zones.</div> : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-left text-[10px] uppercase text-muted"><tr><th>Type</th><th>Zone</th><th>Touch</th><th>Str.</th><th>Dist.</th><th>ATR</th><th>Touches</th></tr></thead>
                <tbody>{[...(t.support_resistance?.resistances ?? []).slice().reverse(), ...(t.support_resistance?.supports ?? [])].map(zrow)}</tbody>
              </table>
            </div>
          )}
          {t.warnings.length ? <ul className="mt-3 list-disc pl-4 text-[11px] text-warn">{t.warnings.map((w) => <li key={w}>{w}</li>)}</ul> : null}
        </div>
      </CardBody>
    </Card>
  )
}

// ───────────────────────────── prediction ────────────────────────────────────────────────────────
export function PredictionPanel({ sec }: { sec: string }) {
  const q = usePrediction(sec)
  return (
    <Card>
      <CardHeader title="Prediction" right={<Badge tone="warn">Model status: not yet validated</Badge>} sub="No Champion model exists. No probabilities, expected returns or confidence are shown." />
      <CardBody>
        {q.isError ? <PanelError what="Prediction status" error={q.error} onRetry={() => q.refetch()} /> : null}
        <div className="grid gap-4 sm:grid-cols-2">
          {['6M', '12M'].map((h) => (
            <div key={h} className="rounded-md border border-dashed border-border p-3 opacity-80">
              <div className="mb-2 text-xs font-medium">{h} horizon</div>
              <div className="grid grid-cols-2 gap-3">
                <Metric label="Expected excess return" value="—" reason="NOT_YET_VALIDATED" />
                <Metric label="P(outperform)" value="—" reason="NOT_YET_VALIDATED" />
                <Metric label="P10 / P50 / P90" value="—" reason="NOT_YET_VALIDATED" />
                <Metric label="Confidence · calibration" value="—" reason="NOT_YET_VALIDATED" />
              </div>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-muted">{q.data?.message ?? 'The panel activates only when the Research Lab promotes a calibrated Champion (candidate → backtest → report → human review → explicit promotion).'}</p>
      </CardBody>
    </Card>
  )
}

// ───────────────────────────── filings ───────────────────────────────────────────────────────────
export function FilingsPanel({ sec }: { sec: string }) {
  const q = useFilings(sec)
  return (
    <Card>
      <CardHeader title="Latest filings" sub="SEC EDGAR · acceptance timestamps from filing headers" />
      <CardBody>
        {q.isPending ? <Skeleton className="h-24" /> : q.isError ? <PanelError what="Filings" error={q.error} onRetry={() => q.refetch()} /> : q.data?.filings.length ? (
          <table className="w-full text-xs">
            <thead className="text-left text-[10px] uppercase text-muted"><tr><th>Form</th><th>Filed</th><th>Accepted (UTC)</th><th>Period</th><th>Accession</th></tr></thead>
            <tbody>
              {q.data.filings.map((f) => (
                <tr key={f.accession} className="border-t border-border">
                  <td className="py-1.5"><Badge>{f.form}</Badge></td>
                  <td className="num">{fmtDate(f.filed_date)}</td>
                  <td className="num">{f.accepted_at.slice(0, 16).replace('T', ' ')}</td>
                  <td className="num">{fmtDate(f.report_period)}</td>
                  <td className="num">{f.link ? <a className="text-accent underline" href={f.link} target="_blank" rel="noreferrer">{f.accession}</a> : f.accession}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <div className="text-sm text-muted">No filings known for this security.</div>}
      </CardBody>
    </Card>
  )
}
