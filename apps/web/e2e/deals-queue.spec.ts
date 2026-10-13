import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { checkedDeal, filledBrand, openCompare, openInbox, openReview } from "./helpers";

/**
 * Deals (map #121, Slice B; tickets #126 to #132): the queue (one row per task, five tabs with the server's counts, a search), the selected negotiation in three levels
 * (decide, consequence, investigate on request), the selection in the address and nothing else, and the commit area. Mock mode, on the API's own recordings: every
 * string asserted is the server's, read from the page or from the recording. The same page on a phone, in Chinese and under axe is at the foot.
 */

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded reads");
});

const OFFER = "OFF-f806f79b6c21";
const DECISION = `deal:${OFFER}`;
const OPTION_B = "CTR-6b07cbf70441";

async function scan(page: Page, label: string) {
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => undefined))));
  const result = await new AxeBuilder({ page }).analyze();
  const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(result.passes.length, `${label}: axe ran its rules`).toBeGreaterThan(10);
  expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`), `${label}: serious or critical findings`).toEqual([]);
}

test("cold: the page is 'Deals' with the state sentence under it, the server's work first, and 'Select a request' while nothing is selected", async ({ page }) => {
  await page.goto("/deals");
  await expect(page.locator("h1")).toHaveText("Deals");
  await expect(page.locator("h1")).toHaveCount(1);
  // Nothing needs the owner at the opening books: the sentence says so, the tabs carry the server's counts, the agreement in force is a row, the alert is pinned above the tabs.
  await expect(page.getByText("Nothing needs you today.")).toBeVisible();
  await expect(page.getByTestId("queue-alert")).toContainText("FLOW action ready");
  await expect(page.getByTestId("queue-count-all")).toHaveText("0");
  await expect(page.getByTestId("queue-count-needs_you")).toHaveText("0");
  await expect(page.getByTestId("queue-count-waiting")).toHaveText("0");
  await expect(page.getByTestId("queue-count-agreements")).toHaveText("0");
  await expect(page.getByTestId("queue-count-customers")).toHaveText("2");
  // Nothing is open, but the owner has customers: the tab says so in the server's words, and "No records" is not said.
  await expect(page.getByTestId("queue-empty")).toContainText("Nothing is open.");
  await page.getByTestId("queue-tab-customers").click();
  await expect(page.getByTestId("queue-row")).toHaveCount(2);
  await expect(page.getByTestId("deals-select")).toContainText("Select a request");
  await expect(page.getByTestId("deal-pane")).toHaveCount(0);
  // "No records" is only for a queue that is empty everywhere: not here.
  await expect(page.getByText("No records")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  await expect(page.locator("body")).not.toContainText(/BUYER-1|OFF-/);
});

test("a message read becomes a negotiation: the address is the selection, the row is the negotiation's own, and the pane opens on it", async ({ page }) => {
  await checkedDeal(page);
  await expect(page).toHaveURL(new RegExp(`/deals\\?customer=BUYER-1&decision=${encodeURIComponent(DECISION).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`));
  const row = page.getByTestId("queue-row").first();
  await expect(row).toContainText("Foshan");
  await expect(row).toContainText("Payment terms");
  await expect(row.getByTestId("queue-status")).toHaveText("Counter ready");
  await expect(row).toHaveAttribute("data-selected", "true");
  await expect(row).toHaveAttribute("data-tier", "needs_you");
  await expect(page.getByTestId("queue-count-needs_you")).toHaveText("1");
  await expect(page.getByText("1 task needs you.")).toBeVisible();
  await expect(page.getByTestId("deal-pane")).toHaveAttribute("data-decision", DECISION);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
  await expect(page.getByTestId("deal-state-chip")).toContainText("Counter recommended");
  // The negotiation is hydrated from the server: the session's own cache plays no part (a reload with it emptied reads the same).
  await page.evaluate(() => sessionStorage.removeItem("tl-demo-v3"));
  await page.reload();
  await expect(page.getByTestId("queue-recommends")).toContainText("Option A");
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
});

test("the tabs filter by who acts next, the search filters the words already read, and an empty tab says so in its own words", async ({ page }) => {
  await checkedDeal(page);
  await page.getByTestId("queue-tab-needs_you").click();
  await expect(page).toHaveURL(/tab=needs_you/);
  await expect(page.getByTestId("queue-row")).toHaveCount(1);
  await page.getByTestId("queue-tab-waiting").click();
  await expect(page.getByTestId("queue-empty")).toContainText("Nothing is waiting on anyone else.");
  await page.getByTestId("queue-tab-agreements").click();
  await expect(page.getByTestId("queue-empty")).toContainText("No agreement is in force.");
  await page.getByTestId("queue-tab-customers").click();
  await expect(page.getByTestId("queue-row")).toHaveCount(2);
  await page.getByTestId("queue-tab-all").click();
  await expect(page.getByTestId("queue-row")).toHaveCount(1);
  await page.getByTestId("queue-search").fill("zzz");
  await expect(page.getByTestId("queue-empty")).toContainText("Nothing matches “zzz”.");
  await page.getByTestId("queue-search").fill("payment terms");
  await expect(page.getByTestId("queue-row")).toHaveCount(1);
  // Arrow keys move between the tabs and the choice follows the focus.
  await page.getByTestId("queue-search").fill("");
  await page.getByTestId("queue-tab-all").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("queue-tab-needs_you")).toHaveAttribute("aria-selected", "true");
});

test("Decide: the ask in the buyer's words, what we recommend and why, who decides and why, and both costs with their basis words", async ({ page }) => {
  await checkedDeal(page);
  await expect(page.getByTestId("queue-heading")).toHaveText("Counter instead of accepting as asked");
  await expect(page.getByTestId("deal-ask-quote")).toContainText("We'll settle the ¥420k early at 1.2%");
  await expect(page.getByTestId("deal-ask-terms")).toContainText("60 days");
  await expect(page.getByTestId("deal-recommends-title")).toHaveText("What we recommend · Option A");
  await expect(page.getByTestId("queue-option")).toContainText("Terms stay at 45 days, no rebate.");
  await expect(page.getByTestId("deal-recommended-reason")).toHaveText("Recommended because FLOW can send it within your mandate without your approval.");
  await expect(page.getByTestId("queue-authority")).toContainText("FLOW can send it");
  await expect(page.getByTestId("deal-authority-reason")).toContainText("within the 1.50% limit you signed");
  // The two costs, each with the words that say what it is: a cheaper-looking figure is never presented as cheaper.
  await expect(page.getByTestId("deal-cost-asked")).toContainText("¥28,326.92");
  await expect(page.getByTestId("deal-cost-asked")).toContainText("over 12 months, plus ¥5,040.00 once");
  await expect(page.getByTestId("queue-cost")).toContainText("¥3,027.77");
  await expect(page.getByTestId("queue-cost")).toContainText("once, nothing ongoing");
  // One filled primary in the commit area; the other two buttons are outlined.
  expect(await filledBrand(page)).toBe(1);
  await expect(page.getByTestId("queue-review-open")).toHaveText("Review and send the counter");
  await expect(page.getByTestId("deal-compare-toggle")).toHaveText("Compare responses");
  await expect(page.getByTestId("deal-chart-toggle")).toHaveText("Cash impact");
});

test("Consequence: the request against the recommended reply, the payment-timing tabs bound to ?scenario=, and the sentence under each column that says what it assumes", async ({ page }) => {
  await checkedDeal(page);
  const table = page.getByTestId("deal-consequence");
  await expect(table.locator("thead th")).toHaveText(["Financial consequence", "As they askedOver your limit", "Option AFLOW recommends"]);
  await expect(page.getByTestId("deal-consequence-row-lowest")).toContainText("¥165k");
  await expect(page.getByTestId("deal-consequence-row-lowest")).toContainText("in 60 days");
  await expect(page.getByTestId("deal-consequence-row-reserve")).toContainText(/below it for 15 days/i);
  await expect(page.getByTestId("deal-consequence-row-limits")).toContainText("exceeded");
  await expect(page.getByTestId("deal-consequence-row-approval")).toContainText("FLOW can send it");
  // Each path states its own footing: the request carries no funding plan, the reply carries its own.
  const assumptions = page.getByTestId("deal-assumption");
  await expect(assumptions).toHaveCount(2);
  await expect(assumptions.first()).toContainText("FLOW takes no new funding");
  await expect(assumptions.last()).toContainText("funding plan runs");
  // The timing assumption is the address: back and forward restore it.
  const tabs = page.getByRole("tablist", { name: "Payment timing assumption" });
  await expect(tabs.getByRole("tab", { name: "Expected payments" })).toHaveAttribute("aria-selected", "true");
  await tabs.getByRole("tab", { name: /30 days late/ }).click();
  await expect(page).toHaveURL(/scenario=late/);
  await expect(page.getByTestId("deal-scenario-panel")).toHaveAttribute("data-scenario", "late");
  await expect(page.getByTestId("deal-consequence-row-lowest")).toContainText("−¥250k");
  await page.goBack();
});

test("Investigate on request: every response in one table with its basis words, the late-payment row, and a pick that changes what the review is about", async ({ page }) => {
  await checkedDeal(page);
  await expect(page.getByTestId("deal-investigate")).toHaveCount(0);
  await openCompare(page);
  await expect(page).toHaveURL(/compare=1/);
  const table = page.getByTestId("deal-compare-table");
  await expect(table.locator("thead th")).toHaveText(["Compare responses", /^As they asked/, /^Option AFLOW recommends/, /^Option BNeeds your approval/, "Do nothing"]);
  await expect(page.getByTestId("deal-compare-table-row-economics")).toContainText("net over 12 months");
  await expect(page.getByTestId("deal-compare-table-row-economics")).toContainText("once, nothing ongoing");
  await expect(page.getByTestId("deal-compare-table-row-lowest")).toContainText("Assumes the buyer accepts this reply");
  await expect(page.getByTestId("deal-compare-table-row-stress")).toContainText("−¥250k");
  await expect(page.getByTestId("deal-compare-table-row-approval")).toContainText("Needs your approval");
  // A comparison never binds the commit: "Review Option B" only chooses which reply the review above is about.
  await page.locator(`[data-testid="deal-use-${OPTION_B}"]:visible`).click();
  await expect(page).toHaveURL(new RegExp(`path=${OPTION_B}`));
  await expect(page.getByTestId("deal-recommends-title")).toHaveText("The response you picked · Option B");
  await expect(page.getByTestId("queue-authority")).toContainText("Needs your approval");
  await expect(page.getByTestId("path-reply-back")).toHaveText("Back to Option A");
  await openReviewFor(page);
  await expect(page.getByTestId("deal-send")).toHaveText("Send Option B to Foshan");
  // The review reads Option B's own receipt (the server priced every sendable reply), not Option A's and not words composed from the path.
  const receiptB = (await page.getByTestId("commitment-receipt").textContent())!;
  await expect(page.getByTestId("deal-unpriced")).toHaveCount(0);
  await page.getByTestId("queue-review-close").click();
  await page.getByTestId("path-reply-back").click();
  await openReviewFor(page);
  expect((await page.getByTestId("commitment-receipt").textContent())!, "Option A's receipt is not Option B's").not.toBe(receiptB);
  await page.getByTestId("queue-review-close").click();
  await expect(page.getByTestId("deal-recommends-title")).toHaveText("What we recommend · Option A");
  // The chart is asked for on its own.
  await expect(page.getByTestId("deal-chart")).toHaveCount(0);
  await page.getByTestId("deal-chart-toggle").click();
  await expect(page).toHaveURL(/chart=1/);
  await expect(page.getByTestId("deal-chart")).toBeVisible();
});

async function openReviewFor(page: Page) {
  await page.getByTestId("queue-review-open").click();
  await page.getByTestId("queue-review").waitFor();
}

test("the address restores the whole state: customer, decision, path, timing and the open investigation, in a fresh read", async ({ page }) => {
  await checkedDeal(page);
  await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(DECISION)}&path=${OPTION_B}&scenario=late&compare=1&tab=needs_you`);
  await expect(page.getByTestId("deal-recommends-title")).toHaveText("The response you picked · Option B");
  await expect(page.getByTestId("deal-scenario-panel")).toHaveAttribute("data-scenario", "late");
  await expect(page.getByTestId("deal-compare-table")).toBeVisible();
  await expect(page.getByTestId("queue-tab-needs_you")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("queue-row").first()).toHaveAttribute("data-selected", "true");
});

