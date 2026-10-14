import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { checkedDeal, expandRow, filledBrand, openCompare, openInbox, openReview } from "./helpers";

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
  // Nothing needs the owner at the opening books: the sentence says so; the alert is the page's own row above the queue.
  await expect(page.getByText("Nothing needs you today.")).toBeVisible();
  await expect(page.getByTestId("queue-alert")).toContainText("FLOW action ready");
  // Round three (section 9): with fewer than two negotiations the queue is its rows and nothing else (no lifecycle tabs); the total is the queue's own, and the alert is the page's row, counted nowhere.
  await expect(page.getByTestId("queue-total")).toHaveText("0");
  await expect(page.getByTestId("queue-tabs")).toHaveCount(0);
  // The queue lists negotiations only (round two): there is no Customers tab, and an approval or a collection is not a row here.
  await expect(page.getByTestId("queue-tab-customers")).toHaveCount(0);
  // Nothing is open: the tab says so in the server's words, and "No records" is not said.
  await expect(page.getByTestId("queue-empty")).toContainText("Nothing is open.");
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
  await expect(row).toContainText("60-day terms on future invoices");
  await expect(row.getByTestId("queue-status")).toHaveText("Counter ready");
  await expect(row).toHaveAttribute("data-selected", "true");
  await expect(row).toHaveAttribute("data-tier", "needs_you");
  await expect(page.getByTestId("queue-total")).toHaveText("1");
  await expect(page.getByText("1 task needs you.")).toBeVisible();
  await expect(page.getByTestId("deal-pane")).toHaveAttribute("data-decision", DECISION);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
  await expect(page.getByTestId("deal-state-chip")).toContainText("Counter ready");
  // The negotiation is hydrated from the server: the session's own cache plays no part (a reload with it emptied reads the same).
  await page.evaluate(() => sessionStorage.removeItem("tl-demo-v3"));
  await page.reload();
  await expect(page.getByTestId("queue-recommends")).toContainText("Option A");
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
});

