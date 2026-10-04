import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

/**
 * Mock-mode specs for the API changes the web caught up with: the alert act bound to what was shown (409 ALERT_CHANGED),
 * the MANDATE_EXPIRING alert, and the bank reference on the reconciliation receipts. The mock replays recordings of the
 * live API (the live equivalents are in live.spec.ts), and the 409 path is a mock variant switched on through sessionStorage.
 */

const MOVE_BOOKS_KEY = "tl-mock-books-moved";

/** The home's clock control moves the clock by days (from `from`), and the day it reaches is shown. */
async function advanceTo(page: Page, day: number, from = 0) {
  await page.getByTestId("home-days").fill(String(day - from));
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText(`Day ${day}`);
}

test("the books move after the alert was shown: 409 says so, shows the current alert, runs nothing and is not styled as success", async ({ page }) => {
  await page.goto("/");
  await advanceTo(page, 34);
  await page.evaluate((k) => sessionStorage.setItem(k, "1"), MOVE_BOOKS_KEY);
  await page.getByTestId("fix-ALERT-RESERVE-42").click();

  const changed = page.getByTestId("fix-changed");
  await expect(changed).toBeVisible();
  await expect(changed).toContainText("The books changed since this was shown");
  await expect(changed).toContainText("Nothing was run");
  await expect(changed).toHaveAttribute("role", "alert");
  // The current alert is shown, with its cost, for the owner to review.
  await expect(page.getByTestId("fix-changed-alert")).toContainText("Reserve breach ahead on day 42");
  await expect(page.getByTestId("fix-changed-alert")).toContainText("Cost ¥1,782.19");
  // No success styling, no executed result, nothing queued.
  await expect(changed).toHaveClass(/text-warn-fg/);
  await expect(changed).not.toHaveClass(/text-ok-fg|bg-ok-bg/);
  await expect(page.getByTestId("fix-result")).toHaveCount(0);
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toHaveCount(0);
  await expect(page.getByTestId("home-done-SUBMIT_INVOICE_FOR_FINANCING")).toHaveCount(0);

  // The list was refetched with the new version, so pressing again acts on what is shown now: it queues the cure, still not as success.
  await page.getByTestId("fix-ALERT-RESERVE-42").click();
  const op = page.getByTestId("fix-result").getByTestId("chat-op-SUBMIT_INVOICE_FOR_FINANCING");
  await expect(op).toHaveAttribute("data-status", "PENDING_APPROVAL");
  await expect(op.getByTestId("op-state")).toContainText("Waiting for your approval");
  await expect(op.getByTestId("op-state").locator(":scope > span")).not.toHaveClass(/text-ok-fg/);
  await expect(page.getByTestId("fix-changed")).toHaveCount(0);
});

test("the books move and the alert is gone: the 409 says the alert no longer applies", async ({ page }) => {
  await page.goto("/");
  await advanceTo(page, 34);
  await page.evaluate((k) => sessionStorage.setItem(k, "gone"), MOVE_BOOKS_KEY);
  await page.getByTestId("fix-ALERT-RESERVE-42").click();
  await expect(page.getByTestId("fix-changed")).toContainText("The books changed since this was shown");
  await expect(page.getByTestId("fix-changed-gone")).toContainText("That alert is gone");
  await expect(page.getByTestId("fix-changed-alert")).toHaveCount(0);
  await expect(page.getByTestId("fix-result")).toHaveCount(0);
});

test("MANDATE_EXPIRING: a warning 14 days before, critical once expired; information only, no button", async ({ page }) => {
  await page.goto("/");
  await advanceTo(page, 80);
  await page.getByRole("link", { name: "Alerts", exact: true }).click();
  const warning = page.locator("#alert-ALERT-MANDATE-EXPIRY");
  await expect(warning).toContainText("Mandate v1 expires in 10 day(s)");
  await expect(warning).toContainText("Mandate expiring");
  await expect(warning.getByTestId("alert-info-only")).toContainText("Renewal is a step you take offline");
  await expect(warning.getByRole("button")).toHaveCount(0);
  await expect(warning.getByText("Warning", { exact: true })).toBeVisible();

  await page.getByRole("navigation").getByRole("link", { name: "Home", exact: true }).first().click();
  await advanceTo(page, 95, 80);
  await page.getByRole("link", { name: "Alerts", exact: true }).click();
  const expired = page.locator("#alert-ALERT-MANDATE-EXPIRY");
  await expect(expired).toContainText("mandate expired: the agent can no longer act");
  await expect(expired.getByText("Critical", { exact: true })).toBeVisible();
  await expect(expired.getByTestId("alert-info-only")).toBeVisible();
  await expect(expired.getByRole("button")).toHaveCount(0);
});

test("reconciliation lists the bank's reference on a receipt that carries one", async ({ page }) => {
  await page.goto("/");
  await advanceTo(page, 34);
  await page.getByRole("link", { name: "Payments received", exact: true }).click();
  await expect(page).toHaveURL(/\/reconciliation/);
  const receipts = page.getByRole("table", { name: "Receipts" }).or(page.locator("#receipts"));
  await expect(receipts.getByTestId("receipt-rec-receipt-1")).toContainText("RCV-A");
  await expect(receipts.getByTestId("receipt-ref-rec-receipt-1")).toContainText("Bank reference DEMO-RCPT-1");
});
