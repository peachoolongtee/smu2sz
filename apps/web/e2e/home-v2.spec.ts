import AxeBuilder from "@axe-core/playwright";
import { en } from "../lib/dictionary";
import type { Page } from "@playwright/test";
import { expect, proseOf, test } from "./fixtures";
import { filledBrand, runPlan } from "./helpers";
import homeDay0 from "../mocks/home_v2/home_day0.json";
import homeOffer from "../mocks/home_v2/home_offer.json";
import homeAfter from "../mocks/home_v2/home_after_fund.json";
import worklistDay0 from "../mocks/home_v2/worklist_day0.json";
import worklistOffer from "../mocks/home_v2/worklist_offer.json";
import worklistAfter from "../mocks/home_v2/worklist_after_fund.json";
import evaluated from "../mocks/deals_day0_evaluated.json";
import focusOfferRec from "../mocks/home_v2/focus_offer.json";
import customersOffer from "../mocks/home_v2/customers_offer.json";
import receivablesAfter from "../mocks/home_v2/receivables_after_fund.json";

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
    // The deal's name is the buyer's ask in words (the server's `asks_text`), not the verdict's short heading.
    const asks = evaluated.deals.find((d) => d.open_offer)!.open_offer!.asks_text;
    // The title is the ask from the first read, so the check is done when the recommendation is there.
    await page.getByTestId("queue-recommends").waitFor();
    await expect(page.getByTestId("queue-heading")).toContainText(asks);
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
  // "FLOW action ready" is said once, by the recommendation card: no pill beside the headline, and the line under it keeps the server's count sentence and drops "One funding action ready.".
  await expect(page.getByTestId("hv2-state-pill")).toHaveCount(0);
  expect(v2.summary_text).toBe("One funding action ready. One deal decision needs you.");
  await expect(page.getByTestId("hv2-summary")).toHaveText("One deal decision needs you.");
  expect(await page.getByTestId("hv2-summary").evaluate((n) => getComputedStyle(n).fontSize)).toBe("15px");
  expect(await page.getByTestId("hv2-headline").evaluate((n) => getComputedStyle(n).fontSize)).toBe("32px");
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
  // The planned amount is the figure; the cost to the owner is one line under it; the funding legs are one inline bar in the gap (no disclosure).
  await expect(page.getByTestId("hv2-plan-amount")).toHaveText(homeOffer.en.home_v2.kpis.funding.value_display);
  // "Conditional on you running the plan; not counted as cash" left the card (it is the pill's meaning); it is the first line of the funding disclosure.
  await expect(page.getByTestId("hv2-funding-hint")).toHaveCount(0);
  await expect(page.getByTestId("hv2-action-facts")).toContainText("Cost to you");
  await expect(page.getByTestId("hv2-hero-value")).toHaveText(facts[0].value);
  await expect(page.getByTestId("hv2-funding-fact")).toHaveCount(0);
  await expect(page.getByTestId("hv2-funding-bar")).toBeVisible();
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
  // Round four: the card is a flex column. The cost is the bold fact, the funding bar fills the gap under it, the approval line sits directly above the actions, and the actions are pinned to the card's bottom.
  const [actionsBox, lineBox, costBox, barBox, cardBox] = await Promise.all([page.getByTestId("home-attention-run").boundingBox(), approval.boundingBox(), page.getByTestId("hv2-hero-value").boundingBox(), page.getByTestId("hv2-funding-bar").boundingBox(), page.getByTestId("hv2-action").boundingBox()]);
  expect(lineBox!.y + lineBox!.height).toBeLessThanOrEqual(actionsBox!.y + 1);
  expect(actionsBox!.y - (lineBox!.y + lineBox!.height)).toBeLessThan(16);
  expect(barBox!.y).toBeGreaterThan(costBox!.y + costBox!.height - 1);
  expect(barBox!.y + barBox!.height).toBeLessThanOrEqual(lineBox!.y + 1);
  expect(Math.round(cardBox!.y + cardBox!.height - (actionsBox!.y + actionsBox!.height))).toBeLessThanOrEqual(20); // 16 px padding: the actions are pinned to the bottom
  // The plan is checked and run on Cash & funding: the card's one filled button opens it there, "Compare funding options" is the outlined link beside it.
  await expect(page.getByTestId("home-check-plan")).toHaveText(en["hv2.action.check"]);
  await expect(page.getByTestId("home-check-plan")).toHaveAttribute("href", "/cash");
  await expect(page.getByTestId(`fix-open-${ALERT}`)).toHaveCount(0);
  await expect(page.getByTestId("next-action-alternatives")).toHaveText("Compare funding options");
  await expect(page.getByTestId("next-action-alternatives")).toHaveAttribute("href", a.secondary.href);
  expect(await filledBrand(page)).toBe(1);
  // On Cash the plan's two presses are there: ask, then run exactly that; cancel returns.
  await page.getByTestId("home-check-plan").click();
  await expect(page).toHaveURL(/\/cash/);
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

// A facility application carries no planned amount: the server's funding says state NONE and its word "None" (the busy Demo's "Apply for ¥288,570.00 on Equipment lease"); an optional word the server leaves null is not text.
test("no funding amount: the figure line is omitted (the title carries the amount) and no null, undefined or 'None' is ever rendered on the Home", async ({ page }) => {
  const funding = { ...homeOffer.en.home_v2.kpis.funding, state: "NONE", value_display: "None", status_text: null, hint: null };
  const action = {
    ...homeOffer.en.home_v2.action,
    title: "Apply for ¥288,570.00 on Equipment lease",
    facts: [],
    legs: [],
    consequence_text: null,
    approval_text: null,
    approval_needed: false,
    cost_basis_text: null,
  };
  const lowest = { ...homeOffer.en.home_v2.kpis.lowest_ahead, with_plan: null, short_note: null };
  const v2 = { ...homeOffer.en.home_v2, summary_text: null, kpis: { ...homeOffer.en.home_v2.kpis, funding, lowest_ahead: lowest }, action };
  await page.context().addInitScript(([key, patch]) => sessionStorage.setItem(key as string, JSON.stringify(patch)), ["tl-mock-home-patch", { home_v2: v2 }] as const);
  await open(page, { offer: true });
  await expect(page.getByTestId("home-action-title")).toHaveText("Apply for ¥288,570.00 on Equipment lease");
  await expect(page.getByTestId("home-kpi-funding-value")).toHaveCount(0);
  await expect(page.getByTestId("hv2-plan-amount")).toHaveCount(0);
  await expect(page.getByTestId("hv2-plan-pill")).toHaveCount(0);
  await expect(page.getByTestId("hv2-approval")).toHaveCount(0);
  // With no consequence sentence the card keeps the action's own text (the server's), never an empty line.
  await expect(page.getByTestId("home-action-text")).toHaveText(homeOffer.en.home_v2.action.text);
  await expect(page.getByTestId("hv2-summary")).toHaveCount(0);
  await expect(page.getByTestId("home-kpi-lowest-plan")).toHaveCount(0);
  // Round four's rule: the card has a title, so the Home renders a recommendation card and the worklist's alert row is absent (it is not keyed to the funding state).
  await expect(page.getByTestId("home-worklist-alert")).toHaveCount(0);
  const said = await page.getByTestId("home-v2").innerText();
  expect(said).not.toMatch(/\b(None|null|undefined|NaN)\b/);
  // The same with the customer selected and the forecast open.
  for (const url of ["/?customer=BUYER-1", "/?expand=1"]) {
    await page.goto(url);
    await expect(page.getByTestId("home-v2")).toBeVisible();
    await expect(page.getByTestId("hv2-stage")).toBeVisible();
    expect(await page.getByTestId("home-v2").innerText(), url).not.toMatch(/\b(None|null|undefined|NaN)\b/);
  }
});

