import { DEMO_TOKEN, expect, test } from "./fixtures";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { checkedDeal, filledBrand, walkStory } from "./helpers";
import type { TrackerView } from "../lib/tracker";

/**
 * Slice B round three (docs/design/flow-mockup-2026-10-13/05_slice_b_round_three.md): the selected deal as one comparison. The tabs and their address, the sticky deal header with the
 * review button on every tab, one scroll, the queue's rail, then (as the slices land) the Overview, Compare responses, Cash impact, Messages and the whole life of a deal. The mock
 * project runs on the API's recordings; the live project on a real API (golden and busy books). Every word is the server's, read from the page.
 */

const live = (info: { project: { name: string } }) => info.project.name === "live";

async function busy(request: import("@playwright/test").APIRequestContext) {
  const port = process.env.E2E_API_PORT ?? 8000;
  const res = await request.post(`http://localhost:${port}/demo/reset?scenario=busy`, { headers: { "X-Owner-Token": DEMO_TOKEN } });
  expect(res.ok()).toBeTruthy();
}

/** The address of the selected deal with a view: the current path and query with `view` set (or removed for the Overview). */
function withView(url: string, view: string | null): string {
  const u = new URL(url);
  if (view) u.searchParams.set("view", view);
  else u.searchParams.delete("view");
  return `${u.pathname}${u.search}`;
}

test.describe("tabs, address, header, one scroll and the rail (slice a)", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  test("a checked deal has four tabs in one line; each tab is an address, back restores it, and the chosen tab replaces the workspace", async ({ page }) => {
    await checkedDeal(page);
    const tabs = page.getByTestId("deal-tabs");
    await expect(tabs.getByRole("tab")).toHaveText(["Overview", "Compare responses", "Cash impact", "Messages"]);
    await expect(page.getByTestId("deal-tab-overview")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("deal-panel-overview")).toBeVisible();
    for (const [key, panel] of [["compare", "deal-panel-compare"], ["cash", "deal-panel-cash"], ["messages", "deal-panel-messages"]] as const) {
      await page.getByTestId(`deal-tab-${key}`).click();
      await expect(page).toHaveURL(new RegExp(`view=${key}`));
      await expect(page.getByTestId(panel)).toBeVisible();
      await expect(page.getByTestId("deal-tab-overview").and(page.getByRole("tab"))).toHaveAttribute("aria-selected", "false");
      // Nothing is appended under the page: only the chosen tab's panel is there.
      await expect(page.locator('[data-testid^="deal-panel-"]')).toHaveCount(1);
    }
    await page.goBack();
    await expect(page.getByTestId("deal-panel-cash")).toBeVisible();
    // A deep link in a fresh load reads the same tab.
    await page.goto(withView(page.url(), "compare"));
    await expect(page.getByTestId("deal-tab-compare")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("deal-panel-compare")).toBeVisible();
  });

  test("the old addresses (investigate, compare, chart, show) land on view=compare and are rewritten", async ({ page }) => {
    await checkedDeal(page);
    for (const old of ["investigate=1", "compare=1", "chart=1", "show=cost"]) {
      await page.goto(`${withView(page.url(), null)}${new URL(page.url()).search ? "&" : "?"}${old}`);
      await expect(page).toHaveURL(/view=compare/);
      await expect(page).not.toHaveURL(/investigate=|compare=1|chart=|show=/);
      await expect(page.getByTestId("deal-panel-compare")).toBeVisible();
    }
  });

  test("[Review the counter] sits in the sticky header on every tab and opens the review in place", async ({ page }) => {
    await checkedDeal(page);
    const header = page.getByTestId("deal-header");
    for (const view of ["overview", "compare", "cash", "messages"]) {
      await page.getByTestId(`deal-tab-${view}`).click();
      await expect(header.getByTestId("queue-review-open")).toHaveText("Review the counter");
      // At most one filled button on the page.
      expect(await filledBrand(page)).toBe(1);
    }
    await header.getByTestId("queue-review-open").click();
    await expect(page.getByTestId("queue-review")).toBeVisible();
    // The review is open: the header's button gives way to the one commit button.
    await expect(page.getByTestId("queue-review-open")).toHaveCount(0);
    await expect(page.getByTestId("deal-send")).toBeVisible();
    // It stays open across the tabs.
    await page.getByTestId("deal-tab-messages").click();
    await expect(page.getByTestId("queue-review")).toBeVisible();
  });

  test("one scroll: the workspace has no scroll of its own and the deal header stays under the app's header", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-compare").click();
    await expect(page.getByTestId("deal-panel-compare")).toBeVisible();
    const nested = await page.getByTestId("deal-pane").evaluate((pane) => {
      const hits: string[] = [];
      for (const el of Array.from(pane.querySelectorAll("*")).concat([pane])) {
        const s = getComputedStyle(el);
        if ((s.overflowY === "auto" || s.overflowY === "scroll") && el.scrollHeight > el.clientHeight + 1) hits.push(`${el.tagName}.${el.getAttribute("data-testid") ?? ""}`);
      }
      return hits;
    });
    expect(nested, "no element of the workspace scrolls on its own").toEqual([]);
    await page.evaluate(() => window.scrollTo(0, 600));
    const box = await page.getByTestId("deal-header").boundingBox();
    expect(box?.y ?? 999).toBeGreaterThanOrEqual(60);
    expect(box?.y ?? 999).toBeLessThanOrEqual(72);
  });

  test("Compare responses and Cash impact fold the queue to a 72 px rail; Show queue and Escape bring it back; Overview and Messages keep the queue", async ({ page }) => {
    await checkedDeal(page);
    await expect(page.getByTestId("deals-queue")).toBeVisible();
    await expect(page.getByTestId("queue-rail")).toHaveCount(0);
    await page.getByTestId("deal-tab-compare").click();
    const rail = page.getByTestId("queue-rail");
    await expect(rail).toBeVisible();
    expect((await rail.boundingBox())?.width).toBeLessThanOrEqual(76);
    await expect(page.getByTestId("deals-queue")).toHaveCount(0);
    await expect(rail.getByTestId("queue-rail-row").first()).toHaveAttribute("data-selected", "true");
    await expect(rail.getByTestId("queue-rail-select").first()).toHaveAttribute("aria-label", /Foshan/);
    // The workspace takes the content width.
    const wide = (await page.getByTestId("deals-detail").boundingBox())?.width ?? 0;
    expect(wide).toBeGreaterThan(900);
    await rail.getByTestId("queue-rail-show").click();
    await expect(page.getByTestId("deals-queue")).toBeVisible();
    await expect(page.getByTestId("queue-rail")).toHaveCount(0);
    expect((await page.getByTestId("deals-detail").boundingBox())?.width ?? 0).toBeLessThanOrEqual(852);
    // Escape also returns the queue; leaving the wide tab and coming back folds it again.
    await page.getByTestId("deal-tab-cash").click();
    await expect(page.getByTestId("queue-rail")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("deals-queue")).toBeVisible();
    await expect(page).toHaveURL(/view=cash/);
    await page.getByTestId("deal-tab-messages").click();
    await expect(page.getByTestId("deals-queue")).toBeVisible();
    await expect(page.getByTestId("queue-rail")).toHaveCount(0);
  });

  test("Compare and Cash start with the breadcrumb: the customer, the deal and the tab; the deal crumb goes back to the Overview", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-compare").click();
    const crumbs = page.getByTestId("deal-crumbs");
    await expect(crumbs).toContainText("Foshan");
    await expect(crumbs).toContainText("Compare responses");
    await expect(crumbs.getByTestId("deal-crumb-customer")).toHaveAttribute("href", /customers\/BUYER-1/);
    await crumbs.getByTestId("deal-crumb-deal").click();
    await expect(page.getByTestId("deal-panel-overview")).toBeVisible();
    await expect(page).not.toHaveURL(/view=/);
  });
});

