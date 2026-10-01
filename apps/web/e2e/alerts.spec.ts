import { expect, test } from "./fixtures";
import { resetBooks } from "./helpers";

/**
 * Alerts panel (GET /alerts) and reconciliation view (GET /reconciliation) on the opening books.
 * Runs in both projects: mock mode serves a recording of the same server output, live mode calls the API.
 */

test("alerts: the day-12 reserve breach shows its amounts, formula and committed cure", async ({ page, request }) => {
  await resetBooks(request);
  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Cash-flow alerts", level: 1 })).toBeVisible();

  await expect(page.getByTestId("alert-count-CRITICAL")).toContainText("1 Critical");
  await expect(page.getByRole("heading", { name: "Reserve breach ahead on day 12" })).toBeVisible();
  await expect(page.getByText("A committed cure exists", { exact: true })).toBeVisible();
  // Every figure is the server's string: the shortfall, and the two suggested operations (never auto-executed).
  await expect(page.getByText("¥240,000.00").first()).toBeVisible();
  await expect(page.getByText("¥150,000.00").first()).toBeVisible();
  await expect(page.getByText("¥336,000.00").first()).toBeVisible();
  // The note is the server's: live says "...executed only through POST /alerts/{id}/act...", an older recording says "never executed automatically".
  await expect(page.getByText(/never executed automatically|executed only through POST \/alerts\/\{id\}\/act/i).first()).toBeVisible();
});

test("reconciliation: no receipts yet, one outstanding receivable, chain valid", async ({ page, request }) => {
  await resetBooks(request);
  await page.goto("/reconciliation");
  await expect(page.getByRole("heading", { name: "Receipt reconciliation", level: 1 })).toBeVisible();

  await expect(page.getByText("No receipts in the log yet")).toBeVisible();
  const outstanding = page.getByRole("table", { name: "Outstanding receivables" });
  await expect(outstanding).toContainText("RCV-A");
  await expect(outstanding).toContainText("¥420,000.00");
  await expect(page.getByText("Chain valid").first()).toBeVisible();
});

test("alerts and reconciliation are reachable from the navigation", async ({ page }) => {
  await page.goto("/mandate");
  await page.getByRole("link", { name: "Alerts" }).click();
  await expect(page).toHaveURL(/\/alerts/);
  await page.getByRole("link", { name: "Reconciliation" }).click();
  await expect(page).toHaveURL(/\/reconciliation/);
});
