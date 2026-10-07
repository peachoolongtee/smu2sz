import { expect, test } from "./fixtures";

/**
 * The Business Activity page in mock mode: every row leads with the executor's sentence in business words (names, not ids,
 * and distances from today), with the plain operation name as a muted label; the codes and hashes are audit details, closed.
 * The recorded demo path: day 34, the owner queues the fix for approval.
 */

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded demo path");
});

test("each row leads with the executor's sentence, the operation name is a muted label, and the hashes are audit details", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await page.getByTestId("fix-ALERT-RESERVE-42").click();
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toBeVisible();

  await page.goto("/activity");
  const rows = page.getByTestId("activity-list").locator("li");
  await expect(rows.first()).toBeVisible();
  const row = page.getByTestId("activity-SUBMIT_INVOICE_FOR_FINANCING").first();
  // The sentence is the row's heading line; the operation's plain name sits beside the day as a label.
  const sentence = row.locator("p").first();
  await expect(sentence).toContainText("Queued for owner approval (APR-000001)");
  await expect(row.getByTestId("activity-op")).toHaveText("Get cash early on an invoice");
  await expect(row).toContainText("today");
  // Codes and hashes stay under Audit details, closed until opened.
  const audit = row.locator("details");
  await expect(audit).not.toHaveAttribute("open", "");
  await audit.locator("summary").click();
  await expect(audit).toContainText("Tier 2");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
});
