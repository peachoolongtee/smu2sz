import { expect, test } from "./fixtures";

/**
 * Cash & funding (mock mode): the risk, the plan, the other options and then the forecast, in that order; the plan's figures
 * are the home's; the chart draws the home's series below zero; the options carry business names and no internal label.
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
  const action = page.getByTestId("home-next-action");
  await expect(action.getByTestId("next-action-title")).toHaveText("Secure ¥405k of funding");
  await expect(action.getByTestId("next-action-cost")).toContainText("¥3,113.93");
  // The sections come in the owner's order: risk, plan, options, forecast.
  const order = await page.evaluate(() => ["cash-answer", "home-next-action", "cash-options", "cash-chart"].map((id) => (document.getElementById(id) ?? document.querySelector(`[data-testid="${id}"]`))?.getBoundingClientRect().top ?? -1));
  expect(order[0]).toBeLessThan(order[1]);
  expect(order[1]).toBeLessThan(order[2]);
  expect(order[2]).toBeLessThan(order[3]);
  // The options list speaks in business names, the cheapest first and marked as recommended.
  const options = page.getByTestId("cash-options-list");
  await expect(options).not.toContainText("Router optimum");
  await expect(options.getByTestId("cash-option-selected")).toContainText("Cheapest committed plan");
  await expect(options.getByTestId("cash-option-selected")).toContainText("Recommended");
  await expect(options.getByTestId("cash-option-selected")).toContainText("¥3,113.93");
  // The forecast is the home's own series: the trough the headline quotes is inside the drawn range.
  const chart = page.getByTestId("cash-forecast");
  await expect(chart).toHaveAttribute("data-lowest", "-10500000");
  await expect(chart).toHaveAttribute("data-horizon", "60");
  await expect(chart).toContainText("If you do nothing");
  await expect(chart).toContainText("With the recommended plan");
  await page.getByTestId("forecast-horizon-120").click();
  await expect(chart).toHaveAttribute("data-horizon", "120");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // The sources explainer opens on demand and names each facility in plain words.
  await page.getByTestId("cash-sources").locator("> summary").click();
  await expect(page.getByTestId("facility-FAC-LINE")).toContainText("Ready to use");
});
