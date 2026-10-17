import { defineConfig, devices } from "@playwright/test";

/**
 * Two targets, both built and started by Playwright itself:
 *
 *   mock  Next.js in NEXT_PUBLIC_API_MODE=mock on :3100. No backend needed.
 *   live  FastAPI (uvicorn, in-memory store, recorded LLM cache, no Supabase) on :8000 plus Next.js in
 *         NEXT_PUBLIC_API_MODE=live on :3000. The demo walk is the same spec as in mock mode.
 *
 * The live web server uses :3000 (the API default CORS origin); E2E_LIVE_PORT moves it and tells the API to allow that origin.
 * E2E_STRATEGY=1 builds the web app with NEXT_PUBLIC_STRATEGY_MVP=1 (its own dist dir) and starts the live API with
 * FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1, so e2e/strategy.spec.ts and the screenshot walk see the strategy surfaces; unset,
 * the app is the default build and that spec skips.
 * E2E_REUSE_API=1 starts no API: the live project runs against one already listening on E2E_API_PORT (start it yourself, with
 * CORS_ORIGINS set to the live web origin). E2E_DATABASE_URL is the DATABASE_URL of the API this config starts (default `memory`,
 * e.g. sqlite:////absolute/path/e2e.db); it has no effect with E2E_REUSE_API=1, because then the API's own environment decides.
 * E2E_TARGET=mock|live|all (default all) chooses which servers start; `pnpm test:e2e:mock` and
 * `pnpm test:e2e:live` set it. Needs `uv` for the API and `pnpm exec playwright install chromium` once.
 * E2E_TARGET=video starts no server and adds only the `video` project (e2e/video/walkthrough.spec.ts, the recorded demo walkthrough):
 * `pnpm demo:video` at the root starts the demo on blank books and runs it. No other project ever runs e2e/video.
 */
const MOCK_PORT = Number(process.env.E2E_PORT ?? 3100);
const LIVE_PORT = Number(process.env.E2E_LIVE_PORT ?? 3000); // override when another program holds :3000; the API is then told to allow that origin
const API_PORT = Number(process.env.E2E_API_PORT ?? 8000); // override when another program holds :8000
// contract.spec.ts calls the live adapters from Node: they read the API address from this variable.
process.env.NEXT_PUBLIC_API_URL ??= `http://localhost:${API_PORT}`;
const target = process.env.E2E_TARGET ?? "all";
const wantMock = target === "all" || target === "mock";
const wantLive = target === "all" || target === "live";
const wantVideo = target === "video";
// The recorded walkthrough (e2e/video) is never part of the mock or live suites.
const VIDEO_DIR = /[\\/]video[\\/]/;
// E2E_REUSE_API=1: do not start the API; use the one already on E2E_API_PORT.
const reuseApi = process.env.E2E_REUSE_API === "1";
const databaseUrl = process.env.E2E_DATABASE_URL || "memory";

