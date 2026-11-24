import { defineConfig } from "@playwright/test";

/** E2E runs the built SPA served by the real backend on a throw-away data directory.
 *  No real job site is contacted and nothing is ever submitted. */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8000", trace: "retain-on-failure" },
  webServer: {
    command:
      "rm -rf /tmp/jobagent-e2e && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
    cwd: "../backend",
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      JOBAGENT_DATA_DIR: "/tmp/jobagent-e2e/data",
      JOBAGENT_DOCUMENTS_DIR: "/tmp/jobagent-e2e/documents",
      JOBAGENT_LOGS_DIR: "/tmp/jobagent-e2e/logs",
      JOBAGENT_SCHEDULER_ENABLED: "false",
      JOBAGENT_AI_ENABLED: "false",
    },
  },
  projects: [{
    name: "chromium",
    // Optional: point at an existing Chromium (E2E_CHROMIUM=/path/to/chrome); otherwise `npx playwright install chromium`.
    use: { browserName: "chromium", launchOptions: process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {} },
  }],
});
