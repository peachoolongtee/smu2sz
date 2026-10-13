import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, proseOf, test } from "./fixtures";
import { filledBrand } from "./helpers";
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
 * Home V2 (the Home), after the refinement: the header, the metric strip, the recommendation, the company cash forecast with its fixed
 * inspector, the link row and the worklist as an inbox (a pane from `xl`, a bottom sheet on a phone); a selected customer or deal in place, the deal in three levels.
 *
 * Every string below is read from the recordings (`mocks/home_v2/*.json`, `scripts/record-mocks.mjs --home-v2`): the words are the server's. The mock serves them always
 * (lib/mock/home-v2.ts), the story state choosing the opening books, the package offer read, or the books after the plan ran.
 * The "offer" state is the opening books with the package offer read by FLOW (the plan is still ready; Needs you holds the Foshan decision).
 */
const ALERT = "ALERT-RESERVE-12";
type Lang = "en" | "zh";

async function overflowX(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

/** The language is set before the page loads. With `offer`, the owner has FLOW read the package offer first (the Deals page), as the Deals spec does. */
async function open(page: Page, { lang = "en", offer = false }: { lang?: Lang; offer?: boolean } = {}) {
  await page.context().addInitScript(
    ([l]) => {
      localStorage.setItem("tl-lang", JSON.stringify({ lang: l }));
    },
    [lang] as const,
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
  await expect(page.getByTestId("home-v2")).toBeVisible();
  await expect(page.getByTestId("hv2-outlook-card")).toBeVisible();
}

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "mock-mode spec on the recorded story (the phone is measured inside it)");
});

test("the header and the three cards: the headline, the state pill, the cash card with the reserve bar, the outlook card with its mini chart", async ({ page }) => {
  await open(page, { offer: true });
  const h = homeOffer.en;
  const v2 = h.home_v2;
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.getByTestId("home-headline")).toHaveText(h.cash.headline_conditional);
  await expect(page.getByTestId("home-status-word")).toHaveText(h.cash.status_word);
  await expect(page.getByTestId("home-read-when")).toHaveText("Updated today");
  await expect(page.getByTestId("home-read-when")).toHaveAttribute("aria-label", "Read today");
  // The state pill is the alert's own kind word on the amber fill; the one-line summary is the server's (none until it sends it).
  const said = worklistOffer.en.alert as { kind_text?: string | null; eyebrow: string };
  await expect(page.getByTestId("hv2-state-pill")).toHaveText(said.kind_text ?? said.eyebrow);
  await expect(page.getByTestId("hv2-state-pill")).toHaveAttribute("data-tone", "amber");
  await expect(page.getByTestId("hv2-summary")).toHaveCount(0);
  // Cash available today: the figure, the server's note, the reserve bar (a track to the minimum and the buffer above it); not a progress bar.
  const cash = v2.kpis.cash_available;
  await expect(page.getByTestId("hv2-metric-cash-label")).toHaveText("Cash available today");
  await expect(page.getByTestId("home-kpi-cash-value")).toHaveText(cash.value_display);
  await expect(page.getByTestId("home-kpi-cash-note")).toHaveText(cash.note);
  await expect(page.getByTestId("home-buffer-min-text")).toContainText(cash.buffer.min_display);
  await expect(page.getByTestId("home-buffer-room-text")).toContainText(cash.buffer.headroom_text);
  await expect(page.getByTestId("home-buffer-bar")).toHaveAttribute("aria-label", cash.note);
  await expect(page.getByTestId("home-buffer-cash")).toBeAttached();
  await expect(page.getByRole("progressbar")).toHaveCount(0);
  // Company cash outlook: the lowest figure in the one risk red, "Without new funding", the mini step chart, the plan's cash, Expand.
  const low = v2.kpis.lowest_ahead;
  await expect(page.getByTestId("hv2-metric-lowest-label")).toHaveText("Company cash outlook");
  await expect(page.getByTestId("home-kpi-lowest-value")).toHaveText("−¥105,000");
  await expect(page.getByTestId("home-kpi-lowest-value")).toHaveClass(/text-bad-fg/);
  expect(await page.getByTestId("home-kpi-lowest-value").evaluate((n) => getComputedStyle(n).color)).toBe("rgb(168, 50, 34)");
  await expect(page.getByTestId("hv2-outlook-when")).toHaveText(new RegExp(`^${h.cash.lowest_when}$`, "i"));
  await expect(page.getByTestId("home-kpi-lowest-note")).toHaveText(low.short_note ?? low.note);
  await expect(page.getByTestId("hv2-mini-current")).toBeAttached();
  await expect(page.getByTestId("hv2-mini-plan")).toHaveAttribute("stroke-dasharray", /./);
  if (low.with_plan) await expect(page.getByTestId("home-kpi-lowest-plan")).toHaveText(new RegExp(`^${low.with_plan.label} ${low.with_plan.value_text}$`, "i"));
  await expect(page.getByTestId("hv2-outlook-expand")).toHaveAttribute("aria-expanded", "false");
  // The three cards sit in one row on a desktop.
  const tops = await Promise.all(["hv2-cash-card", "hv2-action", "hv2-outlook-card"].map(async (id) => Math.round((await page.getByTestId(id).boundingBox())!.y)));
  expect(Math.max(...tops) - Math.min(...tops)).toBeLessThan(4);
  await expect(page.getByTestId("hv2-plan-pill")).toHaveText(/^planned$/i);
});

