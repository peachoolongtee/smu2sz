import { expect, proseOf, test } from "./fixtures";
import { runPlan } from "./helpers";

/**
 * The Business Activity page in mock mode: every row leads with a business sentence (what happened, in the owner's words:
 * names, not ids, and distances from today), with the plain operation name as a muted label; the executor's own sentence, the
 * operation id, the codes and the hashes are audit details, closed.
 * The recorded demo path: day 34, the owner queues the fix for approval, then approves it.
 */

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded demo path");
});

const RAW = '[data-testid="activity-raw"]';

test("each row leads with the business sentence, the operation name is a muted label, and the executor's sentence is an audit detail", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toBeVisible();

  await page.goto("/activity");
  const rows = page.getByTestId("activity-list").locator("li");
  await expect(rows.first()).toBeVisible();
  const row = page.getByTestId("activity-SUBMIT_INVOICE_FOR_FINANCING").first();
  // The sentence is the row's heading line; the operation's plain name sits beside the day as a label.
  const sentence = row.getByTestId("activity-event");
  await expect(sentence).toHaveText("Waiting for your approval: ¥200,000.00 of invoice financing at 32.5% a year, above the 15.00% limit you signed for funding without your approval.");
  await expect(sentence).not.toContainText("Queued for owner approval");
  await expect(sentence).not.toContainText("what the agent may borrow alone");
  await expect(sentence).not.toContainText("RI:");
  await expect(row.getByTestId("activity-op")).toHaveText("Get cash early on an invoice");
  await expect(row).toContainText("today");
  // The raw executor sentence, the operation id, the tier and the hashes stay under Audit details, closed until opened.
  const audit = row.locator("details");
  await expect(audit).not.toHaveAttribute("open", "");
  await audit.locator("summary").click();
  await expect(audit.getByTestId("activity-raw")).toContainText("Queued for owner approval (APR-000001)");
  await expect(audit).toContainText("Tier 2");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // The executor's own sentence is the audit level and keeps the engine's day numbers; the rest of the page does not.
  expect(await proseOf(page, [RAW])).not.toMatch(/\bday \d/i);
});

test("approving the fix reads \"You approved ...\" on Activity, never the executor's advance sentence", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await page.locator("#approval-APR-000001").getByRole("button", { name: "Approve" }).click();
  await expect(page.locator("#approval-APR-000001")).toContainText("Approved");

  await page.goto("/activity");
  const approved = page.getByTestId("activity-event").filter({ hasText: "You approved" });
  await expect(approved).toHaveText("You approved ¥200,000.00 of invoice financing. Funds arrive in 3 days.");
  // One operation, one story: the entry that waited reads in the past beside the decision, never "Waiting" beside "You approved".
  const events = await page.getByTestId("activity-event").allTextContents();
  expect(events.filter((x) => x.includes("¥200,000.00 of invoice financing")).map((x) => x.split(":")[0].split(".")[0])).toEqual(["You approved ¥200,000", "Queued for your approval"].map((x) => x));
  expect(events.some((x) => x.startsWith("Waiting for your approval"))).toBe(false);
  // No row leads with the executor's sentence.
  for (const text of await page.getByTestId("activity-event").allTextContents()) {
    expect(text).not.toMatch(/^Advance ¥/);
    expect(text).not.toMatch(/^Queued for owner approval/);
    expect(text).not.toContain("RI:");
  }
  expect(await proseOf(page, [RAW])).not.toMatch(/\bday \d/i);
});

test("day 34: Activity lists the agreement Receivables lists, not 'No commitments yet'", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/receivables");
  await expect(page.getByTestId("promised-RCV-A")).toBeVisible();
  await page.goto("/activity");
  const agreements = page.locator("#activity-commitments");
  await expect(agreements).toContainText("Foshan Home Retail Co.");
  await expect(agreements).not.toContainText("No commitments yet");
  await expect(page.getByTestId("activity-ACCEPT_OFFER")).toBeVisible();
  await expect(page.getByTestId("chain-status")).toContainText("Records verified");
});
