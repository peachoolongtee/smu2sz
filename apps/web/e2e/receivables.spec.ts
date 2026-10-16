import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { openOperatorTools } from "./helpers";

/**
 * The Receivables page of before (the fallback while the server has no GET /receivables; the page on that read is e2e/receivables-layers.spec.ts).
 * Every test here sets the mock's "route absent" hook so it keeps covering the reads the fallback uses.
 *
 * The Business Receivables page in mock mode: the summary first (outstanding, overdue, the next payment, all server strings
 * from GET /home), then the invoices with late rows first, then the early payments and the payments received only when
 * there are any. No standing empty panels.
 */

test.beforeEach(async ({ context }, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded demo path");
  await context.addInitScript(() => {
    try {
      sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: "mock-owner" }));
      sessionStorage.setItem("tl-mock-receivables-absent", "1");
    } catch {
      /* storage unavailable */
    }
  });
});

/** The story page's clock moves the simulated day; the page is then opened as the owner does. */
async function advanceTo34(page: Page) {
  await page.goto("/demo");
  await openOperatorTools(page);
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
  await expect(page.getByTestId("recv-overdue")).toHaveText("¥160,000.00");
  // Overdue first: its heading row leads the table, then the late invoice, then the heading over the rest.
  await expect(page.getByTestId("recv-group-overdue")).toHaveText("Overdue first");
  // "Not overdue" until the collections ranking is on; with it (the strategy build) the heading says what orders the rest.
  await expect(page.getByTestId("recv-group-rest")).toHaveText(/^(Not overdue|Ranked by what collecting saves you)$/);
  const rows = page.locator("#recv-open tbody tr:not([data-group])");
  await expect(rows.first()).toHaveAttribute("data-testid", "recv-RCV-A");
  await expect(rows.first()).toContainText("Foshan Home Retail Co.");
  await expect(rows.first()).toContainText("2 days late");
  await expect(rows.first()).toContainText("2 days ago");
  // The buyer is a monogram and a name; the invoice id waits behind the row's chevron (level 2).
  await expect(rows.first()).not.toContainText("RCV-A");
  await page.getByTestId("recv-toggle-RCV-A").click();
  await expect(page.getByTestId("recv-detail-RCV-A")).toContainText("RCV-A");
  await expect(page.getByRole("heading", { name: "Expected early payments" })).toBeVisible();
  await expect(page.getByTestId("promised-RCV-A")).toContainText("¥257,790.00");
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

test("day 34: the full list leads with the overdue invoice, and the red Overdue tile applies the Late filter", async ({ page }) => {
  await advanceTo34(page);
  const open = page.locator("#recv-open");
  await expect(open.getByTestId("recv-group-overdue")).toHaveText("Overdue first");
  await expect(open.getByTestId("recv-group-rest")).toBeVisible();
  const all = page.getByTestId("recv-filter-all");
  await expect(all).toHaveAttribute("aria-pressed", "true");
  // The tile is a real button: a tap on it shows the late invoices only, and the headings (which name the groups of the whole list) step aside.
  const tile = page.getByTestId("recv-overdue-show");
  await expect(tile).toHaveText("Show the late invoices");
  await tile.click();
  await expect(page.getByTestId("recv-filter-late")).toHaveAttribute("aria-pressed", "true");
  await expect(open.locator("tbody tr[data-testid^='recv-RCV']")).toHaveCount(1);
  await expect(open.getByTestId("recv-group-overdue")).toHaveCount(0);
  await all.click();
  await expect(open.getByTestId("recv-group-overdue")).toBeVisible();
  // Keyboard: the same button, reached by Tab and pressed with Enter.
  await tile.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("recv-filter-late")).toHaveAttribute("aria-pressed", "true");
});

test("day 0: nothing is overdue, so there are no group headings and the Overdue tile is not a button", async ({ page }) => {
  await page.goto("/receivables");
  await expect(page.getByTestId("recv-RCV-A")).toBeVisible();
  await expect(page.getByTestId("recv-overdue-show")).toHaveCount(0);
  await expect(page.locator('[data-testid^="recv-group-"]')).toHaveCount(0);
});

