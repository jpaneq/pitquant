import { defineConfig } from '@playwright/test'

// Browser E2E over a SYNTHETIC fixture DB: no external APIs, no secrets (tests/e2e/serve.py).
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: { baseURL: 'http://127.0.0.1:8765', trace: 'retain-on-failure' },
  webServer: {
    command: 'python -m tests.e2e.serve 8765',
    cwd: '..',
    url: 'http://127.0.0.1:8765/analyzer/status',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
