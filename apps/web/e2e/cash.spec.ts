import { expect, proseOf, test } from "./fixtures";
import { filledBrand, openCashOptions, runPlan, walkStory, openOperatorTools } from "./helpers";

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
  // Four facts on the picture's header row (cash today, the minimum, when cash becomes unsafe, the worst point); the headroom is the caption of the one it belongs to.
  const figures = page.getByTestId("cash-figures");
  await expect(figures.locator("dt")).toHaveText(["Cash today", "Minimum", "Cash becomes unsafe", "Worst point"]);
  await expect(page.getByTestId("cash-unsafe-when")).toHaveText("in 12 days");
  await expect(page.getByTestId("cash-headroom")).toHaveText("Your cash is ¥100k above it");
  await expect(figures).toContainText("Lowest point: ¥405k below your minimum");
  await expect(figures).toContainText("−¥105k");
  const action = page.getByTestId("home-next-action");
  await expect(action.getByTestId("next-action-title")).toHaveText("Secure ¥405k of funding");
  await expect(action.getByTestId("next-action-cost")).toContainText("¥3,113.93");
  // The sections come in the owner's order: the answer, the plan bar (the page's most important part), the picture, the options (the bar is in flow, so the order is the document's).
  const inOrder = await page.evaluate(() => {
    const els = ["cash-answer", "home-next-action", "cash-chart", "cash-options-all"].map((id) => document.getElementById(id) ?? document.querySelector(`[data-testid="${id}"]`));
    return els.every((el, i) => el !== null && (i === 0 || (els[i - 1]!.compareDocumentPosition(el!) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0));
  });
  expect(inOrder).toBe(true);
  // The comparison is the server's: grouped and ordered as it sent them, one sentence saying how, a numeral only where the server ranked.
  await openCashOptions(page);
  const options = page.getByTestId("cash-options-list");
  await expect(options).not.toContainText("Router optimum");
  await expect(options).not.toContainText("Cheapest committed plan");
  // The recommended plan is the first row of the radio group and the one chosen by default; the server's ordering sentence starts from it.
  await expect(page.getByTestId("cash-options-order")).toHaveCount(1);
  await expect(page.getByTestId("cash-options-RECOMMENDED")).toHaveCount(1);
  await expect(page.getByTestId("cash-options-RECOMMENDED").locator("input[type=radio]")).toBeChecked();
  await expect(page.getByTestId("cash-options-list")).not.toContainText("ranked by cost");
  expect(await options.locator("[data-group]").evaluateAll((els) => els.filter((el) => el.hasAttribute("data-testid") && el.getAttribute("data-testid")!.startsWith("cash-options-")).map((el) => el.getAttribute("data-group")))).toEqual([
    "RECOMMENDED",
    "CONDITIONAL_ON_BUYER",
    "INSUFFICIENT",
    "NOT_AVAILABLE_YET",
  ]);
  // The plan's cost is on the plan bar and on its own row, in the server's string.
  expect((await page.locator("main").innerText()).match(/¥3,113\.93/g)).toHaveLength(2);
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
  // The alternative line is the chosen plan, under its own name.
  await expect(chart.getByTestId("picture-view-plan")).toHaveText("Chosen plan");
  await expect(chart.getByTestId("picture-table")).toContainText("Bank credit line + Invoice financing (onboarded platform)");
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
  // The 30 / 60 / 120-day switch drives the picture's window: the 120-day picture reaches the receipt and the operating bill of day 47.
  await page.getByTestId("forecast-horizon-30").click();
  await expect(chart).toHaveAttribute("data-horizon", "30");
  await page.getByTestId("forecast-horizon-120").click();
  await expect(chart.getByTestId("picture-table")).toContainText("Operating bill");
  await expect(chart).toHaveAttribute("data-horizon", "120");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // No "day N" in the prose, the options included: the rows say the server's `note_when` ("cash in 21 days"), never the router's "cash on day 21".
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);

  // The sources explainer opens on demand and names each facility in plain words.
  await page.getByTestId("cash-sources").locator("> summary").click();
  await expect(page.getByTestId("facility-FAC-LINE")).toContainText("Ready to use");
});

