import { test } from '@playwright/test'

// Documentation screenshots of the Simulation Lab on the SYNTHETIC fixture. Skipped unless SIM_SCREENSHOTS=1 (npm run e2e does not write files).
test.skip(!process.env.SIM_SCREENSHOTS, 'screenshots are generated on demand')
const T0 = '2016-12-30T23:00:00+00:00'
const out = (n: string) => ({ path: `../docs/img/simulation-lab/${n}.png`, fullPage: true })

test('simulation lab screenshots', async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  const px = ((await (await request.get('/analyzer/SYNSIM/quote', { params: { as_of: T0 } })).json()).price as number)
  const mk = async (data: Record<string, unknown>) => (await (await request.post('/simulations', { data: { security: 'SYNSIM', as_of: T0, ...data } })).json()).simulation_id as string
  const r4 = (x: number) => Math.round(x * 10000) / 10000
  const closed = await mk({ plan_origin: 'USER_DEFINED', plan: { entry_type: 'LIMIT', entry_price: r4(px * 0.99), stop_loss: r4(px * 0.95), target_1: r4(px * 1.03), target_2: r4(px * 1.06) } })
  const active = await mk({ plan_origin: 'USER_DEFINED', plan: { entry_type: 'MARKET_REFERENCE', stop_loss: r4(px * 0.85), target_1: r4(px * 1.2) } })
  for (const id of [closed, active]) await request.post(`/simulations/${id}/update`)
  // active: only the first bars (as_of before the wide bar) — an update at an earlier instant materialises nothing newer, so make a fresh one
  await page.goto('/simulations')
  await page.waitForSelector('[data-testid="sim-table"]')
  await page.screenshot(out('dashboard'))
  await page.goto('/analyzer/SYNF')
  await page.getByTestId('simulate-open').click()
  await page.getByTestId('wizard-next').click()
  const p2 = ((await (await request.get('/analyzer/SYNF/quote')).json()).price as number)
  await page.getByLabel('Entry zone low', { exact: true }).fill((p2 * 0.97).toFixed(2))
  await page.getByLabel('Entry zone high', { exact: true }).fill(p2.toFixed(2))
  await page.getByTestId('wizard-next').click()
  await page.getByLabel('Stop loss', { exact: true }).fill((p2 * 0.9).toFixed(2))
  await page.getByLabel('Target 1', { exact: true }).fill((p2 * 1.05).toFixed(2))
  await page.getByLabel('Target 2', { exact: true }).fill((p2 * 1.1).toFixed(2))
  await page.screenshot(out('create-simulation'))
  await page.goto(`/simulations/${active}`)
  await page.waitForSelector('[data-testid="sim-timeline"]')
  await page.screenshot(out('active-simulation'))
  await page.goto(`/simulations/${closed}`)
  await page.getByRole('button', { name: 'Post-mortem' }).click()
  await page.waitForSelector('[data-testid="postmortem"]')
  await page.screenshot(out('closed-postmortem'))
})
