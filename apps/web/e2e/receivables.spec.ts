import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

/**
 * The Business Receivables page in mock mode: the summary first (outstanding, overdue, the next payment, all server strings
 * from GET /home), then the invoices with late rows first, then the early payments and the payments received only when
 * there are any. No standing empty panels.
 */

test.beforeEach(async ({ context }, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded demo path");
  await context.addInitScript(() => {
    try {
      sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: "mock-owner" }));
    } catch {
      /* storage unavailable */
    }
  });
});

/** The story page's clock moves the simulated day; the page is then opened as the owner does. */
async function advanceTo34(page: Page) {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/receivables");
}

test("day 0: the summary answers who owes what, with no empty panels", async ({ page }) => {
  await page.goto("/receivables");
  const summary = page.getByTestId("recv-summary");
  await expect(summary.getByTestId("recv-outstanding")).toHaveText("¥420,000.00");
  await expect(summary.getByTestId("recv-overdue")).toHaveText("¥0.00");
  await expect(summary.getByTestId("recv-next-amount")).toHaveText("¥420,000.00");
  await expect(summary.getByTestId("recv-next-hint")).toHaveText("Foshan Home Retail Co., due in 32 days");
  await expect(page.getByTestId("recv-none")).toHaveCount(0);
  const row = page.getByTestId("recv-RCV-A");
  await expect(row).toContainText("Foshan Home Retail Co.");
  await expect(row).toContainText("RCV-A");
  await expect(row).toContainText("in 32 days");
  await expect(page.getByRole("heading", { name: "Expected early payments" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Payments received" })).toHaveCount(0);
  await expect(page.locator("#recv-promised, #recv-receipts")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
});

test("day 34: the late invoice leads, the overdue total is the server's, and the early payment and receipt appear", async ({ page }) => {
  await advanceTo34(page);
  await expect(page.getByTestId("recv-overdue")).toHaveText("¥162,800.00");
  const rows = page.locator("#recv-open tbody tr");
  await expect(rows.first()).toHaveAttribute("data-testid", "recv-RCV-A");
  await expect(rows.first()).toContainText("Foshan Home Retail Co.");
  await expect(rows.first()).toContainText("2 days late");
  await expect(rows.first()).toContainText("2 days ago");
  // The invoice id is a muted second line under the buyer, not part of the name.
  await expect(rows.first().locator("td").first()).toContainText("Foshan Home Retail Co.");
  await expect(rows.first().locator("td").first().locator("span.block")).toHaveText("RCV-A");
  await expect(page.getByRole("heading", { name: "Expected early payments" })).toBeVisible();
  await expect(page.getByTestId("promised-RCV-A")).toContainText("¥255,013.80");
  await expect(page.getByRole("heading", { name: "Payments received" })).toBeVisible();
  await expect(page.getByTestId("receipt-rec-receipt-1")).toContainText("Foshan Home Retail Co.");
  await expect(page.getByTestId("receipt-ref-rec-receipt-1")).toContainText("DEMO-RCPT-1");
});
