import { expect, proseOf, test } from "./fixtures";
import { runPlan, walkStory } from "./helpers";

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
  // Four fact tiles (cash today, the reserve, when cash becomes unsafe, the worst point); the headroom is the caption of the tile it belongs to.
  const figures = page.getByTestId("cash-figures");
  await expect(figures.locator("dt")).toHaveText(["Cash today", "Minimum cash reserve", "Cash becomes unsafe", "Worst point"]);
  await expect(page.getByTestId("cash-unsafe-when")).toHaveText("in 12 days");
  await expect(figures).toContainText("Available headroom");
  await expect(page.getByTestId("cash-headroom")).toHaveText("¥100k");
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
  await expect(full.getByTestId("cash-option-alternative-note").first()).toContainText("within your limits but dearer than the selected plan");
  await expect(full).not.toContainText("at a higher cost");

  await expect(full.getByTestId("cash-option-selected")).toContainText("¥3,113.93");
  // Each row opens to why it ranks where it does: closed first, the server's note once it is tapped; what is uncovered stays on the line.
  const alt = full.locator("li").nth(1);
  await expect(alt.getByTestId("cash-option-details")).not.toHaveAttribute("open", "");
  await expect(alt.getByTestId("cash-option-why")).toBeHidden();
  await alt.locator("summary").click();
  await expect(alt.getByTestId("cash-option-why")).toBeVisible();
  await expect(alt.getByTestId("cash-option-why")).toContainText("within your limits but dearer than the selected plan");
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
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("fix-result")).toBeVisible();
  await page.goto("/cash");
  await expect(page.getByTestId("cash-headline")).toHaveText("You're covered.");
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  await expect(page.getByTestId("cash-unsafe-when")).toHaveText("Not in the next 120 days");
  // No plan beside the line: it is the projection, not "if you do nothing", in the legend and in the table.
  const chart = page.getByTestId("cash-forecast");
  await expect(chart).toContainText("Projected cash");
  await expect(chart).not.toContainText("If you do nothing");
  await expect(chart).not.toContainText("With the recommended plan");
  const current = page.locator("#cash-current");
  await expect(current).toContainText("Current funding");
  await expect(current.getByTestId("cash-lot-landed")).toContainText("¥150,000.00");
  await expect(current.getByTestId("cash-lot-landed")).toContainText("today");
  await expect(current.getByTestId("cash-lot-transit")).toContainText("¥255,000.00");
  await expect(current.getByTestId("cash-lot-transit")).toContainText("in 3 days");
  await expect(current.getByTestId("cash-no-gap")).toHaveText("No additional funding is needed.");
  // No comparison was taken when the plan was chosen (the plan ran from the home), and a fresh plan on covered books is empty:
  // the page shows the current funding and nothing that reads as a to-do list.
  await expect(page.locator("body")).not.toContainText(/ways to cover the gap/i);
  await expect(page.getByTestId("cash-options")).toHaveCount(0);
  await expect(page.locator("#cash-options")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // One projection: the debt readings on Cash & funding are the Home's, said in the summary line and in the table's first month.
  await page.getByTestId("cash-readings").locator("> summary").click();
  const now = await page.getByTestId("cash-readings-now").innerText();
  const firstRow = (await page.getByTestId("cash-readings").locator("tbody tr").first().innerText()).split("\t");
  const lev = firstRow[firstRow.length - 1].trim();
  const dscr = firstRow[firstRow.length - 2].trim();
  await page.goto("/");
  await page.getByTestId("home-details").locator("> summary").click();
  expect(now).toContain(await page.getByTestId("home-leverage").innerText());
  expect(now).toContain(await page.getByTestId("home-dscr").innerText());
  expect(await page.getByTestId("home-leverage").innerText()).toBe(lev);
  expect(await page.getByTestId("home-dscr").innerText()).toBe(dscr);
});