test("with one negotiation the tabs, the search and the controls are not offered; the lifecycle tabs, search, sort and group appear with more rows (the busy books, in slice-b-round-three.spec.ts)", async ({ page }) => {
  await checkedDeal(page);
  for (const gone of ["queue-tabs", "queue-tab-needs_you", "queue-search", "queue-controls", "queue-sort-urgency", "queue-group"]) await expect(page.getByTestId(gone)).toHaveCount(0);
  await expect(page.getByTestId("queue-row")).toHaveCount(1);
  // A tab named in an old address changes nothing for a queue that has none.
  await page.goto(`${new URL(page.url()).pathname}${new URL(page.url()).search}&tab=waiting`);
  await expect(page.getByTestId("queue-row")).toHaveCount(1);
});
test("Overview: the ask in one line, FLOW's reply, the mandate sentence, the terms by scope; who decides and the costs are one tab on (Compare responses)", async ({ page }) => {
  await checkedDeal(page);
  await expect(page.getByTestId("queue-heading")).toHaveText("Counter instead of accepting as asked");
  await expect(page.getByTestId("queue-ask")).toContainText("early settlement of ¥420,000.00 at 1.20%");
  await expect(page.getByTestId("deal-recommends-title")).toHaveText("FLOW's reply · Option A");
  await expect(page.getByTestId("queue-option")).toContainText("Terms stay at 45 days, no rebate.");
  await expect(page.getByTestId("deal-mandate")).toHaveText("Option A is the reply FLOW can send within your mandate.");
  // The buyer's own words are in the Messages tab.
  await page.getByTestId("deal-tab-messages").click();
  await expect(page.getByTestId("deal-ask-quote-messages")).toContainText("We'll settle the ¥420k early at 1.2%");
  await page.getByTestId("deal-tab-overview").click();
  // The terms by scope, the changed cells marked by a tint (and carrying the server's "instead of" words), never an underline.
  const terms = page.getByTestId("deal-scope-terms-table");
  await expect(terms.locator("thead th")).toHaveText(["Buyer asks", /^FLOW counters/, "Option B"]);
  await expect(page.getByTestId("deal-scope-terms-row-future")).toContainText("60 days");
  await expect(page.getByTestId("deal-scope-terms-row-future").locator("td[data-changed=true]")).toHaveCount(2);
  // Who decides and why, and both costs with their basis words, are in the comparison.
  await page.getByTestId("deal-tab-compare").click();
  await expect(page.getByTestId("deal-why-reason")).toHaveText("Recommended because FLOW can send it within your mandate without your approval.");
  await expect(page.getByTestId("deal-why-authority")).toContainText("within the 1.50% limit you signed");
  await expandRow(page, "economic");
  const visible = (id: string) => page.locator(`[data-testid="${id}"]:visible`);
  await expect(visible("deal-cost-table-total-asked")).toContainText("¥28,326.92");
  await expect(visible("deal-cost-table-total-asked")).toContainText("over 12 months, plus ¥5,040.00 once");
  await expect(visible("deal-cost-table-total-reply").first()).toContainText("¥3,027.77");
  await expect(visible("deal-cost-table-total-reply").first()).toContainText("once, nothing ongoing");
  // One filled primary: the header's review; the Overview's Compare responses is outlined.
  expect(await filledBrand(page)).toBe(1);
  await expect(page.getByTestId("queue-review-open")).toHaveText("Review the counter");
});
test("Cash consequences: the outcome table and the compared cash rows hold the request against the replies; the payment-timing tabs are bound to ?scenario= on Cash impact", async ({ page }) => {
  await checkedDeal(page);
  await page.getByTestId("deal-tab-compare").click();
  // One place per fact: the cash, the reserve, the financing and who may send each response are the outcome table's (the columns above it carry the terms, the economics and the buyer's status).
  const outcomes = page.getByTestId("deal-outcomes");
  await expect(outcomes.getByTestId("deal-outcome-row-lowest")).toContainText("¥165k");
  await expect(outcomes.getByTestId("deal-outcome-row-when")).toContainText("in 60 days");
  await expect(outcomes.getByTestId("deal-outcome-row-reserve")).toContainText("Breached by ¥135k for 15 days");
  await expect(outcomes.getByTestId("deal-outcome-row-send")).toContainText("FLOW can send");
  await expect(outcomes.getByTestId("deal-outcome-row-financing")).toContainText("¥150k credit-line draw today");
  await expect(page.getByTestId("deal-compare-row-cash")).toHaveCount(0);
  await expect(page.getByTestId("deal-compare-row-authority")).toHaveCount(0);
  // The funding each response rests on is said in "What each option assumes", once.
  await expect(page.getByTestId("deal-why-assumes")).toContainText("¥150k credit-line draw today");
  await page.getByTestId("deal-tab-cash").click();
  // The timing assumption is the address: back and forward restore it.
  const tabs = page.getByRole("tablist", { name: "Payment timing assumption" });
  await expect(tabs.getByRole("tab", { name: "Expected payments" })).toHaveAttribute("aria-selected", "true");
  await tabs.getByRole("tab", { name: /30 days late/ }).click();
  await expect(page).toHaveURL(/scenario=late/);
  await expect(page.getByTestId("deal-chart")).toHaveAttribute("data-late", "true");
  await expect(page.getByTestId("deal-inspector-lowest-asked")).toContainText("−¥250k");
  await tabs.getByRole("tab", { name: "Expected payments" }).click();
  await expect(page.getByTestId("deal-chart")).toHaveAttribute("data-late", "false");
});
test("Compare responses: the packages in one table with their short words, the evidence behind it, and a pick that changes what the review is about", async ({ page }) => {
  await checkedDeal(page);
  await expect(page.getByTestId("deal-panel-compare")).toHaveCount(0);
  await openCompare(page);
  await expect(page).toHaveURL(/view=compare/);
  // "Why these results differ": the server's reason, who decides each path and why, the assumptions, and the rule in words.
  await expect(page.getByTestId("deal-why-reason")).toContainText("Recommended because");
  await expect(page.getByTestId("deal-why-rule")).toHaveText("FLOW recommends the first reply it may send within your mandate; it does not rank replies by cost.");
  const table = page.getByTestId("deal-compare-table");
  await expect(table.locator("thead th").filter({ hasText: /\S/ })).toHaveText([/^Buyer request/, /^Option A/, /^Option B/]);
  await expect(page.getByTestId("deal-compare-cell-economic-reply").nth(1)).toContainText("Net economic cost over 12 months");
  await expect(page.getByTestId("deal-compare-cell-economic-reply").first()).toContainText("One-off cost, nothing ongoing");
  await expect(page.getByTestId("deal-outcome-row-reserve")).toContainText("Held, no buffer at the lowest point");
  await expect(page.getByTestId("deal-outcome-row-send")).toContainText("Needs your approval");
  // A comparison never binds the commit: "Review Option B" only chooses which reply the review is about.
  await page.locator(`[data-testid="deal-use-${OPTION_B}"]:visible`).click();
  await expect(page).toHaveURL(new RegExp(`path=${OPTION_B}`));
  await openReviewFor(page);
  await expect(page.getByTestId("deal-send")).toHaveText("Send Option B to Foshan");
  // The review reads Option B's own receipt (the server priced every sendable reply), not Option A's and not words composed from the path.
  const receiptB = (await page.getByTestId("commitment-receipt").textContent())!;
  await expect(page.getByTestId("deal-unpriced")).toHaveCount(0);
  await page.getByTestId("queue-review-close").click();
  await page.getByTestId("deal-back").click();
  await expect(page.getByTestId("deal-recommends-title")).toHaveText("The response you picked · Option B");
  await expect(page.getByTestId("path-reply-back")).toHaveText("Back to Option A");
  await page.getByTestId("path-reply-back").click();
  await openReviewFor(page);
  expect((await page.getByTestId("commitment-receipt").textContent())!, "Option A's receipt is not Option B's").not.toBe(receiptB);
  await page.getByTestId("queue-review-close").click();
  await expect(page.getByTestId("deal-recommends-title")).toHaveText("FLOW's reply · Option A");
  // The deal's cash chart is on Cash impact.
  await page.getByTestId("deal-tab-cash").click();
  await expect(page.getByTestId("deal-chart")).toBeVisible();
});
async function openReviewFor(page: Page) {
  await page.getByTestId("queue-review-open").click();
  await page.getByTestId("queue-review").waitFor();
}