test("the recommendation: the title, the planned amount, one line that reconciles with the outlook, the cost, the actions, then one approval line in both forms", async ({ page }) => {
  await open(page, { offer: true });
  const a = homeOffer.en.home_v2.action as typeof homeOffer.en.home_v2.action & { consequence_text?: string | null; approval_text?: string | null; approval_needed?: boolean };
  await expect(page.getByTestId("home-action-eyebrow")).toHaveText("What we recommend");
  await expect(page.getByTestId("home-action-title")).toHaveText(a.title);
  // One line, the server's when it sends it (the first breach day and the lowest point), else the Home read's note.
  await expect(page.getByTestId("home-action-text")).toHaveText(a.consequence_text ?? homeOffer.en.cash.headline_note);
  const facts = a.facts ?? [];
  expect(facts.length).toBe(3);
  // The planned amount is the figure; the cost to the owner is one line under it; the funding sentence is behind "Funding sources".
  await expect(page.getByTestId("hv2-plan-amount")).toHaveText(homeOffer.en.home_v2.kpis.funding.value_display);
  await expect(page.getByTestId("hv2-funding-hint")).toHaveText(homeOffer.en.home_v2.kpis.funding.hint);
  await expect(page.getByTestId("hv2-action-facts")).toContainText("Cost to you");
  await expect(page.getByTestId("hv2-hero-value")).toHaveText(facts[0].value);
  await expect(page.getByTestId("hv2-funding-fact")).toContainText(facts[1].value);
  await expect(page.getByTestId("hv2-funding-fact")).toContainText("Funding sources");
  // Who approves is the one line under the actions, not a fact.
  await expect(page.getByTestId("hv2-action-facts")).not.toContainText(facts[2].label);
  await expect(page.getByTestId("hv2-authority")).toHaveCount(0);
  await expect(page.getByTestId("hv2-timeline")).toHaveCount(0);
  await expect(page.getByTestId("hv2-funding-composition")).toHaveCount(0);
  // Approval is said once, as one 13 px line under the actions: with no approval needed the check glyph and the server's sentence in the quiet ink.
  const approval = page.getByTestId("hv2-approval");
  expect(a.approval_text).toBe("No approval needed");
  expect(a.approval_needed).toBe(false);
  await expect(approval).toHaveText(a.approval_text!);
  await expect(approval).toHaveAttribute("data-needs-owner", "false");
  await expect(approval.locator("svg")).toHaveCount(1);
  expect(await approval.evaluate((n) => parseFloat(getComputedStyle(n).fontSize))).toBe(13);
  expect(await approval.evaluate((n) => getComputedStyle(n).fontWeight)).not.toBe("600");
  const [actionsBox, lineBox] = await Promise.all([page.getByTestId("home-attention-run").boundingBox(), approval.boundingBox()]);
  expect(lineBox!.y).toBeGreaterThan(actionsBox!.y + actionsBox!.height - 1);
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
  await expect(page.getByTestId("next-action-alternatives")).toHaveText("Compare funding options");
  await expect(page.getByTestId("next-action-alternatives")).toHaveAttribute("href", a.secondary.href);
  expect(await filledBrand(page)).toBe(1);
  // The plan's two presses: ask, then run exactly that; cancel returns.
  await page.getByTestId(`fix-open-${ALERT}`).click();
  await expect(page.getByTestId(`fix-confirm-${ALERT}`)).toBeVisible();
  await page.getByTestId(`fix-cancel-${ALERT}`).click();
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
});

test("when the owner must approve, the same line is a warn-tone alert line with the server's approval sentence, still one line and no box", async ({ page }) => {
  // A temporary in-spec patch of the recorded read (no recording has a plan waiting on the owner while its control is on the page): the server's two fields as it sends them for an approval that waits.
  const sentence = "Needs your approval before it runs";
  const action = { ...homeOffer.en.home_v2.action, approval_text: sentence, approval_needed: true };
  await page.context().addInitScript(([key, patch]) => sessionStorage.setItem(key as string, JSON.stringify(patch)), ["tl-mock-home-patch", { home_v2: { ...homeOffer.en.home_v2, action } }] as const);
  await open(page, { offer: true });
  const approval = page.getByTestId("hv2-approval");
  await expect(approval).toHaveText(sentence);
  await expect(approval).toHaveAttribute("data-needs-owner", "true");
  await expect(approval.locator("svg")).toHaveCount(1);
  expect(await approval.evaluate((n) => parseFloat(getComputedStyle(n).fontSize))).toBe(13);
  expect(await approval.evaluate((n) => getComputedStyle(n).color)).not.toBe(await page.getByTestId("home-action-text").evaluate((n) => getComputedStyle(n).color));
  expect(await approval.evaluate((n) => getComputedStyle(n).backgroundColor)).toBe("rgba(0, 0, 0, 0)"); // a line, not a box
  expect((await approval.boundingBox())!.height).toBeLessThan(26);
  await expect(page.getByTestId("hv2-action-facts")).not.toContainText("Approval");
});

