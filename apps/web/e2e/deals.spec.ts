import { expect, proseOf, test } from "./fixtures";
import { checkedDeal, openInbox, openReview, sendCounter, walkAway } from "./helpers";

/**
 * Deals in Business mode, the flows around the queue (map #121, Slice B): the buyer messages that wait in the inbox (one thread per buyer, only senders the books
 * vouch for), a message read into a negotiation, the commit area (the receipt above the one commit button, the simulated buyer's lean), the answer and the agreement it
 * leaves on the books, a buyer who refuses, and `?buyer=`. Mock mode, on the API's own recordings. The queue and the three levels are in deals-queue.spec.ts.
 */

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded reads");
});

test("the inbox groups a buyer's messages into one thread and names each evaluated one's state in the record's words", async ({ page }) => {
  await walkAway(page); // both Foshan offers compiled and evaluated, the hard-line buyer refused, the reworded offer selected

  // Running the story put the browser in Demo mode: the Demo inbox shows every message, the unknown sender flagged.
  await page.goto("/deals");
  await openInbox(page);
  await expect(page.getByRole("heading", { name: "Simulated inbox" })).toBeVisible();
  await expect(page.getByTestId("inbox-list").getByTestId("inbox-msg-SEC")).toContainText("Not in your contacts");
  // Back in Business mode: one thread for Foshan Home Retail Co.; the FastCapital message is gone, one line says it was blocked.
  await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "business" })));
  await page.reload();
  await openInbox(page);
  const inbox = page.getByTestId("inbox-list");
  await expect(page.getByRole("heading", { name: "Inbox", exact: true })).toBeVisible();
  await expect(page.getByTestId("inbox-thread-BUYER-1")).toHaveCount(1);
  await expect(inbox.getByTestId("inbox-msg-SEC")).toHaveCount(0);
  // The set-aside line is the books' (the ledger's refusal block): nothing was refused yet, so it is the labelled example, and its link lands on Activity's real section.
  await expect(page.getByTestId("inbox-blocked")).toHaveAttribute("data-example", "true");
  await expect(page.getByTestId("inbox-blocked")).toContainText("Example only: nothing has been refused in your books yet.");
  await expect(page.getByTestId("inbox-blocked").getByRole("link", { name: "See what was refused" })).toHaveAttribute("href", "/activity#activity-refused");
  // The walk-away scene negotiated the original offer with a buyer who refused: its row says the outcome in the record's words, not an engine code.
  const original = inbox.getByTestId("inbox-msg-EX01");
  if (await original.isHidden()) await page.getByTestId("inbox-thread-BUYER-1").locator("details > summary").first().click();
  await expect(original).toContainText("No deal");
  await expect(original).not.toContainText("REJECT");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // Opening it selects that negotiation (the address names it) and the pane says where it ended.
  await original.click();
  await expect(page).toHaveURL(/decision=deal%3AOFF-/);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "NO_DEAL");
  await expect(page.getByTestId("deal-state-chip")).toContainText("No deal: the buyer did not accept");
  await expect(page.getByTestId("queue-review-open")).toHaveCount(0);
  await expect(page.getByTestId("deal-record")).toBeVisible();
});