test.describe("the Overview and the terms by scope (slice b)", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  test("the Overview is the ask, FLOW's reply, the recommendation's two sentences, the compact terms and nothing else: no cost card, no cash card, no chart, no Authority row", async ({ page }) => {
    await checkedDeal(page);
    const overview = page.getByTestId("deal-panel-overview");
    await expect(overview.getByTestId("queue-ask")).toContainText("early settlement of ¥420,000.00 at 1.20%, payment terms to 60 days and a 1.00% rebate");
    await expect(overview.getByTestId("queue-option")).toContainText("Terms stay at 45 days, no rebate");
    await expect(overview.getByTestId("deal-mandate")).toHaveText("Option A is the reply FLOW can send within your mandate.");
    await expect(overview.getByTestId("deal-alternative")).toContainText("Option B needs your approval for 55-day terms. Its net economic cost over 12 months is stated as about ¥0 under the model's assumptions.");
    for (const gone of ["deal-card-cost", "deal-card-cash", "deal-chart", "deal-compare-table", "deal-cost-table", "deal-timing", "deal-consequence"]) await expect(overview.getByTestId(gone)).toHaveCount(0);
    await expect(overview.getByTestId("deal-scope-terms-table").getByRole("row", { name: /^Authority/ })).toHaveCount(0);
    // The recommendation never says "best", and "Safe" is not a word of this page.
    const text = (await overview.innerText()).replace(/\s+/g, " ");
    expect(text).not.toMatch(/best/i);
    expect(text).not.toMatch(/Safe/);
    // Two ways on: the header's review and the Compare responses button (outlined).
    await expect(overview.getByTestId("deal-to-compare")).toHaveText("Compare responses");
    await overview.getByTestId("deal-to-compare").click();
    await expect(page).toHaveURL(/view=compare/);
  });

  test("terms by scope: three rows, a column for the ask, Option A and Option B, each cell the server's word; changed cells tinted and never underlined; the period bars inside Future invoices; at most 180 px high", async ({ page }) => {
    await checkedDeal(page);
    const terms = page.getByTestId("deal-scope-terms");
    await expect(terms.getByRole("columnheader")).toHaveText(["Buyer asks", "FLOW counters · Option A", "Option B"]);
    await expect(terms.locator("tbody tr")).toHaveCount(3);
    await expect(terms.locator("tbody tr").nth(0)).toContainText("Existing invoice");
    await expect(terms.locator("tbody tr").nth(1)).toContainText("Future invoices");
    await expect(terms.locator("tbody tr").nth(2)).toContainText("Next quarter");
    const cell = (scope: string, col: string) => terms.getByTestId(`deal-scope-terms-cell-${scope}-${col}`);
    await expect(cell("existing", "asked")).toContainText("1.20% off ¥420,000.00");
    // Option A leaves the rebate out, said as the server's "Not offered" with what it stands instead of.
    await expect(terms.locator('[data-scope="quarter"] td').nth(1)).toContainText("Not offered");
    await expect(terms.locator('[data-scope="quarter"] td').nth(1)).toContainText("instead of a 1.00% rebate");
    await expect(terms.locator('[data-scope="quarter"] td').nth(1)).toHaveAttribute("data-changed", "true");
    // Tinted, not underlined: nothing inside the terms block carries an underline.
    const underlined = await terms.evaluate((el) => Array.from(el.querySelectorAll("*")).filter((n) => getComputedStyle(n).textDecorationLine.includes("underline")).length);
    expect(underlined).toBe(0);
    const tint = await terms.locator('[data-scope="quarter"] td').nth(1).evaluate((n) => getComputedStyle(n).backgroundColor);
    expect(tint).not.toBe("rgba(0, 0, 0, 0)");
    // The payment-period bars, one in each Future invoices cell and the current terms in the row head; the timing diagram section is gone.
    await expect(terms.getByTestId("deal-scope-terms-bar-current")).toHaveAttribute("data-days", "45");
    await expect(terms.getByTestId("deal-scope-terms-bar-asked")).toHaveAttribute("data-days", "60");
    await expect(terms.getByTestId("deal-scope-terms-delta-asked")).toHaveText("+15 days requested by buyer");
    await expect(page.getByTestId("deal-timing")).toHaveCount(0);
    expect((await terms.boundingBox())?.height ?? 999).toBeLessThanOrEqual(180);
  });
});

