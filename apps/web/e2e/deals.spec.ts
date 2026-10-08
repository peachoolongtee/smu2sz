import { expect, proseOf, test } from "./fixtures";

/**
 * Deals in Business mode, in the owner's order: one inbox thread per buyer, the ask in plain words, the business action
 * with its three numbers, the recommended response, then the closed disclosures. Mock mode: the guided demo is walked to
 * step 11 in the first spec (both Foshan offers compiled and evaluated); the second opens a message the way the owner
 * does. The page must fit about two desktop screens with the disclosures closed (the brief's section 36).
 */

test("the inbox groups a buyer's messages into one thread and names each evaluated one's recommendation", async ({ page }) => {
  await page.goto("/mandate");
  for (let i = 0; i < 11; i++) {
    const button = page.getByTestId("demo-next");
    await expect(button).toBeEnabled();
    await button.click();
    // Wait for the step to finish: a click while the stepper is busy is ignored.
    await expect(page.getByRole("region", { name: "Guided demo" }).locator("[aria-live=polite]")).toContainText(`${i + 1}/15`);
  }

  // Running the story put the browser in Demo mode: the Demo inbox shows every message, the unknown sender flagged.
  await page.goto("/deals");
  const inbox = page.getByTestId("inbox-list");
  await expect(page.getByRole("heading", { name: "Simulated inbox" })).toBeVisible();
  await expect(inbox.getByTestId("inbox-msg-SEC")).toContainText("Not in your contacts");
  // Back in Business mode: one thread for Foshan Home Retail Co.; the FastCapital message is gone, one line says it was blocked.
  await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "business" })));
  await page.reload();
  await expect(page.getByRole("heading", { name: "Inbox", exact: true })).toBeVisible();
  await expect(page.getByTestId("inbox-thread-BUYER-1")).toHaveCount(1);
  await expect(inbox.getByTestId("inbox-msg-SEC")).toHaveCount(0);
  await expect(page.getByTestId("inbox-blocked")).toContainText("1 message from an unknown sender was set aside. The agent does not act on messages from senders that are not on your books.");
  await expect(page.getByTestId("inbox-blocked").getByRole("link", { name: "See what was refused" })).toHaveAttribute("href", "/activity#refused");
  // Step 11 selected the reworded offer; the original is in the thread, evaluated, with its recommendation in words, no code.
  const reworded = inbox.getByTestId("inbox-msg-EX01B");
  const original = inbox.getByTestId("inbox-msg-EX01");
  await expect(reworded).toHaveAttribute("aria-current", "true");
  // The story's step 11 negotiated this offer with a buyer who refused: the row says the outcome, not the earlier recommendation.
  await expect(original).toContainText("No deal");
  await expect(original).not.toContainText("REJECT");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  await original.click();
  await expect(original).toHaveAttribute("aria-current", "true");
  await expect(reworded).not.toHaveAttribute("aria-current", "true");
  await expect(page.getByTestId("deal-recommendation")).toHaveText("No deal");
  await expect(page.getByTestId("deal-steps").getByRole("link", { name: /Respond/ })).toHaveAttribute("href", "/deals#counters");
  await expect(page.getByTestId("deal-steps").getByRole("link", { name: /No deal/ })).toHaveAttribute("href", "/deals#counters");
  const originalId = await page.evaluate(() => JSON.parse(sessionStorage.getItem("tl-demo-v2") ?? "{}").offerId);
  // Picking the latest message folded the thread; the earlier ones are one click away.
  await expect(reworded).toBeHidden();
  await page.getByTestId("inbox-thread-BUYER-1").locator("details > summary").first().click();
  await reworded.click();
  await expect(reworded).toHaveAttribute("aria-current", "true");
  await expect.poll(() => page.evaluate(() => JSON.parse(sessionStorage.getItem("tl-demo-v2") ?? "{}").offerId)).not.toBe(originalId);
});

