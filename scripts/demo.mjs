#!/usr/bin/env node
// The demo in one command, on Windows (PowerShell or cmd), macOS and Linux. Node only, no packages.
//
//   pnpm demo                      API on :8000 + web app on :3000 against it (live mode, owner sign-in prefilled)
//   pnpm demo:blank                the same, the API opening on a new business with no books (the setup wizard)
//   pnpm demo:mock                 the web app alone on the recorded mocks (no API, no Python)
//   pnpm demo:keep                 like pnpm demo, but the books live in .demo-data/flow-demo.db and survive a restart
//   pnpm demo:keep --fresh         the same, starting from new demo books (deletes that file first)
//   pnpm demo:keep --data .demo-data/other.db   the same, with the books in another file (the default file is left alone)
//   pnpm demo --web-port 3141 --api-port 8041   other ports (the API is told to allow the web origin)
//
// The API runs with the environment of scripts/dev-api.sh: in-memory books (DATABASE_URL=memory), the repo-root .env ignored
// (TERMSLEDGER_NO_DOTENV=1; it points at a hosted database), the demo credentials, cached LLM outputs and every feature flag.
// --keep changes only DATABASE_URL, to a local SQLite file (gitignored). The API seeds the demo books into an empty file on the
// first start and opens what the file holds on every later start (app/api/runtime.py: it never reseeds or deletes stored books).
// It checks both ports first and stops if one is taken (it never stops another program). Ctrl+C stops both servers.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const API_DIR = path.join(ROOT, "services", "api");
const WEB_DIR = path.join(ROOT, "apps", "web");
const NEXT_BIN = path.join(WEB_DIR, "node_modules", "next", "dist", "bin", "next");
const IS_WIN = process.platform === "win32";
const DEFAULT_KEEP_DB = path.join(ROOT, ".demo-data", "flow-demo.db");

const USAGE = `usage: node scripts/demo.mjs [--api-port 8000] [--web-port 3000] [--blank | --mock] [--keep [--fresh] [--data FILE]] [--live-llm]
  --api-port N  port for the API (default 8000)
  --web-port N  port for the web app (default 3000)
  --blank       open on a new business with no books (DEMO_SCENARIO=blank), so the setup wizard can open new books
  --mock        the web app alone on the recorded mocks; no API, no Python needed
  --keep        keep the books in a local file (.demo-data/flow-demo.db): uploads, confirmations and the clock survive a restart
  --fresh       with --keep: delete that file first and start from new demo books (new blank books with --blank)
  --data FILE   with --keep: keep the books in FILE instead (relative to the repository root; default .demo-data/flow-demo.db)
  --live-llm    call the model provider live (LLM_MODE=live) instead of the cached outputs: Ask FLOW's router answers the questions
                the built-in answers miss, and new documents and buyer messages are read by the model. Needs DEEPSEEK_API_KEY (or
                ANTHROPIC_API_KEY) set in this shell; .env is never read. Costs money per call; text is redacted before it leaves.`;

function say(line) {
  console.log(`[demo] ${line}`);
}

function fail(line) {
  console.error(`[demo] ${line}`);
  process.exit(1);
}

function parseArgs(argv) {
  const opts = { apiPort: 8000, webPort: 3000, blank: false, mock: false, keep: false, fresh: false, data: null, liveLlm: false };
  const port = (name, value) => {
    const n = Number(value);
    if (!Number.isInteger(n) || n < 1 || n > 65535) fail(`${name} needs a port number between 1 and 65535, not "${value ?? ""}".`);
    return n;
  };
  for (let i = 0; i < argv.length; i++) {
    const [flag, inline] = argv[i].split("=", 2);
    const value = () => (inline !== undefined ? inline : argv[++i]);
    if (flag === "--") continue; // `pnpm demo -- --web-port 3141` passes the separator through
    else if (flag === "--api-port") opts.apiPort = port(flag, value());
    else if (flag === "--web-port") opts.webPort = port(flag, value());
    else if (flag === "--blank") opts.blank = true;
    else if (flag === "--mock") opts.mock = true;
    else if (flag === "--keep") opts.keep = true;
    else if (flag === "--fresh") opts.fresh = true;
    else if (flag === "--live-llm") opts.liveLlm = true;
    else if (flag === "--data") {
      const v = value();
      if (!v || v.startsWith("--")) fail(`--data needs a file path, not "${v ?? ""}".`);
      opts.data = path.resolve(ROOT, v);
      // --fresh deletes this file: keep it to a .db file inside .demo-data/, never a path elsewhere on the machine
      const dir = path.resolve(ROOT, ".demo-data");
      if (path.relative(dir, opts.data).startsWith("..") || path.isAbsolute(path.relative(dir, opts.data)) || !opts.data.endsWith(".db"))
        fail(`--data must name a .db file inside .demo-data/ (got "${v}").`);
    }
    else if (flag === "--help" || flag === "-h") {
      console.log(USAGE);
      process.exit(0);
    } else fail(`unknown option "${argv[i]}".\n${USAGE}`);
  }
  if (opts.blank && opts.mock) fail("--blank needs the API, and --mock runs without it: pick one.");
  if (opts.liveLlm && opts.mock) fail("--live-llm calls the model from the API, and --mock runs without it: pick one.");
  if (opts.keep && opts.mock) fail("--keep keeps the API's books, and --mock runs without the API (its answers are recorded): pick one.");
  if (opts.fresh && !opts.keep) fail("--fresh starts the kept books again, so it only goes with --keep (pnpm demo:keep --fresh).");
  if (opts.data && !opts.keep) fail("--data names the file the kept books live in, so it only goes with --keep (pnpm demo:keep --data FILE).");
  opts.keepDb = opts.data ?? DEFAULT_KEEP_DB;
  if (!opts.mock && opts.apiPort === opts.webPort) fail(`the API and the web app cannot share port ${opts.apiPort}.`);
  return opts;
}