test("no approval line when the server sends no approval text (a card with no plan)", async ({ page }) => {
  const action = { ...homeOffer.en.home_v2.action, approval_text: null, approval_needed: false };
  await page.context().addInitScript(([key, patch]) => sessionStorage.setItem(key as string, JSON.stringify(patch)), ["tl-mock-home-patch", { home_v2: { ...homeOffer.en.home_v2, action } }] as const);
  await open(page, { offer: true });
  await expect(page.getByTestId("hv2-action")).toBeVisible();
  await expect(page.getByTestId("hv2-approval")).toHaveCount(0);
});

// A block the server could not read (a supporting read failed): the status stays, the page says so with Retry, and never shows an empty page. In-spec patches of the recorded read.
test("failed read: a home_v2 the server could not read leaves the status, the server's sentence and Retry, and no strip", async ({ page }) => {
  const text = "Part of the home page could not be read: the company forecast.";
  await page.context().addInitScript(([key, patch]) => sessionStorage.setItem(key as string, JSON.stringify(patch)), ["tl-mock-home-patch", { home_v2: null, partial: { missing: ["home_v2"], missing_text: ["the company forecast"], text } }] as const);
  await page.goto("/");
  await expect(page.getByTestId("home-v2")).toBeVisible();
  await expect(page.getByTestId("home-headline")).toHaveText(homeDay0.en.cash.headline_conditional || homeDay0.en.headline);
  await expect(page.getByTestId("partial-read")).toContainText(text);
  await expect(page.getByTestId("partial-retry")).toBeVisible();
  await expect(page.getByTestId("home-kpi-cash-value")).toHaveCount(0);
  await expect(page.getByTestId("home-chart")).toHaveCount(0);
  await expect(page.getByTestId("hv2-action")).toHaveCount(0);
  expect(await filledBrand(page)).toBe(0); // Retry is not a filled button
});

test("failed read: a home_v2 that is absent without a sentence says so in the dictionary's words, with Retry", async ({ page }) => {
  await page.context().addInitScript(([key, patch]) => sessionStorage.setItem(key as string, JSON.stringify(patch)), ["tl-mock-home-patch", { home_v2: null }] as const);
  await page.goto("/");
  await expect(page.getByTestId("home-v2")).toBeVisible();
  await expect(page.locator("main").getByRole("alert")).toContainText("This part of the home page could not be read");
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
  await expect(page.getByTestId("partial-read")).toHaveCount(0);
});

// The plan's legs are the server's `action.legs[]`, recorded with the rest of the read (`home_offer.json`).
type RecordedLeg = NonNullable<typeof homeOffer.en.home_v2.action.legs>[number] & { share_text?: string | null };
const LEGS: { en: RecordedLeg[]; zh: RecordedLeg[] } = { en: homeOffer.en.home_v2.action.legs ?? [], zh: homeOffer.zh.home_v2.action.legs ?? [] };

