#!/usr/bin/env node
// Records the demo videos: the app walked from empty books (apps/web/e2e/video), at 1080p, one cut per run.
//
//   pnpm demo:video                      the 5-minute cut (flow-demo-5min, at most 4:50): the competition's video
//   pnpm demo:video --cut full           the full tour (flow-full-tour): every scene
//   pnpm demo:video --keep-servers       leave the demo running afterwards (stop it with Ctrl+C)
//
// 1. Starts `node scripts/demo.mjs [--blank] --keep --data .demo-data/video.db --fresh --api-port 8090 --web-port 3090` (live mode, the
//    books in the recorder's own SQLite file, started fresh; cached LLM readings, no network, no key) and waits for its "Ready" line. The
//    owner's kept demo books (.demo-data/flow-demo.db) are never touched. --books blank (the default) or golden picks the books it starts
//    on; a cut switches books between its takes itself (POST /demo/reset behind a title card), so one cut is one continuous file.
// 2. Opens every page once so the dev server has compiled it before the camera rolls.
// 3. Runs the cut's test of the `video` Playwright project headless (E2E_TARGET=video; never part of the mock or live suites).
// 4. Copies the recording to docs/deliverables/video/<cut name>.webm, keeps its chapter timings in <cut name>.chapters.json and rewrites
//    docs/deliverables/video/README.md from every cut recorded so far, with key frames in docs/deliverables/video/frames.
// 5. Stops only what it started, by PID tree (taskkill /T on Windows, the process group elsewhere). Never by program name.
import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const WEB_DIR = path.join(ROOT, "apps", "web");
const OUT_DIR = path.join(ROOT, "docs", "deliverables", "video");
const FRAMES_DIR = path.join(OUT_DIR, "frames");
const RESULTS = path.join(WEB_DIR, "test-results", "video");
const PW_CLI = path.join(WEB_DIR, "node_modules", "@playwright", "test", "cli.js");
const API_PORT = 8090;
const WEB_PORT = 3090;
const IS_WIN = process.platform === "win32";
const keepServers = process.argv.includes("--keep-servers");
/** The value after `--name` (or in `--name=value`), else the default. */
function option(name, fallback) {
  const i = process.argv.findIndex((x) => x === `--${name}` || x.startsWith(`--${name}=`));
  if (i < 0) return fallback;
  return process.argv[i].includes("=") ? process.argv[i].split("=")[1] : process.argv[i + 1];
}
const BOOKS = option("books", "blank");
if (!["blank", "golden"].includes(BOOKS)) {
  console.error(`[video] --books takes blank or golden, not "${BOOKS ?? ""}".`);
  process.exit(1);
}
/** The recorder's own kept books: never the owner's .demo-data/flow-demo.db. */
const VIDEO_DB = ".demo-data/video.db";
const CUTS = { "5min": "flow-demo-5min", full: "flow-full-tour" };
const cutArg = option("cut", "5min");
if (!Object.hasOwn(CUTS, cutArg ?? "")) {
  console.error(`[video] --cut takes 5min or full, not "${cutArg ?? ""}".`);
  process.exit(1);
}
const CUT_NAME = CUTS[cutArg];

const say = (line) => console.log(`[video] ${line}`);
let demo = null;
let stopping = false;

