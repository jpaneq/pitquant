import { expect, test } from '@playwright/test'

// Fixture server: no real prices for IBEX/MSCI World/BTC, SYNF as the only analysable S&P 500 name would need the universe file, so the report must say what is not accessible.
test('daily routine page: run today and get a plain-text report that says what could not be accessed', async ({ page }) => {
  await page.goto('/rutina')
  await expect(page.getByRole('heading', { name: 'Rutina diaria de compras simuladas' })).toBeVisible()
  await expect(page.getByText('Dinero simulado, reglas sin validar', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Ejecutar rutina de hoy' }).click()
  await expect(page.getByText('Rutina ejecutada.')).toBeVisible()
  const report = page.getByLabel('Informe de la rutina')
  await expect(report).toContainText('1. PARÁMETROS EN USO')
  await expect(report).toContainText('2. DATOS NO ACCESIBLES')
  await expect(report).toContainText('8. PUNTOS A REVISAR')
  await expect(report).toContainText('NO están validados')
  await expect(page.getByRole('link', { name: 'Descargar .txt' })).toBeVisible()
  await page.screenshot({ path: 'artifacts/routine-report.png', fullPage: false })
})

test('the routine is reachable from the app launcher and the guide explains it', async ({ page }) => {
  await page.goto('/watchlist')
  await page.getByRole('button', { name: /Aplicaciones/ }).click()
  await page.getByRole('menuitem', { name: /Rutina diaria/ }).click()
  await expect(page).toHaveURL(/\/rutina$/)
  await page.getByRole('link', { name: 'Cómo funciona' }).click()
  await expect(page.getByRole('heading', { name: 'Rutina diaria de compras simuladas' })).toBeVisible()
})