test.describe("Compare responses (slice c)", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  test("the commercial packages only: three columns with the short authority words, five rows, each cell the server's word; no scenarios here", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-compare").click();
    const table = page.getByTestId("deal-compare-table");
    await expect(table.getByRole("columnheader").filter({ hasText: /\S/ })).toHaveCount(3);
    await expect(page.getByTestId("deal-compare-head-asked")).toContainText("Buyer request");
    await expect(page.getByTestId("deal-compare-head-asked").getByTestId("deal-compare-badge")).toHaveText("Outside mandate");
    await expect(page.getByTestId("deal-compare-head-reply").first()).toContainText("Option A");
    await expect(page.getByTestId("deal-compare-head-reply").first().getByTestId("deal-compare-badge")).toHaveText("FLOW can send");
    await expect(page.getByTestId("deal-compare-head-reply").nth(1).getByTestId("deal-compare-badge")).toHaveText("Needs your approval");
    const rowKeys = ["terms", "economic", "cash", "authority", "status"];
    const rowLabels = ["Commercial terms", "Economic impact", "Cash outcome", "Authorization", "Buyer status"];
    await expect(table.locator('tbody tr[data-testid^="deal-compare-row-"]')).toHaveCount(5);
    for (const [i, k] of rowKeys.entries()) await expect(table.getByTestId(`deal-compare-row-${k}`).locator("th")).toContainText(rowLabels[i]);
    await expect(page.getByTestId("deal-compare-cell-terms-reply").first()).toContainText("Not offered");
    await expect(page.getByTestId("deal-compare-cell-economic-asked")).toContainText("¥5,040.00 once, ¥28,326.92 over 12 months");
    await expect(page.getByTestId("deal-compare-cell-economic-asked")).toContainText("Two parts, not added together");
    await expect(page.getByTestId("deal-compare-cell-economic-reply").nth(1)).toContainText("About ¥0");
    await expect(page.getByTestId("deal-compare-cell-cash-asked")).toContainText("Breached by ¥135k for 15 days");
    await expect(page.getByTestId("deal-compare-cell-status-asked")).toHaveText("Asked by Foshan");
    await expect(page.getByTestId("deal-compare-cell-status-reply").first()).toHaveText("Not yet sent");
    // Doing nothing and the buyer stopping are Business consequences on Cash impact, not columns here.
    await expect(page.getByTestId("deal-panel-compare")).not.toContainText(/Do nothing|stops buying/i);
    await expect(page.getByTestId("deal-panel-compare")).not.toContainText(/\bSafe\b/);
    // The buyer's request cannot be accepted here: no [Review the request].
    await expect(page.getByTestId("deal-review-request")).toHaveCount(0);
  });

  test("a row expands in place to its calculation: the terms by scope, the cost rows, the funding each response rests on", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-compare").click();
    await page.getByTestId("deal-compare-expand-economic").click();
    await expect(page.getByTestId("deal-compare-expand-economic")).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByTestId("deal-compare-calc-economic").getByTestId("deal-cost-table")).toBeVisible();
    await expect(page.getByTestId("deal-compare-calc-economic").getByTestId("deal-cost-table-total-asked")).toBeVisible();
    await page.getByTestId("deal-compare-expand-cash").click();
    await expect(page.getByTestId("deal-compare-calc-cash").getByTestId("deal-funding-plans")).toContainText("Funding plan required: ¥150k credit-line draw today");
    await page.getByTestId("deal-compare-expand-terms").click();
    await expect(page.getByTestId("deal-compare-calc-terms").getByTestId("deal-compare-scope-terms")).toBeVisible();
    await page.getByTestId("deal-compare-expand-economic").click();
    await expect(page.getByTestId("deal-compare-calc-economic")).toHaveCount(0);
  });

  test("[Choose A] / [Review B] only select: the address names the response, the review below is of it, and nothing is sent", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-compare").click();
    // (the table and its stacked twin are both in the page; one of them is shown)
    const a = page.locator('[data-testid="deal-use-CTR-193394b6ba8b"]:visible');
    const b = page.locator('[data-testid="deal-use-CTR-6b07cbf70441"]:visible');
    await expect(a).toHaveText("Option A is selected");
    await expect(b).toHaveText("Review Option B");
    await b.click();
    await expect(page).toHaveURL(/path=CTR-6b07cbf70441/);
    await expect(b).toHaveText("Option B is selected");
    await expect(b).toHaveAttribute("aria-pressed", "true");
    await page.getByTestId("deal-review-selected").click();
    await expect(page.getByTestId("queue-review")).toBeVisible();
    await expect(page.getByTestId("deal-send")).toContainText("Option B");
    await expect(page.getByTestId("deal-sent")).toHaveCount(0);
    await expect(page.getByTestId("send-statements")).toBeVisible();
    await page.getByTestId("queue-review-close").click();
    await page.getByTestId("deal-back").click();
    await expect(page.getByTestId("deal-panel-overview")).toBeVisible();
  });

  test("financial outcomes: the outcome table and the headroom dot plot are the server's words; below the reserve is red, the reserve a labelled dashed line; and Why these results differ states the rule once", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-compare").click();
    const out = page.getByTestId("deal-outcomes");
    await expect(out.getByTestId("deal-outcome-row-lowest")).toContainText("¥165k");
    await expect(out.getByTestId("deal-outcome-row-when")).toContainText("in 60 days");
    await expect(out.getByTestId("deal-outcome-row-reserve")).toContainText("Breached by ¥135k for 15 days");
    await expect(out.getByTestId("deal-outcome-row-reserve")).toContainText("Held, no buffer at the lowest point");
    await expect(out.getByTestId("deal-outcome-row-financing")).toContainText("None in this scenario");
    await expect(out.getByTestId("deal-outcome-row-financing")).toContainText("¥150k credit-line draw today");
    await expect(out.getByTestId("deal-outcome-row-send")).toContainText("Needs your approval");
    const rows = out.getByTestId("deal-headroom-row");
    await expect(rows).toHaveCount(3);
    await expect(rows.first()).toHaveAttribute("data-below", "true");
    await expect(rows.nth(1)).toHaveAttribute("data-below", "false");
    await expect(out.getByTestId("deal-headroom-reserve-label")).toContainText("Minimum cash reserve");
    const red = await rows.first().locator("span.rounded-pill").first().evaluate((el) => getComputedStyle(el).backgroundColor);
    const ink = await rows.nth(1).locator("span.rounded-pill").first().evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(red).not.toBe(ink);
    // The dots stand left to right in the order of their cash: the request's lowest is the smallest.
    const xs = await rows.evaluateAll((els) => els.map((e) => e.querySelector('[data-testid="deal-headroom-dot"]')!.getBoundingClientRect().x));
    expect(xs[0]).toBeLessThan(xs[1]);
    await expect(page.getByTestId("deal-why")).toContainText("Why these results differ");
    await expect(page.getByTestId("deal-why-rule")).toHaveText("FLOW recommends the first reply it may send within your mandate; it does not rank replies by cost.");
    await expect(page.getByTestId("deal-why-authority")).toContainText("Option A.");
  });
});

