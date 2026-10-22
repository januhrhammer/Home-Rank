import { defineConfig, devices } from "@playwright/test";

import { AUTH_FILE } from "./account";

// End-to-end tests: a real browser against the whole app (website, worker and database) as
// Docker Compose runs it for self-hosters. `just e2e` starts that stack and runs them.
export default defineConfig({
  testDir: ".",
  // The tests share one account and one database, so they run one after another.
  workers: 1,
  // A forgotten test.only would quietly skip every other test in CI.
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:8104",
    // A recording of every step of a failed test: `pnpm exec playwright show-trace <file>`.
    trace: "retain-on-failure",
  },
  projects: [
    // Logs in once and saves the session cookie for the other tests.
    { name: "login", testMatch: "login.setup.ts" },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], storageState: AUTH_FILE },
      dependencies: ["login"],
    },
  ],
});
