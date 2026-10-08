import { expect, test as signedOut } from "@playwright/test";
import { proseOf, test } from "./fixtures";
import { runPlan } from "./helpers";

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
  await expect(card.getByTestId("approval-reason")).toContainText("Apply for facility Equipment term loan");
  await expect(card.getByTestId("approval-detail-APR-000001")).toHaveCount(0);
  await card.getByTestId("approval-toggle-APR-000001").click();
  const detail = card.getByTestId("approval-detail-APR-000001");
  await expect(detail).toContainText("Apply for a loan");
  await expect(detail).toContainText("FAC-ETL");
  await expect(detail).toContainText("¥600,000.00");
  // The request day is a distance from today, even inside the audit details.
  await expect(detail).toContainText("today, by Agent");
  await expect(detail).toContainText("apply for facility FAC-ETL");
  // The buttons say what they do: the amount to approve, and "Decline"; an approval no alert asked for is simply closed by declining.
  await expect(card.getByTestId("approval-if-decline")).toHaveText("Nothing runs; the request is closed.");
  await expect(card.getByRole("button", { name: "Decline", exact: true })).toBeVisible();
  await card.getByRole("button", { name: "Approve ¥600,000.00", exact: true }).click();
  await expect(card.getByTestId("approval-result-APR-000001")).toContainText("Result:");
  await expect(card).toContainText("Approved");
});

test("an approval born of the reserve alert says what declining leaves, in days from today", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await expect(page).toHaveURL(/\/approvals#approval-APR-000001/);
  const card = page.locator("#approval-APR-000001");
  // The server's sentence, not a static one: the shortfall and the day it peaks, never "Day N".
  await expect(card.getByTestId("approval-if-decline")).toHaveText(
    "¥200,000.00 below your minimum cash reserve in 8 days; the gap peaks at ¥200,000.00 in 8 days.",
  );
  // "Why it needs you" in the owner's words: the signed limit and the holding period from today, never the agent's ceiling or "day N".
  // The reason the owner approves against is on the pending card itself, not behind a click.
  await expect(card.getByTestId("approval-reason")).toBeVisible();
  await expect(card.getByTestId("approval-reason").locator("xpath=preceding-sibling::dt")).toHaveText("Why it needs you");
  await expect(card.getByTestId("approval-reason")).toContainText("The yearly cost of 32.5% is above the 15.00% limit you signed for funding without your approval.");
  // The executor's working ("all charges on ¥200,000.00 held 10 days, annualised = 32.52%") is not in the sentence.
  await expect(card.getByTestId("approval-reason")).not.toContainText("annualised");
  await expect(card.getByTestId("approval-reason")).not.toContainText("32.52");
  await expect(card.getByTestId("approval-result-APR-000001")).toHaveCount(0);
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
  await expect(card.getByRole("button", { name: "Approve ¥200,000.00", exact: true })).toBeVisible();
  // The tier is an audit detail, closed by default; so are the working behind the rate and the facility's lead time.
  await expect(card).not.toContainText("Tier");
  const visible = await card.innerText();
  expect(visible).not.toMatch(/annualised|lead time|Tier 2/);
  await expect(card.getByTestId("approval-reason")).toContainText("32.5%");
  await card.getByTestId("approval-toggle-APR-000001").click();
  await expect(card.getByTestId("approval-detail-APR-000001")).toContainText("Tier 2");
  // The working is one level down, in the executor's own words.
  await expect(card.getByTestId("approval-detail-APR-000001")).toContainText("annualised = 32.52%");
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

signedOut("signed out, an owner page asks for the sign-in in words, not an error code, and opens the dialog", async ({ page }) => {
  await page.goto("/");
  const ask = page.getByTestId("signin-needed");
  await expect(ask).toBeVisible();
  await expect(ask).toContainText("Sign in to see your books");
  await expect(ask).not.toContainText("401");
  // The refused read opened the dialog; once it is cancelled the page's own button brings it back.
  const dialog = page.getByRole("dialog", { name: "Owner sign-in" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog).toBeHidden();
  await ask.getByRole("button", { name: "Owner sign-in" }).click();
  await expect(dialog).toBeVisible();
});