test("the funding timing opens the funding composition on the real pointer, on keyboard focus and from the address; its bar is proportional to the legs' amounts", async ({ page }) => {
  const legs = LEGS.en;
  expect(legs.length).toBeGreaterThan(1);
  const v2 = homeOffer.en.home_v2;
  await open(page, { offer: true });
  const fact = page.getByTestId("hv2-funding-fact");
  const comp = page.getByTestId("hv2-funding-composition");
  await expect(comp).toHaveCount(0);
  await expect(fact).toHaveAttribute("aria-expanded", "false");
  // The pointer on the fact opens it (the composition sits under the facts row and keeps open while the pointer is on it); leaving closes it.
  await fact.hover();
  await expect(comp).toBeVisible();
  await expect(fact).toHaveAttribute("aria-expanded", "true");
  await comp.hover();
  await expect(comp).toBeVisible();
  await page.mouse.move(5, 5);
  await expect(comp).toHaveCount(0);
  // One row per leg in the server's words, the total, and the plan's own basis for its cost.
  await fact.hover();
  for (const [i, leg] of legs.entries()) {
    const r = page.getByTestId(`hv2-comp-row-${i}`);
    await expect(r).toContainText(leg.amount_display);
    await expect(r).toContainText(leg.label);
    await expect(r).toContainText(leg.lands_when);
    await expect(r).toContainText(leg.state_text);
    await expect(r).toHaveAttribute("data-state", leg.state);
  }
  await expect(page.getByTestId("hv2-comp-total")).toContainText(v2.kpis.funding.value_display);
  if (v2.action.cost_basis_text) await expect(page.getByTestId("hv2-comp-basis")).toHaveText(v2.action.cost_basis_text);
  // The bar's widths are the amounts (the legs' `amount_fen` as the weights), not a percentage worked out here; the labels are the server's `share_text` when it sends one, else none.
  const widths = await Promise.all(legs.map(async (_, i) => (await page.getByTestId(`hv2-comp-seg-${i}`).boundingBox())!.width));
  const total = legs.reduce((n, l) => n + (l.amount_fen ?? 0), 0);
  for (const [i, leg] of legs.entries()) expect(widths[i] / widths.reduce((a, b) => a + b, 0)).toBeCloseTo((leg.amount_fen ?? 0) / total, 1);
  if (legs.every((l) => l.share_text)) for (const [i, leg] of legs.entries()) await expect(page.getByTestId(`hv2-comp-share-${i}`)).toHaveText(leg.share_text!);
  else await expect(page.getByTestId("hv2-comp-shares")).toHaveCount(0);
  await page.mouse.move(5, 5);
  // A press pins it into the address (and again releases it); the address alone opens it on load; keyboard focus opens it too.
  await fact.click();
  await expect(page).toHaveURL(/funding=1/);
  await page.mouse.move(5, 5);
  await expect(comp).toBeVisible();
  await page.reload();
  await expect(comp).toBeVisible();
  await fact.click();
  await page.mouse.move(5, 5);
  await expect(comp).toHaveCount(0);
  await expect(page).not.toHaveURL(/funding=1/);
  await fact.evaluate((el) => (el as HTMLElement).blur());
  for (let i = 0; i < 40 && !(await fact.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press("Tab");
  await expect(fact).toBeFocused();
  await expect(comp).toBeVisible();
  expect(await filledBrand(page)).toBe(1);
});

test("on a phone the funding fact opens its composition on a tap (rows, the bar), and in Chinese the words are the server's", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { lang: "zh", offer: true });
  const legs = LEGS.zh;
  await expect(page.getByTestId("hv2-funding-composition")).toHaveCount(0);
  await page.getByTestId("hv2-funding-fact").click();
  await page.mouse.move(5, 5);
  for (const [i, leg] of legs.entries()) {
    const row = page.getByTestId(`hv2-comp-row-${i}`);
    await expect(row).toContainText(leg.label);
    await expect(row).toContainText(leg.amount_display);
    await expect(row).toContainText(leg.state_text);
  }
  await expect(page.getByTestId("hv2-comp-bar")).toBeVisible();
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
  if (v2.kpis.funding.status_text) await expect(page.getByTestId("home-kpi-funding-status")).toHaveText(v2.kpis.funding.status_text);
  await expect(page.getByTestId("hv2-funding-hint")).toHaveText(v2.kpis.funding.hint);
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

test("Expand opens the full company forecast in place under the cards, with the events as chips and the selected event's sentence; Close and Escape restore the cards", async ({ page }) => {
  await open(page, { offer: true });
  const chart = homeOffer.en.home_v2.chart;
  const cash = homeOffer.en.cash;
  const forecast = page.getByTestId("hv2-forecast");
  const expand = page.getByTestId("hv2-outlook-expand");
  await expect(forecast).toHaveCount(0);
  await expect(page.getByTestId("home-chart")).toHaveCount(0);
  await expand.click();
  await expect(page).toHaveURL(/expand=1/);
  await expect(expand).toHaveAttribute("aria-expanded", "true");
  await expect(expand).toHaveText("Close");
  await expect(forecast).toBeVisible();
  await expect(page.getByRole("heading", { name: "Company cash forecast" })).toBeVisible();
  // It sits under the three cards, which stay.
  const cards = (await page.getByTestId("hv2-outlook-card").boundingBox())!;
  expect((await forecast.boundingBox())!.y).toBeGreaterThanOrEqual(cards.y + cards.height);
  await expect(page.getByTestId("hv2-action")).toBeVisible();
  // The chart: three legend entries (the red stretches stay red and unlabelled), the current line, the plan dashed grey, the minimum with its band, the lowest point; 300 px tall.
  const legend = page.getByTestId("home-legend");
  await expect(legend.locator("li")).toHaveCount(3);
  await expect(legend).toContainText("Current forecast");
  await expect(legend).toContainText("conditional on execution");
  await expect(legend).toContainText("Minimum reserve");
  await expect(page.getByTestId("hv2-below-base")).toBeAttached();
  await expect(page.getByTestId("home-line-counter")).toHaveClass(/stroke-ink-3/);
  await expect(page.getByTestId("home-line-plan")).toHaveClass(/stroke-chart-base/);
  await expect(page.getByTestId("hv2-danger")).toBeAttached();
  await expect(page.getByTestId("home-reserve")).toHaveClass(/stroke-chart-reserve/);
  await expect(page.getByTestId("home-lowest-mark")).toBeAttached();
  expect(Math.round((await page.getByTestId("home-chart").boundingBox())!.height)).toBe(300);
  await expect(page.getByTestId("hv2-inspector")).toHaveCount(0);
  await expect(page.getByTestId("hv2-forecast-full")).toHaveAttribute("href", "/cash");
  await expect(page.getByTestId("hv2-forecast-full")).toContainText("Open full analysis");
  // The window: three words in a compact control.
  const windows = page.getByRole("tablist", { name: "Days shown" }).getByRole("tab");
  await expect(windows).toHaveCount(3);
  await page.getByTestId("home-window-120").click();
  await page.getByTestId("home-window-36").click();
  // The events of the Home read are chips, one per day, and the selected one says its sentence (the server's `explain`); it opens on the lowest point.
  const rail = cash.events_rail.filter((e) => e.day >= 0);
  const days = [...new Set(rail.map((e) => e.day))];
  const lowestEvent = rail.find((e) => e.day === cash.lowest_day)!;
  await expect(page.getByTestId(`hv2-event-${cash.lowest_day}`)).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("hv2-event-card")).toHaveAttribute("data-day", String(cash.lowest_day));
  await expect(page.getByTestId("hv2-event-explain")).toHaveText(lowestEvent.explain);
  await expect(page.getByTestId("hv2-event-amount")).toHaveText(lowestEvent.amount_short);
  // Choosing another chip moves the chart's guide and the sentence; a click on the plot moves the chip.
  const other = rail.find((e) => e.kind === "payroll")!;
  await page.getByTestId(`hv2-event-${other.day}`).click();
  await expect(page.getByTestId("hv2-event-explain")).toHaveText(other.explain);
  await expect(page.getByTestId("home-chart")).toHaveAttribute("data-day", String(other.day));
  await expect(page.getByTestId(`hv2-event-${other.day}`)).toHaveAttribute("aria-pressed", "true");
  expect(days.length).toBeGreaterThan(3);
  await page.getByTestId("home-lowest-point").click();
  await expect(page.getByTestId(`hv2-event-${cash.lowest_day}`)).toHaveAttribute("aria-pressed", "true");
  expect(chart.lowest_inspector.day_text).toBeTruthy();
  // Close restores the cards and the address; Escape does the same.
  await page.getByTestId("hv2-forecast-close").click();
  await expect(forecast).toHaveCount(0);
  await expect(page).not.toHaveURL(/expand=1/);
  await expect(expand).toHaveText("Expand");
  await page.goto("/?expand=1");
  await expect(forecast).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(forecast).toHaveCount(0);
  await expect(page).not.toHaveURL(/expand=1/);
  await expand.click();
  await expect(forecast).toBeVisible();
  await expand.click();
  await expect(forecast).toHaveCount(0);
});

test("the worklist as the mockup's table: one alert line, tabs with counts, rows with the next step and the status pill, the count, the way to all deals", async ({ page }) => {
  await open(page, { offer: true });
  const w = worklistOffer.en;
  await expect(page.getByTestId("hv2-worklist-title")).toHaveText("Your worklist");
  await expect(page.getByTestId("hv2-worklist-count")).toHaveText(String(w.counts.needs_you + w.counts.waiting));
  const alert = page.getByTestId("home-worklist-alert");
  // The alert reads as the pending action when the server says so (its kind and pending words), else with its own eyebrow and text.
  const said = w.alert as typeof w.alert & { kind_text?: string | null; pending_text?: string | null };
  await expect(alert).toContainText(said.pending_text ?? said.text);
  await expect(alert).toContainText(said.kind_text ?? said.eyebrow);
  await expect(page.getByTestId("home-worklist-alert-go")).toContainText(w.alert.primary.label);
  await expect(alert).toHaveClass(/border-l-2/);
  const note = page.getByTestId("home-worklist-alert-note");
  await expect(alert).toHaveAttribute("aria-describedby", (await note.getAttribute("id")) ?? "");
  expect(((await note.boundingBox())?.width ?? 0) <= 1).toBe(true);
  expect((await alert.boundingBox())!.height).toBeLessThan(120);
  // Tabs: All is the two lists together; the count beside the label; a tab's hint is its title, not a line on the page. The chosen tab is a white pill.
  expect(w.counts.needs_you).toBe(w.needs_you.length);
  const all = page.getByTestId("home-tab-all");
  await expect(all).toHaveAttribute("aria-selected", "true");
  await expect(all).toContainText("All");
  await expect(page.getByTestId("home-tab-all-badge")).toHaveText(String(w.counts.needs_you + w.counts.waiting));
  expect(await all.evaluate((n) => getComputedStyle(n).backgroundColor)).toBe("rgb(255, 255, 255)");
  await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveText(String(w.counts.needs_you));
  await expect(page.getByTestId("home-tab-waiting-badge")).toHaveText(String(w.counts.waiting));
  await expect(page.getByTestId("home-tab-customers-badge")).toHaveText(String(w.counts.customers));
  await expect(page.getByTestId("home-tab-needs_you")).toHaveAttribute("title", /./);
  // The table's head and the rows: the subject, the next step (the server's consequence) and the status pill (the server's status words; amber when it is the owner's turn).
  for (const col of ["Customer / deal", "Next step", "Status"]) await expect(page.getByTestId("home-worklist").getByText(col, { exact: true })).toBeVisible();
  const rows = page.getByTestId("home-worklist-row");
  await expect(rows).toHaveCount(w.needs_you.length + w.waiting.length);
  await expect(rows.first()).toContainText(w.needs_you[0].subject_text);
  await expect(rows.first()).toContainText(w.needs_you[0].consequence_text);
  const pill = rows.first().getByTestId("home-row-status");
  await expect(pill).toHaveText(w.needs_you[0].status_text);
  await expect(pill).toHaveAttribute("data-tone", "amber");
  expect(await pill.evaluate((n) => parseFloat(getComputedStyle(n).fontSize))).toBeGreaterThanOrEqual(13);
  expect(await rows.first().locator("a").evaluate((n) => getComputedStyle(n).backgroundColor)).toBe("rgb(255, 255, 255)");
  await expect(rows.first().getByTestId("home-row-severity")).toHaveAttribute("data-severity", w.needs_you[0].severity);
  await expect(page.getByTestId("home-why-first")).toHaveCount(0);
  await expect(page.getByTestId("home-worklist-all")).toHaveText(/^All deals/);
  await expect(page.getByTestId("home-worklist-all")).toHaveAttribute("href", "/deals");
  // Needs you and Waiting filter it; Waiting is empty in words; Customers lists one row per buyer.
  await page.getByTestId("home-tab-needs_you").click();
  await expect(rows).toHaveCount(w.needs_you.length);
  await page.getByTestId("home-tab-waiting").click();
  await expect(page.getByTestId("home-worklist-empty")).toContainText("All caught up.");
  await page.getByTestId("home-tab-customers").click();
  await expect(rows).toHaveCount(w.customers.length);
  await expect(rows.first()).toContainText(w.customers[0].name);
  await expect(rows.first()).toContainText(w.customers[0].detail_text);
  await expect(rows.first().getByTestId("home-row-status")).toHaveText(w.customers[0].status_text);
  // The arrow keys move between the tabs.
  await page.getByTestId("home-tab-customers").focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByTestId("home-tab-waiting")).toHaveAttribute("aria-selected", "true");
});

