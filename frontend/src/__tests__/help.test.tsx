import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Metric, InfoTip } from '../components/ui/primitives'
import { AppSwitcher } from '../components/AppSwitcher'
import { HelpPage, SECTIONS } from '../features/help/HelpPage'
import { GLOSSARY, lookup } from '../lib/glossary'

const wrap = (ui: React.ReactElement) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>

describe('InfoTip', () => {
  it('shows what it is, when it is positive and when negative, in Spanish', async () => {
    render(<Metric label="ROE" value="25%" />)
    await userEvent.click(screen.getByRole('button', { name: /Qué es ROE/ }))
    const tip = screen.getByRole('dialog')
    expect(tip).toHaveTextContent('Positivo:')
    expect(tip).toHaveTextContent('Negativo:')
  })
  it('closes with Escape', async () => {
    render(<Metric label="RSI 14" value="55" />)
    await userEvent.click(screen.getByRole('button', { name: /Qué es RSI 14/ }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
  })
  it('renders nothing for an unknown label', () => {
    render(<Metric label="zzz unknown" value="1" />)
    expect(screen.queryByRole('button')).toBeNull()
    expect(lookup('zzz unknown')).toBeUndefined()
    render(<InfoTip />)
  })
  it('every glossary entry explains what it is, and metrics with direction give both readings', () => {
    for (const [k, v] of Object.entries(GLOSSARY)) {
      expect(v.t.length, k).toBeGreaterThan(2)
      expect(v.q.length, k).toBeGreaterThan(10)
      if (v.p || v.n) expect(Boolean(v.p) && Boolean(v.n), k).toBe(true)
    }
  })
})

describe('App switcher', () => {
  it('opens Acciones, Bitcoin and Simulation Lab from any view and flags Bitcoin when it is not in this server', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 404 })))
    render(wrap(<AppSwitcher />))
    await userEvent.click(screen.getByRole('button', { name: /Aplicaciones/ }))
    expect(screen.getByRole('menuitem', { name: /Acciones/ })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /Simulation Lab/ })).toBeInTheDocument()
    expect(await screen.findByText(/no incluido en este servidor/)).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /Ayuda/ })).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
  it('says Bitcoin is available when the API answers', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } })))
    render(wrap(<AppSwitcher />))
    await userEvent.click(screen.getByRole('button', { name: /Aplicaciones/ }))
    expect(await screen.findByText(/cotización, predicciones y simulaciones/)).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
})

describe('Help page', () => {
  it('indexes every section with a working anchor and an illustration per program', () => {
    render(wrap(<HelpPage />))
    const nav = screen.getAllByRole('navigation', { name: 'Índice de la guía' })[0]
    for (const [id, title] of SECTIONS) {
      expect(nav.querySelector(`a[href="#${id}"]`), title).not.toBeNull()
      expect(document.getElementById(id), id).not.toBeNull()
    }
    expect(screen.getAllByRole('img').length).toBeGreaterThanOrEqual(6)
    expect(screen.getByText(/no son precios reales/)).toBeInTheDocument()
  })
  it('filters the glossary', async () => {
    render(wrap(<HelpPage />))
    await userEvent.type(screen.getByLabelText('Buscar en el glosario'), 'beta')
    expect(screen.getByText('Beta 252 días')).toBeInTheDocument()
    expect(screen.queryByText('ROE (rentabilidad sobre recursos propios)')).toBeNull()
  })
})