test("selecting pushes history, Escape and Close clear the selection, and back restores it", async ({ page }) => {
  await checkedDeal(page);
  await page.getByTestId("deal-close").click();
  await expect(page).toHaveURL(/\/deals$/);
  await expect(page.getByTestId("deals-select")).toBeVisible();
  await page.getByTestId("queue-select").first().click();
  await expect(page).toHaveURL(/decision=/);
  await expect(page.getByTestId("deal-pane")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/deals$/);
  await page.goBack();
  await expect(page.getByTestId("deal-pane")).toBeVisible();
  await page.getByTestId("queue-select").first().focus();
  await expect(page.getByTestId("queue-select").first()).toBeFocused();
});

test("the customer link carries the row's own context and the origin; the aside to the customer's page and back lands on the same negotiation", async ({ page }) => {
  await checkedDeal(page);
  await expect(page.getByTestId("queue-customer").first()).toHaveAttribute("href", `/customers/BUYER-1?decision=${encodeURIComponent(DECISION)}&from=deal`);
  await page.getByTestId("queue-customer").first().click();
  await expect(page.getByTestId("customer-back")).toHaveText("Back to the Foshan deal");
  await page.getByTestId("customer-back").click();
  await expect(page).toHaveURL(/\/deals\?decision=/);
  await expect(page.getByTestId("queue-recommends")).toContainText("Option A");
});

