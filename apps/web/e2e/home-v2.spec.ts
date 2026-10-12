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
import customersOffer from "../mocks/home_v2/customers_offer.json";

/**
 * Home V2, wave 2 (the web page behind the server's FEATURE_HOME_V2): the header, the company strip, the action bar, the compact company cash chart, the link row and
 * the worklist (a column from `xl`, a bottom sheet on a phone).
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
  await page.context().addInitScript(
    ([v2]) => sessionStorage.setItem("tl-mock-home-patch", JSON.stringify({ home_v2: v2 })),
    [homeDay0.en.home_v2] as const,
  );
  await open(page, { flag: false });
  await expect(page.getByTestId("home-headline")).toHaveText(day0.cash.headline_conditional);
  await expect(page.getByTestId("home-v2")).toHaveCount(0);
});

test("day 0, before the plan runs: the header and the three KPI strings are the read's", async ({ page }) => {
  await open(page, { offer: true });
  const v2 = homeOffer.en.home_v2;
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Home");
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.getByTestId("home-status-word")).toHaveText(homeOffer.en.cash.status_word);
  await expect(page.getByTestId("home-read-when")).toHaveText("Read today");
  for (const [id, k] of [["cash", v2.kpis.cash_available], ["lowest", v2.kpis.lowest_ahead], ["funding", v2.kpis.funding]] as const) {
    await expect(page.getByTestId(`home-kpi-${id}-eyebrow`)).toHaveText(k.eyebrow);
    await expect(page.getByTestId(`home-kpi-${id}-value`)).toHaveText(k.value_display);
    await expect(page.getByTestId(`home-kpi-${id}-note`)).toHaveText(k.note);
  }
  await expect(page.getByTestId("home-kpi-lowest-value")).toHaveText("−¥105,000");
  await expect(page.getByTestId("home-kpi-lowest-note")).toContainText("current books, no new funding");
  await expect(page.getByTestId("home-kpi-lowest-value")).toHaveClass(/text-bad-fg/);
  await expect(page.getByTestId("home-kpi-funding-eyebrow")).toHaveText("PLANNED FUNDING");
  await expect(page.getByTestId("home-kpi-funding-value")).toHaveText("¥405,000");
  // Each cell is its eyebrow, its figure and one note line: the second sentence is not on the page until it is asked for (hover or focus; a tap on a phone).
  for (const [id, text] of [["lowest", v2.kpis.lowest_ahead.with_plan_hint], ["funding", v2.kpis.funding.hint]] as const) {
    const cell = page.getByTestId(`home-kpi-${id}`);
    const hint = page.getByTestId(`home-kpi-${id}-hint`);
    await expect(hint).toHaveText(text);
    await expect(hint).toBeHidden();
    await expect(cell).toHaveAttribute("aria-describedby", (await hint.getAttribute("id")) ?? "");
    await cell.hover();
    await expect(hint).toBeVisible();
    await page.mouse.move(5, 5);
    await expect(hint).toBeHidden();
    await cell.focus();
    await expect(hint).toBeVisible();
    await cell.blur();
  }
  // The colours are the meanings': the planned funding wears the planned state's dashed ring and blue; the lowest figure is red below the minimum; the cash is green above it.
  await expect(page.getByTestId("home-kpi-funding-value")).toHaveClass(/text-info-fg/);
  await expect(page.getByTestId("home-kpi-funding").locator("svg").first()).toHaveClass(/text-info-solid/);
  await expect(page.getByTestId("home-kpi-cash-value")).toHaveClass(/text-ok-fg/);
  // The buffer scale places the minimum and today's cash; it is a scale, not a progress bar.
  await expect(page.getByTestId("home-buffer-min")).toBeAttached();
  await expect(page.getByTestId("home-buffer-cash")).toBeAttached();
  await expect(page.getByRole("progressbar")).toHaveCount(0);
});

test("the action bar: the run-the-plan control is the one filled primary and the one decision card; Compare is the secondary", async ({ page }) => {
  await open(page, { offer: true });
  const a = homeOffer.en.home_v2.action;
  await expect(page.getByTestId("home-action-eyebrow")).toHaveText(a.eyebrow);
  await expect(page.getByTestId("home-action-title")).toHaveText(a.title);
  await expect(page.getByTestId("home-action-text")).toHaveText(a.text);
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
  await expect(page.getByTestId("next-action-alternatives")).toHaveText(a.secondary.label);
  await expect(page.getByTestId("next-action-alternatives")).toHaveAttribute("href", a.secondary.href);
  expect(await filledBrand(page)).toBe(1);
  await expect(page.locator(".card-decision")).toHaveCount(1);
  // The same two presses as the older Home: ask, then run exactly that; cancel returns.
  await page.getByTestId(`fix-open-${ALERT}`).click();
  await expect(page.getByTestId(`fix-confirm-${ALERT}`)).toBeVisible();
  await page.getByTestId(`fix-cancel-${ALERT}`).click();
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
});

test("running the plan: no alert, FUNDING ARRANGED, the quiet action with no filled primary, and the financing waits on the worklist", async ({ page }) => {
  await open(page, { offer: true });
  await expect(page.getByTestId("home-worklist-alert")).toBeVisible();
  await page.getByTestId(`fix-open-${ALERT}`).click();
  await page.getByTestId(`fix-${ALERT}`).click();
  const v2 = homeAfter.en.home_v2;
  await expect(page.getByTestId("home-kpi-funding-eyebrow")).toHaveText(v2.kpis.funding.eyebrow);
  await expect(page.getByTestId("home-kpi-funding-eyebrow")).toHaveText("FUNDING ARRANGED");
  await expect(page.getByTestId("home-kpi-funding-value")).toHaveText(v2.kpis.funding.value_display);
  await expect(page.getByTestId("home-kpi-funding-hint")).toHaveText(v2.kpis.funding.hint);
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "quiet");
  await expect(page.getByTestId("home-action-title")).toHaveText(v2.action.title);
  await expect(page.getByTestId("home-worklist-alert")).toHaveCount(0);
  await expect(page.getByTestId("fix-open-" + ALERT)).toHaveCount(0);
  expect(await filledBrand(page)).toBe(0);
  await expect(page.locator(".card-decision")).toHaveCount(0);
  // Waiting holds the financing that has not landed: not cash, and not a decision.
  await page.getByTestId("home-tab-waiting").click();
  const row = worklistAfter.en.waiting[0];
  await expect(page.getByTestId("home-worklist-row")).toHaveCount(1);
  await expect(page.getByTestId("home-worklist-row")).toContainText(row.subject_text);
  await expect(page.getByTestId("home-worklist-row")).toContainText(row.status_text);
  await expect(page.getByTestId("home-worklist-row")).toContainText(row.consequence_text);
  await expect(page.getByTestId("home-tab-needs_you")).toContainText("0");
  // The counts sit beside the labels as badges: nothing needs the owner, so Needs you's is neutral, and every other badge is neutral too.
  await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveText("0");
  await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveAttribute("data-tone", "neutral");
  await expect(page.getByTestId("home-tab-waiting-badge")).toHaveText("1");
});

test("the chart: the legend, the minimum, the plan as the grey dashed comparator, and the window word", async ({ page }) => {
  await open(page, { offer: true });
  const chart = homeOffer.en.home_v2.chart;
  await expect(page.getByTestId("home-chart-scope")).toHaveText(chart.scope_title);
  await expect(page.getByTestId("home-legend-current")).toHaveText(chart.legend[0].label);
  await expect(page.getByTestId("home-legend-planned")).toHaveText(chart.legend[1].label);
  await expect(page.getByTestId("home-line-plan")).toBeAttached();
  await expect(page.getByTestId("home-line-counter")).toHaveClass(/stroke-ink-3/);
  await expect(page.getByTestId("home-reserve")).toBeAttached();
  await expect(page.getByTestId("home-lowest-mark")).toBeAttached();
  // No event rail and no numbered marks here: they live in Cash & Funding.
  await expect(page.getByTestId("home-rail")).toHaveCount(0);
  await expect(page.getByTestId("rail-mark-0")).toHaveCount(0);
  await expect(page.getByTestId("home-lowest-cause")).toHaveText(/payment|repayment|goes out/i);
  await expect(page.getByTestId("home-chart-note")).toHaveText(chart.note);
  await expect(page.getByTestId("home-chart-full")).toHaveAttribute("href", "/cash");
  // The window: three words as tabs, none with an icon; choosing one widens the picture.
  const windows = page.getByRole("tablist", { name: "Days shown" }).getByRole("tab");
  await expect(windows).toHaveCount(3);
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-window", "36");
  await page.getByTestId("home-window-120").click();
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-window", "120");
  await expect(page.getByTestId("home-window-120").locator("svg")).toHaveCount(0);
  // Hovering the plot shows each line's figure.
  const box = (await page.getByTestId("home-chart").boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.4);
  await expect(page.getByTestId("home-tooltip")).toBeVisible();
});

test("the lowest point opens the inspector with its four rows; Escape closes it and returns focus", async ({ page }) => {
  await open(page, { offer: true });
  const insp = homeOffer.en.home_v2.chart.lowest_inspector;
  await expect(page.getByTestId("home-inspector")).toHaveCount(0);
  const point = page.getByTestId("home-lowest-point");
  await expect(point).toHaveAttribute("aria-expanded", "false");
  await point.click();
  await expect(point).toHaveAttribute("aria-expanded", "true");
  const rows = page.getByTestId("home-inspector-row");
  await expect(rows).toHaveCount(4);
  await expect(page.getByTestId("home-inspector-title")).toHaveText(insp.day_text);
  await expect(rows.nth(0)).toContainText(insp.projected_display);
  await expect(rows.nth(1)).toContainText(insp.minimum_display);
  await expect(rows.nth(2)).toContainText(insp.third_label);
  await expect(rows.nth(2)).toContainText(insp.third_display);
  await expect(rows.nth(3)).toHaveText(insp.note);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("home-inspector")).toHaveCount(0);
  await expect(point).toBeFocused();
  // The keyboard reaches it and opens it.
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("home-inspector")).toBeVisible();
});

test("the worklist: the alert pinned and counted nowhere, the counts equal the rows, three tabs with their counts beside them, the first row says why it is first", async ({ page }) => {
  await open(page, { offer: true });
  const w = worklistOffer.en;
  await expect(page.getByTestId("home-worklist-alert")).toContainText(w.alert.text);
  await expect(page.getByTestId("home-worklist-alert")).toContainText(w.alert.eyebrow);
  await expect(page.getByTestId("home-worklist-alert-go")).toContainText(w.alert.primary.label);
  // Not a red box: a quiet card with a left rule. Its explanation is the card's description for a reader who asks, and is not text on the page.
  await expect(page.getByTestId("home-worklist-alert")).toHaveClass(/border-l-/);
  await expect(page.getByTestId("home-worklist-alert")).not.toHaveClass(/bg-bad/);
  const note = page.getByTestId("home-worklist-alert-note");
  await expect(page.getByTestId("home-worklist-alert")).toHaveAttribute("aria-describedby", (await note.getAttribute("id")) ?? "");
  expect(((await note.boundingBox())?.width ?? 0) <= 1).toBe(true);
  await expect(note).toHaveText("An alert, not a queue item: it is counted nowhere below.");
  // Needs you: the badge is the read's count and equals the rows; the alert is not one of them.
  expect(w.counts.needs_you).toBe(w.needs_you.length);
  await expect(page.getByTestId("home-tab-needs_you")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveText(String(w.counts.needs_you));
  const rows = page.getByTestId("home-worklist-row");
  await expect(rows).toHaveCount(w.needs_you.length);
  await expect(rows.first()).toContainText(w.needs_you[0].subject_text);
  await expect(rows.first()).toContainText(w.needs_you[0].status_text);
  await expect(rows.first()).toContainText(w.needs_you[0].consequence_text);
  await expect(page.getByTestId("home-why-first")).toHaveText(w.needs_you[0].why_first_text);
  await expect(rows.first().getByTestId("home-row-severity")).toHaveAttribute("data-severity", w.needs_you[0].severity);
  await expect(page.getByTestId("home-worklist-all")).toHaveText(/^All deals/);
  // Waiting: nothing yet, said in words.
  await page.getByTestId("home-tab-waiting").click();
  await expect(page.getByTestId("home-tab-waiting")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("home-worklist-empty")).toBeVisible();
  // Customers: one row per buyer.
  await page.getByTestId("home-tab-customers").click();
  await expect(rows).toHaveCount(w.customers.length);
  await expect(rows.first()).toContainText(w.customers[0].name);
  await expect(rows.first()).toContainText(w.customers[0].status_text);
  await expect(rows.first()).toContainText(w.customers[0].detail_text);
  await expect(page.getByTestId("home-worklist-all")).toHaveText(/^All customers/);
  // The counts: red on Needs you while something needs the owner, neutral on the others, beside the labels and not under them.
  await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveAttribute("data-tone", "alert");
  await expect(page.getByTestId("home-tab-waiting-badge")).toHaveText(String(w.counts.waiting));
  await expect(page.getByTestId("home-tab-waiting-badge")).toHaveAttribute("data-tone", "neutral");
  await expect(page.getByTestId("home-tab-customers-badge")).toHaveText(String(w.counts.customers));
  await expect(page.getByTestId("home-worklist-hint")).toHaveCount(0);
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
  // The same box filters Needs you by the buyer's name.
  await page.getByTestId("home-tab-needs_you").click();
  await search.fill("foshan home retail");
  await expect(rows).toHaveCount(1);
  await search.fill("dongguan");
  await expect(page.getByTestId("home-worklist-empty")).toBeVisible();
});

test("day 0 with nothing open: Needs you is empty in words and the customers are listed", async ({ page }) => {
  await open(page);
  await expect(page.getByTestId("home-worklist-alert")).toContainText(worklistDay0.en.alert.text);
  await expect(page.getByTestId("home-tab-needs_you")).toContainText("0");
  await expect(page.getByTestId("home-worklist-empty")).toBeVisible();
  await expect(page.getByTestId("home-kpi-funding-value")).toHaveText(homeDay0.en.home_v2.kpis.funding.value_display);
});

test("nothing in Business mode is an id, a code or a day number; every figure is at least 13 px", async ({ page }) => {
  await open(page, { offer: true });
  const prose = await proseOf(page);
  expect(prose).not.toMatch(/\bday\s+\d/i);
  expect(prose).not.toMatch(/BUYER-\d|OFF-[0-9a-f]|ALERT-|deal:|NEEDS_YOU|CRITICAL|PROPOSED/);
  const small = await page.evaluate(() => {
    const root = document.querySelector('[data-testid="home-v2"]')!;
    const out: string[] = [];
    for (const id of ["home-kpi-cash-value", "home-kpi-cash-note", "home-kpi-lowest-note", "home-kpi-lowest-hint", "home-kpi-funding-note", "home-action-text", "home-chart-note", "home-lowest-cause"]) {
      const el = root.querySelector(`[data-testid="${id}"]`);
      if (el && parseFloat(getComputedStyle(el).fontSize) < 13) out.push(id);
    }
    for (const t of Array.from(root.querySelectorAll("svg text"))) if (parseFloat(getComputedStyle(t).fontSize) < 13) out.push(t.textContent ?? "svg text");
    return out;
  });
  expect(small).toEqual([]);
});

test("zh parity: every KPI, the action, the legend, the inspector and the worklist are the Chinese read's", async ({ page }) => {
  await open(page, { lang: "zh", offer: true });
  const v2 = homeOffer.zh.home_v2;
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("首页");
  await expect(page.getByTestId("home-read-when")).toHaveText("今天读取");
  await expect(page.getByTestId("home-kpi-cash-eyebrow")).toHaveText(v2.kpis.cash_available.eyebrow);
  await expect(page.getByTestId("home-kpi-lowest-note")).toHaveText(v2.kpis.lowest_ahead.note);
  await expect(page.getByTestId("home-kpi-funding-eyebrow")).toHaveText(v2.kpis.funding.eyebrow);
  await expect(page.getByTestId("home-kpi-funding-hint")).toHaveText(v2.kpis.funding.hint);
  await expect(page.getByTestId("home-action-title")).toHaveText(v2.action.title);
  await expect(page.getByTestId("home-legend-planned")).toHaveText(v2.chart.legend[1].label);
  await page.getByTestId("home-lowest-point").click();
  await expect(page.getByTestId("home-inspector-row").nth(3)).toHaveText(v2.chart.lowest_inspector.note);
  const w = worklistOffer.zh;
  await expect(page.getByTestId("home-worklist-alert")).toContainText(w.alert.text);
  await expect(page.getByTestId("home-worklist-row").first()).toContainText(w.needs_you[0].subject_text);
  await expect(page.getByTestId("home-why-first")).toHaveText(w.needs_you[0].why_first_text);
  await expect(page.getByTestId("home-worklist-search")).toHaveAttribute("placeholder", "搜索客户或交易");
  await expect(page.getByTestId("home-tab-waiting")).toContainText("等待中");
  await expect(page.getByTestId("home-worklist-all")).toContainText("全部交易");
  // After the plan, in Chinese too.
  await page.getByTestId("home-lowest-point").click();
  await page.getByTestId(`fix-open-${ALERT}`).click();
  await page.getByTestId(`fix-${ALERT}`).click();
  await expect(page.getByTestId("home-kpi-funding-eyebrow")).toHaveText(homeAfter.zh.home_v2.kpis.funding.eyebrow);
});

test("phone: the strip as rows, the action and its primary in the first viewport, the worklist in a sheet that returns focus", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { offer: true });
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
  // The three KPIs are rows, one under the other, each its eyebrow, figure and note: the second sentence is not on the page until a tap asks for it.
  const ys = await Promise.all(["cash", "lowest", "funding"].map(async (k) => (await page.getByTestId(`home-kpi-${k}`).boundingBox())!.y));
  expect(ys[0]).toBeLessThan(ys[1]);
  expect(ys[1]).toBeLessThan(ys[2]);
  await expect(page.getByTestId("home-kpi-funding-hint")).toBeHidden();
  await page.getByTestId("home-kpi-funding").click();
  await expect(page.getByTestId("home-kpi-funding-hint")).toBeVisible();
  await page.getByTestId("home-kpi-funding").click();
  await page.mouse.move(5, 5);
  await expect(page.getByTestId("home-kpi-funding-hint")).toBeHidden();
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
  // No side panel on a phone: a button with the count opens the sheet.
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
  // Focus is held inside the sheet: Tab never leaves it.
  for (let i = 0; i < 12; i++) await page.keyboard.press("Tab");
  expect(await page.evaluate(() => Boolean(document.activeElement?.closest("dialog")))).toBe(true);
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(opener).toBeFocused();
  // The close button does the same.
  await opener.click();
  await sheet.getByTestId("home-worklist-close").click();
  await expect(sheet).toBeHidden();
  await expect(opener).toBeFocused();
  // The alert's "Run or compare" closes the sheet and takes the owner to the action.
  await opener.click();
  await sheet.getByTestId("home-worklist-alert-go").click();
  await expect(sheet).toBeHidden();
  await expect(page.getByTestId("home-v2-action")).toBeInViewport();
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
});

test("reduced motion: the inspector arrives without an animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page, { offer: true });
  await page.getByTestId("home-lowest-point").click();
  const name = await page.getByTestId("home-inspector").evaluate((el) => getComputedStyle(el).animationName);
  const ms = await page.getByTestId("home-inspector").evaluate((el) => parseFloat(getComputedStyle(el).animationDuration) * 1000);
  expect(name === "none" || ms <= 1).toBe(true);
});

test("accessibility: no axe violations at 1440 (the inspector open) and at 390 (the sheet open)", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-lowest-point").click();
  const desktop = await new AxeBuilder({ page }).analyze();
  expect(desktop.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByTestId("home-worklist-open")).toBeVisible();
  const phone = await new AxeBuilder({ page }).analyze();
  expect(phone.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
  await page.getByTestId("home-worklist-open").click();
  await expect(page.getByTestId("home-worklist-sheet")).toBeVisible();
  const sheet = await new AxeBuilder({ page }).analyze();
  expect(sheet.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
});

// ---------------------------------------------------------------- slice 2: the customer and the decision, in place

const exposure = exposureRec as unknown as Record<Lang, { paths: { key: string; kind: string; label: string; lowest_display?: string; lowest_when_text?: string; limit_text?: string; share_after_text?: string }[] }>;
const focusOffer = focusOfferRec as unknown as Record<Lang, { customers: Record<string, FocusView>; deals: Record<string, FocusView> }>;
interface FocusView {
  name: string;
  figures: { key: string; label: string; value_display: string; note: string; state?: string; state_text?: string }[];
  decision: { eyebrow: string; text: string; headline_short?: string; authority_text?: string; primary: { label: string; href: string } } | null;
  context: { back: { href: string }; deal: string | null; scenario: string | null };
}
const DECISION = worklistOffer.en.needs_you[0].key; // deal:OFF-…
const DEAL = `/?customer=BUYER-1&decision=${encodeURIComponent(DECISION)}`;
const query = (page: Page) => new URL(page.url()).searchParams;

test("a customer row opens the customer in place: the address is the selection, the overview's figures and state words, the open rows, the alert stays", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page).toHaveURL(/\/\?customer=BUYER-1$/);
  const view = focusOffer.en.customers["BUYER-1"];
  const focus = page.getByTestId("home-customer-focus");
  await expect(focus).toBeVisible();
  await expect(page.getByTestId("focus-title")).toHaveText(view.name);
  await expect(page.getByTestId("focus-announce")).toHaveText(view.name);
  for (const f of view.figures) {
    await expect(page.getByTestId(`focus-figure-${f.key}-value`)).toHaveText(f.value_display);
    if (f.state && f.state !== "none") await expect(page.getByTestId(`focus-figure-${f.key}-state`)).toHaveText(f.state_text!);
  }
  // The open rows are the worklist's own rows for this customer; the decision opens in place from them too.
  await expect(page.getByTestId("focus-rows").getByTestId("home-worklist-row")).toHaveCount(1);
  await expect(page.getByTestId("focus-open-customer")).toHaveAttribute("href", "/customers/BUYER-1");
  // The company is still on the page: the strip as it was, the alert pinned, the action's warning (held, no filled button), and no second chart under the panel.
  await expect(page.getByTestId("home-kpi-lowest-value")).toHaveText("−¥105,000");
  await expect(page.getByTestId("home-worklist-alert")).toBeVisible();
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "held");
  await expect(page.getByTestId("home-action-back")).toBeVisible();
  await expect(page.getByTestId("home-chart")).toHaveCount(0);
  expect(await filledBrand(page)).toBe(0);
  await expect(page.locator(".card-decision")).toHaveCount(0);
  // The selected row says so.
  await page.getByTestId("home-tab-customers").click();
  await expect(page.getByTestId("home-worklist-panel").getByTestId("home-worklist-row").first().getByRole("link")).toHaveAttribute("aria-current", "true");
});

test("Escape, the cross and 'All business' clear the selection; 'Back to the action' too, and the plan's control returns", async ({ page }) => {
  await open(page, { offer: true });
  await page.goto("/?customer=BUYER-1");
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("home-customer-focus")).toHaveCount(0);
  await expect(page.getByTestId("home-chart")).toBeVisible();
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
  await page.goto("/?customer=BUYER-1");
  await page.getByTestId("focus-close").click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/?customer=BUYER-1");
  await page.getByTestId("focus-all").click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/?customer=BUYER-1");
  await page.getByTestId("home-action-back").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
});

test("a decision row opens the deal in place: the server's action as the one filled primary, the paths, the scenario in the address, the figures from one read", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`customer=BUYER-1&decision=${encodeURIComponent(DECISION).replace(/%/g, "%")}$`));
  const view = focusOffer.en.deals.none;
  const d = view.decision!;
  await expect(page.getByTestId("home-deal-focus")).toBeVisible();
  await expect(page.getByTestId("deal-eyebrow")).toHaveText(d.eyebrow);
  await expect(page.getByTestId("focus-title")).toHaveText(d.headline_short!);
  await expect(page.getByTestId("deal-text")).toHaveText(d.text);
  await expect(page.getByTestId("deal-authority")).toHaveText(d.authority_text!);
  // The one filled primary on the page is the deal's; the company's action is held, quiet, and the plan's control is not on the page; one decision card.
  await expect(page.getByTestId("deal-primary")).toHaveText(d.primary.label);
  await expect(page.getByTestId("deal-primary")).toHaveAttribute("href", d.primary.href);
  await expect(page.getByTestId("deal-open")).toHaveAttribute("href", view.context.back.href);
  expect(await filledBrand(page)).toBe(1);
  await expect(page.locator(".card-decision")).toHaveCount(1);
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "held");
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toHaveCount(0);
  // The paths are the Deals page's own columns, in the server's order.
  await expect(page.getByTestId("path-columns")).toBeVisible();
  await expect(page.getByTestId("path-col-0")).toContainText("As they asked");
  await expect(page.getByTestId("path-col-1")).toContainText("Option A");
  // No scenario: the current books, said so; nothing is drawn as hypothetical.
  await expect(page.getByTestId("deal-current-note")).toBeVisible();
  await expect(page.getByTestId("home-legend-hypothetical")).toHaveCount(0);
  await expect(page.getByTestId("home-chart-scope")).toHaveText("Impact of Foshan's proposed terms");
  // The scenario: a tab, written to the address by replacing it, validated by the server, its figures the exposure read's words, its path the one dashed hypothetical line.
  await page.getByTestId("deal-scenario-counter:0").click();
  await expect(page).toHaveURL(/scenario=counter%3A0$/);
  await expect(page.getByTestId("deal-scenario-panel")).toHaveAttribute("data-scenario", "counter:0");
  const optionA = exposure.en.paths.find((p) => p.label === "Option A")!;
  await expect(page.getByTestId("deal-figure-lowest")).toContainText(optionA.lowest_display!);
  await expect(page.getByTestId("deal-figure-lowest")).toContainText(optionA.lowest_when_text!);
  await expect(page.getByTestId("deal-figure-limit")).toContainText(optionA.limit_text!);
  await expect(page.getByTestId("deal-figure-share")).toContainText(optionA.share_after_text!);
  await expect(page.getByTestId("home-legend-hypothetical")).toContainText("Option A");
  await expect(page.getByTestId("home-legend-hypothetical")).toContainText("Hypothetical");
  await expect(page.getByTestId("home-line-pending")).toBeAttached();
  await page.getByTestId("deal-scenario-asked").click();
  await expect(page.getByTestId("deal-scenario-panel")).toHaveAttribute("data-scenario", "asked");
  const asked = exposure.en.paths.find((p) => p.kind === "asked")!;
  await expect(page.getByTestId("deal-figure-lowest")).toContainText(asked.lowest_display!);
  // A column's own button picks the scenario too, and the company's figures never moved.
  await page.getByTestId("path-col-1").getByRole("radio").click();
  await expect(page).toHaveURL(/scenario=counter%3A0$/);
  await expect(page.getByTestId("home-kpi-lowest-value")).toHaveText("−¥105,000");
  await page.getByTestId("deal-scenario-current").click();
  await expect(page).not.toHaveURL(/scenario=/);
  await expect(page.getByTestId("deal-current-note")).toBeVisible();
  // The customer's name goes up one level; Escape clears everything.
  await page.getByTestId("focus-customer").click();
  await expect(page).toHaveURL(/\/\?customer=BUYER-1$/);
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
});

test("back and forward restore the selections, a reload keeps them, and a decision that is not open says so", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.getByTestId("focus-rows").getByRole("link").click();
  await expect(page.getByTestId("home-deal-focus")).toBeVisible();
  await page.getByTestId("deal-scenario-counter:0").click();
  await expect(page.getByTestId("deal-scenario-panel")).toHaveAttribute("data-scenario", "counter:0");
  // The scenario replaced the entry (no history of its own): back goes to the customer, back again to the company.
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
  await expect(page.getByTestId("deal-scenario-panel")).toHaveAttribute("data-scenario", "counter:0");
  await page.reload();
  await expect(page.getByTestId("home-deal-focus")).toBeVisible();
  await expect(page.getByTestId("deal-scenario-panel")).toHaveAttribute("data-scenario", "counter:0");
  await expect(page.getByTestId("deal-scenario-counter:0")).toHaveAttribute("aria-selected", "true");
  // A decision the server does not know for this customer is not shown as a deal.
  await page.goto("/?customer=BUYER-2&decision=deal%3AOFF-nope");
  await expect(page.getByTestId("home-deal-gone")).toBeVisible();
  // Nothing is kept in a store: the address alone held all of it.
  expect(await page.evaluate(() => Object.keys(localStorage).filter((k) => /customer|decision|scenario/i.test(k)))).toEqual([]);
});

test("the focus panels in Chinese: the overview's figures and state words, the decision, the scenario's figures", async ({ page }) => {
  await open(page, { lang: "zh", offer: true });
  await page.goto(DEAL);
  const view = focusOffer.zh.deals.none;
  await expect(page.getByTestId("focus-title")).toHaveText(view.decision!.headline_short!);
  await expect(page.getByTestId("deal-eyebrow")).toHaveText(view.decision!.eyebrow);
  await expect(page.getByTestId("deal-primary")).toHaveText(view.decision!.primary.label);
  await expect(page.getByTestId("deal-current-note")).toHaveText("当前账目，没有任何假设。选择一个情景，即可与之对比。");
  await page.getByTestId("deal-scenario-counter:0").click();
  const optionA = exposure.zh.paths.find((p) => p.kind === "reply")!;
  await expect(page.getByTestId("deal-figure-lowest")).toContainText(optionA.lowest_display!);
  await expect(page.getByTestId("home-legend-hypothetical")).toContainText("假设");
  await page.goto("/?customer=BUYER-1");
  const customer = focusOffer.zh.customers["BUYER-1"];
  await expect(page.getByTestId("focus-title")).toHaveText(customer.name);
  for (const f of customer.figures) if (f.state && f.state !== "none") await expect(page.getByTestId(`focus-figure-${f.key}-state`)).toHaveText(f.state_text!);
  await expect(page.getByTestId("home-action-back")).toHaveText("回到待办操作");
});

test("reduced motion: a selection replaces the panel without an animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page, { offer: true });
  await page.goto("/?customer=BUYER-1");
  const panel = page.getByTestId("home-customer-focus");
  await expect(panel).toBeVisible();
  const ms = await panel.evaluate((el) => parseFloat(getComputedStyle(el).animationDuration) * 1000);
  const name = await panel.evaluate((el) => getComputedStyle(el).animationName);
  expect(name === "none" || ms <= 1).toBe(true);
});

test("phone: a row in the sheet closes it and the panel opens under the action bar, the primary in the first viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { offer: true });
  await page.getByTestId("home-worklist-open").click();
  await page.getByTestId("home-worklist-sheet").getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("home-worklist-sheet")).toBeHidden();
  await expect(page.getByTestId("home-deal-focus")).toBeVisible();
  await expect(page).toHaveURL(/decision=/);
  // The panel sits under the action bar (held), nothing scrolls sideways, and the deal's primary is reachable.
  const bar = (await page.getByTestId("home-v2-action").boundingBox())!;
  const panel = (await page.getByTestId("home-focus").boundingBox())!;
  expect(panel.y).toBeGreaterThan(bar.y);
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
  await expect(page.getByTestId("deal-primary")).toBeVisible();
  expect(await filledBrand(page)).toBe(1);
  // Opening the deal from a fresh load puts the primary in the first viewport.
  await page.goto(DEAL);
  const primary = (await page.getByTestId("deal-primary").boundingBox())!;
  const tabBar = (await page.getByTestId("tab-bar").boundingBox())!;
  expect(primary.y + primary.height).toBeLessThanOrEqual(tabBar.y);
});

test("accessibility: no axe violations with the customer and with the deal open, at 1440 and at 390", async ({ page }) => {
  await open(page, { offer: true });
  for (const url of ["/?customer=BUYER-1", `${DEAL}&scenario=counter%3A0`]) {
    await page.goto(url);
    await expect(page.getByTestId("home-focus")).toBeVisible();
    await expect(page.getByTestId("deal-working")).toHaveCount(0);
    const found = await new AxeBuilder({ page }).analyze();
    expect(found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByTestId("home-focus")).toBeVisible();
    const phone = await new AxeBuilder({ page }).analyze();
    expect(phone.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
    await page.setViewportSize({ width: 1440, height: 900 });
  }
});
