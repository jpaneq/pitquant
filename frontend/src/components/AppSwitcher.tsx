import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

/** Lanzador de aplicaciones presente en todas las vistas: Acciones, Bitcoin y Simulation Lab. */
export function AppSwitcher() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const nav = useNavigate()
  const btc = useQuery({ queryKey: ['btc-available'], queryFn: ({ signal }) => api<unknown>('/btc/status', signal), enabled: open, staleTime: 5 * 60_000, retry: false })
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
  const go = (to: string) => { setOpen(false); nav(to) }
  const btcOk = btc.isSuccess
  return (
    <div ref={ref} className="relative">
      <button aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="rounded-md border border-border px-2.5 py-1.5 text-xs text-muted hover:text-fg">Aplicaciones ▾</button>
      {open ? (
        <div role="menu" aria-label="Aplicaciones" className="absolute left-0 top-9 z-40 w-60 rounded-md border border-border bg-surface p-1 shadow-lg">
          <button role="menuitem" onClick={() => go('/')} className="block w-full rounded px-3 py-2 text-left text-sm hover:bg-surface-2">Acciones<span className="block text-[10px] text-muted">Analyzer, señales y plan</span></button>
          <button role="menuitem" onClick={() => go('/bitcoin')} className="block w-full rounded px-3 py-2 text-left text-sm hover:bg-surface-2">Bitcoin<span className="block text-[10px] text-muted">{btc.isPending ? 'comprobando…' : btcOk ? 'cotización, predicciones y simulaciones' : 'no incluido en este servidor (rama de Bitcoin)'}</span></button>
          <button role="menuitem" onClick={() => go('/simulations')} className="block w-full rounded px-3 py-2 text-left text-sm hover:bg-surface-2">Simulation Lab<span className="block text-[10px] text-muted">operaciones paper e Insights</span></button>
          <Link role="menuitem" to="/ayuda" onClick={() => setOpen(false)} className="block rounded px-3 py-2 text-sm hover:bg-surface-2">Ayuda y guía de uso</Link>
        </div>
      ) : null}
    </div>
  )
}