test("a selection that names nothing asks which negotiation and never shows a sample", async ({ page }) => {
  await page.goto("/deals?decision=deal%3AOFF-nope");
  await expect(page.getByTestId("deal-ask-which")).toContainText("Which negotiation?");
  await expect(page.getByTestId("deal-irrelevant")).toContainText("does not match anything open");
  await expect(page.getByTestId("queue-recommends")).toHaveCount(0);
  await page.getByTestId("deal-which-close").click();
  await expect(page).toHaveURL(/\/deals$/);
  // Another customer's negotiation than the address names is asked about too.
  await checkedDeal(page);
  await page.goto(`/deals?customer=BUYER-2&decision=${encodeURIComponent(DECISION)}`);
  await expect(page.getByTestId("deal-ask-which")).toBeVisible();
  await expect(page.getByTestId("queue-recommends")).toHaveCount(0);
});

test("a deal not yet checked offers one action, Check against my limits, and no review", async ({ page }) => {
  await page.goto("/deals");
  await openInbox(page);
  await page.getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("queue-check")).toBeVisible();
  await expect(page.getByTestId("queue-check-button")).toHaveText("Check against my limits");
  expect(await filledBrand(page)).toBe(1);
  await expect(page.getByTestId("queue-review-open")).toHaveCount(0);
  await expect(page.getByTestId("deal-level-consequence")).toHaveCount(0);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RECEIVED");
});