// Round four, section 4: the worklist's alert row stands in only when the Home renders NO recommendation card (the action has no title and no control).
test("the alert row shows only when the Home renders no recommendation card: its kind, its words and the way to act", async ({ page }) => {
  const action = { ...homeOffer.en.home_v2.action, variant: "QUIET", title: "", eyebrow: "", text: "", control: null, primary: null, secondary: null, facts: [], legs: [], consequence_text: null, approval_text: null, approval_needed: false, cost_basis_text: null };
  const funding = { ...homeOffer.en.home_v2.kpis.funding, state: "PROPOSED" }; // the funding state is not the rule: a proposed funding with no card still shows the row
  const v2 = { ...homeOffer.en.home_v2, kpis: { ...homeOffer.en.home_v2.kpis, funding }, action };
  await page.context().addInitScript(([key, patch]) => sessionStorage.setItem(key as string, JSON.stringify(patch)), ["tl-mock-home-patch", { home_v2: v2 }] as const);
  await open(page, { offer: true });
  const alertRead = worklistOffer.en.alert as typeof worklistOffer.en.alert & { kind_text?: string | null; pending_text?: string | null };
  const alert = page.getByTestId("home-worklist-alert");
  await expect(alert).toContainText(alertRead.pending_text ?? alertRead.text);
  await expect(alert).toContainText(alertRead.kind_text ?? alertRead.eyebrow);
  await expect(page.getByTestId("home-worklist-alert-go")).toContainText(alertRead.primary.label);
  await expect(alert).toHaveClass(/border-l-2/);
  const note = page.getByTestId("home-worklist-alert-note");
  await expect(alert).toHaveAttribute("aria-describedby", (await note.getAttribute("id")) ?? "");
  expect((await alert.boundingBox())!.height).toBeLessThan(120);
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

test("the funding legs are one inline stacked bar in the card's gap: widths from the legs' amounts, the server's labels, amounts, landing words and shares, the total at the right; a leg card on hover and focus", async ({ page }) => {
  const legs = LEGS.en;
  expect(legs.length).toBeGreaterThan(1);
  const v2 = homeOffer.en.home_v2;
  await open(page, { offer: true });
  // No disclosure and no `funding` address flag: the bar is simply there.
  await expect(page.getByTestId("hv2-funding-fact")).toHaveCount(0);
  const bar = page.getByTestId("hv2-funding-bar");
  await expect(bar).toBeVisible();
  expect((await bar.boundingBox())!.height).toBeLessThanOrEqual(14); // one thin bar
  for (const [i, leg] of legs.entries()) {
    const r = page.getByTestId(`hv2-funding-row-${i}`);
    await expect(r).toContainText(leg.label);
    await expect(r).toContainText(leg.amount_display);
    await expect(r).toContainText(leg.lands_when);
    if (leg.share_text) await expect(page.getByTestId(`hv2-funding-share-${i}`)).toHaveText(leg.share_text);
  }
  // The total sits at the right end of the bar, in the server's word.
  const total = page.getByTestId("hv2-funding-total");
  await expect(total).toHaveText(v2.kpis.funding.value_display);
  const [barBox, totalBox] = await Promise.all([bar.boundingBox(), total.boundingBox()]);
  expect(totalBox!.x).toBeGreaterThanOrEqual(barBox!.x + barBox!.width - 1);
  // The widths are the amounts (the legs' `amount_fen` as the weights), not a percentage worked out here.
  const widths = await Promise.all(legs.map(async (_, i) => (await page.getByTestId(`hv2-funding-seg-${i}`).boundingBox())!.width));
  const sum = legs.reduce((n, l) => n + (l.amount_fen ?? 0), 0);
  for (const [i, leg] of legs.entries()) expect(widths[i] / widths.reduce((a, b) => a + b, 0)).toBeCloseTo((leg.amount_fen ?? 0) / sum, 1);
  // Hover on a segment opens its leg card (the leg, when it lands, its state, its cost and when it is repaid, who approves); leaving closes it. Focus does the same.
  const tip = page.getByTestId("hv2-funding-tip-0");
  expect(await tip.evaluate((n) => getComputedStyle(n).opacity)).toBe("0");
  await page.getByTestId("hv2-funding-seg-0").hover();
  await expect.poll(() => tip.evaluate((n) => getComputedStyle(n).opacity)).toBe("1");
  await expect(tip).toContainText(legs[0].label);
  await expect(tip).toContainText(legs[0].state_text);
  await expect(tip).toContainText(legs[0].cost_display!);
  await expect(tip).toContainText(legs[0].authority_text!);
  await page.mouse.move(5, 5);
  await expect.poll(() => tip.evaluate((n) => getComputedStyle(n).opacity)).toBe("0");
  await page.getByTestId("hv2-funding-seg-1").focus();
  await expect.poll(() => page.getByTestId("hv2-funding-tip-1").evaluate((n) => getComputedStyle(n).opacity)).toBe("1");
  await expect(page.getByTestId("hv2-funding-seg-1")).toHaveAttribute("aria-describedby", /hv2-funding-tip-1/);
  // A press says that leg's sentence; a second press clears.
  await page.getByTestId("hv2-funding-seg-1").click();
  await expect(page.getByTestId("hv2-funding-sentence")).toContainText(legs[1].label);
  await expect(page).not.toHaveURL(/funding=1/);
  expect(await filledBrand(page)).toBe(1);
});

test("a single-leg plan is one full bar with its one label; a plan with no legs shows the server's cost basis alone", async ({ page }) => {
  const one = homeOffer.en.home_v2.action.legs![0];
  const action = { ...homeOffer.en.home_v2.action, legs: [one] };
  await page.context().addInitScript(([key, patch]) => sessionStorage.setItem(key as string, JSON.stringify(patch)), ["tl-mock-home-patch", { home_v2: { ...homeOffer.en.home_v2, action } }] as const);
  await open(page, { offer: true });
  await expect(page.getByTestId("hv2-funding-seg-0")).toBeVisible();
  await expect(page.getByTestId("hv2-funding-seg-1")).toHaveCount(0);
  const [barBox, segBox] = await Promise.all([page.getByTestId("hv2-funding-bar").boundingBox(), page.getByTestId("hv2-funding-seg-0").boundingBox()]);
  expect(Math.abs(barBox!.width - segBox!.width)).toBeLessThan(2);
  await expect(page.getByTestId("hv2-funding-row-0")).toContainText(one.label);
  await expect(page.getByTestId("hv2-funding-row-0")).toContainText(one.amount_display);
});

test("a plan with no legs shows the server's cost basis alone in the gap", async ({ page }) => {
  const action = { ...homeOffer.en.home_v2.action, legs: [] };
  await page.context().addInitScript(([key, patch]) => sessionStorage.setItem(key as string, JSON.stringify(patch)), ["tl-mock-home-patch", { home_v2: { ...homeOffer.en.home_v2, action } }] as const);
  await open(page, { offer: true });
  await expect(page.getByTestId("hv2-funding-bar")).toHaveCount(0);
  await expect(page.getByTestId("hv2-cost-basis")).toHaveText(homeOffer.en.home_v2.action.cost_basis_text!);
  expect(await page.getByTestId("hv2-cost-basis").evaluate((n) => parseFloat(getComputedStyle(n).fontSize))).toBeGreaterThanOrEqual(13);
});

test("on a phone the funding bar and its legend stay inside the card, and in Chinese the words are the server's", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { lang: "zh", offer: true });
  const legs = LEGS.zh;
  for (const [i, leg] of legs.entries()) {
    const row = page.getByTestId(`hv2-funding-row-${i}`);
    await expect(row).toContainText(leg.label);
    await expect(row).toContainText(leg.amount_display);
    await expect(row).toContainText(leg.lands_when);
  }
  await expect(page.getByTestId("hv2-funding-bar")).toBeVisible();
  const [cardBox, barBox] = await Promise.all([page.getByTestId("hv2-action").boundingBox(), page.getByTestId("hv2-funding-bar").boundingBox()]);
  expect(barBox!.x + barBox!.width).toBeLessThanOrEqual(cardBox!.x + cardBox!.width);
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
  expect(await filledBrand(page)).toBe(1);
});

