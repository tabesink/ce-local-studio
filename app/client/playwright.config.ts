import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 300_000,
  expect: {
    timeout: 60_000,
    toHaveScreenshot: { maxDiffPixelRatio: 0.005 },
  },
  // Match visual-parity-manifest.json expectedPath under tests/e2e/visual-baselines/chromium/
  snapshotPathTemplate: "{testDir}/visual-baselines/chromium/{arg}{ext}",
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  globalSetup: "./tests/e2e/global-setup.ts",
  outputDir: "./test-results",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    locale: "en-US",
    timezoneId: "UTC",
    deviceScaleFactor: 1,
  },
  projects: [
    {
      name: "chromium-pr-fast",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
