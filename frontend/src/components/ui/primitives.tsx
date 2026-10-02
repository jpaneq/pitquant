import clsx from 'clsx'
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'
import { reasonText } from '../../lib/format'

export function Card({ className, ...p }: HTMLAttributes<HTMLElement>) {
  return <section className={clsx('rounded-lg border border-border bg-surface', className)} {...p} />
}
export function CardHeader({ title, right, sub }: { title: ReactNode; right?: ReactNode; sub?: ReactNode }) {
  return (
    <header className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
      <div>
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">{title}</h2>
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
      <div className="text-[11px] text-muted">{label}</div>
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
