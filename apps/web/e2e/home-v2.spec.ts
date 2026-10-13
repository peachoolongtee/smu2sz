import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, proseOf, test } from "./fixtures";
import { filledBrand } from "./helpers";
import day0 from "../mocks/home_summary_day0.json";
import homeDay0 from "../mocks/home_v2/home_day0.json";
import homeOffer from "../mocks/home_v2/home_offer.json";
import homeAfter from "../mocks/home_v2/home_after_fund.json";
import worklistDay0 from "../mocks/home_v2/worklist_day0.json";
import worklistOffer from "../mocks/home_v2/worklist_offer.json";
import worklistAfter from "../mocks/home_v2/worklist_after_fund.json";
import evaluated from "../mocks/deals_day0_evaluated.json";
import focusOfferRec from "../mocks/home_v2/focus_offer.json";
import exposureRec from "../mocks/home_v2/exposure_offer.json";
import pictureRec from "../mocks/home_v2/picture_offer.json";
import customersOffer from "../mocks/home_v2/customers_offer.json";

/**
 * Home V2 (the web page behind the server's FEATURE_HOME_V2), after the refinement: the header, the metric strip, the recommendation, the company cash forecast with its fixed
 * inspector, the link row and the worklist as an inbox (a pane from `xl`, a bottom sheet on a phone); a selected customer or deal in place, the deal in three levels.
 *
 * Every string below is read from the recordings taken with the flag on (`mocks/home_v2/*.json`, `scripts/record-mocks.mjs --home-v2`): the words are the server's. The mock
 * plays a server with the flag on while the session key `tl-mock-home-v2` is set (lib/mock/home-v2.ts); without it the switch answers off and the Home is the older one.
 * The "offer" state is the opening books with the package offer read by FLOW (the plan is still ready; Needs you holds the Foshan decision).
 */
const KEY = "tl-mock-home-v2";
const ALERT = "ALERT-RESERVE-12";
type Lang = "en" | "zh";

async function overflowX(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

/** The session key and the language are set before the page loads. With `offer`, the owner has FLOW read the package offer first (the Deals page), as the Deals spec does. */
async function open(page: Page, { lang = "en", flag = true, offer = false }: { lang?: Lang; flag?: boolean; offer?: boolean } = {}) {
  await page.context().addInitScript(
    ([key, on, l]) => {
      if (on) sessionStorage.setItem(key as string, "1");
      localStorage.setItem("tl-lang", JSON.stringify({ lang: l }));
    },
    [KEY, flag, lang] as const,
  );
  if (offer) {
    await page.goto("/deals");
    await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
    await page.getByTestId("queue-check-button").click();
    // The queue names the offer once FLOW has read it: only then is the offer open on the books the Home reads.
    const headline = evaluated.deals.find((d) => d.open_offer)!.open_offer!.headline_short;
    await expect(page.getByTestId("queue-heading")).toHaveText(headline);
  }
  await page.goto("/");
  await expect(page.getByTestId(flag ? "home-v2" : "home-status")).toBeVisible();
  if (flag) await expect(page.getByTestId("home-chart")).toBeVisible();
}

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "mock-mode spec on the recorded story (the phone is measured inside it)");
});

test("flag off: the older Home, exactly, and no Home V2 anywhere", async ({ page }) => {
  await open(page, { flag: false });
  await expect(page.getByTestId("home-headline")).toHaveText(day0.cash.headline_conditional);
  await expect(page.getByTestId("home-v2")).toHaveCount(0);
  await expect(page.getByTestId("home-worklist")).toHaveCount(0);
  await expect(page.getByTestId("home-next-action")).toBeVisible();
  await expect(page.getByTestId("rail-mark-0")).toBeAttached();
});

test("a read that carries home_v2 under a server that says the switch is off is the older Home", async ({ page }) => {
  await page.context().addInitScript(([v2]) => sessionStorage.setItem("tl-mock-home-patch", JSON.stringify({ home_v2: v2 })), [homeDay0.en.home_v2] as const);
  await open(page, { flag: false });
  await expect(page.getByTestId("home-headline")).toHaveText(day0.cash.headline_conditional);
  await expect(page.getByTestId("home-v2")).toHaveCount(0);
});

test("the header and the metric strip: the status sentence, 'Updated today', and the three cells are the read's", async ({ page }) => {
  await open(page, { offer: true });
  const h = homeOffer.en;
  const v2 = h.home_v2;
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.getByTestId("hv2-page-name")).toHaveText("Home");
  await expect(page.getByTestId("home-headline")).toHaveText(h.cash.headline_conditional);
  await expect(page.getByTestId("home-status-word")).toHaveText(h.cash.status_word);
  await expect(page.getByTestId("home-read-when")).toHaveText("Updated today");
  await expect(page.getByTestId("home-read-when")).toHaveAttribute("aria-label", "Read today");
  const cash = v2.kpis.cash_available;
  await expect(page.getByTestId("hv2-metric-cash-label")).toHaveText("Cash balance");
  await expect(page.getByTestId("home-kpi-cash-value")).toHaveText(cash.value_display);
  await expect(page.getByTestId("home-kpi-cash-note")).toHaveText(cash.note);
  if (cash.buffer.headroom_text) await expect(page.getByTestId("home-buffer-headroom")).toHaveText(cash.buffer.headroom_text);
  await expect(page.getByTestId("home-buffer")).toHaveAttribute("aria-label", cash.note);
  const low = v2.kpis.lowest_ahead;
  await expect(page.getByTestId("home-kpi-lowest-value")).toHaveText("−¥105,000");
  await expect(page.getByTestId("home-kpi-lowest-value")).toHaveClass(/text-bad-fg/);
  await expect(page.getByTestId("home-kpi-lowest-note")).toHaveText(low.short_note ?? low.note);
  if (low.with_plan) await expect(page.getByTestId("home-kpi-lowest-plan")).toHaveText(`${low.with_plan.label} ${low.with_plan.value_text}`);
  const fund = v2.kpis.funding;
  await expect(page.getByTestId("hv2-metric-funding-label")).toHaveText("Funding plan");
  await expect(page.getByTestId("home-kpi-funding-value")).toHaveText("¥405,000");
  await expect(page.getByTestId("home-kpi-funding-value")).toHaveClass(/text-brand-600/);
  await expect(page.getByTestId("home-kpi-funding-note")).toHaveText(fund.note);
  if (fund.status_text) await expect(page.getByTestId("home-kpi-funding-status")).toHaveText(fund.status_text);
  // The second sentence is behind the cell's info control, not on the page.
  const pop = page.getByTestId("hv2-metric-funding-pop");
  await expect(pop).toBeHidden();
  await page.getByTestId("hv2-metric-funding-info").click();
  await expect(pop).toBeVisible();
  await expect(pop).toHaveText(fund.hint);
  await page.keyboard.press("Escape");
  await expect(pop).toBeHidden();
  // A scale, not a progress bar.
  await expect(page.getByTestId("home-buffer-min")).toBeAttached();
  await expect(page.getByTestId("home-buffer-cash")).toBeAttached();
  await expect(page.getByRole("progressbar")).toHaveCount(0);
});