test("the address restores the whole state: customer, decision, path, timing, the tab and the lines, in a fresh read", async ({ page }, testInfo) => {
  await checkedDeal(page);
  await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(DECISION)}&path=${OPTION_B}&scenario=late&view=cash&lines=asked,${OPTION_B}`);
  await expect(page.getByTestId("deal-tab-cash")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("deal-chart")).toHaveAttribute("data-late", "true");
  await expect(page.getByTestId(`deal-chip-${OPTION_B}`)).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("deal-chip-CTR-193394b6ba8b")).toHaveAttribute("aria-pressed", "false");
  // (Cash impact folds the queue to its rail from the two-pane width: the selected row is marked there.)
  if (!testInfo.project.name.includes("phone")) await expect(page.getByTestId("queue-rail-row").first()).toHaveAttribute("data-selected", "true");
  await page.getByTestId("deal-tab-overview").click();
  await expect(page.getByTestId("deal-recommends-title")).toHaveText("The response you picked · Option B");
});
test("selecting pushes history, Escape and Close clear the selection, and back restores it", async ({ page }, testInfo) => {
  await checkedDeal(page);
  await page.getByTestId("deal-close").click();
  await expect(page).toHaveURL(/\/deals$/);
  await expect(page.getByTestId("deals-select")).toBeVisible();
  await page.getByTestId("queue-select").first().click();
  await expect(page).toHaveURL(/decision=/);
  await expect(page.getByTestId("deal-pane")).toBeVisible();
  await expect(page.getByTestId("deal-panel-overview")).toBeVisible();
  // On the Overview Escape clears the selection (the queue is already beside it); on Compare or Cash it first brings the queue back from its rail.
  await page.getByTestId("deal-tab-compare").click();
  if (!phoneProject(testInfo)) {
    await expect(page.getByTestId("queue-rail")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("deals-queue")).toBeVisible();
    await expect(page).toHaveURL(/view=compare/);
  }
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
  await expect(page.getByTestId("deal-recommends-title")).toContainText("FLOW 的回复");
  await expect(page.getByTestId("queue-review-open")).toHaveText("查看还价");
  await page.getByTestId("deal-tab-compare").click();
  await expandRow(page, "economic");
  await expect(page.locator('[data-testid="deal-cost-table-total-asked"]:visible')).toContainText("¥28,326.92");
  await scan(page, "/deals zh");
});

test("a phone: the rows stack, nothing scrolls sideways, the tabs scroll inside their own track, and the controls reach 44 px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await checkedDeal(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  for (const id of ["queue-review-open", "deal-to-compare"]) {
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
  await scan(page, "/deals open");
});

// The four tabs sharing one line inside the queue at 1280 and 1440, in English and Chinese, need a queue with two or more rows: they are pinned on the busy books in slice-b-round-three.spec.ts (live).

// ---------------------------------------------------------------------------------------------------------------------------------------------------
// The owner's cue that a row opens the workspace beside it (the chevron, the connector, the empty sentence, the slide, the first-visit pulse)

const phoneProject = (info: { project: { name: string } }) => info.project.name === "phone";

test("every queue row has a decorative chevron, quiet at rest, ink on hover and keyboard focus, filled on the selected row; the row's accessible name is its own words", async ({ page }, testInfo) => {
  await checkedDeal(page);
  const rows = page.getByTestId("queue-row");
  const n = await rows.count();
  expect(n).toBeGreaterThan(0);
  await expect(page.getByTestId("queue-list").getByTestId("row-chevron")).toHaveCount(n);
  for (let i = 0; i < n; i++) {
    const chevron = rows.nth(i).getByTestId("row-chevron");
    await expect(chevron).toHaveAttribute("aria-hidden", "true");
    await expect(chevron).toHaveText("");
    await expect(chevron).toHaveAttribute("data-selected", (await rows.nth(i).getAttribute("data-selected")) === "true" ? "true" : "false");
  }
  const ink = await page.getByTestId("deals-queue").locator("h2").first().evaluate((el) => getComputedStyle(el).color);
  const selected = page.locator('[data-testid="queue-row"][data-selected="true"]').first();
  const filled = selected.getByTestId("row-chevron");
  await expect(filled).toHaveAttribute("data-selected", "true");
  expect(await filled.evaluate((el) => getComputedStyle(el).backgroundColor), "the selected row's chevron is an ink disc").toBe(ink);
  // The accessible name is the row's words, never the chevron's.
  const name = await selected.getByTestId("queue-select").getAttribute("aria-label");
  expect(name).toContain("Foshan");
  expect(name).not.toMatch(/[›>]/);
  // A row that is not selected: quiet at rest, ink on hover and on keyboard focus (a pointer is not a phone's input).
  if (n > 0 && !phoneProject(testInfo)) {
    await page.getByTestId("deal-close").click();
    const row = rows.first();
    const chevron = row.getByTestId("row-chevron");
    await expect(chevron).toHaveAttribute("data-selected", "false");
    const quiet = await chevron.evaluate((el) => getComputedStyle(el).color);
    await row.hover();
    await expect.poll(() => chevron.evaluate((el) => getComputedStyle(el).color)).toBe(ink);
    expect(quiet).not.toBe(ink);
    await page.mouse.move(2, 2);
    await expect.poll(() => chevron.evaluate((el) => getComputedStyle(el).color)).toBe(quiet);
    await row.getByTestId("queue-select").focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    await expect(row.getByTestId("queue-select")).toBeFocused();
    await expect.poll(() => chevron.evaluate((el) => getComputedStyle(el).color)).toBe(ink);
  }
});

test("at 1440 the selected row opens into the workspace: a 1 px purple connector at the row's centre reaches the workspace; a phone has none", async ({ page }, testInfo) => {
  await checkedDeal(page);
  const row = page.locator('[data-testid="queue-row"][data-selected="true"]').first();
  if (phoneProject(testInfo)) {
    await expect(row.getByTestId("row-connector")).toBeHidden();
    return;
  }
  const connector = row.getByTestId("row-connector");
  await expect(connector).toBeVisible();
  const [c, r, pane] = await Promise.all([connector.boundingBox(), row.locator(".flow-row").boundingBox(), page.getByTestId("deals-detail").boundingBox()]);
  expect(c!.height).toBeCloseTo(1, 0);
  expect(Math.abs(c!.y + c!.height / 2 - (r!.y + r!.height / 2)), "aligned to the row's vertical centre").toBeLessThan(1);
  expect(Math.abs(c!.x - (r!.x + r!.width)), "starts at the row's right edge").toBeLessThan(1);
  expect(Math.abs(c!.x + c!.width - pane!.x), "ends at the workspace").toBeLessThan(1.5);
  expect(await connector.evaluate((el) => getComputedStyle(el).backgroundColor)).not.toBe("rgba(0, 0, 0, 0)");
  expect(await connector.evaluate((el) => [getComputedStyle(el).backgroundImage, getComputedStyle(el).boxShadow])).toEqual(["none", "none"]);
});

test("with nothing selected the workspace says to choose a request, with the same chevron, in English and Chinese", async ({ page }, testInfo) => {
  await checkedDeal(page);
  await page.getByTestId("deal-close").click();
  const body = page.getByTestId("deals-select-body");
  await expect(body).toBeVisible();
  await expect(body).toHaveText(phoneProject(testInfo) ? "Choose a request above to review it here" : "Choose a request on the left to review it here");
  await expect(body.locator("svg")).toHaveCount(1);
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.reload();
  await expect(page.getByTestId("deals-select-body")).toHaveText(phoneProject(testInfo) ? "在上方选择一项请求，即可在此查看" : "在左侧选择一项请求，即可在此查看");
});

test("a newly selected negotiation slides in from the queue's side over the base duration (a fade on a phone); under reduced motion there is none", async ({ page }, testInfo) => {
  await checkedDeal(page);
  await page.getByTestId("deal-close").click();
  const anim = async () => page.getByTestId("deal-pane").locator(".motion-slide").first().evaluate((el) => ({ name: getComputedStyle(el).animationName, duration: getComputedStyle(el).animationDuration }));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.getByTestId("queue-select").first().click();
  await expect(page.getByTestId("deal-pane")).toBeVisible();
  expect((await anim()).name, "reduced motion: no slide, no fade").toBe("none");
  await page.getByTestId("deal-close").click();
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.getByTestId("queue-select").first().click();
  await expect(page.getByTestId("deal-pane")).toBeVisible();
  const on = await anim();
  expect(on.name).toBe(phoneProject(testInfo) ? "deals-fade-in" : "deals-slide-in");
  expect(on.duration).toBe("0.22s");
});

test("the first visit's cue: with nothing selected the top row's chevron pulses twice, once, and not on the second load", async ({ page }, testInfo) => {
  test.skip(phoneProject(testInfo), "the cue is the desktop list's; a phone's rows are links with the chevron");
  await checkedDeal(page);
  await page.evaluate(() => localStorage.removeItem("tl-deals-hint"));
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/deals");
  const first = page.getByTestId("queue-row").first().getByTestId("row-chevron");
  await expect(first).toHaveAttribute("data-hint", "true");
  expect(await first.evaluate((el) => [getComputedStyle(el).animationName, getComputedStyle(el).animationIterationCount, getComputedStyle(el).animationDuration])).toEqual(["row-hint", "2", "0.6s"]);
  await expect(first).not.toHaveAttribute("data-hint", "true", { timeout: 4000 });
  expect(await page.evaluate(() => localStorage.getItem("tl-deals-hint"))).toBe("1");
  await page.reload();
  await expect(page.getByTestId("queue-row").first()).toBeVisible();
  await page.waitForTimeout(300);
  await expect(page.getByTestId("queue-row").first().getByTestId("row-chevron")).not.toHaveAttribute("data-hint", "true");
  // Under reduced motion there is no cue and the one-time flag is not spent: allowing motion later still shows it once.
  await page.evaluate(() => localStorage.removeItem("tl-deals-hint"));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload();
  await expect(page.getByTestId("queue-row").first()).toBeVisible();
  await page.waitForTimeout(300);
  await expect(page.getByTestId("queue-row").first().getByTestId("row-chevron")).not.toHaveAttribute("data-hint", "true");
  expect(await page.evaluate(() => localStorage.getItem("tl-deals-hint"))).toBeNull();
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.reload();
  await expect(page.getByTestId("queue-row").first().getByTestId("row-chevron")).toHaveAttribute("data-hint", "true");
});
