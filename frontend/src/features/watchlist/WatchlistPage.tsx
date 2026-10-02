import { useReactTable, getCoreRowModel, flexRender, type ColumnDef } from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSummary } from '../../api/hooks'
import { Badge, Button, Card, CardBody, CardHeader, Skeleton } from '../../components/ui/primitives'
import { fmtNum, fmtPct, fmtTime, signClass } from '../../lib/format'

const KEY = 'pq-watchlist'
const load = (): string[] => {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '["AAPL","MSFT","KO"]') as string[]
  } catch {
    return ['AAPL', 'MSFT', 'KO']
  }
}
type Row = { ticker: string }

function Cells({ t, col }: { t: string; col: string }) {
  const q = useSummary(t)
  if (q.isPending) return <Skeleton className="h-4 w-14" />
  if (q.isError) return <span className="text-warn">n/a</span>
  const s = q.data
  const lab = (k: string) => s.summary[k] ?? '—'
  switch (col) {
    case 'price': return <span className="num">{fmtNum(s.quote.price)}</span>
    case 'day': return <span className={`num ${signClass(s.quote.change_pct)}`}>{fmtPct(s.quote.change_pct, 2, true)}</span>
    case 'fundamental': return <Badge>{lab('fundamentals')}</Badge>
    case 'valuation': return <Badge>{lab('valuation')}</Badge>
    case 'trend': return <Badge>{lab('trend')}</Badge>
    case 'momentum': return <Badge>{lab('momentum')}</Badge>
    case 'risk': return <Badge>{lab('risk')}</Badge>
    case 'model': return <span className="text-muted" title="No validated Champion">—</span>
    case 'updated': return <span className="num text-[11px] text-muted">{fmtTime(s.quote.timestamp)}</span>
    default: return null
  }
}

export function WatchlistPage() {
  const [list, setList] = useState<string[]>(load)
  const [input, setInput] = useState('')
  const save = (l: string[]) => (setList(l), localStorage.setItem(KEY, JSON.stringify(l)))
  const cols = useMemo<ColumnDef<Row>[]>(
    () => [
      { id: 'ticker', header: 'Ticker', cell: ({ row }) => <Link className="num font-semibold text-accent" to={`/analyzer/${row.original.ticker}`}>{row.original.ticker}</Link> },
      ...(['price', 'day', 'fundamental', 'valuation', 'trend', 'momentum', 'risk', 'model', 'updated'] as const).map<ColumnDef<Row>>((c) => ({ id: c, header: c === 'day' ? 'Day %' : c[0].toUpperCase() + c.slice(1), cell: ({ row }) => <Cells t={row.original.ticker} col={c} /> })),
      { id: 'rm', header: '', cell: ({ row }) => <button aria-label={`Remove ${row.original.ticker}`} className="text-xs text-muted hover:text-down" onClick={() => save(list.filter((x) => x !== row.original.ticker))}>Remove</button> },
    ],
    [list],
  )
  const table = useReactTable({ data: list.map((ticker) => ({ ticker })), columns: cols, getCoreRowModel: getCoreRowModel() })
  return (
    <div className="mx-auto max-w-6xl">
      <Card>
        <CardHeader title="Watchlist" sub="Stored in this browser. Values come from the Analyzer API." right={
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); const t = input.trim().toUpperCase(); if (t && !list.includes(t)) save([...list, t]); setInput('') }}>
            <input aria-label="Add ticker" placeholder="Add ticker" value={input} onChange={(e) => setInput(e.target.value)} className="w-28 rounded-md border border-border bg-surface-2 px-2 py-1 text-xs" />
            <Button type="submit">Add</Button>
          </form>
        } />
        <CardBody className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="text-left text-[10px] uppercase tracking-[0.08em] text-muted">
              {table.getHeaderGroups().map((hg) => <tr key={hg.id}>{hg.headers.map((h) => <th key={h.id} className="px-4 py-2 font-medium">{flexRender(h.column.columnDef.header, h.getContext())}</th>)}</tr>)}
            </thead>
            <tbody>{table.getRowModel().rows.map((r) => <tr key={r.id} className="border-t border-border">{r.getVisibleCells().map((c) => <td key={c.id} className="px-4 py-2.5">{flexRender(c.column.columnDef.cell, c.getContext())}</td>)}</tr>)}</tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  )
}
