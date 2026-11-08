import { useState, type ReactNode } from 'react'

/** Small, dependency-free SVG charts for the learning page: one y-axis, thin marks, hover tooltip. */

export type Series = { key: string; label: string; color: string; dashed?: boolean; values: (number | null)[] }

const W = 640
const PAD = { l: 44, r: 12, t: 12, b: 26 }

function ticks(min: number, max: number, n = 4) {
  const step = (max - min) / n
  return Array.from({ length: n + 1 }, (_, i) => min + i * step)
}

export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
    {items.map(i => <span key={i.label} className="inline-flex items-center gap-1.5">
      <svg width="18" height="8" aria-hidden><line x1="1" x2="17" y1="4" y2="4" stroke={i.color} strokeWidth="2" strokeDasharray={i.dashed ? '4 3' : undefined} strokeLinecap="round" /></svg>
      {i.label}
    </span>)}
  </div>
}

/** Line chart over categorical x labels (months or dates). `format` renders y values. */
export function LineChart({ x, series, yMin, yMax, format, zero, height = 220, label }: {
  x: string[]; series: Series[]; yMin: number; yMax: number; format: (v: number) => string
  zero?: number; height?: number; label: string
}) {
  const [hover, setHover] = useState<number | null>(null)
  const H = height
  const iw = W - PAD.l - PAD.r
  const ih = H - PAD.t - PAD.b
  const sx = (i: number) => PAD.l + (x.length <= 1 ? iw / 2 : (i / (x.length - 1)) * iw)
  const sy = (v: number) => PAD.t + (1 - (v - yMin) / (yMax - yMin)) * ih
  const path = (values: (number | null)[]) => values.reduce((d, v, i) => {
    if (v == null) return d
    const prev = i > 0 ? values[i - 1] : null
    return `${d}${prev == null ? 'M' : 'L'}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`
  }, '')
  const every = Math.max(1, Math.ceil(x.length / 8))
  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    const box = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - box.left) / box.width) * iw
    setHover(Math.max(0, Math.min(x.length - 1, Math.round((px / iw) * (x.length - 1)))))
  }
  return <figure className="relative" aria-label={label}>
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={label}>
      {ticks(yMin, yMax).map(t => <g key={t}>
        <line x1={PAD.l} x2={W - PAD.r} y1={sy(t)} y2={sy(t)} stroke="var(--border)" strokeWidth="1" />
        <text x={PAD.l - 6} y={sy(t) + 3} textAnchor="end" className="num" fontSize="10" fill="var(--muted)">{format(t)}</text>
      </g>)}
      {zero != null && <line x1={PAD.l} x2={W - PAD.r} y1={sy(zero)} y2={sy(zero)} stroke="var(--muted)" strokeWidth="1" />}
      {x.map((l, i) => i % every === 0 || i === x.length - 1 ? <text key={l} x={sx(i)} y={H - 8} textAnchor={i === x.length - 1 && x.length > 1 ? 'end' : i === 0 && x.length > 1 ? 'start' : 'middle'} fontSize="10" fill="var(--muted)">{l}</text> : null)}
      {series.map(s => <path key={s.key} d={path(s.values)} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" strokeDasharray={s.dashed ? '5 4' : undefined} />)}
      {x.length === 1 && series.map(s => s.values[0] != null && <circle key={s.key} cx={sx(0)} cy={sy(s.values[0])} r="4" fill={s.color} />)}
      {hover != null && <>
        <line x1={sx(hover)} x2={sx(hover)} y1={PAD.t} y2={PAD.t + ih} stroke="var(--muted)" strokeDasharray="2 3" />
        {series.map(s => s.values[hover] != null && <circle key={s.key} cx={sx(hover)} cy={sy(s.values[hover] as number)} r="4" fill={s.color} stroke="var(--surface)" strokeWidth="2" />)}
      </>}
      <rect x={PAD.l} y={PAD.t} width={iw} height={ih} fill="transparent" onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
    </svg>
    {hover != null && <div className="pointer-events-none absolute top-1 rounded-md border border-border bg-surface px-2.5 py-1.5 text-[11px] shadow-lg" style={{ left: `${Math.min(70, (sx(hover) / W) * 100)}%` }}>
      <b className="block">{x[hover]}</b>
      {series.map(s => <span key={s.key} className="num flex items-center gap-1.5"><span className="inline-block h-2 w-2 rounded-full" style={{ background: s.color }} />{s.label}: {s.values[hover] == null ? '—' : format(s.values[hover] as number)}</span>)}
    </div>}
  </figure>
}

/** "When it says X %, it goes up Y %": dots against the perfect-calibration diagonal. */
export function CalibrationChart({ points, color, label }: { points: { p_mean: number; up_rate: number; n: number }[]; color: string; label: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const H = 240, lo = 0.3, hi = 0.9
  const S = H - PAD.t - PAD.b
  const sx = (v: number) => PAD.l + ((v - lo) / (hi - lo)) * S
  const sy = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * S
  const clamp = (v: number) => Math.max(lo, Math.min(hi, v))
  const maxN = Math.max(...points.map(p => p.n), 1)
  const t = [0.3, 0.45, 0.6, 0.75, 0.9]
  return <figure className="relative" aria-label={label}>
    <svg viewBox={`0 0 ${S + PAD.l + PAD.r} ${H}`} className="mx-auto w-full max-w-sm" role="img" aria-label={label}>
      {t.map(v => <g key={v}>
        <line x1={PAD.l} x2={sx(hi)} y1={sy(v)} y2={sy(v)} stroke="var(--border)" />
        <text x={PAD.l - 6} y={sy(v) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">{Math.round(v * 100)}%</text>
        <text x={sx(v)} y={H - 8} textAnchor="middle" fontSize="10" fill="var(--muted)">{Math.round(v * 100)}%</text>
      </g>)}
      <line x1={sx(lo)} y1={sy(lo)} x2={sx(hi)} y2={sy(hi)} stroke="var(--muted)" strokeDasharray="5 4" />
      <text x={sx(0.86)} y={sy(0.86) - 8} textAnchor="end" fontSize="10" fill="var(--muted)">perfecto</text>
      {points.map((p, i) => <circle key={i} cx={sx(clamp(p.p_mean))} cy={sy(clamp(p.up_rate))} r={4 + 6 * Math.sqrt(p.n / maxN)} fill={color} fillOpacity={0.85} stroke="var(--surface)" strokeWidth="2" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />)}
    </svg>
    {hover != null && <div className="pointer-events-none absolute left-2 top-1 rounded-md border border-border bg-surface px-2.5 py-1.5 text-[11px] shadow-lg">
      Dijo <b className="num">{(points[hover].p_mean * 100).toFixed(0)}%</b> → subió el <b className="num">{(points[hover].up_rate * 100).toFixed(0)}%</b><br />
      <span className="num text-muted">{points[hover].n.toLocaleString()} pronósticos</span>
    </div>}
  </figure>
}

/** Horizontal bars for a handful of comparable percentages (hit rates). */
export function CompareBars({ rows, min = 0.4, max = 0.7 }: { rows: { label: ReactNode; value: number; color: string; note?: string }[]; min?: number; max?: number }) {
  const w = (v: number) => `${Math.max(2, ((v - min) / (max - min)) * 100)}%`
  return <div className="space-y-2.5">{rows.map((r, i) => <div key={i} className="grid grid-cols-[9rem_1fr_3.5rem] items-center gap-3 text-xs" title={r.note}>
    <span className="truncate text-muted">{r.label}</span>
    <span className="h-3 rounded-r bg-surface-2"><span className="block h-3 rounded-r" style={{ width: w(r.value), background: r.color }} /></span>
    <span className="num text-right font-medium">{(r.value * 100).toFixed(1)}%</span>
  </div>)}
    <p className="num pl-[9.75rem] text-[10px] text-muted">La escala empieza en {Math.round(min * 100)}% para que se vean las diferencias.</p>
  </div>
}