/** True when the command runs (`uv --version`, `pnpm --version`). pnpm is a .cmd shim on Windows, so it needs the shell there. */
function hasCommand(cmd) {
  const r = spawnSync(cmd, ["--version"], { stdio: "ignore", shell: IS_WIN && cmd !== "uv" });
  return !r.error && r.status === 0;
}

function checkTools(opts) {
  if (!existsSync(NEXT_BIN)) {
    if (!hasCommand("pnpm")) {
      fail("pnpm is not installed. Install it (npm install -g pnpm), then run `pnpm install` in apps/web, then try again.");
    }
    fail("the web app's packages are not installed. Run `pnpm install` in apps/web (cd apps/web; pnpm install), then try again.");
  }
  if (!opts.mock && !hasCommand("uv")) {
    fail(
      "uv (the Python runner for the API) is not installed or not on PATH. Install it from https://docs.astral.sh/uv/getting-started/installation/ " +
        "(PowerShell: powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"), open a new terminal, " +
        "and try again. Or run the web app alone on the recorded mocks: pnpm demo:mock",
    );
  }
}

/** A SQLAlchemy URL for an absolute file path: sqlite:///C:/x/y.db on Windows, sqlite:////home/x/y.db on macOS and Linux. */
function sqliteUrl(file) {
  return `sqlite:///${path.resolve(file).replace(/\\/g, "/")}`;
}

/** --keep: make the folder and, with --fresh, delete the file (and SQLite's companion files) so the API seeds new books. */
function prepareKeep(opts) {
  mkdirSync(path.dirname(opts.keepDb), { recursive: true });
  if (opts.fresh) {
    for (const suffix of ["", "-journal", "-wal", "-shm"]) {
      try {
        rmSync(opts.keepDb + suffix, { force: true });
      } catch (err) {
        fail(`could not delete ${opts.keepDb + suffix} (${err.code ?? err.message}). Is another demo still running on it? Stop it first.`);
      }
    }
  }
  say(`keeping the books in ${opts.keepDb}`);
  say(
    existsSync(opts.keepDb)
      ? "  opening the books it holds (nothing is reseeded). To start again from new books: pnpm demo:keep --fresh"
      : `  the file is new: the API seeds ${opts.blank ? "blank books" : "the demo books"} into it, and later starts keep what you do.`,
  );
  return sqliteUrl(opts.keepDb);
}

/** Does something answer on this port (IPv4 or IPv6 loopback)? */
function answers(host, port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host, port });
    const done = (result) => {
      socket.destroy();
      resolve(result);
    };
    socket.setTimeout(700, () => done(false));
    socket.once("connect", () => done(true));
    socket.once("error", () => done(false));
  });
}

/** Can we listen on this port? Returns null when free, else the error code (EADDRINUSE, or EACCES for a port Windows reserves). */
function canListen(port, host) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.once("error", (err) => resolve(err.code ?? "ERROR"));
    server.listen({ port, host, exclusive: true }, () => server.close(() => resolve(null)));
  });
}

async function checkPort(port, what, flag, suggestion) {
  const taken = (await answers("127.0.0.1", port)) || (await answers("::1", port));
  const code = taken ? "EADDRINUSE" : ((await canListen(port, "127.0.0.1")) ?? (await canListen(port, undefined)));
  if (!code) return;
  const reason = code === "EACCES" ? "is reserved by Windows or not allowed" : "is already in use by another program";
  fail(`port ${port} (${what}) ${reason}. Close that program, or start on another port: pnpm demo ${flag} ${suggestion}`);
}

