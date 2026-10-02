import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ResearchPage } from '../features/research/ResearchPage'

const json = (b: unknown) => Promise.resolve(new Response(JSON.stringify(b), { status: 200, headers: { 'Content-Type': 'application/json' } }))
const ROUTES: Record<string, unknown> = {
  '/research/status': { holdout: 'SEALED', holdout_range: ['2022-10-01', '2025-09-30'], flags: { RESEARCH_LAB_IMPLEMENTED: true, RESEARCH_DATA_READY: false }, reasons: {} },
  '/dev/status': { components: {}, research: { flags: { FEATURE_RESEARCH_READY_US: false }, status: {}, reasons: {}, metrics: {} }, holdout: { state: 'SEALED', start: '2022-10-01', end: '2025-09-30', outcomes_exposed: false } },
  '/research/experiments': [],
  '/research/datasets': [],
  '/research/features': { catalog: ['ret_6m', 'pe_ttm'], feature_sets: [], labels: [] },
  '/research/models': { predefined_baselines: [{ kind: 'ELASTIC_NET', target: 'future_excess_total_return', horizons: [6, 12], config_hash: 'abc' }], registered: [] },
  '/research/backtests': { folds: [], metric_sets: [] },
  '/research/audit': { holdout: 'SEALED', holdout_range: ['2022-10-01', '2025-09-30'], gates: ['gate D02 = false'], rules: ['decision_at mandatory'] },
}
beforeEach(() => {
  vi.spyOn(globalThis, 'fetch').mockImplementation((u) => json(ROUTES[String(u).replace(/^.*?(\/(research|dev)\/)/, '$1').split('?')[0]] ?? {}))
})
afterEach(() => vi.restoreAllMocks())

const renderPage = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><ResearchPage /></MemoryRouter></QueryClientProvider>)

describe('Research Lab', () => {
  it('always shows HOLDOUT SEALED and separates lab from data readiness', async () => {
    renderPage()
    expect(screen.getByText('HOLDOUT SEALED')).toBeInTheDocument()
    expect(await screen.findByText('RESEARCH_LAB_IMPLEMENTED')).toBeInTheDocument()
    expect(screen.getByText('RESEARCH_DATA_READY')).toBeInTheDocument()
  })
  it('shows empty states, never fake experiments or metrics', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: 'Experiments' }))
    expect(await screen.findByTestId('empty-state')).toHaveTextContent(/No experiments yet/)
    await userEvent.click(screen.getByRole('button', { name: 'Backtests' }))
    expect(await screen.findByTestId('empty-state')).toHaveTextContent(/No backtests yet/)
    await userEvent.click(screen.getByRole('button', { name: 'Models' }))
    expect(await screen.findByText(/No registered models or champion yet/)).toBeInTheDocument()
    expect(screen.getByText('ELASTIC_NET')).toBeInTheDocument()
  })
  it('keeps the sealed badge on every tab', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: 'Audit' }))
    expect((await screen.findAllByText(/SEALED/)).length).toBeGreaterThan(1)
  })
})
