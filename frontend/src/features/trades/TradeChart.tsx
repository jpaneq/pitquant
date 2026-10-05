import { CandlestickSeries, ColorType, CrosshairMode, LineSeries, LineStyle, createChart, createSeriesMarkers, type SeriesMarker, type Time } from 'lightweight-charts'
import { useEffect, useRef } from 'react'

export type TradeBar = { date: string; open: number; high: number; low: number; close: number }
export type TradeLine = { date: string; value: number }
export type TradeLevel = { label: string; price: number; kind: 'entry' | 'target' | 'stop' | 'invalidation' }
export type TradeMarker = { date: string; price: number; kind: 'entry' | 'skip' | 'exit'; label: string }
export type TradePayload = {
  ref: string; title: string; kind: string; asset: string
  decision: { action: string; recommendation: string | null; score: number | null; reason: string; decided_at: string | null }
  bars: TradeBar[]; sma50: TradeLine[]; sma200: TradeLine[]; levels: TradeLevel[]; markers: TradeMarker[]
  decision_date: string; horizon_end: string
  outcome: { state: string; closed: boolean; return_pct: number | null; exit_date: string | null }
  explanation: string[]; disclaimer: string
}
const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || '#888'
const lastOnOrBefore = (bars: TradeBar[], d: string) => { let r = bars[0]?.date; for (const b of bars) { if (b.date <= d) r = b.date; else break } return r }

/** Candles + SMA50/SMA200 (trend) + the planned entry / target / stop lines + markers for the decision, the entry and the exit. */
export function TradeChart({ t }: { t: TradePayload }) {
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!host.current || t.bars.length === 0) return
    const up = css('--up'), down = css('--down'), grid = css('--border'), muted = css('--muted'), accent = css('--accent')
    const c = createChart(host.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: muted, fontFamily: 'Inter, system-ui, sans-serif', fontSize: 11 },
      grid: { vertLines: { color: grid + '55' }, horzLines: { color: grid + '55' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: grid },
      timeScale: { borderColor: grid, rightOffset: 6 },
    })
    const s = c.addSeries(CandlestickSeries, { upColor: up, downColor: down, wickUpColor: up, wickDownColor: down, borderVisible: false })
    s.setData(t.bars.map((b) => ({ time: b.date as Time, open: b.open, high: b.high, low: b.low, close: b.close })))
    const sma = (data: TradeLine[], color: string, title: string) => {
      if (!data.length) return
      const l = c.addSeries(LineSeries, { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title })
      l.setData(data.map((p) => ({ time: p.date as Time, value: p.value })))
    }
    sma(t.sma50, '#e0a030', 'SMA50')
    sma(t.sma200, '#6a8cff', 'SMA200')
    const col = { entry: accent, target: up, stop: down, invalidation: down + 'aa' }
    for (const l of t.levels) s.createPriceLine({ price: l.price, color: col[l.kind], lineWidth: 2, lineStyle: l.kind === 'target' ? LineStyle.Dotted : l.kind === 'invalidation' ? LineStyle.Dashed : LineStyle.Solid, axisLabelVisible: true, title: l.label })
    const markers: SeriesMarker<Time>[] = t.markers.map((m) => ({
      time: lastOnOrBefore(t.bars, m.date) as Time,
      position: m.kind === 'exit' ? 'aboveBar' : 'belowBar',
      shape: m.kind === 'entry' ? 'arrowUp' : m.kind === 'exit' ? 'arrowDown' : 'circle',
      color: m.kind === 'exit' ? down : m.kind === 'entry' ? up : muted,
      text: m.label,
    }))
    createSeriesMarkers(s, markers.sort((a, b) => String(a.time).localeCompare(String(b.time))))
    c.timeScale().fitContent()
    return () => c.remove()
  }, [t])
  if (t.bars.length === 0) return <p className="text-xs text-muted">Sin velas disponibles para este activo.</p>
  return <div ref={host} data-testid="trade-chart" role="img" aria-label="Velas, tendencia y plan de la operación" className="h-[26rem] w-full" />
}
