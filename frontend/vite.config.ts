/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const API = process.env.PITQUANT_API ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // SPA routes (/analyzer/AAPL) share a prefix with API routes (/analyzer/AAPL/summary): browser
    // navigations (Accept: text/html) are served the app, fetch() calls go to the API.
    proxy: Object.fromEntries(
      ['/search', '/analyzer', '/health', '/dev'].map((p) => [
        p,
        { target: API, bypass: (req: { headers: { accept?: string } }) => (req.headers.accept?.includes('text/html') ? '/index.html' : undefined) },
      ]),
    ),
  },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test-setup.ts'], css: false, include: ['src/**/*.test.{ts,tsx}'] },
})
