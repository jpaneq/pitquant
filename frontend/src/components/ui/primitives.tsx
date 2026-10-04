import clsx from 'clsx'
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'
import { useEffect, useId, useRef, useState } from 'react'
import { reasonText } from '../../lib/format'
import { lookup, type Term } from '../../lib/glossary'

export function Card({ className, ...p }: HTMLAttributes<HTMLElement>) {
  return <section className={clsx('rounded-lg border border-border bg-surface', className)} {...p} />
}
/** Botón «i» con explicación en castellano: qué es, cuándo suele ser positivo y cuándo negativo. Se cierra con Esc o al pulsar fuera. */
export function InfoTip({ term, label }: { term?: Term; label?: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  const id = useId()
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onDown)
    }
  }, [open])
  const t = term ?? lookup(label)
  if (!t) return null
  return (
    <span ref={ref} className="relative inline-block align-middle">
      <button type="button" aria-label={`Qué es ${t.t}`} aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)} className="ml-1 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-border text-[9px] font-semibold italic leading-none text-muted hover:border-accent hover:text-accent">
        i
      </button>
      {open ? (
        <span id={id} role="dialog" aria-label={t.t} className="absolute left-0 top-5 z-30 w-64 rounded-md border border-border bg-surface p-3 text-left text-[11px] font-normal normal-case leading-snug tracking-normal text-fg shadow-lg">
          <b className="block text-xs">{t.t}</b>
          <span className="mt-1 block">{t.q}</span>
          {t.p ? <span className="mt-1.5 block text-up"><b>Positivo:</b> {t.p}</span> : null}
          {t.n ? <span className="mt-1 block text-down"><b>Negativo:</b> {t.n}</span> : null}
          {t.c ? <span className="mt-1 block text-muted"><b>Ojo:</b> {t.c}</span> : null}
        </span>
      ) : null}
    </span>
  )
}

export function CardHeader({ title, right, sub }: { title: ReactNode; right?: ReactNode; sub?: ReactNode }) {
  return (
    <header className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
      <div>
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">{title}{typeof title === 'string' ? <InfoTip label={title} /> : null}</h2>
        {sub ? <div className="mt-0.5 text-xs text-muted">{sub}</div> : null}
      </div>
      {right}
    </header>
  )
}
export const CardBody = ({ className, ...p }: HTMLAttributes<HTMLDivElement>) => <div className={clsx('p-4', className)} {...p} />

type Tone = 'neutral' | 'up' | 'down' | 'warn' | 'info' | 'accent'
const TONES: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-muted border-border',
  up: 'bg-up/10 text-up border-up/30',
  down: 'bg-down/10 text-down border-down/30',
  warn: 'bg-warn/10 text-warn border-warn/30',
  info: 'bg-info/10 text-info border-info/30',
  accent: 'bg-accent/10 text-accent border-accent/30',
}
export function Badge({ tone = 'neutral', className, ...p }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return <span className={clsx('inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide', TONES[tone], className)} {...p} />
}

export function Button({ className, variant = 'ghost', ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'ghost' | 'solid' }) {
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
        variant === 'solid' ? 'border-accent bg-accent text-bg hover:opacity-90' : 'border-border bg-surface-2 text-fg hover:border-accent/60',
        className,
      )}
      {...p}
    />
  )
}

export const Skeleton = ({ className }: { className?: string }) => <div aria-hidden className={clsx('animate-pulse rounded bg-surface-2', className)} />

export function Metric({ label, value, context, help, reason, tone, big }: { label: string; value: ReactNode; context?: ReactNode; help?: string; reason?: string; tone?: string; big?: boolean }) {
  const unavailable = value === '—'
  return (
    <div title={help} className="min-w-0">
      <div className="text-[11px] text-muted">{label}<InfoTip label={label} /></div>
      <div className={clsx('num font-medium', big ? 'text-xl' : 'text-sm', tone, unavailable && 'text-muted')}>{value}</div>
      {unavailable && reason !== undefined ? <div className="text-[10px] text-muted">{reasonText(reason)}</div> : context ? <div className="num text-[11px] text-muted">{context}</div> : null}
    </div>
  )
}

export function PanelError({ error, onRetry, what }: { error: unknown; onRetry?: () => void; what: string }) {
  const msg = (error as { message?: string })?.message ?? 'unavailable'
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-md border border-warn/30 bg-warn/5 px-3 py-2 text-xs text-warn">
      <span>
        {what} unavailable — {msg}
      </span>
      {onRetry ? (
        <Button onClick={onRetry} className="px-2 py-1 text-[11px]">
          Retry
        </Button>
      ) : null}
    </div>
  )
}

export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: readonly T[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="inline-flex overflow-hidden rounded-md border border-border">
      {options.map((o) => (
        <button key={o} aria-pressed={o === value} onClick={() => onChange(o)} className={clsx('px-2.5 py-1 text-[11px] font-medium', o === value ? 'bg-accent/15 text-accent' : 'bg-surface text-muted hover:text-fg')}>
          {o}
        </button>
      ))}
    </div>
  )
}