test.describe("Cash impact (slice d)", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  const ASKED = "asked";
  const A = "CTR-193394b6ba8b";
  const B = "CTR-6b07cbf70441";

  test("the chips choose the lines: two on by default, a third may be added, one always stays; the choice is in the address", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-cash").click();
    const chip = (k: string) => page.getByTestId(`deal-chip-${k}`);
    await expect(chip(ASKED)).toHaveAttribute("aria-pressed", "true");
    await expect(chip(A)).toHaveAttribute("aria-pressed", "true");
    await expect(chip(B)).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByTestId("deal-chart").locator('[data-testid^="home-line-"]')).toHaveCount(2);
    await expect(page.getByTestId("deal-chart-funding")).toContainText("Each option with its own funding plan");
    await chip(B).click();
    await expect(page).toHaveURL(new RegExp(`lines=${ASKED}%2C${A}%2C${B}|lines=${ASKED},${A},${B}`));
    await expect(page.getByTestId("deal-chart").locator('[data-testid^="home-line-"]')).toHaveCount(3);
    await chip(ASKED).click();
    await chip(A).click();
    // The last line stays: its chip is held on.
    await expect(chip(B)).toHaveAttribute("aria-pressed", "true");
    await expect(chip(B)).toHaveAttribute("aria-disabled", "true");
    await expect(page.getByTestId("deal-chart").locator('[data-testid^="home-line-"]')).toHaveCount(1);
    // A deep link keeps the choice and its order.
    await page.goto(`${withView(page.url(), "cash")}`);
    await expect(chip(B)).toHaveAttribute("aria-pressed", "true");
    await expect(chip(A)).toHaveAttribute("aria-pressed", "false");
  });

  test("colours mean one thing each: the first line ink, the second purple, the third muted and dashed; the reserve amber and dashed; below it red", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-cash").click();
    await page.getByTestId(`deal-chip-${B}`).click();
    const stroke = (id: string) => page.getByTestId(id).evaluate((el) => ({ stroke: getComputedStyle(el).stroke, dash: getComputedStyle(el).strokeDasharray }));
    const first = await stroke("home-line-first");
    const second = await stroke("home-line-second");
    const third = await stroke("home-line-third");
    const reserve = await stroke("home-reserve");
    const red = await stroke("hv2-below-first");
    expect(new Set([first.stroke, second.stroke, third.stroke, reserve.stroke, red.stroke]).size, "five different colours").toBe(5);
    expect(first.dash).toBe("none");
    expect(second.dash).toBe("none");
    expect(third.dash).not.toBe("none");
    expect(reserve.dash).not.toBe("none");
    // Red marks the stretch under the reserve only; no response is named by it.
    await expect(page.getByTestId("hv2-below-second")).toHaveCount(1);
    await expect(page.getByTestId("home-legend")).toContainText("Below minimum reserve");
  });

  test("event markers sit on the first line only and say the server's words for that day; the inspector follows", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-cash").click();
    const markers = page.getByTestId("deal-marker");
    await expect(markers.first()).toBeVisible();
    expect(await markers.count()).toBeGreaterThan(2);
    const marker = markers.first();
    const day = await marker.getAttribute("data-day");
    await marker.hover();
    await expect(page.getByTestId("deal-marker-tip")).toBeVisible();
    await expect(page.getByTestId("deal-marker-tip")).toHaveText(((await marker.getAttribute("aria-label")) ?? "").trim());
    await marker.click();
    await expect(page.getByTestId("hv2-inspector")).toHaveAttribute("data-day", String(day));
    // Switching the first line off moves the markers to the new first line.
    const before = await markers.count();
    await page.getByTestId("deal-chip-asked").click();
    await expect(page.getByTestId("deal-marker").first()).toBeVisible();
    expect(await page.getByTestId("deal-marker").count()).toBeGreaterThan(0);
    expect(before).toBeGreaterThan(0);
  });

  test("the inspector shows two comparisons apart: the pair on this day with the server's difference, and each option's lowest point, never subtracted", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-cash").click();
    const inspector = page.getByTestId("hv2-inspector");
    const day = inspector.getByTestId("deal-inspector-day");
    const lowest = inspector.getByTestId("deal-inspector-lowest");
    await expect(day.getByRole("heading", { name: "On this day" })).toBeVisible();
    await expect(lowest.getByRole("heading", { name: "Each option's lowest point" })).toBeVisible();
    await expect(day).toContainText("not negotiation alone");
    await expect(lowest.getByTestId(`deal-inspector-lowest-${ASKED}`)).toContainText("¥165k");
    await expect(lowest.getByTestId(`deal-inspector-lowest-${ASKED}`)).toContainText("in 60 days");
    await expect(lowest.getByTestId(`deal-inspector-lowest-${A}`)).toContainText("¥300k");
    await expect(lowest.getByTestId(`deal-inspector-lowest-${A}`)).toContainText("in 30 days");
    // The lowest points are never subtracted: no difference in that block.
    await expect(lowest.locator('[data-testid$="-diff"]')).toHaveCount(0);
    await expect(lowest).toContainText("never subtracted");
    // Today, the pair's words are the server's own strip for that day.
    await page.getByTestId("home-chart").focus();
    await page.keyboard.press("Home");
    await expect(inspector).toHaveAttribute("data-day", "0");
    await expect(day.getByTestId("deal-inspector-day-diff")).toContainText("+¥149,986.20");
    await expect(day.getByTestId(`deal-inspector-day-${ASKED}`)).toContainText("¥400,000.00");
    await expect(day.getByTestId(`deal-inspector-day-${A}`)).toContainText("¥549,986.20");
  });

  test("the payment-timing switch swaps every drawn line to its stressed series; markers go with it", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-cash").click();
    await expect(page.getByTestId("deal-chart")).toHaveAttribute("data-late", "false");
    await page.getByTestId("deal-scenario-late").click();
    await expect(page).toHaveURL(/scenario=late/);
    await expect(page.getByTestId("deal-chart")).toHaveAttribute("data-late", "true");
    await expect(page.getByTestId("deal-marker")).toHaveCount(0);
    await expect(page.getByTestId("deal-panel-cash")).not.toContainText(/\bSafe\b|\bbest\b/i);
  });
});

