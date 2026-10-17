import { expect, request as apiRequest, type Page } from "@playwright/test";
import { join } from "node:path";
import { card, glide, go, point, press, scrollTo, type, type Reel, type Scene } from "./reel";

/**
 * The scenes of the demo videos, one per feature or step, each with its chapter title and first caption. A scene starts where the one
 * before it left the app (the books build up from blank: setup, then documents, then deals ...), so a cut lists them in this file's order
 * and may leave some out. Every wait for correctness is on text or a test id the server wrote; `reel.hold` is only for the viewer.
 */

const API = process.env.VIDEO_API_URL ?? "http://localhost:8090";
/** The local demo build's published owner token (scripts/demo.mjs runs the API with DEMO_MODE=1). It also signs the limits at setup. */
const DEMO_TOKEN = "demo-owner-token";
/** Foshan is the first customer the setup enters, so the books give it BUYER-1, the buyer whose demo channel key the API publishes. */
const FOSHAN_CHANNEL_KEY = "demo-buyer-1-key";
const FIXTURES = join(__dirname, "..", "..", "..", "..", "fixtures");

const COMPANY = "Lingnan Homeware Manufacturing Co., Ltd.";
const FOSHAN = "Foshan Home Retail Co.";
const DONGGUAN = "Dongguan Office Supplies Ltd.";
const SHUNDE = "Shunde Kitchen Supply Co.";
const BANK = "Pearl River Commercial Bank";
const PLATFORM = "Invoice financing platform";

const day = (start: string, n: number) => new Date(Date.parse(`${start}T00:00:00Z`) + n * 86_400_000).toISOString().slice(0, 10);

/** Attach deals' upload form. */
const docs = (page: Page) => page.locator("#docs-read");

/**
 * "Who it is with" on Attach deals, chosen by name: typed into the field (`doc-counterparty`), the matching option picked when the field
 * lists the companies as options, and done once the field takes it (it is marked invalid until the companies on the books have loaded and
 * the name is one of them). Only roles, names and the field's test id: the field's internals can change.
 */
async function chooseCompany(page: Page, name: string): Promise<void> {
  const field = docs(page).getByTestId("doc-counterparty");
  await type(page, field, name);
  const option = page.getByRole("option", { name, exact: true }).first();
  if (await option.isVisible().catch(() => false)) await press(page, option);
  await expect(field).not.toHaveAttribute("aria-invalid", "true");
}

async function upload(page: Page, ...file: string[]): Promise<void> {
  await docs(page).locator('input[type="file"]').setInputFiles(join(FIXTURES, ...file));
}

// ---------------------------------------------------------------- the opening and the end

/** Not a chapter: the title card over the public landing page. */
export async function opening(reel: Reel): Promise<void> {
  const { page } = reel;
  await page.goto("/");
  await card(
    page,
    "<div><h1>FLOW</h1><p>An AI working-capital agent for small suppliers.<br/>From empty books to a funded cash gap, on the owner's own figures.</p><small>Simulation · every company, bank and figure is synthetic</small></div>",
  );
  await reel.hold(4);
  await card(page, null);
}

export const endCard: Scene = {
  id: "end",
  title: "FLOW",
  caption: "FLOW · supplier-owned working-capital agent · every figure from the books, every action logged",
  run: async (reel) => {
    const { page } = reel;
    await page.goto("/");
    await expect(page.getByTestId("home-status-word")).toBeVisible();
    await reel.hold(2);
    await card(page, "<div><h1>FLOW</h1><p>Supplier-owned working-capital agent<br/>Every figure from the books, every action logged.</p><small>FinTechathon 2026 · simulation, synthetic companies and figures</small></div>");
    await page.waitForTimeout(6000); // the end card stays its full length in every cut
  },
};

// ---------------------------------------------------------------- start

export const signIn: Scene = {
  id: "sign-in",
  title: "Sign in",
  caption: "The owner signs in. The demo build pre-fills its owner token.",
  run: async (reel) => {
    const { page } = reel;
    const link = page.getByRole("link", { name: "Sign in" }).first();
    await expect(link).toBeVisible();
    await reel.hold(2.5);
    await press(page, link);
    const dialog = page.getByTestId("owner-signin");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByLabel("Owner token")).toHaveValue(DEMO_TOKEN);
    await reel.hold(2);
    await press(page, dialog.getByRole("button", { name: "Sign in" }));
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("link", { name: "Start setup" })).toBeVisible();
    await reel.say("Empty books: FLOW can't say whether the business is safe until the owner sets them up.");
    await reel.hold(3.5);
  },
};

