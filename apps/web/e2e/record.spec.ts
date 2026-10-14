import type { Page } from "@playwright/test";
import { expect, proseOf, test } from "./fixtures";
import { checkedDeal, openCompare, openReview, runPlan, sendCounter, openOperatorTools } from "./helpers";

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

/** Opens the first Foshan message and checks it against the limits, as the owner does; returns the address of the negotiation (the address is the selection). */
async function checked(page: Page): Promise<string> {
  await checkedDeal(page);
  return page.url();
}

async function advanceTo(page: Page, day: number) {
  await page.goto("/demo");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill(String(day));
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toContainText(String(day));
}

test("the steps follow the record: Response ready names the recommendation, a send moves it to Sent and Agreed", async ({ page }) => {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("deal-pane")).toBeVisible();
  // Read but not checked: the record is RECEIVED. The chip is the record's state in the server's words and tone; there is no step line.
  const steps = page.getByTestId("deal-state-chip");
  await expect(steps).toHaveAttribute("data-state", "RECEIVED");
  await expect(page.getByTestId("deal-steps")).toHaveCount(0);
  // (The queue's detail has no five-stage track: the chip is the record's state in the server's words and moves with it, and the list row says what the owner is to do.
  // The track's own assertions, the five stages and their `aria-current`, have no counterpart here.)
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(steps).toHaveAttribute("data-state", "RESPONSE_READY");
  await expect(steps).toContainText("Counter ready");
  await expect(steps).not.toContainText("Agreed");
  // The inbox row says the record's state in the server's words (the inbox is one row until it is asked for).
  await page.getByTestId("inbox-back").click();
  await expect(page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01")).toContainText("Showing below");

  await openReview(page);
  await sendCounter(page.locator("#counters"));
  await expect(steps).toHaveAttribute("data-state", "AGREED");
  await expect(steps).toContainText("Agreed");
  // The agreements card keeps the deal, with the record's word for where it stands.
  await expect(page.locator("#commitments").getByTestId("commitment-state")).toHaveText("Agreed");
});

test("the send names its option, says the reply is simulated, and carries what was shown; Option B is reviewed on its own", async ({ page }) => {
  await checked(page);
  await openReview(page);
  const response = page.locator("#counters");
  const send = response.getByTestId("deal-send");
  await expect(send).toHaveText("Send Option A to Foshan");
  await expect(response.getByTestId("receipt-line-authorizes")).toContainText("FLOW records it as a proposed agreement that stands only if Foshan accepts.");
  await expect(response.getByTestId("receipt-line-executes_now")).toContainText("Funding cost ¥841.57 for the draw");
  await expect(response.getByTestId("deal-send-confirm-box")).toContainText("The buyer's reply is simulated");
  await page.getByTestId("queue-review-close").click();
  // Option B is a path of its own: picking it in the comparison makes it the reply under review, with its own send; Option A's gives way, never two at once.
  await openCompare(page);
  await page.locator('[data-testid^="deal-use-CTR-"]:visible').last().click();
  await expect(page.getByTestId("queue-recommends")).toContainText("Option B");
  await expect(page.getByTestId("queue-authority")).toContainText("Needs your approval");
  await openReview(page);
  await expect(page.getByRole("button", { name: "Send Option B to Foshan" })).toBeVisible();
  await expect(page.getByTestId("deal-send")).toHaveCount(1);
  // Its own receipt, the server's block on Option B's priced response (not Option A's, and not words composed from the path): its own funding and its own authority.
  await expect(page.getByTestId("receipt-line-executes_now")).toContainText("Funding cost ¥3,706.46 in addition");
  await expect(page.getByTestId("receipt-line-authority")).toContainText("It changes your terms, so you approve it first.");
});

