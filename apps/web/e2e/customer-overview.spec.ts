import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { checkedDeal, openInbox, runPlan } from "./helpers";

/**
 * The customer overview, /customers/{id} (map #88, ticket #108), in mock mode on the recorded API answers (scripts/record-mocks.mjs --overview):
 * the four figures, the one commercial decision with its primary, the back link the server builds from the query, the links each page's customer
 * names carry, the exposure note while that read is off, Chinese, a phone, and axe. Every string asserted is the server's, read from the page or from
 * the recording; nothing is hand-written into a mock. What waits on another ticket: Deals selecting the `path` it is sent back with (the Deals
 * queue, #109) and the Cash page showing a customer by name (none is shown there today).
 */

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded overview");
});

/** The decision's own query (`decision`, `path`), taken from the primary link the page shows. */
async function decisionQuery(page: Page): Promise<URLSearchParams> {
  await page.goto("/customers/BUYER-1");
  const href = await page.getByTestId("customer-decision-primary").getAttribute("href");
  expect(href).toMatch(/^\/deals\?decision=.+&path=.+/);
  return new URL(href!, "http://flow.local").searchParams;
}

async function scan(page: Page, label: string) {
  const result = await new AxeBuilder({ page }).analyze();
  const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(result.passes.length, `${label}: axe ran its rules`).toBeGreaterThan(10);
  expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`), `${label}: serious or critical findings`).toEqual([]);
}

test("the opening books: the name, the four figures, no decision waiting, the two other links, both panels and the history", async ({ page }) => {
  await page.goto("/customers/BUYER-1");
  await expect(page.locator("h1")).toHaveText("Foshan Home Retail Co.");
  await expect(page.getByText("What this relationship is worth, and what it puts at risk.")).toBeVisible();
  const figures = page.getByTestId("customer-figures");
  await expect(figures.locator("dt")).toHaveText(["Estimated annual gross contribution", "Outstanding", "Financing linked", "Share of what you are owed"]);
  await expect(page.locator("body")).not.toContainText("Relationship value");
  await expect(page.getByTestId("customer-figure-outstanding-value")).toHaveText("¥420,000");
  await expect(page.getByTestId("customer-figure-outstanding-note")).toHaveText("due in 32 days, nothing overdue");
  await expect(page.getByTestId("customer-figure-share-value")).toHaveText("100%");
  await expect(page.getByTestId("customer-figure-share-note")).toHaveText("one open invoice; not its share of your sales");
  // The Demo's sales and margin give the server's estimate; the browser makes none of its own.
  await expect(page.getByTestId("customer-figure-value-value")).toHaveText("about ¥1.09m");
  // Where it comes from is said beside it, in the server's words (the margin is the weakest link), once.
  await expect(page.getByTestId("customer-figure-value-note")).toHaveText("a year, estimated contribution; margin assumed for the Demo, not confirmed by you");
  await expect(page.getByTestId("customer-figure-value-provenance")).toHaveCount(0);
  // No decision waits: the server's line, the two links that remain, and no filled primary on the page.
  const none = page.getByTestId("customer-decision-none");
  await expect(none).toContainText("No commercial decision is waiting for you with Foshan.");
  await expect(none.getByRole("link")).toHaveText(["View the invoices", "Stress-test payment"]);
  await expect(page.getByTestId("customer-decision")).toHaveCount(0);
  // What is open with the customer is the queue's own rows for it (here the agreement in force), and the way to the complete queue.
  await expect(page.getByTestId("customer-all-tasks")).toHaveAttribute("href", "/deals?customer=BUYER-1&from=customer");
  await expect(none.getByRole("link", { name: "View the invoices" })).toHaveAttribute("href", "/receivables?customer=BUYER-1&invoice=RCV-A");
  await expect(none.getByRole("link", { name: "Stress-test payment" })).toHaveAttribute("href", "/cash?stress=BUYER-1:30&invoice=RCV-A&customer=BUYER-1&from=customer");
  // The economics and the exposure panels, each in the server's rows.
  await expect(page.getByTestId("customer-economics-rows-annual_sales")).toContainText("¥5,460,000");
  await expect(page.getByTestId("customer-economics-rows-annual_sales")).toContainText("projected from your books");
  await expect(page.getByTestId("customer-economics-rows-gross_margin")).toContainText("assumed for the Demo, not confirmed by you");
  // With nowhere to enter a fact (no `edit_href`) a row that only says "not entered yet" is left out: no dead ends.
  await expect(page.getByTestId("customer-economics-rows-classification")).toHaveCount(0);
  await expect(page.getByTestId("customer-economics-note")).toContainText("None of this changes what FLOW may do on its own.");
  // The facts are editable only where the server gives the place (`edit_href` is null until the economics flag is on).
  await expect(page.getByTestId("customer-edit")).toHaveCount(0);
  await expect(page.getByTestId("customer-exposure-rows-stress")).toContainText("Paid 30 days late");
  await expect(page.getByTestId("customer-exposure-rows-stress")).toContainText("¥550,000 uncovered");
  await expect(page.getByTestId("customer-exposure-note")).toContainText("The same figures as on the deal, on Receivables and on Cash");
  await expect(page.getByTestId("customer-history-row").first()).toContainText("In force");
  // The back link, with no context, is the server's plain one.
  await expect(page.getByTestId("customer-back")).toHaveText("Back to Deals");
  await expect(page.getByTestId("customer-back")).toHaveAttribute("href", "/deals");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  await expect(page.locator("body")).not.toContainText("BUYER-1");
  await scan(page, "/customers/BUYER-1 quiet");
});

test("a deal waiting: the decision card leads with its primary, and the back link puts the owner on that deal and path", async ({ page }) => {
  await checkedDeal(page);
  const query = await decisionQuery(page);
  const card = page.getByTestId("customer-decision");
  await expect(card).toContainText("One commercial decision waits for you");
  await expect(page.getByTestId("customer-decision-text")).toContainText("FLOW recommends countering with Option A, ¥3,027.77 once if accepted.");
  const primary = page.getByTestId("customer-decision-primary");
  await expect(primary).toHaveText("Review the counter");
  await expect(card.getByRole("link")).toHaveText(["Review the counter", "View the invoices", "Stress-test payment"]);
  await expect(page.getByTestId("customer-figure-outstanding-value")).toHaveText("¥420,000");
  await expect(page.getByTestId("customer-exposure-rows-capacity")).toContainText("if Foshan accepts Option A");
  // Opened from the deal and its path: the server's back link returns to both, and following the primary carries both to Deals.
  const decision = query.get("decision")!;
  const path = query.get("path")!;
  await page.goto(`/customers/BUYER-1?decision=${encodeURIComponent(decision)}&path=${encodeURIComponent(path)}`);
  const back = page.getByTestId("customer-back");
  await expect(back).toHaveText("Back to the Foshan deal");
  await expect(back).toHaveAttribute("href", `/deals?decision=${encodeURIComponent(decision)}&path=${encodeURIComponent(path)}`);
  await back.click();
  await expect(page).toHaveURL(new RegExp(`/deals\\?decision=${encodeURIComponent(decision).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}&path=`));
  // Opened from an invoice, the back link returns to that invoice.
  await page.goto("/customers/BUYER-1?invoice=RCV-A");
  await expect(page.getByTestId("customer-back")).toHaveText("Back to the invoices");
  await expect(page.getByTestId("customer-back")).toHaveAttribute("href", "/receivables?customer=BUYER-1&invoice=RCV-A");
  await scan(page, "/customers/BUYER-1 decision waiting");
});

test("an offer not yet read: the decision says so and its primary is Read the offer", async ({ page }) => {
  await page.goto("/deals");
  await openInbox(page);
  await page.getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("queue-check-button")).toBeVisible();
  await page.goto("/customers/BUYER-1");
  await expect(page.getByTestId("customer-decision")).toContainText("One offer waits to be read");
  await expect(page.getByTestId("customer-decision-primary")).toHaveText("Read the offer");
  await expect(page.getByTestId("customer-decision-primary")).toHaveAttribute("href", /^\/deals\?decision=/);
  await expect(page.getByTestId("customer-decision-authority")).toHaveCount(0);
});

test("after the day-0 plan the financing is linked, in the server's words", async ({ page }) => {
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("fix-result")).toContainText("2 executed");
  await page.goto("/customers/BUYER-1");
  await expect(page.getByTestId("customer-figure-financing-value")).toHaveText("¥255,000");
  await expect(page.getByTestId("customer-figure-financing-note")).toHaveText("financing arranged, expected in 3 days");
  await expect(page.getByTestId("customer-exposure-rows-financing")).toContainText("¥255,000 against the ¥420,000 invoice");
  await expect(page.getByTestId("customer-exposure-rows-financing_then")).toContainText("runs 30 days longer");
});

test("a customer link carries that row's own customer, decision and invoice and the origin, never what the address holds for another row (audit UX07, UX34)", async ({ page }) => {
  await checkedDeal(page);
  const query = await decisionQuery(page);
  const decision = encodeURIComponent(query.get("decision")!);
  // Receivables: the invoice row's own invoice and the origin `invoice`, whatever else the address names.
  await page.goto(`/receivables?decision=${decision}&path=${encodeURIComponent(query.get("path")!)}&invoice=RCV-A`);
  const row = page.getByTestId("recv-RCV-A");
  await expect(row).toBeVisible();
  await expect(row.getByRole("link", { name: "Foshan Home Retail Co." }).first()).toHaveAttribute("href", "/customers/BUYER-1?invoice=RCV-A&from=invoice");
  await page.goto("/receivables");
  await expect(page.getByTestId("recv-RCV-A").getByRole("link", { name: "Foshan Home Retail Co." })).toHaveAttribute("href", "/customers/BUYER-1?invoice=RCV-A&from=invoice");
  // Deals: the selected negotiation's customer carries that negotiation and the origin `deal`; so does the row in the queue.
  await page.goto(`/deals?customer=BUYER-1&decision=${decision}`);
  await expect(page.getByTestId("deal-selected-customer")).toHaveAttribute("href", `/customers/BUYER-1?decision=${decision}&from=deal`);
  await expect(page.getByTestId("queue-customer").first()).toHaveAttribute("href", `/customers/BUYER-1?decision=${decision}&from=deal`);
  await page.getByTestId("deal-selected-customer").click();
  await expect(page).toHaveURL(new RegExp(`/customers/BUYER-1\\?decision=.*&from=deal`));
  await expect(page.getByTestId("customer-back")).toHaveText("Back to the Foshan deal");
});

test("the customer link on Activity carries the context of the URL it is on", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/activity?invoice=RCV-A");
  // Activity holds no selection: its links carry the origin and nothing from the address.
  const link = page.locator("#activity-commitments").getByRole("link", { name: "Foshan Home Retail Co." }).first();
  await expect(link).toHaveAttribute("href", "/customers/BUYER-1?from=activity");
});

test("while the exposure read is off the panel says why, in the server's words, and the stress link is not offered", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-exposure-off", "1"));
  await page.goto("/customers/BUYER-1");
  await expect(page.getByTestId("customer-exposure-off")).toHaveText("Financial exposure is not switched on for this account, so payment behaviour, the late-payment test and spare capacity are not shown.");
  await expect(page.getByTestId("customer-exposure-rows")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Stress-test payment" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "View the invoices" })).toBeVisible();
  await scan(page, "/customers/BUYER-1 exposure off");
});

test("a customer the books do not hold says so and leads back to Deals", async ({ page }) => {
  await page.goto("/customers/NOBODY");
  await expect(page.getByTestId("customer-missing")).toContainText("We could not find this customer");
  await page.getByTestId("customer-missing").getByRole("link", { name: "Back to Deals" }).click();
  await expect(page).toHaveURL(/\/deals$/);
});

test("in Chinese the page reads in Chinese with the same figures", async ({ page }) => {
  await checkedDeal(page);
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.goto("/customers/BUYER-1");
  await expect(page.locator("h1")).toHaveText("Foshan Home Retail Co.");
  await expect(page.getByTestId("customer-figures").locator("dt")).toHaveText(["估算的全年毛利贡献", "未收款", "已关联的融资", "占您应收款的比例"]);
  await expect(page.getByTestId("customer-figure-outstanding-value")).toHaveText("¥420,000");
  await expect(page.getByRole("heading", { name: "客户经济状况" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "财务风险敞口" })).toBeVisible();
  await expect(page.getByTestId("customer-back")).toBeVisible();
  await expect(page.getByTestId("customer-exposure-rows-stress")).toContainText("晚付 30 天");
  await expect(page.getByTestId("customer-decision-primary")).toBeVisible();
  await scan(page, "/customers/BUYER-1 zh");
});

test("on a phone the figures and links fit, nothing scrolls sideways, and the links reach 44 px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await checkedDeal(page);
  await page.goto("/customers/BUYER-1");
  await expect(page.getByTestId("customer-decision-primary")).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  for (const key of ["value", "outstanding", "financing", "share"]) {
    const box = await page.getByTestId(`customer-figure-${key}`).boundingBox();
    expect(box && box.x >= 0 && box.x + box.width <= 390, key).toBeTruthy();
  }
  for (const name of ["Review the counter", "View the invoices", "Stress-test payment"]) {
    const box = await page.getByRole("link", { name, exact: true }).boundingBox();
    expect(box?.height ?? 0, name).toBeGreaterThanOrEqual(44);
  }
  await scan(page, "/customers/BUYER-1 phone");
});

/** The primary, whole, above the phone's tab bar: the first screen holds the question and its one action (390 x 844, the unread offer and the read one, both languages). */
for (const lang of ["en", "zh"] as const) {
  for (const moment of ["offer_received", "offer_evaluated"] as const) {
    test(`on a phone the primary is wholly in view above the tab bar: ${moment}, ${lang}`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      if (moment === "offer_evaluated") await checkedDeal(page);
      else {
        await page.goto("/deals");
        await openInbox(page);
        await page.getByTestId("inbox-msg-EX01").click();
        await expect(page.getByTestId("queue-check-button")).toBeVisible();
      }
      await page.evaluate((l) => localStorage.setItem("tl-lang", JSON.stringify({ lang: l })), lang);
      await page.goto("/customers/BUYER-1");
      const primary = page.getByTestId("customer-decision-primary");
      await expect(primary).toBeVisible();
      await expect(page.getByTestId("customer-decision")).toContainText(moment === "offer_received" ? (lang === "en" ? "One offer waits to be read" : "有一份报价等待阅读") : (lang === "en" ? "One commercial decision waits for you" : "有一项商务决定等待您处理"));
      const box = (await primary.boundingBox())!;
      const bar = (await page.getByTestId("tab-bar").boundingBox())!;
      expect(box.y).toBeGreaterThanOrEqual(0);
      expect(box.y + box.height, "the primary ends above the tab bar").toBeLessThanOrEqual(bar.y);
      expect(bar.y + bar.height).toBeLessThanOrEqual(844 + 1);
    });
  }
}

test("the keyboard, from the top of the page, reaches the back link, then the primary and the other two links in order", async ({ page }) => {
  await checkedDeal(page);
  await page.goto("/customers/BUYER-1");
  await expect(page.getByTestId("customer-decision-primary")).toBeVisible();
  const order: string[] = [];
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab");
    const id = await page.evaluate(() => document.activeElement?.getAttribute("data-testid") ?? "");
    if (id.startsWith("customer-")) order.push(id);
  }
  expect(order.slice(0, 4)).toEqual(["customer-back", "customer-decision-primary", "customer-action-invoices", "customer-action-stress"]);
});

/** In-spec patches of the recorded read (the mock's `tl-mock-overview-patch` key merges these fields over the recording): the fields the recording does not carry. */
async function patched(page: Page, patch: object) {
  await page.addInitScript((p) => sessionStorage.setItem("tl-mock-overview-patch", p), JSON.stringify(patch));
}

test("a partial read shows the existing notice with Retry, and the rest of the page stays", async ({ page }) => {
  await patched(page, { partial: { missing: ["receivables"], missing_text: ["receivables"], text: "Part of this page could not be read just now." } });
  await page.goto("/customers/BUYER-1");
  await expect(page.getByTestId("partial-read")).toContainText("Part of this page could not be read just now.");
  await expect(page.getByTestId("customer-figures")).toBeVisible();
  await page.getByTestId("partial-retry").click();
  await expect(page.getByTestId("partial-read")).toBeVisible();
});

test("with an edit place from the server, Edit these facts is a link and every fact row is shown", async ({ page }) => {
  await patched(page, { edit_href: "/customers/BUYER-1/inputs" });
  await page.goto("/customers/BUYER-1");
  await expect(page.getByTestId("customer-edit")).toHaveText("Edit these facts");
  await expect(page.getByTestId("customer-edit")).toHaveAttribute("href", "/customers/BUYER-1/inputs");
  await expect(page.getByTestId("customer-economics-rows-classification")).toContainText("not entered yet");
});

test("a history row with a link says where it goes and opens it", async ({ page }) => {
  await page.goto("/customers/BUYER-1");
  const terms = page.getByTestId("customer-history-row").getByRole("link", { name: "The terms" });
  await expect(terms).toHaveAttribute("href", "/documents");
  await terms.click();
  await expect(page).toHaveURL(/\/documents/);
});

test("a section the server did not send is not drawn, and the other panel takes the width", async ({ page }) => {
  await patched(page, { exposure: null, note: null, history: [] });
  await page.goto("/customers/BUYER-1");
  await expect(page.getByTestId("customer-economics-rows")).toBeVisible();
  await expect(page.locator("#customer-exposure")).toHaveCount(0);
  await expect(page.locator("#customer-history")).toHaveCount(0);
  const economics = (await page.locator("#customer-economics").boundingBox())!;
  const figures = (await page.getByTestId("customer-figures").boundingBox())!;
  expect(economics.width, "one panel spans the page").toBeGreaterThan(figures.width * 0.9);
});

test("the decision is a named region in both of its forms", async ({ page }) => {
  await page.goto("/customers/BUYER-1");
  await expect(page.getByRole("region", { name: "Commercial decision" })).toContainText("No commercial decision is waiting");
  await checkedDeal(page);
  await page.goto("/customers/BUYER-1");
  await expect(page.getByRole("region", { name: "One commercial decision waits for you" })).toBeVisible();
});