export const setupBooks: Scene = {
  id: "setup",
  title: "Set up your books",
  caption: "The owner enters cash, customers, facilities and limits once, in six short steps.",
  run: async (reel) => {
    const { page } = reel;
    await press(page, page.getByRole("link", { name: "Start setup" }));
    await page.waitForURL(/\/setup\?step=1/);
    const startField = page.getByTestId("setup-start");
    await expect(startField).not.toHaveValue("");
    const start = await startField.inputValue();
    await reel.say("Step 1: the business and the cash in the bank today, ¥400,000.");
    await type(page, page.getByTestId("setup-company"), COMPANY);
    await page.getByPlaceholder(/./).nth(1).fill("Home furnishings");
    await type(page, page.getByTestId("setup-cash"), "400000");
    await page.getByTestId("setup-sales").fill("1000000");
    await page.getByTestId("setup-costs").fill("910000");
    await page.getByTestId("setup-costs").blur();
    await reel.hold(2);
    await press(page, page.getByTestId("setup-next"));
    await page.waitForURL(/step=2/);

    await reel.say("Step 2: a ¥150,000 bank credit line at 6.4% and ¥350,000 of invoice financing.");
    await press(page, page.getByTestId("setup-add-source"));
    await page.getByTestId("setup-add-source").click();
    const sources = page.getByRole("region", { name: "Ways to borrow" }).locator("tbody tr");
    await expect(sources).toHaveCount(2);
    await type(page, sources.nth(0).getByLabel("Name"), BANK);
    await sources.nth(0).getByLabel("Limit").fill("150000");
    await sources.nth(0).getByLabel("Cost a year (%)").fill("6.4");
    await sources.nth(1).getByLabel("Kind").selectOption("INVOICE_FINANCING");
    await sources.nth(1).getByLabel("Name").fill(PLATFORM);
    await sources.nth(1).getByLabel("Limit").fill("350000");
    await sources.nth(1).getByLabel("Cost a year (%)").fill("7.8");
    await sources.nth(1).getByLabel("Fee per 30 days (%)").fill("0.25");
    await sources.nth(1).getByLabel("Fee per 30 days (%)").blur();
    await reel.hold(2.5);
    await press(page, page.getByTestId("setup-next"));
    await page.waitForURL(/step=3/);

    await reel.say("Step 3: Foshan Home Retail Co. — an open ¥420,000 invoice on 45-day terms, invoiced every 30 days.");
    await press(page, page.getByTestId("setup-add-customer"));
    await type(page, page.getByTestId("setup-customer-name"), FOSHAN);
    await press(page, page.getByTestId("setup-add-contract"));
    await page.getByLabel("Invoice amount").fill("420000");
    await page.getByLabel("Invoiced every (days)").fill("30");
    await page.getByLabel("Pays within (days)").first().fill("45");
    // The supply agreement's own schedule: invoiced on 3 Oct 2026, the next batch 30 days later.
    await page.getByLabel("Next invoice on").fill(day(start, 16));
    await press(page, page.getByTestId("setup-add-invoice"));
    const invoices = page.getByRole("region", { name: "Invoices sent and not fully paid" });
    await invoices.getByLabel("Sent on").fill(day(start, -14));
    await invoices.getByLabel("Amount", { exact: true }).fill("420000");
    await invoices.getByLabel("Amount", { exact: true }).blur();
    await reel.hold(2.5);
    await reel.say("…and Dongguan Office Supplies Ltd., with one open ¥180,000 invoice and no contract on file yet.");
    await press(page, page.getByTestId("setup-add-customer"));
    await type(page, page.getByTestId("setup-customer-name"), DONGGUAN);
    await press(page, page.getByTestId("setup-add-invoice"));
    await invoices.getByLabel("Sent on").fill(day(start, -17));
    await invoices.getByLabel("Amount", { exact: true }).fill("180000");
    await invoices.getByLabel("Pays within (days)").fill("45");
    await invoices.getByLabel("Pays within (days)").blur();
    await reel.hold(2);
    await press(page, page.getByTestId("setup-next"));
    await page.waitForURL(/step=4/);

    await reel.say("Step 4: the bills coming up — payroll of ¥340,000 every month and a ¥120,000 supplier payment.");
    await press(page, page.getByTestId("setup-quick-PAYROLL"));
    await press(page, page.getByTestId("setup-quick-SUPPLIER"));
    const bills = page.getByRole("region", { name: "Bills coming up" }).locator("tbody tr");
    await expect(bills).toHaveCount(2);
    await bills.nth(0).getByLabel("Amount").fill("340000");
    await bills.nth(0).getByLabel("Next on").fill(day(start, 12));
    await bills.nth(1).getByLabel("Amount").fill("120000");
    await bills.nth(1).getByLabel("Next on").fill(day(start, 20));
    await bills.nth(1).getByLabel("Next on").blur();
    await reel.hold(2.5);
    await press(page, page.getByTestId("setup-next"));
    await page.waitForURL(/step=5/);

    await reel.say("Step 5: the owner's limits — always keep ¥300,000; everything else at the defaults.");
    await type(page, page.getByTestId("setup-min-cash"), "300000");
    await page.getByTestId("setup-min-cash").blur();
    await reel.hold(3);
    await press(page, page.getByTestId("setup-next"));
    await page.waitForURL(/step=6/);

    await reel.say("Step 6: FLOW checks every figure and shows a first forecast: cash falls below the minimum in 12 days.");
    await expect(page.getByTestId("setup-summary")).toBeVisible();
    await expect(page.getByTestId("setup-first-look")).toContainText("below your minimum");
    await reel.hold(2);
    await glide(page, page.getByTestId("setup-first-look"));
    await reel.hold(4);
    await reel.frame("setup-review");
    await reel.say("The owner signs the limits and opens the books: the first entry of the record.");
    await glide(page, page.getByTestId("setup-sign"), "center");
    await type(page, page.getByTestId("setup-password"), DEMO_TOKEN);
    await reel.hold(1);
    await press(page, page.getByTestId("setup-open"));
    await page.waitForURL((u) => u.pathname === "/");
  },
};

