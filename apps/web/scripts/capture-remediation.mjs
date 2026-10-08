#!/usr/bin/env node
/**
 * On-demand screenshot capture for the UX remediation (wayfinder map #65, Wave 8 part B). It is not part of any test run.
 *
 * It drives a LIVE stack through the real API, with the same walks as e2e/live.spec.ts (the day-34 walk with a full, half or no receipt,
 * the bound send, the cure, the refused approval) and e2e/demo.spec.ts (the six-scene story), and writes full-page PNGs at four widths:
 *
 *   desktop 1440x900, laptop 1366x768, tablet 820x1180, phone 412x915 (normal motion, English; Home and Approvals also in Chinese at 1440 and 412)
 *
 * into  <OUT>/{desktop,laptop,tablet,phone}/NN-<route>-<state>.png  with a manifest.json per width: route, state, width, viewport height,
 * page height in viewport heights, the y (document coordinates) of the top and bottom of the page's primary action (the first visible
 * brand-blue filled button or link in main, a dialog or the Demo stepper; document y for a full-page shot, viewport y for a modal's viewport shot; null when the state has none) and the head commit.
 *
 * Needs a running stack (it changes no product code and never edits a mock). From the repository root:
 *
 *   API (own port; the web origin must be allowed):
 *     cd services/api && TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 \
 *       FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 CORS_ORIGINS=http://localhost:3261 \
 *       uv run uvicorn app.main:app --port 8191
 *   Web (production build):
 *     cd apps/web && NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=http://localhost:8191 NEXT_PUBLIC_STRATEGY_MVP=1 pnpm build
 *     NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=http://localhost:8191 NEXT_PUBLIC_STRATEGY_MVP=1 pnpm exec next start -p 3261
 *   Capture:
 *     node apps/web/scripts/capture-remediation.mjs
 *
 * Variables: WEB (default http://localhost:3261), API (default http://localhost:8191), OUT (default docs/screenshots/ux-remediation-2026-10-10
 * under the repository root), WIDTHS (comma list of desktop,laptop,tablet,phone), ONLY (a substring: take only the shots whose name has it),
 * PW_CHROMIUM_PATH (a Chromium to use instead of Playwright's own).
 * It resets the API's books (POST /demo/reset) before every walk and at the end, so use a throwaway API.
 */
import { execSync } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../..");
const WEB = process.env.WEB ?? "http://localhost:3261";
const API = process.env.API ?? "http://localhost:8191";
const OUT = resolve(process.env.OUT ?? join(repo, "docs/screenshots/ux-remediation-2026-10-10"));
const ONLY = process.env.ONLY ?? "";
const TOKEN = "demo-owner-token";
const OWNER = { "X-Owner-Token": TOKEN };
const BANK = { "X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key" };
const STORY_STEPS = 11;

const ALL_WIDTHS = {
  desktop: { width: 1440, height: 900 },
  laptop: { width: 1366, height: 768 },
  tablet: { width: 820, height: 1180 },
  phone: { width: 412, height: 915, mobile: true },
};
const wanted = (process.env.WIDTHS ?? Object.keys(ALL_WIDTHS).join(",")).split(",").map((s) => s.trim());
const head = execSync("git rev-parse --short HEAD", { cwd: repo }).toString().trim();


/** The order of the shots in every folder: NN is the position here, so the same state has the same number at every width. */
const ORDER = [
  "home-day0",
  "home-day34-no-receipt-before-cure",
  "home-day34-no-receipt-residual",
  "deals-evaluated-day0",
  "deals-ask-flow-why-countering",
  "deals-agreed",
  "deals-day34-missed-no-receipt",
  "cash-day0",
  "cash-day34",
  "receivables-day34-half-receipt-chase-dialog",
  "receivables-day34-half-receipt-list",
  "activity-day34-after-cure",
  "approvals-pending-agreement-terms",
  "approvals-pending-funding-cure",
  "approvals-pending-funding-cure-full-receipt",
  "approvals-decided-with-quote",
  "approvals-refused-mandate-expired",
  "decisions-deal-record-agreed",
  "decisions-cure-record-settled",
  "demo-scene2-flow-decides",
  "demo-scene5-owner-approve-step",
  "demo-story-page-scene5",
  "home-day34-cure-pending-zh",
  "approvals-pending-funding-cure-zh",
];

