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
    await expect(page.getByTestId("queue-heading")).toBeVisible();
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
  await expect(page.getByTestId("home-kpi-lowest-hint")).toHaveText(v2.kpis.lowest_ahead.with_plan_hint);
  await expect(page.getByTestId("home-kpi-funding-eyebrow")).toHaveText("PLANNED FUNDING");
  await expect(page.getByTestId("home-kpi-funding-value")).toHaveText("¥405,000");
  await expect(page.getByTestId("home-kpi-funding-hint")).toHaveText(v2.kpis.funding.hint);
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
  await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveCount(0);
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

test("the worklist: the alert pinned and counted nowhere, the counts equal the rows, three tabs, one hint each, the first row says why it is first", async ({ page }) => {
  await open(page, { offer: true });
  const w = worklistOffer.en;
  await expect(page.getByTestId("home-worklist-alert")).toContainText(w.alert.text);
  await expect(page.getByTestId("home-worklist-alert")).toContainText(w.alert.eyebrow);
  await expect(page.getByTestId("home-worklist-alert-go")).toContainText(w.alert.primary.label);
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
  const hints = new Set<string>();
  hints.add((await page.getByTestId("home-worklist-hint").textContent()) ?? "");
  await expect(page.getByTestId("home-worklist-all")).toHaveText(/^All deals/);
  // Waiting: nothing yet, said in words.
  await page.getByTestId("home-tab-waiting").click();
  await expect(page.getByTestId("home-tab-waiting")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("home-worklist-empty")).toBeVisible();
  hints.add((await page.getByTestId("home-worklist-hint").textContent()) ?? "");
  // Customers: one row per buyer; the badge belongs to Needs you only.
  await page.getByTestId("home-tab-customers").click();
  await expect(rows).toHaveCount(w.customers.length);
  await expect(rows.first()).toContainText(w.customers[0].name);
  await expect(rows.first()).toContainText(w.customers[0].status_text);
  await expect(rows.first()).toContainText(w.customers[0].detail_text);
  hints.add((await page.getByTestId("home-worklist-hint").textContent()) ?? "");
  expect(hints.size).toBe(3);
  await expect(page.getByTestId("home-worklist-all")).toHaveText(/^All customers/);
  await expect(page.getByTestId("home-tab-waiting-badge")).toHaveCount(0);
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

test("a row opens its workspace: a decision opens the deal, a customer opens the customer", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page).toHaveURL(/\/deals\?customer=BUYER-1&decision=deal%3AOFF-/);
  await page.goto("/");
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page).toHaveURL(/\/customers\/BUYER-1/);
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
    for (const id of ["home-kpi-cash-value", "home-kpi-cash-note", "home-kpi-lowest-note", "home-kpi-lowest-hint", "home-kpi-funding-note", "home-action-text", "home-chart-note", "home-lowest-cause", "home-worklist-hint"]) {
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
  // The three KPIs are rows, one under the other.
  const ys = await Promise.all(["cash", "lowest", "funding"].map(async (k) => (await page.getByTestId(`home-kpi-${k}`).boundingBox())!.y));
  expect(ys[0]).toBeLessThan(ys[1]);
  expect(ys[1]).toBeLessThan(ys[2]);
  // The primary is in the first viewport, above the bottom tab bar.
  const primary = (await page.getByTestId(`fix-open-${ALERT}`).boundingBox())!;
  expect(primary.y + primary.height).toBeLessThanOrEqual(844 - 56);
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