test("the recommendation: the server's facts, the plan's control is the one filled button, 'Compare funding options' an outline", async ({ page }) => {
  await open(page, { offer: true });
  const a = homeOffer.en.home_v2.action;
  await expect(page.getByTestId("home-action-eyebrow")).toHaveText("What we recommend");
  await expect(page.getByTestId("home-action-title")).toHaveText(a.title);
  const facts = a.facts ?? [];
  if (facts.length === 3) {
    // The cost is the hero fact (the server's value, under its own label), the funding the server's sentence until it sends the legs, who approves one quiet line under the actions.
    const dl = page.getByTestId("hv2-action-facts");
    await expect(dl).toContainText("Cost to you");
    await expect(page.getByTestId("hv2-hero-value")).toHaveText(facts[0].value);
    expect(await page.getByTestId("hv2-hero-value").evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBe(28);
    await expect(page.getByTestId("hv2-hero-value")).toHaveCSS("border-bottom-width", "2px");
    await expect(page.getByTestId("hv2-funding-text")).toContainText(facts[1].value);
    const approval = page.getByTestId("hv2-approval");
    await expect(approval).toHaveText(facts[2].value);
    expect(await approval.evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(13);
    expect((await approval.boundingBox())!.y).toBeGreaterThan((await page.getByTestId("next-action-alternatives").boundingBox())!.y);
    await expect(page.getByTestId("home-action-text")).toHaveText(homeOffer.en.cash.headline_note);
  } else await expect(page.getByTestId("home-action-text")).toHaveText(a.text);
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
  await expect(page.getByTestId("next-action-alternatives")).toHaveText("Compare funding options");
  await expect(page.getByTestId("next-action-alternatives")).toHaveAttribute("href", a.secondary.href);
  expect(await filledBrand(page)).toBe(1);
  // The two presses of the older Home: ask, then run exactly that; cancel returns.
  await page.getByTestId(`fix-open-${ALERT}`).click();
  await expect(page.getByTestId(`fix-confirm-${ALERT}`)).toBeVisible();
  await page.getByTestId(`fix-cancel-${ALERT}`).click();
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
});

// The plan's legs are the server's `action.legs[]` (a batch the server is adding): until it is recorded, the spec lays a leg list over the recorded read through the mock's patch key.
const LEGS = {
  en: [
    { label: "Bank credit line", amount_display: "¥150k", lands_when: "today", cost_display: "¥840.00", repaid_when: "in 32 days", state: "planned", state_text: "planned", authority_text: "No approval needed", lands_day: 0, amount_fen: 15000000 },
    { label: "Invoice financing", amount_display: "¥255k", lands_when: "in 3 days", cost_display: "¥2,272.29", repaid_when: "in 32 days", state: "planned", state_text: "planned", authority_text: "No approval needed", lands_day: 3, amount_fen: 25500000 },
  ],
  zh: [
    { label: "银行信用额度", amount_display: "¥150k", lands_when: "今天", cost_display: "¥840.00", repaid_when: "32 天后", state: "planned", state_text: "计划中", authority_text: "无需批准", lands_day: 0, amount_fen: 15000000 },
    { label: "发票融资", amount_display: "¥255k", lands_when: "3 天后", cost_display: "¥2,272.29", repaid_when: "32 天后", state: "planned", state_text: "计划中", authority_text: "无需批准", lands_day: 3, amount_fen: 25500000 },
  ],
};

test("the funding as a timeline when the server sends the legs: one marker per leg with its source and amount, the total at the right, a card with the leg's words on hover and focus; still one filled button", async ({ page }) => {
  const v2 = { ...homeOffer.en.home_v2, action: { ...homeOffer.en.home_v2.action, legs: LEGS.en } };
  await page.context().addInitScript(([patch]) => sessionStorage.setItem("tl-mock-home-patch", JSON.stringify({ home_v2: patch })), [v2] as const);
  await open(page, { offer: true });
  const line = page.getByTestId("hv2-timeline");
  await expect(line).toBeVisible();
  await expect(page.getByTestId("hv2-funding-text")).toHaveCount(0);
  await expect(line).toHaveAttribute("data-legs", "2");
  for (const [i, leg] of LEGS.en.entries()) {
    await expect(page.getByTestId(`hv2-leg-${i}`)).toContainText(leg.label);
    await expect(page.getByTestId(`hv2-leg-${i}`)).toContainText(leg.amount_display);
    await expect(page.getByTestId(`hv2-leg-${i}`)).toHaveAttribute("data-state", "planned");
  }
  // Sized by amount, the larger leg's marker is the larger.
  const sizes = await Promise.all([0, 1].map(async (i) => (await page.getByTestId(`hv2-leg-dot-${i}`).boundingBox())!.width));
  expect(sizes[1]).toBeGreaterThan(sizes[0]);
  expect(sizes[1]).toBeLessThanOrEqual(18);
  expect(Math.min(...sizes)).toBeGreaterThanOrEqual(10);
  // Placed by the day the leg lands: the later leg is to the right of the earlier one.
  const xs = await Promise.all([0, 1].map(async (i) => (await page.getByTestId(`hv2-leg-marker-${i}`).boundingBox())!.x));
  expect(xs[1]).toBeGreaterThan(xs[0]);
  await expect(page.getByTestId("hv2-timeline-total")).toHaveText(v2.kpis.funding.value_display);
  // Hovering a marker opens its card (the leg's own words), leaving closes it; focus does the same; Escape closes it.
  const card = page.getByTestId("hv2-leg-card-1");
  await expect(card).toBeHidden();
  await page.getByTestId("hv2-leg-marker-1").hover();
  await expect(card).toBeVisible();
  for (const w of [LEGS.en[1].label, LEGS.en[1].amount_display, LEGS.en[1].lands_when, LEGS.en[1].cost_display, LEGS.en[1].repaid_when, LEGS.en[1].authority_text]) await expect(card).toContainText(w);
  await page.mouse.move(5, 5);
  await expect(card).toBeHidden();
  await page.getByTestId("hv2-leg-marker-0").focus();
  await expect(page.getByTestId("hv2-leg-card-0")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("hv2-leg-card-0")).toBeHidden();
  expect(await filledBrand(page)).toBe(1);
  await expect(page.getByTestId("hv2-approval")).toHaveText(homeOffer.en.home_v2.action.facts![2].value);
});

test("the legs on a phone are stacked rows that open on a tap; in Chinese they are the server's words", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const v2 = { ...homeOffer.zh.home_v2, action: { ...homeOffer.zh.home_v2.action, legs: LEGS.zh } };
  await page.context().addInitScript(([patch]) => sessionStorage.setItem("tl-mock-home-patch", JSON.stringify({ home_v2: patch })), [v2] as const);
  await open(page, { lang: "zh", offer: true });
  const rows = page.getByTestId("hv2-timeline-rows");
  await expect(rows).toBeVisible();
  for (const [i, leg] of LEGS.zh.entries()) {
    const row = page.getByTestId(`hv2-leg-row-${i}`);
    await expect(row).toContainText(leg.label);
    await expect(row).toContainText(leg.amount_display);
  }
  const first = page.getByTestId("hv2-leg-row-0");
  await expect(first.getByTestId("hv2-leg-cost")).toBeHidden();
  await first.locator("summary").click();
  await expect(first.getByTestId("hv2-leg-cost")).toContainText(LEGS.zh[0].cost_display);
  await expect(first.getByTestId("hv2-leg-lands")).toContainText(LEGS.zh[0].lands_when);
  await expect(first.getByTestId("hv2-leg-authority")).toContainText(LEGS.zh[0].authority_text);
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
  expect(await filledBrand(page)).toBe(1);
});

test("running the plan: no alert, the arranged funding, the quiet recommendation with no filled button, the financing on the worklist", async ({ page }) => {
  await open(page, { offer: true });
  await expect(page.getByTestId("home-worklist-alert")).toBeVisible();
  await page.getByTestId(`fix-open-${ALERT}`).click();
  await page.getByTestId(`fix-${ALERT}`).click();
  const v2 = homeAfter.en.home_v2;
  await expect(page.getByTestId("home-kpi-funding-value")).toHaveText(v2.kpis.funding.value_display);
  await expect(page.getByTestId("home-kpi-funding-note")).toHaveText(v2.kpis.funding.note);
  await expect(page.getByTestId("hv2-metric-funding-pop")).toHaveText(v2.kpis.funding.hint);
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "quiet");
  await expect(page.getByTestId("home-action-title")).toHaveText(v2.action.title);
  await expect(page.getByTestId("home-worklist-alert")).toHaveCount(0);
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toHaveCount(0);
  expect(await filledBrand(page)).toBe(0);
  await page.getByTestId("home-tab-waiting").click();
  const row = worklistAfter.en.waiting[0];
  const rows = page.getByTestId("home-worklist-row");
  await expect(rows).toHaveCount(1);
  await expect(rows).toContainText(row.subject_text);
  await expect(rows).toContainText(row.status_text);
  await expect(rows).toContainText(row.consequence_text);
  await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveText("0");
  await expect(page.getByTestId("home-tab-waiting-badge")).toHaveText("1");
});

