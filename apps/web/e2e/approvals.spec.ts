import { expect, test as signedOut } from "@playwright/test";
import { test } from "./fixtures";

/**
 * Mock-mode specs for the owner's decision surfaces: no tier badge on a REJECT, the approval card, the autonomy proof
 * on a Tier 1 ACCEPT, and the demo stepper resuming after sign-in. The Tier 1 offer is recorded from the live API
 * (mocks/offer_accept.json, verdict_accept.json); the mock matches it by its text.
 */

const ACCEPT_TEXT = "We will pay the full ¥420,000 invoice early at 0.5%.";

test("a REJECT verdict shows the outcome only, no tier badge, and says nothing is executed", async ({ page }) => {
  await page.goto("/inbox");
  await page.getByRole("button", { name: "Compile" }).click();
  await page.getByRole("button", { name: "Evaluate against the mandate" }).click();
  await expect(page).toHaveURL(/\/verdict/);
  await expect(page.getByTestId("outcome-badge")).toContainText("REJECT");
  await expect(page.getByTestId("nothing-executed")).toHaveText("Nothing is executed");
  const outcome = page.locator("#outcome");
  await expect(outcome).not.toContainText("Tier 1");
  await expect(outcome).not.toContainText("the agent may act");
  await expect(page.getByTestId("autonomy-panel")).toHaveCount(0);
});

test("a Tier 1 ACCEPT shows why the agent may accept it alone, with the server's three tests", async ({ page }) => {
  await page.goto("/inbox");
  await page.getByRole("textbox").fill(ACCEPT_TEXT);
  await page.getByRole("button", { name: "Compile" }).click();
  await page.getByRole("button", { name: "Evaluate against the mandate" }).click();
  await expect(page).toHaveURL(/\/verdict/);
  await expect(page.getByTestId("outcome-badge")).toContainText("ACCEPT");
  const panel = page.getByTestId("autonomy-panel");
  await expect(panel).toContainText("Every figure and request in the message is accounted for");
  await expect(panel).toContainText("names a whole open invoice");
  for (const code of ["MAX_APR", "MIN_CASH", "EARLY_PAY_VS_PLAN"]) {
    const row = panel.getByTestId(`autonomy-check-${code}`);
    await expect(row).toBeVisible();
    await expect(row).not.toContainText("not reported");
  }
  await expect(panel.getByTestId("autonomy-check-MIN_CASH")).toContainText("¥312,900.00 on day 30");
});

test("an approval card expands in place to the operation, the reason, the amount and who asked", async ({ page }) => {
  await page.goto("/mandate");
  await page.getByRole("button", { name: "Scene 3" }).click(); // runs the capex evaluation, which writes nothing
  await expect(page).toHaveURL(/\/capex/);
  await page.goto("/approvals");
  await expect(page.getByText("0 pending")).toBeVisible();
  await page.goto("/capex");
  await page.getByTestId("capex-apply").click(); // the owner's explicit application queues the loan application
  await expect(page.getByTestId("capex-applied")).toBeVisible();
  await page.goto("/approvals");
  const card = page.locator("#approval-APR-000001");
  await expect(card).toContainText("¥600,000.00");
  // The card speaks in business words (the facility's name); the executor's own sentence with the id is an audit detail.
  await expect(card.getByTestId("approval-headline")).toHaveText("Approve ¥600,000.00 of facility application?");
  await expect(card.getByTestId("approval-reason")).toContainText("apply for facility Equipment term loan");
  await expect(card.getByTestId("approval-detail-APR-000001")).toHaveCount(0);
  await card.getByTestId("approval-toggle-APR-000001").click();
  const detail = card.getByTestId("approval-detail-APR-000001");
  await expect(detail).toContainText("Apply for facility");
  await expect(detail).toContainText("FAC-ETL");
  await expect(detail).toContainText("¥600,000.00");
  await expect(detail).toContainText("Day 0, by Agent");
  await expect(detail).toContainText("apply for facility FAC-ETL");
  await card.getByRole("button", { name: "Approve" }).click();
  await expect(card.getByTestId("approval-result-APR-000001")).toContainText("Result:");
  await expect(card).toContainText("Approved");
});

signedOut("the stepper's Start resumes by itself after the owner signs in from the dialog it opened", async ({ page }) => {
  await page.goto("/mandate");
  await page.getByTestId("demo-next").click(); // one click only
  const dialog = page.getByRole("dialog", { name: "Owner sign-in" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Owner token").fill("mock-owner");
  await dialog.getByRole("button", { name: "Sign in" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("region", { name: "Guided demo" }).locator("[aria-live=polite]")).toContainText("1/15");
});
