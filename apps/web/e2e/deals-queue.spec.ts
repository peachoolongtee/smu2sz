import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { checkedDeal, demoMode, filledBrand, openInbox, openReview } from "./helpers";

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

test("cold: the page is 'Deals' with the state sentence under it, the server's work first, and the list alone (no empty workspace) while nothing is selected", async ({ page }) => {
  await page.goto("/deals");
  await expect(page.locator("h1")).toHaveText("Deals");
  await expect(page.locator("h1")).toHaveCount(1);
  // The page's sentence is the server's `queue.headline_text`, which counts the funding plan that waits for the owner; the alert is the page's own row above the queue.
  await expect(page.getByText("A funding plan is ready.")).toBeVisible();
  await expect(page.getByTestId("queue-alert")).toContainText("FLOW action ready");
  // Round three (section 9): with fewer than two negotiations the queue is its rows and nothing else (no lifecycle tabs); the total is the queue's own, and the alert is the page's row, counted nowhere.
  await expect(page.getByTestId("queue-total")).toHaveText("0");
  await expect(page.getByTestId("queue-tabs")).toHaveCount(0);
  // The queue lists negotiations only (round two): there is no Customers tab, and an approval or a collection is not a row here.
  await expect(page.getByTestId("queue-tab-customers")).toHaveCount(0);
  // Nothing is open: the tab says so in the server's words, and "No records" is not said.
  await expect(page.getByTestId("queue-empty")).toContainText("Nothing is open.");
  await expect(page.getByTestId("deals-select")).toHaveCount(0);
  await expect(page.getByTestId("deal-pane")).toHaveCount(0);
  // "No records" is only for a queue that is empty everywhere: not here.
  await expect(page.getByText("No records")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  await expect(page.locator("body")).not.toContainText(/BUYER-1|OFF-/);
});

test("a message read becomes a negotiation: the address is the selection, the row is the negotiation's own, and the pane opens on it", async ({ page }) => {
  await checkedDeal(page);
  await expect(page).toHaveURL(new RegExp(`/deals\\?customer=BUYER-1&decision=${encodeURIComponent(DECISION).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`));
  // The deal is its own page: the list is kept, hidden, and comes back with "All deals (N)".
  await expect(page.getByTestId("deals-list-view")).toBeHidden();
  await expect(page.getByTestId("deal-back-all")).toContainText("All deals (1)");
  const row = page.getByTestId("queue-row").first();
  await expect(row).toContainText("Foshan");
  await expect(row).toContainText("60-day terms on future invoices");
  await expect(row.getByTestId("queue-status")).toHaveText("Counter ready");
  await expect(row).toHaveAttribute("data-selected", "true");
  await expect(row).toHaveAttribute("data-tier", "needs_you");
  await expect(page.getByTestId("queue-total")).toHaveText("1");
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
test("Overview: the buyer's ask is the deal's name, FLOW recommends first with its reason and three facts, then one table of the choices; who decides and the costs are cells of it", async ({ page }) => {
  await checkedDeal(page);
  await expect(page.getByTestId("queue-heading")).toHaveText("Foshan asks for early settlement of ¥420,000.00 at 1.20%, payment terms to 60 days and a 1.00% rebate.");
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.getByTestId("deal-recommends-title")).toHaveText("FLOW recommends");
  await expect(page.getByTestId("deal-rec-label")).toHaveText("Option A");
  await expect(page.getByTestId("queue-option")).toContainText("Terms stay at 45 days, no rebate.");
  await expect(page.getByTestId("deal-rec-reason")).toHaveText("Recommended because FLOW can send it within your mandate without your approval.");
  await expect(page.getByTestId("deal-fact-cash")).toContainText("Held, no buffer at the lowest point");
  await expect(page.getByTestId("deal-fact-cost")).toContainText("¥3,027.77");
  await expect(page.getByTestId("deal-fact-decides")).toContainText("FLOW can send");
  await expect(page.getByTestId("deal-rec-why")).toContainText("Breached by ¥135k for 15 days");
  // The buyer's own words are in the Messages section.
  await page.getByTestId("deal-tab-messages").click();
  await expect(page.getByTestId("deal-ask-quote-messages")).toContainText("We'll settle the ¥420k early at 1.2%");
  await page.getByTestId("deal-tab-overview").click();
  // One table, "Your choices": the request and each reply side by side; Option A is tinted and says so; every cell is the server's word.
  const table = page.getByTestId("deal-choices-table");
  await expect(table.locator("thead th").filter({ hasText: /\S/ })).toHaveText([/^Accept their request/, /^Option A\s*Recommended/, /^Option B/]);
  await expect(page.getByTestId("deal-choice-cell-terms-reply").first()).toContainText("45 days");
  await expect(page.getByTestId("deal-choice-cell-terms-asked")).toContainText("60 days");
  await expect(page.getByTestId("deal-choice-cell-cost-asked")).toContainText("¥28,326.92 over 12 months");
  await expect(page.getByTestId("deal-choice-cell-cost-reply").first()).toContainText("¥3,027.77");
  await expect(page.getByTestId("deal-choice-cell-cost-reply").first()).toContainText("One-off cost, nothing ongoing");
  await expect(page.getByTestId("deal-choice-cell-funding-reply").first()).toContainText("¥150k credit-line draw today");
  await expect(page.getByTestId("deal-choice-cell-decides-reply").nth(1)).toContainText("Needs your approval");
  // The compare tab, the breadcrumb, the Close button and the queue rail are gone.
  for (const gone of ["deal-tab-compare", "deal-crumbs", "deal-close", "queue-rail", "deal-compare-table"]) await expect(page.getByTestId(gone)).toHaveCount(0);
  // One filled primary: the recommendation's review button, named for the reply.
  expect(await filledBrand(page)).toBe(1);
  await expect(page.getByTestId("queue-review-open")).toHaveText("Review and send Option A");
  await expect(page.getByTestId("deal-decline-open")).toHaveText("Decline the request");
});
test("Cash impact: two charts, each answering one question; the removed controls are not there", async ({ page }) => {
  await checkedDeal(page);
  await page.getByTestId("deal-tab-cash").click();
  await expect(page).toHaveURL(/view=cash/);
  // Chart 1: one thin bar per choice to its lowest cash, the minimum a dashed line through each, the server's words on the right.
  const lowest = page.getByTestId("deal-lowest");
  await expect(lowest.locator("h2")).toHaveText("Does cash stay above your ¥300k minimum?");
  await expect(lowest.getByTestId("deal-lowest-row")).toHaveCount(3);
  await expect(lowest.getByTestId("deal-lowest-row").first()).toContainText("¥165k");
  await expect(lowest.getByTestId("deal-lowest-row").first()).toContainText("Breached by ¥135k for 15 days");
  await expect(lowest.getByTestId("deal-lowest-row").first()).toHaveAttribute("data-below", "true");
  await expect(lowest.getByTestId("deal-lowest-floor")).toHaveCount(3);
  expect((await lowest.getByTestId("deal-lowest-bar").first().evaluate((el) => (el.parentElement as HTMLElement).getBoundingClientRect().height))).toBeLessThanOrEqual(10.5);
  await expect(page.getByTestId("deal-lowest-ticks")).toContainText("¥200k");
  // Chart 2: exactly two lines, the request dashed and the chosen reply, a toggle between the replies, the days below the minimum.
  const chart = page.getByTestId("deal-chart");
  await expect(chart.locator("h2")).toHaveText("How your cash moves, day by day");
  await expect(chart.locator("polyline")).toHaveCount(2);
  await expect(page.getByTestId("deal-chart-below")).toHaveText("Below your minimum for 15 days");
  await expect(page.getByTestId("deal-reply-toggle").getByRole("button", { name: "Option A" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("deal-why-lines")).toContainText("Credit line draw ¥150k today");
  await expect(page.getByTestId("deal-lowest-asked")).toContainText("¥165k");
  await expect(page.getByTestId("deal-lowest-reply")).toContainText("¥300k");
  await page.getByTestId("deal-reply-toggle").getByRole("button", { name: "Option B" }).click();
  await expect(page.getByTestId("deal-chart").locator("polyline")).toHaveCount(2);
  await expect(page.getByTestId("deal-lowest-reply")).toContainText("Option B");
  // Removed: the headroom plot, the line chips and ?lines=, the inspector, the 66 / 120 switch and the timing switch.
  for (const gone of ["deal-headroom", "deal-chips", "deal-inspector-lowest-asked", "deal-assumption-row", "deal-outcomes"]) await expect(page.getByTestId(gone)).toHaveCount(0);
  await expect(page).not.toHaveURL(/lines=|scenario=/);
  // The day labels under chart 2 never touch: measured on the page at this width and at a phone's.
  const noTouch = async (label: string) => {
    // Polled as a whole: after a resize the row is measured again and the labels are redrawn for its new width.
    await expect
      .poll(async () => {
        const row = await page.getByTestId("deal-chart-days").boundingBox();
        const boxes = (await page.getByTestId("deal-chart-days").locator("span").evaluateAll((els) => els.map((el) => el.getBoundingClientRect()).map((r) => ({ left: r.left, right: r.right })))).sort((x, y) => x.left - y.left);
        if (!row || boxes.length < 2) return ["not drawn"];
        const bad: string[] = [];
        for (let i = 1; i < boxes.length; i++) if (boxes[i].left < boxes[i - 1].right) bad.push(`label ${i} touches label ${i - 1}`);
        if (boxes[0].left < row.x - 0.5 || boxes[boxes.length - 1].right > row.x + row.width + 0.5) bad.push("outside the row");
        return bad;
      }, `${label}: day labels`)
      .toEqual([]);
  };
  await noTouch(`${page.viewportSize()!.width} px`);
  await page.setViewportSize({ width: 390, height: 844 });
  await noTouch("390 px");
  await page.setViewportSize({ width: 1440, height: 900 });
  // Business consequences stays below, with the server's own scenario labels.
  await expect(page.getByTestId("deal-scenarios")).toContainText("Buyer pays 30 days late");
});
test("Your choices: a reply is picked and reviewed from its own column, and the review is of that reply", async ({ page }) => {
  await demoMode(page); // the simulated send is the Demo's only
  await checkedDeal(page);
  await expect(page.getByTestId("deal-panel-compare")).toHaveCount(0);
  // "Review Option B" opens B's review in one step (it is not a selection that waits for a second button).
  await page.locator(`[data-testid^="deal-use-${OPTION_B}"]:visible`).click();
  await page.getByTestId("queue-review").waitFor();
  await expect(page).toHaveURL(new RegExp(`path=${OPTION_B}`));
  await expect(page.getByTestId("deal-send")).toHaveText("Approve and send Option B to Foshan");
  // What happens if the buyer refuses is the server's sentence, above the send button.
  await expect(page.getByTestId("deal-if-refused")).toContainText("If Foshan refuses, FLOW will fund the gap on its own");
  // The review reads Option B's own receipt (the server priced every sendable reply), not Option A's and not words composed from the path.
  const receiptB = (await page.getByTestId("commitment-receipt").textContent())!;
  await expect(page.getByTestId("deal-unpriced")).toHaveCount(0);
  await page.getByTestId("queue-review-close").click();
  await page.getByTestId("queue-review-open").click();
  await page.getByTestId("queue-review").waitFor();
  await expect(page.getByTestId("deal-send")).toHaveText("Send Option A to Foshan");
  expect((await page.getByTestId("commitment-receipt").textContent())!, "Option A's receipt is not Option B's").not.toBe(receiptB);
  // Changing section clears the review: it never shows under another section.
  await page.getByTestId("deal-tab-cash").click();
  await expect(page.getByTestId("queue-review")).toHaveCount(0);
  await expect(page.getByTestId("deal-chart")).toBeVisible();
});
test("the address restores the whole state: customer, decision, path and the section, in a fresh read", async ({ page }) => {
  await checkedDeal(page);
  await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(DECISION)}&path=${OPTION_B}&view=cash`);
  await expect(page.getByTestId("deal-tab-cash")).toHaveAttribute("aria-current", "page");
  await expect(page.getByTestId("deal-chart")).toBeVisible();
  await page.getByTestId("deal-tab-overview").click();
  await expect(page.getByTestId("deal-use-CTR-193394b6ba8b")).toHaveCount(0);
  // A retired address (the Compare tab) lands on the Overview.
  await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(DECISION)}&view=compare`);
  await expect(page.getByTestId("deal-choices")).toBeVisible();
  await expect(page).not.toHaveURL(/view=compare/);
});
test("opening a deal pushes one history entry, its sections replace it, All deals and Escape clear the selection, and Back leaves the deal in one step", async ({ page }) => {
  await checkedDeal(page);
  await page.getByTestId("deal-tab-cash").click();
  await page.getByTestId("deal-tab-messages").click();
  // Two section changes did not add history: one Back is the list.
  await page.goBack();
  await expect(page).toHaveURL(/\/deals$/);
  await expect(page.getByTestId("deals-list-view")).toBeVisible();
  await page.goForward();
  await expect(page.getByTestId("deal-pane")).toBeVisible();
  await page.getByTestId("deal-back-all").click();
  await expect(page).toHaveURL(/\/deals$/);
  await expect(page.getByTestId("deals-select")).toHaveCount(0);
  await page.getByTestId("queue-select").first().click();
  await expect(page).toHaveURL(/decision=/);
  await expect(page.getByTestId("deal-pane")).toBeVisible();
  await expect(page.getByTestId("deal-panel-overview")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/deals$/);
  await page.goBack();
  await expect(page.getByTestId("deal-pane")).toBeVisible();
});
test("the customer link carries the row's own context and the origin; the aside to the customer's page and back lands on the same negotiation", async ({ page }) => {
  await checkedDeal(page);
  await expect(page.getByTestId("deal-selected-customer")).toHaveAttribute("href", `/customers/BUYER-1?decision=${encodeURIComponent(DECISION)}&from=deal`);
  await page.getByTestId("deal-selected-customer").click();
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

test("a send in flight holds the selection: the rows, All deals and the sections wait, and the send is not unmounted", async ({ page }) => {
  await demoMode(page); // the simulated send is the Demo's only
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-negotiate-slow", "1500"));
  await checkedDeal(page);
  await openReview(page);
  await page.getByTestId("deal-send").click();
  await expect(page.getByTestId("deal-send")).toBeDisabled();
  await expect(page.getByTestId("deal-back-all")).toBeDisabled();
  await expect(page.getByTestId("queue-select").first()).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("deal-pane")).toBeVisible();
  await expect(page.getByTestId("deal-sent")).toContainText("The buyer accepted Option A.");
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
});

test("when the books moved the API refuses, nothing is sent, and Check again is an explicit step", async ({ page }) => {
  await demoMode(page); // the simulated send is the Demo's only
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
  await expect(page.locator("h1")).toContainText("Foshan");
  await expect(page.getByTestId("deal-recommends-title")).toHaveText("FLOW 的建议");
  await expect(page.getByTestId("queue-review-open")).toContainText("查看并发送");
  await expect(page.getByTestId("deal-choice-cell-cost-asked")).toContainText("¥28,326.92");
  await page.getByTestId("deal-tab-cash").click();
  await expect(page.getByTestId("deal-lowest")).toContainText("最低额");
  await scan(page, "/deals zh");
});

test("a phone: the choices are stacked cards, nothing scrolls sideways, the section links are rows, and the controls reach 44 px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await checkedDeal(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  for (const id of ["queue-review-open", "deal-decline-open"]) {
    const box = (await page.getByTestId(id).boundingBox())!;
    expect(box.height, id).toBeGreaterThanOrEqual(44);
    expect(box.x >= 0 && box.x + box.width <= 390, `${id} fits`).toBe(true);
  }
  await expect(page.getByTestId("queue-review-open")).toBeVisible();
  await expect(page.getByTestId("deal-choices-stack")).toBeVisible();
  await expect(page.getByTestId("deal-choices-table")).toBeHidden();
  await page.getByTestId("deal-tab-cash").click();
  await expect(page.getByTestId("deal-chart")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  await scan(page, "/deals phone");
});

test("axe finds nothing serious or critical on the queue with the review and the cash charts open", async ({ page }) => {
  await checkedDeal(page);
  await openReview(page);
  await scan(page, "/deals review");
  await page.getByTestId("deal-tab-cash").click();
  await expect(page.getByTestId("deal-chart")).toBeVisible();
  await scan(page, "/deals cash");
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
    await page.getByTestId("deal-back-all").click();
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

test("no purple connector, no rail and no empty workspace: the deal is its own page and the list comes back with All deals", async ({ page }) => {
  await checkedDeal(page);
  await expect(page.getByTestId("row-connector")).toHaveCount(0);
  await expect(page.getByTestId("queue-rail")).toHaveCount(0);
  // The page is the full width of the content: it does not sit beside a list.
  const pane = (await page.getByTestId("deal-page").boundingBox())!;
  expect(pane.width).toBeGreaterThan(page.viewportSize()!.width * 0.6);
  await page.getByTestId("deal-back-all").click();
  await expect(page.getByTestId("deals-list-view")).toBeVisible();
  await expect(page.getByTestId("row-connector")).toHaveCount(0);
  await expect(page.getByTestId("deals-select")).toHaveCount(0);
  await expect(page.getByTestId("deal-pane")).toHaveCount(0);
});

test("a newly selected negotiation slides in from the queue's side over the base duration (a fade on a phone); under reduced motion there is none", async ({ page }, testInfo) => {
  await checkedDeal(page);
  await page.getByTestId("deal-back-all").click();
  const anim = async () => page.getByTestId("deal-pane").locator(".motion-slide").first().evaluate((el) => ({ name: getComputedStyle(el).animationName, duration: getComputedStyle(el).animationDuration }));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.getByTestId("queue-select").first().click();
  await expect(page.getByTestId("deal-pane")).toBeVisible();
  expect((await anim()).name, "reduced motion: no slide, no fade").toBe("none");
  await page.getByTestId("deal-back-all").click();
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
