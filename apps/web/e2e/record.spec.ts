import type { Page } from "@playwright/test";
import { expect, proseOf, test } from "./fixtures";
import { runPlan } from "./helpers";

/**
 * Wave 2 (map #65), mock mode: the pages read the durable decision record (ADR-0011). Each state is a recording of GET /decisions/{id} from the
 * real API (mocks/decisions.json, scripts/record-mocks.mjs), chosen by where the recorded story stands. Switched on, before the page loads, by
 *   tl-mock-counter-changed  replaced | moved                     the next bound send is refused with the API's own 409 COUNTER_CHANGED
 *   tl-mock-no-receipt       1 | residual                         day 34 without the day-2 receipt; the cure that left the reserve short
 * The live equivalents (the real API's states after a send, the clock and a refused approval) are in live.spec.ts.
 */

test.beforeEach(async ({ page }, testInfo) => {
  void page;
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded story (the live equivalent is in live.spec.ts)");
});

async function hook(page: Page, key: string, value: string) {
  await page.evaluate(([k, v]) => sessionStorage.setItem(k, v), [key, value]);
}

/** Opens the first Foshan message and checks it against the limits, as the owner does. */
async function checked(page: Page) {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Counter recommended");
}

async function advanceTo(page: Page, day: number) {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill(String(day));
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toContainText(String(day));
}

