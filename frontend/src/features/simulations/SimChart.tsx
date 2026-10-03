import { CandlestickSeries, ColorType, CrosshairMode, LineStyle, createChart, type Time } from 'lightweight-charts'
import { useEffect, useRef } from 'react'
import type { Bar } from './types'

export type Level = { label: string; price: number; kind: 'entry' | 'stop' | 'target' | 'invalidation' | 'sr' | 'fill' }
const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || '#888'

/** Candles since the decision with the plan levels. The levels are the ones frozen at T0 (never recomputed). */
export function SimChart({ bars, levels }: { bars: Bar[]; levels: Level[] }) {
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!host.current || bars.length === 0) return
    const up = css('--up'), down = css('--down'), grid = css('--border'), muted = css('--muted'), accent = css('--accent')
    const c = createChart(host.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: muted, fontFamily: 'Inter, system-ui, sans-serif', fontSize: 11 },
      grid: { vertLines: { color: grid + '55' }, horzLines: { color: grid + '55' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: grid },
      timeScale: { borderColor: grid, rightOffset: 3 },
    })
    const s = c.addSeries(CandlestickSeries, { upColor: up, downColor: down, wickUpColor: up, wickDownColor: down, borderVisible: false, priceFormat: { type: 'price', precision: 2, minMove: 0.01 } })
    s.setData(bars.map((b) => ({ time: b.date as Time, open: b.open, high: b.high, low: b.low, close: b.close })))
    const col = { entry: accent, fill: accent, stop: down, target: up, invalidation: down + 'aa', sr: muted }
    for (const l of levels) s.createPriceLine({ price: l.price, color: col[l.kind], lineWidth: l.kind === 'sr' ? 1 : 2, lineStyle: l.kind === 'sr' || l.kind === 'invalidation' ? LineStyle.Dashed : l.kind === 'target' ? LineStyle.Dotted : LineStyle.Solid, axisLabelVisible: true, title: l.label })
    c.timeScale().fitContent()
    return () => c.remove()
  }, [bars, levels])
  if (bars.length === 0) return <p className="text-xs text-muted" data-testid="sim-chart-empty">No completed bar after the decision yet: the chart starts when the first session closes. Levels below are the T0 plan.</p>
  return <div ref={host} data-testid="sim-chart" role="img" aria-label="Candles since the decision with the T0 plan levels" className="h-72 w-full" />
}