test("the upcoming cash movements are the rail's nearest events, and the way to the forecast; the footer row leads to the four routes", async ({ page }) => {
  await open(page, { offer: true });
  const events = homeOffer.en.cash.events_rail.filter((e) => !e.planned && e.amount_fen !== 0 && e.day >= 0).slice(0, 4);
  const rows = page.getByTestId("hv2-upcoming-row");
  await expect(rows).toHaveCount(events.length);
  for (const [i, e] of events.entries()) {
    await expect(rows.nth(i)).toContainText(e.amount_short);
    await expect(rows.nth(i)).toContainText(e.when);
    await expect(rows.nth(i)).toContainText(e.label);
  }
  await expect(page.getByTestId("home-chart-full")).toHaveAttribute("href", "/cash");
  await expect(page.getByTestId("home-chart-full")).toContainText("Explore company forecast");
  const foot = page.getByTestId("home-v2-links");
  for (const [route, word] of [["documents", "Documents"], ["whatif", "What-if terms"], ["capex", "Evaluate a purchase"], ["approvals", "Approvals"]]) {
    await expect(foot.getByTestId(`hv2-foot-${route}`)).toHaveText(word);
    await expect(foot.getByTestId(`hv2-foot-${route}`)).toHaveAttribute("href", `/${route}`);
  }
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
  await expect(page.getByTestId("home-worklist-alert")).toContainText((worklistDay0.en.alert as { text: string; pending_text?: string | null }).pending_text ?? worklistDay0.en.alert.text);
  await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveText("0");
  // Nothing in the queue: the server's alert-aware words when it sends them ("Nothing else needs you." while the plan waits for the owner's go), else the plain ones.
  const empty = (worklistDay0.en as typeof worklistDay0.en & { needs_you_empty_text?: string | null }).needs_you_empty_text;
  await expect(page.getByTestId("home-worklist-empty")).toContainText(empty ?? "All caught up.");
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
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
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
  // The selected card replaces the cash and recommendation cards and keeps the outlook; its header names the deal and carries Dismiss; the stage pill is in the context panel.
  await expect(page.getByTestId("hv2-cash-card")).toHaveCount(0);
  await expect(page.getByTestId("hv2-outlook-card")).toBeVisible();
  await expect(page.getByTestId("focus-all")).toHaveText("Dismiss");
  await expect(page.getByTestId("hv2-context-stage")).toHaveText(worklistOffer.en.needs_you[0].status_text);
  await expect(page.getByTestId("hv2-context")).toContainText("Deal context");
  await expect(page.getByTestId("hv2-context-sentence")).toHaveText(worklistOffer.en.needs_you[0].consequence_text);
  await expect(page.getByTestId("focus-title")).toHaveText(SUBJECT.en);
  // Three figures in the server's words: what is outstanding, the early payment asked, the payment terms asked.
  const kpiAsked = pictures.en.paths.find((p) => p.kind === "asked") as unknown as { terms: { key: string; value_text: string }[] };
  await expect(page.getByTestId("hv2-deal-kpi-outstanding")).toContainText(view.figures.find((f) => f.key === "outstanding")!.value_display);
  await expect(page.getByTestId("hv2-deal-kpi-early_payment")).toContainText(kpiAsked.terms.find((t) => t.key === "early_payment")!.value_text);
  await expect(page.getByTestId("hv2-deal-kpi-payment_terms")).toContainText(kpiAsked.terms.find((t) => t.key === "payment_terms")!.value_text);
  await expect(page.getByTestId("hv2-deal-next")).toContainText(d.eyebrow);
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
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
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

test("zh parity: the cards, the recommendation, the worklist, the forecast and the deal in Chinese, the server's words as recorded", async ({ page }) => {
  await open(page, { lang: "zh", offer: true });
  const v2 = homeOffer.zh.home_v2;
  await expect(page.getByTestId("home-read-when")).toHaveText("今天更新");
  await expect(page.getByTestId("hv2-metric-cash-label")).toHaveText("今日可用现金");
  await expect(page.getByTestId("hv2-metric-lowest-label")).toHaveText("公司现金展望");
  await expect(page.getByTestId("home-kpi-cash-note")).toHaveText(v2.kpis.cash_available.note);
  await expect(page.getByTestId("home-kpi-lowest-note")).toHaveText(v2.kpis.lowest_ahead.short_note ?? v2.kpis.lowest_ahead.note);
  if (v2.kpis.funding.status_text && v2.kpis.funding.state === "ARRANGED") await expect(page.getByTestId("home-kpi-funding-status")).toHaveText(v2.kpis.funding.status_text);
  await expect(page.getByTestId("hv2-funding-hint")).toHaveText(v2.kpis.funding.hint);
  await expect(page.getByTestId("hv2-plan-pill")).toHaveText("计划中");
  await expect(page.getByTestId("home-action-title")).toHaveText(v2.action.title);
  await expect(page.getByTestId("home-action-eyebrow")).toHaveText("我们的建议");
  await expect(page.getByTestId("hv2-approval")).toHaveText(v2.action.approval_text!);
  await expect(page.getByTestId("hv2-outlook-expand")).toHaveText("展开");
  await page.getByTestId("hv2-outlook-expand").click();
  const lowestEvent = homeOffer.zh.cash.events_rail.find((e) => e.day === homeOffer.zh.cash.lowest_day)!;
  await expect(page.getByTestId("hv2-event-explain")).toHaveText(lowestEvent.explain);
  await expect(page.getByTestId("home-legend")).toContainText("取决于方案执行");
  await expect(page.getByTestId("hv2-forecast-close")).toHaveText("收起");
  await page.getByTestId("hv2-forecast-close").click();
  const w = worklistOffer.zh;
  await expect(page.getByTestId("home-worklist-alert")).toContainText((w.alert as { text: string; pending_text?: string | null }).pending_text ?? w.alert.text);
  await expect(page.getByTestId("home-worklist-row").first()).toContainText(w.needs_you[0].subject_text);
  await expect(page.getByTestId("home-worklist-row").first().getByTestId("home-row-status")).toHaveText(w.needs_you[0].status_text);
  await expect(page.getByTestId("home-worklist-search")).toHaveAttribute("placeholder", "搜索客户或交易");
  await expect(page.getByTestId("home-tab-all")).toContainText("全部");
  await expect(page.getByTestId("home-tab-waiting")).toContainText("等待中");
  await expect(page.getByTestId("hv2-upcoming")).toContainText("即将发生的现金变动");
  await expect(page.getByTestId("hv2-foot-documents")).toHaveText("文件");
  await page.goto(DEAL + "&compare=1");
  const pic = pictures.zh.paths;
  await expect(page.getByTestId("focus-title")).toHaveText(SUBJECT.zh);
  await expect(page.getByTestId("focus-all")).toHaveText("关闭");
  await expect(page.getByTestId("hv2-context")).toContainText("交易背景");
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
  await expect(page.getByTestId("hv2-context")).toContainText("客户背景");
});

test("phone: the cards stack with the recommendation's primary in the first viewport; the worklist is a list with the pill under the subject; nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { offer: true });
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
  // The cards are one column, in the mockup's order: cash, recommendation, outlook.
  const ys = await Promise.all(["hv2-cash-card", "hv2-action", "hv2-outlook-card"].map(async (id) => (await page.getByTestId(id).boundingBox())!));
  expect(ys[1].y).toBeGreaterThan(ys[0].y + ys[0].height - 1);
  expect(ys[2].y).toBeGreaterThan(ys[1].y + ys[1].height - 1);
  expect(Math.abs(ys[0].width - ys[2].width)).toBeLessThan(2);
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
  // No sheet and no opener: the worklist is on the page; a row is the subject, its next step and the status pill under it (the head of the table is hidden).
  await expect(page.getByTestId("home-worklist-open")).toHaveCount(0);
  await expect(page.getByTestId("home-worklist-panel")).toBeVisible();
  const row = page.getByTestId("home-worklist-row").first();
  await row.scrollIntoViewIfNeeded();
  const subject = (await row.getByText(worklistOffer.en.needs_you[0].subject_text).boundingBox())!;
  const pill = (await row.getByTestId("home-row-status").boundingBox())!;
  expect(pill.y).toBeGreaterThan(subject.y + subject.height - 1);
  expect(pill.x + pill.width).toBeLessThanOrEqual(390);
  // The alert's "Run or compare" brings the recommendation into view.
  await page.getByTestId("home-worklist-alert-go").click();
  await expect(page.getByTestId("home-v2-action")).toBeInViewport();
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
});

test("phone: a row opens the deal at the top, under the one-row band; the table stacks; Dismiss restores the cards; nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { offer: true });
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
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
  await page.getByTestId("focus-all").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
});