test("opening a message reads it, and the evaluated deal reads in the owner's order within two screens", async ({ page }) => {
  await page.goto("/deals");
  await expect(page.getByRole("heading", { name: "Inbox", exact: true })).toBeVisible();
  const inbox = page.getByTestId("inbox-list");
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Foshan Home Retail Co.");
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Li Wei");
  await expect(page.getByTestId("deal-steps")).toHaveCount(0);
  await expect(page.getByTestId("deal-recommendation")).toHaveCount(0);

  // Opening a message reads it (no separate button); the ask is in plain words; the one next step is the check.
  await inbox.getByTestId("inbox-msg-EX01").click();
  await expect(inbox.getByTestId("inbox-msg-EX01")).toHaveAttribute("aria-current", "true");
  await expect(page.getByTestId("deal-ask-IMMEDIATE_DISCOUNT")).toContainText("1.20% discount for paying the ¥420,000.00 invoice early");
  await expect(page.getByTestId("deal-ask-TERMS_EXTENSION")).toContainText("60");
  await expect(page.getByTestId("deal-ask-CONTINGENT_REBATE")).toContainText("1.00% rebate");
  // The buyer's earlier messages sit inside the thread; there is no other thread in Business mode, so nothing else folds.
  await expect(page.getByTestId("inbox-thread-BUYER-1").locator("details > summary").first()).toContainText("earlier message");
  await expect(page.getByTestId("inbox-others")).toHaveCount(0);
  await expect(page.getByTestId("inbox-blocked")).toBeVisible();
  const next = page.getByTestId("next-step");
  await next.getByRole("button", { name: "Check against my limits" }).click();

  // The business action, then the three numbers: first breach and worst point are two named days.
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Counter recommended");
  await expect(page.getByTestId("deal-ask-TERMS_EXTENSION")).toContainText("45 → 60 day payment terms going forward");
  const cost = page.getByTestId("deal-fact-cost");
  await expect(cost).toContainText("12-month cost of concessions");
  await expect(cost).toContainText("¥28,326.92");
  await expect(cost).toContainText("Your limit: ¥5,000.00");
  const breach = page.getByTestId("deal-fact-cash");
  await expect(breach).toContainText("First reserve breach");
  await expect(breach).toContainText("in 47 days");
  await expect(breach).toContainText("Cash falls to ¥209,960.00");
  const worst = page.getByTestId("deal-fact-worst");
  await expect(worst).toContainText("Worst point");
  await expect(worst).toContainText("¥164,960.00");
  await expect(worst).toContainText("in 60 days");
  // The three numbers are about the offer as the buyer asked for it, and the page says so.
  await expect(page.getByTestId("deal-if-accept")).toHaveText("If you accept the offer as asked:");
  await expect(page.getByTestId("deal-parsed-terms").locator("> summary")).toHaveText("How the agent read it");
  await expect(page.getByTestId("deal-discount-dearer")).toContainText("1.20% early-payment discount also costs more");
  // No engine count or code at level 1.
  await expect(page.locator("body")).not.toContainText("failed,");
  await expect(page.locator("#deal-recommendation-card")).not.toContainText("REJECT");

  // The recommended response: Option A with its cost; Option B behind "Compare", with its net economic cost and both parts.
  const response = page.locator("#counters");
  await expect(response.getByTestId("deal-option-Option-A")).toContainText("Recommended");
  await expect(response.getByTestId("deal-option-Option-A").getByTestId("deal-option-cost")).toHaveText("¥3,027.77");
  await expect(response.getByTestId("deal-option-Option-B")).toHaveCount(0);
  await response.getByTestId("deal-compare").click();
  const b = response.getByTestId("deal-option-Option-B");
  await expect(b).toContainText("Net economic cost");
  await expect(b.getByTestId("deal-option-cost")).toContainText("¥0");
  await expect(b).toContainText("¥16,217.95");
  await expect(b).toContainText("¥16,380.00");
  await expect(b).not.toContainText("¥0.00");
  await response.getByTestId("deal-compare").click();
  await expect(response.getByTestId("deal-option-Option-B")).toHaveCount(0);

  // The next step points at the response; the disclosures are closed and hold the evidence.
  await expect(next.getByRole("link", { name: "See what we'd offer back" })).toHaveAttribute("href", "#counters");
  // One filled call to action on the page ("Send this counter"); the next-step link is the secondary style.
  await expect(next.getByRole("link", { name: "See what we'd offer back" })).not.toHaveClass(/bg-brand-600/);
  await expect(response.getByTestId("deal-send")).toHaveClass(/bg-brand-600/);
  for (const id of ["deal-why", "deal-original", "deal-calc"]) {
    await expect(page.getByTestId(id)).not.toHaveAttribute("open", "");
  }
  await expect(page.getByTestId("deal-why")).toContainText("Why FLOW recommends this");
  await page.getByTestId("deal-why").locator("> summary").click();
  // Three reasons in the owner's words; every check, the formulas and the engine's verdict one level further down.
  const reasons = page.getByTestId("deal-reasons");
  await expect(reasons.locator("li")).toHaveCount(3);
  await expect(page.getByTestId("deal-reason-AGG_CONCESSION_EXCEEDED")).toHaveText("The package gives away ¥28,326.92 over 12 months, above your ¥5,000.00 limit.");
  await expect(page.getByTestId("deal-reason-RESERVE_BREACH")).toHaveText("It pushes cash to ¥209,960.00 in 47 days, below your ¥300,000.00 minimum cash reserve.");
  await expect(page.getByTestId("deal-reason-DISCOUNT_ABOVE_BREAK_EVEN")).toContainText("break-even 0.88%");
  await expect(page.getByTestId("deal-why")).not.toContainText("d/(1");
  await expect(page.getByTestId("deal-technical-summary")).toBeHidden();
  await page.getByTestId("deal-all-checks").locator("> summary").click();
  await expect(page.getByTestId("deal-all-checks").locator("> summary")).toContainText("Show all checks (8)");
  await expect(page.getByTestId("deal-technical-summary")).toContainText("Engine verdict");
  await expect(page.getByTestId("deal-technical-summary")).toContainText("REJECT");
  await page.getByTestId("deal-why").locator("> summary").click();
  // The calculation opens with the reading, the equation behind it.
  await page.getByTestId("deal-calc").locator("> summary").click();
  const items = page.getByTestId("deal-calc-item");
  await expect(items.nth(1)).toContainText("60-day terms add 15 days of financing to 13 expected invoices");
  await expect(items.nth(1)).toContainText("¥24,326.92");
  await expect(items.nth(1).locator("details > summary")).toHaveText("Formula");
  await page.getByTestId("deal-calc").locator("> summary").click();
  // No empty commitments card; the page fits about two screens with the disclosures closed.
  await expect(page.locator("#commitments")).toHaveCount(0);
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  expect(height).toBeLessThanOrEqual(2 * 900 + 100);
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // Reading the same message again costs nothing: it is shown, not read twice.
  await inbox.getByTestId("inbox-msg-EX01").click();
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Showing below");
  // Sending the counter: the buyer's (simulated) answer comes back in words, and the next step is the agreement.
  await expect(response).toContainText("The buyer's reply is simulated in this demo.");
  await response.getByTestId("deal-send").click();
  await expect(page.getByTestId("deal-negotiation")).toContainText("The buyer accepted Option A. The agreement is on your books.");
  await expect(response.getByTestId("deal-send")).toHaveCount(0);
  // The outcome card: the buyer's answer, the agreement with its terms as sentences; the headline, the step and the inbox row follow.
  await expect(response.getByRole("heading", { name: "The buyer's answer" })).toBeVisible();
  await expect(response.getByTestId("deal-agreed-terms")).toContainText("0.85% off the ¥257,200.00 invoice");
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Agreed with the buyer");
  await expect(page.getByTestId("deal-steps")).toContainText("Agreed");
  await expect(inbox.getByTestId("inbox-msg-EX01").getByTestId("inbox-msg-status")).toHaveCount(0); // the message being read says "Showing below"
  await expect(response.getByTestId("deal-option-Option-A")).toHaveCount(0);
  await expect(next).toContainText(/agree|books/i);
});

