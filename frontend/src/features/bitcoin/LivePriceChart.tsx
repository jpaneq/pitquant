import { useEffect, useRef, useState } from 'react'
import { ColorType, LineSeries, createChart, type ISeriesApi, type IChartApi, type UTCTimestamp } from 'lightweight-charts'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

type Quote = { status: string; price: number; market_at: string }
type Point = { time: number; value: number }
export function LivePriceChart() {
  const { data: quote, isError: quoteFailed } = useQuery({ queryKey: ['btc-live-quote'], queryFn: () => api<Quote>('/btc/quote'), refetchInterval: 5000, staleTime: 4000, retry: false })
  const disconnected = quoteFailed || quote?.status !== 'LIVE'
  const host = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const series = useRef<ISeriesApi<'Line'> | null>(null)
  const samples = useRef<Point[]>([])
  const [range, setRange] = useState(60)
  const { data: history, isError } = useQuery({ queryKey: ['btc-live-history'], queryFn: () => api<{ points: Point[] }>('/btc/quote/history'), refetchInterval: 60000, retry: false })
  useEffect(() => {
    if (!host.current) return
    const css = getComputedStyle(document.documentElement)
    const chart = createChart(host.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: css.getPropertyValue('--muted').trim() },
      grid: { vertLines: { visible: false }, horzLines: { color: css.getPropertyValue('--border').trim() } },
      timeScale: { timeVisible: true, secondsVisible: true },
      localization: { priceFormatter: (v: number) => `${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT` },
    })
    chartRef.current = chart
    series.current = chart.addSeries(LineSeries, { color: css.getPropertyValue('--accent').trim(), lineWidth: 2 })
    return () => { series.current = null; chartRef.current = null; chart.remove() }
  }, [])
  useEffect(() => {
    if (quote?.status === 'LIVE' && !disconnected) {
      const point = { time: Math.floor(Date.parse(quote.market_at) / 1000), value: quote.price }
      const last = samples.current.at(-1)
      if (!last || point.time > last.time) samples.current.push(point)
      else if (point.time === last.time) samples.current[samples.current.length - 1] = point
      samples.current = samples.current.slice(-12000)
    }
    const merged = new Map((history?.points ?? []).map(p => [p.time, p]))
    for (const point of samples.current) merged.set(point.time, point)
    const points = [...merged.values()].sort((a, b) => a.time - b.time)
    const cutoff = (points.at(-1)?.time ?? Date.now() / 1000) - range * 60
    series.current?.setData(points.filter(p => p.time >= cutoff).map(p => ({ ...p, time: p.time as UTCTimestamp })))
  }, [quote, history, range, disconnected])
  useEffect(() => { chartRef.current?.timeScale().fitContent() }, [history, range])
  return <figure className="rounded-lg border border-border bg-surface p-4" aria-label="BTC live chart">
    <figcaption className="mb-3 flex flex-wrap items-center justify-between gap-3"><strong>BTC / USDT · gráfica en vivo</strong><div className="flex gap-2">{[[60, '1h'], [360, '6h'], [960, '16h']].map(([minutes, label]) => <button key={minutes} aria-pressed={range === minutes} className={`rounded border border-border px-3 py-1 text-xs ${range === minutes ? 'bg-accent/10 text-accent' : ''}`} onClick={() => setRange(Number(minutes))}>{label}</button>)}</div></figcaption>
    <div ref={host} className="h-80 w-full" role="img" aria-label="BTC intraday live price" />
    <p className="mt-2 text-xs text-muted">Cierres de 1 minuto y precio actual cada 5 s · eje horario UTC · Binance Spot</p>
    {disconnected && <p role="status" className="text-xs text-warn">Sin conexión a la cotización: la gráfica conserva los últimos precios recibidos.</p>}
    {isError && <p role="status" className="text-xs text-warn">Historial intradía no disponible; se muestran las cotizaciones recibidas durante esta sesión.</p>}
  </figure>
}
