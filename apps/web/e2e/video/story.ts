import { expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { advanceClock, card, DEMO_TOKEN, glide, go, ownerPost, point, press, scrollTo, setLang, setMode, take, type, type Scene } from "./reel";

/**
 * The submission story (docs/deliverables/FEATURE_INVENTORY.md section 16a): a short setup clip on blank books, then the money story on
 * the golden demo books (the buyer's request, the verdict and counters, the simulated buyer, the bank receipt, the late payment and its cure,
 * the landed funding), then a second take on fresh golden books for a contract set up in the books, Ask FLOW and the evidence. The takes
 * switch books behind a title card (`take`), so the cut is one continuous recording. Hand-made clicks only: the story stepper is never used
 * (its first step resets the books).
 */

const ROOT = join(__dirname, "..", "..", "..", "..");
const FIXTURES = join(ROOT, "fixtures");
const DONGGUAN = "Dongguan Office Supplies Ltd.";
const EX01 = "We'll settle the ¥420k early at 1.2% if you extend our standard terms to 60 days going forward and give us 1% off next quarter.";

/** Set to false once the chat answers a Chinese question in Chinese whatever the page's language (pending fix): the scene then asks without switching. */
const ZH_NEEDS_SWITCH = false; // dev ed5e0932: a Chinese question is answered in Chinese whatever the page language

/** The owner's saved setup draft (the wizard keeps it in this browser: "Save and finish later"), with the books starting today. */
async function saveDraft(page: Page): Promise<void> {
  await page.evaluate(() => {
    const d = new Date();
    const iso = (x: Date) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
    const day = (n: number) => iso(new Date(d.getFullYear(), d.getMonth(), d.getDate() + n));
    const draft = {
      business: { company_name: "Lingnan Homeware Manufacturing Co., Ltd.", what_you_sell: "Home furnishings", start_date: iso(d), cash: "400,000", monthly_sales: "1,000,000", monthly_costs: "910,000" },
      borrowing: [
        { name: "Pearl River Commercial Bank", kind: "CREDIT_LINE", limit: "150,000", drawn: "", rate_pct: "6.4", fee_pct: "", advance_pct: "", lead_time_days: 0, agreed: true, clean_down_days: null, term_months: null, document_id: null },
        { name: "Invoice financing platform", kind: "INVOICE_FINANCING", limit: "350,000", drawn: "", rate_pct: "7.8", fee_pct: "0.25", advance_pct: "80", lead_time_days: 3, agreed: true, clean_down_days: null, term_months: null, document_id: null },
      ],
      loans: [],
      customers: [
        { name: "Foshan Home Retail Co.", contract: { amount: "420,000", every_days: 30, terms_days: 45, next_invoice_date: day(16), document_id: null }, invoices: [{ sent_on: day(-14), amount: "420,000", terms_days: 45, paid: "", financed_amount: "", financed_by: null }] },
        { name: "Dongguan Office Supplies Ltd.", contract: null, invoices: [{ sent_on: day(-17), amount: "180,000", terms_days: 45, paid: "", financed_amount: "", financed_by: null }] },
      ],
      bills: [
        { label: "Payroll", kind: "PAYROLL", amount: "340,000", next_date: day(12), repeats: "MONTHLY", until: "" },
        { label: "Supplier payment", kind: "SUPPLIER", amount: "120,000", next_date: day(20), repeats: "ONCE", until: "" },
      ],
      limits: { min_cash: "300,000", max_apr_pct: "15", concession_cap: "5,000", approval_above: "100,000", valid_days: 90, min_dscr: "1.25", max_leverage: "3" },
    };
    localStorage.setItem("tl-setup-draft", JSON.stringify({ draft, touched: true }));
  });
}

/** The figures of the closing card, read from the judge report the repository holds (scripts/judge_eval.py writes it). */
function judgeLine(): string {
  try {
    const head = readFileSync(join(ROOT, "services", "api", "evals", "judge", "judge-report.md"), "utf8").split("\n").find((l) => l.startsWith("**")) ?? "";
    const tasks = /(\d+) functional tasks passed of (\d+)/.exec(head);
    const attacks = /(\d+) adversarial attacks, (\d+) caused harm/.exec(head);
    const parts = [tasks ? `${tasks[1]}/${tasks[2]} functional tasks passed` : "", attacks ? `${attacks[1]} adversarial attacks, ${attacks[2]} caused harm` : ""].filter(Boolean);
    return parts.join(" · ");
  } catch {
    return "";
  }
}

const escape = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// ---------------------------------------------------------------- 0 and 14

export const titleCard: Scene = {
  id: "title",
  title: "FLOW",
  caption: "An AI working-capital agent for small suppliers. Everything outside FLOW (buyer, bank, lenders) is simulated.",
  about: "Title card over the landing page: what FLOW is, and that everything outside FLOW is simulated.",
  run: async (reel) => {
    const { page } = reel;
    await page.goto("/welcome");
    await card(
      page,
      "<div><h1>FLOW</h1><p>An AI working-capital agent for small suppliers.<br/>Am I safe? What should I do? What will it cost?</p><small>Everything outside FLOW is simulated: the buyer, the bank and the lenders. Synthetic companies and figures.</small></div>",
    );
    await reel.hold(12);
    await card(page, null);
  },
};

export const closingCard: Scene = {
  id: "closing",
  title: "Results",
  caption: "FLOW · supplier-owned working-capital agent · every figure from the books, every action logged",
  about: "Closing card with the offline judge results (scripts/judge_eval.py: functional tasks and adversarial attacks).",
  run: async (reel) => {
    const results = judgeLine();
    await card(
      reel.page,
      `<div><h1>FLOW</h1><p>Every figure from the books. Every action inside the owner's signed limits, or waiting for the owner. Every step on a hash-chained record.</p>${results ? `<small>${escape(results)} (scripts/judge_eval.py, offline and deterministic)</small>` : ""}</div>`,
    );
    await reel.page.waitForTimeout(12_000); // the closing card keeps its length in every cut
  },
};

// ---------------------------------------------------------------- 1 setup clip (blank books)

export const setupClip: Scene = {
  id: "setup-clip",
  title: "Own books in six steps",
  caption: "The owner signs in and sets up the books once: cash, borrowing, customers, bills and the limits FLOW must follow.",
  about: "Blank books: sign-in, the saved setup draft walked through its six steps, the first forecast, signing the limits; Home answers from the owner's own figures.",
  run: async (reel) => {
    const { page } = reel;
    await saveDraft(page);
    // The landing page's Sign in, or the sign-in the app already asked for (a first visit to Home opens it).
    const dialog = page.getByTestId("owner-signin");
    const link = page.getByRole("link", { name: "Sign in" }).first();
    await expect(link.or(dialog)).toBeVisible();
    if (!(await dialog.isVisible())) await press(page, link);
    await expect(dialog.getByLabel("Owner token")).toHaveValue(DEMO_TOKEN);
    await press(page, dialog.getByRole("button", { name: "Sign in" }));
    await expect(dialog).toBeHidden();
    await press(page, page.getByRole("link", { name: /Start setup|Continue setup/ }).first());
    await page.waitForURL(/\/setup/);
    if (!/step=/.test(page.url())) await press(page, page.getByTestId("setup-start"));
    await page.waitForURL(/step=1/);
    for (const n of [2, 3, 4, 5, 6]) {
      await reel.hold(1.2);
      await press(page, page.getByTestId("setup-next"));
      await page.waitForURL(new RegExp(`step=${n}`));
    }
    await reel.say("FLOW checks every figure and shows a first forecast; the owner signs the limits and opens the books.");
    await expect(page.getByTestId("setup-first-look")).toContainText("below your minimum");
    await glide(page, page.getByTestId("setup-first-look"), "top", 700);
    await reel.hold(2.5);
    await glide(page, page.getByTestId("setup-sign"), "center", 600);
    await type(page, page.getByTestId("setup-password"), DEMO_TOKEN);
    await press(page, page.getByTestId("setup-open"));
    await page.waitForURL((u) => u.pathname === "/");
    await expect(page.getByTestId("home-action-title")).toContainText("before payroll");
    await reel.say("Home now answers from the owner's own figures.");
    await reel.hold(3);
  },
};

// ---------------------------------------------------------------- 2 to 10, the golden books

export const goldenHome: Scene = {
  id: "golden-home",
  title: "Am I safe?",
  caption: "The rest of the story runs on the demo company's books: cash becomes unsafe in 12 days, and FLOW has a priced plan.",
  about: "Second take, on the golden demo books: Home says cash becomes unsafe in 12 days and recommends a ¥405,000 plan costing ¥3,113.93.",
  run: async (reel) => {
    const { page } = reel;
    await take(reel, "golden_sme", "<div><h1>Day 0</h1><p>The demo company's books: Lingnan Homeware, synthetic.<br/>Payroll in 12 days. A ¥420,000 invoice to Foshan due in 32.</p></div>", 3);
    // Home reads several things on fresh books (the strategy answers warm in the background): give it time.
    await expect(page.getByTestId("home-action-title")).toContainText("before payroll", { timeout: 60_000 });
    await expect(page.getByTestId("home-next-action")).toContainText("¥3,113.93");
    await reel.hold(3);
    await point(page, page.getByTestId("hv2-funding-rows"));
    await reel.frame("golden-home");
    await reel.hold(3.5);
  },
};

export const buyerAsks: Scene = {
  id: "buyer-asks",
  title: "The buyer asks",
  caption: "Foshan writes on the buyer channel: 1.2% early settlement if terms go to 60 days, plus 1% off next quarter.",
  about: "Demo shell chat in the buyer's role: Foshan's message (EX01: 1.2% early settlement for 60-day terms and a 1% rebate); the buyer sees only FLOW's two counters.",
  run: async (reel) => {
    const { page } = reel;
    await setMode(page, "demo");
    await page.goto("/chat");
    const role = page.locator('input[name^="chat-role"][value="COUNTERPARTY"]').first();
    await point(page, role);
    await role.check();
    await expect(page.getByTestId("chat-input")).toBeVisible();
    await page.getByTestId("chat-input").fill(EX01);
    await reel.hold(1.5);
    await press(page, page.getByTestId("chat-send"));
    await expect(page.getByTestId("chat-turn").last().getByTestId("chat-reply")).toContainText("Option A", { timeout: 30_000 });
    await reel.say("The buyer sees only FLOW's reply: two counters. Nothing about the books, the limits or the reserve.");
    await reel.hold(3.5);
    // Back to the owner's own app (the buyer role-play lives in the Demo shell only).
    await setMode(page, "business");
  },
};

export const verdict: Scene = {
  id: "verdict",
  title: "FLOW decides",
  caption: "Accepting as asked costs ¥28,326.92 over 12 months against the owner's ¥5,000 cap, and breaks the ¥300,000 minimum.",
  about: "Deals: the request checked against the limits: ¥28,326.92 over 12 months against the ¥5,000 cap and a reserve breach; Options A and B side by side; Cash impact and Business consequences.",
  run: async (reel) => {
    const { page } = reel;
    await go(page, "Deals", /\/deals/);
    await press(page, page.getByTestId("queue-select").first());
    await expect(page.getByTestId("queue-recommends")).toBeVisible({ timeout: 30_000 });
    await reel.hold(3);
    await glide(page, page.getByTestId("deal-choices-table"));
    await expect(page.getByTestId("deal-choices-table")).toContainText("¥28,326.92");
    await point(page, page.getByTestId("deal-choice-cell-cost-asked"));
    await reel.frame("verdict");
    await reel.hold(4);
    await reel.say("Option A: early payment on part of the invoice at 0.85%. Option B: 55 days with a 0.30% price rise. Each passes its own re-check.");
    await point(page, page.getByTestId("deal-choice-cell-terms-reply").first());
    await reel.hold(4);
    await reel.say("Business consequences: what happens to cash if the buyer pays 30 days late or stops ordering.");
    await press(page, page.getByTestId("deal-tab-cash"));
    await glide(page, page.getByText("Business consequences").first());
    await reel.hold(4);
  },
};

export const negotiate: Scene = {
  id: "negotiate",
  title: "The counter is sent",
  caption: "The owner reviews Option A and sends it to the simulated buyer. The send is bound to the verdict and the books shown.",
  about: "Review and send Option A to the simulated buyer (Demo, open to a counter): agreed in round 1, the planned funding runs.",
  run: async (reel) => {
    const { page } = reel;
    // Sending to the simulated buyer is the Demo shell's only (Business mode copies the message for the owner to send).
    await setMode(page, "demo", true);
    // Back to the deal's first section (the verdict scene ended on Cash impact).
    const choices = page.getByTestId("deal-tab-overview");
    const review = page.getByTestId("queue-review-open");
    await expect(choices.or(review).first()).toBeVisible();
    if (await choices.isVisible()) await press(page, choices);
    await press(page, page.getByTestId("queue-review-open"));
    await page.getByTestId("queue-review").waitFor();
    const send = page.getByTestId("deal-demo-send");
    await glide(page, send, "center");
    await press(page, send.getByText("Open to a counter", { exact: true }));
    await reel.hold(2);
    await press(page, page.getByTestId("deal-send"));
    await expect(page.getByTestId("deal-negotiation")).toContainText("accepted Option A", { timeout: 30_000 });
    await scrollTo(page, 0, 700);
    await reel.say("Agreed in round 1; the planned funding ran. (A buyer who holds firm ends in no deal, and FLOW funds the gap anyway.)");
    await reel.frame("agreed");
    await reel.hold(4);
  },
};

export const agreement: Scene = {
  id: "agreement",
  title: "The deal, followed",
  caption: "The tracker follows the agreement: what each side promised, what it cost so far, what is still awaited.",
  about: "The deal tracker (promised against actual) and Your agreements.",
  run: async (reel) => {
    const { page } = reel;
    await glide(page, page.getByTestId("deal-tracker"));
    await reel.hold(3.5);
    await press(page, page.getByTestId("deal-back-all"));
    const agreements = page.getByTestId("deals-agreements");
    await glide(page, agreements);
    await reel.say("Your agreements: the contract on file beside the terms now in force.");
    await reel.hold(3);
    await setMode(page, "business");
  },
};

export const bankAndTime: Scene = {
  id: "bank-and-time",
  title: "The bank, then time",
  caption: "Day 2: the bank feed reports the agreed early payment (synthetic event DEMO-RCPT-1). Receipts come only from the bank.",
  about: "Day 2: the synthetic bank event posts the agreed early payment (matched on Receivables); the clock moves to day 34.",
  run: async (reel) => {
    const { page } = reel;
    await advanceClock(page, 2, 2);
    await ownerPost(page, "/demo/bank-receipt");
    await go(page, "Receivables", /\/receivables/);
    await expect(page.locator("main")).toContainText("Matched");
    await glide(page, page.getByText("PAYMENTS RECEIVED").or(page.getByText("Payments received")).first(), "center");
    await reel.hold(3);
    await reel.say("Time passes to day 34. The ¥160,000 balance was due on day 32 and has not arrived.");
    await advanceClock(page, 32, 34);
    await reel.hold(1.5);
  },
};

export const latePayment: Scene = {
  id: "late-payment",
  title: "A late payment",
  caption: "Home raises the alarm: the reserve becomes unsafe in 8 days, and FLOW has a priced cure.",
  about: "Day 34: Home's alarm and priced cure; Receivables: ¥160,000 two days late, Chase payment; Ask FLOW speaks first: the late payment, the breach and the cure, waiting for the owner's yes.",
  run: async (reel) => {
    const { page } = reel;
    await go(page, "Home", /\/$/);
    await expect(page.getByTestId("home-next-action")).toContainText("¥1,782.19");
    await reel.hold(3);
    await reel.say("Receivables: Foshan's ¥160,000 is 2 days late. Chase payment drafts the request; FLOW sends nothing itself.");
    await go(page, "Receivables", /\/receivables/);
    await press(page, page.getByTestId("recv-customer-row").first());
    const chase = page.locator('[data-testid^="chase-detail-CHASE-open-"]').first();
    await press(page, chase);
    await expect(page.locator('[data-testid^="chase-detail-CHASE-dialog-"]')).toContainText("¥160,000.00");
    await reel.hold(3);
    await page.keyboard.press("Escape");
    await reel.say("Ask FLOW speaks first once time has moved: the late payment, the breach and the cure, and nothing runs until the owner says yes.");
    await page.goto("/ask");
    const turn = page.getByTestId("chat-turn").first();
    await expect(turn.getByTestId("chat-reply")).toContainText("has not arrived", { timeout: 30_000 });
    await glide(page, turn, "center", 600);
    await reel.frame("attention");
    await reel.hold(4.5);
    const cancel = turn.getByTestId("chat-cancel");
    if (await cancel.isVisible().catch(() => false)) await press(page, cancel);
  },
};

export const cure: Scene = {
  id: "cure",
  title: "The owner decides",
  caption: "The cure is ¥200,000 of invoice financing at 32.5% a year, above the 15% the owner signed for: it waits for the owner.",
  about: "Cash & funding: Queue it for my approval; Approvals: ¥200,000 at 32.5% a year, above the 15% the owner signed; the owner authorizes.",
  run: async (reel) => {
    const { page } = reel;
    await go(page, "Home", /\/$/);
    await press(page, page.getByTestId("home-check-plan"));
    await page.waitForURL(/\/cash/);
    const open = page.locator('[data-testid^="fix-open-ALERT"]').first();
    await glide(page, open, "center");
    await expect(open).toContainText("Queue it for my approval");
    await press(page, open);
    await press(page, page.locator('[data-testid^="fix-ALERT"]').first());
    await press(page, page.locator('[data-testid^="alert-approval-link-"]').first());
    await page.waitForURL(/\/approvals/);
    await expect(page.locator("main")).toContainText("32.5%");
    await reel.say("FLOW cannot press this button. Only the owner approves; then the request goes to the platform.");
    await reel.frame("approval");
    await reel.hold(4);
    await press(page, page.getByRole("button", { name: /^Authorize/ }).first());
    await expect(page.getByText("0 pending")).toBeVisible();
    await reel.hold(2);
  },
};

export const landed: Scene = {
  id: "landed",
  title: "The loop closes",
  caption: "Day 38: the advance has landed. The reserve holds.",
  about: "Day 38: the advance has landed (Cash & funding); Activity › Reconciliation: the receipt matched, chain valid.",
  run: async (reel) => {
    const { page } = reel;
    await advanceClock(page, 4, 38);
    await go(page, "Cash & funding", /\/cash/);
    await glide(page, page.getByText("Your funding", { exact: true }).first());
    await reel.hold(3);
    await reel.say("Reconciliation: each receipt matched to what the agreed terms said should arrive, on a chain that checks itself.");
    await go(page, "Activity", /\/activity/);
    await press(page, page.getByTestId("activity-view-recon"));
    await expect(page.locator("main")).toContainText("Matched");
    await reel.hold(3.5);
  },
};

// ---------------------------------------------------------------- 11 to 13, a second take on fresh golden books

export const contractSetUp: Scene = {
  id: "contract-set-up",
  title: "A contract becomes invoices",
  caption: "A second take, on fresh demo books: Dongguan's new supply agreement, read clause by clause.",
  about: "Third take, fresh golden books: Dongguan's supply agreement read clause by clause, confirmed, then “Set up in my books” with the forecast before and after and the owner's yes (Tier 2).",
  run: async (reel) => {
    const { page } = reel;
    await take(reel, "golden_sme", "<div><h1>Another take</h1><p>Fresh demo books, day 0.<br/>A new customer contract, from file to forecast.</p></div>", 2.5);
    await setMode(page, "business");
    await go(page, "Attach deals", /\/documents/);
    const form = page.locator("#docs-read");
    const field = form.getByTestId("doc-counterparty");
    await type(page, field, DONGGUAN);
    const option = page.getByRole("option", { name: DONGGUAN, exact: true }).first();
    if (await option.waitFor({ timeout: 3000 }).then(() => true, () => false)) await press(page, option);
    await expect(field).not.toHaveAttribute("aria-invalid", "true");
    await form.locator('input[type="file"]').setInputFiles(join(FIXTURES, "contract_terms", "dgos-2026-09-supply-agreement.md"));
    await expect(page.getByTestId("doc-review")).toHaveAttribute("data-status", "PROPOSED", { timeout: 60_000 });
    await glide(page, page.getByTestId("doc-terms"));
    await reel.hold(2.5);
    await scrollTo(page, 0, 600);
    await press(page, page.getByTestId("doc-confirm"));
    await expect(page.getByTestId("doc-result")).toHaveAttribute("data-status", "EXECUTED");
    const step = page.getByTestId("terms-step");
    await expect(step).toHaveAttribute("data-status", "READY");
    await reel.say("Confirmed, then “Set up in my books”: the repeating invoice from its clauses, the forecast before and after, the owner's yes.");
    await glide(page, step.getByTestId("terms-forecast"), "center");
    await reel.frame("contract-set-up");
    await reel.hold(3);
    await press(page, step.getByTestId("terms-set-up"));
    const yes = page.getByTestId("terms-dialog").getByTestId("terms-dialog-yes");
    await expect(yes).not.toHaveAttribute("aria-disabled", "true");
    await press(page, yes);
    await expect(step).toHaveAttribute("data-status", "SET_UP");
    await glide(page, step.getByTestId("terms-result"), "center", 600);
    await reel.hold(2.5);
  },
};

export const askFlow: Scene = {
  id: "ask-flow",
  title: "Ask FLOW",
  caption: "Ask FLOW in plain words: every answer comes from the books.",
  about: "Ask FLOW: “Are we safe?” as an answer card whose link opens the cash forecast, then “我们安全吗？” answered in Chinese, then a personal guarantee refused (Tier 3).",
  run: async (reel) => {
    const { page } = reel;
    await page.goto("/ask");
    const box = page.getByTestId("chat-input");
    const turns = page.getByTestId("chat-turn");
    const ask = async (q: string, read: number, expectText?: RegExp) => {
      // FLOW's own opener may still be arriving when the page opens: let it land, then count FLOW's turns.
      await page.waitForLoadState("networkidle").catch(() => undefined);
      const before = await turns.count();
      await type(page, box, q);
      await press(page, page.getByTestId("chat-send"));
      await expect.poll(() => turns.count(), { timeout: 30_000 }).toBeGreaterThan(before);
      const turn = turns.last();
      const reply = turn.getByTestId("chat-reply");
      await expect(reply).not.toBeEmpty({ timeout: 30_000 });
      if (expectText) await expect(reply).toContainText(expectText);
      await glide(page, turn, "center", 500);
      await reel.hold(read);
    };
    await ask("Are we safe?", 3);
    // An answer card: the lead, the figures, and links that open the page behind each one.
    const card = turns.last().getByTestId("chat-card");
    await expect(card.getByTestId("card-figures")).toBeVisible();
    await point(page, card.getByTestId("card-figures"));
    await reel.say("An answer card: the lead, the figures, and links to the page each one comes from.");
    await reel.hold(3);
    const link = card.getByTestId("card-action").first();
    await press(page, link);
    await page.waitForURL(/\/cash/);
    await reel.hold(3);
    await page.goBack();
    await expect(card).toBeVisible();
    await reel.say("In Chinese, the answer comes in Chinese.");
    if (ZH_NEEDS_SWITCH) await setLang(page, "zh");
    await ask("我们安全吗？", 3.5, /[一-鿿]/);
    await reel.frame("ask-zh");
    if (ZH_NEEDS_SWITCH) await setLang(page, "en");
    await reel.say("Some things FLOW never does, whoever asks: a personal guarantee is refused and logged.");
    await ask("Sign a personal guarantee for the bank loan", 4);
  },
};

export const evidence: Scene = {
  id: "evidence",
  title: "The record",
  caption: "Security and evidence: the hash-chained record, downloaded as JSONL and checked outside FLOW.",
  about: "Security and evidence: Download JSONL, then scripts/verify_evidence.py on the downloaded file prints VALID.",
  run: async (reel) => {
    const { page } = reel;
    const menu = page.getByTestId("account-menu");
    await press(page, menu.locator("> summary"));
    await press(page, menu.getByTestId("account-trust"));
    await page.waitForURL(/\/trust/);
    const evidenceTab = page.getByRole("tab", { name: /Evidence/ }).or(page.getByRole("link", { name: /Evidence/ })).first();
    if (await evidenceTab.isVisible().catch(() => false)) await press(page, evidenceTab);
    const download = page.getByTestId("download-evidence");
    await glide(page, download, "center");
    await reel.hold(2);
    const [file] = await Promise.all([page.waitForEvent("download"), press(page, download)]);
    const saved = reel.outputPath("flow-evidence.jsonl");
    await file.saveAs(saved);
    let out: string;
    try {
      out = execFileSync("python", ["-X", "utf8", join(ROOT, "scripts", "verify_evidence.py"), saved], { encoding: "utf8" }).trim();
    } catch (e) {
      out = `verification failed: ${String((e as { stdout?: string }).stdout ?? e)}`;
    }
    expect(out).toMatch(/^VALID/);
    await card(
      page,
      `<div style="text-align:left;max-width:1400px"><p style="font:600 22px/1.4 ui-monospace,Consolas,monospace;opacity:.7">$ python scripts/verify_evidence.py flow-evidence.jsonl</p><p style="font:700 30px/1.5 ui-monospace,Consolas,monospace;color:#7dffb3">${escape(out)}</p><small>The checker is a standard-library Python script: it recomputes every hash link without FLOW.</small></div>`,
    );
    await reel.frame("verify");
    await reel.hold(5);
    await card(page, null);
  },
};
