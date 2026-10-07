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
  // The unknown sender's message never reached the agent, so the line says it was set aside and shows it on demand.
  await expect(page.getByTestId("inbox-blocked")).toContainText("1 message from an unknown sender was set aside");
  await page.getByTestId("inbox-blocked").getByText("Show it").click();
  await expect(page.getByTestId("inbox-blocked")).toContainText("FastCapital");
  // Step 11 selected the reworded offer; the original is in the thread, evaluated, with its recommendation in words, no code.
  const reworded = inbox.getByTestId("inbox-msg-EX01B");
  const original = inbox.getByTestId("inbox-msg-EX01");
  await expect(reworded).toHaveAttribute("aria-current", "true");
  // Step 8 ran the hard-line negotiation on the original offer, so its row says how it ended.
  await expect(original).toContainText("No deal");
  await expect(original).not.toContainText("REJECT");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  await original.click();
  await expect(original).toHaveAttribute("aria-current", "true");
  await expect(reworded).not.toHaveAttribute("aria-current", "true");
  await expect(page.getByTestId("deal-recommendation")).toHaveText("No deal");
  await expect(page.getByTestId("deal-steps").getByRole("link", { name: /Reply/ })).toHaveAttribute("href", "/deals#counters");
  await expect(page.getByTestId("deal-steps").getByRole("link", { name: /No deal/ })).toHaveAttribute("href", "/deals#commitments");
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
  await expect(next.getByRole("link", { name: "See the counter-offer" })).toHaveAttribute("href", "#counters");
  for (const id of ["deal-why", "deal-original", "deal-calc"]) {
    await expect(page.getByTestId(id)).not.toHaveAttribute("open", "");
  }
  await expect(page.getByTestId("deal-why")).toContainText("Why FLOW recommends this");
  await page.getByTestId("deal-why").locator("> summary").click();
  await expect(page.getByTestId("deal-technical-summary")).toContainText("Engine verdict");
  await expect(page.getByTestId("deal-technical-summary")).toContainText("REJECT");
  await page.getByTestId("deal-why").locator("> summary").click();
  // No empty commitments card; the page fits about two screens with the disclosures closed.
  await expect(page.locator("#commitments")).toHaveCount(0);
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  expect(height).toBeLessThanOrEqual(2 * 900 + 100);
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // Reading the same message again costs nothing: it is shown, not read twice.
  await inbox.getByTestId("inbox-msg-EX01").click();
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Showing below");
});

/** Open the Foshan offer in Business mode and check it, ready to send the recommended counter. */
async function checkedOffer(page: import("@playwright/test").Page) {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Counter recommended");
  return page.locator("#counters");
}

test("sending the recommended counter asks first, and Cancel sends nothing", async ({ page }) => {
  const response = await checkedOffer(page);
  const a = response.getByTestId("deal-option-Option-A");
  await expect(response.getByTestId("deal-send-open")).toHaveCount(1);
  await expect(response.getByTestId("deal-option-Option-B")).toHaveCount(0);
  await a.getByTestId("deal-send-open").click();
  const confirm = a.getByTestId("deal-send-confirm");
  await expect(confirm).toContainText("Send Option A to Foshan Home Retail Co.?");
  await expect(confirm).toContainText("simulated");
  await expect(confirm).toContainText("FLOW offers Option B next");
  await confirm.getByTestId("deal-send-cancel").click();
  await expect(a.getByTestId("deal-send-confirm")).toHaveCount(0);
  await expect(response.getByTestId("deal-rounds")).toHaveCount(0);
  await expect(page.getByTestId("deal-steps")).not.toContainText("No deal");
});

test("the buyer open to a counter accepts Option A: the deal is agreed, with the buyer's reply and the funding", async ({ page }) => {
  const response = await checkedOffer(page);
  await response.getByTestId("deal-send-open").click();
  await response.getByTestId("deal-send").click();
  await expect(response).toContainText("Accepted by the buyer");
  await expect(response.getByTestId("deal-rounds")).toContainText("We accept Option A as proposed.");
  await expect(response.getByTestId("deal-negotiation")).toContainText("The buyer accepted Option A");
  await expect(response.getByTestId("deal-gap-funded")).toContainText("Bank credit line");
  await expect(response.getByTestId("deal-gap-funded")).not.toContainText("FAC-");
  await expect(response.getByTestId("deal-send-open")).toHaveCount(0);
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Agreed with the buyer");
});

test("the buyer who holds firm refuses every counter: no deal, each reply shown, the gap still funded", async ({ page }) => {
  const response = await checkedOffer(page);
  await response.getByTestId("deal-send-open").click();
  await response.getByLabel("Holds firm").check();
  await response.getByTestId("deal-send").click();
  await expect(response.getByTestId("deal-negotiation")).toContainText("No deal");
  await expect(response.getByTestId("deal-rounds").locator("li")).toHaveCount(3);
  await expect(response.getByTestId("deal-rounds")).toContainText("Option B");
  await expect(response.getByTestId("deal-gap-funded")).toBeVisible();
  await expect(page.getByTestId("deal-recommendation")).toHaveText("No deal");
});