test("the company cash forecast: the legend, the reserve, the plan conditional on execution, the compact window, the fixed inspector, one link", async ({ page }) => {
  await open(page, { offer: true });
  const chart = homeOffer.en.home_v2.chart;
  const cash = homeOffer.en.cash;
  await expect(page.getByRole("heading", { name: "Company cash forecast" })).toBeVisible();
  await expect(page.getByTestId("home-legend-current")).toHaveCount(0);
  const legend = page.getByTestId("home-legend");
  await expect(legend).toContainText(chart.legend[0].label);
  await expect(legend).toContainText("Below minimum reserve");
  await expect(legend).toContainText(chart.legend[1].label);
  await expect(legend).toContainText("conditional on execution");
  await expect(legend).toContainText(`Minimum cash reserve ${cash.floor_short}`);
  await expect(page.getByTestId("home-line-plan")).toBeAttached();
  await expect(page.getByTestId("home-line-counter")).toHaveClass(/stroke-ink-3/);
  await expect(page.getByTestId("hv2-below-base")).toBeAttached();
  await expect(page.getByTestId("hv2-danger")).toBeAttached();
  await expect(page.getByTestId("home-reserve")).toHaveClass(/stroke-chart-reserve/);
  await expect(page.getByTestId("picture-ytick")).toHaveCount(3);
  await expect(page.getByTestId("home-lowest-mark")).toBeAttached();
  // No rail, no numbered marks, no second chart link: the one link is the timeline.
  await expect(page.getByTestId("home-rail")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Compare cash outcomes/ })).toHaveCount(0);
  await expect(page.getByTestId("home-chart-full")).toHaveAttribute("href", "/cash");
  // The window: three words in a compact control (32 px, none with an icon).
  const windows = page.getByRole("tablist", { name: "Days shown" }).getByRole("tab");
  await expect(windows).toHaveCount(3);
  expect((await page.getByRole("tablist", { name: "Days shown" }).boundingBox())!.height).toBeLessThanOrEqual(34);
  await expect(page.getByTestId("hv2-chart")).toBeVisible();
  await page.getByTestId("home-window-120").click();
  await expect(page.getByTestId("home-window-120").locator("svg")).toHaveCount(0);
  await page.getByTestId("home-window-36").click();
  // The strip opens on the lowest point and says it in the server's words; it is under the chart, not over the line.
  const insp = chart.lowest_inspector;
  const strip = page.getByTestId("hv2-inspector");
  await expect(strip).toHaveAttribute("data-day", String(cash.lowest_day));
  await expect(page.getByTestId("hv2-inspector-when")).toContainText(insp.day_text);
  await expect(page.getByTestId("hv2-inspector-projected")).toContainText(insp.projected_display);
  await expect(page.getByTestId("hv2-inspector-gap")).toContainText(insp.third_display);
  await expect(page.getByTestId("hv2-inspector-gap")).toContainText(insp.third_label);
  await expect(page.getByTestId("hv2-inspector-plan")).toContainText("300,000");
  if (chart.lowest?.cause) await expect(page.getByTestId("hv2-inspector-events")).toContainText(chart.lowest.cause);
  await expect(page.getByTestId("hv2-inspector-events")).toContainText("On that day,");
  await expect(page.getByTestId("hv2-inspector-note")).toHaveText(insp.note);
  const frame = (await page.getByTestId("home-chart").boundingBox())!;
  expect((await strip.boundingBox())!.y).toBeGreaterThanOrEqual(frame.y + frame.height - 1);
  // The guide snaps to the days the server names: the arrow keys move it, and the strip moves with it.
  await page.getByTestId("home-chart").focus();
  await page.keyboard.press("ArrowLeft");
  await expect(strip).not.toHaveAttribute("data-day", String(cash.lowest_day));
  await expect(page.getByTestId("hv2-inspector-minimum")).toContainText(insp.minimum_display);
  await page.getByTestId("home-lowest-point").click();
  await expect(strip).toHaveAttribute("data-day", String(cash.lowest_day));
  // Pointing at the plot previews a day.
  const box = (await page.getByTestId("home-chart").boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5);
  await expect(strip).not.toHaveAttribute("data-day", String(cash.lowest_day));
  await page.mouse.move(5, 5);
  await expect(strip).toHaveAttribute("data-day", String(cash.lowest_day));
});

