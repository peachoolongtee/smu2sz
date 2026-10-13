import { DEMO_TOKEN, expect, test } from "./fixtures";
import { checkedDeal } from "./helpers";

/**
 * Slice B round two (docs/design/flow-mockup-2026-10-13/04_slice_b_round_two.md): the Deals queue's controls, the workspace's timing diagram and its two switchable cards, the Customer page's flow,
 * its links and the share bar, and Approvals' lifecycle. The mock project runs on the API's recordings; the live project on a real API and the busy books. Every string is the server's, read from the page.
 */

const live = (info: { project: { name: string } }) => info.project.name === "live";

test.describe("mock", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  test("the timing diagram has a bar for current terms, the buyer's request and FLOW's counter on one scale, with the server's words and the difference said", async ({ page }) => {
    await checkedDeal(page);
    const diagram = page.getByTestId("deal-timing");
    await expect(diagram).toBeVisible();
    await expect(diagram.getByTestId("deal-timing-bar-current")).toHaveAttribute("data-days", "45");
    await expect(diagram.getByTestId("deal-timing-bar-asked")).toHaveAttribute("data-days", "60");
    await expect(diagram.getByTestId("deal-timing-bar-reply")).toHaveAttribute("data-days", "45");
    await expect(diagram).toContainText("Current terms");
    await expect(diagram).toContainText("Buyer requests");
    await expect(diagram).toContainText("FLOW counter");
    await expect(page.getByTestId("deal-timing-delta")).toHaveText("+15 days requested by buyer");
    // The image has a name made of the server's words.
    await expect(diagram.getByTestId("deal-timing-svg")).toHaveAttribute("aria-label", /Payment period: .*45 days/);
  });

  test("the cost and cash cards: the reason's card is open, a press swaps them, the address says which, and Escape folds it before the selection", async ({ page }) => {
    await checkedDeal(page);
    const cost = page.getByTestId("deal-card-cost");
    const cash = page.getByTestId("deal-card-cash");
    // Each card carries its headline figures for both options on one line, folded or open.
    await expect(cost.getByTestId("deal-card-cost-headline")).toContainText("¥28,326.92");
    await expect(cost.getByTestId("deal-card-cost-headline")).toContainText("¥3,027.77");
    await expect(cash.getByTestId("deal-card-cash-headline")).toContainText("Option A");
    await expect(cash).toHaveAttribute("data-open", "true"); // the recommendation reason is about cash
    await expect(cash.getByTestId("deal-card-cash-toggle")).toHaveAttribute("aria-expanded", "true");
    await cost.getByTestId("deal-card-cost-toggle").click();
    await expect(page).toHaveURL(/show=cost/);
    await expect(cost).toHaveAttribute("data-open", "true");
    await expect(cash).toHaveAttribute("data-open", "false");
    await expect(page.getByTestId("deal-cost-table")).toBeVisible();
    // Escape folds the open card (both folded: `show=none`); the next Escape clears the selection.
    await page.keyboard.press("Escape");
    await expect(page).toHaveURL(/show=none/);
    await expect(cost).toHaveAttribute("data-open", "false");
    await expect(page.getByTestId("deal-pane")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("deal-pane")).toHaveCount(0);
  });

  test("a deep link keeps the open card, and Full analysis opens the reasons: the server's reason, who decides each path, the assumptions and the rule", async ({ page }) => {
    await checkedDeal(page);
    await page.goto(`${new URL(page.url()).pathname}${new URL(page.url()).search}&show=cost&investigate=1`);
    await expect(page.getByTestId("deal-card-cost")).toHaveAttribute("data-open", "true");
    await expect(page.getByTestId("deal-compare-toggle")).toHaveAttribute("aria-expanded", "true");
    const why = page.getByTestId("deal-why");
    await expect(why).toContainText("Why FLOW recommends this");
    await expect(page.getByTestId("deal-why-reason")).toContainText("Recommended because");
    await expect(page.getByTestId("deal-why-authority")).toContainText("Option A.");
    await expect(page.getByTestId("deal-why-rule")).toHaveText("FLOW recommends the first reply it may send within your mandate; it does not rank replies by cost.");
    await expect(page.getByTestId("deal-compare-table")).toBeVisible();
    await expect(page.getByTestId("deal-chart")).toBeVisible();
  });

  test("the queue's controls: sort by latest activity is offered once the server says when each moved, and grouping files rows under their customer", async ({ page }) => {
    await checkedDeal(page);
    await expect(page.getByTestId("queue-sort-urgency")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("queue-sort-latest")).toBeEnabled();
    await page.getByTestId("queue-sort-latest").click();
    await expect(page.getByTestId("queue-sort-latest")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("queue-activity").first()).toBeVisible();
    await page.getByTestId("queue-group").click();
    await expect(page.getByTestId("queue-group")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("queue-group-heading").first()).toContainText("Foshan");
    // Nothing else changed: the same row, selected.
    await expect(page.getByTestId("queue-row").first()).toHaveAttribute("data-selected", "true");
  });

  test("Customer: the share figure has its bar, the flow's steps and chips lead to the invoice and the money, and the exposure is a table", async ({ page }) => {
    await checkedDeal(page);
    await page.goto("/customers/BUYER-1");
    await expect(page.getByTestId("customer-figure-share-bar")).toBeVisible();
    const flow = page.getByTestId("customer-flow");
    expect(await flow.getByTestId("customer-flow-steps").locator("li").count()).toBeGreaterThanOrEqual(2);
    await expect(flow.getByTestId("customer-flow-step-owed")).toContainText("Foshan owes you");
    await expect(flow.getByTestId("customer-flow-step-link-owed")).toHaveAttribute("href", /\/receivables\?/);
    const chips = flow.getByTestId("customer-flow-links").getByRole("link");
    expect(await chips.count()).toBeGreaterThanOrEqual(2);
    await expect(page.getByTestId("customer-exposure-table")).toBeVisible();
  });

  test("Approvals: the lifecycle shows three stages, the first current while the owner has not authorized, and the button names the act", async ({ page }) => {
    await page.goto("/demo");
    await page.getByTestId("more-run-capex").click();
    await page.getByTestId("capex-apply").click();
    await expect(page.getByTestId("capex-applied")).toBeVisible();
    await page.goto("/approvals");
    const stages = page.getByTestId("approval-stage");
    await expect(stages).toHaveCount(3);
    await expect(stages.nth(0)).toHaveAttribute("data-state", "current");
    await expect(stages.nth(1)).toHaveAttribute("data-state", "next");
    await expect(stages.nth(2)).toHaveAttribute("data-state", "next");
    await expect(page.getByTestId("approval-approve-APR-000001")).toHaveText("Authorize the application");
  });
});