test("phone: the collection state, a customer's row opens its card and its context under the worklist, in one column", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  const a = (await page.getByTestId("home-customer-focus").boundingBox())!;
  const b = (await page.getByTestId("hv2-outlook-card").boundingBox())!;
  const c = (await page.getByTestId("hv2-context").boundingBox())!;
  expect(b.y).toBeGreaterThan(a.y + a.height - 1);
  expect(c.y).toBeGreaterThan(b.y);
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

test("a selected row: Dismiss and Escape restore the overview and clear the address; the context panel replaces the upcoming movements and the cards come back", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("hv2-context")).toBeVisible();
  await expect(page.getByTestId("hv2-upcoming")).toHaveCount(0);
  await expect(page.getByTestId("hv2-cash-card")).toHaveCount(0);
  await page.getByTestId("focus-all").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("hv2-context")).toHaveCount(0);
  await expect(page.getByTestId("hv2-upcoming")).toBeVisible();
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toBeVisible();
  await page.goto(DEAL);
  await expect(page.getByTestId("home-deal-focus")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
  // With the forecast open, Escape closes it first; a second Escape clears a selection.
  await page.goto(DEAL + "&expand=1");
  await expect(page.getByTestId("hv2-forecast")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("hv2-forecast")).toHaveCount(0);
  await expect(page.getByTestId("home-deal-focus")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("home-deal-focus")).toHaveCount(0);
  // The context panel: the stage as the row's own pill, Customer profile, and the evidence fold that opens on the deal's own sentence.
  await page.goto(DEAL);
  const ctx = page.getByTestId("hv2-context");
  await expect(ctx.getByTestId("focus-open-customer")).toHaveText("Customer profile");
  const fold = page.getByTestId("hv2-context-evidence");
  await expect(fold).toContainText("Agreement & supporting evidence");
  await expect(page.getByTestId("hv2-context-evidence-text")).toBeHidden();
  await fold.locator("> summary").click();
  await expect(page.getByTestId("hv2-context-evidence-text")).toContainText("early settlement");
});

