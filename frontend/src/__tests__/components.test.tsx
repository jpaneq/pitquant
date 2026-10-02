import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { GlobalSearch } from '../components/GlobalSearch'
import { PredictionPanel } from '../features/analyzer/Panels'
import { Metric } from '../components/ui/primitives'

const wrap = (ui: ReactNode, path = '/') => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="*" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status, headers: { 'Content-Type': 'application/json' } }))

afterEach(() => vi.restoreAllMocks())

describe('GlobalSearch', () => {
  it('suggests AAPL for a misspelling and does NOT navigate silently on Enter', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({ query: 'APPL', exact: false, needs_confirmation: false, results: [{ security_id: 's1', ticker: 'AAPL', name: 'Apple Inc.', exchange: 'Nasdaq', country: 'US', asset_class: 'Equity', status: 'PRICES+FUNDAMENTALS', match_type: 'NAME', score: 80 }] }))
    wrap(<GlobalSearch />)
    const box = screen.getByRole('combobox')
    await userEvent.type(box, 'APPL')
    expect(await screen.findByText(/Apple Inc\./)).toBeInTheDocument()
    await userEvent.keyboard('{Enter}')
    // still in the listbox: the user must pick the suggestion explicitly
    expect(screen.getByRole('listbox')).toBeInTheDocument()
  })
  it('flags fuzzy results as "did you mean"', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({ query: 'APLE', exact: false, needs_confirmation: true, results: [{ security_id: 's1', ticker: 'AAPL', name: 'Apple Inc.', exchange: 'Nasdaq', country: 'US', asset_class: 'Equity', status: 'NO_DATA', match_type: 'FUZZY', score: 40 }] }))
    wrap(<GlobalSearch />)
    await userEvent.type(screen.getByRole('combobox'), 'APLE')
    expect(await screen.findByText(/No exact match/)).toBeInTheDocument()
    expect(screen.getByText('did you mean')).toBeInTheDocument()
  })
})

describe('panels', () => {
  it('Prediction shows NOT YET VALIDATED and never a number', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({ model_status: 'NOT_YET_VALIDATED', message: 'No validated Champion model exists', horizons: {} }))
    wrap(<PredictionPanel sec="AAPL" />)
    expect(screen.getByText(/not yet validated/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText(/No validated Champion/)).toBeInTheDocument())
    expect(screen.queryByText(/%/)).toBeNull()
  })
  it('Metric shows the reason when a value is unavailable (never 0)', () => {
    render(<Metric label="P/E" value="—" reason="denominator_invalid" />)
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByText(/not meaningful/)).toBeInTheDocument()
  })
  it('ErrorBoundary isolates a failing panel', () => {
    const Boom = () => {
      throw new Error('kaput')
    }
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    render(
      <div>
        <ErrorBoundary what="Bad panel"><Boom /></ErrorBoundary>
        <span>other panel still renders</span>
      </div>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Bad panel failed to render')
    expect(screen.getByText('other panel still renders')).toBeInTheDocument()
  })
})