// ---------------------------------------------------------------- home

export const homeGap: Scene = {
  id: "home-gap",
  title: "Home: the forecast and the gap",
  caption: "Home answers from the owner's own books: without new funding, cash runs short before payroll.",
  run: async (reel) => {
    const { page } = reel;
    await expect(page.getByTestId("home-action-title")).toContainText("before payroll");
    await expect(page.getByTestId("home-check-plan")).toBeVisible();
    await reel.hold(3.5);
    await reel.frame("home-gap");
    const box = await page.getByTestId("home-chart").boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width * 0.08, box.y + box.height * 0.5, { steps: 10 });
      await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.5, { steps: 40 });
      await reel.hold(1.5);
    }
    await reel.say("FLOW's funding plan: what to draw, from where, when, and what it costs — all within the signed limits. Not approved yet.");
    await point(page, page.getByTestId("hv2-funding-rows"));
    await reel.hold(4);
    if (reel.cut === "full") {
      await glide(page, page.getByTestId("home-worklist-panel"));
      await reel.say("Below: the worklist, the cash today against the minimum, and the money coming in and going out.");
      await reel.hold(3.5);
      await scrollTo(page, 0);
    }
  },
};

// ---------------------------------------------------------------- documents

export const attachDeal: Scene = {
  id: "attach-deal",
  title: "Attach a deal",
  caption: "Attach deals: the owner uploads Foshan's signed supply agreement (a PDF).",
  run: async (reel) => {
    const { page } = reel;
    await go(page, "Attach deals", /\/documents/);
    await chooseCompany(page, FOSHAN);
    await reel.hold(1);
    await upload(page, "contracts", "fhr-2026-07-supply-agreement.pdf");
    const review = page.getByTestId("doc-review");
    await expect(review).toHaveAttribute("data-status", "PROPOSED", { timeout: 60_000 });
    await reel.say("FLOW reads the contract. The deal at a glance: price, payment terms, early payment, invoicing, term.");
    await glide(page, page.getByTestId("deal-picture-terms"));
    await reel.hold(4);
    await reel.frame("deal-at-a-glance");
    await reel.say("Every term sits beside the clause it came from; pointing at a term shows its clause.");
    await glide(page, page.getByTestId("doc-terms"));
    for (const i of reel.cut === "full" ? [7, 9] : [7]) {
      await point(page, page.getByTestId(`doc-item-term:${i}`));
      await reel.hold(1.8);
    }
    await reel.say("The owner confirms the reading. Confirming records what the contract says; it changes nothing in the books.");
    await scrollTo(page, 0, 900);
    await press(page, page.getByTestId("doc-confirm"));
    await expect(page.getByTestId("doc-result")).toHaveAttribute("data-status", "EXECUTED");
    await glide(page, page.getByTestId("doc-outcome"));
    await expect(page.getByTestId("terms-step")).toHaveAttribute("data-status", "ALREADY");
    await reel.hold(4.5);
  },
};

