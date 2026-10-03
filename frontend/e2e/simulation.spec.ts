import { expect, test, type APIRequestContext } from '@playwright/test'

// Synthetic fixture only: SYNF (prices+fundamentals) and SYNSIM (the same path plus SCRIPTED future sessions, tests/e2e/serve.py).
// Never real market data. PAPER TRADE, NO REAL MONEY.
const T0 = '2016-12-30T23:00:00+00:00'

async function c0(request: APIRequestContext): Promise<number> {
  return (await (await request.get('/analyzer/SYNSIM/quote', { params: { as_of: T0 } })).json()).price as number
}
async function create(request: APIRequestContext, data: Record<string, unknown>): Promise<string> {
  const r = await request.post('/simulations', { data: { security: 'SYNSIM', as_of: T0, ...data } })
  expect(r.status(), await r.text()).toBe(200)
  return (await r.json()).simulation_id as string
}
const round = (x: number) => Math.round(x * 10000) / 10000

test.describe('Simulation Lab on the synthetic fixture', () => {
  const errors: string[] = []
  test.beforeEach(({ page }) => {
    errors.length = 0
    page.on('pageerror', (e) => errors.push(e.message))
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
  })
  test.afterEach(() => { expect(errors, 'no console/page errors').toEqual([]) })

  test('wizard from the Analyzer: T0 is frozen, WAITING_ENTRY, update is idempotent, cancel', async ({ page, request }) => {
    const px = (await (await request.get('/analyzer/SYNF/quote')).json()).price as number
    await page.goto('/analyzer/SYNF')
    await page.getByTestId('simulate-open').click()
    await expect(page.getByTestId('wizard-setup')).toContainText('Current price')
    await page.getByTestId('wizard-next').click()
    const set = async (label: string, v: number) => page.getByLabel(label, { exact: true }).fill(v.toFixed(2))
    await set('Entry zone low', px * 0.5); await set('Entry zone high', px * 0.55) // far below the market: it will wait
    await page.getByTestId('wizard-next').click()
    await set('Stop loss', px * 0.4); await set('Target 1', px * 0.7)
    await expect(page.getByTestId('rr-preview')).toContainText('R:R TP1')
    await expect(page.getByTestId('size-preview')).toContainText('shares')
    await page.getByTestId('simulate-submit').click()
    await expect(page).toHaveURL(/simulations\//)
    await expect(page.getByTestId('paper-banner')).toContainText('PAPER TRADE — NO REAL MONEY')
    await expect(page.getByText('PREDICTION ENGINE NOT YET VALIDATED').first()).toBeVisible()
    const id = page.url().split('/').pop() as string
    const t0 = (await (await request.get(`/simulations/${id}`)).json()).simulation
    await expect(page.getByTestId('tab-t0')).toContainText('never changes after creation')
    await expect(page.getByTestId('sim-chart-empty')).toBeVisible()
    await expect(page.getByTestId('sim-levels')).toContainText('Stop')
    await page.getByTestId('sim-update').click()
    await expect(page.getByTestId('sim-state')).toContainText('WAITING ENTRY')
    await page.getByTestId('sim-update').click()
    await expect(page.getByTestId('update-result')).toContainText('0 new events')
    const after = (await (await request.get(`/simulations/${id}`)).json()).simulation
    expect(after, 'the T0 row is identical after the update').toEqual(t0)
    await page.getByTestId('sim-cancel').click()
    await page.getByTestId('sim-update').click()
    await expect(page.getByTestId('sim-state')).toContainText('CANCELLED')
    await expect(page.getByTestId('sim-timeline')).toContainText('Cancelled before the entry')
  })

  test('lifecycle: entry at the limit, target touched without exit, stop, MAE/MFE/R, replay, post-mortem, hypothesis', async ({ page, request }) => {
    const p = await c0(request)
    const id = await create(request, { plan_origin: 'USER_DEFINED', plan: { entry_type: 'LIMIT', entry_price: round(p * 0.99), stop_loss: round(p * 0.95), target_1: round(p * 1.03), target_2: round(p * 1.06) } })
    await page.goto(`/simulations/${id}`)
    await expect(page.getByTestId('sim-state')).toContainText('CREATED')
    await page.getByTestId('sim-update').click()
    await expect(page.getByTestId('sim-state')).toContainText('STOPPED')
    const tl = page.getByTestId('sim-timeline')
    await expect(tl).toContainText('Entry filled @')
    await expect(tl).toContainText('EXPLICIT_LIMIT')
    await expect(tl).toContainText('TP1 touched')
    await expect(tl).toContainText('position unchanged (track targets only)')
    await expect(tl).toContainText('Stopped @')
    const perf = page.getByTestId('sim-performance')
    await expect(perf).toContainText('-1.00R') // realised R: (stop - entry) / initial risk
    await expect(perf).toContainText('-1.25R') // MAE in R
    await expect(perf).toContainText('+1.25R') // MFE in R
    await expect(perf).toContainText('STOP_HIT')
    await expect(perf).toContainText('n/a (NOT_YET_VALIDATED)') // prediction and execution are separate questions
    await page.getByTestId('sim-replay').click()
    await expect(page.getByTestId('replay-result')).toContainText('MATCH')
    await page.getByTestId('sim-update').click()
    await expect(page.getByTestId('update-result')).toContainText('0 new events')
    // post-mortem: facts first, then a person classifies, then a hypothesis (UNTESTED)
    await page.getByRole('button', { name: 'Post-mortem' }).click()
    await expect(page.getByTestId('postmortem')).toContainText('STOP_HIT')
    await expect(page.getByTestId('diagnostic-flags')).toContainText('STOP_HIT_BEFORE_LATER_TP')
    await expect(page.getByTestId('diagnostic-flags')).toContainText('HIGH_MFE_LOW_REALIZED')
    await page.getByLabel('Classified by').fill('tester')
    await page.getByLabel('Primary cause').selectOption('NO_CLEAR_ERROR')
    await page.getByTestId('pm-save').click()
    await expect(page.getByTestId('pm-saved')).toContainText('NO_CLEAR_ERROR')
    await page.getByLabel('Hypothesis statement').fill('Stops under 1.5 ATR may stop out before a later target (synthetic example)')
    await page.getByTestId('hyp-create').click()
    await expect(page.getByTestId('hyp-created')).toContainText('UNTESTED')
    const hyps = await (await request.get('/simulations/hypotheses')).json()
    expect(hyps.at(0).status).toBe('UNTESTED')
    await page.getByRole('button', { name: 'Provenance' }).click()
    await expect(page.getByTestId('tab-provenance')).toContainText('verified: true')
  })

  test('AMBIGUOUS_INTRABAR: stop and target in the same daily bar are not resolved favourably', async ({ page, request }) => {
    const p = await c0(request)
    const id = await create(request, { plan_origin: 'USER_DEFINED', plan: { entry_type: 'MARKET_REFERENCE', stop_loss: round(p * 0.93), target_1: round(p * 1.05), exit_policy: 'PARTIAL_FRACTIONS', exit_fractions: [1, 0, 0] } })
    await page.goto(`/simulations/${id}`)
    await page.getByTestId('sim-update').click()
    await expect(page.getByTestId('sim-state')).toContainText('AMBIGUOUS INTRABAR')
    const amb = page.getByTestId('ambiguity')
    await expect(amb).toContainText('STOP_FIRST -1.00R')
    await expect(amb).toContainText('TARGET_FIRST +0.71R')
    await expect(page.getByTestId('sim-timeline')).toContainText('Ambiguous intrabar')
    await page.getByTestId('sim-replay').click()
    await expect(page.getByTestId('replay-result')).toContainText('MATCH')
  })

  test('USER_MODIFIED vs the PITQuant plan: comparison and a labelled counterfactual', async ({ page, request }) => {
    const plan = (await (await request.get('/analyzer/SYNSIM/trade-plan', { params: { as_of: T0 } })).json()).setups.find((s: { profile: string }) => s.profile === 'BASE')
    const id = await create(request, { plan_origin: 'USER_MODIFIED', plan: { entry_type: 'ENTRY_ZONE', entry_zone_low: plan.entry_zone.lower, entry_zone_high: plan.entry_zone.upper, stop_loss: round(plan.stop * 0.97), target_1: plan.target_1, target_2: plan.target_2, invalidation_level: plan.invalidation_level } })
    await page.goto(`/simulations/${id}`)
    await page.getByTestId('sim-update').click()
    await expect(page.getByTestId('sim-state')).not.toContainText('CREATED')
    await page.getByRole('button', { name: 'Plan comparison' }).click()
    const cmp = page.getByTestId('plan-comparison')
    await expect(cmp).toContainText('PITQuant original')
    await expect(cmp.locator('[data-changed="true"]').first()).toBeVisible() // the user moved the stop
    await expect(cmp).toContainText('COUNTERFACTUAL')
    await expect(page.getByTestId('counterfactual-line')).not.toHaveText('—')
    const real = await (await request.get(`/simulations/${id}/replay`)).json()
    expect(real.match, 'the counterfactual is not part of the real event log').toBe(true)
  })

  test('dashboard: neutral state wording, N, filters, insights with insufficient sample', async ({ page }) => {
    await page.goto('/simulations')
    await expect(page.getByText('PREDICTION ENGINE NOT YET VALIDATED').first()).toBeVisible()
    await expect(page.getByTestId('sim-insufficient')).toBeVisible()
    await expect(page.getByTestId('sim-table')).toBeVisible()
    expect((await page.getByTestId('sim-table').textContent()) ?? '').not.toMatch(/\bwin\b|\bloss\b/i)
    await page.getByTestId('insights-link').click()
    await expect(page.getByTestId('insights-table')).toContainText('INSUFFICIENT SAMPLE')
  })

  test('engine pinning and recorded observations: a new current engine never changes an existing simulation', async ({ page, request }) => {
    const p = await c0(request)
    const plan = { entry_type: 'MARKET_REFERENCE', stop_loss: round(p * 0.5), target_1: round(p * 5) }
    const first = await create(request, { plan_origin: 'USER_DEFINED', plan, horizon_sessions: 120 })
    // 1. a V1 simulation: observations are generated by the update and shown as HISTORICAL records
    await page.goto(`/simulations/${first}`)
    await expect(page.getByTestId('engine-badge')).toContainText('Engine v1')
    await page.getByTestId('sim-update').click()
    await expect(page.getByTestId('update-result')).toBeVisible()
    await page.getByRole('button', { name: 'Recorded observations' }).click()
    const rows = page.getByTestId('obs-row')
    await expect(rows.first()).toContainText('T+1')
    await expect(page.getByTestId('tab-observations')).toContainText('T+5')
    await expect(rows.first()).toContainText('analyzer analyzer-v0')
    // 2. Changes: T0 vs the latest RECORDED observation (historical), CURRENT is a separate, labelled option
    await page.getByRole('button', { name: 'Changes', exact: true }).click()
    await expect(page.getByTestId('to-source')).toContainText('RECORDED — historical')
    await expect(page.getByTestId('tab-changes')).toContainText('Return since entry')
    await page.getByLabel('Changes to').selectOption('CURRENT')
    await expect(page.getByTestId('to-source')).toContainText('CURRENT — not known on any earlier date')
    // 3. Provenance: the pinned engine and the event schema
    await page.getByRole('button', { name: 'Provenance' }).click()
    await expect(page.getByTestId('engine-provenance')).toContainText('Simulation Engine')
    await expect(page.getByTestId('engine-provenance')).toContainText('v1')
    await expect(page.getByTestId('engine-provenance')).toContainText('Event Schema')
    // 4. the fixture switches the CURRENT engine: the existing simulation stays on v1, a NEW one is pinned to the other
    const sw = await request.post('/__e2e__/current-engine', { data: { version: 'v_e2e_different' } })
    expect(sw.status()).toBe(200)
    try {
      const second = await create(request, { plan_origin: 'USER_DEFINED', plan, horizon_sessions: 120 })
      await page.goto(`/simulations/${second}`)
      await expect(page.getByTestId('engine-badge')).toContainText('Engine v_e2e_different')
      await page.goto(`/simulations/${first}`)
      await page.getByTestId('sim-update').click()
      await expect(page.getByTestId('engine-badge')).toContainText('Engine v1')
      const ev = (await (await request.get(`/simulations/${first}/events`)).json()) as { engine_version: string }[]
      expect(new Set(ev.map((e) => e.engine_version))).toEqual(new Set(['v1']))
      await page.getByTestId('sim-replay').click()
      await expect(page.getByTestId('replay-result')).toContainText('MATCH')
      const rep = await (await request.get(`/simulations/${first}/replay`)).json()
      expect(rep.engine_version).toBe('v1')
      await page.goto('/simulations')
      await page.getByTestId('insights-link').click()
      await expect(page.getByTestId('engines-note')).toContainText('engine v1')
      await expect(page.getByTestId('engines-note')).toContainText('engine v_e2e_different')
    } finally {
      await request.post('/__e2e__/current-engine', { data: { version: 'v1' } })
    }
  })
})
