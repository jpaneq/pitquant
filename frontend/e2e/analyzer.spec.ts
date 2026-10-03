import { expect, test } from '@playwright/test'

// Synthetic fixture only (SYNF = prices + fundamentals, SYNO = fundamentals only). Never real market data.
test.describe('Analyzer + Research Lab on the synthetic fixture', () => {
  const errors: string[] = []
  test.beforeEach(({ page }) => {
    errors.length = 0
    page.on('pageerror', (e) => errors.push(e.message))
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
  })
  test.afterEach(() => { expect(errors, 'no console/page errors').toEqual([]) })

  test('search → analyzer → panels, data quality, trade plan, no holdout leakage', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByTestId('demo-banner')).toContainText('DEMO DATA')
    const box = page.getByRole('combobox')
    await box.fill('SYNF')
    await page.getByRole('option').first().click()
    await expect(page).toHaveURL(/analyzer\/SYNF/)
    await expect(page.getByText('SYN FULL CO (FIXTURE)').first()).toBeVisible()
    await expect(page.locator('canvas').first()).toBeVisible()
    await expect(page.getByText('Trade plan (long)')).toBeVisible()
    await expect(page.getByText(/Rule-based · not yet backtest validated/)).toBeVisible()
    // provenance is on demand
    await page.getByText(/Provenance of this analysis/).click()
    await expect(page.getByText(/not a prediction/i)).toBeVisible()
    // a holdout date is refused by the API, so it can never reach the UI
    const r = await page.request.get('/analyzer/SYNF/summary?as_of=2023-06-01T00:00:00%2B00:00')
    expect(r.status()).toBe(403)
  })

  test('fundamentals-only security degrades without prices', async ({ page }) => {
    await page.goto('/analyzer/SYNO')
    await expect(page.getByText(/No price chart/)).toBeVisible()
  })

  test('Research Lab: HOLDOUT SEALED, empty states, no fake results', async ({ page }) => {
    await page.goto('/research')
    await expect(page.getByText('HOLDOUT SEALED')).toBeVisible()
    await expect(page.getByText('RESEARCH_DATA_READY').first()).toBeVisible()
    for (const tab of ['Experiments', 'Backtests']) {
      await page.getByRole('button', { name: tab }).click()
      await expect(page.getByTestId('empty-state')).toContainText(/No .* yet/)
      await expect(page.getByText('HOLDOUT SEALED')).toBeVisible()
    }
    await page.getByRole('button', { name: 'Models' }).click()
    await expect(page.getByText(/No registered models or champion yet/)).toBeVisible()
  })
})
