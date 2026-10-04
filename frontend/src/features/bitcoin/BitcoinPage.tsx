import { useState } from 'react'
import { LivePriceChart } from './LivePriceChart'
import { NavLink, useLocation } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiPost } from '../../api/client'
import { LiveHeader, MarketChart, MarketContext, ModelBar, useLiveMarket } from './LiveMarket'
import { BtcLivePlan } from './BtcLivePlan'
import { PositionsPanel } from '../positions/PositionsPanel'
import { PredictionFollowUp } from './PredictionFollowUp'
import { ForecastTracking, RetrospectiveEvidence, type Tracking } from './ForecastTracking'

type Prediction = { prediction_id: string; horizon: number; prediction_hash: string; payload: { status: string; expected_return: number | null; p_up: number | null; q10: number | null; q50: number | null; q90: number | null; model_version: string | null; data_quality: string; target_price?: number; generated_at?: string; target_at?: string; reference_price?: number } }
type Snapshot = { snapshot_id: string; decision_at: string; snapshot_hash: string; feature_version: string; commit_sha: string; payload: Features; predictions: Prediction[]; trade_plan: Record<string, unknown> }
type Features = { availability: Record<string, string>; missing_reasons: Record<string, string>; provenance: { metric: string; source: string; raw_hash: string; available_at: string; exchange_timestamp: string }[]; spot_ready: boolean; last_spot_close: string | null; [key: string]: unknown }
type Source = { status: string; earliest: string | null; latest: string | null; count: number; reason: string | null }
type Status = { data: { sources: Record<string, Source> } | null; readiness: { status: string; blockers: string[]; earliest_usable: string | null }; strategies: Record<string, string> }
type Sim = { simulation_id: string; simulation_engine_version: string; position_size_simulated: number }
type Detail = { prediction_tracking: Tracking; simulation: Sim; replay: { match: boolean }; outcomes: { state: string; realized_return: number | null; excess_return_vs_benchmark: number | null; realized_r: number | null; max_drawdown: number | null; details: Record<string, unknown> }[]; postmortems: unknown[] }
const TABS = ['Analyzer', 'Prediction Lab', 'Strategy Lab', 'Simulations', 'Research']
const paths = ['', 'predictions', 'strategies', 'simulations', 'research']
const display = (value: unknown) => value == null ? '—' : typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 6 }) : String(value)
function featureProvenance(features: Features, family: string, name: string) {
  let metrics = ['spot']
  if (family === 'network_features') metrics = [name]
  if (family === 'derivatives_features') {
    metrics = name.startsWith('funding') ? ['funding_rate']
      : name.includes('_oi_') ? ['spot', 'open_interest']
      : name === 'open_interest' || name.startsWith('oi_') ? ['open_interest']
      : ['basis', 'annualized_basis', 'perp_premium'].includes(name) ? ['basis'] : [name]
  }
  return metrics.map(metric => features.provenance.filter(p => p.metric === metric).at(-1))
    .filter(p => p != null)
    .map(p => `${p.source} · ${p.exchange_timestamp} · available ${p.available_at} · SHA256 ${p.raw_hash}`).join('; ')
}