test("the worklist as an inbox: one alert line, tabs with counts, three-line rows with a severity word, the first row's reason is in its focus", async ({ page }) => {
  await open(page, { offer: true });
  const w = worklistOffer.en;
  await expect(page.getByTestId("hv2-worklist-title")).toHaveText("Your worklist");
  const alert = page.getByTestId("home-worklist-alert");
  await expect(alert).toContainText(w.alert.text);
  await expect(alert).toContainText(w.alert.eyebrow);
  await expect(page.getByTestId("home-worklist-alert-go")).toContainText(w.alert.primary.label);
  await expect(alert).toHaveClass(/border-l-2/);
  await expect(alert).not.toHaveClass(/bg-bad/);
  const note = page.getByTestId("home-worklist-alert-note");
  await expect(alert).toHaveAttribute("aria-describedby", (await note.getAttribute("id")) ?? "");
  expect(((await note.boundingBox())?.width ?? 0) <= 1).toBe(true);
  // The alert is one line of the pane: its sentence does not take more than two lines.
  expect((await alert.boundingBox())!.height).toBeLessThan(120);
  // Tabs: the count beside the label, neutral; a tab's hint is its title, not a line on the page.
  expect(w.counts.needs_you).toBe(w.needs_you.length);
  await expect(page.getByTestId("home-tab-needs_you")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("home-tab-needs_you")).toContainText("Needs you");
  await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveText(String(w.counts.needs_you));
  await expect(page.getByTestId("home-tab-waiting-badge")).toHaveText(String(w.counts.waiting));
  await expect(page.getByTestId("home-tab-customers-badge")).toHaveText(String(w.counts.customers));
  await expect(page.getByTestId("home-tab-needs_you")).toHaveAttribute("title", /./);
  await expect(page.getByTestId("home-worklist-hint")).toHaveCount(0);
  const rows = page.getByTestId("home-worklist-row");
  await expect(rows).toHaveCount(w.needs_you.length);
  await expect(rows.first()).toContainText(w.needs_you[0].subject_text);
  await expect(rows.first()).toContainText(w.needs_you[0].status_text);
  await expect(rows.first()).toContainText(w.needs_you[0].consequence_text);
  await expect(rows.first().getByTestId("home-row-severity")).toHaveAttribute("data-severity", w.needs_you[0].severity);
  await expect(page.getByTestId("home-why-first")).toHaveCount(0);
  await expect(page.getByTestId("home-worklist-all")).toHaveText(/^All deals/);
  // Waiting is empty in words; Customers lists one row per buyer.
  await page.getByTestId("home-tab-waiting").click();
  await expect(page.getByTestId("home-worklist-empty")).toContainText("All caught up.");
  await page.getByTestId("home-tab-customers").click();
  await expect(rows).toHaveCount(w.customers.length);
  await expect(rows.first()).toContainText(w.customers[0].name);
  await expect(rows.first()).toContainText(w.customers[0].detail_text);
  await expect(page.getByTestId("home-worklist-all")).toHaveText(/^All customers/);
  // The arrow keys move between the tabs.
  await page.getByTestId("home-tab-customers").focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByTestId("home-tab-waiting")).toHaveAttribute("aria-selected", "true");
});

test("search narrows the rows already fetched, by the customers' search terms", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  const rows = page.getByTestId("home-worklist-row");
  await expect(rows).toHaveCount(customersOffer.en.customers.length);
  const search = page.getByTestId("home-worklist-search");
  await search.fill("dongguan");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("Dongguan");
  await expect(page.getByTestId("home-worklist-found")).toHaveText("1 shown");
  await search.fill("zzz");
  await expect(page.getByTestId("home-worklist-empty")).toContainText("zzz");
  await search.fill("");
  await expect(rows).toHaveCount(customersOffer.en.customers.length);
  await page.getByTestId("home-tab-needs_you").click();
  await search.fill("foshan home retail");
  await expect(rows).toHaveCount(1);
  await search.fill("dongguan");
  await expect(page.getByTestId("home-worklist-empty")).toBeVisible();
});

test("day 0 with nothing open: Needs you is empty in words and the customers are listed", async ({ page }) => {
  await open(page);
  await expect(page.getByTestId("home-worklist-alert")).toContainText(worklistDay0.en.alert.text);
  await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveText("0");
  await expect(page.getByTestId("home-worklist-empty")).toContainText("All caught up.");
  await expect(page.getByTestId("home-kpi-funding-value")).toHaveText(homeDay0.en.home_v2.kpis.funding.value_display);
});

