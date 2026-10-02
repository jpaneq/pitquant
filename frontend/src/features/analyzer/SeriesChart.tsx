import { ColorType, CrosshairMode, HistogramSeries, LineSeries, createChart, type Time } from 'lightweight-charts'
import { useEffect, useRef, useState } from 'react'
import type { HistoryPoint } from '../../api/types'
import { fmtCompact, fmtPct } from '../../lib/format'

export function SeriesChart({ title, points, kind, percent }: { title: string; points: HistoryPoint[]; kind: 'bar' | 'line'; percent?: boolean }) {
  const host = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<HistoryPoint | null>(null)
  useEffect(() => {
    if (!host.current || points.length === 0) return
    const cs = getComputedStyle(document.documentElement)
    const col = (v: string) => cs.getPropertyValue(v).trim()
    const c = createChart(host.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: col('--muted'), fontSize: 10 },
      grid: { vertLines: { visible: false }, horzLines: { color: col('--border') + '55' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: false },
      crosshair: { mode: CrosshairMode.Magnet },
      localization: { priceFormatter: (v: number) => (percent ? fmtPct(v, 0) : fmtCompact(v)) },
      handleScroll: false,
      handleScale: false,
    })
    const accent = col('--accent')
    const s = kind === 'bar' ? c.addSeries(HistogramSeries, { color: accent + 'cc', priceLineVisible: false, lastValueVisible: false }) : c.addSeries(LineSeries, { color: accent, lineWidth: 2, priceLineVisible: false, lastValueVisible: false })
    s.setData(points.map((p) => ({ time: p.date as Time, value: p.value })))
    const byDate = new Map(points.map((p) => [p.date, p]))
    c.subscribeCrosshairMove((p) => setHover(typeof p.time === 'string' ? (byDate.get(p.time) ?? null) : null))
    c.timeScale().fitContent()
    return () => c.remove()
  }, [points, kind])
  const shown = hover ?? points.at(-1)
  return (
    <div className="rounded-md border border-border bg-surface-2/40 p-2">
      <div className="mb-1 flex items-baseline justify-between text-[11px]">
        <span className="font-medium">{title}</span>
        {shown ? (
          <span className="num text-muted">
            {shown.date} · <span className="text-fg">{percent ? fmtPct(shown.value, 1) : fmtCompact(shown.value)}</span>
            {shown.yoy !== null && shown.yoy !== undefined ? <span className={shown.yoy >= 0 ? ' text-up' : ' text-down'}> {fmtPct(shown.yoy, 1, true)} YoY</span> : null}
          </span>
        ) : null}
      </div>
      {points.length ? <div ref={host} className="h-32 w-full" role="img" aria-label={`${title} history`} /> : <div className="flex h-32 items-center justify-center text-[11px] text-muted">No history</div>}
    </div>
  )
}
