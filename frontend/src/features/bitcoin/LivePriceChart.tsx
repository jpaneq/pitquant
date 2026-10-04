import { useEffect, useRef, useState } from 'react'
import { ColorType, LineSeries, createChart, type ISeriesApi, type IChartApi, type UTCTimestamp } from 'lightweight-charts'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

type Quote = { status: string; price: number; market_at: string; change_24h_percent: number }
type Point = { time: number; value: number }
export function LivePriceChart() {
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [range, setRange] = useState('1h')
  const intraday = ['1h', '6h', '16h'].includes(range)
  const { data: quote, isError: quoteFailed } = useQuery({ queryKey: ['btc-live-quote', symbol], queryFn: () => api<Quote>(`/btc/quote?symbol=${symbol}`), refetchInterval: 5000, staleTime: 4000, retry: false })
  const disconnected = quoteFailed || quote?.status !== 'LIVE'
  const host = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const series = useRef<ISeriesApi<'Line'> | null>(null)
  const samples = useRef<Point[]>([])
  const { data: history, isError } = useQuery({ queryKey: ['btc-live-history', symbol, intraday ? 'LIVE' : range], queryFn: () => api<{ points: Point[] }>(`/btc/quote/history?symbol=${symbol}&range=${intraday ? 'LIVE' : range}`), refetchInterval: 60000, retry: false })
  useEffect(() => {
    if (!host.current) return
    samples.current = []
    const css = getComputedStyle(document.documentElement)
    const chart = createChart(host.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: css.getPropertyValue('--muted').trim() },
      grid: { vertLines: { visible: false }, horzLines: { color: css.getPropertyValue('--border').trim() } },
      timeScale: { timeVisible: intraday, secondsVisible: intraday },
      localization: { priceFormatter: (v: number) => `${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${symbol === 'BTCEUR' ? 'EUR' : 'USDT'}` },
    })
    chartRef.current = chart
    series.current = chart.addSeries(LineSeries, { color: css.getPropertyValue('--accent').trim(), lineWidth: 2 })
    return () => { series.current = null; chartRef.current = null; chart.remove() }
  }, [symbol, intraday])
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
    const cutoff = (points.at(-1)?.time ?? Date.now() / 1000) - ({ '1h': 60, '6h': 360, '16h': 960 }[range] ?? Infinity) * 60
    series.current?.setData(points.filter(p => p.time >= cutoff).map(p => ({ ...p, time: p.time as UTCTimestamp })))
  }, [quote, history, range, disconnected, symbol, intraday])
  useEffect(() => { chartRef.current?.timeScale().fitContent() }, [history, range])
  return <figure className="rounded-lg border border-border bg-surface p-4" aria-label="BTC live chart">
    <figcaption className="mb-3 flex flex-wrap items-center justify-between gap-3"><div><label className="mr-3">Par <select aria-label="BTC chart pair" value={symbol} onChange={e => setSymbol(e.target.value)} className="rounded border border-border bg-surface px-2 py-1"><option value="BTCUSDT">BTC / USDT</option><option value="BTCEUR">BTC / EUR</option></select></label><strong>{quote?.status === 'LIVE' ? quote.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'} {symbol === 'BTCEUR' ? 'EUR' : 'USDT'}</strong></div><div className="flex flex-wrap gap-2">{['1h', '6h', '16h', '1M', '3M', '6M', '1Y', '3Y', 'MAX'].map(label => <button key={label} aria-pressed={range === label} className={`rounded border border-border px-3 py-1 text-xs ${range === label ? 'bg-accent/10 text-accent' : ''}`} onClick={() => setRange(label)}>{label}</button>)}</div></figcaption>
    <div ref={host} className="h-80 w-full" role="img" aria-label="BTC historical and live price" />
    <p className="mt-2 text-xs text-muted">{intraday ? 'Cierres de 1 minuto' : 'Histórico de cierres diarios del par seleccionado'} y precio actual cada 5 s · eje horario UTC · Binance Spot</p>
    {disconnected && <p role="status" className="text-xs text-warn">Sin conexión a la cotización: la gráfica conserva los últimos precios recibidos.</p>}
    {!history && !isError && <p role="status" className="text-xs text-muted">Cargando histórico…</p>}
    {history?.points?.length && !intraday ? <p className="text-xs text-muted">Desde {new Date(history.points[0].time * 1000).toISOString().slice(0, 10)} · {history.points.length} cierres · EUR utiliza cotizaciones BTCEUR, sin convertir precios históricos con el cambio actual.</p> : null}
    {isError && <p role="status" className="text-xs text-warn">Historial no disponible; se muestran las cotizaciones recibidas durante esta sesión.</p>}
  </figure>
}