test.describe("live", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(!live(testInfo), "live-mode: a real API and the busy books");
  });

  async function busy(request: import("@playwright/test").APIRequestContext) {
    const port = process.env.E2E_API_PORT ?? 8000;
    const res = await request.post(`http://localhost:${port}/demo/reset?scenario=busy`, { headers: { "X-Owner-Token": DEMO_TOKEN } });
    expect(res.ok()).toBeTruthy();
  }

  test("the busy queue: distinct subjects, lifecycle words, sort by latest activity and grouping by customer", async ({ page, request }) => {
    await busy(request);
    await page.goto("/deals");
    await expect(page.getByTestId("queue-row")).toHaveCount(6);
    const subjects = await page.getByTestId("queue-subject").allTextContents();
    expect(new Set(subjects).size, "every negotiation has its own subject").toBe(subjects.length);
    for (const word of ["Owner review needed", "Counter ready", "More information needed"]) await expect(page.getByTestId("queue-status").filter({ hasText: word }).first()).toBeVisible();
    await expect(page.locator("main")).not.toContainText(/OFF-|RCV-|\bDay \d/);
    await expect(page.getByTestId("queue-sort-latest")).toBeEnabled();
    await page.getByTestId("queue-sort-latest").click();
    await expect(page.getByTestId("queue-activity").first()).toBeVisible();
    await page.getByTestId("queue-group").click();
    const headings = (await page.getByTestId("queue-group-heading").allTextContents()).map((h) => h.replace(/\s*\(\d+\)$/, ""));
    expect(headings.length, "three customers").toBe(3);
    expect(headings.some((h) => h.startsWith("Foshan"))).toBe(true);
    // Demo mode may show the offer's id; Business never does.
    await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "demo" })));
    await page.reload();
    await expect(page.getByTestId("queue-subject").first()).toContainText(/OFF-/);
  });

  test("Foshan's EX01 on the busy books: the cash card is open for a request that breaches the reserve, the timing diagram says the difference, and the customer page leads with the selected negotiation", async ({ page, request }) => {
    await busy(request);
    await page.goto("/deals");
    await page.getByTestId("queue-row").filter({ hasText: "60-day terms" }).getByTestId("queue-select").click();
    await expect(page.getByTestId("deal-card-cash")).toHaveAttribute("data-open", "true");
    await expect(page.getByTestId("deal-timing-delta")).toContainText("15 days");
    await expect(page.getByTestId("deal-timing-bar-current")).toBeVisible();
    await page.getByTestId("deal-selected-customer").click();
    await expect(page.getByTestId("customer-relationship")).toContainText("Foshan contributes an estimated");
    await expect(page.getByTestId("customer-decision-heading")).toContainText("60-day terms");
    await expect(page.getByTestId("customer-others")).toContainText("Other open negotiations (3)");
    await expect(page.getByTestId("customer-flow-links").getByRole("link").first()).toBeVisible();
  });
});