test("running the plan: no alert, the covered recommendation with its one button to the deals, the financing on the worklist", async ({ page }) => {
  await open(page, { offer: true });
  await expect(page.getByTestId("home-worklist-alert")).toHaveCount(0); // the recommendation card is the alert
  await runPlan(page, ALERT); // the Home's card opens Cash & funding, where the two presses are; the owner is back on the Home after
  const v2 = homeAfter.en.home_v2;
  // Nothing needs funding any more: the card is the "You're covered!" celebration (a quiet recommendation with the cash covered), with the lowest cash ahead and the room above the minimum, and one filled button, on to the deals.
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "covered");
  await expect(page.getByTestId("home-action-title")).toHaveText(v2.action.title);
  await expect(page.getByTestId("hv2-covered-facts")).toContainText(v2.kpis.lowest_ahead.value_display);
  await expect(page.getByTestId("hv2-explore-deals")).toHaveAttribute("href", "/deals");
  await expect(page.getByTestId("home-worklist-alert")).toHaveCount(0);
  await expect(page.getByTestId("home-check-plan")).toHaveCount(0);
  expect(await filledBrand(page)).toBe(0); // "You're covered" means nothing is urgent: its way to the deals is the outlined button
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
  // In page coordinates: the forecast scrolls itself into view, so viewport boxes taken at different moments are not comparable.
  const pageBottom = (id: string) => page.getByTestId(id).evaluate((el) => el.getBoundingClientRect().bottom + window.scrollY);
  const pageTop = (id: string) => page.getByTestId(id).evaluate((el) => el.getBoundingClientRect().top + window.scrollY);
  await expect.poll(async () => (await pageTop("hv2-forecast")) - (await pageBottom("hv2-outlook-card")), { message: "the forecast unfolds under the cards" }).toBeGreaterThanOrEqual(-1);
  await expect(page.getByTestId("hv2-action")).toBeVisible();
  // The chart: three legend entries (the red stretches stay red and unlabelled), the current line, the plan dashed grey, the minimum with its band, the lowest point; 300 px tall.
  const legend = page.getByTestId("home-legend");
  await expect(legend.locator("li")).toHaveCount(3);
  await expect(legend).toContainText("Current forecast");
  await expect(legend).toContainText("conditional on execution");
  await expect(legend).toContainText("Minimum reserve");
  await expect(page.getByTestId("hv2-below-base")).toBeAttached();
  // FLOW's plan is the better line now: solid, bolder and in the agreed green (it was a dashed grey).
  await expect(page.getByTestId("home-line-counter")).toHaveClass(/stroke-ok-solid/);
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
  // The events of the Home read are numbered markers on their line, one per day; one opens its callout with the server's sentence (`explain`), its amount and its words for when.
  const rail = cash.events_rail.filter((e) => e.day >= 0);
  const chips = [...new Map(rail.map((e) => [e.day, e])).values()];
  expect(chips.length).toBeGreaterThan(3);
  await expect(page.locator('[data-testid^="hv2-marker-"][data-day]')).toHaveCount(chips.length);
  await expect(page.getByTestId("hv2-marker-callout")).toHaveCount(0);
  const at = (day: number) => page.locator(`[data-testid^="hv2-marker-"][data-day="${day}"]`);
  const lowestEvent = chips.find((e) => e.day === cash.lowest_day) ?? chips[0];
  await at(lowestEvent.day).click();
  await expect(page.getByTestId("hv2-marker-callout")).toHaveAttribute("data-day", String(lowestEvent.day));
  await expect(page.getByTestId("hv2-marker-callout")).toContainText(lowestEvent.explain);
  await expect(page.getByTestId("hv2-marker-callout")).toContainText(lowestEvent.amount_short);
  // Choosing another marker moves the chart's guide and the callout.
  const other = chips.find((e) => e.day !== lowestEvent.day && e.kind === "payroll") ?? chips.find((e) => e.day !== lowestEvent.day)!;
  await at(other.day).click();
  await expect(page.getByTestId("hv2-marker-callout")).toHaveAttribute("data-day", String(other.day));
  await expect(page.getByTestId("hv2-marker-callout")).toContainText(other.explain);
  await expect(page.getByTestId("home-chart")).toHaveAttribute("data-day", String(other.day));
  await page.getByTestId("home-lowest-point").click();
  await expect(page.getByTestId("home-chart")).toHaveAttribute("data-day", String(cash.lowest_day));
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
  // The alert row is not here: the recommendation card is the alert (it is shown only without a plan card, see below).
  await expect(page.getByTestId("home-worklist-alert")).toHaveCount(0);
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
  // A row the server marks Critical or Caution wears that severity (a red or amber edge, a faint tint, its word as a tag); a normal row is plain white.
  const sev = w.needs_you[0].severity;
  const tone = sev === "CRITICAL" ? "bad" : sev === "CAUTION" ? "warn" : null;
  if (tone) {
    await expect(rows.first()).toHaveAttribute("data-tone", tone);
    await expect(rows.first().getByTestId("hv2-row-tag")).toHaveText(en[`hv2.sev.${sev}` as "hv2.sev.CRITICAL"]);
  } else {
    expect(await rows.first().locator("a").evaluate((n) => getComputedStyle(n).backgroundColor)).toBe("rgb(255, 255, 255)");
  }
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

test("round four: the worklist is a fixed-column table: the same columns on every row and under the header, 56 px rows, a one-line next step with its whole sentence in title, group headings under All, the pill never moving for Select", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, { offer: true });
  const w = worklistOffer.en;
  const rows = page.getByTestId("home-worklist-row");
  const n = await rows.count();
  expect(n).toBeGreaterThan(0);
  // Group headings: 12 px uppercase, the group's name and its count; only the groups that have rows.
  const heading = page.getByTestId("hv2-group-heading");
  await expect(heading).toHaveCount(w.needs_you.length && w.waiting.length ? 2 : 1);
  await expect(heading.first()).toHaveText(`Needs you (${w.needs_you.length})`);
  expect(await heading.first().evaluate((n) => [getComputedStyle(n).fontSize, getComputedStyle(n).textTransform])).toEqual(["12px", "uppercase"]);
  // The same columns on every row and under the header: x of the subject, the next step, the pill and the select cell; widths 36 : 44 : 20 of the table less the select column.
  const cols = async (row: ReturnType<typeof rows.nth>) => ({
    subject: (await row.getByTestId("hv2-row-subject").boundingBox())!,
    next: (await row.getByTestId("hv2-row-next").boundingBox())!,
    status: (await row.getByTestId("hv2-row-status").boundingBox())!,
    select: (await row.getByTestId("hv2-row-select-cell").boundingBox())!,
    row: (await row.boundingBox())!,
  });
  const first = await cols(rows.first());
  for (let i = 0; i < n; i++) {
    const c = await cols(rows.nth(i));
    expect(Math.round(c.row.height), `row ${i} height`).toBe(56);
    expect(Math.abs(c.subject.x - first.subject.x), `row ${i} subject x`).toBeLessThan(1);
    expect(Math.abs(c.next.x - first.next.x), `row ${i} next x`).toBeLessThan(1);
    expect(Math.abs(c.status.x + c.status.width - (first.status.x + first.status.width)), `row ${i} status right edge`).toBeLessThan(1);
    expect(Math.abs(c.next.width - first.next.width)).toBeLessThan(1);
    expect(Math.round(c.select.width), "the chevron column").toBe(32);
  }
  const ratio = first.subject.width / first.next.width;
  expect(ratio).toBeGreaterThan(0.7);
  expect(ratio).toBeLessThan(0.95); // 36 : 44
  // The head's labels line up with their columns, Status at the right.
  const head = page.getByTestId("hv2-work-head");
  const [hDeal, hNext, hStatus] = await Promise.all(["Customer / deal", "Next step", "Status"].map(async (t) => (await head.getByText(t, { exact: true }).boundingBox())!));
  expect(Math.abs(hDeal.x - first.subject.x)).toBeLessThan(1);
  expect(Math.abs(hNext.x - first.next.x)).toBeLessThan(1);
  expect(Math.abs(hStatus.x + hStatus.width - (first.status.x + first.status.width))).toBeLessThan(1);
  // Hierarchy: the subject 15 px semibold, the next step 13 px muted on ONE line with its whole sentence in `title`; the pill is not moved by Select.
  const one = rows.first();
  expect(await one.getByTestId("hv2-row-subject").evaluate((n) => [getComputedStyle(n).fontSize, getComputedStyle(n).fontWeight])).toEqual(["15px", "600"]);
  const next = one.getByTestId("hv2-row-next");
  expect(await next.evaluate((n) => [getComputedStyle(n).fontSize, getComputedStyle(n).whiteSpace, getComputedStyle(n).textOverflow])).toEqual(["13px", "nowrap", "ellipsis"]);
  await expect(next).toHaveAttribute("title", w.needs_you[0].consequence_text);
  const pillBefore = (await one.getByTestId("home-row-status").boundingBox())!;
  await one.getByRole("link").hover();
  const pillAfter = (await one.getByTestId("home-row-status").boundingBox())!;
  expect(pillAfter.x).toBe(pillBefore.x);
  expect(pillAfter.y).toBe(pillBefore.y);
  // Below lg the rows are two lines at a fixed 64 px (subject and status, then the next step); the chevron stays at the right edge.
  await page.setViewportSize({ width: 820, height: 1000 });
  await expect(page.getByTestId("hv2-work-head")).toBeHidden();
  for (let i = 0; i < n; i++) expect(Math.round((await rows.nth(i).boundingBox())!.height), `phone row ${i}`).toBe(64);
  await expect(rows.first().getByTestId("row-chevron")).toBeVisible();
  const [s1, n1] = await Promise.all([rows.first().getByTestId("hv2-row-subject").boundingBox(), rows.first().getByTestId("hv2-row-next").boundingBox()]);
  expect(n1!.y).toBeGreaterThan(s1!.y + s1!.height - 1);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
  // The Customers tab is the same rows.
  await page.getByTestId("home-tab-customers").click();
  await expect(page.getByTestId("hv2-group-heading")).toHaveCount(0);
});