export const wrongCompany: Scene = {
  id: "wrong-company",
  title: "Safety: the wrong company",
  caption: "Safety: the same contract filed under the wrong customer, Dongguan.",
  run: async (reel) => {
    const { page } = reel;
    await scrollTo(page, 0, 900);
    await chooseCompany(page, DONGGUAN);
    await upload(page, "contracts", "fhr-2026-07-supply-agreement.pdf");
    const flags = page.getByTestId("doc-flags");
    await expect(flags).toContainText("does not name the company you chose", { timeout: 60_000 });
    await expect(page.getByTestId("doc-confirm")).toBeDisabled();
    await reel.say("Blocked: the document names other companies, so it cannot be confirmed under Dongguan.");
    await glide(page, flags, "center");
    await reel.hold(4);
    await reel.frame("blocked");
    await reel.say("One press files it under the buyer it does name: Foshan Home Retail Co.");
    await press(page, page.getByTestId("doc-party-actions").getByRole("button", { name: `File it under ${FOSHAN}` }));
    await expect(page.getByTestId("doc-replaces")).toContainText(`instead of under ${DONGGUAN}`);
    await expect(page.getByTestId("doc-confirm")).toBeEnabled();
    await reel.hold(2.5);
    await reel.say("Foshan's contract is already confirmed, so this duplicate reading is rejected: nothing is recorded from it.");
    await press(page, page.getByTestId("doc-reject"));
    await expect(page.getByTestId("doc-review")).toHaveAttribute("data-status", "REJECTED");
    await reel.hold(3);
  },
};

export const newCustomer: Scene = {
  id: "new-customer",
  title: "A new customer",
  caption: "A contract from a buyer not on the books yet: Shunde Kitchen Supply Co.",
  run: async (reel) => {
    const { page } = reel;
    const form = docs(page);
    await scrollTo(page, 0, 900);
    await type(page, form.getByTestId("doc-counterparty"), SHUNDE);
    const offer = form.getByTestId("doc-new-customer");
    await expect(offer).toContainText("Add");
    await reel.hold(1.5);
    await press(page, offer);
    await expect(form.getByTestId("doc-new-customer-panel")).toBeVisible();
    await reel.hold(1.5);
    await press(page, form.getByTestId("doc-new-customer-add"));
    await expect(form.getByTestId("doc-new-customer-done")).toContainText(`You added ${SHUNDE} as a customer.`);
    await reel.say("Added as a new customer, and chosen: its contract can be uploaded now.");
    await reel.hold(3);
  },
};