// The strategy MVP is a build-time flag on the web app and a runtime flag on the API; both follow E2E_STRATEGY.
const strategy = process.env.E2E_STRATEGY === "1";
const strategyWeb: Record<string, string> = strategy ? { NEXT_PUBLIC_STRATEGY_MVP: "1" } : {};
const strategyApi: Record<string, string> = strategy ? { FEATURE_ENVELOPE: "1", FEATURE_PRICE_CURVE: "1", FEATURE_COLLECTIONS_WORTH: "1" } : {};

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
            testIgnore: [/(live|contract|slow|home-v2-states)\.spec\.ts/, VIDEO_DIR],
            use: { ...desktop, baseURL: `http://localhost:${MOCK_PORT}` },
          },
          {
            name: "phone",
            testMatch: /(responsive|screenshots|strategy|a11y|deals-queue)\.spec\.ts/,
            testIgnore: VIDEO_DIR,
            use: { ...devices["Pixel 7"], baseURL: `http://localhost:${MOCK_PORT}` },
          },
        ]
      : []),
    ...(wantLive
      ? [
          {
            name: "live",
            // The same demo walk, what-if and document specs as mock mode, plus the live-only checks and the adapter contract tests.
            testMatch: /(demo|whatif|alerts|contract|live|chat|strategy|slow|lang|documents|contract-terms|slice-b|slice-b-round-two|accept-as-asked|home-v2-states|ask-header-live|activity|trust|tracker)\.spec\.ts/, // Deal tracker: tracker added; ADR-0014: contract-terms
            testIgnore: VIDEO_DIR,
            use: { ...desktop, baseURL: `http://localhost:${LIVE_PORT}` },
          },
        ]
      : []),
    ...(wantVideo
      ? [
          {
            // The demo walkthrough, recorded (scripts/record-demo-video.mjs): 1080p, every action slowed so a viewer can follow it, the app's own motion on.
            name: "video",
            testMatch: /video[\\/]walkthrough\.spec\.ts/,
            timeout: 25 * 60_000,
            use: {
              ...desktop,
              viewport: { width: 1920, height: 1080 },
              deviceScaleFactor: 1,
              baseURL: process.env.VIDEO_WEB_URL ?? "http://localhost:3090",
              video: { mode: "on" as const, size: { width: 1920, height: 1080 } },
              reducedMotion: "no-preference" as const,
              trace: "off" as const,
              // A step that cannot happen fails in seconds (the chapter is kept with a screenshot and the next one runs), never at the test's timeout.
              actionTimeout: 30_000,
              navigationTimeout: 60_000,
              launchOptions: {
                slowMo: Number(process.env.VIDEO_SLOWMO_MS ?? 180),
                ...(process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {}),
              },
            },
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
              NEXT_DIST_DIR: strategy ? ".next-e2e-mock-strategy" : ".next-e2e-mock",
              ...strategyWeb,
            },
          },
        ]
      : []),
    ...(wantLive
      ? [
          ...(reuseApi
            ? []
            : [
                {
                  // Memory store by default: nothing touches Supabase or disk. E2E_DATABASE_URL swaps in a SQLite file.
                  // LLM_MODE=cache replays recorded outputs, so no network.
                  command: `uv run uvicorn app.main:app --port ${API_PORT}`,
                  cwd: "../../services/api",
                  url: `http://localhost:${API_PORT}/health`,
                  timeout: 120_000,
                  // A server already on :8000 could hold state from a previous run or point at a real database.
                  reuseExistingServer: false,
                  // FEATURE_EXPOSURE: the Deals page is the decision queue once the open offer has its exposure read.
                  // DEMO_MODE=1: the live suite signs in with the published demo credentials (DEMO_MODE is off by default).
                  env: { TERMSLEDGER_NO_DOTENV: "1", DATABASE_URL: databaseUrl, LLM_MODE: "cache", DEMO_MODE: "1", CORS_ORIGINS: `http://localhost:${LIVE_PORT}`, FEATURE_EXPOSURE: "1", FEATURE_CONTRACT_TERMS: "1", ...strategyApi },
                },
              ]),
          {
            command: `pnpm build && pnpm start -p ${LIVE_PORT}`,
            url: `http://localhost:${LIVE_PORT}`,
            timeout: 240_000,
            reuseExistingServer: false,
            env: {
              NEXT_PUBLIC_API_MODE: "live",
              NEXT_PUBLIC_API_URL: `http://localhost:${API_PORT}`,
              // Every request gives up after 6 s in this build (20 s and 60 s in production), so e2e/slow.spec.ts can show the slow state quickly.
              NEXT_PUBLIC_REQUEST_TIMEOUT_MS: "6000",
              NEXT_DIST_DIR: strategy ? ".next-e2e-live-strategy" : ".next-e2e-live",
              ...strategyWeb,
            },
          },
        ]
      : []),
  ],
});
