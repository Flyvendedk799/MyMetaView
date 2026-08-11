import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E config for MyMetaView demo generation flow.
 * Run: npm run test:e2e
 *
 * BASE_URL: App under test (default: http://localhost:5173)
 * For production: BASE_URL=https://www.mymetaview.com npm run test:e2e
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 15000,
    navigationTimeout: 15000,
  },
  timeout: 120000, // Demo generation can take 60–90s (batch submit + polling + results)
  expect: {
    timeout: 10000,
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Same override the backend honors: point at a system Chromium when
        // the Playwright-managed download isn't present (CI images, sandboxes).
        ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
          ? { launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } }
          : {}),
      },
    },
  ],
});
