import { defineConfig } from '@playwright/test'

// Smoke tests run against an already-running stack:
//   docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  use: { baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173' },
  reporter: [['list']],
})