test("the steps follow the record: Response ready names the recommendation, a send moves it to Sent and Agreed", async ({ page }) => {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  // Read but not checked: the record is RECEIVED, so the line stops after the first step.
  const steps = page.getByTestId("deal-steps");
  await expect(steps).toHaveAttribute("data-state", "RECEIVED");
  await expect(steps.getByRole("link", { name: "Received" })).toBeVisible();
  await expect(steps.getByRole("link", { name: /Response ready/ })).toHaveCount(1);
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(steps).toHaveAttribute("data-state", "RESPONSE_READY");
  await expect(steps).toContainText("Response ready (Counter recommended)");
  await expect(page.getByTestId("deal-steps-outcome")).toHaveText("Agreement");
  await expect(steps).not.toContainText("Agreed");
  // The inbox row says the record's state in the server's words.
  await expect(page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01")).toContainText("Showing below");

  await page.locator("#counters").getByTestId("deal-send").click();
  await expect(steps).toHaveAttribute("data-state", "AGREED");
  await expect(page.getByTestId("deal-steps-outcome")).toHaveText("Agreed");
  await expect(steps).toContainText("Sent");
  // The agreements card keeps the deal, with the record's word for where it stands.
  await expect(page.locator("#commitments").getByTestId("commitment-state")).toHaveText("Agreed");
});

test("the send names its option, says the reply is simulated, and carries what was shown; Option B has its own send", async ({ page }) => {
  await checked(page);
  const response = page.locator("#counters");
  const send = response.getByTestId("deal-send");
  await expect(send).toHaveText("Send Option A (simulated buyer reply)");
  await expect(response.getByTestId("deal-option-Option-A").getByTestId("deal-send-scope")).toHaveText(
    "Sends Option A to the buyer (the reply is simulated); records the agreement, with your approval when it changes terms; runs the funding for any remaining gap within your limits.",
  );
  // The send is described by its scope sentence for assistive tools.
  await expect(send).toHaveAttribute("aria-describedby", /scope-deal-option-Option-A/);
  await response.getByTestId("deal-compare").click();
  const b = response.getByTestId("deal-option-Option-B");
  await expect(b.getByRole("button", { name: "Send Option B (simulated buyer reply)" })).toBeVisible();
  await expect(b.getByTestId("deal-send-scope")).toContainText("Sends Option B to the buyer");
  // The page's one filled call to action is still Option A's; Option B's is the quiet style.
  await expect(send).toHaveClass(/bg-brand-600/);
  await expect(b.getByRole("button", { name: /^Send Option B/ })).not.toHaveClass(/bg-brand-600/);
});

test("COUNTER_CHANGED, the verdict was replaced: the current proposal takes the old one's place and nothing was sent", async ({ page }) => {
  await checked(page);
  await hook(page, "tl-mock-counter-changed", "replaced");
  const response = page.locator("#counters");
  await response.getByTestId("deal-send").click();
  const changed = response.getByTestId("deal-counter-changed");
  await expect(changed).toBeVisible();
  await expect(changed).toHaveAttribute("role", "alert");
  await expect(changed).toContainText("The books moved since this was shown");
  await expect(changed).toContainText("Here is the current proposal. Nothing was sent.");
  // The current counters are shown and can be sent; nothing was sent, so the record is where it was.
  await expect(response.getByTestId("deal-option-Option-A")).toBeVisible();
  await expect(page.getByTestId("deal-steps")).toHaveAttribute("data-state", "RESPONSE_READY");
  await expect(page.getByTestId("deal-negotiation")).toHaveCount(0);
  await expect(changed.getByTestId("deal-check-again")).toHaveCount(0);
  // Sending the proposal that is now shown goes through.
  await response.getByTestId("deal-send").click();
  await expect(page.getByTestId("deal-negotiation")).toContainText("The buyer accepted Option A.");
  await expect(page.getByTestId("deal-steps")).toHaveAttribute("data-state", "AGREED");
});

test("COUNTER_CHANGED, the books moved: the old proposal is withdrawn and Check again gets a current one", async ({ page }) => {
  await checked(page);
  await hook(page, "tl-mock-counter-changed", "moved");
  const response = page.locator("#counters");
  await response.getByTestId("deal-send").click();
  const changed = response.getByTestId("deal-counter-changed");
  await expect(changed).toContainText("The books moved since this was shown");
  await expect(changed).toContainText("Nothing was sent. Check again to get a current one.");
  // No counter is offered to send until the check is run again.
  await expect(response.getByTestId("deal-send")).toHaveCount(0);
  await expect(page.getByTestId("deal-steps")).toHaveAttribute("data-state", "RESPONSE_READY");
  await changed.getByTestId("deal-check-again").click();
  await expect(changed).toHaveCount(0);
  await expect(response.getByTestId("deal-send")).toHaveText("Send Option A (simulated buyer reply)");
});

test("day 34: the deal's steps say Fulfilled with the receipt and 'Early payment did not arrive' without it, never Agreed", async ({ page }) => {
  await checked(page);
  await page.locator("#counters").getByTestId("deal-send").click();
  await expect(page.getByTestId("deal-steps")).toHaveAttribute("data-state", "AGREED");
  await advanceTo(page, 34);
  await page.goto("/deals");
  await expect(page.getByTestId("deal-steps")).toHaveAttribute("data-state", "FULFILLED");
  await expect(page.getByTestId("deal-steps-outcome")).toHaveText("Fulfilled");
  await expect(page.locator("#commitments").getByTestId("commitment-state")).toHaveText("Fulfilled");
});

test("day 34 without the receipt: the line and the agreements card say the early payment did not arrive", async ({ page }) => {
  await page.goto("/");
  await hook(page, "tl-mock-no-receipt", "1");
  await checked(page);
  await page.locator("#counters").getByTestId("deal-send").click();
  await advanceTo(page, 34);
  await page.goto("/deals");
  const steps = page.getByTestId("deal-steps");
  await expect(steps).toHaveAttribute("data-state", "MISSED");
  await expect(page.getByTestId("deal-steps-outcome")).toHaveText("Early payment did not arrive");
  await expect(steps).not.toContainText("Agreed");
  // A lapsed agreement stays on the page, with its word, instead of disappearing.
  await expect(page.locator("#commitments").getByTestId("commitment-state")).toHaveText("Early payment did not arrive");
  await expect(page.locator("#commitments")).toContainText("Agreement expired");
});

test("the execution summary is the record's: the agreement in its words, what ran, what has landed", async ({ page }) => {
  await checked(page);
  await page.locator("#counters").getByTestId("deal-send").click();
  await expect(page.getByTestId("deal-steps")).toHaveAttribute("data-state", "AGREED");
  // The Demo verdict page shares the card with Deals.
  await page.goto("/verdict");
  const summary = page.getByTestId("execution-summary");
  await expect(summary.getByTestId("execution-text")).toContainText("Funding of ¥149,986.20 was requested and has landed.");
  await expect(summary.getByTestId("execution-agreement")).toHaveText("Agreed");
  await expect(summary.getByTestId("execution-settlement")).toContainText("Waiting for Foshan Home Retail Co. to pay");
  await expect(summary.getByTestId("execution-funding")).toContainText("¥149,986.20 drawn on the Bank credit line");
  await expect(summary.getByTestId("execution-lots")).toContainText("Landed");
});

test("the approval card shows what was quoted, and once decided what happened and how it differs", async ({ page }) => {
  await advanceTo(page, 34);
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  const card = page.locator("#approval-APR-000001");
  const quote = card.getByTestId("approval-quote");
  await expect(quote).toContainText("Quoted when requested (today)");
  await expect(quote).toContainText("Invoice financing is billed in whole 30-day periods until the invoice is paid.");
  // The after-state and what declining leaves are the quote's.
  await expect(card.getByTestId("approval-after")).toContainText("Cash stays above your minimum cash reserve for the next 120 days.");
  await expect(card.getByTestId("approval-if-decline")).toContainText("below your minimum cash reserve");
  await expect(card.getByTestId("approval-quote-actual")).toHaveCount(0);

  await card.getByRole("button", { name: "Approve" }).click();
  const decided = card.getByTestId("approval-quote");
  await expect(decided).toContainText("Quoted when requested");
  await expect(decided.getByTestId("approval-quote-actual")).toContainText("What actually happened");
  await expect(decided.getByTestId("approval-quote-actual")).toContainText("¥200,000.00");
  await expect(card.getByTestId("approval-cost")).toContainText("¥1,782.19");
  await expect(card.getByTestId("approval-result-APR-000001")).toContainText("the cash lands in 3 days");
  expect(await proseOf(page, ['[data-testid^="approval-detail-"]'])).not.toMatch(/\bday \d/i);
  // The card links to the record, which says the same thing.
  await card.getByTestId("approval-record-APR-000001").click();
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "SETTLEMENT_PENDING");
  await expect(page.getByTestId("record-waiting")).toContainText("to land the funds");
  await expect(page.getByTestId("record-operations")).toContainText("You approved ¥200,000.00 of invoice financing");
});

