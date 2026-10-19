import { expect, test } from "./fixtures";

/**
 * The buy side (ADR-0013) in mock mode: the recorded demo vendor contract (DOC-000004, a ¥600,000
 * die-cutting line: 30% on signing, 60% 45 days after delivery, 10% retention for 12 months after acceptance), its screen on
 * the owner's timeline, the commitment, financial health, loan eligibility and long-term plans. Every figure is the server's
 * recording (mocks/buyside).
 */

test("Deals is selling only: no buying card there; the purchases live on Capex & purchases, and Buying leads back to it", async ({ page }) => {
  // The owner (17 Oct): Deals stays purely the buyers' negotiations; the buy side is one page under Capex & purchases.
  await page.goto("/deals");
  await expect(page.getByTestId("deals-queue")).toBeVisible();
  await expect(page.getByTestId("deals-buying")).toHaveCount(0);
  await page.goto("/capex");
  await expect(page.getByTestId("capex-purchase-DOC-000004")).toBeVisible();
  await page.goto("/buy");
  await expect(page.getByTestId("purchase-DOC-000004")).toBeVisible();
  await page.getByTestId("back-to-capex").click();
  await expect(page).toHaveURL(/\/capex$/);
});

test("Capex is the buy side's one page: the health figures, every purchase, and the picked one worked through to the commitment", async ({ page }) => {
  await page.goto("/capex");
  await expect(page.getByTestId("capex-health")).toContainText("2.55×");
  const row = page.getByTestId("capex-purchase-DOC-000004");
  await expect(row).toContainText("¥600,000.00");
  await expect(row).toContainText("Ready to plan");
  await expect(row).toHaveAttribute("aria-expanded", "false");
  // the quick check without a contract stays on the page, below the purchases
  await expect(page.getByTestId("capex-quick")).toHaveAttribute("open", "");
  await expect(page.getByRole("button", { name: "Evaluate the ¥600k machine" })).toBeVisible();

  await row.click();
  await expect(page).toHaveURL(/\/capex\?purchase=DOC-000004$/);
  await expect(row).toHaveAttribute("aria-expanded", "true");
  const bench = page.getByTestId("capex-bench-DOC-000004");
  await bench.getByTestId("buy-evaluate").click();
  await expect(bench.getByTestId("buy-schedule").locator("tbody tr")).toHaveCount(3);
  await expect(bench.getByTestId("buy-structure-loan_36m")).toContainText("Selected");
  await bench.getByTestId("buy-commit").click();
  await expect(bench.getByTestId("buy-committed")).toContainText("Queued for your approval");

  await page.getByTestId("capex-bench-close").click();
  await expect(page).toHaveURL(/\/capex$/);
  await expect(page.getByTestId("capex-bench-DOC-000004")).toHaveCount(0);
});

test("a vendor contract's schedule, financing and early payment, then the commitment", async ({ page }) => {
  await page.goto("/buy/contract?id=DOC-000004");
  await page.getByTestId("buy-evaluate").click();
  const rows = page.getByTestId("buy-schedule").locator("tbody tr");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText("¥180,000.00");
  await expect(rows.nth(1)).toContainText("¥352,800.00"); // the early payment is taken: the server recommends it on this timeline
  await expect(rows.nth(2)).toContainText("¥60,000.00");
  await expect(page.getByTestId("buy-early")).toContainText("Take it");
  await expect(page.getByTestId("buy-beyond")).toContainText("¥60,000.00");
  await expect(page.getByTestId("buy-structure-loan_36m")).toContainText("Selected");

  await page.getByTestId("buy-early-take").uncheck();
  await expect(rows.nth(1)).toContainText("¥360,000.00");

  await page.getByTestId("buy-commit").click();
  await expect(page.getByTestId("buy-committed")).toContainText("Queued for your approval");
});

test("signing on the contract's own date breaks the reserve, and the page says why", async ({ page }) => {
  await page.goto("/buy/contract?id=DOC-000004");
  await page.getByTestId("timeline-signing_day").fill("");
  await page.getByTestId("buy-evaluate").click();
  await expect(page.getByTestId("buy-summary")).toContainText("No structure holds every covenant");
  await expect(page.getByTestId("buy-structure-loan_36m")).toContainText("comes before the Equipment term loan proceeds land");
});

