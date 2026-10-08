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
  await expect(row).toContainText("in 32 days");
  // The record id is a level-2 fact: not in the row, one chevron down.
  await expect(row).not.toContainText("RCV-A");
  await page.getByTestId("recv-toggle-RCV-A").click();
  await expect(page.getByTestId("recv-detail-RCV-A")).toContainText("RCV-A");
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
  // The buyer is a monogram and a name; the invoice id waits behind the row's chevron (level 2).
  await expect(rows.first()).not.toContainText("RCV-A");
  await expect(rows.first().locator("td").nth(1)).toContainText("Foshan Home Retail Co.");
  await page.getByTestId("recv-toggle-RCV-A").click();
  await expect(page.getByTestId("recv-detail-RCV-A")).toContainText("RCV-A");
  await expect(page.getByRole("heading", { name: "Expected early payments" })).toBeVisible();
  await expect(page.getByTestId("promised-RCV-A")).toContainText("¥255,013.80");
  await expect(page.getByRole("heading", { name: "Payments received" })).toBeVisible();
  await expect(page.getByTestId("receipt-rec-receipt-1")).toContainText("Foshan Home Retail Co.");
  // The record ids (the invoice, the bank's reference) are one fold down; the sentences use names.
  const receipts = page.locator("#recv-receipts");
  await expect(receipts.getByTestId("receipt-audit-rec-receipt-1")).not.toHaveAttribute("open", "");
  await expect(receipts.getByTestId("receipt-audit-rec-receipt-1")).toContainText("DEMO-RCPT-1");
  await expect(page.getByTestId("receipt-ref-rec-receipt-1")).toContainText("DEMO-RCPT-1");
  const promised = await page.locator("#recv-promised").innerText();
  const received = await receipts.innerText();
  expect(promised + received).not.toMatch(/CMT-|RI:|DEMO-RCPT/);
  await expect(page.getByTestId("promised-RCV-A")).toContainText("the ¥420,000.00 invoice to Foshan Home Retail Co.");
});