test("a send in flight holds the selection: the rows, the close and the tabs wait, and the send is not unmounted", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-negotiate-slow", "1500"));
  await checkedDeal(page);
  await openReview(page);
  await page.getByTestId("deal-send").click();
  await expect(page.getByTestId("deal-send")).toBeDisabled();
  await expect(page.getByTestId("deal-close")).toBeDisabled();
  await expect(page.getByTestId("queue-select").first()).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("deal-pane")).toBeVisible();
  await expect(page.getByTestId("deal-sent")).toContainText("The buyer accepted Option A.");
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
});

test("when the books moved the API refuses, nothing is sent, and Check again is an explicit step", async ({ page }) => {
  await checkedDeal(page);
  await openReview(page);
  await page.evaluate(() => sessionStorage.setItem("tl-mock-counter-changed", "moved"));
  await page.getByTestId("deal-send").click();
  const changed = page.getByTestId("deal-counter-changed");
  await expect(changed).toContainText("The books moved since this was shown");
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
  await changed.getByTestId("deal-check-again").click();
  await expect(changed).toHaveCount(0);
  await expect(page.getByTestId("queue-recommends")).toBeVisible();
});

test("the page in Chinese: the same negotiation in the owner's voice with the same figures", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await checkedDeal(page);
  await expect(page.locator("h1")).toHaveText("交易");
  await expect(page.getByTestId("queue-tab-needs_you")).toContainText("需要您");
  await expect(page.getByTestId("deal-recommends-title")).toContainText("我们的建议");
  await expect(page.getByTestId("queue-review-open")).toHaveText("查看并发送还价");
  await expect(page.getByTestId("deal-cost-asked")).toContainText("¥28,326.92");
  await scan(page, "/deals zh");
});

test("a phone: the rows stack, nothing scrolls sideways, the tabs scroll inside their own track, and the controls reach 44 px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await checkedDeal(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  for (const id of ["queue-review-open", "deal-compare-toggle", "deal-chart-toggle"]) {
    const box = (await page.getByTestId(id).boundingBox())!;
    expect(box.height, id).toBeGreaterThanOrEqual(44);
    expect(box.x >= 0 && box.x + box.width <= 390, `${id} fits`).toBe(true);
  }
  await expect(page.getByTestId("queue-review-open")).toBeVisible();
  await openCompare(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  await scan(page, "/deals phone");
});

test("axe finds nothing serious or critical on the queue with the review, the comparison and the chart open", async ({ page }) => {
  await checkedDeal(page);
  await openReview(page);
  await openCompare(page);
  await page.getByTestId("deal-chart-toggle").click();
  await scan(page, "/deals open");
});
