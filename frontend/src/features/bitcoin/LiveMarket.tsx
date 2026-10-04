import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export type Bar = { open_time: string; close_time: string; open: number; high: number; low: number; close: number; volume: number; number_of_trades?: number | null; status?: string; gap_before?: boolean }
export type Series = { metric: string; status: string; value: number | null; as_of: string | null; available_at: string | null; first_knowledge_at: string | null; retrieved_at: string | null; source: string; reason?: string }
export type LiveMarketData = {
  data_mode?: string; warning?: string; reason?: string; retrieved_at: string | null
  quote?: { price: number | null; retrieved_at: string | null; status: string; source: string; timestamp_kind: string; note?: string }
  rolling_24h?: { change: number; change_pct: number; high: number; low: number; volume_btc: number; volume_usdt: number } | null
  last_closed_daily_bar?: Bar | null; forming_daily_bar?: Bar | null
  funding?: Series; open_interest?: Series; basis?: Series; network?: Series[]
}
const usd = (v: number | null | undefined) => v == null ? '—' : v.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const num = (v: number | null | undefined, d = 2) => v == null ? '—' : v.toLocaleString('en-US', { maximumFractionDigits: d })
const utc = (iso: string | null | undefined) => iso ? `${iso.slice(0, 16).replace('T', ' ')} UTC` : '—'
const BADGE: Record<string, string> = { LIVE: 'border-good text-good', RECENT: 'border-warn text-warn', STALE: 'border-bad text-bad', UNAVAILABLE: 'border-bad text-bad' }

/** Polls every 5 s while the page is visible; react-query pauses in a hidden tab and refetches on return. Display only: nothing here is a model input. */
export function useLiveMarket() {
  return useQuery({ queryKey: ['btc-market-live'], queryFn: () => api<LiveMarketData>('/btc/market/live'), refetchInterval: 5000, refetchIntervalInBackground: false, refetchOnWindowFocus: true, staleTime: 4000, retry: false })
}

