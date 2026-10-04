import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { AppSwitcher } from './AppSwitcher'
import { GlobalSearch } from './GlobalSearch'
import { useTheme } from '../hooks/useTheme'
import { ErrorBoundary } from './ErrorBoundary'

const NAV = [
  { to: '/', label: 'Analyzer', end: true },
  { to: '/bitcoin', label: 'Bitcoin' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/research', label: 'Research Lab' },
  { to: '/simulations', label: 'Simulations' },
  { to: '/ayuda', label: 'Ayuda' },
  { to: '/status', label: 'Data Status' },
  { to: '/settings', label: 'Settings' },
]

type Status = { data_notice: { live_reference: string; required_env: string | null; mode: string } }

export function AppShell() {
  const { dark, toggle } = useTheme()
  const isBitcoin = useLocation().pathname.startsWith('/bitcoin')
  const { data } = useQuery({ queryKey: ['analyzer-status'], queryFn: ({ signal }) => api<Status>('/analyzer/status', signal), staleTime: 5 * 60_000 })
  const notice = data?.data_notice
  return (
    <div className="flex h-full">
      <aside className="hidden w-52 shrink-0 flex-col border-r border-border bg-surface md:flex">
        <div className="px-4 py-4">
          <div className="text-sm font-semibold tracking-tight">PIT<span className="text-accent">Quant</span></div>
          <div className="text-[10px] uppercase tracking-[0.12em] text-muted">Analyzer</div>
        </div>
        <nav aria-label="Primary" className="flex flex-col gap-0.5 px-2">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `rounded-md px-3 py-2 text-sm ${isActive ? 'bg-accent/10 font-medium text-accent' : 'text-muted hover:bg-surface-2 hover:text-fg'}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto p-3 text-[10px] leading-snug text-muted">
          Charts by{' '}
          <a className="underline" href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
            TradingView Lightweight Charts™
          </a>
          . Structured analysis, not investment advice.
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border bg-surface px-4 py-2.5">
          <nav aria-label="Mobile" className="flex gap-1 md:hidden">
            {NAV.slice(0, 4).map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `rounded px-2 py-1 text-[11px] ${isActive ? 'bg-accent/10 text-accent' : 'text-muted'}`}>
                {n.label.split(' ')[0]}
              </NavLink>
            ))}
          </nav>
          <AppSwitcher />
          <GlobalSearch />
          <Link to="/ayuda" className="ml-auto rounded-md border border-border px-2.5 py-1.5 text-xs text-muted hover:text-fg">Ayuda</Link>
          <button onClick={toggle} aria-label="Toggle light/dark theme" className="rounded-md border border-border px-2.5 py-1.5 text-xs text-muted hover:text-fg">
            {dark ? 'Light' : 'Dark'}
          </button>
        </header>
        {notice?.live_reference === 'FIXTURE' ? (
          <div role="status" data-testid="demo-banner" className="border-b border-warn/30 bg-warn/5 px-4 py-1.5 text-[11px] text-warn">
            <b>DEMO DATA</b> — synthetic fixture, not market data. Nothing on this screen is a real price, filing or result.
          </div>
        ) : !isBitcoin && notice && notice.live_reference !== 'CONFIGURED' ? (
          <div role="status" className="border-b border-warn/30 bg-warn/5 px-4 py-1.5 text-[11px] text-warn">
            <b>DATA SOURCE NOT CONFIGURED</b> — live reference quotes need <code className="num">{notice.required_env}</code>. Showing persisted end-of-day bars ({notice.mode}).
          </div>
        ) : null}
        <main className="min-h-0 flex-1 overflow-auto p-4 lg:p-6">
          <ErrorBoundary what="This page">
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