test("reduced motion: a selection arrives without an animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page, { offer: true });
  await page.goto("/?customer=BUYER-1");
  const panel = page.getByTestId("home-customer-focus").locator(".motion-swap");
  await expect(panel).toBeVisible();
  const ms = await panel.evaluate((el) => parseFloat(getComputedStyle(el).animationDuration) * 1000);
  const name = await panel.evaluate((el) => getComputedStyle(el).animationName);
  expect(name === "none" || ms <= 1).toBe(true);
});

test("accessibility: no axe violations on the default Home, expanded, with the customer and with the deal open (compared, with its chart), at 1440 and at 390", async ({ page }) => {
  await open(page, { offer: true });
  for (const url of ["/", "/?expand=1&funding=1", "/?customer=BUYER-1", `${DEAL}&compare=1&chart=1`]) {
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
});

test("the page is fluid: with the rail collapsed the cards fill the width to 1680 px, pinned the content reflows narrower; the cards and the worklist share the same edges", async ({ page }) => {
  const widths = async () =>
    page.evaluate(() => {
      const box = (id: string) => document.querySelector(`[data-testid="${id}"]`)!.getBoundingClientRect();
      const left = box("hv2-cash-card").left;
      const right = box("hv2-outlook-card").right;
      return { main: Math.round(document.querySelector("main")!.getBoundingClientRect().width), row: Math.round(right - left), worklistLeft: Math.round(box("home-worklist-panel").left - left), upcomingRight: Math.round(box("hv2-upcoming").right - right), pane: Math.round(box("hv2-upcoming").width) };
    });
  const seen: Record<number, { collapsed: Awaited<ReturnType<typeof widths>>; pinned: Awaited<ReturnType<typeof widths>> }> = {};
  await open(page, { offer: true });
  for (const width of [1280, 1440, 1680, 1920] as const) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
    const collapsed = await widths();
    await page.getByTestId("sidebar-toggle").click();
    await page.mouse.move(width / 2, 400);
    // Pinned, the track is 200 px: the page is narrower unless the window is wide enough that it is the 1680 cap either way.
    if (collapsed.main < 1680) await expect.poll(async () => (await widths()).main).toBeLessThan(collapsed.main);
    else await expect(page.locator("html")).toHaveAttribute("data-sidebar", "pinned");
    const pinned = await widths();
    await page.getByTestId("sidebar-toggle").click();
    seen[width] = { collapsed, pinned };
    // The cards' row and the worklist row share the left and right edges, and nothing scrolls sideways.
    expect(collapsed.worklistLeft, `${width} left edge`).toBe(0);
    expect(collapsed.upcomingRight, `${width} right edge`).toBe(0);
    expect(await overflowX(page)).toBeLessThanOrEqual(0);
    // The rail's own 56 px: the page fills what is left, to 1680.
    expect(collapsed.main).toBe(Math.min(width - 56, 1680));
    expect(pinned.main).toBe(Math.min(width - 200, 1680));
  }
  expect(seen[1680].collapsed.row - seen[1680].pinned.row).toBeGreaterThanOrEqual(130);
  expect(seen[1680].collapsed.row).toBeGreaterThan(seen[1440].collapsed.row);
  expect(seen[1920].collapsed.main).toBe(1680);
});