export const contractToForecast: Scene = {
  id: "contract-to-forecast",
  title: "From contract to forecast",
  caption: "Dongguan's new supply agreement: read, confirmed, then set up in the books.",
  run: async (reel) => {
    const { page } = reel;
    if (!new URL(page.url()).pathname.startsWith("/documents")) await go(page, "Attach deals", /\/documents/);
    await scrollTo(page, 0, 700);
    await chooseCompany(page, DONGGUAN);
    await upload(page, "contract_terms", "dgos-2026-09-supply-agreement.md");
    await expect(page.getByTestId("doc-review")).toHaveAttribute("data-status", "PROPOSED", { timeout: 60_000 });
    await glide(page, page.getByTestId("deal-picture-terms"));
    await reel.hold(2.5);
    await scrollTo(page, 0, 900);
    await press(page, page.getByTestId("doc-confirm"));
    await expect(page.getByTestId("doc-result")).toHaveAttribute("data-status", "EXECUTED");
    const step = page.getByTestId("terms-step");
    await expect(step).toHaveAttribute("data-status", "READY");
    await reel.say("“Set up in my books”: the repeating invoice, each term from its clause, and the forecast before and after.");
    await glide(page, step);
    await reel.hold(3.5);
    await glide(page, step.getByTestId("terms-forecast"), "center");
    await reel.hold(4);
    await reel.frame("contract-to-forecast");
    await reel.say("Changing the books is the owner's decision (Tier 2): FLOW asks for the confirmation, then logs it.");
    await press(page, step.getByTestId("terms-set-up"));
    const dialog = page.getByTestId("terms-dialog");
    await expect(dialog).toBeVisible();
    const yes = dialog.getByTestId("terms-dialog-yes");
    await expect(yes).not.toHaveAttribute("aria-disabled", "true");
    await reel.hold(2.5);
    await press(page, yes);
    await expect(step.getByTestId("terms-result")).toHaveAttribute("data-status", "EXECUTED");
    await expect(step).toHaveAttribute("data-status", "SET_UP");
    await glide(page, step.getByTestId("terms-result"), "center");
    await reel.hold(3);
    await reel.say("Home's forecast now counts on Dongguan's invoices: the 120-day view ends higher.");
    await go(page, "Home", /\/$/);
    await expect(page.getByTestId("home-action-title")).toBeVisible();
    await press(page, page.getByTestId("home-window-120"));
    await reel.hold(4);
  },
};

export const lenderAgreement: Scene = {
  id: "lender-agreement",
  title: "A lender agreement",
  caption: "A lender agreement: the bank's credit-line agreement, filed under Pearl River Commercial Bank.",
  run: async (reel) => {
    const { page } = reel;
    const form = docs(page);
    await go(page, "Attach deals", /\/documents/);
    await press(page, form.getByTestId("doc-kind"));
    await press(page, form.getByTestId("doc-kind-list").getByRole("option", { name: /^Lender agreement/ }));
    await expect(form.getByTestId("doc-kind")).toContainText("Lender agreement");
    await chooseCompany(page, BANK);
    await upload(page, "contracts", "mb-cl-2026-031-credit-line-agreement.pdf");
    await expect(page.getByTestId("doc-review")).toHaveAttribute("data-kind", "LENDER_AGREEMENT", { timeout: 60_000 });
    await expect(page.getByTestId("doc-review")).toHaveAttribute("data-status", "PROPOSED");
    await reel.say("FLOW reads the limit, the rate and the lead time, and sets them against the books.");
    await glide(page, page.getByTestId("deal-picture-terms"));
    await reel.hold(3.5);
    await scrollTo(page, 0, 900);
    await reel.say("Confirmed, and linked to the credit line on the books for reference.");
    const link = page.getByLabel(/Also link this agreement/);
    await point(page, link);
    await link.check();
    await press(page, page.getByTestId("doc-confirm"));
    await expect(page.getByTestId("doc-result")).toHaveAttribute("data-status", "EXECUTED");
    await glide(page, page.getByTestId("doc-outcome"));
    await reel.hold(3.5);
  },
};

// ---------------------------------------------------------------- deals