test("after the plan ran, the page states the current funding and folds the comparison away", async ({ page }) => {
  await page.goto("/cash"); // the plan is run on Cash & funding
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
  const current = page.locator("#cash-sources-now");
  await expect(current).toContainText("Your funding");
  await expect(current.getByTestId("cash-current-amount").filter({ hasText: "¥150,000.00" })).toHaveCount(1);
  await expect(current.getByTestId("cash-current-amount").filter({ hasText: "¥255,000.00" })).toHaveCount(1);
  await expect(current).toContainText("today");
  await expect(current).toContainText("in 3 days");
  await expect(current.getByTestId("cash-no-gap")).toHaveText("No additional funding is needed.");
  // No comparison was taken when the plan was chosen (the plan ran from the home), and a fresh plan on covered books is empty:
  // the page shows the current funding and nothing that reads as a to-do list.
  await expect(page.locator("body")).not.toContainText(/ways to cover the gap/i);
  await expect(page.getByTestId("cash-options")).toHaveCount(0);
  await expect(page.locator("#cash-options")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // One projection: the debt readings in the summary line are the table's first month.
  await page.getByTestId("cash-readings").locator("> summary").click();
  const now = await page.getByTestId("cash-readings-now").innerText();
  const firstRow = (await page.getByTestId("cash-readings").locator("tbody tr").first().innerText()).split("\t");
  const lev = firstRow[firstRow.length - 1].trim();
  const dscr = firstRow[firstRow.length - 2].trim();
  expect(now).toContain(lev);
  expect(now).toContain(dscr);
});

test("covered after the walk: the comparison taken when the plan was chosen is history, closed under Other plans considered", async ({ page }) => {
  // The guided demo's funding step records the Debt Desk as it stood when the decision was made.
  await page.goto("/demo");
  await walkStory(page, 2); // the buyer asks, FLOW decides: the Debt Desk's view at decision time is kept
  await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "business" })));
  await page.goto("/cash"); // the plan is run on Cash & funding
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
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/cash");
  await expect(page.getByTestId("home-next-action").getByTestId("next-action-cost")).toContainText("¥1,782.19");
  await openCashOptions(page);
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
  await expect(page.getByTestId("cash-options-RECOMMENDED")).toHaveCount(1);
  await expect(alternative.locator('[data-key="router_optimum"]')).toContainText("¥1,706.10");
  await expect(page.getByTestId("cash-options-CONDITIONAL_ON_BUYER")).not.toContainText("#");
  // The server's roles say it in the alternative's chip, so the grey "a cheaper option exists" note is not drawn a second time;
  // and the first row is titled with its sources, not the generic "Recommended plan".
  await expect(page.getByTestId("cash-cheaper-option")).toHaveCount(0);
  await expect(options.locator('[data-key="recommended_plan"]')).toHaveCount(1);
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
});

test("day 34: the first breach is also the worst point, so the figures row says it once", async ({ page }) => {
  await page.goto("/demo");
  await openOperatorTools(page);
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
  // The sandbox is run for a negotiation: the link names none, so the page asks which (it never opens on a sample, audit UX26).
  await expect(page.getByTestId("whatif-ask")).toBeVisible();
  expect(await proseOf(page, ["details"])).not.toMatch(/\bday \d/i);
});

test("engine words stay out of level 1 on Cash & funding and Activity", async ({ page }) => {
  await page.goto("/cash");
  // Visible text only (closed disclosures hold the audit level).
  const cash = await page.locator("main").innerText();
  for (const word of [/\bverdict\b/i, /sandbox/i, /admissible/i, /\bexecutor\b/i, /hash/i]) expect(cash, String(word)).not.toMatch(word);
  await expect(page.locator("#cash-whatif")).toContainText("watch your cash line move");
  await expect(page.locator("#cash-whatif").getByRole("link")).toHaveText("Open the sandbox");
  await page.goto("/activity");
  const activity = await page.locator("main").innerText();
  for (const word of [/hash-chained/i, /\bexecutor\b/i, /operations the/i]) expect(activity, String(word)).not.toMatch(word);
  await expect(page.locator("#activity-timeline")).toContainText("Every entry stays in the record");
});

// ---- pages A1 (part 2): the picture, the ways to cover the gap as a radio group, the facility bars