const focusOffer = focusOfferRec as unknown as Record<Lang, { customers: Record<string, FocusView>; deals: Record<string, FocusView> }>;
const exposure = exposureRec as unknown as Record<Lang, { paths: { key: string; kind: string; label: string; lowest_display?: string; lowest_when?: string; lowest_when_text?: string; limit_text?: string; limit_word?: string }[]; stress: { delay_days: number; paths: Record<string, { lowest_short: string; lowest_when: string; text: string; breach_days_text?: string } | null> } }>;
interface PicPath {
  key: string;
  kind: string;
  label: string;
  recommended: boolean;
  tag_text: string;
  authority_text?: string;
  authority_reason_text?: string | null;
  cost_total_display?: string | null;
  cost_once_display?: string | null;
  cost_forward_display?: string | null;
  cost_basis_text?: string | null;
  cost_components?: { label: string; display: string }[];
  reply_text?: string | null;
  cost_note: string;
  cost_display: string;
}
const pictures = pictureRec as unknown as Record<Lang, { paths: PicPath[] }>;
interface FocusView {
  name: string;
  figures: { key: string; label: string; value_display: string; note: string; state?: string; state_text?: string }[];
  decision: { eyebrow: string; text: string; headline_short?: string; authority_text?: string; primary: { label: string; href: string } } | null;
  context: { back: { href: string }; deal: string | null; scenario: string | null };
}
const DECISION = worklistOffer.en.needs_you[0].key; // deal:OFF-…
const SUBJECT = { en: worklistOffer.en.needs_you[0].subject_text, zh: worklistOffer.zh.needs_you[0].subject_text };
const DEAL = `/?customer=BUYER-1&decision=${encodeURIComponent(DECISION)}`;
const query = (page: Page) => new URL(page.url()).searchParams;

test("a customer row opens the customer in place: the address is the selection, the overview's figures and state words, the open rows, the alert stays as the band", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page).toHaveURL(/\/\?customer=BUYER-1$/);
  const view = focusOffer.en.customers["BUYER-1"];
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await expect(page.getByTestId("focus-title")).toHaveText(view.name);
  await expect(page.getByTestId("focus-announce")).toHaveText(view.name);
  for (const f of view.figures) {
    await expect(page.getByTestId(`focus-figure-${f.key}-value`)).toHaveText(f.value_display);
    if (f.state && f.state !== "none") await expect(page.getByTestId(`focus-figure-${f.key}-state`)).toHaveText(f.state_text!);
  }
  await expect(page.getByTestId("focus-rows").getByTestId("home-worklist-row")).toHaveCount(1);
  await expect(page.getByTestId("focus-open-customer")).toHaveAttribute("href", "/customers/BUYER-1");
  // The company is still on the page: the strip as it was, the alert pinned, the health band with an OUTLINED button, no filled button anywhere, no second chart.
  await expect(page.getByTestId("home-kpi-lowest-value")).toHaveText("−¥105,000");
  await expect(page.getByTestId("home-worklist-alert")).toBeVisible();
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "held");
  await expect(page.getByTestId("hv2-band")).toBeVisible();
  await expect(page.getByTestId("home-action-back")).toHaveText("Review funding plan");
  await expect(page.getByTestId("home-chart")).toHaveCount(0);
  expect(await filledBrand(page)).toBe(0);
  await page.getByTestId("home-tab-customers").click();
  await expect(page.getByTestId("home-worklist-panel").getByTestId("home-worklist-row").first().getByRole("link")).toHaveAttribute("aria-current", "true");
});

test("Escape, 'All business' and the band's button clear the selection and the plan's control returns", async ({ page }) => {
  await open(page, { offer: true });
  await page.goto("/?customer=BUYER-1");
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("home-customer-focus")).toHaveCount(0);
  await expect(page.getByTestId("home-chart")).toBeVisible();
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
  await page.goto("/?customer=BUYER-1");
  await page.getByTestId("focus-all").click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/?customer=BUYER-1");
  await page.getByTestId("home-action-back").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
});

test("a decision row opens the deal in place: level 1 the decision, level 2 the consequence; nothing else until it is asked for", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`customer=BUYER-1&decision=${encodeURIComponent(DECISION)}$`));
  const view = focusOffer.en.deals.none;
  const d = view.decision!;
  const pic = pictures.en.paths;
  const rec = pic.find((p) => p.recommended)!;
  const asked = pic.find((p) => p.kind === "asked")!;
  await expect(page.getByTestId("home-deal-focus")).toBeVisible();
  await expect(page.getByTestId("deal-eyebrow")).toHaveText(worklistOffer.en.needs_you[0].status_text);
  await expect(page.getByTestId("focus-title")).toHaveText(SUBJECT.en);
  await expect(page.getByTestId("focus-announce")).toHaveText(SUBJECT.en);
  await expect(page.getByTestId("hv2-customer-line")).toContainText(view.name);
  await expect(page.getByTestId("focus-open-customer")).toHaveAttribute("href", /\/customers\/BUYER-1\?decision=/);
  await expect(page.getByTestId("deal-ask")).toContainText("early settlement");
  await expect(page.getByTestId("home-why-first")).toHaveText(worklistOffer.en.needs_you[0].why_first_text!);
  // FLOW's recommendation with its own sentence and its cost; the request's cost with its basis.
  await expect(page.getByTestId("deal-recommends")).toHaveText(`FLOW recommends ${rec.label}`);
  await expect(page.getByTestId("hv2-recommendation")).toContainText(rec.reply_text!);
  await expect(page.getByTestId("queue-cost")).toContainText(rec.cost_once_display!);
  await expect(page.getByTestId("deal-request-cost")).toContainText(asked.cost_forward_display!);
  await expect(page.getByTestId("deal-request-cost")).toContainText(asked.cost_note);
  // The one filled button on the page is the deal's (the same control Deals uses); the others are outlined; the health band's too.
  await expect(page.getByTestId("deal-primary")).toHaveText(d.primary.label);
  await expect(page.getByTestId("deal-primary")).toHaveAttribute("href", d.primary.href);
  expect(await filledBrand(page)).toBe(1);
  await expect(page.getByTestId("hv2-band")).toBeVisible();
  await expect(page.getByTestId("home-action-back")).toHaveText("Review funding plan");
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toHaveCount(0);
  await expect(page.getByTestId("hv2-compare-toggle")).toHaveText("Compare responses");
  await expect(page.getByTestId("hv2-chart-toggle")).toHaveText("Cash impact");
  await expect(page.getByTestId("deal-open")).toHaveAttribute("href", /\/deals\?customer=BUYER-1&decision=/);
  // Level 2: the payment-timing assumption and one table, the request against the recommended option, with the four rows.
  await expect(page.getByText("Payment timing assumption")).toBeVisible();
  await expect(page.getByText("Changes the lowest projected cash below and the cash chart.")).toBeVisible();
  const table = page.getByTestId("hv2-consequence-table");
  await expect(table.locator("tbody tr")).toHaveCount(4);
  const ex = exposure.en.paths;
  await expect(table.getByTestId("hv2-consequence-row-lowest")).toContainText(ex.find((p) => p.kind === "asked")!.lowest_display!);
  await expect(table.getByTestId("hv2-consequence-row-lowest")).toContainText(ex.find((p) => p.key === rec.key)!.lowest_display!);
  await expect(table.getByTestId("hv2-consequence-row-reserve")).toContainText(ex.find((p) => p.kind === "asked")!.lowest_when_text!);
  await expect(table.getByTestId("hv2-consequence-row-limits")).toContainText(/exceeded/i);
  await expect(table.getByTestId("hv2-consequence-row-limits")).toContainText(/within/i);
  await expect(table.getByTestId("hv2-consequence-row-approval")).toContainText(asked.authority_text!);
  await expect(table.getByTestId("hv2-consequence-row-approval")).toContainText(rec.authority_text!);
  // Level 3 is not on the page: no full table, no why, no deal chart.
  await expect(page.getByTestId("hv2-compare")).toHaveCount(0);
  await expect(page.getByTestId("hv2-deal-chart")).toHaveCount(0);
  await expect(page.getByTestId("home-chart")).toHaveCount(0);
});