test("a missing day is asked for, not guessed", async ({ page }) => {
  await page.goto("/buy/contract?id=DOC-000004");
  await page.getByTestId("timeline-delivery_day").fill("");
  await page.getByTestId("buy-evaluate").click();
  await expect(page.getByTestId("buy-reasons")).toContainText("Give the delivery day and the acceptance day");
  await expect(page.getByTestId("buy-commit")).toHaveCount(0);
});

test("financial health, the owner's ratios and loan eligibility", async ({ page }) => {
  await page.goto("/finance");
  await expect(page.getByTestId("finance-summary")).toContainText("Cash falls below your ¥300,000.00 minimum on day 12");
  await expect(page.getByTestId("finance-stats")).toContainText("2.55×");
  await expect(page.getByTestId("finance-capacity")).toContainText("Equipment term loan");
  await expect(page.getByTestId("finance-liquidity")).toContainText("need your inventory");

  await page.getByTestId("finance-ratios").locator("summary").first().click();
  await page.getByTestId("finance-inventory_fen").fill("300000");
  await page.getByTestId("finance-other_current_assets_fen").fill("0");
  await page.getByTestId("finance-trade_payables_fen").fill("250000");
  await page.getByTestId("finance-other_current_liabilities_fen").fill("50000");
  await page.getByTestId("finance-read-ratios").click();
  await expect(page.getByTestId("finance-liquidity")).toContainText("Current ratio 1.33×, quick ratio 0.98×");

  await expect(page.getByTestId("finance-indicative")).toContainText("Indicative only");
  await expect(page.getByTestId("product-PRD-BANK2-GGL-36")).toContainText("Not eligible");
  await page.getByTestId("finance-months").fill("48");
  await page.getByTestId("finance-read-loans").click();
  await expect(page.getByTestId("product-PRD-BANK1-TERM-60")).toContainText("Eligible up to a limit");
  await page.getByTestId("add-PRD-BANK1-TERM-60").click();
  await expect(page.getByTestId("finance-added")).toContainText("Queued for your approval");
});

test("long-term plans rank the permutations and say what the limits cost", async ({ page }) => {
  await page.goto("/plans");
  await page.getByTestId("plans-run").click();
  await expect(page.getByTestId("plans-result")).toBeVisible();
  await expect(page.getByTestId("plan-1")).toContainText("Worth ¥");
  await expect(page.getByTestId("plans-unconstrained")).toContainText("above the ¥600,000.00 left on it");
  await expect(page.getByTestId("plans-daily")).toContainText("passes the daily test");
});

test("the buying pages stay in the Business shell, each with its way back", async ({ page }) => {
  for (const [path, back, label] of [
    ["/buy", "back-to-capex", "Back to Capex & purchases"],
    ["/buy/contract?id=DOC-000004", "back-to-buy", "Back to Buying"],
    ["/finance", "back-to-buy", "Back to Buying"],
    ["/plans", "back-to-buy", "Back to Buying"],
  ] as const) {
    await page.goto(path);
    await expect(page.getByTestId("demo-strip")).toHaveCount(0);
    await expect(page.getByTestId("back-to-business")).toHaveCount(0);
    await expect(page.getByTestId(back)).toHaveText(label);
  }
  await page.goto("/buy");
  await page.getByTestId("buy-door-finance").click();
  await expect(page).toHaveURL(/\/finance$/);
  await page.getByTestId("back-to-buy").click();
  await expect(page).toHaveURL(/\/buy$/);
  await expect(page.getByTestId("buy-doors")).toContainText("Long-term plans");
});

test("the approval of a purchase shows the schedule the owner is committing to, in the server's words", async ({ page }) => {
  await page.goto("/buy/contract?id=DOC-000004");
  await page.getByTestId("buy-evaluate").click();
  await page.getByTestId("buy-commit").click();
  await expect(page.getByTestId("buy-committed")).toContainText("Queued for your approval");
  await page.goto("/approvals");
  const schedule = page.getByTestId("approval-schedule-APR-000001");
  await expect(schedule).toBeVisible();
  await expect(schedule).toContainText("What you are committing to");
  await expect(schedule).toContainText("Guangzhou Precision Machinery Co., Ltd.");
  await expect(schedule).toContainText("Equipment purchase contract GZPM-2026-114");
  await expect(schedule).toContainText("¥180,000.00, in 20 days");
  await expect(schedule).toContainText("¥360,000.00, in 105 days");
  await expect(schedule).toContainText("¥60,000.00, in 440 days (retention)");
  await expect(schedule).toContainText("Not taken: every payment is made on its day");
  await expect(schedule).toContainText("¥600,000.00");
});