const children = [];
let stopping = false;

function start(name, cmd, args, cwd, env) {
  const child = spawn(cmd, args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: ["ignore", "inherit", "inherit"],
    // POSIX: its own process group, so the whole tree (uv -> python, node -> next workers) stops together.
    detached: !IS_WIN,
    windowsHide: true,
  });
  child.once("error", (err) => {
    if (!stopping) shutdown(1, `could not start the ${name}: ${err.message}`);
  });
  child.once("exit", (code, signal) => {
    child.exited = true;
    // Ctrl+C reaches the children too (Windows exit code 0xC000013A, POSIX 130 or SIGINT): that is a normal stop.
    if (signal === "SIGINT" || code === 130 || code === 3221225786) return shutdown(0, "stopping the demo.");
    if (!stopping) shutdown(1, `the ${name} stopped (${signal ?? `exit code ${code}`}). Its messages are above.`);
  });
  children.push(child);
  return child;
}

/** Stops only the processes this script started, by PID (and their children). Never by program name. */
function stopChild(child) {
  if (!child.pid || child.exited) return;
  if (IS_WIN) {
    spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
  } else {
    try {
      process.kill(-child.pid, "SIGTERM");
    } catch {
      /* already gone */
    }
  }
}

function shutdown(code, message) {
  if (stopping) return;
  stopping = true;
  if (message) (code ? console.error : console.log)(`[demo] ${message}`);
  for (const child of children) stopChild(child);
  if (!IS_WIN) {
    // A last SIGKILL for anything that ignored SIGTERM.
    setTimeout(() => {
      for (const child of children) {
        try {
          if (child.pid && !child.exited) process.kill(-child.pid, "SIGKILL");
        } catch {
          /* already gone */
        }
      }
      process.exit(code);
    }, 1500).unref();
    setTimeout(() => process.exit(code), 1600);
  } else {
    process.exit(code);
  }
}

for (const sig of ["SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"]) {
  try {
    process.on(sig, () => shutdown(0, "stopping the demo."));
  } catch {
    /* signal not supported on this platform */
  }
}

