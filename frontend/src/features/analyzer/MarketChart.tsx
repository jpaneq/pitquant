import { CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, LineSeries, LineStyle, createChart, type IChartApi, type ISeriesApi, type MouseEventParams, type Time } from 'lightweight-charts'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useChart, useTechnicals, useTradePlan } from '../../api/hooks'
import { Badge, Button, Card, PanelError, Segmented, Skeleton } from '../../components/ui/primitives'
import { fmtCompact, fmtNum, fmtPct, signClass } from '../../lib/format'

const RANGES = ['1M', '3M', '6M', 'YTD', '1Y', '3Y', '5Y', 'MAX'] as const
type Range = (typeof RANGES)[number]
const OVERLAYS = [
  ['sma20', 'SMA20', '#e0a64a'],
  ['sma50', 'SMA50', '#6c93f0'],
  ['sma200', 'SMA200', '#c586e8'],
  ['ema20', 'EMA20', '#3ecf9a'],
  ['ema50', 'EMA50', '#7fd1e8'],
] as const

const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || '#888'

type Legend = { date: string; o?: number; h?: number; l?: number; c?: number; chg?: number; chgPct?: number; v?: number; vals: [string, number][] }

export function MarketChart({ sec }: { sec: string }) {
  const [range, setRange] = useState<Range>('1Y')
  const [on, setOn] = useState<Record<string, boolean>>({ sma50: true, sma200: true, sr: true, plan: false, rsi: false, macd: false, boll: false })
  const [profile, setProfile] = useState('BASE')
  const chart = useChart(sec, range)
  const tech = useTechnicals(sec)
  const plan = useTradePlan(sec)
  const host = useRef<HTMLDivElement>(null)
  const [legend, setLegend] = useState<Legend | null>(null)
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    const el = document.documentElement
    const obs = new MutationObserver(() => setDark(el.classList.contains('dark')))
    obs.observe(el, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  const data = chart.data
  const zones = tech.data?.support_resistance
  const planData = plan.data
  const setups = useMemo(() => planData?.setups ?? [], [planData])
  const shownSetup = useMemo(() => setups.find((s) => s.profile === profile) ?? setups[0], [setups, profile])
  const toggle = (k: string) => setOn((s) => ({ ...s, [k]: !s[k] }))

  useEffect(() => {
    if (!host.current || !data || data.candles.length === 0) return
    const up = css('--up'), down = css('--down'), grid = css('--border'), muted = css('--muted')
    const c: IChartApi = createChart(host.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: muted, fontFamily: 'Inter, system-ui, sans-serif', fontSize: 11, panes: { separatorColor: grid } },
      grid: { vertLines: { color: grid + '55' }, horzLines: { color: grid + '55' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: grid },
      timeScale: { borderColor: grid, rightOffset: 4 },
    })
    const candles = c.addSeries(CandlestickSeries, { upColor: up, downColor: down, wickUpColor: up, wickDownColor: down, borderVisible: false, priceFormat: { type: 'price', precision: 2, minMove: 0.01 } }, 0)
    candles.setData(data.candles.map((k) => ({ time: k.time as Time, open: k.open, high: k.high, low: k.low, close: k.close })))
    const vol = c.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false }, 1)
    vol.setData(data.candles.map((k, i, a) => ({ time: k.time as Time, value: k.volume, color: (i > 0 && k.close >= a[i - 1].close ? up : down) + '88' })))
    const named: Record<string, ISeriesApi<'Line'>> = {}
    const ov = data.overlays ?? {}
    for (const [key, label, color] of OVERLAYS) {
      if (!on[key] || !ov[key]?.length) continue
      const s = c.addSeries(LineSeries, { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: label }, 0)
      s.setData(ov[key].map((p) => ({ time: p.time as Time, value: p.value })))
      named[label] = s
    }
    if (on.boll) {
      for (const k of ['bollinger_upper', 'bollinger_mid', 'bollinger_lower']) {
        const s = c.addSeries(LineSeries, { color: '#8b95a7', lineWidth: 1, lineStyle: k === 'bollinger_mid' ? LineStyle.Dotted : LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }, 0)
        s.setData((ov[k] ?? []).map((p) => ({ time: p.time as Time, value: p.value })))
      }
    }
    let pane = 2
    const panes = data.panes ?? {}
    if (on.rsi && panes.rsi14?.length) {
      const r = c.addSeries(LineSeries, { color: '#e0a64a', lineWidth: 1, priceLineVisible: false, title: 'RSI14' }, pane)
      r.setData(panes.rsi14.map((p) => ({ time: p.time as Time, value: p.value })))
      r.createPriceLine({ price: 70, color: grid, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: false, title: '70' })
      r.createPriceLine({ price: 30, color: grid, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: false, title: '30' })
      pane++
    }
    if (on.macd && panes.macd?.length) {
      const h = c.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, pane)
      h.setData((panes.macd_hist ?? []).map((p) => ({ time: p.time as Time, value: p.value, color: (p.value >= 0 ? up : down) + 'aa' })))
      c.addSeries(LineSeries, { color: '#6c93f0', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: 'MACD' }, pane).setData(panes.macd.map((p) => ({ time: p.time as Time, value: p.value })))
      c.addSeries(LineSeries, { color: '#e0a64a', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: 'Signal' }, pane).setData((panes.macd_signal ?? []).map((p) => ({ time: p.time as Time, value: p.value })))
      pane++
    }
    try {
      const ps = c.panes()
      ps[0]?.setStretchFactor(5)
      ps[1]?.setStretchFactor(1.2)
      for (let i = 2; i < ps.length; i++) ps[i]?.setStretchFactor(1.6)
    } catch {
      /* pane API not available: default heights */
    }
    if (on.sr && zones) {
      for (const z of [...zones.supports, ...zones.resistances]) {
        const col = z.kind === 'SUPPORT' ? up : down
        for (const [p, t] of [[z.lower, ''], [z.upper, `${z.kind === 'SUPPORT' ? 'S' : 'R'} ${fmtNum(z.midpoint)}`]] as const)
          candles.createPriceLine({ price: p, color: col + '99', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: t !== '', title: t })
      }
    }
    if (on.plan && shownSetup) {
      candles.createPriceLine({ price: shownSetup.entry, color: css('--accent'), lineWidth: 2, lineStyle: LineStyle.Solid, title: `Entry ${shownSetup.profile}` })
      candles.createPriceLine({ price: shownSetup.stop, color: down, lineWidth: 2, lineStyle: LineStyle.Solid, title: 'Stop' })
      for (const t of shownSetup.r_targets) candles.createPriceLine({ price: t.price, color: up, lineWidth: 1, lineStyle: LineStyle.Dotted, title: `${t.r_multiple}R` })
    }
    const prev = new Map<string, number>()
    data.candles.forEach((k, i, a) => i > 0 && prev.set(k.time, a[i - 1].close))
    const onMove = (p: MouseEventParams<Time>) => {
      const t = typeof p.time === 'string' ? p.time : undefined
      const k = t ? data.candles.find((x) => x.time === t) : undefined
      if (!t || !k) return setLegend(null)
      const pc = prev.get(t)
      const vals: [string, number][] = []
      for (const [label, s] of Object.entries(named)) {
        const d = p.seriesData.get(s) as { value?: number } | undefined
        if (d?.value !== undefined) vals.push([label, d.value])
      }
      setLegend({ date: t, o: k.open, h: k.high, l: k.low, c: k.close, chg: pc ? k.close - pc : undefined, chgPct: pc ? k.close / pc - 1 : undefined, v: k.volume, vals })
    }
    c.subscribeCrosshairMove(onMove)
    c.timeScale().fitContent()
    return () => {
      c.unsubscribeCrosshairMove(onMove)
      c.remove()
    }
  }, [data, on, zones, shownSetup, dark])

  const last = data?.candles.at(-1)
  const first = data?.candles[0]
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
        <Segmented label="Chart range" value={range} options={RANGES} onChange={setRange} />
        <div className="ml-1 flex flex-wrap items-center gap-1" role="group" aria-label="Chart overlays">
          {OVERLAYS.map(([k, l, col]) => (
            <ToggleChip key={k} on={!!on[k]} onClick={() => toggle(k)} color={col}>
              {l}
            </ToggleChip>
          ))}
          <ToggleChip on={!!on.boll} onClick={() => toggle('boll')}>Bollinger 20,2</ToggleChip>
          <ToggleChip on={!!on.sr} onClick={() => toggle('sr')}>Support/Resistance</ToggleChip>
          <ToggleChip on={!!on.plan} onClick={() => toggle('plan')} disabled={!setups.length}>Trade Plan</ToggleChip>
          <ToggleChip on={!!on.rsi} onClick={() => toggle('rsi')}>RSI</ToggleChip>
          <ToggleChip on={!!on.macd} onClick={() => toggle('macd')}>MACD</ToggleChip>
          <ToggleChip on={false} onClick={() => undefined} disabled title="Prediction overlay requires a validated Champion model (none yet)">Prediction</ToggleChip>
        </div>
        {on.plan && setups.length ? (
          <Segmented label="Trade plan profile" value={profile} options={['AGGRESSIVE', 'BASE', 'CONSERVATIVE'] as const} onChange={setProfile} />
        ) : null}
        <span className="ml-auto text-[10px] text-muted">{data?.price_basis === 'SPLIT_ADJUSTED_NOT_DIVIDEND_ADJUSTED' ? 'Split-adjusted · no dividend adjustment' : ''}</span>
      </div>
      <div className="relative">
        {legend ? (
          <div className="num pointer-events-none absolute left-3 top-2 z-10 rounded border border-border bg-surface/90 px-2 py-1 text-[11px]">
            <span className="text-muted">{legend.date}</span> O {fmtNum(legend.o)} H {fmtNum(legend.h)} L {fmtNum(legend.l)} C {fmtNum(legend.c)}{' '}
            <span className={signClass(legend.chg)}>
              {legend.chg !== undefined ? `${legend.chg >= 0 ? '+' : ''}${fmtNum(legend.chg)} (${fmtPct(legend.chgPct, 2, true)})` : ''}
            </span>{' '}
            <span className="text-muted">Vol {fmtCompact(legend.v)}</span>
            {legend.vals.map(([l, v]) => (
              <span key={l} className="ml-2 text-muted">
                {l} {fmtNum(v)}
              </span>
            ))}
          </div>
        ) : null}
        {chart.isPending ? <Skeleton className="m-3 h-[420px]" /> : null}
        {chart.isError ? <div className="p-3"><PanelError what="Price chart" error={chart.error} onRetry={() => chart.refetch()} /></div> : null}
        {data && data.candles.length === 0 ? <div className="p-6 text-sm text-muted">No price bars known for this security{data.status === 'NO_DATA' ? ' (no market-data source ingested)' : ''}.</div> : null}
        <div ref={host} role="img" aria-label={last && first ? `Price chart, ${data?.range}: last close ${fmtNum(last.close)}, ${fmtPct(last.close / first.close - 1, 1, true)} over the range` : 'Price chart'} className={data?.candles.length ? 'h-[460px] w-full' : 'h-0'} />
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-border px-3 py-1.5 text-[10px] text-muted">
        <span>{data?.n_bars ?? 0} bars</span>
        {(data?.sources ?? []).map((s) => (
          <Badge key={s}>{s}</Badge>
        ))}
        <Button className="ml-auto px-2 py-0.5 text-[10px]" onClick={() => chart.refetch()}>Refresh</Button>
      </div>
    </Card>
  )
}

function ToggleChip({ on, onClick, children, color, disabled, title }: { on: boolean; onClick: () => void; children: React.ReactNode; color?: string; disabled?: boolean; title?: string }) {
  return (
    <button aria-pressed={on} disabled={disabled} title={title} onClick={onClick} className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium disabled:opacity-40 ${on ? 'border-accent/50 bg-accent/10 text-fg' : 'border-border text-muted hover:text-fg'}`}>
      {color ? <i aria-hidden className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: color }} /> : null}
      {children}
    </button>
  )
}