test("the upcoming cash movements are the rail's nearest events, and the way to the forecast; there is no tool-tile footer under the worklist", async ({ page }) => {
  await open(page, { offer: true });
  // The server's `home_v2.upcoming`: the three nearest movements of the books, label, short signed figure, when and the direction.
  const events = homeOffer.en.home_v2.upcoming;
  expect(events.length).toBe(3);
  const rows = page.getByTestId("hv2-upcoming-row");
  await expect(rows).toHaveCount(events.length);
  for (const [i, e] of events.entries()) {
    await expect(rows.nth(i)).toContainText(e.amount_display);
    await expect(rows.nth(i)).toContainText(e.when);
    await expect(rows.nth(i)).toContainText(e.label);
    await expect(rows.nth(i)).toHaveAttribute("data-kind", e.kind);
  }
  await expect(page.getByTestId("home-chart-full")).toHaveAttribute("href", "/cash");
  await expect(page.getByTestId("home-chart-full")).toContainText("Explore company forecast");
  // The owner decided against the deal tool tiles (Home's strip of approvals, sandbox, loans and attach): none is drawn; those routes are the rail's.
  await expect(page.getByTestId("home-tools")).toHaveCount(0);
  await expect(page.getByTestId("home-v2-links")).toHaveCount(0);
  for (const route of ["documents", "whatif", "capex", "approvals"]) await expect(page.getByTestId(`hv2-foot-${route}`)).toHaveCount(0);
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
  await expect(page.getByTestId("home-worklist-alert")).toHaveCount(0);
  await expect(page.getByTestId("hv2-action")).toBeVisible();
  await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveText("0");
  // Nothing in the queue: the server's alert-aware words when it sends them ("Nothing else needs you." while the plan waits for the owner's go), else the plain ones.
  const empty = (worklistDay0.en as typeof worklistDay0.en & { needs_you_empty_text?: string | null }).needs_you_empty_text;
  await expect(page.getByTestId("home-worklist-empty")).toContainText(empty ?? "All caught up.");
  await expect(page.getByTestId("home-kpi-funding-value")).toHaveText(homeDay0.en.home_v2.kpis.funding.value_display);
});

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
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible(); // the customer card sits beside the cash card, as the default's left pair
  await expect(page.getByTestId("hv2-outlook-card")).toHaveCount(0);
  await expect(page.getByTestId("home-worklist-alert")).toHaveCount(0);
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "held");
  await expect(page.getByTestId("hv2-band")).toBeVisible();
  await expect(page.getByTestId("home-action-back")).toHaveText(`Review ${homeOffer.en.home_v2.kpis.funding.value_display} funding plan`);
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
  await expect(page.getByTestId("home-check-plan")).toBeVisible();
  await page.goto("/?customer=BUYER-1");
  await page.getByTestId("focus-all").click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/?customer=BUYER-1");
  await page.getByTestId("home-action-back").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("home-check-plan")).toBeVisible();
});

test("a Home deal row opens that deal on the Deals page with the selection keys and from=home; Back to Home returns", async ({ page }) => {
  await open(page, { offer: true });
  const row = page.getByTestId("home-worklist-row").first();
  await expect(row.getByRole("link")).toHaveAttribute("href", `/deals?customer=BUYER-1&decision=${encodeURIComponent(DECISION)}&from=home`);
  await row.getByRole("link").click();
  // The deal is on the Deals page, never in the Home: the address carries the selection keys and the origin.
  await expect(page).toHaveURL(new RegExp(`/deals\\?customer=BUYER-1&decision=${encodeURIComponent(DECISION)}&from=home$`));
  expect(query(page).get("from")).toBe("home");
  await expect(page.getByTestId("deal-page")).toBeVisible();
  await expect(page.getByTestId("home-deal-focus")).toHaveCount(0);
  await expect(page.getByTestId("home-v2")).toHaveCount(0);
  // The way back is the server's words ("Back to Home", from `context.back`), and it returns to the Home overview.
  const back = page.getByTestId("queue-back");
  await expect(back).toContainText("Back to Home");
  await expect(back).toHaveAttribute("href", "/");
  // "All deals" returns to the list of deals, still opened from the Home; the Home's way back stays.
  await page.getByTestId("deal-back-all").click();
  await expect(page.getByTestId("deals-list-view")).toBeVisible();
  await expect(page.getByTestId("queue-back")).toContainText("Back to Home");
  await page.getByTestId("queue-back").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("home-v2")).toBeVisible();
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
});

test("an older Home address that names a deal is opened on the Deals page; the Home keeps no deal view", async ({ page }) => {
  await open(page, { offer: true });
  await page.goto(DEAL);
  await expect(page).toHaveURL(new RegExp(`/deals\\?customer=BUYER-1&decision=${encodeURIComponent(DECISION)}&from=home$`));
  await expect(page.getByTestId("deal-page")).toBeVisible();
  // None of the Home's former deal view remains in the Home.
  await page.goto("/?customer=BUYER-1");
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  for (const id of ["home-deal-focus", "hv2-deal-chart", "hv2-compare-toggle", "hv2-chart-toggle", "deal-open"]) await expect(page.getByTestId(id)).toHaveCount(0);
  await expect(page.getByTestId("hv2-context")).toContainText("Customer context");
  await expect(page.getByTestId("hv2-context")).not.toContainText("Deal context");
});

test("back and forward restore the selections, a reload keeps them, and a deal row leaves the Home for the Deals page", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.getByTestId("hv2-focus-rows-fold").locator("> summary").click();
  // A deal in the customer's open rows is opened on the Deals page, with the origin.
  await page.getByTestId("focus-rows").getByRole("link").click();
  await expect(page).toHaveURL(/\/deals\?.*decision=.*&from=home/);
  await expect(page.getByTestId("deal-page")).toBeVisible();
  // Back goes to the customer, back again to the company.
  await page.goBack();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  expect(query(page).get("decision")).toBeNull();
  await page.goBack();
  await expect(page.getByTestId("home-customer-focus")).toHaveCount(0);
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
  await page.goForward();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  expect(await page.evaluate(() => Object.keys(localStorage).filter((k) => /customer|decision|scenario|compare/i.test(k)))).toEqual([]);
});

