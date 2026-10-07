import { expect, test } from "./fixtures";

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
  await expect(page.getByTestId("inbox-blocked")).toContainText("1 suspicious message was blocked");
  await expect(page.getByTestId("inbox-blocked").getByRole("link", { name: "See what was refused" })).toHaveAttribute("href", "/activity#refused");
  // Step 11 selected the reworded offer; the original is in the thread, evaluated, with its recommendation in words, no code.
  const reworded = inbox.getByTestId("inbox-msg-EX01B");
  const original = inbox.getByTestId("inbox-msg-EX01");
  await expect(reworded).toHaveAttribute("aria-current", "true");
  await expect(original).toContainText("Counter recommended");
  await expect(original).not.toContainText("REJECT");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  await original.click();
  await expect(original).toHaveAttribute("aria-current", "true");
  await expect(reworded).not.toHaveAttribute("aria-current", "true");
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Counter recommended");
  await expect(page.getByTestId("deal-steps").getByRole("link", { name: /Respond/ })).toHaveAttribute("href", "/deals#counters");
  await expect(page.getByTestId("deal-steps").getByRole("link", { name: /Agreed/ })).toHaveAttribute("href", "/deals#commitments");
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
  await expect(next).toContainText(/agree|books/i);
});
