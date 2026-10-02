import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSearch } from '../api/hooks'
import type { SearchHit } from '../api/types'
import { Badge } from './ui/primitives'

const MATCH: Record<SearchHit['match_type'], string> = { EXACT: 'ticker', IDENTIFIER: 'identifier', PREFIX: 'prefix', NAME: 'name', FUZZY: 'did you mean' }
const STATUS: Record<string, string> = { 'PRICES+FUNDAMENTALS': 'Full data', PRICES_ONLY: 'Prices only', FUNDAMENTALS_ONLY: 'Fundamentals only', NO_DATA: 'No data' }

export function GlobalSearch() {
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 180)
    return () => clearTimeout(t)
  }, [q])
  useEffect(() => {
    const h = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  const { data, isFetching } = useSearch(debounced)
  const results = data?.results ?? []
  const go = (h: SearchHit) => {
    setOpen(false)
    setQ('')
    nav(`/analyzer/${encodeURIComponent(h.ticker ?? h.security_id)}`)
  }
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(a + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Escape') setOpen(false)
    else if (e.key === 'Enter') {
      // an inexact match is NEVER analysed silently: Enter only navigates on an exact ticker/identifier hit
      const h = results[active]
      if (h && (h.match_type === 'EXACT' || h.match_type === 'IDENTIFIER' || active > 0 || results.length === 1) && data?.exact) go(h)
      else setOpen(true)
    }
  }
  return (
    <div ref={box} className="relative w-full max-w-xl">
      <input
        role="combobox"
        aria-expanded={open}
        aria-controls="search-results"
        aria-label="Search security by ticker, company, CUSIP or ISIN"
        placeholder="Search ticker, company, CUSIP or ISIN — e.g. AAPL, Apple, 037833100"
        value={q}
        onChange={(e) => {
          setQ(e.target.value)
          setOpen(true)
          setActive(0)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
        className="w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-sm placeholder:text-muted focus:border-accent"
      />
      {open && debounced.trim() ? (
        <ul id="search-results" role="listbox" className="absolute z-30 mt-1 max-h-96 w-full overflow-auto rounded-md border border-border bg-surface shadow-xl">
          {data?.needs_confirmation ? <li className="border-b border-border px-3 py-2 text-[11px] text-warn">No exact match for “{data.query}”. Did you mean:</li> : null}
          {results.length === 0 && !isFetching ? <li className="px-3 py-3 text-xs text-muted">No security matches “{debounced}”.</li> : null}
          {results.map((h, i) => (
            <li key={h.security_id} role="option" aria-selected={i === active} onMouseEnter={() => setActive(i)} onClick={() => go(h)} className={`flex cursor-pointer items-center justify-between gap-3 px-3 py-2 text-sm ${i === active ? 'bg-surface-2' : ''}`}>
              <span className="min-w-0">
                <span className="num font-semibold">{h.ticker ?? '—'}</span> <span className="text-muted">— {h.name}</span>
                <span className="block text-[11px] text-muted">
                  {[h.exchange, h.country, h.asset_class].filter(Boolean).join(' · ')}
                </span>
              </span>
              <span className="flex shrink-0 flex-col items-end gap-1">
                <Badge tone={h.match_type === 'FUZZY' ? 'warn' : 'neutral'}>{MATCH[h.match_type]}</Badge>
                <Badge tone={h.status === 'NO_DATA' ? 'down' : h.status === 'PRICES+FUNDAMENTALS' ? 'up' : 'info'}>{STATUS[h.status] ?? h.status}</Badge>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