test("opening a message reads it into a negotiation; Check against my limits is the one action; then the receipt, the commit and the agreement", async ({ page }) => {
  await page.goto("/deals");
  await openInbox(page);
  const inbox = page.getByTestId("inbox-list");
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Foshan Home Retail Co.");
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Li Wei");
  await expect(page.getByTestId("inbox-thread-BUYER-1").locator("details > summary").first()).toContainText("earlier message");
  await expect(page.getByTestId("inbox-blocked")).toBeVisible();
  await expect(page.getByTestId("deal-pane")).toHaveCount(0);
  // Opening a message reads it (no separate button): the inbox card gives way (the buyer's messages are the deal's Messages tab) and the pane opens on the ask.
  await inbox.getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("deals-inbox")).toHaveCount(0);
  await page.getByTestId("deal-tab-messages").click();
  await expect(page.getByTestId("deal-ask-quote-messages")).toContainText("We'll settle the ¥420k early at 1.2%");
  await page.getByTestId("deal-tab-overview").click();
  await page.getByTestId("queue-check-button").click();
  await expect(page.getByTestId("queue-recommends")).toBeVisible();
  // Reading the same message again costs nothing: it is selected, not read twice.
  await page.getByTestId("deal-tab-messages").click();
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Showing below");
  await inbox.getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("queue-recommends")).toBeVisible();

  // The review: the server's receipt, in its order, then the simulated buyer's lean and the one commit button that names the action.
  await openReview(page);
  const receipt = page.getByTestId("commitment-receipt");
  await expect(receipt).toContainText("What sending Option A does");
  // Round two: three statements above the button (authorizing, immediately, not yet), then the terms and the cost of this very send; the rest of the receipt is the fold after the button.
  const keys = await page.getByTestId("send-statements").locator("[data-testid^=receipt-line-]").evaluateAll((els) => els.map((el) => el.getAttribute("data-testid")!.replace("receipt-line-", "")));
  expect(keys).toEqual(["authorizes", "executes_now", "remaining"]);
  await expect(page.getByTestId("send-terms-table-table")).toBeVisible();
  await expect(page.getByTestId("send-cost-table")).toBeVisible();
  await expect(page.getByTestId("receipt-line-authorizes")).toContainText("FLOW records it as a proposed agreement that stands only if Foshan accepts.");
  await expect(page.getByTestId("receipt-line-executes_now")).toContainText("Draws ¥149,986.20 on the Bank credit line today");
  await page.getByTestId("send-fold").locator("> summary").click();
  const rest = await page.getByTestId("send-fold-lines").locator("[data-testid^=receipt-line-]").evaluateAll((els) => els.map((el) => el.getAttribute("data-testid")!.replace("receipt-line-", "")));
  expect(rest).toEqual(["others_must_agree", "in_hand_vs_future", "fees", "when", "assumptions", "authority"]);
  await expect(page.getByTestId("receipt-line-fees")).toContainText("¥3,027.77");
  await expect(page.getByTestId("receipt-line-others_must_agree")).toContainText("must accept the counter");
  await expect(page.getByTestId("receipt-line-gross")).toHaveCount(0); // the server has no gross for a counter: the line is omitted, not invented
  await expect(page.getByTestId("deal-send")).toHaveText("Send Option A to Foshan");
  const box = page.getByTestId("deal-send-confirm-box");
  await expect(box).toContainText("The buyer's reply is simulated in this environment");
  // The simulated buyer's lean is the Demo's control: Business sends with the cooperative buyer and shows no choice.
  await expect(box.getByLabel("Open to a counter")).toHaveCount(0);
  await expect(box.getByLabel("Holds firm")).toHaveCount(0);
  // Not now closes the review and nothing was sent.
  await page.getByTestId("queue-review-close").click();
  await expect(page.getByTestId("queue-review")).toHaveCount(0);
  await openReview(page);
  // One press sends: the receipt on screen is the review, there is no second confirmation.
  await sendCounter(page);
  await expect(page.getByTestId("deal-negotiation")).toContainText("The buyer accepted Option A. The agreement is on your books.");
  // What ran is the server's own summary, said once under the result; the agreement receipt's "Runs now" line is the same summary, not the state word "Agreed".
  await expect(page.getByTestId("deal-sent-ran")).toHaveText("Agreement with Foshan Home Retail Co. recorded. Funding of ¥149,986.20 was requested and has landed.");
  await expect(page.getByTestId("deal-agreement-receipt").getByTestId("receipt-line-executes_now")).toContainText("Agreement with Foshan Home Retail Co. recorded.");
  await expect(page.getByTestId("deal-agreement-receipt").getByTestId("receipt-line-executes_now")).not.toHaveText(/Runs now\s*Agreed$/);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
  await expect(page.getByTestId("deal-send")).toHaveCount(0);
  await expect(page.getByTestId("queue-review-open")).toHaveCount(0);
  // The record's own account: money received, what was agreed, what is left, and the agreement's receipt.
  await expect(page.getByTestId("deal-money-lines")).toContainText("¥149,986.20");
  await expect(page.getByTestId("deal-terms")).toContainText("0.85% off");
  await expect(page.getByTestId("deal-waiting")).toContainText("Waiting for Foshan Home Retail Co. to pay");
  await expect(page.getByTestId("deal-agreement-receipt")).toContainText("In force.");
  await expect(page.getByTestId("deal-agreements").or(page.locator("#commitments"))).toContainText("0.85% off");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
});

