import { defineConfig, devices } from "@playwright/test";

/**
 * Two targets, both built and started by Playwright itself:
 *
 *   mock  Next.js in NEXT_PUBLIC_API_MODE=mock on :3100. No backend needed.
 *   live  FastAPI (uvicorn, in-memory store, recorded LLM cache, no Supabase) on :8000 plus Next.js in
 *         NEXT_PUBLIC_API_MODE=live on :3000. The demo walk is the same spec as in mock mode.
 *
 * The live web server uses :3000 (the API default CORS origin); E2E_LIVE_PORT moves it and tells the API to allow that origin.
 * E2E_TARGET=mock|live|all (default all) chooses which servers start; `pnpm test:e2e:mock` and
 * `pnpm test:e2e:live` set it. Needs `uv` for the API and `pnpm exec playwright install chromium` once.
 */
const MOCK_PORT = Number(process.env.E2E_PORT ?? 3100);
const LIVE_PORT = Number(process.env.E2E_LIVE_PORT ?? 3000); // override when another program holds :3000; the API is then told to allow that origin
const API_PORT = Number(process.env.E2E_API_PORT ?? 8000); // override when another program holds :8000
// contract.spec.ts calls the live adapters from Node: they read the API address from this variable.
process.env.NEXT_PUBLIC_API_URL ??= `http://localhost:${API_PORT}`;
const target = process.env.E2E_TARGET ?? "all";
const wantMock = target === "all" || target === "mock";
const wantLive = target === "all" || target === "live";

const desktop = { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } };

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  // PW_CHROMIUM_PATH points at a pre-installed Chromium when the pinned browser build is not downloadable (cloud sessions).
  use: { trace: "retain-on-failure", reducedMotion: "reduce", ...(process.env.PW_CHROMIUM_PATH ? { launchOptions: { executablePath: process.env.PW_CHROMIUM_PATH } } : {}) },
  projects: [
    ...(wantMock
      ? [
          {
            name: "desktop",
            testIgnore: /(live|contract)\.spec\.ts/,
            use: { ...desktop, baseURL: `http://localhost:${MOCK_PORT}` },
          },
          {
            name: "phone",
            testMatch: /(responsive|screenshots)\.spec\.ts/,
            use: { ...devices["Pixel 7"], baseURL: `http://localhost:${MOCK_PORT}` },
          },
        ]
      : []),
    ...(wantLive
      ? [
          {
            name: "live",
            // The same demo walk and what-if spec as mock mode, plus the live-only checks and the adapter contract tests.
            testMatch: /(demo|whatif|alerts|contract|live|chat)\.spec\.ts/,
            use: { ...desktop, baseURL: `http://localhost:${LIVE_PORT}` },
          },
        ]
      : []),
  ],
  webServer: [
    ...(wantMock
      ? [
          {
            command: `pnpm build && pnpm start -p ${MOCK_PORT}`,
            url: `http://localhost:${MOCK_PORT}`,
            timeout: 240_000,
            reuseExistingServer: !process.env.CI,
            env: {
              NEXT_PUBLIC_API_MODE: "mock",
              NEXT_PUBLIC_MOCK_LATENCY_MS: "10",
              NEXT_DIST_DIR: ".next-e2e-mock",
            },
          },
        ]
      : []),
    ...(wantLive
      ? [
          {
            // Memory store: nothing touches Supabase or disk. LLM_MODE=cache replays recorded outputs, so no network.
            command: `uv run uvicorn app.main:app --port ${API_PORT}`,
            cwd: "../../services/api",
            url: `http://localhost:${API_PORT}/health`,
            timeout: 120_000,
            // A server already on :8000 could hold state from a previous run or point at a real database.
            reuseExistingServer: false,
            env: { TERMSLEDGER_NO_DOTENV: "1", DATABASE_URL: "memory", LLM_MODE: "cache", CORS_ORIGINS: `http://localhost:${LIVE_PORT}` },
          },
          {
            command: `pnpm build && pnpm start -p ${LIVE_PORT}`,
            url: `http://localhost:${LIVE_PORT}`,
            timeout: 240_000,
            reuseExistingServer: false,
            env: {
              NEXT_PUBLIC_API_MODE: "live",
              NEXT_PUBLIC_API_URL: `http://localhost:${API_PORT}`,
              NEXT_DIST_DIR: ".next-e2e-live",
            },
          },
        ]
      : []),
  ],
});