for (const story of ["replaced", "moved"] as const) {
  test(`COUNTER_CHANGED, ${story === "moved" ? "the books moved" : "the verdict was replaced"}: nothing was sent, and Check again is the explicit step to a current proposal`, async ({ page }) => {
    await checked(page);
    await hook(page, "tl-mock-counter-changed", story);
    await openReview(page);
    await sendCounter(page);
    const changed = page.getByTestId("deal-counter-changed");
    await expect(changed).toBeVisible();
    await expect(changed).toHaveAttribute("role", "alert");
    await expect(changed).toContainText("The books moved since this was shown");
    await expect(changed).toContainText("Nothing was sent. Check again to get a current one.");
    // Nothing was sent: the record is where it was, and no send is offered until the check is run again.
    await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
    await expect(page.getByTestId("deal-negotiation")).toHaveCount(0);
    await changed.getByTestId("deal-check-again").click();
    await expect(changed).toHaveCount(0);
    // The owner reviews the current proposal and sends it.
    await openReview(page);
    await sendCounter(page);
    await expect(page.getByTestId("deal-negotiation")).toContainText("The buyer accepted Option A.");
    await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
  });
}

test("day 34: the deal's steps say Fulfilled with the receipt and 'Early payment did not arrive' without it, never Agreed", async ({ page }) => {
  const deal = await checked(page);
  await openReview(page);
  await sendCounter(page.locator("#counters"));
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
  await advanceTo(page, 34);
  await page.goto(deal);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "FULFILLED");
  await expect(page.getByTestId("deal-state-chip")).toContainText("Fulfilled");
  await expect(page.locator("#commitments").getByTestId("commitment-state")).toHaveText("Fulfilled");
});

test("day 34 without the receipt: the line and the agreements card say the early payment did not arrive", async ({ page }) => {
  await page.goto("/");
  await hook(page, "tl-mock-no-receipt", "1");
  const deal = await checked(page);
  await openReview(page);
  await sendCounter(page.locator("#counters"));
  await advanceTo(page, 34);
  await page.goto(deal);
  const steps = page.getByTestId("deal-state-chip");
  await expect(steps).toHaveAttribute("data-state", "MISSED");
  await expect(page.getByTestId("deal-state-chip")).toContainText("Early payment did not arrive");
  await expect(steps).not.toContainText("Agreed");
  // A lapsed agreement stays on the page, with its word, instead of disappearing.
  await expect(page.locator("#commitments").getByTestId("commitment-state")).toHaveText("Early payment did not arrive");
  await expect(page.locator("#commitments")).toContainText("Agreement expired");
  // The missed payment's card carries the two ways forward the record has: compare the funding options, and chase the payment.
  const links = page.getByTestId("deal-left-links");
  await expect(links.getByRole("link", { name: "Compare your funding options" })).toHaveAttribute("href", /\/cash/);
  await expect(links.getByRole("button", { name: /Chase payment/ })).toBeVisible();
  // The original ask is history: its cost, the most the owner could give and the first breach sit folded under one heading.
  const original = page.getByTestId("deal-original");
  await expect(original.locator("> summary")).toHaveText("The original ask (not agreed)");
  await expect(original).not.toHaveAttribute("open", "");
  await expect(page.getByTestId("deal-ask-quote")).toBeHidden();
  await original.locator("> summary").click();
  await expect(page.getByTestId("deal-ask-quote")).toBeVisible();
});

test("the execution summary is the record's: the agreement in its words, what ran, what has landed", async ({ page }) => {
  await checked(page);
  await openReview(page);
  await sendCounter(page.locator("#counters"));
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
  // The Demo verdict page shares the card with Deals.
  await page.goto("/verdict");
  const summary = page.getByTestId("execution-summary");
  await expect(summary.getByTestId("execution-text")).toContainText("Funding of ¥149,986.20 was requested and has landed.");
  await expect(summary.getByTestId("execution-agreement")).toContainText("Agreed");
  await expect(summary.getByTestId("execution-settlement")).toContainText("Waiting for Foshan Home Retail Co. to pay");
  await expect(summary.getByTestId("execution-funding")).toContainText("¥149,986.20 drawn on the Bank credit line");
  await expect(summary.getByTestId("execution-lots")).toContainText("Cash received today");
});

