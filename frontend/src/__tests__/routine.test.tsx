import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RoutinePage } from '../features/routine/RoutinePage'

const REPORT = 'INFORME DE LA RUTINA DIARIA\n2. DATOS NO ACCESIBLES\n  IBEX: sin datos\n'
const wrap = (ui: React.ReactElement) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>
const stub = () => vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
  if (init?.method === 'POST') return new Response(JSON.stringify({ run: { run_date: '2026-10-05', markets: [{ market: 'IBEX', status: 'NO_DATA', unavailable: { SAN: 'x' } }, { market: 'SP500', status: 'ANALYZED', ticker: 'AAPL', bought: [3, 12] }] }, evaluation: { week: '2026-W41', evaluations_written: 2, closed: 0 } }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  return new Response(String(url).includes('/routine/report') ? REPORT : '{}', { status: 200, headers: { 'Content-Type': 'text/plain' } })
}))

describe('RoutinePage', () => {
  it('shows the plain-text report, copy and download actions', async () => {
    stub()
    render(wrap(<RoutinePage />))
    expect(await screen.findByText(/DATOS NO ACCESIBLES/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copiar informe' })).toBeEnabled()
    expect(screen.getByRole('link', { name: 'Descargar .txt' })).toHaveAttribute('download', 'informe_rutina.txt')
    vi.unstubAllGlobals()
  })
  it('runs today\'s step and summarises each market, saying what had no data', async () => {
    stub()
    render(wrap(<RoutinePage />))
    await screen.findByText(/DATOS NO ACCESIBLES/)
    await userEvent.click(screen.getByRole('button', { name: 'Ejecutar rutina de hoy' }))
    expect(await screen.findByText(/AAPL · compras simuladas a 3, 12 meses/)).toBeInTheDocument()
    expect(screen.getByText(/sin datos utilizables \(SAN/)).toBeInTheDocument()
    expect(screen.getByText('Rutina ejecutada.')).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
  it('states that it is simulated money with unvalidated rules', async () => {
    stub()
    render(wrap(<RoutinePage />))
    expect(screen.getByText(/Dinero simulado, reglas sin validar/)).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
})