test.describe("Business consequences (slice d)", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  test("three scenario controls, one read-only card at a time: the assumption sentence first, then its rows; the late payment shows the lowest cash of each response; the customer loss separates its sentences; no id, no None, no best", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-cash").click();
    const section = page.getByTestId("deal-scenarios");
    await expect(section.getByRole("heading", { name: "Business consequences" })).toBeVisible();
    await expect(section.getByRole("tab")).toHaveText(["Continue current position", "Buyer pays 30 days late", "Buyer stops placing new orders"]);
    const card = section.getByTestId("deal-scenario-card");
    await expect(card).toHaveAttribute("data-scenario", "no_new_agreement");
    await expect(card.getByTestId("deal-scenario-assumption")).toHaveText("Your books as they stand: Foshan keeps buying on today's terms.");
    await expect(card.getByTestId("deal-scenario-lowest")).toContainText("−¥105k");
    await section.getByTestId("deal-scenario-tab-late_30").click();
    await expect(card).toHaveAttribute("data-scenario", "late_30");
    await expect(card.getByTestId("deal-scenario-assumption")).toContainText("paid every invoice 30 days late (a test, not a forecast)");
    await expect(card.getByTestId("deal-scenario-lowest")).toHaveCount(3);
    await expect(card.getByTestId("deal-scenario-asked")).toContainText("As they asked");
    await expect(card.getByTestId("deal-scenario-asked")).toContainText("−¥250k");
    await expect(card.getByTestId("deal-scenario-asked")).toContainText("in 60 days");
    await section.getByTestId("deal-scenario-tab-customer_loss").click();
    await expect(card.getByTestId("deal-scenario-assumption")).toContainText("This is not a prediction.");
    await expect(card.getByTestId("deal-scenario-lost_billings")).toContainText("About ¥5,460,000 a year of billings");
    await expect(card.getByTestId("deal-scenario-cash_effect")).toContainText("¥1,260,000 of receipts removed within the next 120 days; ¥420,000 still arrives.");
    await expect(card.getByTestId("deal-scenario-invoice_remains")).toHaveText(/The ¥420,000 already invoiced \(due in 32 days\) is still paid\./);
    const text = (await section.innerText()).replace(/\s+/g, " ");
    expect(text).not.toMatch(/\bNone\b|\bbest\b|\bSafe\b|CTR-|OFF-|BUYER-/);
  });

  test("zh: the scenario labels and sentences are the server's Chinese", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
    await checkedDeal(page);
    await page.getByTestId("deal-tab-cash").click();
    const section = page.getByTestId("deal-scenarios");
    await expect(section.getByRole("tab")).toHaveCount(3);
    await expect(section.getByRole("heading", { name: "业务后果" })).toBeVisible();
    await expect(section.getByTestId("deal-scenario-assumption")).toContainText(/[一-鿿]/);
  });
});