test("the approval card shows what was quoted, and once decided what happened and how it differs", async ({ page }) => {
  await advanceTo(page, 34);
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  const card = page.locator("#approval-APR-000001");
  const quote = card.getByTestId("approval-quote");
  // What was quoted waits in the application details, behind its own fold (a quote with terms of its own shows them as rows on the card).
  await card.getByTestId("approval-details-APR-000001").locator("> summary").click();
  await expect(card.getByTestId("approval-quoted-APR-000001").locator("> summary")).toContainText("Quoted when requested (today)");
  await card.getByTestId("approval-quoted-APR-000001").locator("> summary").click();
  await expect(quote).toContainText("Invoice financing is billed in whole 30-day periods until the invoice is paid.");
  // The after-state and what declining leaves are the quote's.
  await expect(card.getByTestId("approval-after")).toContainText("Cash stays above your minimum cash reserve for the next 120 days.");
  await expect(card.getByTestId("approval-if-decline")).toContainText("below your minimum cash reserve");
  await expect(card.getByTestId("approval-quote-actual")).toHaveCount(0);

  await card.getByRole("button", { name: /^Authorize/ }).click();
  // Decided: what was quoted is history, behind its own fold.
  await card.getByTestId("approval-quoted-APR-000001").locator("> summary").click();
  const decided = card.getByTestId("approval-quote");
  await expect(card.getByTestId("approval-quoted-APR-000001").locator("> summary")).toContainText("Quoted when requested");
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
  await card.getByRole("button", { name: /^Authorize/ }).click();
  // One state word and the server's tone: never green on a refusal.
  await expect(card.getByTestId("approval-state-APR-000001")).toContainText("Approved, did not run. No money moved.");
  await expect(card.getByTestId("approval-state-APR-000001")).toHaveAttribute("data-tone", "bad");
  await expect(card.getByTestId("approval-refused-APR-000001")).toContainText("could not run");
  await expect(card.getByTestId("approval-refused-APR-000001")).toContainText("No money moved.");
  await card.getByTestId("approval-record-APR-000001").click();
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "FAILED");
  await expect(page.getByTestId("record-state")).toContainText("Could not run");
});

test("after the cure is approved, Home's strip says the funding is on its way; the approval links to its record; Activity links each row to its record", async ({ page }) => {
  await advanceTo(page, 34);
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await page.locator("#approval-APR-000001").getByRole("button", { name: /^Authorize/ }).click();
  await expect(page.locator("#approval-APR-000001").getByTestId("approval-decided-APR-000001")).toBeVisible();
  await page.getByRole("navigation").getByRole("link", { name: "Home", exact: true }).first().click();
  // The strip's funding cell says what is on its way (from the server's recording of the approved cure).
  await expect(page.getByTestId("home-kpi-funding-value")).toBeVisible();
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "quiet");
  await page.goto("/approvals");
  await page.getByTestId("approval-record-APR-000001").click();
  await expect(page).toHaveURL(/\/decisions\/alert%3AALERT-RESERVE-42/);
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "SETTLEMENT_PENDING");
  await expect(page.getByTestId("record-settlement")).toContainText("¥200,000.00");
  // Activity: each row that belongs to a record opens it.
  await page.goto("/activity");
  await page.getByTestId("activity-list").getByTestId("activity-open-decision").first().click();
  await expect(page.getByTestId("record-state")).toBeVisible();
  // A record that is not on the books says so in words.
  await page.goto("/decisions/deal%3AOFF-nothing");
  await expect(page.getByText("That record is not here")).toBeVisible();
});

test("Cash & funding carries the remaining task, with the routes it names, after a cure that did not restore the reserve", async ({ page }) => {
  await page.goto("/");
  await hook(page, "tl-mock-no-receipt", "residual");
  await advanceTo(page, 34);
  await page.goto("/cash");
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
  await expect(page).toHaveURL(/\/receivables(\?[^#]*)?#/);
  const id = decodeURIComponent(new URL(page.url()).hash.slice(1));
  const row = page.locator(`[id="${id}"]:visible`);
  await expect(row).toHaveCount(1);
  await expect(row).toBeInViewport();
});

test("in Chinese the record page and the remaining task on Cash & funding read in Chinese from the recordings", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await hook(page, "tl-mock-no-receipt", "residual");
  await advanceTo(page, 34);
  await page.goto("/cash");
  await expect(page.locator("#home-remaining")).toContainText("需要您决定");
  await page.locator("#home-remaining").getByRole("link", { name: "查看记录" }).click();
  await expect(page.getByTestId("record-state")).toContainText("已融资，储备仍有缺口");
});
