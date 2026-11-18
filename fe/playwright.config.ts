import { defineConfig, devices } from "@playwright/test";
const production = process.env.TEST_PRODUCTION === "1";
export default defineConfig({
  testMatch: production ? "**/devtools.spec.ts" : "**/*.spec.ts",
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  use: {
    baseURL: "http://127.0.0.1:5199",
    trace: "retain-on-failure",
    viewport: { width: 1280, height: 900 },
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 900 },
      },
    },
  ],
  webServer: {
    command: production
      ? "npm run preview -- --port 5199"
      : "npm run dev -- --port 5199",
    url: "http://127.0.0.1:5199",
    reuseExistingServer: false,
    env: {
      MOCK_DATA_DIR: ".data-e2e",
      VITE_CACHE_DIR: "node_modules/.vite-e2e",
    },
  },
  reporter: "list",
});