// ---- the API, as the e2e specs call it ------------------------------------------------------------------------------------------------------

async function call(method, path, data, headers = OWNER) {
  const res = await fetch(`${API}${path}`, { method, headers: { "content-type": "application/json", ...headers }, body: data === undefined ? undefined : JSON.stringify(data) });
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${await res.text()}`);
  return res.json();
}
const post = (path, data, headers) => call("POST", path, data ?? {}, headers);
const get = (path, headers) => call("GET", path, undefined, headers);
const reset = () => post("/demo/reset", {});

/** Day 2: the buyer's receipt (all, half or none of what the server expected); then day 30 and day 34. */
async function dayTwoToDay34(receipt) {
  await post("/clock/advance", { to_day: 2 });
  if (receipt !== "none") {
    const recon = await get("/reconciliation");
    const promised = recon.reconciliation.promised[0];
    const mandate = await get("/mandate");
    await post(
      "/operations",
      {
        kind: "RECEIVE_PAYMENT",
        op_id: "shots-receipt-1",
        idempotency_key: "shots-receipt-1",
        mandate_version: mandate.mandate.version,
        requested_by: "SYSTEM",
        receivable_id: promised.receivable_id,
        amount_fen: receipt === "half" ? Math.floor(promised.expected_fen / 2) : promised.expected_fen,
        bank_reference: "SHOTS-RCPT-1",
      },
      BANK,
    );
  }
  await post("/clock/advance", { to_day: 30 });
  await post("/clock/advance", { to_day: 34 });
}

/** Reset, the EX01 deal sent bound to what was evaluated, then day 34 with the given receipt. */
async function walkToDay34(receipt) {
  await reset();
  const { offer } = await post("/offers", { fixture_id: "EX01_PACKAGE" });
  const verdict = await post(`/offers/${offer.offer_id}/evaluate`, { fixture_id: "EX01_PACKAGE" });
  const deal = await post(`/negotiate/${offer.offer_id}`, { buyer_profile: "cooperative", verdict_id: verdict.id, counter_id: verdict.counters[0].id, state_version: verdict.state_version });
  if (deal.outcome !== "DEAL") throw new Error(`the walk did not reach a deal: ${deal.outcome}`);
  await dayTwoToDay34(receipt);
  return offer.offer_id;
}

// ---- the browser ----------------------------------------------------------------------------------------------------------------------------

/** One signed-in page at the width, normal motion. `lang` sets the stored language before the page loads. */
async function openPage(browser, vp, lang = "en") {
  const context = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    deviceScaleFactor: 1,
    isMobile: !!vp.mobile,
    hasTouch: !!vp.mobile,
    reducedMotion: "no-preference",
  });
  await context.addInitScript(
    ([tok, l]) => {
      try {
        sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: tok }));
        localStorage.setItem("tl-lang", JSON.stringify({ lang: l }));
      } catch {
        /* storage unavailable */
      }
    },
    [TOKEN, lang],
  );
  const page = await context.newPage();
  page.setDefaultTimeout(20_000);
  const problems = [];
  page.on("pageerror", (e) => problems.push(String(e)));
  return { context, page, problems };
}

const tid = (page, id) => page.getByTestId(id);

/** The first visible brand-blue filled button or link in main, a dialog or the Demo stepper: the page's primary action, in document y. */
async function primaryOf(page, fullPage) {
  return page.evaluate((fullPage) => {
    const BRAND = "rgb(26, 95, 224)";
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
    };
    const sel = 'main button, main a, [role="dialog"] button, [role="dialog"] a, dialog[open] button, dialog[open] a, [aria-label="Guided demo"] button, [data-testid="home-review-primary"]';
    const found = Array.from(document.querySelectorAll(sel)).filter((el) => visible(el) && getComputedStyle(el).backgroundColor === BRAND);
    // A dialog's own primary wins over the page behind it.
    const inDialog = found.find((el) => el.closest('[role="dialog"], dialog[open]'));
    const el = inDialog ?? found[0];
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { label: (el.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 60), top: Math.round(r.top + (fullPage ? window.scrollY : 0)), bottom: Math.round(r.bottom + (fullPage ? window.scrollY : 0)), count: found.length };
  }, fullPage);
}

function makeShooter(name, vp) {
  const dir = join(OUT, name);
  if (!ONLY) rmSync(dir, { recursive: true, force: true }); // a partial run (ONLY) keeps the folder and writes manifest.only.json
  mkdirSync(dir, { recursive: true });
  const entries = [];
  /** `fullPage: false` is for a modal that is fixed to the viewport (the Ask FLOW panel). */
  async function shoot(page, _unused, route, state, { lang = "en", fullPage = true } = {}) {
    const key = `${route}-${state}`;
    const at = ORDER.indexOf(key);
    if (at < 0) throw new Error(`${key} is not in ORDER`);
    if (ONLY && !key.includes(ONLY)) return;
    const nn = String(at + 1).padStart(2, "0");
    await page.waitForLoadState("networkidle").catch(() => {});
    // A loading skeleton in the picture would be a lie about the finished page: wait for it to go, and say so in the manifest when it does not.
    const idle = () => !document.querySelector('.animate-pulse, [aria-busy="true"]');
    const settled = await page.waitForFunction(idle, undefined, { timeout: 10_000 }).then(() => true, () => false);
    if (fullPage) await page.evaluate(() => window.scrollTo(0, 0)); // a page scrolled by a click or an anchor would put its sticky header mid-image
    await page.waitForTimeout(700); // let the entrance motion settle
    const file = `${nn}-${route}-${state}.png`;
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    const primary = await primaryOf(page, fullPage);
    await page.screenshot({ path: join(dir, file), fullPage });
    entries.push({
      file,
      route,
      state,
      lang,
      url: page.url().replace(/^https?:\/\/[^/]+/, ""),
      width: vp.width,
      viewport_height: vp.height,
      page_height: height,
      page_height_in_viewports: Math.round((height / vp.height) * 100) / 100,
      full_page: fullPage,
      loading_skeleton_still_visible: !settled,
      primary_action_y_is: fullPage ? "document" : "viewport (the shot is the viewport, a modal is open)",
      primary_action: primary ? { label: primary.label, top: primary.top, bottom: primary.bottom, filled_actions_on_page: primary.count } : null,
      head,
    });
    console.log(`  ${name} ${file}  ${height}px (${Math.round((height / vp.height) * 10) / 10} screens)  primary ${primary ? `${primary.top}-${primary.bottom}` : "none"}`);
  }
  const finish = () => writeFileSync(join(dir, ONLY ? "manifest.only.json" : "manifest.json"), JSON.stringify({ width_name: name, width: vp.width, viewport_height: vp.height, head, captured_at: new Date().toISOString(), shots: entries.sort((a, b) => a.file.localeCompare(b.file)) }, null, 2));
  return { shoot, finish, entries };
}

// ---- the walks ------------------------------------------------------------------------------------------------------------------------------

async function home(page) {
  await page.goto(`${WEB}/`);
  await tid(page, "home-status").waitFor();
}

/** Opens the Foshan message on Deals and checks it against the limits. */
async function checkedDeal(page) {
  await page.goto(`${WEB}/deals`);
  await tid(page, "inbox-list").getByTestId("inbox-msg-EX01").click();
  await tid(page, "next-step").getByRole("button", { name: "Check against my limits" }).click();
  await tid(page, "deal-recommendation").waitFor();
  await page.waitForFunction(() => document.querySelector('[data-testid="deal-state-chip"]')?.getAttribute("data-state") === "RESPONSE_READY");
}

/** Home's cure: the first press opens the confirmation, the second sends the act; the approval link then opens Approvals. */
async function queueCure(page) {
  await home(page);
  const next = tid(page, "home-next-action");
  await next.waitFor();
  const open = next.locator('[data-testid^="fix-open-ALERT-RESERVE"]');
  const alertId = ((await open.getAttribute("data-testid")) ?? "").replace("fix-open-", "");
  await next.getByTestId(`fix-open-${alertId}`).click();
  await next.getByTestId(`fix-${alertId}`).click();
  await tid(page, `alert-approval-link-${alertId}`).click();
  await page.waitForURL(/\/approvals#approval-APR-/);
  const card = page.locator('[id^="approval-APR-"]').first();
  await card.waitFor();
  return { alertId, card };
}

async function scenarioDay0(browser, vp, S) {
  console.log("day 0: home, cash, the deal evaluated, Ask FLOW, the bound send, the record");
  await reset();
  const { context, page } = await openPage(browser, vp);
  await home(page);
  await S.shoot(page, "01", "home", "day0");
  await page.goto(`${WEB}/cash`);
  await tid(page, "cash-options-list").waitFor();
  await S.shoot(page, "07", "cash", "day0");
  await checkedDeal(page);
  await S.shoot(page, "02", "deals", "evaluated-day0");

  // Ask FLOW on the evaluated deal: the page's prompt, the answer and the echo line ("Discussing: ...").
  await tid(page, "chat-open").click();
  const panel = page.getByRole("dialog", { name: "Ask FLOW" });
  await panel.waitFor();
  await panel.getByTestId("prompt-page-counter").click();
  const answer = panel.getByTestId("chat-turn").last().getByTestId("chat-reply");
  await answer.waitFor();
  await panel.getByTestId("chat-discussing").waitFor();
  await S.shoot(page, "23", "deals", "ask-flow-why-countering", { fullPage: false });
  await page.keyboard.press("Escape");
  await panel.waitFor({ state: "hidden" });

  // The bound send (two presses), then the agreement.
  await tid(page, "deal-send").click();
  await tid(page, "deal-send-confirm").click();
  await page.waitForFunction(() => document.querySelector('[data-testid="deal-state-chip"]')?.getAttribute("data-state") === "AGREED");
  await S.shoot(page, "03", "deals", "agreed");

  const offerId = await page.evaluate(() => JSON.parse(sessionStorage.getItem("tl-demo-v3") ?? "{}").offerId);
  if (!offerId) throw new Error("no offer id in the session to open the deal record");
  await page.goto(`${WEB}/decisions/${encodeURIComponent(`deal:${offerId}`)}`);
  await tid(page, "record-state").waitFor();
  await S.shoot(page, "20", "decisions", "deal-record-agreed");
  await context.close();
}

async function scenarioNoReceipt(browser, vp, S) {
  console.log("day 34, no receipt: missed deal, the cure queued, approved, its quote, the record, the residual Home");
  // The deal is sent from the Deals page at day 0, as the owner does; then the clock and the bank feed move through the API.
  await reset();
  const { context, page } = await openPage(browser, vp);
  await checkedDeal(page);
  await tid(page, "deal-send").click();
  await tid(page, "deal-send-confirm").click();
  await page.waitForFunction(() => document.querySelector('[data-testid="deal-state-chip"]')?.getAttribute("data-state") === "AGREED");
  await dayTwoToDay34("none");
  await home(page);
  await S.shoot(page, "04", "home", "day34-no-receipt-before-cure");
  await page.goto(`${WEB}/deals`);
  await tid(page, "deal-state-chip").waitFor();
  await page.waitForFunction(() => document.querySelector('[data-testid="deal-state-chip"]')?.getAttribute("data-state") === "MISSED");
  await S.shoot(page, "05", "deals", "day34-missed-no-receipt");

  const { card } = await queueCure(page);
  await S.shoot(page, "14", "approvals", "pending-funding-cure");
  await card.getByRole("button", { name: "Approve" }).click();
  await card.locator('[data-testid^="approval-result-"]').waitFor();
  const quoted = card.locator('[data-testid^="approval-quoted-"] > summary');
  await quoted.click();
  await tid(card, "approval-quote-actual").waitFor();
  await S.shoot(page, "15", "approvals", "decided-with-quote");

  // The cash lands on day 37; the reserve is still short, so Home leaves the remaining task.
  await post("/clock/advance", { to_day: 38 });
  await home(page);
  await page.locator("#home-remaining").waitFor();
  await S.shoot(page, "06", "home", "day34-no-receipt-residual");
  await page.goto(`${WEB}/approvals`);
  await page.locator('[data-testid^="approval-record-"]').first().click();
  await page.waitForURL(/\/decisions\//);
  await tid(page, "record-state").waitFor();
  await S.shoot(page, "21", "decisions", "cure-record-settled");
  await context.close();
}

async function scenarioAgreement(browser, vp, S) {
  console.log("an agreement approval with its terms");
  await reset();
  const sent = await fetch(`${API}/nl`, {
    method: "POST",
    headers: { "content-type": "application/json", "X-Counterparty-Key": "demo-buyer-1-key" },
    body: JSON.stringify({ session_id: "shots-agreement", actor: "COUNTERPARTY", counterparty_id: "BUYER-1", text: "We can pay the invoice early at 0.5%.", request_id: "shots-agreement-1" }),
  });
  if (!sent.ok) throw new Error(`POST /nl -> ${sent.status}`);
  const { context, page } = await openPage(browser, vp);
  await page.goto(`${WEB}/approvals`);
  const card = page.locator('[id^="approval-APR-"]').first();
  await tid(card, "approval-terms").waitFor();
  await S.shoot(page, "13", "approvals", "pending-agreement-terms");
  await context.close();
}

async function scenarioRefused(browser, vp, S) {
  console.log("approval refused: the mandate expired at day 91");
  await walkToDay34("none");
  const { context, page } = await openPage(browser, vp);
  const { card } = await queueCure(page);
  await post("/clock/advance", { to_day: 91 });
  await card.getByRole("button", { name: /^Approve/ }).click();
  await card.locator('[data-testid^="approval-refused-"]').waitFor();
  await S.shoot(page, "16", "approvals", "refused-mandate-expired");
  await context.close();
}

async function scenarioHalf(browser, vp, S) {
  console.log("day 34, half receipt: Receivables with the chase dialog open");
  await walkToDay34("half");
  const { context, page } = await openPage(browser, vp);
  await page.goto(`${WEB}/receivables`);
  await tid(page, "receipt-e2e-receipt-1").or(page.locator('[data-testid^="receipt-"]').first()).waitFor();
  // Let the page finish loading first: a re-render after the press would close the dialog.
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForFunction(() => !document.querySelector('.animate-pulse, [aria-busy="true"]'));
  await page.waitForTimeout(500);
  // The page holds the table's control and the phone list's at once (the breakpoint hides one): press the visible one, not the one beside the top sentence.
  await page.locator('[data-testid="chase-open-RCV-A"], [data-testid="chase-list-open-RCV-A"]').locator("visible=true").first().click();
  const dialog = page.locator('dialog[open][data-testid^="chase-"]');
  await dialog.waitFor();
  await S.shoot(page, "10", "receivables", "day34-half-receipt-chase-dialog", { fullPage: false });
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "hidden" }).catch(() => {});
  await S.shoot(page, "10b", "receivables", "day34-half-receipt-list");
  await context.close();
}

async function scenarioFull(browser, vp, S) {
  console.log("day 34, full receipt: Cash, the cure pending (en, then zh at 1440 and 412), approved, Activity");
  await walkToDay34("full");
  const { context, page } = await openPage(browser, vp);
  await page.goto(`${WEB}/cash`);
  await tid(page, "cash-headline").waitFor();
  await S.shoot(page, "08", "cash", "day34");
  const { card } = await queueCure(page);
  await S.shoot(page, "14b", "approvals", "pending-funding-cure-full-receipt");

  if (vp.width === 1440 || vp.width === 412) {
    const zh = await openPage(browser, vp, "zh");
    await home(zh.page);
    await S.shoot(zh.page, "25", "home", "day34-cure-pending-zh", { lang: "zh" });
    await zh.page.goto(`${WEB}/approvals`);
    await zh.page.locator('[id^="approval-APR-"]').first().waitFor();
    await zh.page.waitForFunction(() => /批准/.test(document.querySelector('[data-testid="approval-headline"]')?.textContent ?? ""));
    await S.shoot(zh.page, "26", "approvals", "pending-funding-cure-zh", { lang: "zh" });
    await zh.context.close();
  }

  await card.getByRole("button", { name: "Approve" }).click();
  await card.locator('[data-testid^="approval-result-"]').waitFor();
  await page.goto(`${WEB}/activity`);
  await tid(page, "chain-status").waitFor();
  await S.shoot(page, "09", "activity", "day34-after-cure");
  await context.close();
}

async function scenarioDemo(browser, vp, S) {
  console.log("Demo story: scene 2 (FLOW decides), scene 5 (the owner's approve step)");
  await reset();
  const { context, page } = await openPage(browser, vp);
  await page.goto(`${WEB}/demo`);
  const strip = page.getByRole("region", { name: "Guided demo" }).locator("[aria-live=polite]");
  const next = async (n) => {
    const button = tid(page, "demo-next");
    await button.waitFor();
    await page.waitForFunction(() => !document.querySelector('[data-testid="demo-next"]')?.hasAttribute("disabled"));
    await button.click();
    await strip.getByText(new RegExp(`${n}/${STORY_STEPS}`)).waitFor();
  };
  await next(1);
  await next(2);
  await tid(page, "deal-recommendation").waitFor();
  await S.shoot(page, "21b", "demo", "scene2-flow-decides");
  for (let i = 3; i <= 7; i++) await next(i);
  await page.waitForURL(/\/approvals#approval-APR-/);
  await page.locator('[id^="approval-APR-"]').first().waitFor();
  await page.waitForFunction(() => /Approve/.test(document.querySelector('[data-testid="demo-next"]')?.textContent ?? ""));
  await S.shoot(page, "22", "demo", "scene5-owner-approve-step");
  await page.goto(`${WEB}/demo`);
  await tid(page, "story-run-8").waitFor();
  await S.shoot(page, "22b", "demo", "story-page-scene5");
  await context.close();
}

// ---- main -----------------------------------------------------------------------------------------------------------------------------------

const browser = await chromium.launch(process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {});
const failures = [];
try {
  await get("/health", {});
  for (const name of wanted) {
    const vp = ALL_WIDTHS[name];
    if (!vp) throw new Error(`unknown width ${name}`);
    console.log(`== ${name} ${vp.width}x${vp.height}`);
    const S = makeShooter(name, vp);
    // A failing scenario is recorded and the next one runs, so one missing state does not lose the rest.
    for (const run of [scenarioDay0, scenarioNoReceipt, scenarioAgreement, scenarioRefused, scenarioHalf, scenarioFull, scenarioDemo]) {
      try {
        await run(browser, vp, S);
      } catch (e) {
        failures.push(`${name} ${run.name}: ${String(e.message ?? e).split("\n")[0]}`);
        console.log(`  FAILED ${run.name}: ${String(e.message ?? e).split("\n")[0]}`);
      }
    }
    S.finish();
  }
} finally {
  try {
    await reset();
  } catch {
    /* the API is gone */
  }
  await browser.close();
}
if (failures.length) {
  console.log("\nNOT CAPTURED:\n" + failures.join("\n"));
  process.exitCode = 1;
}