/** Day 34 on the books where the buyer paid half on day 2: the part-paid promise, the balance still owed and the window ended. */
async function advanceTo34Half(page: Page) {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-no-receipt", "half"));
  await advanceTo34(page);
}

test("day 0: nothing is late or at risk, so no row offers Chase payment", async ({ page }) => {
  await page.goto("/receivables");
  await expect(page.getByTestId("recv-RCV-A")).toBeVisible();
  await expect(page.locator('[data-testid^="chase-open-"]')).toHaveCount(0);
});

test("day 34: only the late invoice offers Chase payment; the dialog holds the server's facts and the request, and Copy copies it", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await advanceTo34(page);
  // The two invoices still to come are neither late nor inside the shortfall.
  await expect(page.locator('[data-testid^="chase-open-"]')).toHaveCount(1);
  const open = page.getByTestId("chase-open-RCV-A");
  await expect(open).toHaveText("Chase payment");
  // The normal rule: 32 px on a desktop, 44 px wherever a finger is the pointer.
  expect((await open.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(32);
  await open.click();
  const dialog = page.getByTestId("chase-dialog-RCV-A");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "Chase payment: Foshan Home Retail Co." })).toBeVisible();
  await expect(dialog.getByTestId("chase-fact-outstanding")).toContainText("¥160,000.00");
  await expect(dialog.getByTestId("chase-fact-invoice")).toContainText("¥420,000.00");
  await expect(dialog.getByTestId("chase-fact-late")).toContainText("2 days");
  await expect(dialog.getByTestId("chase-fact-terms")).toContainText("45 days");
  await expect(dialog.getByTestId("chase-fact-promise-0")).toContainText("¥257,790.00");
  const request = dialog.getByTestId("chase-request");
  await expect(request).toContainText("Dear Foshan Home Retail Co.");
  await expect(request).toContainText("¥160,000.00 remains outstanding");
  const asked = await request.innerText();
  expect(asked).not.toMatch(/CMT-|RCV-|\bday \d/);
  // One Primary inside the dialog: Copy. "Open the buyer thread" is a link in the Deals route when a thread exists.
  await expect(dialog.getByTestId("chase-copy")).toHaveText("Copy request");
  await expect(dialog.getByTestId("chase-thread")).toHaveAttribute("href", "/deals?buyer=BUYER-1");
  await expect(dialog.getByTestId("chase-copy-status")).toHaveText("");
  await dialog.getByTestId("chase-copy").click();
  await expect(dialog.getByTestId("chase-copy-status")).toHaveText("Copied");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(asked);
  // Esc closes it and focus returns to the control that opened it.
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(open).toBeFocused();
});

test("day 34 after the half receipt: the chase dialog's balance is the one the page shows, and the receipt row names its four facts", async ({ page }) => {
  await advanceTo34Half(page);
  await expect(page.getByTestId("recv-overdue")).toHaveText("¥290,000.00");
  await page.getByTestId("chase-open-RCV-A").click();
  const dialog = page.getByTestId("chase-dialog-RCV-A");
  await expect(dialog.getByTestId("chase-fact-outstanding")).toHaveText(/¥290,000\.00/);
  await expect(dialog.getByTestId("chase-request")).toContainText("¥290,000.00 remains outstanding");
  await dialog.getByTestId("chase-close").click();
  await expect(dialog).toBeHidden();
  // F25: the receipt row on the Receivables page, not only the Home change row, states received, face cleared, discount, remaining and the window.
  const facts = page.getByTestId("receipt-facts-rec-receipt-1");
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-received")).toContainText("¥128,895.00");
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-cleared")).toContainText("¥130,000.00");
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-discount")).toContainText("¥1,105.00");
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-remaining")).toContainText("¥290,000.00");
  await expect(facts).toContainText("The early-payment window has ended");
});

test("day 34 in Chinese: the handoff and the request are the server's Chinese", async ({ page }) => {
  await advanceTo34(page);
  const menu = page.getByTestId("account-menu");
  if ((await menu.count()) && !(await menu.evaluate((el) => (el as HTMLDetailsElement).open))) await menu.locator("> summary").click();
  await page.getByLabel("中文").check();
  await page.getByTestId("chase-open-RCV-A").click();
  await expect(page.getByTestId("chase-request")).toContainText("请确认付款日期");
});