test("covered after the walk: the comparison taken when the plan was chosen is history, closed under Other plans considered", async ({ page }) => {
  // The guided demo's funding step records the Debt Desk as it stood when the decision was made.
  await page.goto("/demo");
  await walkStory(page, 2); // the buyer asks, FLOW decides: the Debt Desk's view at decision time is kept
  await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "business" })));
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("fix-result")).toBeVisible();
  await page.goto("/cash");
  await expect(page.getByTestId("cash-headline")).toHaveText("You're covered.");
  const considered = page.getByTestId("cash-options");
  await expect(considered.locator("> summary")).toHaveText("Other plans considered");
  await expect(considered).not.toHaveAttribute("open", "");
  await considered.locator("> summary").click();
  await expect(considered.getByTestId("cash-options-full")).toBeVisible();
  await expect(considered.getByTestId("cash-plan-detail").locator("> summary")).toHaveText("Why this plan was selected");
});

test("day 34 with a gap open: the options are today's plan, never the day-0 comparison", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/cash");
  await expect(page.getByTestId("home-next-action").getByTestId("next-action-cost")).toContainText("¥1,782.19");
  const options = page.getByTestId("cash-options-list");
  await expect(options).toBeVisible();
  // Not the opening books' ¥3,113.93 plan, and no reading of a gap "22 days ago".
  await expect(options).not.toContainText("¥3,113.93");
  await expect(options).not.toContainText("¥255,000.00");
  await expect(options).not.toContainText(" ago");
  await expect(options).toContainText("¥1,706.10");
  // The server's roles say it in the alternative's chip, so the grey "a cheaper option exists" note is not drawn a second time;
  // and the first row is titled with its sources, not the generic "Recommended plan".
  await expect(page.getByTestId("cash-cheaper-option")).toHaveCount(0);
  await expect(options.locator('[data-key="recommended_plan"]')).not.toContainText("Recommended plan");
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
});

test("day 34: the first breach is also the worst point, so the figures row says it once", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/cash");
  const figures = page.getByTestId("cash-figures");
  await expect(figures).toContainText("Cash at first breach (also the lowest point)");
  await expect(figures).toContainText("¥100k");
  await expect(figures).toContainText("in 8 days");
  await expect(figures).not.toContainText("Worst point");
  await expect(figures).not.toContainText("Cash becomes unsafe");
  await expect(figures.getByText("in 8 days")).toHaveCount(1);
});

test("the doors lead to Capex and the what-if without a day number in their prose", async ({ page }) => {
  await page.goto("/cash");
  await page.locator("#cash-capex").getByRole("link").click();
  await expect(page).toHaveURL(/\/capex/);
  await page.getByRole("button", { name: /Evaluate/ }).first().click();
  await expect(page.getByTestId("capex-as-of")).toHaveText("Computed today: a snapshot, not a live figure.");
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
  await page.goto("/cash");
  await page.locator("#cash-whatif").getByRole("link").click();
  await expect(page).toHaveURL(/\/whatif/);
  await expect(page.getByTestId("whatif-outcome")).toHaveText("Breaks your limits");
  // The engine's own sentences (with their day numbers) are one disclosure down, closed.
  expect(await proseOf(page, ["details"])).not.toMatch(/\bday \d/i);
});

test("engine words stay out of level 1 on Cash & funding and Activity", async ({ page }) => {
  await page.goto("/cash");
  // Visible text only (closed disclosures hold the audit level).
  const cash = await page.locator("main").innerText();
  for (const word of [/\bverdict\b/i, /sandbox/i, /admissible/i, /\bexecutor\b/i, /hash/i]) expect(cash, String(word)).not.toMatch(word);
  await expect(page.locator("#cash-whatif")).toContainText("see the answer and the cash line");
  await expect(page.locator("#cash-whatif").getByRole("link")).toHaveText("Try different terms");
  await page.goto("/activity");
  const activity = await page.locator("main").innerText();
  for (const word of [/hash-chained/i, /\bexecutor\b/i, /operations the/i]) expect(activity, String(word)).not.toMatch(word);
  await expect(page.locator("#activity-timeline")).toContainText("Each entry is sealed to the one before it.");
  await expect(page.locator("#activity-refused")).toContainText("Nothing has been refused yet");
});