test("nothing in Business mode is an id, a code or a day number; every figure and its qualifier is at least 13 px", async ({ page }) => {
  await open(page, { offer: true });
  const prose = await proseOf(page);
  expect(prose).not.toMatch(/\bday\s+\d/i);
  expect(prose).not.toMatch(/BUYER-\d|OFF-[0-9a-f]|ALERT-|deal:|NEEDS_YOU|CRITICAL|PROPOSED/);
  for (const url of ["/", "/?customer=BUYER-1", "/?expand=1"]) {
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
        if (el.closest("[data-testid=hv2-group-heading]")) continue; // the worklist's 12 px uppercase section rows are not a financial qualifier
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
  await expect(page.getByTestId("hv2-plan-pill")).toHaveText("计划中");
  await expect(page.getByTestId("home-action-title")).toHaveText(v2.action.title);
  await expect(page.getByTestId("home-action-eyebrow")).toHaveText("我们的建议");
  await expect(page.getByTestId("hv2-approval")).toHaveText(v2.action.approval_text!);
  await expect(page.getByTestId("hv2-outlook-expand")).toHaveText("展开");
  await page.getByTestId("hv2-outlook-expand").click();
  const lowestEvent = homeOffer.zh.cash.events_rail.find((e) => e.day === homeOffer.zh.cash.lowest_day)!;
  await page.locator(`[data-testid^="hv2-marker-"][data-day="${lowestEvent.day}"]`).click();
  await expect(page.getByTestId("hv2-marker-callout")).toContainText(lowestEvent.explain);
  await expect(page.getByTestId("home-legend")).toContainText("取决于方案执行");
  await expect(page.getByTestId("hv2-forecast-close")).toHaveText("收起");
  await page.getByTestId("hv2-forecast-close").click();
  const w = worklistOffer.zh;
  await expect(page.getByTestId("hv2-summary")).toHaveText(homeOffer.zh.home_v2.summary_text!.replace(/^[^.。]*[.。]\s*/, ""));
  await expect(page.getByTestId("home-worklist-row").first()).toContainText(w.needs_you[0].subject_text);
  await expect(page.getByTestId("home-worklist-row").first().getByTestId("home-row-status")).toHaveText(w.needs_you[0].status_text);
  await expect(page.getByTestId("home-worklist-search")).toHaveAttribute("placeholder", "搜索客户或交易");
  await expect(page.getByTestId("home-tab-all")).toContainText("全部");
  await expect(page.getByTestId("home-tab-waiting")).toContainText("等待中");
  await expect(page.getByTestId("hv2-upcoming")).toContainText("即将发生的现金变动");
  await expect(page.getByTestId("hv2-foot-documents")).toHaveCount(0); // no tool tiles
  // A deal row opens on the Deals page, whose way back is the server's words in Chinese.
  await expect(page.getByTestId("home-worklist-row").first().getByRole("link")).toHaveAttribute("href", /\/deals\?customer=BUYER-1&decision=.*&from=home$/);
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("deal-page")).toBeVisible();
  await expect(page.getByTestId("queue-back")).toContainText("返回首页");
  await page.goto("/?customer=BUYER-1");
  const customer = focusOffer.zh.customers["BUYER-1"];
  await expect(page.getByTestId("focus-title")).toHaveText(customer.name);
  for (const f of customer.figures) if (f.state && f.state !== "none") await expect(page.getByTestId(`focus-figure-${f.key}-state`)).toHaveText(f.state_text!);
  await expect(page.getByTestId("home-action-back")).toHaveText(`查看 ${homeOffer.zh.home_v2.kpis.funding.value_display} 融资方案`);
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
    await expect(page.getByTestId("home-check-plan")).toBeVisible();
    const primary = (await page.getByTestId("home-check-plan").boundingBox())!;
    const tabBar = (await page.getByTestId("tab-bar").boundingBox())!;
    expect(primary.y + primary.height, `inside the first ${h} px`).toBeLessThanOrEqual(h);
    expect(primary.y + primary.height, "and not behind the tab bar").toBeLessThanOrEqual(tabBar.y);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  // No sheet and no opener: the worklist is on the page; a row is two lines, the subject with the status pill and then its next step (the head of the table is hidden).
  await expect(page.getByTestId("home-worklist-open")).toHaveCount(0);
  await expect(page.getByTestId("home-worklist-panel")).toBeVisible();
  const row = page.getByTestId("home-worklist-row").first();
  await row.scrollIntoViewIfNeeded();
  const subject = (await row.getByText(worklistOffer.en.needs_you[0].subject_text).boundingBox())!;
  const pill = (await row.getByTestId("home-row-status").boundingBox())!;
  // Below lg a row is two lines: the subject and the pill share the first, the next step is the second.
  expect(Math.abs(pill.y + pill.height / 2 - (subject.y + subject.height / 2))).toBeLessThan(14);
  expect((await row.getByTestId("hv2-row-next").boundingBox())!.y).toBeGreaterThan(subject.y + subject.height - 1);
  expect(pill.x + pill.width).toBeLessThanOrEqual(390);
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
});

test("phone: a deal row opens the deal on the Deals page; Back to Home returns to the cards; nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { offer: true });
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("deal-page")).toBeVisible();
  await expect(page).toHaveURL(/\/deals\?.*decision=.*&from=home/);
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
  await expect(page.getByTestId("queue-back")).toContainText("Back to Home");
  await page.getByTestId("queue-back").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
});

test("a customer with a financed invoice: the card shows the net after repayment in the server's word, the breakdown with its shares and the one filled button View invoice", async ({ page }) => {
  await open(page, { offer: true });
  await runPlan(page, ALERT);
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "covered");
  await page.goto("/?customer=BUYER-1");
  const row = receivablesAfter.en.rows[0] as unknown as { receivable_id: string; net_after_repayment_display: string; collection_due_text: string; face_display: string; breakdown: { label: string; amount_display: string; share_text: string }[] };
  expect(row.net_after_repayment_display).toMatch(/^about /);
  await expect(page.getByTestId("hv2-invoice")).toHaveCount(1);
  await expect(page.getByTestId("hv2-invoice-net")).toContainText("Net cash after repayment");
  await expect(page.getByTestId("hv2-invoice-net")).toContainText(row.net_after_repayment_display);
  await expect(page.getByTestId("hv2-invoice-value")).toContainText(row.face_display);
  await expect(page.getByTestId("hv2-invoice-due")).toContainText(row.collection_due_text);
  for (const [i, r] of row.breakdown.entries()) {
    await expect(page.getByTestId(`hv2-invoice-breakdown-row-${i}`)).toContainText(r.label);
    await expect(page.getByTestId(`hv2-invoice-breakdown-amount-${i}`)).toHaveText(r.amount_display);
    await expect(page.getByTestId(`hv2-invoice-breakdown-share-${i}`)).toHaveText(r.share_text);
  }
  await expect(page.getByTestId("hv2-invoice-breakdown-bar")).toBeVisible();
  const view = page.getByTestId("hv2-invoice-view");
  await expect(view).toHaveText("View invoice");
  await expect(view).toHaveAttribute("href", `/receivables?invoice=${row.receivable_id}`);
  // One filled button in the state: the card's (the band above is outlined).
  expect(await filledBrand(page)).toBe(1);
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "covered"); // nothing of the company's waits: the covered card (its way to the deals is outlined), no band
});

test("phone: the collection state, a customer's row opens its card and its context under the worklist, in one column", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  const a = (await page.getByTestId("home-customer-focus").boundingBox())!;
  const b = (await page.getByTestId("hv2-cash-card").boundingBox())!;
  const c = (await page.getByTestId("hv2-context").boundingBox())!;
  expect(b.y).toBeGreaterThan(a.y + a.height - 1);
  expect(c.y).toBeGreaterThan(b.y);
  expect(await overflowX(page)).toBeLessThanOrEqual(0);
});

