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
  await expect(page.getByTestId("cash-headroom")).toHaveText("Your cash is ¥100k above it");
  await expect(figures).toContainText("Lowest point: ¥405k below your minimum");
  await expect(figures).toContainText("−¥105k");
  const action = page.getByTestId("home-next-action");
  await expect(action.getByTestId("next-action-title")).toHaveText("Secure ¥405k of funding");
  await expect(action.getByTestId("next-action-cost")).toContainText("¥3,113.93");
  // The sections come in the owner's order: risk, plan, options, forecast.
  const order = await page.evaluate(() => ["cash-answer", "home-next-action", "cash-options", "cash-chart"].map((id) => (document.getElementById(id) ?? document.querySelector(`[data-testid="${id}"]`))?.getBoundingClientRect().top ?? -1));
  expect(order[0]).toBeLessThan(order[1]);
  expect(order[1]).toBeLessThan(order[2]);
  expect(order[2]).toBeLessThan(order[3]);
  // The comparison is the server's: grouped and ordered as it sent them, one sentence saying how, a numeral only where the server ranked.
  const options = page.getByTestId("cash-options-list");
  await expect(options).not.toContainText("Router optimum");
  await expect(options).not.toContainText("Cheapest committed plan");
  // The recommended plan is said once, in the plan card above; the server's ordering sentence starts from it, so it is not drawn over the alternatives.
  await expect(page.getByTestId("cash-options-order")).toHaveCount(0);
  await expect(page.getByTestId("cash-options-RECOMMENDED")).toHaveCount(0);
  await expect(options).not.toContainText("Recommended");
  await expect(page.locator("#cash-options")).not.toContainText("ranked by cost");
  expect(await options.locator("[data-group]").evaluateAll((els) => els.filter((el) => el.hasAttribute("data-testid") && el.getAttribute("data-testid")!.startsWith("cash-options-")).map((el) => el.getAttribute("data-group")))).toEqual([
    "CONDITIONAL_ON_BUYER",
    "INSUFFICIENT",
    "NOT_AVAILABLE_YET",
  ]);
  // The plan itself is the card's: its cost is on the page once, and the options hold no second copy of it.
  expect((await page.locator("main").innerText()).match(/¥3,113\.93/g)).toHaveLength(1);
  // What depends on the buyer is its own group, never numbered, saying whose consent it needs; the server's order puts the cheaper first.
  const conditional = page.getByTestId("cash-options-CONDITIONAL_ON_BUYER");
  await expect(conditional.locator("h3")).toHaveText("Only if the buyer agrees to early payment");
  await expect(conditional.locator("li")).toHaveCount(2);
  await expect(conditional).not.toContainText("#");
  await expect(conditional.getByTestId("cash-option-consent").first()).toHaveText("Needs Foshan Home Retail Co. to agree to pay early; it cannot run until they do.");
  await expect(conditional.getByTestId("cash-option-arrival").first()).toHaveText("When the cash arrives depends on the buyer agreeing to pay early.");
  const costs = await conditional.getByTestId("cash-option-total").allTextContents();
  expect(costs[0]).toContain("¥3,938.81");
  expect(costs[1]).toBe("¥5,040.00");
  // Not ranked with the plans that can run now: the one that leaves a gap and the one not available yet carry no numeral either.
  const insufficient = page.getByTestId("cash-options-INSUFFICIENT");
  await expect(insufficient.locator("h3")).toHaveText("Leaves ¥255,000.00 uncovered");
  await expect(insufficient.locator("li[data-key=line_only]")).toContainText("¥255,000.00 short at the worst point");
  await expect(insufficient.locator("li[data-key=line_only]")).toContainText("in 12 days");
  await expect(insufficient).not.toContainText("#");
  const later = page.getByTestId("cash-options-NOT_AVAILABLE_YET");
  await expect(later.locator("h3")).toHaveText("Not available yet: earliest in 21 days");
  await expect(later.locator("li[data-key=line_guaranteed_loan]")).toContainText("All of the funds are available in 21 days.");
  await expect(later.locator("li[data-key=line_guaranteed_loan]")).not.toContainText(/\bday \d/i);
  await expect(later).not.toContainText("#");
  // The forecast is the home's own series: the trough the headline quotes is inside the drawn range, with short labels.
  const chart = page.getByTestId("cash-forecast");
  await expect(chart).toHaveAttribute("data-lowest", "-10500000");
  await expect(chart).toHaveAttribute("data-horizon", "60");
  await expect(chart).toContainText("If you do nothing");
  await expect(chart).toContainText("With the recommended plan");
  await expect(chart).toContainText("Receipt from Foshan Home Retail Co.");
  await expect(chart).not.toContainText("Receipt the ¥420");
  // The subtitle says what the line counts, in the server's words; the Basis fold has the facts behind it; the conclusion says how fresh it is.
  await expect(page.locator("#cash-chart")).toContainText("Expected invoice payments at their due dates and committed funding; overdue payments are excluded; assumed line repayment in 32 days.");
  await expect(page.locator("#cash-chart")).not.toContainText("confirmed receipts and committed funding only");
  const basis = page.getByTestId("cash-forecast-basis");
  await expect(basis).not.toHaveAttribute("open", "");
  await basis.locator("> summary").click();
  await expect(basis.getByTestId("forecast-basis-confirmed")).toHaveText("¥0.00");
  await expect(basis.getByTestId("forecast-basis-expected")).toHaveText("¥1,680,000.00");
  await expect(basis.getByTestId("forecast-basis-repayment")).toHaveText("in 32 days");
  await expect(basis).toContainText("Overdue payments are left out.");
  await expect(page.getByTestId("cash-read-when")).toHaveText("Cash read today");
  // A day with several events is labelled by its net, never by its largest component: day 47's receipt (+¥420k) and operating bill (−¥100k) read "Net ¥320k".
  await page.getByTestId("forecast-horizon-120").click();
  await expect(chart).toContainText("Net ¥320k");
  await expect(chart.locator("svg").first()).not.toContainText("Operating bill");
  await page.getByTestId("forecast-horizon-60").click();
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
  await expect(considered.getByTestId("cash-options-RECOMMENDED")).toBeVisible();
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
  // The cheaper plan that needs two approvals is the ranked alternative (#2); what depends on the buyer follows it, unranked.
  const alternative = page.getByTestId("cash-options-ALTERNATIVE");
  await expect(alternative.locator("h3")).toHaveText("Another way to fund it");
  await expect(alternative.locator('[data-key="router_optimum"]')).toContainText("#2");
  await expect(page.getByTestId("cash-options-RECOMMENDED")).toHaveCount(0);
  await expect(alternative.locator('[data-key="router_optimum"]')).toContainText("¥1,706.10");
  await expect(page.getByTestId("cash-options-CONDITIONAL_ON_BUYER")).not.toContainText("#");
  // The server's roles say it in the alternative's chip, so the grey "a cheaper option exists" note is not drawn a second time;
  // and the first row is titled with its sources, not the generic "Recommended plan".
  await expect(page.getByTestId("cash-cheaper-option")).toHaveCount(0);
  await expect(options.locator('[data-key="recommended_plan"]')).toHaveCount(0);
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