test("the page has one h1 (the server's headline) and one filled primary, and no card chrome above the picture", async ({ page }) => {
  await page.goto("/cash");
  await expect(page.getByTestId("cash-headline")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Your cash reserve becomes unsafe in 12 days.");
  expect(await filledBrand(page)).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("choosing a plan row draws its line on the picture under its name; a row with no line says why and leaves the baseline", async ({ page }) => {
  await page.goto("/cash");
  await openCashOptions(page);
  const picture = page.getByTestId("cash-picture");
  await expect(picture).toHaveAttribute("data-plan", "yes");
  await expect(picture.getByTestId("picture-line-plan")).toBeVisible();
  await expect(picture.getByTestId("picture-table")).toContainText("Bank credit line + Invoice financing (onboarded platform)");
  const recommended = page.locator("li[data-key=router_optimum]");
  await expect(recommended.locator("input[type=radio]")).toBeChecked();
  // The credit line alone leaves a gap: its line is drawn, named for it, and the row is the chosen one.
  await page.locator("li[data-key=line_only] label").click();
  await expect(page.locator("li[data-key=line_only] input[type=radio]")).toBeChecked();
  await expect(recommended.locator("input[type=radio]")).not.toBeChecked();
  await expect(picture.getByTestId("picture-table")).toContainText("Credit line only");
  await expect(picture.getByTestId("picture-line-plan")).toBeVisible();
  await expect(page.getByTestId("cash-forecast")).toHaveAttribute("data-alternative", "line_only");
  // A plan the server could not project has no line: its note shows and the picture is the baseline alone.
  await page.locator("li[data-key=line_guaranteed_loan] label").click();
  await expect(page.locator("li[data-key=line_guaranteed_loan]").getByTestId("cash-option-series-note")).toHaveText("Cash cannot be projected for this option.");
  await expect(picture).toHaveAttribute("data-plan", "no");
  await expect(picture.getByTestId("picture-line-plan")).toHaveCount(0);
});

test("each option carries a cost bar sized against the dearest row and a coverage bar with its uncovered part said in words", async ({ page }) => {
  await page.goto("/cash");
  const pct = async (key: string) => Number(await page.locator(`li[data-key=${key}] [data-testid=cash-option-cost-bar]`).getAttribute("data-pct"));
  expect(await pct("full_discount")).toBe(100);
  expect(await pct("router_optimum")).toBeGreaterThan(await pct("line_only"));
  expect(await pct("router_optimum")).toBeLessThan(100);
  const gap = page.locator("li[data-key=line_only]");
  await expect(gap.getByTestId("cash-option-coverage")).toHaveAttribute("data-gap", "25500000");
  await expect(gap).toContainText("Uncovered ¥255,000.00");
  await expect(page.locator("li[data-key=router_optimum] [data-testid=cash-option-coverage]")).toHaveAttribute("data-gap", "0");
});

test("your funding sources: a utilisation bar per facility with the server's limit, drawn and available", async ({ page }) => {
  await page.goto("/cash");
  const line = page.getByTestId("cash-facility-FAC-LINE");
  await expect(line).toContainText("Bank credit line");
  await expect(line).toContainText("¥150,000.00");
  await expect(line.getByTestId("cash-facility-bar")).toHaveAttribute("data-pct", "0");
  await expect(line).toContainText("cash in same day");
  await page.goto("/demo");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/cash");
  await expect(page.getByTestId("cash-facility-FAC-LINE")).toBeVisible();
  await expect.poll(async () => Math.max(...(await page.getByTestId("cash-facility-bar").evaluateAll((els) => els.map((el) => Number(el.getAttribute("data-pct"))))))).toBeGreaterThan(0);
});

test("the plan bar is in flow at every width (under the picture at 1280 px, covering none of its plot; right after the headline at 390 px)", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/cash");
  await expect(page.getByTestId("home-next-action")).toBeVisible();
  expect(await page.getByTestId("home-next-action").evaluate((el) => getComputedStyle(el).position)).not.toBe("sticky");
  // Nothing covers the picture's plot: at the top of the page, the element on top at each corner and the middle of the svg is the svg itself.
  await page.locator('[data-testid="cash-picture"] svg[role=img]').scrollIntoViewIfNeeded();
  const covered = await page.evaluate(() => {
    const svg = document.querySelector('[data-testid="cash-picture"] svg[role=img]')!;
    const r = svg.getBoundingClientRect();
    const pts = [[0.1, 0.1], [0.9, 0.1], [0.5, 0.5], [0.1, 0.85], [0.9, 0.85]];
    return pts.filter(([fx, fy]) => {
      const el = document.elementFromPoint(r.left + r.width * fx, r.top + r.height * fy);
      return !el || !svg.contains(el);
    }).length;
  });
  expect(covered).toBe(0);
  // In flow, above the picture: the plan is the page's most important part, so the plot starts under the bar's foot.
  const below = await page.evaluate(() => document.querySelector('[data-testid="home-next-action"]')!.getBoundingClientRect().bottom <= document.querySelector('[data-testid="cash-picture"] svg[role=img]')!.getBoundingClientRect().top + 1);
  expect(below).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByTestId("home-next-action")).toBeVisible();
  expect(await page.getByTestId("home-next-action").evaluate((el) => getComputedStyle(el).position)).not.toBe("sticky");
  const order = await page.evaluate(() => {
    const bar = document.querySelector('[data-testid="home-next-action"]')!;
    const chart = document.getElementById("cash-chart")!;
    return (bar.compareDocumentPosition(chart) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
  });
  expect(order).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("the new strings are in Chinese too", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.goto("/cash");
  await openCashOptions(page);
  await expect(page.getByTestId("cash-options-list")).toBeVisible();
  await expect(page.getByTestId("cash-options-list")).toContainText("成本");
  await expect(page.getByTestId("cash-options-list")).toContainText("已覆盖");
  await expect(page.locator("#cash-sources-now").getByRole("heading", { name: "您的资金" })).toBeVisible();
  await expect(page.getByTestId("cash-figures")).toContainText("最低储备");
});