test("a selected customer: Dismiss and Escape restore the overview and clear the address; the context panel replaces the upcoming movements and the cards come back", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("hv2-context")).toBeVisible();
  await expect(page.getByTestId("hv2-upcoming")).toHaveCount(0);
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible(); // a customer: the customer card beside the company's cash card
  await page.getByTestId("focus-all").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("hv2-context")).toHaveCount(0);
  await expect(page.getByTestId("hv2-upcoming")).toBeVisible();
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
  await expect(page.getByTestId("home-check-plan")).toBeVisible();
  await page.goto("/?customer=BUYER-1");
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
  // With the forecast open, Escape closes it first; a second Escape clears a selection.
  await page.goto("/?customer=BUYER-1&expand=1");
  await expect(page.getByTestId("hv2-forecast")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("hv2-forecast")).toHaveCount(0);
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("home-customer-focus")).toHaveCount(0);
  // The context panel: the stage as the customer's own pill, Customer profile, and the evidence fold with the overview's own sentence.
  await page.goto("/?customer=BUYER-1");
  const ctx = page.getByTestId("hv2-context");
  await expect(ctx).toContainText("Customer context");
  await expect(ctx.getByTestId("focus-open-customer")).toHaveText("Customer profile");
  const fold = page.getByTestId("hv2-context-evidence");
  await expect(fold).toContainText("Agreement & supporting evidence");
  await expect(page.getByTestId("hv2-context-evidence-text")).toBeHidden();
  await fold.locator("> summary").click();
  await expect(page.getByTestId("hv2-context-evidence-text")).not.toBeEmpty();
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

test("accessibility: no axe violations on the default Home, expanded, and with the customer, at 1440 and at 390", async ({ page }) => {
  await open(page, { offer: true });
  for (const url of ["/", "/?expand=1", "/?customer=BUYER-1"]) {
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
    expect(Math.abs(collapsed.worklistLeft), `${width} left edge`).toBeLessThan(1);
    expect(Math.abs(collapsed.upcomingRight), `${width} right edge`).toBeLessThan(1);
    expect(await overflowX(page)).toBeLessThanOrEqual(0);
    // The rail's own 56 px: the page fills what is left, to 1680.
    expect(collapsed.main).toBe(Math.min(width - 56, 1680));
    expect(pinned.main).toBe(Math.min(width - 200, 1680));
  }
  expect(seen[1680].collapsed.row - seen[1680].pinned.row).toBeGreaterThanOrEqual(130);
  expect(seen[1680].collapsed.row).toBeGreaterThan(seen[1440].collapsed.row);
  expect(seen[1920].collapsed.main).toBe(1680);
});

// ---------------------------------------------------------------- round two: sizes, selection, the ways back

// The cash card carries the funding ring ("Where your cash comes from"): the three cards are 360 px tall at most (the tallest decides).
const CARD_MAX = 360;
test("round four sizes at 1440: the three cards are 360 px tall at most (the tallest decides), padded 16 px, titles 16 px, figures 32 px and the planned amount 36 px; rows 56 px and 44 px; nothing wraps to a third line", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, { offer: true });
  const ids = ["hv2-cash-card", "hv2-action", "hv2-outlook-card"];
  for (const id of ids) {
    const box = (await page.getByTestId(id).boundingBox())!;
    expect(box.height, `${id} height`).toBeLessThanOrEqual(CARD_MAX);
    expect(await page.getByTestId(id).evaluate((el) => getComputedStyle(el).paddingTop), `${id} padding`).toBe("16px");
  }
  const px = (id: string) => page.getByTestId(id).evaluate((el) => getComputedStyle(el).fontSize);
  expect(await px("hv2-metric-cash-label")).toBe("16px");
  expect(await px("home-action-eyebrow")).toBe("16px");
  expect(await px("hv2-metric-lowest-label")).toBe("16px");
  expect(await px("home-kpi-cash-value")).toBe("32px");
  expect(await px("home-kpi-lowest-value")).toBe("32px");
  expect(await px("home-kpi-funding-value")).toBe("36px");
  expect(await px("home-action-title")).toBe("18px");
  expect(await px("hv2-headline")).toBe("32px");
  expect(await px("hv2-summary")).toBe("15px");
  // The worklist rows are 56 px (fixed) and the upcoming movements 44 px.
  for (const r of await page.getByTestId("home-worklist-row").all()) expect(Math.round((await r.boundingBox())!.height)).toBe(56);
  expect(Math.round((await page.getByTestId("hv2-upcoming-row").first().boundingBox())!.height)).toBe(39); // compact rows (min-h-9 and 4 px of air)
  // The middle card's order: the eyebrow with the Planned pill, the headline, the amount with the cost at its right, the consequence, the funding bar, the approval line, the actions.
  const order = await Promise.all(["home-action-eyebrow", "home-action-title", "home-kpi-funding-value", "hv2-action-facts", "home-action-text", "hv2-funding-row", "hv2-approval", "home-attention-run"].map(async (id) => (await page.getByTestId(id).boundingBox())!.y));
  expect([...order].sort((x, y) => x - y)).toEqual(order);
  // No text block of the three cards is more than two lines at 1440; at 1280 the recommendation's consequence sentence may take a third line, but nothing is clipped or overlaps.
  for (const width of [1440, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    const lines = await page.evaluate(([cards, most]) => {
      const out: string[] = [];
      for (const id of cards) {
        for (const el of Array.from(document.querySelectorAll(`[data-testid="${id}"] p, [data-testid="${id}"] h2`))) {
          const style = getComputedStyle(el);
          const lh = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.3;
          const rows = Math.round(el.getBoundingClientRect().height / lh);
          if (rows > (most as number) && (el.textContent ?? "").trim()) out.push(`${id}: ${rows} lines: ${(el.textContent ?? "").slice(0, 40)}`);
        }
      }
      return out;
    }, [ids, width === 1280 ? 3 : 2] as const);
    expect(lines, `${width}`).toEqual([]);
    for (const id of ids) {
      const clipped = await page.getByTestId(id).evaluate((el) => el.scrollHeight - el.clientHeight);
      expect(clipped, `${id} clips nothing at ${width}`).toBeLessThanOrEqual(1);
    }
    for (const id of ids) expect((await page.getByTestId(id).boundingBox())!.height, `${id} at ${width}`).toBeLessThanOrEqual(CARD_MAX);
  }
});