test("without the strategy flag, Compare is the response card's own state: it is closed again after reading another message and coming back", async ({ page }) => {
  // With the flag on the page keeps the state (so "Before they ask" can open Option B), which is what e2e/strategy.spec.ts covers.
  test.skip(process.env.E2E_STRATEGY === "1", "the strategy build keeps the compare state on the page");
  await page.goto("/deals");
  const inbox = page.getByTestId("inbox-list");
  await inbox.getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  const response = page.locator("#counters");
  await response.getByTestId("deal-compare").click();
  await expect(response.getByTestId("deal-option-Option-B")).toBeVisible();
  // Read the other message of the thread: the response card is gone until it is checked.
  await page.getByTestId("inbox-thread-BUYER-1").locator("details > summary").first().click();
  await inbox.getByTestId("inbox-msg-EX01B").click();
  await expect(inbox.getByTestId("inbox-msg-EX01B")).toHaveAttribute("aria-current", "true");
  await expect(page.locator("#counters")).toHaveCount(0);
  // Back to the first: its response card starts closed, as it always did.
  await page.getByTestId("inbox-thread-BUYER-1").locator("details > summary").first().click();
  await inbox.getByTestId("inbox-msg-EX01").click();
  await expect(inbox.getByTestId("inbox-msg-EX01")).toHaveAttribute("aria-current", "true");
  await expect(page.locator("#counters").getByTestId("deal-option-Option-A")).toBeVisible();
  await expect(page.locator("#counters").getByTestId("deal-option-Option-B")).toHaveCount(0);
  await expect(page.locator("#counters").getByTestId("deal-compare")).toContainText("Compare");
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
  await expect(page.getByTestId("inbox-blocked")).toContainText("1 message from an unknown sender was set aside. The agent does not act on messages from senders that are not on your books.");
  expect(await page.evaluate(() => (window as unknown as { __sawSec: boolean }).__sawSec)).toBe(false);
});

