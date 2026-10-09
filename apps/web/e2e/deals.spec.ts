import { expect, proseOf, test } from "./fixtures";
import { walkAway, sendCounter } from "./helpers";

/**
 * Deals in Business mode, one workspace in the server's order: one inbox thread per buyer (folded to one row once a deal is selected),
 * the selected buyer's header, what the buyer asks, what it costs (the immediate discount apart from the forward total), why it matters,
 * what FLOW recommends, the priced response, then the closed Advanced details. Mock mode: the optional scene "The buyer walks away" is run
 * in the first spec (both Foshan offers compiled and evaluated); the second opens a message the way the owner
 * does. The page must fit about two desktop screens with the disclosures closed (the brief's section 36).
 */

test("the inbox groups a buyer's messages into one thread and names each evaluated one's recommendation", async ({ page }) => {
  await walkAway(page); // both Foshan offers compiled and evaluated, the hard-line buyer refused, the reworded offer selected

  // Running the story put the browser in Demo mode: the Demo inbox shows every message, the unknown sender flagged.
  await page.goto("/deals");
  // A deal is selected, so even the Demo inbox is one row until it is asked for.
  await expect(page.getByTestId("inbox-collapsed")).toContainText("Simulated inbox (4)");
  await page.getByTestId("inbox-back").click();
  const inbox = page.getByTestId("inbox-list");
  await expect(page.getByRole("heading", { name: "Simulated inbox" })).toBeVisible();
  await expect(inbox.getByTestId("inbox-msg-SEC")).toContainText("Not in your contacts");
  // Back in Business mode: one thread for Foshan Home Retail Co.; the FastCapital message is gone, one line says it was blocked.
  await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "business" })));
  await page.reload();
  // A deal is selected (step 11 read the reworded offer), so the inbox is one row; "Back to inbox" opens the list.
  const collapsed = page.getByTestId("inbox-collapsed");
  await expect(collapsed).toContainText("Inbox (3)");
  await expect(page.getByTestId("inbox-list")).toHaveCount(0);
  await collapsed.getByRole("button", { name: "Back to inbox" }).click();
  await expect(page.getByRole("heading", { name: "Inbox", exact: true })).toBeVisible();
  await expect(page.getByTestId("inbox-thread-BUYER-1")).toHaveCount(1);
  await expect(inbox.getByTestId("inbox-msg-SEC")).toHaveCount(0);
  // The set-aside line is the books' (the ledger's refusal block): nothing was refused yet, so it is the labelled example, and its link lands on Activity's real section.
  await expect(page.getByTestId("inbox-blocked")).toHaveAttribute("data-example", "true");
  await expect(page.getByTestId("inbox-blocked")).toContainText("Example only: nothing has been refused in your books yet.");
  await expect(page.getByTestId("inbox-blocked").getByRole("link", { name: "See what was refused" })).toHaveAttribute("href", "/activity#activity-refused");
  // The walk-away scene selected the reworded offer; the original is in the thread, evaluated, with its recommendation in words, no code.
  const reworded = inbox.getByTestId("inbox-msg-EX01B");
  const original = inbox.getByTestId("inbox-msg-EX01");
  await expect(reworded).toHaveAttribute("aria-current", "true");
  // The walk-away scene negotiated this offer with a buyer who refused: the row says the outcome, not the earlier recommendation.
  await expect(original).toContainText("No deal");
  await expect(original).not.toContainText("REJECT");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  await original.click();
  await expect(page.getByTestId("inbox-collapsed")).toBeVisible();
  await expect(page.getByTestId("deal-recommendation")).toHaveText("No deal: the buyer did not accept");
  // The chip is the record's: this deal ended in No deal, in the server's word and the server's tone. There is no step line.
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "NO_DEAL");
  await expect(page.getByTestId("deal-state-chip")).toContainText("No deal: the buyer did not accept");
  await expect(page.getByTestId("deal-steps")).toHaveCount(0);
  const originalId = await page.evaluate(() => JSON.parse(sessionStorage.getItem("tl-demo-v3") ?? "{}").offerId);
  // Open the inbox again: the selected message is marked, and picking the latest message folded the thread; the earlier ones are one click away.
  await page.getByTestId("inbox-back").click();
  await expect(original).toHaveAttribute("aria-current", "true");
  await expect(reworded).not.toHaveAttribute("aria-current", "true");
  await expect(reworded).toBeHidden();
  await page.getByTestId("inbox-thread-BUYER-1").locator("details > summary").first().click();
  await reworded.click();
  await expect(page.getByTestId("inbox-collapsed")).toBeVisible();
  await expect.poll(() => page.evaluate(() => JSON.parse(sessionStorage.getItem("tl-demo-v3") ?? "{}").offerId)).not.toBe(originalId);
});