/** Stops the demo launcher and everything under it, by its PID (never by program name). */
function stopDemo() {
  if (!demo || demo.exitCode !== null || stopping) return;
  stopping = true;
  if (IS_WIN) spawnSync("taskkill", ["/PID", String(demo.pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
  else {
    try {
      process.kill(-demo.pid, "SIGTERM");
    } catch {
      /* already gone */
    }
  }
}

function fail(message) {
  console.error(`[video] ${message}`);
  stopDemo();
  process.exit(1);
}

for (const sig of ["SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"]) {
  try {
    process.on(sig, () => {
      stopDemo();
      process.exit(130);
    });
  } catch {
    /* signal not supported here */
  }
}
process.on("exit", () => {
  if (!keepServers) stopDemo();
});

/** Starts the demo on blank books and resolves once it prints "Ready". */
function startDemo() {
  return new Promise((resolve, reject) => {
    const args = ["scripts/demo.mjs", ...(BOOKS === "blank" ? ["--blank"] : []), "--keep", "--data", VIDEO_DB, "--fresh", "--api-port", String(API_PORT), "--web-port", String(WEB_PORT)];
    say(`starting: node ${args.join(" ")}`);
    demo = spawn(process.execPath, args, { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"], detached: !IS_WIN, windowsHide: true });
    const timer = setTimeout(() => reject(new Error("the demo did not print Ready within 6 minutes")), 6 * 60_000);
    // The demo's own lines are shown until it is ready, then only read (so they never mix with the recording's report).
    let ready = false;
    createInterface({ input: demo.stdout }).on("line", (line) => {
      if (!ready) console.log(`  | ${line}`);
      if (!ready && /\[demo\] Ready\./.test(line)) {
        ready = true;
        clearTimeout(timer);
        resolve();
      }
    });
    createInterface({ input: demo.stderr }).on("line", (line) => {
      if (!ready) console.error(`  | ${line}`);
    });
    demo.once("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`the demo stopped before it was ready (exit code ${code}); its messages are above`));
    });
  });
}

/** Opens each page once: `next dev` compiles a route on its first request, so the recording never waits on a compile. */
async function warmUp() {
  const pages = ["/", "/welcome", "/setup", "/setup?step=1", "/documents", "/deals", "/chat", "/cash", "/capex", "/receivables", "/activity", "/evidence", "/approvals", "/customers/BUYER-1"];
  for (const p of pages) {
    const started = Date.now();
    try {
      await fetch(`http://127.0.0.1:${WEB_PORT}${p}`, { signal: AbortSignal.timeout(180_000) });
    } catch (err) {
      say(`warm-up of ${p} failed (${err?.message ?? err}); the recording will compile it`);
    }
    say(`warmed ${p} in ${((Date.now() - started) / 1000).toFixed(1)} s`);
  }
}

function runSpec() {
  rmSync(RESULTS, { recursive: true, force: true });
  if (existsSync(FRAMES_DIR)) for (const f of readdirSync(FRAMES_DIR)) if (f.startsWith(`${cutArg}-`)) rmSync(path.join(FRAMES_DIR, f));
  const env = {
    ...process.env,
    E2E_TARGET: "video",
    VIDEO_WEB_URL: `http://localhost:${WEB_PORT}`,
    VIDEO_API_URL: `http://localhost:${API_PORT}`,
    VIDEO_FRAMES_DIR: FRAMES_DIR,
  };
  say(`recording ${CUT_NAME} (headless, 1920×1080) ...`);
  const r = spawnSync(process.execPath, [PW_CLI, "test", "--project=video", "--reporter=list", `--grep=${CUT_NAME}`, `--output=${RESULTS}`], { cwd: WEB_DIR, env, stdio: "inherit" });
  return r.status ?? 1;
}

function find(dir, test) {
  if (!existsSync(dir)) return [];
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) out.push(...find(p, test));
    else if (test(name)) out.push(p);
  }
  return out;
}

const stamp = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** What each scene of scenes.ts shows, for scenes that do not say it themselves (`about`). */
const SCENES = {
  "sign-in": "the landing page, then the owner sign-in with the demo build's pre-filled token. Empty books: Home cannot answer yet.",
  setup:
    "the six-step setup wizard on blank books. Lingnan Homeware Manufacturing Co., Ltd.: cash ¥400,000; a ¥150,000 credit line at 6.4% (Pearl River Commercial Bank) and ¥350,000 of invoice financing; Foshan Home Retail Co. with an open ¥420,000 invoice on 45-day terms and a contract invoicing ¥420,000 every 30 days; Dongguan Office Supplies Ltd. with an open ¥180,000 invoice; payroll ¥340,000 every month and a ¥120,000 supplier payment; a ¥300,000 minimum and the default limits. The review's first forecast, then the owner signs and opens the books.",
  "home-gap": "the cash forecast, the gap before payroll and FLOW's funding plan (not approved yet).",
  "attach-deal": "Foshan's supply agreement (PDF) read, the deal at a glance, each term beside its clause, confirmed.",
  "wrong-company": "the same contract filed under Dongguan is blocked (it names other companies), filed again under Foshan in one press, and the duplicate reading rejected.",
  "new-customer": "Shunde Kitchen Supply Co. added from the upload form.",
  "contract-to-forecast": "Dongguan's new supply agreement confirmed, then “Set up in my books” with the forecast before and after, confirmed by the owner (Tier 2); Home's 120-day forecast reflects it.",
  "lender-agreement": "the bank's credit-line agreement (PDF) confirmed and linked to the credit line.",
  "buyer-request": "Foshan asks for 60-day terms on its own keyed channel (the API's demo buyer key); FLOW's verdict and its counters side by side; Your agreements when Deals lists the confirmed contracts; in the full tour, Foshan's customer record.",
  "ask-flow": "“Are we safe?”, “What if Foshan pays 30 days late?” (the full tour adds “Who owes us the most?” and “Can we clear all our debts?”), then “我们安全吗？” with the app in Chinese; the full tour ends on a new conversation.",
  "fund-gap": "the plan run from Cash & funding (all Tier 1 on these books; a Tier 2 step would be approved in Approvals); Home holds the reserve.",
  "cash-funding": "each funding source, how much is drawn and what is left.",
  capex: "the capex check on a ¥600k machine: NPV, payback and which financing holds every covenant and the reserve.",
  receivables: "who owes what, when it is due, and what is left once financing is repaid.",
  activity: "the hash-chained activity record in the owner's words, then the evidence view (each entry with its hash and the one before).",
  end: "“FLOW · supplier-owned working-capital agent · every figure from the books, every action logged”.",
};

function cutSection(info) {
  const file = `${info.name}.webm`;
  const bytes = existsSync(path.join(OUT_DIR, file)) ? statSync(path.join(OUT_DIR, file)).size : 0;
  const big = bytes > 50e6;
  const rows = info.chapters.map((c) => `| ${c.n} | ${stamp(c.at)} | ${c.title} | ${c.about ?? SCENES[c.id] ?? ""} |`).join("\n");
  const frames = existsSync(FRAMES_DIR) ? readdirSync(FRAMES_DIR).filter((f) => f.startsWith(`${info.cut}-`) && f.endsWith(".png")).sort() : [];
  const problems = info.problems.length ? info.problems.map((p) => `- Chapter ${p.chapter} (${p.title}): ${p.error}`).join("\n") : "None: every chapter ran to its end.";
  return `## ${info.name} (\`--cut ${info.cut}\`)

\`${file}\`: ${stamp(info.total_seconds)} long, ${(bytes / 1e6).toFixed(1)} MB${big ? " (over 50 MB: ignored by git and kept on the recording machine)" : ""}, recorded ${info.recorded ?? "?"}.

| # | Starts at | Chapter | What it shows |
|---|-----------|---------|---------------|
${rows}

Key frames: ${frames.map((f) => `[${f}](frames/${f})`).join(", ") || "none written"}.

Problems seen while recording: ${problems}
`;
}

function writeReadme() {
  const cuts = Object.values(CUTS)
    .map((name) => path.join(OUT_DIR, `${name}.chapters.json`))
    .filter((f) => existsSync(f))
    .map((f) => JSON.parse(readFileSync(f, "utf8")));
  const text = `# FLOW demo videos

The app walked from empty books, recorded at 1920×1080 against the real API in live mode (cached LLM readings, no network, no key,
synthetic companies). Two cuts of the same scenes (\`apps/web/e2e/video/scenes.ts\`, one per feature or step):

- **flow-demo-5min**: the competition's video, at most 4:50: the strongest end-to-end story on the owner's own books.
- **flow-full-tour**: every scene at the full reading pace.

The timestamps come from the recording's own step timings (each chapter's start, measured from the start of the recording), so they move
with every re-recording; each cut's table is rewritten when that cut is recorded.

${cuts.map(cutSection).join("\n") || "No cut recorded yet.\n"}
## Notes from the walkthrough

- **Deals, "Your agreements" stays empty on these books (product bug).** A customer with a confirmed contract and open invoices but no
  negotiation (Foshan and Dongguan here) is neither "agreed" (\`isAgreed\` needs the "Terms negotiated" stage done) nor "invoices only"
  (\`hasInvoicesOnly\` needs no contract) in \`apps/web/components/deals/deal-summary.tsx\`, so confirming a customer's contract removes its
  row from Deals (a fix is in progress on fix/deals-contracts-upload). The Deals scene opens Your agreements whenever the page lists a
  confirmed contract.
- **A question typed in Chinese while the app is in English is answered in English.** The web sends the page's language with every chat
  message, and it overrides the API's own language detection, so the Ask FLOW scene switches the app to 中文 before asking “我们安全吗？”.
- **Why Dongguan has an open invoice in the setup.** With it, FLOW finds counters to Foshan's 60-day request inside the limits; without it
  (monthly payroll, no other receipts) FLOW finds no counter and recommends declining, and the deal shows no counters.
- **The buyer's request** arrives through the API's keyed buyer channel (\`POST /offers\` with the demo key for BUYER-1, Foshan, which is the
  first customer the setup enters) carrying the worked example EX01's message, whose reading is cached; the demo books are never loaded.

## Re-record

From the repository root, with the web app's packages installed (\`cd apps/web; pnpm install\`), \`uv\` on the PATH and Playwright's
Chromium installed (\`pnpm exec playwright install chromium\` in apps/web):

\`\`\`
pnpm demo:video              # flow-demo-5min
pnpm demo:video --cut full   # flow-full-tour
\`\`\`

Each run starts \`node scripts/demo.mjs --blank --keep --data .demo-data/video.db --fresh --api-port 8090 --web-port 3090\` (ports 8090
and 3090 must be free; \`--books golden\` starts on the demo books instead). The recorder keeps its books in its own file, so the owner's
kept demo books (\`.demo-data/flow-demo.db\`) are never touched. It warms every page, records the cut's test in
\`apps/web/e2e/video/walkthrough.spec.ts\` headless (Playwright project \`video\`, \`E2E_TARGET=video\`), writes this folder, and stops only
the processes it started. \`VIDEO_SLOWMO_MS\` (default 180) sets the pause after every browser action. A cut is a list of scenes and a pace
for the viewing pauses (\`CUTS\` in walkthrough.spec.ts). The mock and live suites never run the video spec.
`;
  writeFileSync(path.join(OUT_DIR, "README.md"), text);
}

async function main() {
  if (!existsSync(PW_CLI)) fail("Playwright is not installed: run `pnpm install` in apps/web first.");
  mkdirSync(OUT_DIR, { recursive: true });
  try {
    await startDemo();
  } catch (err) {
    fail(err.message);
  }
  await warmUp();
  const started = Date.now();
  const status = runSpec();
  say(`${CUT_NAME} finished with exit code ${status} after ${((Date.now() - started) / 1000).toFixed(0)} s`);
  const videos = find(RESULTS, (n) => n.endsWith(".webm"));
  const chapters = find(RESULTS, (n) => n === "chapters.json");
  if (!videos.length) fail(`no recording was written under ${RESULTS}`);
  const target = path.join(OUT_DIR, `${CUT_NAME}.webm`);
  copyFileSync(videos[0], target);
  const bytes = statSync(target).size;
  const info = chapters.length
    ? JSON.parse(readFileSync(chapters[0], "utf8"))
    : { cut: cutArg, name: CUT_NAME, total_seconds: 0, chapters: [], problems: [{ chapter: 0, title: "?", error: "chapters.json was not written" }] };
  info.recorded = new Date().toISOString().slice(0, 10);
  info.problems = info.problems.map((p) => ({ ...p, screenshot: path.basename(p.screenshot ?? "") }));
  writeFileSync(path.join(OUT_DIR, `${CUT_NAME}.chapters.json`), `${JSON.stringify(info, null, 2)}\n`);
  writeReadme();
  say(`video: ${target} (${(bytes / 1e6).toFixed(1)} MB, ${stamp(info.total_seconds)})`);
  for (const c of info.chapters) say(`  ${stamp(c.at)}  ${c.n}. ${c.title}`);
  for (const p of info.problems) say(`  problem in chapter ${p.chapter}: ${p.error}`);
  if (keepServers) say(`the demo is still running on http://localhost:${WEB_PORT}; press Ctrl+C to stop it.`);
  else stopDemo();
  if (status !== 0) process.exitCode = 1;
}

main().catch((err) => fail(`unexpected error: ${err?.stack ?? err}`));
