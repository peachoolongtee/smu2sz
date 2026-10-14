import { expect, test } from "./fixtures";
import { resetBooks } from "./helpers";

/**
 * Alerts panel (GET /alerts) and reconciliation view (GET /reconciliation) on the opening books.
 * Runs in both projects: mock mode serves a recording of the same server output, live mode calls the API.
 */

test("alerts: the day-12 reserve breach shows its amounts, formula and fix", async ({ page, request }) => {
  await resetBooks(request);
  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Cash-flow alerts", level: 1 })).toBeVisible();

  await expect(page.getByTestId("alert-count-CRITICAL")).toContainText("1 Critical");
  await expect(page.getByRole("heading", { name: "Reserve breach ahead on day 12" })).toBeVisible();
  await expect(page.getByText("A fix the agent can run exists", { exact: true })).toBeVisible();
  await expect(page.getByText("Cash will drop below your minimum cash reserve", { exact: true })).toBeVisible();
  // Every figure is the server's string: the shortfall, and the two suggested operations (never auto-executed).
  await expect(page.getByText("¥240,000.00").first()).toBeVisible();
  await expect(page.getByText("¥150,000.00").first()).toBeVisible();
  await expect(page.getByText("¥336,000.00").first()).toBeVisible();
  // The note is the server's, the same text in both modes.
  await expect(page.getByText(/executed only through POST \/alerts\/\{id\}\/act/i).first()).toBeVisible();
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
  // Promised early payments (the API's `promised` and `lapsed_promises`): none on the opening books.
  await expect(page.getByRole("heading", { name: "Promised early payments", level: 2 })).toBeVisible();
  await expect(page.getByText("No early payment has been promised.")).toBeVisible();
  await expect(page.getByText("Lapsed promises: 0")).toBeVisible();
});

test("alerts and reconciliation open by their address, in the app's own shell (the Demo has no sidebar of engine views)", async ({ page }) => {
  await page.goto("/alerts");
  await expect(page).toHaveURL(/\/alerts/);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await expect(page.getByTestId("nav-pills")).toBeAttached();
  await page.goto("/reconciliation");
  await expect(page).toHaveURL(/\/reconciliation/);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
});