test("a refused approval ends in the record's words: it could not run, no money moved", async ({ page }) => {
  await page.goto("/");
  await hook(page, "tl-mock-approval-story", "refused");
  await page.goto("/approvals");
  const card = page.locator("#approval-APR-000001");
  await card.getByRole("button", { name: /^Approve/ }).click();
  await expect(card.getByTestId("approval-refused-APR-000001")).toContainText("could not run");
  await expect(card.getByTestId("approval-refused-APR-000001")).toContainText("No money moved.");
  await card.getByTestId("approval-record-APR-000001").click();
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "FAILED");
  await expect(page.getByTestId("record-state")).toContainText("Could not run");
});

test("Home: after the cure is approved, 'Waiting on' lists what is open and links to its record; Activity links each row to its record", async ({ page }) => {
  await advanceTo(page, 34);
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await page.locator("#approval-APR-000001").getByRole("button", { name: "Approve" }).click();
  await expect(page.locator("#approval-APR-000001").getByTestId("approval-decided-APR-000001")).toBeVisible();
  await page.getByRole("navigation").getByRole("link", { name: "Home", exact: true }).first().click();
  const waiting = page.getByTestId("home-waiting-on-list");
  await expect(waiting).toBeVisible();
  await expect(waiting.getByTestId("home-open-state")).toHaveText("Requested; the cash is on its way");
  await expect(waiting.getByTestId("home-open-waiting")).toContainText("to land the funds");
  await waiting.getByTestId("home-open-headline").click();
  await expect(page).toHaveURL(/\/decisions\/alert%3AALERT-RESERVE-42/);
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "SETTLEMENT_PENDING");
  await expect(page.getByTestId("record-settlement")).toContainText("¥200,000.00");
  // Activity: each row that belongs to a record opens it.
  await page.goto("/activity");
  const row = page.getByTestId("activity-SUBMIT_INVOICE_FOR_FINANCING").first();
  await row.locator("> details > summary").click();
  await row.getByTestId("activity-record").click();
  await expect(page.getByTestId("record-state")).toBeVisible();
  // A record that is not on the books says so in words.
  await page.goto("/decisions/deal%3AOFF-nothing");
  await expect(page.getByText("That record is not here")).toBeVisible();
});

test("Home carries the remaining task, with the routes it names, after a cure that did not restore the reserve", async ({ page }) => {
  await page.goto("/");
  await hook(page, "tl-mock-no-receipt", "residual");
  await advanceTo(page, 34);
  await page.goto("/");
  const task = page.locator("#home-remaining");
  await expect(task.getByTestId("home-remaining-text")).toContainText("Your minimum cash reserve is still ¥100,000.00 short from today");
  await expect(task.getByTestId("home-remaining-text")).toContainText("This needs your decision.");
  const links = task.getByTestId("home-remaining-links");
  await expect(links.getByRole("link", { name: "Compare your funding options" })).toHaveAttribute("href", "/cash#cash-options");
  await expect(links.getByRole("link", { name: "Review your limits" })).toHaveAttribute("href", "/limits");
  const invoice = links.getByRole("link", { name: /^Open the .* invoice to Foshan Home Retail Co\.$/ });
  await expect(invoice).toHaveAttribute("href", /^\/receivables#/);
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
  // The record behind it is one click away.
  await task.getByRole("link", { name: "See the record" }).click();
  await expect(page.getByTestId("record-remaining")).toContainText("This needs your decision.");
  // The invoice link lands on that invoice: the page scrolls it into view once the data has loaded.
  await page.goBack();
  await page.locator("#home-remaining").getByRole("link", { name: /^Open the .* invoice/ }).click();
  await expect(page).toHaveURL(/\/receivables#/);
  const id = decodeURIComponent(new URL(page.url()).hash.slice(1));
  const row = page.locator(`[id="${id}"]:visible`);
  await expect(row).toHaveCount(1);
  await expect(row).toBeInViewport();
});

test("in Chinese the record page and the Home blocks read in Chinese from the recordings", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await hook(page, "tl-mock-no-receipt", "residual");
  await advanceTo(page, 34);
  await page.goto("/");
  await expect(page.locator("#home-remaining")).toContainText("这件事仍需您决定");
  await page.locator("#home-remaining").getByRole("link", { name: "查看记录" }).click();
  await expect(page.getByTestId("record-state")).toContainText("已完成");
});