test("Compare responses expands the full table and FLOW's reasons in place, and again collapses them; focus stays on the toggle and the page does not jump", async ({ page }) => {
  await open(page, { offer: true });
  await page.goto(DEAL);
  const toggle = page.getByTestId("hv2-compare-toggle");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.scrollIntoViewIfNeeded();
  const before = await page.evaluate(() => window.scrollY);
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(toggle).toBeFocused();
  expect(await page.evaluate(() => window.scrollY)).toBe(before);
  await expect(page).toHaveURL(/compare=1/);
  const pic = pictures.en.paths;
  const table = page.getByTestId("hv2-compare-table-table");
  await expect(table.locator("thead th")).toHaveCount(pic.length + 1);
  for (const p of pic) await expect(table.locator("thead")).toContainText(p.label);
  // The economic impact is each path's own words with their basis: the request on two lines, a reply's total with its basis, B's components.
  const asked = pic.find((p) => p.kind === "asked")!;
  const a = pic.find((p) => p.recommended)!;
  const b = pic.find((p) => p.kind === "reply" && !p.recommended)!;
  const econ = table.getByTestId("hv2-compare-table-row-economics");
  await expect(econ).toContainText(asked.cost_forward_display!);
  await expect(econ).toContainText(asked.cost_once_display!);
  await expect(econ).toContainText(asked.cost_basis_text!);
  await expect(econ).toContainText(a.cost_total_display!);
  await expect(econ).toContainText(a.cost_basis_text!);
  for (const c of b.cost_components ?? []) {
    await expect(econ).toContainText(c.label);
    await expect(econ).toContainText(c.display);
  }
  // Option B's header carries its authority evidence; the why lines are the server's words.
  await expect(table.locator("thead")).toContainText(b.authority_reason_text!);
  const why = page.getByTestId("hv2-why");
  await expect(why).toContainText(`Why FLOW recommends ${a.label}`);
  await expect(why).toContainText(a.authority_reason_text!);
  await expect(why).toContainText(b.authority_reason_text!);
  // The limit and the approval are two rows, so a reply can be within limits and still need approval.
  await expect(table.getByTestId("hv2-compare-table-row-limits")).toBeVisible();
  await expect(table.getByTestId("hv2-compare-table-row-approval")).toContainText(b.authority_text!);
  expect(await filledBrand(page)).toBe(1);
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByTestId("hv2-compare")).toHaveCount(0);
  await expect(page).not.toHaveURL(/compare=1/);
  await expect(toggle).toBeFocused();
});

test("Cash impact expands the deal's chart: the option solid, the request grey with its stretches under the reserve in red, a same-day inspector; and collapses", async ({ page }) => {
  await open(page, { offer: true });
  await page.goto(DEAL);
  const toggle = page.getByTestId("hv2-chart-toggle");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(page).toHaveURL(/chart=1/);
  const chart = page.getByTestId("hv2-deal-chart");
  await expect(chart).toBeVisible();
  const pic = pictures.en.paths;
  await expect(chart.getByTestId("home-line-option")).toHaveClass(/stroke-brand-600/);
  await expect(chart.getByTestId("home-line-request")).toHaveClass(/stroke-ink-3/);
  await expect(chart.getByTestId("hv2-below-request")).toBeAttached();
  await expect(chart.getByTestId("home-legend")).toContainText(pic.find((p) => p.kind === "asked")!.label);
  await expect(chart.getByTestId("home-legend")).toContainText(pic.find((p) => p.recommended)!.label);
  // The inspector is a same-day comparison and says so; it never says a day number.
  await expect(chart.getByTestId("hv2-inspector-note")).toContainText("same day");
  await expect(chart.getByTestId("hv2-inspector-request")).toBeVisible();
  await expect(chart.getByTestId("hv2-inspector-option")).toBeVisible();
  const when = await chart.getByTestId("hv2-inspector-when").innerText();
  expect(when).not.toMatch(/\bday\s+\d/i);
  await toggle.click();
  await expect(page.getByTestId("hv2-deal-chart")).toHaveCount(0);
  await expect(page).not.toHaveURL(/chart=1/);
});

