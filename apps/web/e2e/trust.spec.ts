import { expect, test } from "./fixtures";

/**
 * Wave 1 (map #65), mock mode. Each story is one recording from the real API (mocks/w1_approval_stories.json and the no-receipt home
 * files, scripts/record-mocks.mjs), switched on by a sessionStorage hook that is set before the page loads:
 *   tl-mock-approval-story  agreement | expired | refused     (lib/mock/handlers.ts)
 *   tl-mock-no-receipt      1 | half                          (lib/mock/home.ts)
 */

async function story(page: import("@playwright/test").Page, key: string, value: string) {
  await page.addInitScript(([k, v]) => sessionStorage.setItem(k, v), [key, value]);
}

test("an agreement approval shows the buyer, the terms and the amount above the buttons", async ({ page }) => {
  await story(page, "tl-mock-approval-story", "agreement");
  await page.goto("/approvals");
  const card = page.locator("#approval-APR-000001");
  await expect(card.getByTestId("approval-headline")).toHaveText("Approve this agreement with Foshan Home Retail Co.?");
  await expect(card.getByTestId("approval-buyer")).toHaveText("Foshan Home Retail Co.");
  const terms = card.getByTestId("approval-terms");
  await expect(terms).toContainText("The buyer may pay early and take 0.50% off the ¥420,000.00 invoice to Foshan Home Retail Co.");
  // A zero forward value is not shown as "¥0.00": the server sends its sentence instead.
  await expect(card.getByTestId("approval-forward")).toHaveText("No cost over the valuation window beyond the early-payment discount.");
  await expect(card).not.toContainText("¥0.00");
  await expect(card).toContainText("¥420,000.00");
  await expect(card).not.toContainText("Accept offer");
  // Everything the owner decides on is above the buttons, not behind "Audit details".
  const approve = card.getByRole("button", { name: /^Approve/ });
  await expect(approve).toBeEnabled();
  const [t, b] = [await terms.boundingBox(), await approve.boundingBox()];
  expect(t!.y).toBeLessThan(b!.y);
  await expect(card.getByTestId("approval-detail-APR-000001")).toBeHidden();
  // The ids and the terms hash stay in the fold.
  await card.getByTestId("approval-toggle-APR-000001").locator("> summary").click();
  await expect(card.getByTestId("approval-detail-APR-000001")).toContainText("Terms hash");
});

test("when the server cannot present the terms, Approve is disabled, the reason is shown and Decline stays", async ({ page }) => {
  await story(page, "tl-mock-approval-story", "expired");
  await page.goto("/approvals");
  const card = page.locator("#approval-APR-000001");
  const gap = card.getByTestId("approval-terms-unavailable");
  await expect(gap).toContainText("I can't safely present the full terms for review. Approval is unavailable until the decision record is restored.");
  await expect(gap).toContainText("The agreement this approval refers to has expired.");
  await expect(card.getByTestId("approval-terms")).toHaveCount(0);
  const approve = card.getByRole("button", { name: /^Approve/ });
  await expect(approve).toBeDisabled();
  await expect(approve).toHaveAttribute("aria-describedby", /terms-APR-000001/);
  await expect(card.getByRole("button", { name: "Decline", exact: true })).toBeEnabled();
  // "Try again" reads the queue again; the server still cannot present the terms, so the gate holds.
  await gap.getByRole("button", { name: "Try again" }).click();
  await expect(gap).toBeVisible();
  await expect(approve).toBeDisabled();
});

test("an approval the executor refuses ends as 'could not run', with no buttons and no money moved", async ({ page }) => {
  await story(page, "tl-mock-approval-story", "refused");
  await page.goto("/approvals");
  const card = page.locator("#approval-APR-000001");
  await card.getByRole("button", { name: /^Approve/ }).click();
  const refused = card.getByTestId("approval-refused-APR-000001");
  await expect(refused).toContainText("You approved it, but it could not run: Mandate v1 expired yesterday. No money moved.");
  await expect(refused).not.toContainText("declined");
  await expect(card).toContainText("Approved");
  await expect(card.getByRole("button", { name: /^Approve/ })).toHaveCount(0);
  await expect(card.getByRole("button", { name: "Decline", exact: true })).toHaveCount(0);
  // The queue was read again: after a reload the card is still terminal.
  await page.reload();
  await expect(page.locator("#approval-APR-000001").getByTestId("approval-refused-APR-000001")).toBeVisible();
});

test("day 34 without a receipt: the Home says it is below the reserve today, never 'N days ago'", async ({ page }) => {
  await story(page, "tl-mock-no-receipt", "1");
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await expect(page.getByTestId("home-headline")).toHaveText("Below reserve today.");
  const hero = page.getByTestId("home-status");
  await expect(hero).toContainText("Below reserve today");
  await expect(page.getByTestId("home-breach-cash")).toHaveText("¥45k");
  await expect(hero).not.toContainText(/ago/);
  // The Cash page reads the same facts and starts its chart today.
  await page.goto("/cash");
  await expect(page.getByTestId("cash-unsafe-when")).toHaveText("¥45k");
  await expect(page.getByText("Below reserve today").first()).toBeVisible();
});

test("a part-paid promise names its four facts and the window under the server's sentence", async ({ page }) => {
  await story(page, "tl-mock-no-receipt", "half");
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  // The late row may sit behind "Show more"; open it when it does.
  const more = page.getByTestId("home-changes-more");
  if (await more.count()) await more.locator("> summary").click();
  const late = page.getByTestId("home-change-LATE").filter({ has: page.getByTestId("home-change-facts") });
  await expect(late).toHaveCount(1);
  // The sentence stays; the facts are named beneath it.
  await expect(late.getByTestId("home-change-text")).toContainText("Received ¥127,506.90 from Foshan Home Retail Co.");
  const facts = late.getByTestId("home-change-facts");
  await expect(facts.getByTestId("home-change-facts-received")).toContainText("Cash received");
  await expect(facts.getByTestId("home-change-facts-received")).toContainText("¥127,506.90");
  await expect(facts.getByTestId("home-change-facts-cleared")).toContainText("Invoice face cleared");
  await expect(facts.getByTestId("home-change-facts-cleared")).toContainText("¥128,600.00");
  await expect(facts.getByTestId("home-change-facts-discount")).toContainText("¥1,093.10");
  await expect(facts.getByTestId("home-change-facts-remaining")).toContainText("Remaining balance");
  await expect(facts.getByTestId("home-change-facts-remaining")).toContainText("¥291,400.00");
  await expect(facts).toContainText("Early-payment window ended");
  // A row without the facts renders no list.
  await expect(page.getByTestId("home-change-facts")).toHaveCount(1);
});
