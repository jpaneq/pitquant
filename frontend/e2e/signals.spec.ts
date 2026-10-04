import { expect, test } from '@playwright/test'

// SYNTHETIC fixture (SYNF): the chart shows the rule-based replay (R) and the user's paper trades (F) as separate, labelled layers.
test('Analyzer chart: retrospective algorithm signals are labelled, not validated, and separate from paper tests', async ({ page }) => {
  await page.goto('/analyzer/SYNF')
  await expect(page.getByRole('group', { name: 'Chart overlays' })).toBeVisible()
  await page.getByRole('button', { name: 'Señales algoritmo (R)' }).click()
  const panel = page.getByLabel('Señales del algoritmo')
  await expect(panel).toBeVisible()
  await expect(panel.getByText('No es una predicción ni un backtest validado', { exact: false })).toBeVisible()
  await expect(panel.getByText('RETROSPECTIVE_NOT_PIT', { exact: false })).toBeVisible()
  await expect(panel.getByText('holdout omitido', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Mis pruebas (F)' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: '3Y' }).click()
  await expect(panel).toBeVisible()
  await page.screenshot({ path: 'artifacts/analyzer-signals.png', fullPage: true })
})