test("the payment-timing assumption switches the rows, the table and the chart from the one read, and the address keeps it", async ({ page }) => {
  await open(page, { offer: true });
  await page.goto(DEAL);
  const panel = page.getByTestId("deal-scenario-panel");
  await expect(panel).toHaveAttribute("data-scenario", "current");
  const ex = exposure.en;
  const asked = pictures.en.paths.find((p) => p.kind === "asked")!;
  const rec = pictures.en.paths.find((p) => p.recommended)!;
  await expect(page.getByTestId("deal-scenario-current")).toHaveText("Expected payments");
  await expect(page.getByTestId("deal-scenario-late")).toHaveText(`Foshan ${ex.stress.delay_days} days late`);
  await page.getByTestId("deal-scenario-late").click();
  await expect(page).toHaveURL(/timing=late/);
  await expect(panel).toHaveAttribute("data-scenario", "late");
  const s = ex.stress.paths[asked.key]!;
  await expect(panel.getByTestId("hv2-consequence-row-lowest")).toContainText(s.lowest_short);
  await expect(panel.getByTestId("hv2-consequence-row-lowest")).toContainText(s.lowest_when);
  await expect(panel.getByTestId("hv2-consequence-row-reserve")).toContainText(s.breach_days_text ?? s.text);
  await expect(panel.getByTestId("hv2-consequence-row-reserve")).toContainText(ex.stress.paths[rec.key]!.breach_days_text ?? ex.stress.paths[rec.key]!.text);
  // The same assumption in the full table and in the chart's subtitle.
  await page.getByTestId("hv2-compare-toggle").click();
  await expect(page.getByTestId("hv2-compare-table-row-lowest")).toContainText(s.lowest_short);
  await page.getByTestId("hv2-chart-toggle").click();
  await expect(page).toHaveURL(/compare=1&chart=1&timing=late/);
  await page.reload();
  await expect(page.getByTestId("deal-scenario-late")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("hv2-compare")).toBeVisible();
  await expect(page.getByTestId("hv2-deal-chart")).toBeVisible();
  await page.getByTestId("deal-scenario-current").click();
  await expect(page).not.toHaveURL(/timing=/);
  await expect(page.getByTestId("deal-scenario-panel")).toHaveAttribute("data-scenario", "current");
});

test("back and forward restore the selections, a reload keeps them, and a decision that is not open says so", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.getByTestId("focus-rows").getByRole("link").click();
  await expect(page.getByTestId("home-deal-focus")).toBeVisible();
  await page.getByTestId("deal-scenario-late").click();
  await expect(page.getByTestId("deal-scenario-panel")).toHaveAttribute("data-scenario", "late");
  // The assumption replaced the entry (no history of its own): back goes to the customer, back again to the company.
  await page.goBack();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  expect(query(page).get("decision")).toBeNull();
  await page.goBack();
  await expect(page.getByTestId("home-customer-focus")).toHaveCount(0);
  await expect(page.getByTestId("home-chart")).toBeVisible();
  await page.goForward();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.goForward();
  await expect(page.getByTestId("home-deal-focus")).toBeVisible();
  await expect(page.getByTestId("deal-scenario-panel")).toHaveAttribute("data-scenario", "late");
  await page.reload();
  await expect(page.getByTestId("home-deal-focus")).toBeVisible();
  await expect(page.getByTestId("deal-scenario-late")).toHaveAttribute("aria-selected", "true");
  await page.goto("/?customer=BUYER-2&decision=deal%3AOFF-nope");
  await expect(page.getByTestId("home-deal-gone")).toBeVisible();
  expect(await page.evaluate(() => Object.keys(localStorage).filter((k) => /customer|decision|scenario|compare/i.test(k)))).toEqual([]);
});

test("nothing in Business mode is an id, a code or a day number; every figure and its qualifier is at least 13 px", async ({ page }) => {
  await open(page, { offer: true });
  const prose = await proseOf(page);
  expect(prose).not.toMatch(/\bday\s+\d/i);
  expect(prose).not.toMatch(/BUYER-\d|OFF-[0-9a-f]|ALERT-|deal:|NEEDS_YOU|CRITICAL|PROPOSED/);
  for (const url of ["/", DEAL + "&compare=1&chart=1"]) {
    await page.goto(url);
    await expect(page.getByTestId("home-v2")).toBeVisible();
    const small = await page.evaluate(() => {
      const root = document.querySelector('[data-testid="home-v2"]')!;
      const out: string[] = [];
      for (const el of Array.from(root.querySelectorAll("main *, [data-testid=home-v2] *"))) {
        if (el.children.length) continue;
        const text = (el.textContent ?? "").trim();
        if (!text || !/[0-9¥%]|[a-zA-Z]/.test(text)) continue;
        const style = getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") continue;
        if (el.closest(".sr-only") || el.closest("[hidden]")) continue;
        if (parseFloat(style.fontSize) < 13) out.push(`${text.slice(0, 40)} ${style.fontSize}`);
      }
      return out;
    });
    expect(small).toEqual([]);
  }
});

test("zh parity: the strip, the recommendation, the worklist and the deal in Chinese, the server's words as recorded", async ({ page }) => {
  await open(page, { lang: "zh", offer: true });
  const v2 = homeOffer.zh.home_v2;
  await expect(page.getByTestId("hv2-page-name")).toHaveText("首页");
  await expect(page.getByTestId("home-read-when")).toHaveText("今天更新");
  await expect(page.getByTestId("hv2-metric-cash-label")).toHaveText("现金余额");
  await expect(page.getByTestId("home-kpi-lowest-note")).toHaveText(v2.kpis.lowest_ahead.short_note ?? v2.kpis.lowest_ahead.note);
  await expect(page.getByTestId("home-kpi-funding-note")).toHaveText(v2.kpis.funding.note);
  await page.getByTestId("hv2-metric-funding-info").click();
  await expect(page.getByTestId("hv2-metric-funding-pop")).toHaveText(v2.kpis.funding.hint);
  await expect(page.getByTestId("home-action-title")).toHaveText(v2.action.title);
  await expect(page.getByTestId("home-action-eyebrow")).toHaveText("我们的建议");
  await expect(page.getByTestId("hv2-inspector-note")).toHaveText(v2.chart.lowest_inspector.note);
  await expect(page.getByTestId("home-legend")).toContainText("取决于方案执行");
  const w = worklistOffer.zh;
  await expect(page.getByTestId("home-worklist-alert")).toContainText(w.alert.text);
  await expect(page.getByTestId("home-worklist-row").first()).toContainText(w.needs_you[0].subject_text);
  await expect(page.getByTestId("home-worklist-search")).toHaveAttribute("placeholder", "搜索客户或交易");
  await expect(page.getByTestId("home-tab-waiting")).toContainText("等待中");
  await page.goto(DEAL + "&compare=1");
  const pic = pictures.zh.paths;
  await expect(page.getByTestId("focus-title")).toHaveText(SUBJECT.zh);
  await expect(page.getByTestId("deal-primary")).toHaveText(focusOffer.zh.deals.none.decision!.primary.label);
  await expect(page.getByTestId("hv2-compare-toggle")).toHaveText("比较各个答复");
  await expect(page.getByTestId("deal-recommends")).toHaveText(`FLOW 建议${pic.find((p) => p.recommended)!.label}`);
  await expect(page.getByTestId("hv2-compare-table-table").locator("thead")).toContainText(pic.find((p) => p.kind === "reply" && !p.recommended)!.authority_reason_text!);
  await expect(page.getByTestId("deal-scenario-late")).toContainText("晚付");
  await page.goto("/?customer=BUYER-1");
  const customer = focusOffer.zh.customers["BUYER-1"];
  await expect(page.getByTestId("focus-title")).toHaveText(customer.name);
  for (const f of customer.figures) if (f.state && f.state !== "none") await expect(page.getByTestId(`focus-figure-${f.key}-state`)).toHaveText(f.state_text!);
  await expect(page.getByTestId("home-action-back")).toHaveText("查看融资方案");
});

