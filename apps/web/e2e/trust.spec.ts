import { expect, test } from "./fixtures";
import { openOperatorTools } from "./helpers";

/**
 * Wave 1 (map #65), mock mode. Each story is one recording from the real API (mocks/w1_approval_stories.json and the no-receipt home
 * files, scripts/record-mocks.mjs), switched on by a sessionStorage hook that is set before the page loads:
 *   tl-mock-approval-story  agreement | expired | refused     (lib/mock/handlers.ts)
 *   tl-mock-no-receipt      1 | half                          (lib/mock/home.ts)
 */

async function story(page: import("@playwright/test").Page, key: string, value: string) {
  await page.addInitScript(([k, v]) => sessionStorage.setItem(k, v), [key, value]);
}

test("an agreement approval shows the buyer, the terms and the amount above the buttons", async ({ page }, info) => {
  test.skip(info.project.name === "live", "mock-mode spec: the recorded approval stories");
  await story(page, "tl-mock-approval-story", "agreement");
  await page.goto("/approvals");
  const card = page.locator("#approval-APR-000001");
  await expect(page.getByTestId("approval-headline")).toHaveText("Approve this agreement with Foshan Home Retail Co.?");
  await expect(card.getByTestId("approval-buyer")).toHaveText("Foshan Home Retail Co.");
  const terms = card.getByTestId("approval-terms");
  await expect(terms).toContainText("The buyer may pay early and take 0.50% off the ¥420,000.00 invoice to Foshan Home Retail Co.");
  // A zero forward value is not shown as "¥0.00": the server sends its sentence instead.
  await expect(card.getByTestId("approval-forward")).toHaveText("No cost over the valuation window beyond the early-payment discount.");
  await expect(card).not.toContainText("¥0.00");
  await expect(card).toContainText("¥420,000.00");
  await expect(card).not.toContainText("Accept offer");
  // The button says what is agreed (the server's label, with the discount and its size), and why it is the owner's: the server's words.
  await expect(card.getByRole("button", { name: "Approve the agreement (0.50% early-payment discount, about ¥2,100.00)" })).toBeVisible();
  await expect(card.getByTestId("approval-reason")).toHaveText("This changes the terms with a buyer, which you keep for yourself.");
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

test("when the server cannot present the terms, Approve is disabled, the reason is shown and Decline stays", async ({ page }, info) => {
  test.skip(info.project.name === "live", "mock-mode spec: the recorded approval stories");
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

test("an approval the executor refuses ends as 'could not run', with no buttons and no money moved", async ({ page }, info) => {
  test.skip(info.project.name === "live", "mock-mode spec: the recorded approval stories");
  await story(page, "tl-mock-approval-story", "refused");
  await page.goto("/approvals");
  const card = page.locator("#approval-APR-000001");
  await card.getByRole("button", { name: /^Approve/ }).click();
  const refused = card.getByTestId("approval-refused-APR-000001");
  await expect(refused).toContainText("You approved it, but it could not run: your signed limits (version 1) expired yesterday. No money moved.");
  await expect(refused).not.toContainText("declined");
  // The title is in the past tense and a refusal says where to go next (the server's sentence and route).
  await expect(card.getByTestId("approval-headline")).toContainText("Approved, but it did not run");
  await expect(card.getByTestId("approval-next-APR-000001")).toHaveAttribute("href", "/limits");
  await expect(card).toContainText("Approved");
  await expect(card.getByRole("button", { name: /^Approve/ })).toHaveCount(0);
  await expect(card.getByRole("button", { name: "Decline", exact: true })).toHaveCount(0);
  // The queue was read again: after a reload the card is still terminal.
  await page.reload();
  await expect(page.locator("#approval-APR-000001").getByTestId("approval-refused-APR-000001")).toBeVisible();
});

test("day 34 without a receipt: the Home says it is below the reserve today, never 'N days ago'", async ({ page }, info) => {
  test.skip(info.project.name === "live", "mock-mode spec: the recorded approval stories");
  await story(page, "tl-mock-no-receipt", "1");
  await page.goto("/demo");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await expect(page.getByTestId("home-headline")).toHaveText("Below reserve today.");
  const hero = page.getByTestId("home-status");
  await expect(hero).toContainText("Below reserve today");
  // Already under the minimum: nothing in the header says "N days ago".
  await expect(hero).not.toContainText(/ago/);
  // The Cash page reads the same facts and starts its chart today.
  await page.goto("/cash");
  await expect(page.getByTestId("cash-unsafe-when")).toHaveText("¥255k");
  await expect(page.getByText("Short of your minimum today").first()).toBeVisible();
  await expect(page.getByTestId("cash-figures")).toContainText("Cash today ¥45k");
});

test("a part-paid promise: Receivables names the four facts and the window", async ({ page }, info) => {
  test.skip(info.project.name === "live", "mock-mode spec: the recorded approval stories");
  await story(page, "tl-mock-no-receipt", "half");
  await page.goto("/demo");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  // The Receivables receipt row is where the four facts are named: a short lead, the facts (the balance largest) and the window in words.
  await page.goto("/receivables");
  const facts = page.getByTestId("receipt-facts-rec-receipt-1");
  await expect(page.getByTestId("receipt-lead-rec-receipt-1")).toContainText("Part-paid by Foshan Home Retail Co.");
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-received")).toContainText("Cash received");
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-remaining")).toContainText("¥291,400.00");
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-remaining").locator("dd")).toHaveClass(/font-bold/);
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-window")).toHaveText("The early-payment window has ended");
});

// ---- Slice D: the /trust address (evidence links land here; mock mode, the recorded story) ----

test.describe("the trust views are chosen by the address", () => {
  test("?view=evidence shows the record's entries in words, a marked entry and the way back by origin", async ({ page }) => {
    await page.goto("/trust?view=evidence&entry=1&from=activity");
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    const back = page.getByTestId("trust-back");
    await expect(back).toHaveText("Back to Activity");
    await expect(back).toHaveAttribute("href", "/activity");
    // The way back is the first control on the page's main content.
    const firstControl = await page.locator("main a, main button, main summary, main [role=tab]").first().getAttribute("data-testid");
    expect(firstControl).toBe("trust-back");
    const entry = page.getByTestId("trust-entry-1");
    await expect(entry).toHaveAttribute("aria-current", "true");
    await expect(entry).toHaveAttribute("data-marked", "true");
    await expect(entry).toBeFocused();
    await expect(entry).toBeInViewport();
    await expect(entry).toContainText("The record you opened");
    // The seeded document confirmations carry the ledger's own words, not the fallback.
    await expect(page.getByTestId("trust-entry-1").getByTestId("trust-entry-kind")).not.toHaveText("Record entry");
    // Only that entry is marked; each entry says what it is in words, never the engine's kind code.
    await expect(page.locator('[data-marked="true"]')).toHaveCount(1);
    for (const kind of await page.getByTestId("trust-entry-kind").allTextContents()) expect(kind).not.toMatch(/^[A-Z][A-Z_]{3,}$/);
    // The raw file stays a preview under a fold, and the download stays.
    await expect(page.getByTestId("evidence-raw")).not.toHaveAttribute("open", "");
    await expect(page.getByTestId("download-evidence")).toBeVisible();
    await back.click();
    await expect(page).toHaveURL(/\/activity$/);
  });

  test("an entry the record does not have says nothing was removed", async ({ page }) => {
    await page.goto("/trust?view=evidence&entry=9999");
    await expect(page.getByTestId("trust-entry-missing")).toContainText("Nothing was removed");
    await expect(page.getByTestId("trust-back")).toHaveCount(0);
  });

  test("from=demo says 'Back to the story'; the view switch keeps the origin", async ({ page }) => {
    await page.goto("/trust?view=security&from=demo");
    await expect(page.getByTestId("trust-back")).toHaveText("Back to the story");
    await page.getByTestId("trust-view-evidence").click();
    await expect(page).toHaveURL(/view=evidence/);
    await expect(page).toHaveURL(/from=demo/);
    await expect(page.getByTestId("trust-evidence")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  });

  test("an event in the address is marked in the security view, with its words and a list of disclosed fields", async ({ page }) => {
    await page.goto("/trust?view=security");
    await page.getByTestId("trust-security-run").click();
    const first = page.locator('[data-testid^="event-SEC"]').first();
    await expect(first).toBeVisible();
    const id = (await first.getAttribute("data-testid"))!.replace("event-", "");
    await page.goto(`/trust?view=security&event=${id}&from=activity`);
    // The scene is a session thing in the mock: run it again in this page load if the events are not there.
    if (!(await page.getByTestId(`event-${id}`).count())) {
      await page.getByTestId("trust-security-run").click();
    }
    const marked = page.getByTestId(`event-${id}`);
    await expect(marked).toHaveAttribute("aria-current", "true");
    await expect(marked).toContainText("The record you opened");
    await expect(marked).not.toContainText(/Day \d+/);
    await expect(page.getByTestId("sec-disclosed-list").or(page.getByText("None").first())).toBeVisible();
  });

  test("in Chinese the way back and the marks are in Chinese; at 390 px nothing scrolls sideways", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
    await page.goto("/trust?view=evidence&entry=1&from=activity");
    await expect(page.getByTestId("trust-back")).toHaveText("返回动态");
    await expect(page.getByTestId("trust-entry-1")).toContainText("您打开的这条记录");
    await page.setViewportSize({ width: 390, height: 844 });
    const wide = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(wide).toBe(false);
  });
});

test.describe("a record the address names that is not in the record says so", () => {
  test("an event id that is not in the security record, and an entry that is not a number", async ({ page }) => {
    await page.goto("/trust?view=security&event=SEC-NOT-THERE");
    await expect(page.getByTestId("trust-event-missing")).toContainText("Nothing was removed");
    await page.goto("/trust?view=evidence&entry=abc");
    await expect(page.getByTestId("trust-entry-missing")).toContainText("Nothing was removed");
    await expect(page.locator('[data-marked="true"]')).toHaveCount(0);
  });
});