test.describe("Messages and the queue (slice e)", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  test("one negotiation is its row and nothing else: no tabs, no search, no sort, no group, no table switch", async ({ page }) => {
    await checkedDeal(page);
    await expect(page.getByTestId("queue-row")).toHaveCount(1);
    for (const gone of ["queue-tabs", "queue-search", "queue-controls", "queue-sort-urgency", "queue-group", "queue-layout-table"]) await expect(page.getByTestId(gone)).toHaveCount(0);
    await expect(page.getByTestId("queue-total")).toHaveText("1");
  });

  test("the company funding alert is the page's own full-width row, outside the queue and in none of its counts", async ({ page }) => {
    await checkedDeal(page);
    const alert = page.getByTestId("queue-alert");
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("FLOW action ready");
    await expect(page.getByTestId("deals-queue").getByTestId("queue-alert")).toHaveCount(0);
    await expect(page.getByTestId("deals-alert-row")).toBeVisible();
    const row = await page.getByTestId("deals-alert-row").boundingBox();
    const queue = await page.getByTestId("deals-queue").boundingBox();
    expect(row!.y + row!.height, "the alert row is above the queue").toBeLessThanOrEqual(queue!.y + 1);
    expect(row!.width).toBeGreaterThan(queue!.width * 2);
    await expect(page.getByTestId("queue-alert-go")).toHaveAttribute("href", /\//);
    await expect(page.getByTestId("queue-total")).toHaveText("1");
  });

  test("the selected row is lighter: no ring, the panel's tint, and a 1 px edge that joins it to the workspace", async ({ page }) => {
    await checkedDeal(page);
    const row = page.getByTestId("queue-row").first().locator(".flow-row");
    await expect(row).toHaveAttribute("aria-current", "true");
    const style = await row.evaluate((el) => ({ shadow: getComputedStyle(el).boxShadow, bg: getComputedStyle(el).backgroundColor }));
    expect(style.shadow).toBe("none");
    const chip = await page.evaluate(() => {
      const probe = document.createElement("div");
      probe.style.background = "var(--color-f-purple-soft)";
      document.body.appendChild(probe);
      const c = getComputedStyle(probe).backgroundColor;
      probe.remove();
      return c;
    });
    expect(style.bg, "lighter than the chip's tint").not.toBe(chip);
    const edge = await page.getByTestId("row-connector").boundingBox();
    expect(edge?.height).toBeLessThanOrEqual(1.5);
  });

  test("Buyer messages are in the deal's Messages tab, only that customer's thread; opening one still reads it; with no deal the inbox card stays under the queue", async ({ page }) => {
    await checkedDeal(page);
    // A deal is selected: the inbox card is not under the queue.
    await expect(page.getByTestId("deals-inbox")).toHaveCount(0);
    await page.getByTestId("deal-tab-messages").click();
    const thread = page.getByTestId("deal-thread");
    await expect(thread).toBeVisible();
    await expect(page.getByTestId("deal-ask-quote-messages")).toContainText("early");
    const ids = await thread.locator('[data-testid^="inbox-thread-"]').evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
    expect(ids).toEqual(["inbox-thread-BUYER-1"]);
    await expect(thread.getByTestId("inbox-msg-EX01")).toBeVisible();
    await thread.getByTestId("inbox-msg-EX01").click();
    await expect(page).toHaveURL(/decision=deal%3AOFF-/);
    // Closing the deal returns the card under the queue.
    await page.getByTestId("deal-close").click();
    await expect(page.getByTestId("deals-inbox")).toBeVisible();
  });
});

