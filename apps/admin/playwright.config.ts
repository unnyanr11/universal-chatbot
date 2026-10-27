import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  use: { channel: process.env.PLAYWRIGHT_CHANNEL || undefined, baseURL: "http://127.0.0.1:8000", trace: "retain-on-failure" },
  webServer: {
    command: "python ../../tests/serve_e2e.py",
    url: "http://127.0.0.1:8000/health",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