test("opening a message reads it, and the evaluated deal is one workspace in the server's order within two screens", async ({ page }) => {
  await page.goto("/deals");
  await expect(page.getByRole("heading", { name: "Inbox", exact: true })).toBeVisible();
  const inbox = page.getByTestId("inbox-list");
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Foshan Home Retail Co.");
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Li Wei");
  await expect(page.getByTestId("deal-steps")).toHaveCount(0);
  await expect(page.getByTestId("deal-recommendation")).toHaveCount(0);

  // The buyer's earlier messages sit inside the thread; there is no other thread in Business mode, so nothing else folds.
  await expect(page.getByTestId("inbox-thread-BUYER-1").locator("details > summary").first()).toContainText("earlier message");
  await expect(page.getByTestId("inbox-others")).toHaveCount(0);
  await expect(page.getByTestId("inbox-blocked")).toBeVisible();
  // Opening a message reads it (no separate button); the inbox folds to one row; the ask is in plain words; the one Action is the check.
  await inbox.getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("inbox-collapsed")).toContainText("Inbox (3)");
  await expect(page.locator("#deal-selected")).toContainText("Foshan Home Retail Co.");
  await expect(page.getByTestId("deal-ask-IMMEDIATE_DISCOUNT")).toContainText("1.20% discount for paying the ¥420,000.00 invoice early");
  await expect(page.getByTestId("deal-ask-TERMS_EXTENSION")).toContainText("60");
  await expect(page.getByTestId("deal-ask-CONTINGENT_REBATE")).toContainText("1.00% rebate");
  const next = page.getByTestId("next-step");
  await next.getByRole("button", { name: "Check against my limits" }).click();

  // The workspace in the server's order: the buyer, what FLOW recommends (with its reason), the priced response, what the buyer asks, what it costs and why it matters.
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Counter recommended");
  await expect(page.getByTestId("deal-recommendation-reason")).not.toBeEmpty();
  const tops = await page.evaluate(() => ["deal-selected", "deal-recommendation-card", "counters", "deal-ask", "deal-impact", "commitments", "deal-advanced"].map((id) => document.getElementById(id) ?? document.querySelector(`[data-testid="${id}"]`)).map((el) => el?.getBoundingClientRect().top ?? -1));
  // (no agreement yet, so there is no commitments card)
  const present = tops.filter((y) => y >= 0);
  expect(present.length).toBe(6);
  expect(present).toEqual([...present].sort((a, b) => a - b));
  // The header: the buyer, when it came and when it was checked, and one chip for where the deal stands. No ask line: the asks card says it once.
  await expect(page.locator("#deal-selected")).not.toContainText("Immediate discount · Terms extension · Contingent rebate");
  await expect(page.getByTestId("deal-state-chip")).toContainText("Counter recommended");
  await expect(page.getByTestId("deal-evaluated")).toHaveText("Evaluated today");
  // Buyer terms appear once: the server's sentence for the term, not again in a second card, the response or the header.
  await expect(page.getByTestId("deal-ask-TERMS_EXTENSION")).toHaveText("The buyer gets 60-day payment terms on future invoices (ongoing, no end date)");
  expect((await page.locator("main").innerText()).match(/60-day payment terms/g)).toHaveLength(1);
  await expect(page.getByTestId("deal-asks").locator("li")).toHaveCount(3);
  await expect(page.getByTestId("deal-parsed-terms")).toHaveCount(0);
  // What it costs: the immediate discount on its own line, the forward lines and their total kept apart, never added together.
  const immediate = page.getByTestId("deal-impact-immediate");
  await expect(immediate).toContainText("Immediate discount");
  await expect(immediate.getByTestId("deal-impact-amount")).toHaveText("¥5,040.00");
  await expect(immediate).toContainText("is not part of the forward figure");
  const forward = page.getByTestId("deal-impact-forward");
  await expect(forward).not.toContainText("¥5,040.00");
  await expect(forward.getByTestId("deal-impact-TERMS_EXTENSION")).toContainText("¥24,326.92");
  // The window the forward lines share is said once, above them.
  await expect(forward.getByTestId("deal-impact-window")).toHaveText("Valued over the next 12 months at your cheapest committed source.");
  await expect(forward.getByTestId("deal-impact-CONTINGENT_REBATE")).toContainText("¥4,000.00");
  await expect(forward).toContainText("12-month forward total");
  await expect(forward.getByTestId("deal-impact-total")).toHaveText("¥28,326.92");
  await expect(forward.getByTestId("deal-impact-cap")).toHaveText("Your limit: ¥5,000.00");
  await expect(forward).toContainText("Over your limit");
  await expect(forward.getByTestId("deal-impact-note")).toContainText("the two are not added together");
  // Why it matters: the server's reasons, then the cash facts of the offer as asked: first breach and worst point are two named days.
  await expect(page.getByTestId("deal-why-reasons").locator("li")).toHaveText([
    "The forward concessions in this offer come to ¥28,326.92, above your ¥5,000.00 limit.",
    "Accepted as asked, cash would fall below your minimum in 47 days.",
  ]);
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

  // With the check done there is no Action left to take on this card: the response carries the page's one filled call ("Send this counter").
  await expect(next).toHaveCount(0);
  await expect(response.getByTestId("deal-send")).toHaveClass(/bg-brand-600/);
  // The jump band and the passive stage links are gone, and so is the step line.
  await expect(page.getByRole("link", { name: "See what we'd offer back" })).toHaveCount(0);
  await expect(page.getByTestId("deal-steps")).toHaveCount(0);
  // One fold holds the rest, in the sections the server names, closed.
  const advanced = page.getByTestId("deal-advanced");
  await expect(advanced).not.toHaveAttribute("open", "");
  await expect(advanced.locator("> summary")).toHaveText("Advanced details");
  await advanced.locator("> summary").click();
  expect(await advanced.locator("[data-testid^='deal-adv-']").evaluateAll((els) => els.map((el) => el.getAttribute("data-testid")))).toEqual([
    "deal-adv-parsed_obligations",
    "deal-adv-source_text",
    "deal-adv-checks",
    "deal-adv-formula",
    "deal-adv-engine_verdict",
    "deal-adv-audit_evidence",
  ]);
  for (const key of ["parsed_obligations", "source_text", "checks", "formula", "engine_verdict", "audit_evidence"]) {
    await expect(page.getByTestId(`deal-adv-${key}`)).not.toHaveAttribute("open", "");
  }
  await expect(page.getByTestId("deal-adv-parsed_obligations").locator("> summary")).toHaveText("How the agent read it");
  await page.getByTestId("deal-adv-parsed_obligations").locator("> summary").click();
  await expect(page.getByTestId("deal-parsed-list")).toContainText("Terms extension");
  // Every check, the formulas and the engine's verdict.
  await page.getByTestId("deal-adv-checks").locator("> summary").click();
  await expect(page.getByTestId("deal-adv-checks").locator("> summary")).toContainText("Show all checks (8)");
  await page.getByTestId("deal-adv-engine_verdict").locator("> summary").click();
  await expect(page.getByTestId("deal-technical-summary")).toContainText("the engine's verdict");
  await expect(page.getByTestId("deal-technical-summary")).toContainText("REJECT");
  // The calculation opens with the reading, the equation behind it.
  await page.getByTestId("deal-adv-formula").locator("> summary").click();
  const items = page.getByTestId("deal-calc-item");
  await expect(items.nth(1)).toContainText("60-day terms add 15 days of financing to 13 expected invoices");
  await expect(items.nth(1)).toContainText("¥24,326.92");
  await expect(items.nth(1).locator("details > summary")).toHaveText("Formula");
  await page.getByTestId("deal-adv-audit_evidence").locator("> summary").click();
  await expect(page.getByTestId("deal-audit-evidence")).toContainText("Decision record");
  await advanced.locator("> summary").click();
  // No empty commitments card; the page fits about two screens with the disclosures closed.
  await expect(page.locator("#commitments")).toHaveCount(0);
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  // (the strategy build adds its "Before they ask" card to the page)
  expect(height).toBeLessThanOrEqual(2 * 900 + 100 + (process.env.E2E_STRATEGY === "1" ? 250 : 0));
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // Reading the same message again costs nothing: it is shown, not read twice.
  await page.getByTestId("inbox-back").click();
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Showing below");
  await inbox.getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("inbox-collapsed")).toBeVisible();
  // Sending the counter: the buyer's (simulated) answer comes back in words, and the next step is the agreement.
  await expect(response.getByTestId("deal-send")).toHaveText("Send Option A (simulated buyer reply)");
  // Above the button, in 14 px ink: "This will" and what sending does, from the server's lines; the first press asks, the second sends.
  await expect(response.getByTestId("deal-send-scope")).toContainText("This will");
  await expect(response.getByTestId("deal-send-scope-lines")).toContainText("Draws ¥149,986.20 on the Bank credit line");
  await response.getByTestId("deal-send").click();
  await expect(response.getByTestId("deal-send-confirm-box")).toContainText("The buyer's reply is simulated");
  await response.getByTestId("deal-send-cancel").click();
  await expect(response.getByTestId("deal-send")).toBeVisible();
  await sendCounter(response);
  await expect(page.getByTestId("deal-negotiation")).toContainText("The buyer accepted Option A. The agreement is on your books.");
  await expect(response.getByTestId("deal-send")).toHaveCount(0);
  // The outcome card: the buyer's answer and the way to the agreement (the terms are said once, in the Agreements card); the headline, the chip and the inbox row follow.
  await expect(response.getByRole("heading", { name: "The buyer's answer" })).toBeVisible();
  await expect(response.getByTestId("deal-agreed-terms")).toHaveCount(0);
  await expect(page.locator("#commitments")).toContainText("0.85% off");
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Agreed");
  await expect(page.getByTestId("deal-eyebrow")).toHaveText("Where this deal stands");
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
  // Money and what is left, from the record: cash received today, and the invoice still to be paid.
  await expect(page.getByTestId("deal-money-lines")).toContainText("Received ¥149,986.20 today.");
  // The original ask is history, folded under one heading so it is not read as part of the agreement.
  await expect(page.getByTestId("deal-original").locator("> summary")).toHaveText("The original ask (not agreed)");
  await expect(page.getByTestId("deal-original")).not.toHaveAttribute("open", "");
  await expect(page.getByTestId("deal-left")).toContainText("Waiting for Foshan Home Retail Co. to pay");
  await page.getByTestId("inbox-back").click();
  await expect(inbox.getByTestId("inbox-msg-EX01").getByTestId("inbox-msg-status")).toHaveCount(0); // the message being read says "Showing below"
  await expect(response.getByTestId("deal-option-Option-A")).toHaveCount(0);
  // No band: an agreement in force is said by the chip and the Agreements card.
  await expect(page.getByTestId("next-step")).toHaveCount(0);
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
  await page.getByTestId("inbox-back").click();
  await page.getByTestId("inbox-thread-BUYER-1").locator("details > summary").first().click();
  await inbox.getByTestId("inbox-msg-EX01B").click();
  await expect(page.getByTestId("inbox-collapsed")).toBeVisible();
  await expect(page.locator("#deal-selected")).toBeVisible();
  await expect(page.locator("#counters")).toHaveCount(0);
  // Back to the first: its response card starts closed, as it always did.
  await page.getByTestId("inbox-back").click();
  await expect(inbox.getByTestId("inbox-msg-EX01B")).toHaveAttribute("aria-current", "true");
  const earlier = page.getByTestId("inbox-thread-BUYER-1").locator("details > summary").first();
  if (await inbox.getByTestId("inbox-msg-EX01").isHidden()) await earlier.click();
  await inbox.getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("inbox-collapsed")).toBeVisible();
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
  await expect(page.getByTestId("inbox-blocked")).toContainText("Example only: nothing has been refused in your books yet. A message from a sender you do not know would be set aside here.");
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
  await expect(page.getByTestId("deal-recommendation")).toHaveText("No deal: the buyer did not accept");
  await expect(page.getByTestId("deal-recommendation")).toHaveAttribute("data-outcome", "NO_DEAL");
  await expect(page.getByTestId("deal-if-accept")).toHaveText("If you had accepted the offer as asked:");
  await expect(page.getByTestId("deal-state-chip")).toContainText("No deal");
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "NO_DEAL");
  const outcome = page.locator("#counters");
  await expect(outcome.getByTestId("deal-negotiation")).toContainText("The buyer refused every counter. Nothing was agreed.");
  await expect(outcome.getByTestId("deal-rounds").locator("li")).toHaveCount(3);
  await expect(outcome.getByTestId("deal-rounds")).toContainText("Refused");
  // What happens next: the funding for the gap still ran, and the way to see it.
  await expect(outcome.getByTestId("deal-gap-funded")).toContainText("The funding for your cash gap still ran on your books.");
  await expect(outcome.getByRole("link", { name: "See it in Cash & funding" })).toHaveAttribute("href", "/cash");
  await expect(outcome.getByTestId("deal-send")).toHaveCount(0);
  await expect(page.locator("#commitments")).toHaveCount(0);
  // The Action offers the way back to the inbox, which opens the list.
  await page.getByTestId("next-step").getByRole("button", { name: "Back to the messages" }).click();
  await expect(inbox).toBeVisible();
  // The buyer's own words (which carry the engine's days) are one fold away; the prose has no "day N".
  await expect(outcome.getByTestId("deal-buyer-words")).not.toHaveAttribute("open", "");
  expect(await proseOf(page, ['[data-testid="deal-buyer-words"]', '[data-testid="deal-advanced"]'])).not.toMatch(/\bday \d/i);
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Showing below");
});

test("?buyer= selects that buyer's deal: the chase dialog's thread link lands on the workspace", async ({ page }) => {
  await page.goto("/deals?buyer=BUYER-1");
  await expect(page.locator("#deal-selected")).toContainText("Foshan Home Retail Co.");
  await expect(page.getByTestId("inbox-collapsed")).toBeVisible();
  await expect(page.getByTestId("deal-ask-IMMEDIATE_DISCOUNT")).toBeVisible();
  // A buyer the books do not know selects nothing.
  await page.evaluate(() => sessionStorage.clear());
  await page.goto("/deals?buyer=BUYER-NOBODY");
  await expect(page.getByTestId("inbox-list")).toBeVisible();
  await expect(page.locator("#deal-selected")).toHaveCount(0);
});