export function BitcoinPage() {
  const location = useLocation()
  const active = Math.max(0, paths.indexOf(location.pathname.split('/')[2] ?? ''))
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [cohort, setCohort] = useState('FORWARD_PAPER')
  const [frozen, setFrozen] = useState<Snapshot | null>(null)
  const [outcome, setOutcome] = useState<Record<string, unknown> | null>(null)
  const [sim, setSim] = useState<Sim | null>(null)
  const [detail, setDetail] = useState<Detail | null>(null)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [hypothesis, setHypothesis] = useState('')
  const [testStart, setTestStart] = useState('2020-01-01')
  const [testEnd, setTestEnd] = useState('2024-01-01')
  const [horizon, setHorizon] = useState(30)
  const [tradeHorizon, setTradeHorizon] = useState(30)
  const [notional, setNotional] = useState(1000)
  const [revealHorizon, setRevealHorizon] = useState(7)
  const [cause, setCause] = useState('NO_CLEAR_ERROR')
  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)
  const client = useQueryClient()
  const cutoff = `${date}T00:00:00+00:00`
  const { data: market, isError: marketFailed } = useLiveMarket()
  const [useLiveRef, setUseLiveRef] = useState(false)
  const { data: status } = useQuery({ queryKey: ['btc-status', cohort], queryFn: () => api<Status>(`/btc/status?cohort=${cohort}`) })
  const { data: features } = useQuery({ queryKey: ['btc-analysis', date, cohort], queryFn: () => api<Features>(`/btc/analyzer?decision_at=${encodeURIComponent(cutoff)}&cohort=${cohort}`) })
  const { data: snapshots } = useQuery({ queryKey: ['btc-snapshots', cohort], queryFn: () => api<Snapshot[]>(`/btc/snapshots?cohort=${cohort}`) })
  const { data: simulations } = useQuery({ queryKey: ['btc-simulations', cohort], queryFn: () => api<Sim[]>(`/btc/simulations?cohort=${cohort}`) })
  const { data: liveDetail } = useQuery({ queryKey: ['btc-detail', sim?.simulation_id], queryFn: () => api<Detail>(`/btc/simulations/${sim?.simulation_id}`), enabled: !!sim && cohort === 'FORWARD_PAPER', refetchInterval: 30000 })
  const shownDetail = cohort === 'FORWARD_PAPER' ? liveDetail ?? detail : detail
  const { data: research } = useQuery({ queryKey: ['btc-research', cohort], queryFn: () => api<{ records: { kind: string; payload: Record<string, unknown> }[] }>(`/btc/research?cohort=${cohort}`) })
  const current = frozen ?? snapshots?.find(s => s.decision_at.startsWith(date) && s.feature_version === 'btc-price-experimental-v1') ?? snapshots?.find(s => s.decision_at.startsWith(date)) ?? null
  const currentFeatures = current?.payload ?? features
  const maturesAt = current ? new Date(new Date(current.decision_at).getTime() + revealHorizon * 86400000) : null
  const immature = cohort === 'FORWARD_PAPER' && maturesAt != null && Date.now() < maturesAt.getTime()
  const run = async (work: () => Promise<void>) => { setBusy(true); setError(''); try { await work(); await client.invalidateQueries({ queryKey: ['btc-snapshots'] }); await client.invalidateQueries({ queryKey: ['btc-simulations'] }); await client.invalidateQueries({ queryKey: ['btc-research'] }) } catch (e) { setError(String(e)) } finally { setBusy(false) } }
  const freeze = () => run(async () => { setFrozen(await apiPost<Snapshot>(cohort === 'FORWARD_PAPER' && date === new Date().toISOString().slice(0, 10) ? '/btc/experimental/forecast' : '/btc/freeze', { decision_at: cutoff, cohort })); setOutcome(null) })
  const reveal = () => run(async () => { if (current) setOutcome(await apiPost(`/btc/predictions/${current.predictions.find(p => p.horizon === revealHorizon)?.prediction_id}/reveal`, { as_of: cohort === 'SYNTHETIC' ? new Date(new Date(cutoff).getTime() + revealHorizon * 86400000).toISOString() : new Date().toISOString() })) })
  const simulate = () => run(async () => { if (current) { const created = await apiPost<Sim>('/btc/simulations', { snapshot_id: current.snapshot_id, notional, horizon_days: tradeHorizon, use_live_reference: useLiveRef }); setSim(created); setDetail(await api<Detail>(`/btc/simulations/${created.simulation_id}`)) } })
  const update = () => run(async () => { if (sim) { await apiPost(`/btc/simulations/${sim.simulation_id}/update`, { as_of: '2026-11-15T00:00:00+00:00' }); setDetail(await api<Detail>(`/btc/simulations/${sim.simulation_id}`)) } })
  return <section className="space-y-5" aria-label="Bitcoin workspace">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold">Bitcoin {TABS[active]}</h1><p className="text-sm text-muted">BTCUSDT · 24/7 · Daily close 00:00 UTC</p></div><span className="rounded border border-warn/40 px-3 py-2 text-xs text-warn">PAPER TRADE — NO REAL MONEY</span></div>
    <LiveHeader data={market} failed={marketFailed} />
    {cohort === 'FORWARD_PAPER' && <LivePriceChart />}
    <ModelBar bar={market?.last_closed_daily_bar} />
    <MarketChart forming={market?.forming_daily_bar} />
    <MarketContext data={market} />
    {<><div className="grid gap-3 md:grid-cols-5">{(current?.predictions ?? [7,30,90,180,365].map<Prediction>(horizon => ({ horizon, prediction_id: '', prediction_hash: '', payload: { status: 'NOT_YET_VALIDATED', expected_return: null, p_up: null, q10: null, q50: null, q90: null, model_version: null, data_quality: 'BLOCKED_BY_DATA' } }))).map(p => <div className="rounded-lg border border-border bg-surface p-4" key={p.horizon}><h2 className="text-lg font-semibold">{p.horizon}D</h2><p className="my-2 text-[10px] text-warn">{p.payload.status}</p><dl className="space-y-1 text-xs"><div>Retorno pronosticado {p.payload.expected_return == null ? '—' : `${(p.payload.expected_return * 100).toFixed(2)}%`}</div><div>P(up) sin calibrar {p.payload.p_up == null ? '—' : `${(p.payload.p_up * 100).toFixed(1)}%`}</div><div>P10 / P50 / P90 {display(p.payload.q10)} / {display(p.payload.q50)} / {display(p.payload.q90)}</div><div>Objetivo {display(p.payload.target_price)} USDT</div><div>Base {display(p.payload.reference_price)} USDT</div><div>Model {display(p.payload.model_version)}</div><div>Generada {p.payload.generated_at ? new Date(p.payload.generated_at).toLocaleString() : '—'}</div><div>Evaluar {p.payload.target_at ? new Date(p.payload.target_at).toLocaleString() : '—'}</div><div>Data {p.payload.data_quality}</div></dl></div>)}</div></>}
    <p className="text-xs text-warn">Pronósticos experimentales, sin calibración validada. Conservan el modelo, la fecha de generación y el cierre diario de referencia.</p>
    <nav aria-label="Bitcoin" className="flex flex-wrap gap-2">{TABS.map((tab, i) => <NavLink key={tab} to={`/bitcoin${paths[i] ? `/${paths[i]}` : ''}`} end className={({ isActive }) => `rounded-md border px-3 py-2 text-sm ${isActive ? 'border-accent text-accent' : 'border-border text-muted'}`}>{tab}</NavLink>)}</nav>
    <div className="flex flex-wrap gap-4 rounded-lg border border-border bg-surface p-4">
      <label className="text-xs">Evidence set<select aria-label="Evidence set" className="ml-2 rounded border border-border bg-surface-2 p-2" value={cohort} onChange={e => { setCohort(e.target.value); setFrozen(null); setOutcome(null); setSim(null); setDetail(null) }}>{['FORWARD_PAPER', 'HISTORICAL_OOS', 'SYNTHETIC'].map(s => <option key={s}>{s}</option>)}</select></label>
      <label className="text-xs">BTC as of<input aria-label="BTC as of" type="date" className="ml-2 rounded border border-border bg-surface-2 p-2" value={date} onChange={e => { setDate(e.target.value); setFrozen(null); setOutcome(null) }} /></label>
      <button disabled={busy} onClick={freeze} className="rounded bg-accent px-3 py-2 text-xs text-white">{cohort === 'FORWARD_PAPER' ? 'Generar pronóstico experimental' : 'Freeze prediction'}</button>
      <label className="text-xs">Reveal horizon<select aria-label="Reveal horizon" value={revealHorizon} onChange={e => setRevealHorizon(Number(e.target.value))} className="ml-2 rounded border border-border bg-surface-2 p-2">{[7,30,90,180,365].map(h => <option key={h} value={h}>{h}D</option>)}</select></label>
      <button disabled={!current || busy || immature} onClick={reveal} className="rounded border border-border px-3 py-2 text-xs disabled:opacity-40">Reveal Outcome</button>
      {immature && <span role="status" className="text-xs text-warn">Madura el {maturesAt?.toISOString().slice(0, 16).replace('T', ' ')} UTC; se comprobará automáticamente.</span>}
    </div>
    {cohort === 'SYNTHETIC' && <p role="status" className="text-sm text-warn">SYNTHETIC BTC FIXTURE — these prices and outcomes are not real market evidence.</p>}
    {error && <p role="alert" className="rounded border border-bad/30 p-3 text-sm text-bad">{error}</p>}
    <div className="rounded-lg border border-border bg-surface p-4"><h2 className="text-sm font-semibold">Data availability</h2><div className="mt-3 grid gap-3 md:grid-cols-4">{Object.entries(status?.data?.sources ?? {}).filter(([name]) => !name.includes('probe')).map(([name, source]) => <div key={name} className="text-xs"><b>{name}</b><p>{source.status} · {source.count} observations</p><p className="text-muted">FROM {source.earliest ?? 'unavailable'}</p><p className="text-muted">{source.reason}</p></div>)}</div><p className="mt-3 text-xs text-muted">Historical test: {status?.readiness.status ?? 'Loading'} · {status?.readiness.blockers.join(', ')}. Archived market history does not prove historical PIT availability.</p></div>

    {currentFeatures && <PriceChart points={(currentFeatures.price_history ?? []) as { time: string; close: number }[]} />}
    {(active === 0 || active === 2) && <><BtcLivePlan /><PositionsPanel asset="BTC" /></>}
    {active === 0 && currentFeatures && <div className="grid gap-4 lg:grid-cols-2">{['price_features','trend_features','momentum_features','volatility_features','volume_features','derivatives_features','network_features','regime'].map(family => <div key={family} className="rounded-lg border border-border bg-surface p-4"><h2 className="mb-3 text-sm font-semibold uppercase">{family.replaceAll('_features','').replaceAll('_',' / ')}</h2>{Object.entries((currentFeatures[family] ?? {}) as Record<string, unknown>).map(([name, value]) => <div key={name} className="flex justify-between gap-3 border-b border-border/50 py-1.5 text-xs"><span>{name}</span><span className="num">{display(value)}</span><details><summary className="cursor-pointer text-accent">Why / Provenance</summary><div className="max-w-60 break-all text-muted">{currentFeatures.availability[name]} {currentFeatures.missing_reasons[name]}<p>{featureProvenance(currentFeatures, family, name)}</p></div></details></div>)}</div>)}</div>}
    {current && (active === 0 || active === 2) && <div className="rounded-lg border border-border bg-surface p-4"><h2 className="font-semibold">BTC Trade Plan</h2><p className="my-2 text-xs text-warn">RULE_BASED · NOT_YET_BACKTEST_VALIDATED · Predicción vinculada para evaluación; plan basado en ATR</p><dl className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">{['entry_zone_low','stop_loss','target_1','target_2'].map(k => <div key={k}><dt className="text-xs text-muted">{k.replaceAll('_', ' ')}</dt><dd>{display(current.trade_plan[k])}</dd></div>)}</dl><details className="mt-3 text-xs"><summary>Plan rules and audit details</summary><pre className="overflow-auto">{JSON.stringify(current.trade_plan, null, 2)}</pre></details><label className="mr-3 text-xs">Importe USDT<input aria-label="Trade notional" type="number" min="1" value={notional} onChange={e => setNotional(Number(e.target.value))} className="ml-2 rounded border border-border bg-surface-2 p-2" /></label><label className="mr-3 text-xs">Pronóstico a evaluar<select aria-label="Trade horizon" value={tradeHorizon} onChange={e => setTradeHorizon(Number(e.target.value))} className="ml-2 rounded border border-border bg-surface-2 p-2">{[7,30,90,180,365].map(h => <option key={h} value={h}>{h}D</option>)}</select></label><label className="mr-3 text-xs"><input type="checkbox" aria-label="Use current quote as T0 reference" checked={useLiveRef} onChange={e => setUseLiveRef(e.target.checked)} /> Guardar cotización actual como referencia T0</label><button disabled={busy || notional <= 0 || current.trade_plan.status === 'BLOCKED_BY_DATA'} onClick={simulate} className="mt-3 rounded bg-accent px-4 py-2 text-xs text-white disabled:opacity-40">Simulate BTC trade</button></div>}
    {active === 2 && <div className="grid gap-4 md:grid-cols-4">{Object.entries(status?.strategies ?? {}).map(([strategy, state]) => <div key={strategy} className="rounded-lg border border-border p-4 text-xs"><b>{strategy}</b><p className="mt-2">{state}</p></div>)}<p className="text-xs text-muted">Benchmark BTC BUY_AND_HOLD · CASH = 0 · COSTS_NOT_MODELED when costs are zero.</p></div>}
    {(sim || active === 3) && <div className="rounded-lg border border-border bg-surface p-4"><h2 className="font-semibold">BTC Simulations</h2>{(sim ? [sim, ...(simulations ?? []).filter(s => s.simulation_id !== sim.simulation_id)] : simulations ?? []).map(s => <button key={s.simulation_id} className="my-2 block text-xs text-accent" onClick={() => run(async () => { setSim(s); setDetail(await api<Detail>(`/btc/simulations/${s.simulation_id}`)) })}>{s.simulation_id} · {s.simulation_engine_version} · {display(s.position_size_simulated)} BTC</button>)}{sim && <><button disabled={busy || cohort !== 'SYNTHETIC'} onClick={update} className="rounded border border-border px-3 py-2 text-xs">Advance synthetic BTC bars</button><p className="mt-2 text-xs">La operación queda registrada ahora. La ejecución paper empieza en la siguiente sesión UTC; los resultados usan velas diarias cerradas. El precio live no confirma por sí solo un TP.</p></>}{shownDetail && <><ForecastTracking tracking={shownDetail.prediction_tracking} /><div className="my-3 grid gap-3 md:grid-cols-4">{shownDetail.outcomes.slice(-1).map(o => <div key={o.state} className="col-span-full"><p className="font-semibold">{o.state}</p><dl className="mt-2 grid gap-3 md:grid-cols-4">{[['Return',o.realized_return],['Excess vs BTC buy-and-hold',o.excess_return_vs_benchmark],['R',o.realized_r],['Maximum drawdown',o.max_drawdown]].map(([label,value]) => <div key={String(label)}><dt className="text-xs text-muted">{label}</dt><dd>{display(value)}</dd></div>)}</dl></div>)}</div><details className="my-3 text-xs"><summary>Outcome and event audit</summary><pre className="overflow-auto">{JSON.stringify(shownDetail.outcomes, null, 2)}</pre></details><label className="text-xs">Primary cause<select aria-label="Primary cause" value={cause} onChange={e => setCause(e.target.value)}>{['NO_CLEAR_ERROR','FUNDING_EXTREME','OI_EXPANSION','OI_FLUSH','BASIS_COMPRESSION','LIQUIDATION_EVENT','VOLATILITY_EXPANSION','NETWORK_CHANGE','REGIME_CHANGE'].map(c => <option key={c}>{c}</option>)}</select></label><label className="text-xs">Post-mortem notes<input value={note} onChange={e => setNote(e.target.value)} className="ml-2 border border-border p-2" /></label><button className="ml-2 rounded border border-border p-2 text-xs" disabled={busy} onClick={() => run(async () => { await apiPost(`/btc/simulations/${shownDetail.simulation.simulation_id}/postmortem`, { primary_cause: cause, classified_by: 'user', notes: note }); setDetail(await api(`/btc/simulations/${shownDetail.simulation.simulation_id}`)) })}>Save explicit post-mortem</button><p className="mt-2 text-xs">Post-mortems: {shownDetail.postmortems.length} · Replay matches: {String(shownDetail.replay.match)}</p></>}</div>}
    {outcome && <div className="rounded-lg border border-border bg-surface p-4"><h2 className="font-semibold">Prediction vs Reality</h2><dl className="my-3 grid gap-3 md:grid-cols-3">{['predicted','actual','error'].map(k => <div key={k}><dt className="text-xs text-muted">{k}</dt><dd>{display((outcome.payload as Record<string, unknown>)?.[k])}</dd></div>)}</dl><details className="my-3 text-xs"><summary>Frozen prediction and outcome audit</summary><pre className="overflow-auto">{JSON.stringify(outcome, null, 2)}</pre></details><p className="text-xs">Original feature hash: {current?.snapshot_hash}. El error se calcula cuando hay un pronóstico numérico registrado y un resultado maduro.</p></div>}
    {(active === 1 || active === 4) && <PredictionFollowUp cohort={cohort} />}
    {active === 4 && <RetrospectiveEvidence horizon={horizon} />}
    {active === 4 && <div className="rounded-lg border border-border p-4"><h2 className="font-semibold">Historical Time Machine / Blind Replay</h2><p className="my-2 text-sm text-muted">Choose an evidence set and historical date. Freeze first, then reveal. Historical OOS, forward paper and synthetic evidence remain separate.</p><p className="text-xs">Feature {current?.feature_version ?? 'btc-core-v0'} · Model NOT_YET_VALIDATED · Strategy btc-plan-v0 · Elastic Net / Logistic Regression · Purged walk-forward</p><p className="my-3 text-xs">Calibration and ablation require OOS model predictions. Champion promotion remains manual.</p><div className="my-4 flex flex-wrap gap-3 text-xs"><label>Test start<input aria-label="Test start" type="date" value={testStart} onChange={e => setTestStart(e.target.value)} className="ml-2 border border-border p-1" /></label><label>Test end<input aria-label="Test end" type="date" value={testEnd} onChange={e => setTestEnd(e.target.value)} className="ml-2 border border-border p-1" /></label><label>Horizon<select aria-label="Test horizon" value={horizon} onChange={e => setHorizon(Number(e.target.value))}>{[7,30,90,180,365].map(h => <option key={h} value={h}>{h}D</option>)}</select></label><button disabled={busy || cohort !== 'HISTORICAL_OOS'} className="rounded border border-border p-2" onClick={() => run(async () => setTestResult(await apiPost('/btc/historical-tests', { start: `${testStart}T00:00:00+00:00`, end: `${testEnd}T00:00:00+00:00`, horizon, feature_version: 'btc-core-v0', model_version: 'btc-core-baseline-v0', strategy_version: 'btc-plan-v0' })))}>Run historical test</button></div>{testResult && <pre className="overflow-auto text-xs">{JSON.stringify(testResult, null, 2)}</pre>}<label className="text-xs">Research hypothesis<input aria-label="Research hypothesis" value={hypothesis} onChange={e => setHypothesis(e.target.value)} className="mx-2 border border-border p-2" /></label><button disabled={busy || !hypothesis.trim()} className="rounded border border-border p-2 text-xs" onClick={() => run(async () => { await apiPost('/btc/hypotheses', { statement: hypothesis, created_by: 'user', evidence: { cohort, snapshot_hash: current?.snapshot_hash ?? null } }); setHypothesis('') })}>Save hypothesis</button><details><summary>Research records</summary><pre className="overflow-auto text-xs">{JSON.stringify(research?.records, null, 2)}</pre></details></div>}
  </section>
}

function PriceChart({ points }: { points: { time: string; close: number }[] }) {
  if (!points.length) return <p className="text-xs text-muted">PRICE_DATA_REQUIRED — no price history known at this cutoff.</p>
  const minimum = Math.min(...points.map(p => p.close)), maximum = Math.max(...points.map(p => p.close))
  const line = points.map((p, i) => `${20 + i / Math.max(points.length - 1, 1) * 760},${150 - (p.close - minimum) / Math.max(maximum - minimum, 1) * 120}`).join(' ')
  return <figure className="rounded-lg border border-border bg-surface p-4"><figcaption className="mb-2 text-xs">BTC known price history · {points[0].time.slice(0, 10)} → {points.at(-1)?.time.slice(0, 10)}</figcaption><svg role="img" aria-label="BTC price at the selected cutoff" viewBox="0 0 800 175" className="w-full"><polyline fill="none" stroke="currentColor" strokeWidth="2" points={line} className="text-accent" /></svg></figure>
}