test.describe("the pair's cause (slice d, task 4)", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  test("What caused the difference? is the server's cause_text for the chosen pair on that day; two replies read the pair map; nothing is listed by the browser", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-cash").click();
    const inspector = page.getByTestId("hv2-inspector");
    await page.getByTestId("home-chart").focus();
    await page.keyboard.press("Home");
    await expect(inspector).toHaveAttribute("data-day", "0");
    const cause = inspector.getByTestId("deal-inspector-day").getByTestId("deal-cause");
    await expect(cause.getByRole("heading", { name: "What caused the difference?" })).toBeVisible();
    await expect(cause).toContainText("Option A: Credit line draw ¥150k today.");
    // Day 2: the request's early payment is on one line and not the other, said by the server.
    await page.keyboard.press("ArrowRight");
    await expect(inspector).toHaveAttribute("data-day", "2");
    await expect(cause).toContainText("As asked: Early payment from Foshan Home Retail Co.");
    // Two replies: Option A and Option B, the request off.
    await page.getByTestId(`deal-chip-${"CTR-6b07cbf70441"}`).click();
    await page.getByTestId("deal-chip-asked").click();
    await page.getByTestId("home-chart").focus();
    await page.keyboard.press("Home");
    await expect(inspector).toHaveAttribute("data-day", "0");
    await expect(inspector.getByTestId("deal-inspector-day-diff")).toContainText("−¥59,986.20");
    await expect(inspector.getByTestId("deal-inspector-day")).toContainText("Option B against Option A");
    await expect(cause).toContainText("Option A: Credit line draw ¥150k today. Option B: Credit line draw ¥90k today.");
  });
});

test.describe("the whole life of a deal (slice f)", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  const recorded = (m: string): { en: TrackerView; zh: TrackerView } => JSON.parse(readFileSync(join(__dirname, "..", "mocks", "tracker", `${m}.json`), "utf8"));
  const figures = async (page: import("@playwright/test").Page) => ({
    headline: await page.getByTestId("tracker-headline").innerText(),
    state: await page.getByTestId("tracker-state").innerText(),
    terms: await page.getByTestId("tracker-terms").innerText(),
    expected: await page.getByTestId("tracker-expected-figure").innerText(),
    actual: await page.getByTestId("tracker-actual-figure").innerText(),
    toCome: await page.getByTestId("tracker-to-come-figure").innerText(),
  });

  test("an agreed deal's Overview is the tracker's body, figure for figure; the lifecycle strip is the server's; Terms holds the agreed terms by scope; the record stays reachable", async ({ page }) => {
    test.setTimeout(240_000);
    await page.goto("/demo");
    await walkStory(page, 3);
    const read = recorded("agreed").en;
    await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(read.decision_id)}`);
    // Three tabs from agreement on; the Overview is the tracker.
    await expect(page.getByTestId("deal-tabs").getByRole("tab")).toHaveText(["Overview", "Terms", "Messages"]);
    await expect(page.getByTestId("deal-tracker")).toBeVisible();
    await expect(page.locator("h1")).toHaveCount(1);
    // The strip: the server's stages in the server's words, never more than seven, a stage the deal does not have is absent.
    const strip = page.getByTestId("deal-lifecycle");
    const stages = read.lifecycle_stages ?? [];
    expect(stages.length).toBeGreaterThan(2);
    expect(stages.length).toBeLessThanOrEqual(7);
    await expect(strip.locator("li")).toHaveCount(stages.length);
    for (const s of stages) {
      const li = strip.getByTestId(`lifecycle-stage-${s.key}`);
      await expect(li).toHaveAttribute("data-state", s.state);
      await expect(li).toContainText(s.label);
      await expect(li).toContainText(s.state_text);
    }
    const inDeals = await figures(page);
    expect(inDeals.headline).toBe(read.headline_text);
    expect(inDeals.expected).toBe(read.cost!.expected.amount_display);
    await expect(page.getByTestId("deal-record-link")).toHaveAttribute("href", /\/decisions\/deal%3AOFF-/);
    // One filled button at most: no next step is due at agreement.
    expect(await filledBrand(page)).toBeLessThanOrEqual(1);
    // The tracker's own address keeps its back link to the record and renders the same figures.
    await page.goto(`/decisions/${encodeURIComponent(read.decision_id)}/tracker`);
    await expect(page.getByTestId("tracker-back")).toContainText("Back to the record");
    expect(await figures(page)).toEqual(inDeals);
    // Terms: the agreed response alone, in the column "Agreed", with its cost quoted.
    await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(read.decision_id)}&view=terms`);
    await expect(page.getByTestId("deal-agreed-scope-terms-head-reply")).toHaveText("Agreed");
    await expect(page.getByTestId("deal-agreed-scope-terms-cell-existing-reply")).toContainText("0.85% off");
    await expect(page.getByTestId("deal-agreed-cost-table")).toBeVisible();
    await expect(page.getByTestId("deal-panel-terms").getByTestId("deal-chart")).toHaveCount(0);
    await expect(page.getByTestId("deal-compare-table")).toHaveCount(0);
    // An address for a tab the agreed deal does not have lands on the Overview.
    await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(read.decision_id)}&view=cash`);
    await expect(page).not.toHaveURL(/view=cash/);
    await expect(page.getByTestId("deal-tracker")).toBeVisible();
  });

  test("the one next step is the deal header's primary button (the tracker's own page keeps its own)", async ({ page }) => {
    test.setTimeout(240_000);
    await page.goto("/demo");
    await walkStory(page, 6);
    const read = recorded("late").en;
    expect(read.next).toBeTruthy();
    await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(read.decision_id)}`);
    const next = page.getByTestId("deal-header").getByTestId("deal-next-action");
    await expect(next).toHaveText(read.next!.label);
    await expect(next).toHaveAttribute("href", read.next!.href);
    expect(await filledBrand(page)).toBe(1);
    await expect(page.getByTestId("deal-tracker").getByTestId("tracker-next-action")).toHaveCount(0);
    await expect(page.getByTestId("deal-tracker").getByTestId("tracker-next")).toContainText(read.next!.text);
  });
});