async function waitFor(url, what, seconds, child) {
  const deadline = Date.now() + seconds * 1000;
  while (Date.now() < deadline) {
    if (stopping || child.exited) return false;
    try {
      await fetch(url, { signal: AbortSignal.timeout(10000) });
      return true; // any HTTP answer means the server is up
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  shutdown(1, `the ${what} did not answer at ${url} within ${seconds} s. Its messages are above.`);
  return false;
}

/**
 * Reads the price curve and BUYER-1's envelope (with its table) once, in the background, while the web app compiles: the API caches
 * both by the books, so the owner's first visit to Cash & funding and to a deal's Cash impact is a cache hit instead of a 17 s
 * sweep. Read-only; a failure (a blank start has no BUYER-1) is ignored. The API repeats it after each reset and setup.
 */
function warmStrategy(apiPort) {
  const headers = { "X-Owner-Token": "demo-owner-token" };
  const base = `http://127.0.0.1:${apiPort}`;
  for (const path of ["/cash/price-curve?lang=en", "/buyers/BUYER-1/envelope?lang=en&zone=1"]) {
    fetch(`${base}${path}`, { headers, signal: AbortSignal.timeout(300_000) }).catch(() => {});
  }
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  checkTools(opts);

  await checkPort(opts.webPort, "web app", "--web-port", opts.webPort === 3141 ? 3142 : 3141);
  if (!opts.mock) await checkPort(opts.apiPort, "API", "--api-port", opts.apiPort === 8041 ? 8042 : 8041);

  const webOrigin = `http://localhost:${opts.webPort}`;
  const apiOrigin = `http://localhost:${opts.apiPort}`;

  // --live-llm: the key comes from this shell only (the API never reads .env here); DeepSeek first when its key is set.
  const llm = { LLM_MODE: "cache" };
  if (opts.liveLlm) {
    const deepseek = Boolean(process.env.DEEPSEEK_API_KEY), claude = Boolean(process.env.ANTHROPIC_API_KEY);
    if (!deepseek && !claude)
      fail("--live-llm needs DEEPSEEK_API_KEY or ANTHROPIC_API_KEY set in this shell (PowerShell: $env:DEEPSEEK_API_KEY = \"...\"). .env is not read.");
    // redaction is forced on and the raw mode off, whatever this shell says: the line below promises it
    Object.assign(llm, { LLM_MODE: "live", LLM_PRIMARY: process.env.LLM_PRIMARY ?? (deepseek ? "deepseek" : "claude"), LLM_REDACT: "1", LLM_LIVE_RAW: "0" });
    say(`live model calls ON (${llm.LLM_PRIMARY}): each unanswered question, new document or buyer message is a paid call; text is redacted first.`);
  }

  if (!opts.mock) {
    const databaseUrl = opts.keep ? prepareKeep(opts) : "memory";
    const books = opts.keep ? `books kept in ${path.relative(ROOT, opts.keepDb)}` : "in-memory books";
    say(`starting the API on ${apiOrigin} (${books}, demo credentials, ${opts.liveLlm ? "LIVE model calls" : "cached LLM outputs"}${opts.blank ? ", blank books" : ""}) ...`);
    const api = start(
      "API",
      "uv",
      ["run", "--project", API_DIR, "--directory", API_DIR, "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(opts.apiPort)],
      API_DIR,
      {
        // Exactly scripts/dev-api.sh: never the repo-root .env, never a real database, never a live LLM unless --live-llm.
        TERMSLEDGER_NO_DOTENV: "1",
        DATABASE_URL: databaseUrl, // "memory", or with --keep the local SQLite file (never a hosted database)
        DEMO_MODE: "1",
        ...llm,
        PYTHONUTF8: "1",
        SKIP_PERF_BENCH: "1",
        FEATURE_ENVELOPE: "1",
        FEATURE_PRICE_CURVE: "1",
        FEATURE_COLLECTIONS_WORTH: "1",
        FEATURE_EXPOSURE: "1",
        FEATURE_CAPEX_CONTRACTS: "1", // the buy side (ADR-0013, certified): the Capex hub shows Your purchases and Deals its Buying card
        FEATURE_CONTRACT_TERMS: "1", // ADR-0014: a confirmed customer contract can set up its repeating invoice (owner, Tier 2)
        FEATURE_ASK_ROUTER: "1", // ADR-0015: the model routes an unanswered owner question to read-only tools (live LLM mode only)
        // After a demo reset or setup, the API reads the price curve and BUYER-1's envelope once in the background, so the first
        // visit is a cache hit (app/api/strategy_warm.py); warmStrategy() below does the same for the books it starts with.
        DEMO_WARM_STRATEGY: "1",
        CORS_ORIGINS: `${webOrigin},http://127.0.0.1:${opts.webPort}`,
        ...(opts.blank ? { DEMO_SCENARIO: "blank" } : {}),
      },
    );
    // The first run installs the API's Python packages, so allow a few minutes.
    if (!(await waitFor(`http://127.0.0.1:${opts.apiPort}/health`, "API", 300, api))) return;
    say(`API ready on ${apiOrigin}.`);
    warmStrategy(opts.apiPort);
  }

  say(`starting the web app on ${webOrigin} (${opts.mock ? "mock mode, recorded answers" : `live mode against ${apiOrigin}`}) ...`);
  const web = start("web app", process.execPath, [NEXT_BIN, "dev", "-p", String(opts.webPort)], WEB_DIR, {
    ...(opts.mock
      ? { NEXT_PUBLIC_API_MODE: "mock" }
      : { NEXT_PUBLIC_API_MODE: "live", NEXT_PUBLIC_API_URL: apiOrigin, NEXT_PUBLIC_DEMO: "1" }),
    // The strategy answers the API above switches on: the price of earlier cash on Cash & funding and the Safe Deal Envelope on a
    // deal's Cash impact ("The most you can give", "What you could answer instead"). Read-only; the mock serves their recordings.
    // The envelope's first read of a set of books is slow (about 17 s on the demo books), so the API reads it once in the background
    // after each reset and setup (DEMO_WARM_STRATEGY above). The pilot journal stays off (NEXT_PUBLIC_PILOT_JOURNAL, the pilot's
    // record of real owners, with FEATURE_PILOT_JOURNAL off). See apps/web/lib/config.ts.
    NEXT_PUBLIC_STRATEGY_MVP: "1",
    NEXT_PUBLIC_STRATEGY_ENVELOPE: "1",
    // Its own build folder: it never clashes with a `pnpm dev` already running in apps/web, nor mixes mock and live builds.
    NEXT_DIST_DIR: opts.mock ? ".next-demo-mock" : ".next-demo",
  });
  // The first page compiles on the first request, which this also does, so the browser opens on a warm page.
  if (!(await waitFor(`${webOrigin}/`, "web app", 300, web))) return;
  say("");
  say(`Ready. Open ${webOrigin} in your browser.${opts.mock ? "" : " Owner token: demo-owner-token (prefilled)."}`);
  if (opts.keep) say(`Your changes are kept in ${opts.keepDb}. To start again from new books: pnpm demo:keep --fresh`);
  say("Press Ctrl+C here to stop.");
}

main().catch((err) => shutdown(1, `unexpected error: ${err?.stack ?? err}`));