test("phone: the strip with the cash cell across, the recommendation and its primary in the first viewport, the worklist in a sheet that returns focus", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { offer: true });
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
  // The cash cell is a row of its own, the other two share the next one.
  const box = async (id: string) => (await page.getByTestId(`hv2-metric-${id}`).boundingBox())!;
  const [cash, lowest, funding] = [await box("cash"), await box("lowest"), await box("funding")];
  expect(cash.width).toBeGreaterThan(lowest.width * 1.6);
  expect(lowest.y).toBeGreaterThan(cash.y);
  expect(Math.abs(lowest.y - funding.y)).toBeLessThan(4);
  // The primary is in the first viewport, above the bottom tab bar, at a 390 x 844 and a 375 x 812 phone.
  for (const [w, h] of [[390, 844], [375, 812]] as const) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto("/");
    await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
    const primary = (await page.getByTestId(`fix-open-${ALERT}`).boundingBox())!;
    const tabBar = (await page.getByTestId("tab-bar").boundingBox())!;
    expect(primary.y + primary.height, `inside the first ${h} px`).toBeLessThanOrEqual(h);
    expect(primary.y + primary.height, "and not behind the tab bar").toBeLessThanOrEqual(tabBar.y);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByTestId("home-v2-worklist")).toHaveCount(0);
  const opener = page.getByTestId("home-worklist-open");
  await expect(opener).toHaveText(`Worklist (${worklistOffer.en.counts.needs_you})`);
  await opener.scrollIntoViewIfNeeded();
  await opener.click();
  const sheet = page.getByTestId("home-worklist-sheet");
  await expect(sheet).toBeVisible();
  await expect(sheet.getByTestId("home-tab-needs_you")).toBeVisible();
  await expect(sheet.getByTestId("home-worklist-row")).toHaveCount(1);
  await sheet.getByTestId("home-tab-customers").click();
  await expect(sheet.getByTestId("home-worklist-row")).toHaveCount(2);
  for (let i = 0; i < 12; i++) await page.keyboard.press("Tab");
  expect(await page.evaluate(() => Boolean(document.activeElement?.closest("dialog")))).toBe(true);
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(opener).toBeFocused();
  await opener.click();
  await sheet.getByTestId("home-worklist-close").click();
  await expect(sheet).toBeHidden();
  await expect(opener).toBeFocused();
  await opener.click();
  await sheet.getByTestId("home-worklist-alert-go").click();
  await expect(sheet).toBeHidden();
  await expect(page.getByTestId("home-v2-action")).toBeInViewport();
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
});

test("phone: a row in the sheet closes it and the deal opens under the recommendation's band; the table stacks; nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { offer: true });
  await page.getByTestId("home-worklist-open").click();
  await page.getByTestId("home-worklist-sheet").getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("home-worklist-sheet")).toBeHidden();
  await expect(page.getByTestId("home-deal-focus")).toBeVisible();
  await expect(page).toHaveURL(/decision=/);
  const band = (await page.getByTestId("home-v2-action").boundingBox())!;
  const panel = (await page.getByTestId("home-deal-focus").boundingBox())!;
  expect(panel.y).toBeGreaterThan(band.y);
  await expect(page.getByTestId("deal-primary")).toBeVisible();
  expect(await filledBrand(page)).toBe(1);
  await page.getByTestId("hv2-compare-toggle").click();
  await expect(page.getByTestId("hv2-compare-table-stack")).toBeVisible();
  await expect(page.getByTestId("hv2-compare-table-scroll")).toBeHidden();
  await page.getByTestId("hv2-chart-toggle").click();
  await expect(page.getByTestId("hv2-deal-chart")).toBeVisible();
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
});

test("1280: the table keeps its columns and scrolls before it crushes; the page does not scroll sideways", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await open(page, { offer: true });
  await page.goto(DEAL + "&compare=1");
  await expect(page.getByTestId("hv2-compare-table-table")).toBeVisible();
  const scroll = page.getByTestId("hv2-compare-table-scroll");
  const dims = await scroll.evaluate((el) => ({ sw: el.scrollWidth, cw: el.clientWidth }));
  expect(dims.sw).toBeGreaterThanOrEqual(600);
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
  expect(await filledBrand(page)).toBe(1);
});

test("reduced motion: the inspector, a selection and the underline arrive without an animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page, { offer: true });
  await page.goto("/?customer=BUYER-1");
  const panel = page.getByTestId("home-customer-focus").locator(".motion-swap");
  await expect(panel).toBeVisible();
  const ms = await panel.evaluate((el) => parseFloat(getComputedStyle(el).animationDuration) * 1000);
  const name = await panel.evaluate((el) => getComputedStyle(el).animationName);
  expect(name === "none" || ms <= 1).toBe(true);
});

test("accessibility: no axe violations on the default Home, with the customer and with the deal open (compared, with its chart), at 1440 and at 390", async ({ page }) => {
  await open(page, { offer: true });
  for (const url of ["/", "/?customer=BUYER-1", `${DEAL}&compare=1&chart=1`]) {
    await page.goto(url);
    await expect(page.getByTestId("home-v2")).toBeVisible();
    await expect(page.getByTestId("deal-working")).toHaveCount(0);
    const found = await new AxeBuilder({ page }).analyze();
    expect(found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByTestId("home-v2")).toBeVisible();
    const phone = await new AxeBuilder({ page }).analyze();
    expect(phone.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
    await page.setViewportSize({ width: 1440, height: 900 });
  }
  await page.goto("/");
  await page.getByTestId("hv2-metric-funding-info").click();
  const open_ = await new AxeBuilder({ page }).analyze();
  expect(open_.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
});