test("every worklist row carries a chevron (quiet, ink on hover and focus, filled on the selected row); hover never changes the cards; a click or Enter on a customer selects it, on a deal opens it on Deals", async ({ page }) => {
  await open(page, { offer: true });
  const first = page.getByTestId("home-worklist-row").first();
  const link = first.getByRole("link");
  const chevron = first.getByTestId("row-chevron");
  const count = await page.getByTestId("home-worklist-row").count();
  await expect(page.getByTestId("home-worklist-row").getByTestId("row-chevron")).toHaveCount(count);
  await expect(chevron).toHaveAttribute("aria-hidden", "true");
  await expect(first.getByTestId("hv2-row-select")).toHaveCount(0);
  const quiet = await chevron.evaluate((el) => getComputedStyle(el).color);
  const before = await Promise.all(["hv2-cash-card", "hv2-action", "hv2-outlook-card"].map((id) => page.getByTestId(id).boundingBox()));
  await link.hover();
  await expect.poll(() => chevron.evaluate((el) => getComputedStyle(el).color)).not.toBe(quiet);
  await page.waitForTimeout(400);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
  await expect(page.getByTestId("hv2-stage")).toHaveAttribute("data-mode", "ov");
  expect(await Promise.all(["hv2-cash-card", "hv2-action", "hv2-outlook-card"].map((id) => page.getByTestId(id).boundingBox()))).toEqual(before);
  await page.mouse.move(5, 5);
  await expect.poll(() => chevron.evaluate((el) => getComputedStyle(el).color)).toBe(quiet);
  // Keyboard focus strengthens it too, and Enter selects.
  await page.getByTestId("home-tab-needs_you").focus();
  for (let i = 0; i < 6 && !(await link.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press("Tab");
  await expect(link).toBeFocused();
  await expect.poll(() => chevron.evaluate((el) => getComputedStyle(el).color)).not.toBe(quiet);
  await page.keyboard.press("Enter");
  // A deal row opens its deal on the Deals page.
  await expect(page).toHaveURL(/\/deals\?.*decision=.*&from=home/);
  await expect(page.getByTestId("deal-page")).toBeVisible();
  await page.goBack();
  // A customer row is selected in place; the selected row's chevron is filled (an ink disc).
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.getByTestId("home-tab-customers").click();
  const selected = page.getByTestId("home-worklist-panel").getByTestId("home-worklist-row").first().getByTestId("row-chevron");
  await expect(selected).toHaveAttribute("data-selected", "true");
  expect(await selected.evaluate((el) => getComputedStyle(el).backgroundColor)).not.toBe("rgba(0, 0, 0, 0)");
});

test("selecting a customer transforms the cards: the company line, the customer card beside the cash card, the context panel; the three ways back and the browser's Back restore the overview", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("hv2-stage")).toHaveAttribute("data-mode", "sel");
  await expect(page.getByTestId("hv2-action")).toHaveCount(0);
  await expect(page.getByTestId("hv2-outlook-card")).toHaveCount(0);
  // The company line: the cash and the minimum reserve in the server's words, and the way to the plan with its amount.
  const cash = homeOffer.en.home_v2.kpis.cash_available;
  const band = page.getByTestId("hv2-band");
  await expect(band).toContainText(cash.value_display);
  await expect(band).toContainText(cash.buffer.min_display);
  await expect(page.getByTestId("home-action-back")).toHaveText(`Review ${homeOffer.en.home_v2.kpis.funding.value_display} funding plan`);
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
  await expect(page.getByTestId("hv2-context")).toBeVisible();
  await expect(page.getByTestId("hv2-context-stage")).toBeVisible();
  await expect(page.getByTestId("hv2-context").getByTestId("focus-open-customer")).toBeVisible();
  await expect(page.getByTestId("hv2-foot-separate")).toHaveText("Company cash stays separate from selected deals.");
  // Way back 1: the Dismiss on the card.
  const back = async () => {
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByTestId("hv2-stage")).toHaveAttribute("data-mode", "ov");
    await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
    await expect(page.getByTestId("hv2-upcoming")).toBeVisible();
    await expect(page.getByTestId("home-check-plan")).toBeVisible();
  };
  await page.getByTestId("focus-all").click();
  await back();
  // Way back 2: "Back to overview" at the top of the context panel.
  await page.goto("/?customer=BUYER-1");
  await expect(page.getByTestId("hv2-context-back")).toContainText("Back to overview");
  await page.getByTestId("hv2-context-back").click();
  await back();
  // Way back 3: Escape. And the browser's Back, which restores the selection and then the overview.
  await page.goto("/?customer=BUYER-1");
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.keyboard.press("Escape");
  await back();
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await page.goBack();
  await back();
  await page.goForward();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
});

test("what you are owed, by customer: its own card under the upcoming movements on the default page and on every selection (the same place), a ring of the customers' rows with every slice and row a button that selects that customer, the selected slice lifted 4 px", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const rowsOf = [
    { customer_id: "BUYER-1", name: "Foshan Home Retail Co.", short: "Foshan", outstanding_display: "¥420,000", share_text: "54.5% of what you are owed" },
    { customer_id: "BUYER-2", name: "Dongguan Office Supplies Ltd.", short: "Dongguan", outstanding_display: "¥200,000", share_text: "26.0% of what you are owed" },
    { customer_id: "BUYER-3", name: "Zhuhai Kitchenware Wholesale Co.", short: "Zhuhai", outstanding_display: "¥150,000", share_text: "19.5% of what you are owed" },
  ];
  const base = customersOffer.en.customers;
  const customers = rowsOf.map((r, i) => ({ ...base[Math.min(i, base.length - 1)], ...r }));
  await page.context().addInitScript(([key, patch]) => sessionStorage.setItem(key as string, JSON.stringify(patch)), ["tl-mock-customers-patch", { customers }] as const);
  await open(page, { offer: true });
  const card = page.getByTestId("hv2-owed-card");
  // The default page: below "Upcoming cash movements", in the right column; nothing is lifted and the centre says nothing yet.
  await expect(card).toBeVisible();
  await expect(card.getByTestId("hv2-owed-title")).toHaveText("What you are owed, by customer");
  const place = async (above: string) => {
    const [c, a] = await Promise.all([card.boundingBox(), page.getByTestId(above).boundingBox()]);
    return { x: Math.round(c!.x), w: Math.round(c!.width), below: c!.y - (a!.y + a!.height) };
  };
  const onDefault = await place("hv2-upcoming");
  expect(onDefault.below).toBeGreaterThan(0);
  expect(onDefault.below).toBeLessThan(24);
  await expect(card.getByTestId("hv2-owed-centre")).toHaveCount(0);
  for (const [i, r] of rowsOf.entries()) {
    await expect(card.getByTestId(`hv2-owed-row-${i}`)).toContainText(r.name);
    await expect(card.getByTestId(`hv2-owed-amount-${i}`)).toHaveText(r.outstanding_display);
    await expect(card.getByTestId(`hv2-owed-share-${i}`)).toHaveText(r.share_text);
    await expect(card.getByTestId(`hv2-owed-slice-${i}`)).toHaveAttribute("aria-pressed", "false");
  }
  // A slice on the default page SELECTS that customer: the address changes, the customer card and the cash card take the stage, the donut has not moved.
  await card.getByTestId("hv2-owed-slice-1").dispatchEvent("click");
  await expect(page).toHaveURL(/customer=BUYER-2/);
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
  const onCustomer = await place("hv2-context");
  expect(onCustomer.x).toBe(onDefault.x);
  expect(onCustomer.w).toBe(onDefault.w);
  expect(onCustomer.below).toBeLessThan(24);
  // The selected customer's slice is lifted 4 px (a larger radius) and named in the centre: short name, amount, percent.
  const centre = card.getByTestId("hv2-owed-centre");
  await expect(centre).toContainText("Dongguan");
  await expect(centre).toContainText("¥200,000");
  await expect(centre).toContainText("26.0%");
  const radius = (i: number) => card.getByTestId(`hv2-owed-slice-${i}`).getAttribute("r").then(Number);
  expect((await radius(1)) - (await radius(0))).toBeCloseTo(4, 0);
  // Another row selects that customer; the keyboard presses a slice.
  await card.getByTestId("hv2-owed-row-2").getByRole("button").click();
  await expect(page).toHaveURL(/customer=BUYER-3/);
  await expect(card.getByTestId("hv2-owed-centre")).toContainText("19.5%");
  await card.getByTestId("hv2-owed-slice-0").focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/customer=BUYER-1/);
  // The company's customer again: the same place under the context panel, and the centre names that customer.
  await page.goto("/?customer=BUYER-1");
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  const onDeal = await place("hv2-context");
  expect(onDeal.x).toBe(onDefault.x);
  expect(onDeal.w).toBe(onDefault.w);
  expect(onDeal.below).toBeLessThan(24);
  await expect(card.getByTestId("hv2-owed-centre")).toContainText("Foshan");
  // Dismiss restores the default, and the card has not moved.
  await page.getByTestId("focus-all").click();
  await expect(page.getByTestId("hv2-stage")).toHaveAttribute("data-mode", "ov");
  await expect(page.getByTestId("hv2-upcoming")).toBeVisible();
  expect((await place("hv2-upcoming")).x).toBe(onDefault.x);
  await expect(card.getByTestId("hv2-owed-centre")).toHaveCount(0);
});