export const buyerRequest: Scene = {
  id: "buyer-request",
  title: "Deals: a buyer asks for 60 days",
  caption: "A buyer writes in on its own channel: Foshan asks for 60-day terms, 1.2% early settlement and a rebate.",
  run: async (reel) => {
    const { page } = reel;
    // The buyer's message arrives through the API's keyed buyer channel (the demo channel key for BUYER-1), as a buyer would send it.
    const api = await apiRequest.newContext();
    const sent = await api.post(`${API}/offers`, { headers: { "X-Counterparty-Key": FOSHAN_CHANNEL_KEY }, data: { fixture_id: "EX01_PACKAGE" } });
    expect(sent.ok()).toBeTruthy();
    await api.dispose();
    await go(page, "Deals", /\/deals/);
    await expect(page.getByTestId("queue-row").first()).toContainText("60-day terms");
    await reel.hold(3);
    await press(page, page.getByTestId("queue-select").first());
    await press(page, page.getByTestId("queue-check-button"));
    await expect(page.getByTestId("queue-recommends")).toBeVisible({ timeout: 30_000 });
    await reel.say("FLOW's verdict: accepting as asked breaks the ¥300,000 minimum. It recommends a counter inside the limits.");
    await reel.hold(4.5);
    await reel.frame("deal-verdict");
    await reel.say("Every choice side by side: the buyer's ask and FLOW's counters, each with its lowest cash, cost and who decides.");
    await glide(page, page.locator('[data-testid="deal-choices-table"]:visible, [data-testid="deal-choices-stack"]:visible').first());
    await reel.hold(5);
    // The agreements in force under the deals list: shown when the page lists the confirmed contracts (it lists only negotiated ones today).
    await press(page, page.getByTestId("deal-back-all"));
    await expect(page.getByTestId("deals-list-view")).toBeVisible();
    const agreements = page.getByTestId("deals-agreements");
    if (await agreements.getByTestId("commitment-toggle").first().isVisible().catch(() => false)) {
      await reel.say("Your agreements: each customer's confirmed contract and open invoices, beside the books.");
      await glide(page, agreements);
      await press(page, agreements.getByTestId("commitment-toggle").first());
      await reel.hold(4);
    }
    if (reel.cut === "full") {
      await reel.say("Each customer's record: what they owe, the financing against it, and the path from receivable to cash.");
      await page.goto("/customers/BUYER-1");
      await expect(page.locator("main")).toContainText(FOSHAN);
      await expect(page.locator("main")).toContainText("From receivable to cash");
      await reel.hold(3);
      await glide(page, page.getByText("From receivable to cash").first());
      await reel.hold(3.5);
    }
  },
};

// ---------------------------------------------------------------- ask FLOW

export const askFlow: Scene = {
  id: "ask-flow",
  title: "Ask FLOW",
  caption: "Ask FLOW in plain language: every answer is computed from the books.",
  run: async (reel) => {
    const { page } = reel;
    await page.goto("/chat");
    const box = page.locator("#chat-input");
    const turns = page.getByTestId("chat-turn");
    await expect(box).toBeVisible();
    let n = 0;
    const ask = async (question: string, read: number) => {
      await type(page, box, question);
      await press(page, page.getByTestId("chat-send"));
      await expect(turns.nth(n).getByTestId("chat-reply")).not.toBeEmpty({ timeout: 30_000 });
      await glide(page, turns.nth(n), "center", 700);
      n += 1;
      await reel.hold(read);
    };
    await ask("Are we safe?", 4);
    if (reel.cut === "full") {
      await ask("Who owes us the most?", 4);
      await ask("Can we clear all our debts?", 3);
    }
    await ask("What if Foshan pays 30 days late?", 5);
    await reel.say("In Chinese too: the owner switches the app to 中文 and asks “我们安全吗？”.");
    const menu = page.getByTestId("account-menu");
    await press(page, menu.locator("> summary"));
    await press(page, menu.getByText("中文", { exact: true }));
    await expect(page.locator("html")).toHaveAttribute("lang", /zh/);
    await page.keyboard.press("Escape");
    await ask("我们安全吗？", 5);
    await expect(turns.nth(n - 1).getByTestId("chat-reply")).toContainText(/[一-鿿]/);
    await reel.frame("ask-flow-zh");
    await press(page, menu.locator("> summary"));
    await press(page, menu.getByText("English", { exact: true }));
    await expect(page.locator("html")).toHaveAttribute("lang", /en/);
    await page.keyboard.press("Escape");
    if (reel.cut === "full") {
      await reel.say("“New conversation” starts afresh.");
      await press(page, page.getByTestId("chat-new"));
      await expect(turns).toHaveCount(0);
      await reel.hold(2.5);
    }
  },
};

// ---------------------------------------------------------------- funding

