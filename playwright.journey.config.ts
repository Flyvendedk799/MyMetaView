import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', testMatch: 'journey.spec.ts', workers: 1, retries: 0, timeout: 180000,
  expect: { timeout: 30000 }, reporter: 'list',
  use: { baseURL: 'http://localhost:5174', ...devices['Desktop Chrome'], actionTimeout: 20000, trace: 'retain-on-failure', screenshot: 'only-on-failure',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {} },
  webServer: [
    { command: 'npm run dev -- --port 5174', url: 'http://localhost:5174', reuseExistingServer: false,
      env: { VITE_API_BASE_URL: 'http://localhost:8015' } },
    { command: `${process.env.JOURNEY_PYTHON || '.venv/bin/python'} -m uvicorn e2e.backend:app --host 127.0.0.1 --port 8015`,
      url: 'http://localhost:8015/health', reuseExistingServer: false, timeout: 90000,
      env: { JOURNEY_TEST_SERVER: '1', DATABASE_URL: 'sqlite:///work/journey.db', REDIS_URL: process.env.JOURNEY_REDIS_URL || 'redis://localhost:6379/15',
        EMAIL_ENABLED: 'false', OPENAI_API_KEY: '', R2_ACCOUNT_ID: '', PUBLIC_BASE_URL: 'http://localhost:8015', MEDIA_ROOT: 'work/journey-media',
        FRONTEND_URL: 'http://localhost:5174', ALLOWED_ORIGINS: 'http://localhost:5174' } }
  ]
})