test("a deep link in a fresh session hydrates the evaluated negotiation: nothing but the server is read", async ({ page }) => {
  await checkedDeal(page);
  const url = page.url();
  await page.evaluate(() => sessionStorage.removeItem("tl-demo-v3"));
  await page.goto(url);
  await expect(page.getByTestId("queue-recommends")).toContainText("Option A");
  await expect(page.getByTestId("deal-mandate")).toBeVisible();
  // The review reads the terms of this send from the server (the same check as "Check again", on the owner's own press) and sends what it showed.
  await page.getByTestId("queue-review-open").click();
  await expect(page.getByTestId("receipt-line-authorizes")).toContainText("proposed agreement");
  await sendCounter(page);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
});

test("Business mode never shows a sender the books have not vouched for, not even while they load", async ({ page }) => {
  // Watch the document from its first paint: the suspicious message must not appear for a single frame.
  await page.addInitScript(() => {
    (window as unknown as { __sawSec: boolean }).__sawSec = false;
    const look = () => {
      if (document.querySelector('[data-testid="inbox-msg-SEC"]')) (window as unknown as { __sawSec: boolean }).__sawSec = true;
    };
    new MutationObserver(look).observe(document, { childList: true, subtree: true });
  });
  await page.goto("/deals");
  await expect(page.getByTestId("inbox-thread-BUYER-1")).toBeVisible();
  await expect(page.getByTestId("inbox-blocked")).toContainText("Example only: nothing has been refused in your books yet. A message from a sender you do not know would be set aside here.");
  expect(await page.evaluate(() => (window as unknown as { __sawSec: boolean }).__sawSec)).toBe(false);
});

test("a buyer who refuses every counter ends in No deal, with what happens next, and nothing sounds like an agreement", async ({ page }) => {
  await checkedDeal(page);
  const deal = page.url();
  // The demo's negotiation panel runs a buyer who refuses (Demo views; the Business page sends to the lean the owner picks).
  await page.goto("/verdict");
  await page.getByLabel("Buyer refuses every counter").check();
  await page.getByRole("button", { name: "Run the negotiation" }).click();
  await expect(page.getByTestId("negotiation-result")).toContainText("NO DEAL");
  await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "business" })));
  await page.goto(deal);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "NO_DEAL");
  await expect(page.getByTestId("deal-state-chip")).toContainText("No deal");
  await expect(page.getByTestId("deal-waiting")).toContainText("Waiting for Invoice financing");
  await expect(page.getByTestId("deal-money-lines")).toContainText("¥255,000.00 arrives in 3 days");
  await expect(page.getByTestId("deal-send")).toHaveCount(0);
  await expect(page.getByTestId("queue-review-open")).toHaveCount(0);
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
});

test("the simulated buyer's lean is chosen in the review in Demo mode; a buyer who holds firm refuses, and the deal ends in No deal", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "demo" })));
  await checkedDeal(page);
  await openReview(page);
  const box = page.getByTestId("deal-send-confirm-box");
  await expect(box.getByTestId("deal-send-refusal")).toHaveCount(0);
  await box.getByLabel("Holds firm").check();
  await expect(box.getByTestId("deal-send-refusal")).toContainText("there is no deal");
  await sendCounter(page);
  await expect(page.getByTestId("deal-negotiation")).toContainText("The buyer refused every counter. Nothing was agreed.");
  await expect(page.getByTestId("deal-sent-ran")).toHaveText("Funding of ¥405,000.00 was requested; ¥255,000.00 is on its way and lands in 3 days.");
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "NO_DEAL");
  await expect(page.getByTestId("deal-send")).toHaveCount(0);
});

test("?buyer= lists that buyer's tasks: the chase dialog's thread link lands on the queue for that customer", async ({ page }) => {
  await checkedDeal(page);
  await page.goto("/deals?buyer=BUYER-1");
  await expect(page.getByTestId("queue-only-customer")).toContainText("Foshan Home Retail Co.");
  await expect(page.getByTestId("queue-row")).toHaveCount(1);
  await page.getByTestId("queue-show-all").click();
  await expect(page.getByTestId("queue-only-customer")).toHaveCount(0);
  // A buyer the books do not know lists nothing and selects nothing.
  await page.goto("/deals?buyer=BUYER-NOBODY");
  await expect(page.getByTestId("queue-row")).toHaveCount(0);
  await expect(page.getByTestId("deal-pane")).toHaveCount(0);
});
