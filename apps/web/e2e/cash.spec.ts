import { expect, proseOf, test } from "./fixtures";

/**
 * Cash & funding (mock mode): the risk with headroom said directly, the plan, the options in two groups that are never
 * ranked together, then the forecast; the plan's figures are the home's; the chart draws the home's series below zero
 * with the server's short labels. After the plan ran the page states the current funding position and never pairs
 * "no funding is needed" with "ways to cover the gap".
 */

test.beforeEach(async ({ context }, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec");
  await context.addInitScript(() => {
    try {
      sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: "mock-owner" }));
    } catch {
      /* storage unavailable */
    }
  });
});

test("risk, plan, options, forecast: one set of figures, in the owner's order", async ({ page }) => {
  await page.goto("/cash");
  await expect(page.getByTestId("cash-headline")).toHaveText("Your cash reserve becomes unsafe in 12 days.");
  // Headroom is said directly: cash minus the reserve, today and at the lowest point ahead.
  const figures = page.getByTestId("cash-figures");
  await expect(figures).toContainText("Available headroom");
  await expect(figures).toContainText("¥100k");
  await expect(figures).toContainText("Lowest forecast headroom");
  await expect(figures).toContainText("−¥405k");
  const action = page.getByTestId("home-next-action");
  await expect(action.getByTestId("next-action-title")).toHaveText("Secure ¥405k of funding");
  await expect(action.getByTestId("next-action-cost")).toContainText("¥3,113.93");
  // The sections come in the owner's order: risk, plan, options, forecast.
  const order = await page.evaluate(() => ["cash-answer", "home-next-action", "cash-options", "cash-chart"].map((id) => (document.getElementById(id) ?? document.querySelector(`[data-testid="${id}"]`))?.getBoundingClientRect().top ?? -1));
  expect(order[0]).toBeLessThan(order[1]);
  expect(order[1]).toBeLessThan(order[2]);
  expect(order[2]).toBeLessThan(order[3]);
  // Two groups: the plans that fully protect cash, numbered and named by their sources; the rest apart, never numbered.
  const options = page.getByTestId("cash-options-list");
  await expect(options).not.toContainText("Router optimum");
  await expect(options).not.toContainText("Cheapest committed plan");
  const full = page.getByTestId("cash-options-full");
  await expect(full).toContainText("Plans that fully protect your cash");
  await expect(full.getByTestId("cash-option-selected")).toContainText("Bank credit line + Invoice financing (onboarded platform)");
  await expect(full.getByTestId("cash-option-selected")).toContainText("Recommended");
  // Words with no cost claim the browser cannot make: the recommended row says it protects cash and can run today, the
  // dearer ones say the server's note ("admissible but dearer than the selected plan").
  await expect(full.getByTestId("cash-option-selected")).toContainText("Fully protects your cash and can run today");
  await expect(full.getByTestId("cash-option-alternative-note").first()).toContainText("admissible but dearer than the selected plan");
  await expect(full).not.toContainText("at a higher cost");

  await expect(full.getByTestId("cash-option-selected")).toContainText("¥3,113.93");
  await expect(full.locator("li")).toHaveCount(3);
  // The recommended plan is #1, then the dearer alternatives in ascending cost.
  const first = full.locator("li").first();
  await expect(first).toHaveAttribute("data-testid", "cash-option-selected");
  await expect(first).toContainText("#1");
  await expect(full.locator("li").nth(1)).toContainText("#2");
  await expect(full).toContainText("Only if the buyer agrees to pay early");
  await expect(full).not.toContainText("Cannot run until the invoice is issued");
  const rest = page.getByTestId("cash-options-rest");
  await expect(rest).toContainText("Insufficient or not currently available");
  await expect(rest.locator("li")).toHaveCount(2);
  await expect(rest.locator("li[data-key=line_only]")).toContainText("Does not cover the gap");
  await expect(rest.locator("li[data-key=line_only]")).toContainText("¥255,000.00 short at the worst point");
  await expect(rest.locator("li[data-key=line_only]")).toContainText("in 12 days");
  await expect(rest.locator("li[data-key=line_guaranteed_loan]")).toContainText("Not available");
  await expect(rest.locator("li[data-key=line_guaranteed_loan]")).toContainText("in 12 days");
  await expect(rest.locator("li[data-key=line_guaranteed_loan]")).not.toContainText(/\bday \d/i);
  await expect(rest).not.toContainText("#");
  // The forecast is the home's own series: the trough the headline quotes is inside the drawn range, with short labels.
  const chart = page.getByTestId("cash-forecast");
  await expect(chart).toHaveAttribute("data-lowest", "-10500000");
  await expect(chart).toHaveAttribute("data-horizon", "60");
  await expect(chart).toContainText("If you do nothing");
  await expect(chart).toContainText("With the recommended plan");
  await expect(chart).toContainText("Receipt from Foshan Home Retail Co.");
  await expect(chart).not.toContainText("Receipt the ¥420");
  await page.getByTestId("forecast-horizon-120").click();
  await expect(chart).toHaveAttribute("data-horizon", "120");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // No "day N" in the prose, the options included: the rows say the server's `note_when` ("cash in 21 days"), never the router's "cash on day 21".
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);

  // The sources explainer opens on demand and names each facility in plain words.
  await page.getByTestId("cash-sources").locator("> summary").click();
  await expect(page.getByTestId("facility-FAC-LINE")).toContainText("Ready to use");
});

test("after the plan ran, the page states the current funding and folds the comparison away", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("fix-ALERT-RESERVE-12").click();
  await expect(page.getByTestId("fix-result")).toBeVisible();
  await page.goto("/cash");
  await expect(page.getByTestId("cash-headline")).toHaveText("You're covered.");
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  const current = page.locator("#cash-current");
  await expect(current).toContainText("Current funding");
  await expect(current.getByTestId("cash-lot-landed")).toContainText("¥150,000.00");
  await expect(current.getByTestId("cash-lot-landed")).toContainText("Received today");
  await expect(current.getByTestId("cash-lot-transit")).toContainText("¥255,000.00");
  await expect(current.getByTestId("cash-lot-transit")).toContainText("Arrives in 3 days");
  await expect(current.getByTestId("cash-no-gap")).toHaveText("No additional funding is needed.");
  // The comparison is history now: closed under "Other plans considered", never beside "no funding is needed" as a to-do list.
  await expect(page.locator("body")).not.toContainText(/ways to cover the gap/i);
  const considered = page.getByTestId("cash-options");
  await expect(considered.locator("> summary")).toHaveText("Other plans considered");
  await expect(considered).not.toHaveAttribute("open", "");
  await considered.locator("> summary").click();
  await expect(considered.getByTestId("cash-options-full")).toBeVisible();
  await expect(considered.getByTestId("cash-plan-detail").locator("> summary")).toHaveText("Why this plan was selected");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
});

test("day 34: the first breach is also the worst point, so the figures row says it once", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/cash");
  const figures = page.getByTestId("cash-figures");
  await expect(figures).toContainText("Cash at first breach (also the lowest point)");
  await expect(figures).toContainText("¥100k · in 8 days");
  await expect(figures).not.toContainText("Worst point");
  await expect(figures).not.toContainText("Cash becomes unsafe");
  await expect(figures.getByText("in 8 days")).toHaveCount(1);
});
