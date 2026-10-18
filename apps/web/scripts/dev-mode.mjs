#!/usr/bin/env node
// `pnpm dev:mock` / `pnpm dev:live` on every shell (PowerShell and cmd cannot set variables inline as `NAME=value next dev`).
// Usage: node scripts/dev-mode.mjs mock|live [next dev options, e.g. -p 3141]
// live: NEXT_PUBLIC_API_URL defaults to http://localhost:8000; set it in the shell to point at another API. The API must allow
// the web origin (CORS_ORIGINS). For both servers in one command, use `pnpm demo` (scripts/demo.mjs at the repository root).
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const NEXT_BIN = path.join(WEB_DIR, "node_modules", "next", "dist", "bin", "next");
const [mode, ...nextArgs] = process.argv.slice(2);

if (mode !== "mock" && mode !== "live") {
  console.error("usage: node scripts/dev-mode.mjs mock|live [next dev options]");
  process.exit(2);
}
if (!existsSync(NEXT_BIN)) {
  console.error("The web app's packages are not installed. Run `pnpm install` in apps/web, then try again.");
  process.exit(1);
}

const env =
  mode === "mock"
    ? { NEXT_PUBLIC_API_MODE: "mock" }
    : {
        NEXT_PUBLIC_API_MODE: "live",
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
        NEXT_PUBLIC_DEMO: "1",
        // The strategy surfaces, as `pnpm demo` builds them (the price of earlier cash); the API needs FEATURE_PRICE_CURVE (and
        // FEATURE_COLLECTIONS_WORTH for the receivables fallback). The envelope and the pilot journal keep their own flags, off here
        // (NEXT_PUBLIC_STRATEGY_ENVELOPE, NEXT_PUBLIC_PILOT_JOURNAL; lib/config.ts).
        NEXT_PUBLIC_STRATEGY_MVP: "1",
      };

const child = spawn(process.execPath, [NEXT_BIN, "dev", ...nextArgs], { cwd: WEB_DIR, stdio: "inherit", env: { ...process.env, ...env } });
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  try {
    process.on(sig, () => child.kill(sig));
  } catch {
    /* signal not supported on this platform */
  }
}
child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
