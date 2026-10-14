import { DEMO_TOKEN, expect, test } from "./fixtures";
import { checkedDeal, filledBrand } from "./helpers";

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
});