test("what you are owed with fewer than two customers owed is the one figure, no ring, still a button that selects the customer", async ({ page }) => {
  await open(page, { offer: true }); // the recording has one customer owing
  const card = page.getByTestId("hv2-owed-card");
  const only = customersOffer.en.customers[0];
  await expect(card).toHaveAttribute("data-ring", "false");
  await expect(card.locator("svg")).toHaveCount(0);
  await expect(card.getByTestId("hv2-owed-one")).toContainText(only.outstanding_display);
  await expect(card.getByTestId("hv2-owed-one")).toContainText(only.name);
  await card.getByTestId("hv2-owed-one").click();
  await expect(page).toHaveURL(/customer=BUYER-1/);
});

test("Upcoming cash movements has no overdue row when nothing is overdue (the live matrix holds the busy books' row, its figure, its count and its link)", async ({ page }) => {
  await open(page, { offer: true });
  await expect(page.getByTestId("hv2-upcoming")).toBeVisible();
  await expect(page.getByTestId("hv2-upcoming-overdue-row")).toHaveCount(0);
  await expect(page.getByTestId("hv2-upcoming-row")).toHaveCount(homeOffer.en.home_v2.upcoming!.length);
});

// The customer view at four widths keeps the customer card with the cash card (no deal view in the Home); a deal row leaves for the Deals page without a sideways scroll.
for (const [width, height] of [[1440, 900], [1100, 800], [820, 1100], [390, 844]] as const) {
  test(`the customer view at ${width}: the customer card with the cash card and the owed card; a deal row leaves for Deals`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await open(page, { offer: true });
    await page.goto("/?customer=BUYER-1");
    await expect(page.getByTestId("home-customer-focus")).toBeVisible();
    await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
    await expect(page.getByTestId("hv2-deal-chart")).toHaveCount(0);
    await expect(page.getByTestId("hv2-owed-card")).toBeVisible();
    expect(await overflowX(page)).toBeLessThanOrEqual(0);
    await page.goto("/");
    await page.getByTestId("home-worklist-row").first().getByRole("link").click();
    await expect(page.getByTestId("deal-page")).toBeVisible();
    expect(await overflowX(page)).toBeLessThanOrEqual(0);
  });
}

test("reduced motion: the stage crossfades by opacity alone", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page, { offer: true });
  await page.goto("/?customer=BUYER-1");
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  const stage = page.getByTestId("hv2-stage");
  const t = await stage.evaluate((n) => [getComputedStyle(n).transitionProperty, getComputedStyle(n).transform]);
  expect(t[0]).toBe("opacity");
  expect(t[1]).toBe("none");
  await page.keyboard.press("Escape");
  await expect(stage).toHaveAttribute("data-mode", "ov");
});

test.describe("with motion allowed", () => {
  test.use({ reducedMotion: "no-preference" });
  test("the stage crossfades (opacity over 100 ms each way)", async ({ page }) => {
    await open(page, { offer: true });
    await page.goto("/?customer=BUYER-1");
    await expect(page.getByTestId("home-customer-focus")).toBeVisible();
    const stage = page.getByTestId("hv2-stage");
    expect(await stage.evaluate((n) => [getComputedStyle(n).transitionProperty, getComputedStyle(n).transitionDuration])).toEqual(["opacity", "0.1s"]);
    // Dismiss: the stage fades out, takes the overview, and fades in again.
    await page.getByTestId("focus-all").click();
    await expect(stage).toHaveAttribute("data-mode", "ov");
    await expect(stage).toHaveAttribute("data-fading", "false");
    await expect(page.getByTestId("hv2-cash-card")).toBeVisible();
  });
});

// ---------------------------------------------------------------- round three: a selection lands at the top of what changed

for (const [width, height] of [[1440, 900], [1100, 800], [820, 1100], [390, 844]] as const) {
  test(`a selection lands with the company line and the selected card at the top of the content, at ${width}: the page scrolls to them, never into the middle of the card; Dismiss scrolls back to the headline`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await open(page, { offer: true });
    await page.getByTestId("home-tab-customers").click();
    const row = page.getByTestId("home-worklist-row").last();
    await row.scrollIntoViewIfNeeded();
    await row.getByRole("link").click();
    await expect(page.getByTestId("home-customer-focus")).toBeVisible();
    await expect(page.getByTestId("hv2-stage")).toHaveAttribute("data-mode", "sel");
    await expect.poll(async () => page.evaluate(() => Math.round(document.getElementById("hv2-stage")!.getBoundingClientRect().top)), { message: "the stage lands under the sticky header" }).toBeLessThan(100);
    const m = await page.evaluate(() => {
      const header = document.querySelector("header")!.getBoundingClientRect();
      const band = document.getElementById("home-v2-action")!.getBoundingClientRect();
      const focus = document.getElementById("home-focus")!.getBoundingClientRect();
      const head = document.querySelector<HTMLElement>("[data-testid=hv2-headline]")!.getBoundingClientRect();
      return { header: Math.round(header.bottom), band: Math.round(band.top), focus: Math.round(focus.top), headBottom: Math.round(head.bottom), y: Math.round(scrollY) };
    });
    // The company line sits right under the header (its 16 px scroll margin), the card's top edge under it, the headline above both (scrolled away) and the page is not at the card's middle.
    expect(m.band - m.header).toBeGreaterThanOrEqual(0);
    expect(m.band - m.header).toBeLessThanOrEqual(24);
    expect(m.focus - m.header).toBeLessThanOrEqual(width < 600 ? 150 : 110);
    expect(m.headBottom).toBeLessThanOrEqual(m.band);
    expect(m.y).toBeGreaterThan(0);
    await expect(page.getByTestId("home-customer-focus")).toBeInViewport({ ratio: 0.5 });
    // Dismiss scrolls back to the top of the overview.
    await page.getByTestId("focus-all").click();
    await expect(page.getByTestId("hv2-stage")).toHaveAttribute("data-mode", "ov");
    await expect.poll(() => page.evaluate(() => Math.round(scrollY))).toBeLessThanOrEqual(2);
  });
}

test("browser Back and Forward between the overview and a selection land at the top of the selection again", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  await page.getByTestId("home-worklist-row").first().getByRole("link").click();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  const bandTop = () => page.evaluate(() => Math.round(document.getElementById("home-v2-action")!.getBoundingClientRect().top));
  await expect.poll(bandTop).toBeLessThan(100);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.goBack();
  await expect(page.getByTestId("hv2-stage")).toHaveAttribute("data-mode", "ov");
  await page.goForward();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await expect.poll(bandTop).toBeLessThan(100);
  // Another customer by the owed card: the page lands at the top again.
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.goBack();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.goForward();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await expect.poll(bandTop).toBeLessThan(100);
});

test("the selection paints at once: a row's reads start on hover and focus, so no skeleton shows and the card does not jump", async ({ page }) => {
  await open(page, { offer: true });
  await page.getByTestId("home-tab-customers").click();
  const link = page.getByTestId("home-worklist-row").first().getByRole("link");
  await link.hover();
  await link.click();
  await expect(page.getByTestId("home-customer-focus")).toBeVisible();
  await expect(page.getByText(en["hv2.focus.working"], { exact: true })).toHaveCount(0);
  const box = (await page.getByTestId("home-customer-focus").boundingBox())!;
  await page.waitForTimeout(500);
  expect(Math.abs((await page.getByTestId("home-customer-focus").boundingBox())!.height - box.height)).toBeLessThan(2);
});

test("until its read arrives the Home shows its own shape (a headline, the three cards, the worklist) and announces Loading; the canvas is never empty", async ({ page }) => {
  // Record, from the first paint, whether the loading shape was ever in the page before the Home itself.
  await page.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as { __seen: string[] }).__seen = seen;
    const look = () => {
      for (const id of ["home-loading", "home-v2"]) if (document.querySelector(`[data-testid="${id}"]`) && !seen.includes(id)) seen.push(id);
    };
    new MutationObserver(look).observe(document, { childList: true, subtree: true });
  });
  await page.goto("/");
  await expect(page.getByTestId("home-v2")).toBeVisible();
  const seen = await page.evaluate(() => (window as unknown as { __seen: string[] }).__seen);
  expect(seen[0], "the loading shape comes first").toBe("home-loading");
  expect(seen).toContain("home-v2");
  await expect(page.getByTestId("home-loading")).toHaveCount(0);
});
