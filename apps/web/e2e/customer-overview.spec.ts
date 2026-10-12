import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { runPlan } from "./helpers";

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

const AFTER_CHECK = /Don't accept as asked|Counter instead of accepting as asked/;

/** The package offer received and read, as the owner does it on Deals: the books then hold one open decision with Foshan. */
async function checkedDeal(page: Page) {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-recommendation")).toContainText(AFTER_CHECK);
}

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
  await expect(figures.locator("dt")).toHaveText(["Relationship value", "Outstanding", "Financing linked", "Share of what you are owed"]);
  await expect(page.getByTestId("customer-figure-outstanding-value")).toHaveText("¥420,000");
  await expect(page.getByTestId("customer-figure-outstanding-note")).toHaveText("due in 32 days, nothing overdue");
  await expect(page.getByTestId("customer-figure-share-value")).toHaveText("100%");
  await expect(page.getByTestId("customer-figure-share-note")).toHaveText("one open invoice; not its share of your sales");
  // The Demo's sales and margin give the server's estimate; the browser makes none of its own.
  await expect(page.getByTestId("customer-figure-value-value")).toHaveText("about ¥1.09m");
  await expect(page.getByTestId("customer-figure-value-note")).toHaveText("a year, estimated contribution");
  // No decision waits: the server's line, the two links that remain, and no filled primary on the page.
  const none = page.getByTestId("customer-decision-none");
  await expect(none).toContainText("No commercial decision is waiting for you with Foshan.");
  await expect(none.getByRole("link")).toHaveText(["View the invoices", "Stress-test payment"]);
  await expect(page.getByTestId("customer-decision")).toHaveCount(0);
  await expect(none.getByRole("link", { name: "View the invoices" })).toHaveAttribute("href", "/receivables?customer=BUYER-1&invoice=RCV-A");
  await expect(none.getByRole("link", { name: "Stress-test payment" })).toHaveAttribute("href", "/cash?stress=BUYER-1:30&invoice=RCV-A");
  // The economics and the exposure panels, each in the server's rows.
  await expect(page.getByTestId("customer-economics-rows-annual_sales")).toContainText("¥5,460,000");
  await expect(page.getByTestId("customer-economics-rows-annual_sales")).toContainText("projected from your books");
  await expect(page.getByTestId("customer-economics-rows-gross_margin")).toContainText("assumed for the Demo, not confirmed by you");
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
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" })).toBeVisible();
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

test("the names on Receivables and Deals link to the overview carrying the decision, the path and the invoice from the URL", async ({ page }) => {
  await checkedDeal(page);
  const query = await decisionQuery(page);
  const ctx = `decision=${encodeURIComponent(query.get("decision")!)}&path=${encodeURIComponent(query.get("path")!)}`;
  // Receivables: the invoice's buyer, with the context of the URL it was opened on.
  await page.goto(`/receivables?${ctx}&invoice=RCV-A`);
  const row = page.getByTestId("recv-RCV-A");
  await expect(row).toBeVisible();
  const link = row.getByRole("link", { name: "Foshan Home Retail Co." }).first();
  await expect(link).toHaveAttribute("href", `/customers/BUYER-1?${ctx}&invoice=RCV-A`);
  // Without a context the link is the plain one.
  await page.goto("/receivables");
  await expect(page.getByTestId("recv-RCV-A").getByRole("link", { name: "Foshan Home Retail Co." })).toHaveAttribute("href", "/customers/BUYER-1");
  // Deals: the buyer of the selected deal.
  await page.goto(`/deals?${ctx}`);
  await expect(page.getByTestId("deal-selected-customer")).toHaveAttribute("href", `/customers/BUYER-1?${ctx}`);
  await page.getByTestId("deal-selected-customer").click();
  await expect(page).toHaveURL(/\/customers\/BUYER-1\?decision=/);
  await expect(page.getByTestId("customer-back")).toHaveText("Back to the Foshan deal");
});

test("Activity: the agreement's buyer is a link to the overview", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/activity?invoice=RCV-A");
  const link = page.locator("#activity-commitments").getByRole("link", { name: "Foshan Home Retail Co." }).first();
  await expect(link).toHaveAttribute("href", "/customers/BUYER-1?invoice=RCV-A");
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
  await expect(page.getByTestId("customer-figures").locator("dt")).toHaveText(["客户关系价值", "未收款", "已关联的融资", "占您应收款的比例"]);
  await expect(page.getByTestId("customer-figure-outstanding-value")).toHaveText("¥420,000");
  await expect(page.getByRole("heading", { name: "客户经济状况" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "财务风险敞口" })).toBeVisible();
  await expect(page.getByTestId("customer-back")).toBeVisible();
  await expect(page.getByTestId("customer-exposure-rows-stress")).toContainText("晚付 30 天");
  await expect(page.getByTestId("customer-decision-primary")).toBeVisible();
  await scan(page, "/customers/BUYER-1 zh");
});

test("on a phone the primary is in the first screen and nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await checkedDeal(page);
  await page.goto("/customers/BUYER-1");
  await expect(page.getByTestId("customer-decision-primary")).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  // The four figures sit two by two; each stays inside the screen.
  for (const key of ["value", "outstanding", "financing", "share"]) {
    const box = await page.getByTestId(`customer-figure-${key}`).boundingBox();
    expect(box && box.x >= 0 && box.x + box.width <= 390, key).toBeTruthy();
  }
  // The links reach 44 px where a finger is the pointer.
  for (const name of ["Review the counter", "View the invoices", "Stress-test payment"]) {
    const box = await page.getByRole("link", { name, exact: true }).boundingBox();
    expect(box?.height ?? 0, name).toBeGreaterThanOrEqual(44);
  }
  await scan(page, "/customers/BUYER-1 phone");
});

test("the keyboard reaches the back link first, then the decision's links in order", async ({ page }) => {
  await checkedDeal(page);
  await page.goto("/customers/BUYER-1");
  await expect(page.getByTestId("customer-decision-primary")).toBeVisible();
  await page.getByTestId("customer-back").focus();
  await expect(page.getByTestId("customer-back")).toBeFocused();
  const order: string[] = [];
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    const id = await page.evaluate(() => document.activeElement?.getAttribute("data-testid") ?? "");
    if (id) order.push(id);
  }
  expect(order.indexOf("customer-decision-primary")).toBeGreaterThanOrEqual(0);
  expect(order.indexOf("customer-action-invoices")).toBeGreaterThan(order.indexOf("customer-decision-primary"));
  expect(order.indexOf("customer-action-stress")).toBeGreaterThan(order.indexOf("customer-action-invoices"));
});
