import { expect, test } from '@playwright/test'

test('info buttons explain each metric in Spanish', async ({ page }) => {
  await page.goto('/analyzer/SYNF')
  const tip = page.getByRole('button', { name: /Qué es RSI 14/ })
  await tip.scrollIntoViewIfNeeded()
  await tip.click()
  const dialog = page.getByRole('dialog', { name: 'RSI 14' })
  await expect(dialog).toContainText('Positivo:')
  await expect(dialog).toContainText('Negativo:')
  await page.screenshot({ path: 'artifacts/help-info-tip.png' })
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
})

test('the app launcher and the help guide are reachable from any view', async ({ page }) => {
  for (const start of ['/analyzer/SYNF', '/simulations', '/watchlist']) {
    await page.goto(start)
    await page.getByRole('button', { name: /Aplicaciones/ }).click()
    await expect(page.getByRole('menuitem', { name: /Acciones/ })).toBeVisible()
    await expect(page.getByRole('menuitem', { name: /Bitcoin/ })).toBeVisible()
    await expect(page.getByRole('menuitem', { name: /Simulation Lab/ })).toBeVisible()
    await page.keyboard.press('Escape')
  }
  await page.goto('/watchlist')
  await page.getByRole('button', { name: /Aplicaciones/ }).click()
  await page.getByRole('menuitem', { name: /Simulation Lab/ }).click()
  await expect(page).toHaveURL(/\/simulations$/)
  await page.getByRole('link', { name: 'Ayuda', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: 'Guía de uso de PITQuant' })).toBeVisible()
  await page.getByRole('link', { name: 'Glosario' }).first().click()
  await expect(page.getByRole('heading', { name: 'Glosario' })).toBeVisible()
  await page.setViewportSize({ width: 1280, height: 2200 })
  await page.screenshot({ path: 'artifacts/help-guide.png', fullPage: false })
})
