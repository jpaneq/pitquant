import { afterEach, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FundsPanel, type Fund } from '../features/forward/FundsPanel'

const cobas: Fund = {
  isin: 'ES0119199000', symbol: '0P00019W2R.F', name: 'Cobas Internacional C FI', currency: 'EUR',
  forecasts: 3, matured: 2, hits: 1, accuracy: .5, always_up_accuracy: 1,
  latest: { p_up: .6, feature_date: '2026-11-05', reference_nav: 198.05, target_date: '2026-12-03', version: '2026-11', last_step: 5, last_return: .012 },
  history: [{ date: '2026-09-01', p_up: .6, return: .02, hit: true }, { date: '2026-09-02', p_up: .4, return: .01, hit: false }],
}
const wrap = (funds: Fund[]) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><FundsPanel funds={funds} /></QueryClientProvider>
afterEach(() => vi.unstubAllGlobals())

it('shows each fund with its forecast, checkpoint and scorecard against "always up"', () => {
  render(wrap([cobas]))
  expect(screen.getByText('Cobas Internacional C FI')).toBeInTheDocument()
  expect(screen.getByText('60%')).toBeInTheDocument()
  expect(screen.getByText(/revisión 5\/20 · \+1\.2%/)).toBeInTheDocument()
  expect(screen.getByText('1/2')).toBeInTheDocument()
  expect(screen.getByText(/«siempre sube»: 100%/)).toBeInTheDocument()
})

it('only searches a well-formed ISIN, then adds the chosen listing', async () => {
  const calls: { url: string; init?: RequestInit }[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url: String(url), init })
    if (String(url).includes('/funds/search')) return new Response(JSON.stringify([{ isin: 'ES0119199000', symbol: '0P00019W2R.F', name: 'Cobas Internacional C FI', currency: 'EUR' }]))
    return new Response(JSON.stringify({ ok: true }))
  }))
  render(wrap([]))
  expect(screen.getByText(/Aún no has añadido fondos/)).toBeInTheDocument()
  const button = screen.getByRole('button', { name: 'Buscar' })
  await userEvent.type(screen.getByLabelText('ISIN del fondo'), 'es01191990')
  expect(button).toBeDisabled()
  await userEvent.type(screen.getByLabelText('ISIN del fondo'), '00')
  await userEvent.click(button)
  await userEvent.click(await screen.findByRole('button', { name: 'Añadir' }))
  const post = calls.find(c => c.init?.method === 'POST')
  expect(post?.url).toContain('/forward-pilots/funds')
  expect(JSON.parse(String(post?.init?.body))).toMatchObject({ isin: 'ES0119199000', symbol: '0P00019W2R.F' })
})
