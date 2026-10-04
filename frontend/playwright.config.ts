import { defineConfig } from '@playwright/test'

const port = process.env.PITQUANT_E2E_PORT ?? '8765'

// Browser E2E over a SYNTHETIC fixture DB: no external APIs, no secrets (tests/e2e/serve.py).
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: { baseURL: `http://127.0.0.1:${port}`, trace: 'retain-on-failure' },
  webServer: {
    command: `python -m tests.e2e.serve ${port}`,
    cwd: '..',
    url: `http://127.0.0.1:${port}/analyzer/status`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