export function LiveHeader({ data, failed }: { data?: LiveMarketData; failed: boolean }) {
  const q = data?.quote
  const status = failed ? 'UNAVAILABLE' : q?.status ?? 'UNAVAILABLE'
  const h = data?.rolling_24h
  return <div aria-label="BTC live market" className="rounded-lg border border-border bg-surface p-4">
    {data?.data_mode === 'SYNTHETIC_TEST_DATA' && <p role="status" className="mb-2 text-xs font-semibold text-warn">SYNTHETIC TEST DATA — not market prices</p>}
    <div className="flex flex-wrap items-baseline gap-3"><h2 className="text-lg font-semibold">Bitcoin</h2><span className="text-sm text-muted">BTC / USDT</span><span aria-label="Quote freshness" className={`rounded border px-2 py-0.5 text-xs font-semibold ${BADGE[status] ?? ''}`}>{status}</span></div>
    {status === 'UNAVAILABLE' || q?.price == null
      ? <p role="status" className="mt-2 text-2xl font-semibold text-bad">REAL DATA UNAVAILABLE</p>
      : <strong aria-label="BTC price" className="num mt-1 block text-4xl">{usd(q.price)}</strong>}
    {data?.reason && <p className="mt-1 text-xs text-warn">{data.reason}</p>}
    {h && <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm"><div><dt className="inline text-muted">24h </dt><dd className={`inline ${h.change_pct >= 0 ? 'text-good' : 'text-bad'}`}>{h.change_pct > 0 ? '+' : ''}{h.change_pct.toFixed(2)}%</dd></div><div><dt className="inline text-muted">High </dt><dd className="inline num">{usd(h.high)}</dd></div><div><dt className="inline text-muted">Low </dt><dd className="inline num">{usd(h.low)}</dd></div><div><dt className="inline text-muted">24h Volume </dt><dd className="inline num">{num(h.volume_btc)} BTC · {usd(h.volume_usdt)}</dd></div></dl>}
    <p className="mt-2 text-xs text-muted">Source: {q?.source === 'BINANCE_SPOT' ? 'Binance Spot' : q?.source === 'BINANCE_SPOT_ARCHIVE' ? 'Binance Spot (archived daily close)' : 'Binance Spot'} · 24H ROLLING · Last updated {q?.retrieved_at ? new Date(q.retrieved_at).toLocaleTimeString() : '—'} <span className="text-muted">(retrieved_at; no trade timestamp provided)</span></p>
  </div>
}

export function ModelBar({ bar }: { bar?: Bar | null }) {
  return <div aria-label="Model bar" className="rounded-lg border border-border bg-surface p-4">
    <h2 className="text-xs font-semibold uppercase text-muted">MODEL BAR — 1D UTC</h2>
    {bar ? <dl className="mt-2 grid grid-cols-2 gap-2 text-sm md:grid-cols-6"><div><dt className="text-xs text-muted">Close</dt><dd className="num">{usd(bar.close)}</dd></div><div><dt className="text-xs text-muted">Open</dt><dd className="num">{usd(bar.open)}</dd></div><div><dt className="text-xs text-muted">High</dt><dd className="num">{usd(bar.high)}</dd></div><div><dt className="text-xs text-muted">Low</dt><dd className="num">{usd(bar.low)}</dd></div><div><dt className="text-xs text-muted">Volume</dt><dd className="num">{num(bar.volume)} BTC</dd></div><div><dt className="text-xs text-muted">Trades</dt><dd className="num">{num(bar.number_of_trades, 0)}</dd></div><div className="col-span-full"><dt className="inline text-xs text-muted">Bar closed: </dt><dd className="inline">{utc(bar.close_time)}</dd><span className="text-xs text-muted"> · opened {utc(bar.open_time)}</span></div></dl>
      : <p className="mt-2 text-sm text-warn">No closed daily bar available.</p>}
    <p className="mt-2 text-xs text-muted">Predictions use closed daily bars, not the live quote.</p>
  </div>
}

const STALE_LABEL = (s: Series) => s.status === 'STALE' ? 'STALE' : s.status === 'UNAVAILABLE' ? 'UNAVAILABLE' : 'OK'
export function MarketContext({ data }: { data?: LiveMarketData }) {
  const deriv = [['Funding', data?.funding], ['Open Interest', data?.open_interest], ['Basis', data?.basis]] as const
  return <div aria-label="Derivatives and network" className="grid gap-4 lg:grid-cols-2">
    <div className="rounded-lg border border-border bg-surface p-4"><h2 className="mb-2 text-sm font-semibold">Derivatives (archived real values)</h2>{deriv.map(([name, s]) => s && <div key={name} className="border-b border-border/50 py-2 text-xs"><b>{name}</b> <span className={s.status === 'AVAILABLE' ? '' : 'text-bad'}>{STALE_LABEL(s)}</span><p>value {s.value == null ? '—' : num(s.value, 8)} · as_of {utc(s.as_of)}</p><p className="text-muted">first_knowledge_at {utc(s.first_knowledge_at)} · {s.source}</p></div>)}</div>
    <div className="rounded-lg border border-border bg-surface p-4"><h2 className="mb-2 text-sm font-semibold">Network (Coin Metrics)</h2>{(data?.network ?? []).map(s => <div key={s.metric} className="border-b border-border/50 py-1.5 text-xs"><b>{s.metric}</b> <span className={s.status === 'AVAILABLE' ? '' : 'text-bad'}>{STALE_LABEL(s)}</span> {s.status === 'UNAVAILABLE' ? <span className="text-muted">{s.reason}</span> : <span>{num(s.value, 4)} · as_of {utc(s.as_of)} · available {utc(s.available_at ?? s.retrieved_at)} · {s.source}</span>}</div>)}</div>
  </div>
}

const RANGES = ['1M', '3M', '6M', '1Y', '3Y', 'MAX']
export function MarketChart({ forming }: { forming?: Bar | null }) {
  const [range, setRange] = useState('1Y')
  const { data } = useQuery({ queryKey: ['btc-market-bars', range], queryFn: () => api<{ bars: Bar[] }>(`/btc/market/bars?range=${range}`), staleTime: 60000, retry: false })
  const bars = data?.bars ?? []
  const closes = [...bars.map(b => b.close), ...(forming ? [forming.close] : [])]
  const lo = Math.min(...closes), hi = Math.max(...closes)
  const n = closes.length
  const pt = (i: number, v: number) => `${20 + i / Math.max(n - 1, 1) * 760},${150 - (v - lo) / Math.max(hi - lo, 1e-9) * 120}`
  let path = ''
  bars.forEach((b, i) => { path += `${i === 0 || b.gap_before ? 'M' : 'L'}${pt(i, b.close)} ` })
  return <figure aria-label="BTC daily chart" className="rounded-lg border border-border bg-surface p-4">
    <figcaption className="mb-2 flex flex-wrap items-center gap-2 text-xs"><span>BTC/USDT · 1D closed UTC bars (Binance Spot archive)</span>{RANGES.map(r => <button key={r} aria-pressed={r === range} onClick={() => setRange(r)} className={`rounded border px-2 py-0.5 ${r === range ? 'border-accent text-accent' : 'border-border text-muted'}`}>{r}</button>)}</figcaption>
    {bars.length === 0 ? <p className="text-xs text-warn">No archived real daily bars in this range.</p>
      : <svg role="img" aria-label="BTC closed daily bars" viewBox="0 0 800 175" className="w-full"><path d={path} fill="none" stroke="currentColor" strokeWidth="2" className="text-accent" />{forming && <circle cx={pt(n - 1, forming.close).split(',')[0]} cy={pt(n - 1, forming.close).split(',')[1]} r="4" className="fill-warn"><title>INCOMPLETE daily candle (display only)</title></circle>}</svg>}
    {forming && <p className="mt-1 text-xs text-warn">Current daily candle INCOMPLETE — display only, not a model input.</p>}
    <p className="mt-1 text-xs text-muted">Missing days appear as gaps; nothing is interpolated.</p>
  </figure>
}