test("a buyer who refuses every counter ends in No deal, with what happens next, and nothing sounds like an agreement", async ({ page }) => {
  await page.goto("/deals");
  const inbox = page.getByTestId("inbox-list");
  await inbox.getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Counter recommended");
  // The demo's negotiation panel runs a buyer who refuses (Demo views; the Business page only sends to a buyer who accepts).
  await page.goto("/verdict");
  await page.getByLabel("Buyer refuses every counter").check();
  await page.getByRole("button", { name: "Run the negotiation" }).click();
  await expect(page.getByTestId("negotiation-result")).toContainText("NO DEAL");
  await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "business" })));
  await page.goto("/deals");
  await expect(page.getByTestId("deal-recommendation")).toHaveText("No deal");
  await expect(page.getByTestId("deal-recommendation")).toHaveAttribute("data-outcome", "NO_DEAL");
  await expect(page.getByTestId("deal-if-accept")).toHaveText("If you had accepted the offer as asked:");
  await expect(page.getByTestId("deal-steps")).toContainText("No deal");
  await expect(page.getByTestId("deal-steps").getByRole("link", { name: "No deal" })).toHaveClass(/text-ink-2/);
  const outcome = page.locator("#counters");
  await expect(outcome.getByTestId("deal-negotiation")).toContainText("The buyer refused every counter. Nothing was agreed.");
  await expect(outcome.getByTestId("deal-rounds").locator("li")).toHaveCount(3);
  await expect(outcome.getByTestId("deal-rounds")).toContainText("Refused");
  // What happens next: the funding for the gap still ran, and the way to see it.
  await expect(outcome.getByTestId("deal-gap-funded")).toContainText("The funding for your cash gap still ran on your books.");
  await expect(outcome.getByRole("link", { name: "See it in Cash & funding" })).toHaveAttribute("href", "/cash");
  await expect(outcome.getByTestId("deal-send")).toHaveCount(0);
  await expect(page.locator("#commitments")).toHaveCount(0);
  // The buyer's own words (which carry the engine's days) are one fold away; the prose has no "day N".
  await expect(outcome.getByTestId("deal-buyer-words")).not.toHaveAttribute("open", "");
  expect(await proseOf(page, ['[data-testid="deal-buyer-words"]', '[data-testid="deal-why"]', '[data-testid="deal-calc"]', '[data-testid="deal-original"]'])).not.toMatch(/\bday \d/i);
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Showing below");
});