export const fundGap: Scene = {
  id: "fund-gap",
  title: "Fund the gap",
  caption: "Fund the gap: the owner checks FLOW's plan and runs it.",
  run: async (reel) => {
    const { page } = reel;
    await go(page, "Home", /\/$/);
    await press(page, page.getByTestId("home-check-plan"));
    await page.waitForURL(/\/cash/);
    const open = page.locator('[data-testid^="fix-open-ALERT"]').first();
    await expect(open).toBeVisible();
    await glide(page, open, "center");
    await reel.hold(3);
    await press(page, open);
    const run = page.locator('[data-testid^="fix-ALERT"]').first();
    await expect(run).toBeVisible();
    await reel.hold(2);
    await reel.say("Everything inside the signed limits runs at once (Tier 1); anything above them would wait in Approvals.");
    await press(page, run);
    await expect(page.locator('[data-testid^="fix-ALERT"]')).toHaveCount(0);
    // A step above the owner's limits waits for the owner: approved in Approvals (none on these books, but the scene handles it).
    const approval = page.locator('[data-testid^="alert-approval-link-"]').first();
    if (await approval.isVisible().catch(() => false)) {
      await press(page, approval);
      await press(page, page.getByRole("button", { name: /^Authorize/ }).first());
      await expect(page.getByText("0 pending")).toBeVisible();
    }
    await reel.hold(2.5);
    await go(page, "Home", /\/$/);
    await expect(page.getByTestId("home-status-word")).toContainText(/covered/i);
    await reel.say("Home: the reserve is held. The funds arriving are shown as waiting until they land.");
    await reel.hold(4.5);
    await reel.frame("reserve-held");
  },
};

export const cashFunding: Scene = {
  id: "cash-funding",
  title: "Cash & funding",
  caption: "Cash & funding: each source, how much is drawn, and what is left.",
  run: async (reel) => {
    const { page } = reel;
    await go(page, "Cash & funding", /\/cash/);
    await expect(page.locator("main")).toContainText("Your funding");
    await glide(page, page.getByText("Your funding", { exact: true }).first());
    await reel.hold(4);
  },
};

export const capex: Scene = {
  id: "capex",
  title: "Capex & purchases",
  caption: "Capex: is a ¥600k machine worth it, and which financing keeps every covenant and the reserve?",
  run: async (reel) => {
    const { page } = reel;
    await go(page, "Capex", /\/capex/);
    const quick = page.getByTestId("capex-quick");
    await expect(quick).toBeVisible();
    if (!(await quick.evaluate((el) => (el as HTMLDetailsElement).open))) await press(page, quick.locator("> summary"));
    await glide(page, quick);
    await press(page, quick.getByRole("button", { name: /Evaluate the/ }));
    await expect(quick).toContainText("Net present value", { timeout: 30_000 });
    await reel.hold(3.5);
    await glide(page, quick.getByText("Financing structures").first());
    await reel.hold(4);
  },
};

export const receivables: Scene = {
  id: "receivables",
  title: "Receivables",
  caption: "Receivables: who owes what, when it is due, and what is left once financing is repaid.",
  run: async (reel) => {
    const { page } = reel;
    await go(page, "Receivables", /\/receivables/);
    await expect(page.getByTestId("recv-customer-list")).toBeVisible();
    await reel.hold(3);
    await glide(page, page.getByTestId("recv-customer-list"));
    await reel.hold(3);
  },
};

export const activity: Scene = {
  id: "activity",
  title: "Activity and evidence",
  caption: "Activity: every action in the owner's words, on a hash-chained record that checks itself.",
  run: async (reel) => {
    const { page } = reel;
    await go(page, "Activity", /\/activity/);
    await expect(page.getByTestId("chain-status")).toContainText("Record chain checks passed");
    await reel.hold(3.5);
    await reel.frame("activity");
    await glide(page, page.getByTestId("activity-list"));
    await reel.hold(3);
    await reel.say("The evidence: each entry with its hash and the one before it, downloadable to verify.");
    await page.goto("/evidence");
    await expect(page.getByTestId("trust-entries")).toBeVisible();
    await reel.hold(3);
    await glide(page, page.getByTestId("trust-entry-2"));
    await reel.hold(3.5);
  },
};
