import { useQuote } from '../../api/hooks'
import type { Summary } from '../../api/types'
import { Badge } from '../../components/ui/primitives'
import { fmtCompact, fmtMoney, fmtNum, fmtPct, fmtTime, signClass } from '../../lib/format'

const BADGE: Record<string, { tone: 'up' | 'info' | 'warn' | 'down' | 'neutral'; text: string }> = {
  REALTIME_REFERENCE: { tone: 'up', text: 'Realtime ref.' },
  DELAYED: { tone: 'info', text: 'Delayed' },
  EOD: { tone: 'info', text: 'End of day' },
  STALE: { tone: 'warn', text: 'Stale' },
  NO_DATA: { tone: 'down', text: 'No price data' },
}

export function SecurityHeader({ summary, sec, onDataQuality }: { summary: Summary; sec: string; onDataQuality: () => void }) {
  const s = summary.security
  const open = summary.quote.market_status === 'OPEN'
  const live = useQuote(sec, open)
  const q = live.data ?? summary.quote
  const b = BADGE[q.badge] ?? BADGE.NO_DATA
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{s.name}</h1>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
          <span className="num font-semibold text-fg">{s.ticker ?? '—'}</span>
          <span>· {s.exchange ?? '—'}</span>
          <span>· {s.industry ?? s.sector ?? s.asset_class}</span>
          {s.sector_source ? <span title={s.sector_source}>· SEC SIC classification</span> : null}
          <Badge tone="neutral">{s.profile_type.replace('_', ' ')}</Badge>
          <Badge tone={summary.availability.analyzer_eligibility === 'FULL' ? 'up' : summary.availability.analyzer_eligibility === 'INSUFFICIENT' ? 'down' : 'warn'}>{String(summary.availability.analyzer_eligibility).replace('_', ' ')}</Badge>
        </div>
      </div>
      {q.status === 'OK' ? (
        <div className="text-right">
          <div className="num text-3xl font-semibold leading-none">{fmtMoney(q.price, q.currency)}</div>
          <div className={`num mt-1 text-sm ${signClass(q.change)}`}>
            {q.change !== null && q.change !== undefined ? `${q.change >= 0 ? '+' : ''}${fmtNum(q.change)}` : '—'} ({fmtPct(q.change_pct, 2, true)})
          </div>
          <div className="num mt-1 flex flex-wrap items-center justify-end gap-x-3 gap-y-1 text-[11px] text-muted">
            <span>Prev close {fmtNum(q.previous_close)}</span>
            <span>Mkt cap {fmtCompact(q.market_cap, '$')}</span>
            <span>Market {q.market_status ?? '—'}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center justify-end gap-1.5 text-[10px] text-muted">
            <Badge tone={b.tone}>{b.text}</Badge>
            <button onClick={onDataQuality} className="underline decoration-dotted" title="Open data quality">
              {q.source ?? 'source n/a'} · session {q.session} · {fmtTime(q.timestamp)} · {q.currency}
            </button>
            {q.freshness?.sessions_behind ? <span className="text-warn">{q.freshness.sessions_behind} session(s) behind</span> : null}
          </div>
        </div>
      ) : (
        <div className="text-right text-sm text-muted">
          <Badge tone="down">No price data</Badge>
          <div className="mt-1 max-w-xs text-xs">{q.reason ?? 'No market-data source has bars for this security.'}</div>
        </div>
      )}
    </header>
  )
}