test.describe("Chinese and a phone (slice b round three)", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  test("zh: the tabs, the header, the mandate sentence, the comparison and the chart speak the owner's voice, with the same figures", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
    await checkedDeal(page);
    await expect(page.getByTestId("deal-tabs").getByRole("tab")).toHaveText(["概览", "比较回复", "现金影响", "消息"]);
    await expect(page.getByTestId("queue-review-open")).toHaveText("查看还价");
    // The server's recommendation and terms, in Chinese.
    await expect(page.getByTestId("deal-mandate")).toContainText(/[一-鿿]/);
    await expect(page.getByTestId("deal-mandate")).not.toContainText("Option A is the reply");
    await expect(page.getByTestId("deal-scope-terms-delta-asked")).toContainText(/[一-鿿]/);
    await page.getByTestId("deal-tab-compare").click();
    await expect(page.getByTestId("deal-compare-head-asked").getByTestId("deal-compare-badge")).toContainText("超出授权");
    await expect(page.getByTestId("deal-compare-row-economic").locator("th")).toContainText("经济影响");
    await expect(page.getByTestId("deal-why-rule")).toContainText("它不按成本对回复排序");
    await expect(page.getByTestId("deal-outcome-row-lowest")).toContainText("¥165k");
    await page.getByTestId("deal-tab-cash").click();
    await expect(page.getByTestId("deal-inspector-day").getByRole("heading", { level: 4 })).toHaveText("这一天");
    await expect(page.getByTestId("deal-inspector-lowest").getByRole("heading", { level: 4 })).toHaveText("各方案的最低点");
    await expect(page.getByTestId("deal-chart-funding")).toContainText("每个方案各用自己的融资安排");
    // No English dictionary label of this round is left on the page.
    const text = await page.getByTestId("deal-pane").innerText();
    for (const english of ["Compare responses", "Cash impact", "Review the counter", "Business consequences", "Why these results differ"]) expect(text, english).not.toContain(english);
  });

  test("a phone (390 px): every tab fits with no sideways scroll, the header's review button and the tabs reach 44 px, and the queue is below the workspace with no rail", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await checkedDeal(page);
    const overflow = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    for (const view of ["overview", "compare", "cash", "messages"]) {
      await page.getByTestId(`deal-tab-${view}`).click();
      await expect(page.getByTestId(`deal-panel-${view}`)).toBeVisible();
      await page.waitForTimeout(400);
      expect(await overflow(), `${view}: no sideways scroll`).toBeLessThanOrEqual(1);
      await expect(page.getByTestId("queue-rail")).toHaveCount(0);
    }
    for (const id of ["queue-review-open", "deal-tab-overview", "deal-tab-compare", "deal-tab-cash", "deal-tab-messages", "deal-close"]) {
      const box = (await page.getByTestId(id).boundingBox())!;
      expect(box.height, id).toBeGreaterThanOrEqual(44);
    }
    // The chart's chips and the timing switch fit the page (their touch height is the coarse pointer's rule, pinned on the phone project).
    await page.getByTestId("deal-tab-cash").click();
    for (const id of ["deal-chip-asked", "deal-scenario-late"]) {
      const box = (await page.getByTestId(id).boundingBox())!;
      expect(box.x + box.width, `${id} fits`).toBeLessThanOrEqual(391);
    }
  });
});

test.describe("live", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(!live(testInfo), "live-mode: a real API");
  });

  test("busy books, Zhuhai: tabs follow the deal, the accept review opens from the header", async ({ page, request }) => {
    await busy(request);
    await page.goto("/deals");
    await page.getByTestId("queue-row").filter({ hasText: "Zhuhai" }).first().getByTestId("queue-select").click();
    await expect(page.getByTestId("deal-header")).toBeVisible();
    await expect(page.getByTestId("deal-tabs").getByRole("tab").first()).toHaveText("Overview");
    const open = page.getByTestId("deal-header").locator('[data-testid="queue-review-open"], [data-testid="accept-review-open"]');
    await expect(open).toHaveCount(1);
  });

  test("busy books: six negotiations show every progressive control; the alert row stays outside the queue; Zhuhai's thread is its own", async ({ page, request }) => {
    await busy(request);
    await page.goto("/deals");
    await expect(page.getByTestId("queue-row")).toHaveCount(6);
    for (const there of ["queue-tabs", "queue-search", "queue-sort-urgency", "queue-group"]) await expect(page.getByTestId(there)).toBeVisible();
    await expect(page.getByTestId("deals-queue").getByTestId("queue-alert")).toHaveCount(0);
    await page.getByTestId("queue-row").filter({ hasText: "Zhuhai" }).first().getByTestId("queue-select").click();
    await page.getByTestId("deal-tab-messages").click();
    const ids = await page.getByTestId("deal-thread").locator('[data-testid^="inbox-thread-"]').evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
    expect(ids.length).toBeLessThanOrEqual(1);
    await expect(page.getByTestId("deals-inbox")).toHaveCount(0);
  });
});
