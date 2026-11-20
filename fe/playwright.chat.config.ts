import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "chat-workspace.spec.ts",
  workers: 1,
  timeout: 30000,
  use: {
    baseURL: process.env.CHAT_E2E_BASE_URL || "http://127.0.0.1:5201",
    viewport: { width: 1500, height: 1000 },
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  reporter: "list",
});
