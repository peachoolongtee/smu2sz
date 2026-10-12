import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { filledBrand, runPlan, walkStory } from "./helpers";
import day0 from "../mocks/home_summary_day0.json";
import day0Zh from "../mocks/home_summary_day0_zh.json";
import afterFund from "../mocks/home_summary_after_fund.json";
import afterFundZh from "../mocks/home_summary_after_fund_zh.json";

/**
 * The Home hybrid (board "Home E"): the position, the attention card, the picture with the event rail, the three cards.
 *
 * Every sentence below is read from the recorded home reads (mocks/home_summary_*.json, GET /home written by the API), so the words are the server's.
 * What no recording has is laid over the recorded read through the mock's session key `tl-mock-home-patch` (a test seam like `tl-mock-worth-fail`, see
 * lib/mock/handlers.ts `withHomePatch`): the late-payment stress (behind the API's exposure flag), an unreadable decision record (`attention.incomplete`), a
 * populated or multi-row deals card, a rail longer than the picture, and an older server with none of the hybrid's fields (set to null). Without the key the
 * read is exactly the recording, whose `stress_available` is false.
 */
const PATCH_KEY = "tl-mock-home-patch";

type Rec = typeof day0;
const rail = (r: Rec) => r.cash.events_rail;
const LOWEST = rail(day0).findIndex((e) => e.kind === "lowest");

async function overflowX(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

/** The late-payment stress as the API would send it (the plan line with the Foshan receipt 30 days later), built from the recorded plan line. */
function stressOf(lang: "en" | "zh") {
  const plan = day0.cash.plan_series as { day: number; closing_fen: number; closing_display: string; events: unknown[] }[];
  const late = plan.map((p) => {
    const fen = p.day >= 32 && p.day < 62 ? p.closing_fen - 42_000_000 : p.closing_fen;
    return { ...p, closing_fen: fen, closing_display: `¥${Math.round(fen / 100000)}k`, events: [] };
  });
  const lateLow = Math.min(...late.map((p) => p.closing_fen));
  return {
    delay_days: 30,
    buyer: lang === "zh" ? "佛山" : "Foshan",
    series: late,
    lowest_short: `¥${Math.round(lateLow / 100000)}k`,
    lowest_when: lang === "zh" ? "32 天后" : "in 32 days",
    breach_days: 14,
    need_short: "¥120k",
    // The sentences are the server's (a fixture written the way the API writes them): the page shows them as they are and composes none.
    text: lang === "zh" ? "现金将在 32 天后降至 -¥108k，有 14 天低于您的最低现金储备，还差 ¥120k。" : "Cash would fall to -¥108k in 32 days, below your minimum for 14 days, and ¥120k would be uncovered.",
    funding_text: lang === "zh" ? "FLOW 会先动用您信用额度的剩余部分。" : "FLOW would draw the rest of your credit line first.",
    net_later_text: lang === "zh" ? "晚到的款项到账后，现金回到 ¥312k。" : "Once the late payment arrives, cash is back to ¥312k.",
    assumption_text: lang === "zh" ? "假设佛山晚付 30 天，其余款项都按期到账。" : "Assumes Foshan pays 30 days after the due date, and every other payment arrives as scheduled.",
    window_days_needed: 62,
  };
}

/** Every field the hybrid added, set to null: what an older server sends. */
const OLDER_SERVER = {
  attention: null,
  funding_line: null,
  deals_card: null,
  receivables_card: null,
  changes_card: null,
  cash: { status_word: null, status_tone: null, headline_conditional: null, headline_note: null, assumptions: null, facts: null, events_rail: null, events_rail_days: null, counterfactual_series: null, counterfactual_label: null, stress_available: false, stress: null },
};

type Patch = Record<string, unknown> & { cash?: Record<string, unknown> };

/** The recorded opening books (day 0): the plan waits to be run. The language and the patch are set before the page loads. */
async function open(page: Page, { lang = "en", stress = false, patch = {} }: { lang?: "en" | "zh"; stress?: boolean; patch?: Patch } = {}) {
  const laid: Patch = { ...patch, cash: { ...(stress ? { stress_available: true, stress: stressOf(lang) } : {}), ...(patch.cash ?? {}) } };
  await page.context().addInitScript(
    ([key, value, l]) => {
      if (Object.keys(value as object).length) sessionStorage.setItem(key as string, JSON.stringify(value));
      localStorage.setItem("tl-lang", JSON.stringify({ lang: l }));
    },
    [PATCH_KEY, laid, lang] as const,
  );
  await page.goto("/");
  await expect(page.getByTestId("home-status")).toBeVisible();
  // The hybrid picture is measured after layout: wait for it to draw (unless the patch took its fields away).
  if (laid.cash && laid.cash.events_rail === null) return;
  await expect(page.getByTestId("home-event-picture")).toBeVisible();
  await expect(page.getByTestId("rail-mark-0")).toBeAttached();
}

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "mock-mode spec on the recorded story (the phone is measured inside it)");
});

test("section 1: the status word, one h1 with the conditional heading, the note, the assumptions and three facts", async ({ page }) => {
  await open(page);
  const c = day0.cash;
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(c.headline_conditional);
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "ACTION_NEEDED");
  await expect(page.getByTestId("home-status-word")).toHaveText("Action needed");
  await expect(page.getByTestId("home-read-when")).toHaveText("Read today");
  await expect(page.getByTestId("home-note")).toHaveText(c.headline_note);
  await expect(page.getByTestId("home-assumptions")).not.toHaveAttribute("open", "");
  await page.getByTestId("home-assumptions").locator("> summary").click();
  await expect(page.getByTestId("home-assumptions").locator("li")).toHaveText(c.assumptions);
  // Three tiles: label, the big figure, a note; the tone colours the figure only (red below the minimum, amber at zero room, nothing when fine).
  const tiles = page.getByTestId("home-facts").locator("> div");
  await expect(tiles).toHaveCount(3);
  for (const [i, f] of c.facts.entries()) {
    await expect(tiles.nth(i)).toContainText(f.label);
    await expect(page.getByTestId(`home-fact-${f.key}`)).toHaveText(f.value_short);
    await expect(tiles.nth(i)).toContainText(f.note);
  }
  await expect(page.getByTestId("home-fact-today")).toHaveText("¥400k");
  await expect(page.getByTestId("home-fact-today")).not.toHaveClass(/text-(warn|bad|ok)-fg/);
  await expect(page.getByTestId("home-fact-lowest")).toHaveClass(/text-warn-fg/);
  await expect(page.getByTestId("home-fact-lowest")).toHaveText("¥300k");
  // Business words: no codes, ids or day numbers; no demo control.
  await expect(page.locator("main")).not.toContainText(/\bDay \d|ALERT-|RI:|day-\d/);
  await expect(page.getByTestId("home-advance")).toHaveCount(0);
});

test("section 2: the plan is the one raised card and the page's only filled primary; first press asks, Cancel runs nothing, the second runs it", async ({ page }) => {
  await open(page);
  const a = day0.attention.items[0];
  const card = page.getByTestId("home-next-action");
  await expect(card).toHaveAttribute("data-alert", "ALERT-RESERVE-12");
  await expect(card.getByTestId("home-attention-eyebrow")).toHaveText(a.eyebrow);
  await expect(card.getByTestId("home-attention-eyebrow")).toHaveClass(/text-warn-fg/);
  // The title is the recommendation: the h1 above already says the first sentence, so it is not said twice.
  const heading = day0.cash.headline_conditional;
  expect(a.title.startsWith(heading)).toBe(true);
  await expect(card.getByTestId("home-attention-title")).toHaveText(a.title.slice(heading.length).trim());
  // The facts the funding line already says (the cost, who decides) are not repeated; when the funds arrive is the server's own text, on the card.
  const facts = card.getByTestId("home-attention-facts");
  await expect(facts).not.toContainText(a.facts[0].label); // "Estimated cost"
  await expect(facts).not.toContainText(a.facts[a.facts.length - 1].value); // Authority is the last fact: "within your signed limits"
  await expect(card.getByTestId("next-action-lands")).toHaveText("in 3 days"); // the plain "Funds arrive" fact, beside the per-leg facts
  expect(await filledBrand(page)).toBe(1);
  const run = card.getByTestId("fix-open-ALERT-RESERVE-12");
  await expect(run).toHaveText("Run funding plan");
  await expect(run).toHaveCSS("background-color", "rgb(3, 104, 233)");
  // The compare link is the secondary, never filled.
  await expect(card.getByTestId("next-action-alternatives")).toHaveText(a.primary.label);
  await expect(card.getByTestId("next-action-alternatives")).toHaveAttribute("href", "/cash#cash-options");
  await expect(card.getByTestId("next-action-alternatives")).not.toHaveCSS("background-color", "rgb(3, 104, 233)");
  await expect(card.getByTestId("home-attention-why")).toHaveText(a.secondary.label); // "Why this?" stays on the funding item
  await expect(card.getByTestId("home-attention-why")).toHaveAttribute("href", a.secondary.href);
  // The funding line beneath: its sentence, the two costs (amount first, "Cost" leads, each with its words), who decides.
  const f = day0.funding_line;
  await expect(card.getByTestId("home-funding-text")).toHaveText(f.text);
  await expect(card.getByTestId("home-funding-costs")).toHaveText(`Cost ${f.cost_leg_display} for ${f.cost_leg_label}; ${f.cost_total_display} for ${f.cost_total_label}`);
  await expect(card.getByTestId("home-funding-authority")).toHaveText(f.authority_text);
  await expect(page.getByTestId("home-attention-queue")).toHaveCount(0);
  // The first press asks, with what is received and what it costs; Cancel sends nothing.
  let acts = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && /\/alerts\/[^/]+\/act(\?|$)/.test(r.url())) acts += 1;
  });
  await run.click();
  const confirm = page.getByTestId("fix-confirm-ALERT-RESERVE-12");
  await expect(confirm).toContainText("Run this plan now?");
  await expect(confirm).toContainText("¥405,000.00");
  await expect(confirm).toContainText("¥3,113.93");
  await expect(run).toHaveCount(0);
  await page.getByTestId("fix-cancel-ALERT-RESERVE-12").click();
  await expect(confirm).toHaveCount(0);
  await expect(run).toBeVisible();
  expect(acts).toBe(0);
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("fix-result")).toContainText("2 executed");
});

test("section 2: once the plan has run the funding on its way is said once, quietly: no raised card, no filled button, no amber", async ({ page }) => {
  await open(page);
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  const a = afterFund.attention.items[0];
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  await expect(page.getByTestId("home-attention-card")).toHaveCount(0);
  await expect(page.getByTestId("home-attention")).toHaveAttribute("data-state", "info");
  await expect(page.getByTestId("home-attention-eyebrow")).toHaveText(a.eyebrow);
  await expect(page.getByTestId("home-attention-eyebrow")).not.toHaveClass(/text-warn-fg/);
  await expect(page.getByTestId("home-attention-link")).toHaveText(a.primary.label);
  await expect(page.getByTestId("home-attention-link")).not.toHaveCSS("background-color", "rgb(3, 104, 233)");
  expect(await filledBrand(page)).toBe(0);
  // Said once on the card (the facts row); the "Arriving next" tile and the rail keep it, the title and the plan's sentence do not repeat it.
  await expect(page.getByTestId("next-action-lands")).toHaveText(afterFund.attention.items[0].facts[0].value); // the quiet card's first fact: the leg and when it lands
  await expect(page.getByTestId("home-attention-title")).toHaveCount(0);
  await expect(page.getByTestId("home-funding-text")).toHaveCount(0);
  await expect(page.getByTestId("home-funding-costs")).toContainText(afterFund.funding_line.cost_total_display);
  await expect(page.getByTestId("home-fact-tile-arriving")).toContainText("in 3 days");
  await expect(page.getByTestId("rail-row-0")).toContainText("in 3 days");
  await expect(page.getByTestId("home-headline")).toHaveText(afterFund.cash.headline_conditional);
  await expect(page.getByTestId("home-status-word")).toHaveText("Covered, but tight");
});

test("section 2: with nothing waiting the card shrinks to the funding line under one quiet line, and nothing is filled", async ({ page }) => {
  await page.goto("/demo");
  await walkStory(page, 3); // the deal is agreed (the first three steps), nothing else needs the owner
  await page.goto("/");
  await expect(page.getByTestId("home-attention-none")).toHaveText("No urgent action required.");
  await expect(page.getByTestId("home-attention-card")).toHaveCount(0);
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  await expect(page.getByTestId("home-funding")).toBeVisible();
  expect(await filledBrand(page)).toBe(0);
});

test("section 2: a longer queue follows as a short ordered list under the card, never as a second raised card", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await expect(page.getByTestId("home-next-action")).toHaveCount(1);
  await expect(page.getByTestId("home-attention-card")).toHaveCount(0);
  const queue = page.getByTestId("home-attention-queue");
  await expect(queue).toContainText("Also waiting");
  await expect(queue.locator("li")).toHaveText(["Foshan is 2 days late on ¥163k."]);
  expect(await filledBrand(page)).toBe(1);
  // Queuing the plan: needs the owner, so the control says so, and afterwards the card is the approval it waits in (the same waiting state).
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-42")).toHaveText("Queue it for my approval");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toHaveText("Waiting for your approval");
  await expect(page.getByTestId("alert-approval-link-ALERT-RESERVE-42")).toHaveText("Review and decide");
  await expect(page.getByTestId("alert-approval-link-ALERT-RESERVE-42")).toHaveClass(/bg-brand-600/);
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-42")).toHaveCount(0);
  expect(await filledBrand(page)).toBe(1);
});

test("section 3: the rail lists the events in order, the lowest point is among them, its mark fills when chosen and the panel reads its sentence", async ({ page }) => {
  await open(page);
  const events = rail(day0);
  await expect(page.locator('[data-testid^="rail-row-"]')).toHaveCount(events.length);
  for (const [i, e] of events.entries()) {
    const row = page.getByTestId(`rail-row-${i}`);
    await expect(row).toContainText(e.when);
    await expect(row).toContainText(e.label, { ignoreCase: true });
    await expect(page.getByTestId(`rail-amount-${i}`)).toHaveText(e.amount_short);
  }
  // The lowest row alone carries the amber note: the server's own sentence for it, under its label.
  await expect(page.getByTestId(`rail-note-${LOWEST}`)).toHaveText(events[LOWEST].note!);
  await expect(page.getByTestId(`rail-note-${LOWEST}`)).toHaveText("cash at its lowest, ¥300k, at your minimum");
  await expect(page.getByTestId(`rail-note-${LOWEST}`)).toHaveClass(/text-warn-fg/);
  await expect(page.locator('[data-testid^="rail-note-"]')).toHaveCount(1);
  // The first event is chosen to begin with; its mark is filled, the others are outlines.
  await expect(page.getByTestId("rail-row-0")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("rail-mark-0")).toHaveAttribute("data-filled", "true");
  await expect(page.getByTestId(`rail-mark-${LOWEST}`)).toHaveAttribute("data-filled", "false");
  // Mark colours: the lowest point amber, a landing green, an outflow grey.
  await expect(page.getByTestId(`rail-mark-${LOWEST}`)).toHaveAttribute("data-mark", "amber");
  await expect(page.getByTestId("rail-mark-0")).toHaveAttribute("data-mark", "green");
  await expect(page.getByTestId("rail-mark-2")).toHaveAttribute("data-mark", "grey");
  // Choosing the lowest point fills its mark; the panel is its sentence, word for word.
  await page.getByTestId(`rail-row-${LOWEST}`).click();
  await expect(page.getByTestId(`rail-row-${LOWEST}`)).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("rail-row-0")).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByTestId(`rail-mark-${LOWEST}`)).toHaveAttribute("data-filled", "true");
  await expect(page.getByTestId("rail-mark-0")).toHaveAttribute("data-filled", "false");
  await expect(page.getByTestId("rail-explain")).toHaveText(events[LOWEST].explain);
  await expect(page.getByTestId("rail-explain")).toContainText("−¥105k"); // what the lowest point would be if you did nothing
  // The same-day receipt and repayment is one event, its split in the sentence.
  await page.getByTestId(`rail-row-${events.length - 1}`).click();
  await expect(page.getByTestId("rail-explain")).toHaveText(events[events.length - 1].explain);
  await page.getByTestId(`rail-row-${LOWEST}`).click();
  await expect(page.getByTestId("home-cursor")).toHaveAttribute("data-day", String(events[LOWEST].day));
  // One polite announcement of the title, for the chosen row.
  await expect(page.getByTestId("rail-announce")).toContainText(events[LOWEST].when);
});

test("section 3: pointing at or focusing a row previews it, leaving restores the chosen one", async ({ page }) => {
  await open(page);
  const events = rail(day0);
  await page.getByTestId(`rail-row-${LOWEST}`).click();
  const announced = await page.getByTestId("rail-announce").textContent();
  await page.getByTestId("rail-row-2").hover();
  // A preview is not an announcement: the live region still holds the chosen event's title, and the chosen row keeps its bar (not only its colour).
  await expect(page.getByTestId("rail-announce")).toHaveText(announced!);
  await expect(page.getByTestId(`rail-chosen-${LOWEST}`)).toBeVisible();
  await expect(page.getByTestId("rail-chosen-2")).toHaveCount(0);
  await expect(page.getByTestId("rail-mark-2")).toHaveAttribute("data-filled", "true");
  await expect(page.getByTestId("rail-explain")).toHaveText(events[2].explain);
  await expect(page.getByTestId("home-cursor")).toHaveAttribute("data-day", String(events[2].day));
  // The chosen row is still the chosen one while another is previewed.
  await expect(page.getByTestId(`rail-row-${LOWEST}`)).toHaveAttribute("aria-pressed", "true");
  await page.mouse.move(5, 5);
  await expect(page.getByTestId("rail-explain")).toHaveText(events[LOWEST].explain);
  await expect(page.getByTestId("rail-mark-2")).toHaveAttribute("data-filled", "false");
  await expect(page.getByTestId(`rail-mark-${LOWEST}`)).toHaveAttribute("data-filled", "true");
  // Keyboard: focus previews (and Enter keeps it); blur returns.
  await page.getByTestId("rail-row-1").focus();
  await expect(page.getByTestId("rail-explain")).toHaveText(events[1].explain);
  await page.keyboard.press("ArrowDown");
  await expect(page.getByTestId("rail-row-2")).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("rail-row-1")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("rail-row-1").blur();
  await expect(page.getByTestId("rail-explain")).toHaveText(events[1].explain);
});

test("section 3: over the plot the dotted cursor follows the pointer with the lines' figures, and leaving returns it to the chosen event", async ({ page }) => {
  await open(page);
  const events = rail(day0);
  await page.getByTestId(`rail-row-${LOWEST}`).click();
  const chart = page.getByTestId("home-chart");
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5);
  const tooltip = page.getByTestId("home-tooltip");
  await expect(tooltip).toBeVisible();
  // The figures are the series' own strings, for the plan line and the dashed comparison.
  await expect(tooltip).toContainText("If you run FLOW's plan");
  await expect(tooltip).toContainText(day0.cash.counterfactual_label);
  await expect(tooltip).toContainText(/¥[\d,.]+/);
  // No day word is made in the browser: a day with no event of its own shows the figures only.
  await expect(tooltip).not.toContainText(/\bin \d+ days?\b/);
  const day = Number(await page.getByTestId("home-cursor").getAttribute("data-day"));
  expect(day).not.toBe(events[LOWEST].day);
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
  await expect.poll(async () => Number(await page.getByTestId("home-cursor").getAttribute("data-day"))).not.toBe(day);
  await page.mouse.move(5, 5);
  await expect(tooltip).toHaveCount(0);
  await expect(page.getByTestId("home-cursor")).toHaveAttribute("data-day", String(events[LOWEST].day));
  // A click on the plot picks the nearest event.
  await page.mouse.click(box.x + box.width * 0.99, box.y + box.height * 0.5);
  await expect(page.getByTestId(`rail-row-${events.length - 1}`)).toHaveAttribute("aria-pressed", "true");
  // Keyboard on the plot: the arrows step through the events.
  await chart.focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByTestId(`rail-row-${events.length - 2}`)).toHaveAttribute("aria-pressed", "true");
});

test("section 3: no event labels or chips on the plot, the comparison line is named in the legend, the reserve and the axis stay, no Play", async ({ page }) => {
  await open(page);
  await expect(page.getByTestId("picture-chips")).toHaveCount(0);
  await expect(page.getByTestId("home-line-plan")).toHaveCount(1);
  await expect(page.getByTestId("home-line-counter")).toHaveCount(1);
  await expect(page.getByTestId("home-legend")).toContainText(day0.cash.counterfactual_label);
  await expect(page.getByTestId("home-legend")).toContainText("If you run FLOW's plan");
  await expect(page.getByTestId("home-reserve")).toHaveCount(1);
  await expect(page.getByTestId("home-chart")).toContainText("Minimum cash reserve ¥300k");
  expect(await page.getByTestId("picture-ytick").count()).toBeGreaterThan(2);
  await expect(page.getByTestId("home-chart").locator("svg")).not.toContainText(/payroll/i);
  await expect(page.getByRole("button", { name: /Play/ })).toHaveCount(0);
  // The picture's sentence and a table for a screen reader.
  await expect(page.getByTestId("home-chart")).toHaveAttribute("aria-label", /key events numbered/);
  await expect(page.getByTestId("home-picture-table")).toContainText(rail(day0)[2].amount_short);
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-window", String(day0.cash.picture_days));
  // After the plan has run there is one line and no view toggle; the comparison keeps its words from the server.
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("home-legend")).toContainText("With FLOW's plan");
  await expect(page.getByTestId("picture-view-plan")).toHaveCount(0);
  await expect(page.getByTestId("home-legend")).toContainText(afterFund.cash.counterfactual_label);
});

test("section 3: the window switch widens the picture", async ({ page }) => {
  await open(page);
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-window", "36");
  await page.getByTestId("home-window-60").click();
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-window", "60");
  await expect(page.getByTestId("home-window-60")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("home-window-120").click();
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-window", "120");
});

test("section 3: the scenario switch is absent while the server says stress is not available", async ({ page }) => {
  await open(page);
  expect(day0.cash.stress_available).toBe(false);
  await expect(page.getByTestId("home-scenario-late")).toHaveCount(0);
  await expect(page.getByTestId("home-scenario-expected")).toHaveCount(0);
});

test("section 3: the late scenario draws the stress line dashed red, replaces the panel, widens the window and switching back restores", async ({ page }) => {
  await open(page, { stress: true });
  await expect(page.getByTestId("home-scenario-expected")).toHaveText("Expected payments");
  await expect(page.getByTestId("home-scenario-late")).toHaveText("Foshan 30 days late");
  await page.getByTestId("home-window-60").click();
  await page.getByTestId(`rail-row-${LOWEST}`).click();
  await page.getByTestId("home-scenario-late").click();
  const picture = page.getByTestId("home-event-picture");
  await expect(picture).toHaveAttribute("data-scenario", "late");
  await expect(page.getByTestId("home-line-late")).toHaveAttribute("stroke-dasharray", /\d/);
  await expect(page.getByTestId("home-line-late")).toHaveClass(/stroke-bad-solid/);
  await expect(page.getByTestId("home-line-plan")).toHaveCount(0);
  // The panel: the server's assumption and the stress sentence (lowest, breach days, need, plan).
  await expect(page.getByTestId("stress-assumption")).toContainText("Assumes Foshan pays 30 days after the due date");
  // The sentence is the server's three strings in order, composed by nothing in the browser.
  await expect(page.getByTestId("stress-sentence")).toHaveText(
    "Cash would fall to -¥108k in 32 days, below your minimum for 14 days, and ¥120k would be uncovered. FLOW would draw the rest of your credit line first. Once the late payment arrives, cash is back to ¥312k.",
  );
  await expect(page.getByTestId("rail-explain")).toHaveCount(0);
  // The window widened to the days needed, with one line saying so.
  await expect(picture).toHaveAttribute("data-window", "62");
  await expect(page.getByTestId("home-widened")).toHaveText("Showing 62 days so the late payment appears.");
  await expect(page.getByTestId("home-legend")).toContainText("Foshan 30 days late");
  // The rail is inert while the expected events do not apply.
  await expect(page.getByTestId("rail-row-1")).toBeDisabled();
  await expect(page.locator('[data-testid^="rail-mark-"]')).toHaveCount(0);
  // Back: everything is as it was, including the chosen event and the owner's window.
  await page.getByTestId("home-scenario-expected").click();
  await expect(picture).toHaveAttribute("data-scenario", "expected");
  await expect(picture).toHaveAttribute("data-window", "60");
  await expect(page.getByTestId("home-widened")).toHaveCount(0);
  await expect(page.getByTestId("home-line-plan")).toHaveCount(1);
  await expect(page.getByTestId(`rail-row-${LOWEST}`)).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("rail-explain")).toHaveText(rail(day0)[LOWEST].explain);
});

test("section 4: three cards, each a link; the receivables card reads from the server; the old rows are gone", async ({ page }) => {
  await open(page);
  const cards = page.getByTestId("home-cards");
  await expect(cards.locator("> section")).toHaveCount(3);
  const deals = page.getByTestId("home-card-deals");
  await expect(deals).toContainText("Your deals");
  await expect(deals.getByTestId("home-card-deals-none")).toHaveText(day0.deals_card.empty_text);
  await expect(deals.locator("button")).toHaveCount(0);
  await expect(page.getByTestId("home-deals")).toHaveCount(0);
  await expect(deals.getByTestId("home-card-deals-link")).toHaveAttribute("href", "/deals");
  const recv = page.getByTestId("home-card-receivables");
  await expect(recv).toContainText("Receivables");
  const rc = day0.receivables_card;
  await expect(page.getByTestId("home-card-outstanding")).toHaveText(rc.outstanding_short);
  await expect(page.getByTestId("home-card-overdue")).toHaveText(rc.overdue_short);
  await expect(page.getByTestId("home-card-next")).toHaveText(rc.next_text);
  await expect(page.getByTestId("home-card-financing")).toHaveCount(0); // nothing is financed on this invoice yet
  await expect(recv.getByTestId("home-card-receivables-link")).toHaveAttribute("href", "/receivables");
  const changes = page.getByTestId("home-card-changes");
  await expect(changes).toContainText("Recent changes");
  await expect(changes.getByTestId("home-card-changes-none")).toHaveText(day0.changes_card.empty_text);
  await expect(changes.getByTestId("home-card-changes-link")).toHaveAttribute("href", "/activity");
  await expect(page.locator("#home-receivables")).toHaveCount(0);
  // "Also on your radar" is a closed fold under the row.
  const radar = page.getByTestId("home-radar");
  await expect(radar.locator("> summary")).toHaveText("Also on your radar");
  await expect(radar).not.toHaveAttribute("open", "");
  // The whole card is the link: clicking its body goes there (the link is stretched over the card, so the click is made at the figure's place).
  await page.getByTestId("home-card-outstanding").scrollIntoViewIfNeeded();
  const figure = (await page.getByTestId("home-card-outstanding").boundingBox())!;
  await page.mouse.click(figure.x + figure.width / 2, figure.y + figure.height / 2);
  await expect(page).toHaveURL(/\/receivables/);
});

test("section 4: after the plan the changes card lists the ledger sentences, the receivables card says how the financing touches the receipt, and 'What changed' is a fold", async ({ page }) => {
  await open(page);
  await runPlan(page, "ALERT-RESERVE-12");
  const changes = page.getByTestId("home-card-changes");
  await expect(changes.getByTestId("home-card-change")).toHaveText(afterFund.changes_card.rows.map((r) => new RegExp(`^${r.text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`)));
  await expect(changes).not.toContainText("Advance ¥");
  await expect(changes).not.toContainText("RI:");
  await expect(page.getByTestId("home-card-financing")).toHaveText(afterFund.receivables_card.financing_note!);
  const fold = page.getByTestId("home-changes-fold");
  await expect(fold.locator("> summary")).toHaveText("What changed");
  await expect(fold).not.toHaveAttribute("open", "");
  await fold.locator("> summary").click();
  await expect(fold.getByTestId("home-changes-list")).toContainText("drawn on the Bank credit line");
});

test("section 4: an agreed deal is one line: the buyer, the status word and what was asked", async ({ page }) => {
  await page.goto("/demo");
  await walkStory(page, 3);
  await page.goto("/");
  const row = page.getByTestId("home-card-deals").getByTestId("home-card-deal");
  await expect(row).toHaveCount(1);
  await expect(row).toContainText("Foshan Home Retail Co.");
  await expect(row).toContainText("Agreed");
  await expect(row).toContainText("60-day terms");
  await expect(row.locator("ol, li li, img, svg")).toHaveCount(0); // no stages, no avatar, no badge
});

test("a phone (390 x 844): the primary is in the first screen, the rail sits below the picture, nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { stress: true });
  const primary = page.getByTestId("fix-open-ALERT-RESERVE-12");
  await expect(primary).toBeInViewport();
  const box = (await primary.boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(844 - 72); // above the tab bar
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  await expect(page.locator("h1")).toHaveCount(1);
  expect(await filledBrand(page)).toBe(1);
  const chart = (await page.getByTestId("home-chart").boundingBox())!;
  const panel = (await page.getByTestId("rail-panel").boundingBox())!;
  const rail = (await page.getByTestId("home-rail").boundingBox())!;
  expect(rail.y).toBeGreaterThanOrEqual(chart.y + chart.height);
  expect(rail.y).toBeGreaterThanOrEqual(panel.y + panel.height);
  // The card is in the page's flow here, not sticky; the plan sits above the chart.
  expect(await page.getByTestId("home-next-action").evaluate((el) => getComputedStyle(el).position)).not.toBe("sticky");
  const bar = (await page.getByTestId("home-next-action").boundingBox())!;
  const head = (await page.getByTestId("home-status").boundingBox())!;
  expect(bar.y).toBeGreaterThan(head.y);
  expect(bar.y).toBeLessThan(chart.y);
  // The cards stack in one column.
  const a = (await page.getByTestId("home-card-deals").boundingBox())!;
  const b = (await page.getByTestId("home-card-receivables").boundingBox())!;
  expect(b.y).toBeGreaterThan(a.y + a.height - 1);
  // The late scenario and the rail stay inside the width too.
  await page.getByTestId("home-scenario-late").click();
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  await page.getByTestId("home-scenario-expected").click();
  // Row targets are finger-sized.
  const row = (await page.getByTestId("rail-row-0").boundingBox())!;
  expect(row.height).toBeGreaterThanOrEqual(44);
  await page.getByTestId(`rail-row-${LOWEST}`).click();
  await expect(page.getByTestId("rail-explain")).toHaveText(rail0Explain(LOWEST));
  // The h1 is 24 px here.
  await expect(page.getByTestId("home-headline")).toHaveCSS("font-size", "24px");
});

const rail0Explain = (i: number) => rail(day0)[i].explain;

test("desktop: the picture and the rail sit side by side with the rail 312 px wide, the h1 is 34 px at weight 800, and the primary is in the first screen at 1366 x 768", async ({ page }) => {
  await open(page);
  const chart = (await page.getByTestId("home-chart").boundingBox())!;
  const rail = (await page.getByTestId("home-rail").boundingBox())!;
  expect(rail.x).toBeGreaterThanOrEqual(chart.x + chart.width);
  expect(Math.round(rail.width)).toBe(312);
  await expect(page.getByTestId("home-headline")).toHaveCSS("font-size", "34px");
  await expect(page.getByTestId("home-headline")).toHaveCSS("font-weight", "800");
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  await page.setViewportSize({ width: 1366, height: 768 });
  const run = (await page.getByTestId("fix-open-ALERT-RESERVE-12").boundingBox())!;
  expect(run.y + run.height).toBeLessThanOrEqual(768);
});

test("Chinese: the same sections, every label and word in Chinese, the server's sentences as recorded", async ({ page }) => {
  await open(page, { lang: "zh", stress: true });
  const c = day0Zh.cash;
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(c.headline_conditional);
  await expect(page.getByTestId("home-status-word")).toHaveText(c.status_word);
  await expect(page.getByTestId("home-read-when")).toHaveText("今天读取");
  await expect(page.getByTestId("home-assumptions").locator("> summary")).toHaveText("预测所依据的假设");
  await expect(page.getByTestId("home-facts").locator("> div")).toHaveCount(3);
  await expect(page.getByTestId("home-attention-eyebrow")).toHaveText(day0Zh.attention.items[0].eyebrow);
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-12")).toBeVisible();
  const f = day0Zh.funding_line;
  await expect(page.getByTestId("home-funding-costs")).toHaveText(`成本 ${f.cost_leg_display}，对应${f.cost_leg_label}；${f.cost_total_display}，对应${f.cost_total_label}`);
  expect(await filledBrand(page)).toBe(1);
  await expect(page.locator('[data-testid^="rail-row-"]')).toHaveCount(c.events_rail.length);
  await page.getByTestId(`rail-row-${LOWEST}`).click();
  await expect(page.getByTestId("rail-explain")).toHaveText(c.events_rail[LOWEST].explain);
  await expect(page.getByTestId("home-scenario-expected")).toHaveText("按预期收款");
  await expect(page.getByTestId("home-scenario-late")).toHaveText("佛山晚付 30 天");
  await expect(page.getByTestId("home-window-60")).toHaveText("60 天");
  await expect(page.getByTestId("home-legend")).toContainText(c.counterfactual_label);
  await page.getByTestId("home-scenario-late").click();
  await expect(page.getByTestId("stress-sentence")).toHaveText("现金将在 32 天后降至 -¥108k，有 14 天低于您的最低现金储备，还差 ¥120k。 FLOW 会先动用您信用额度的剩余部分。 晚到的款项到账后，现金回到 ¥312k。");
  await expect(page.getByTestId("home-widened")).toHaveText("为显示这笔晚到的款项，已展开到 62 天。");
  await expect(page.getByTestId("home-card-deals")).toContainText("您的交易");
  await expect(page.getByTestId("home-card-receivables")).toContainText("应收款");
  await expect(page.getByTestId("home-card-changes")).toContainText("近期变化");
  await expect(page.getByTestId("home-radar").locator("> summary")).toHaveText("您还需留意");
  // No English UI labels leak in.
  const text = (await page.locator("main").innerText()).replace(/FLOW|¥[\w,.]+|Foshan/g, "");
  for (const word of ["Forecast assumptions", "Also waiting", "Expected payments", "Key events", "Recent changes", "Your deals", "Receivables", "Run funding plan"]) expect(text).not.toContain(word);
});

test("an incomplete queue never says nothing is urgent: the server's sentence about what was not read, or nothing", async ({ page }) => {
  await open(page, { patch: { attention: { items: [], primary_key: null, none_text: null, incomplete: true }, partial: { missing: ["decisions"], text: "The decisions could not be read just now." } } });
  await expect(page.getByTestId("home-attention-none")).toHaveCount(0);
  await expect(page.getByTestId("home-attention-unread")).toHaveText("The decisions could not be read just now.");
  await expect(page.locator("main")).not.toContainText("No urgent action required.");
});

test("an incomplete queue with no sentence from the server says nothing at all about urgency", async ({ page }) => {
  await open(page, { patch: { attention: { items: [], primary_key: null, none_text: null, incomplete: true } } });
  await expect(page.getByTestId("home-attention")).toBeVisible();
  await expect(page.getByTestId("home-attention-none")).toHaveCount(0);
  await expect(page.getByTestId("home-attention-unread")).toHaveCount(0);
  await expect(page.locator("main")).not.toContainText("No urgent action required.");
});

test("section 3: a rail longer than the picture widens the window with its own one-line note", async ({ page }) => {
  await open(page, { patch: { cash: { events_rail_days: 62 } } });
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-window", "62");
  await expect(page.getByTestId("home-widened")).toHaveText("Showing 62 days so every key event appears.");
  // The owner's own choices stay what they are: the first window is still the one pressed.
  await expect(page.getByTestId("home-window-36")).toHaveAttribute("aria-pressed", "true");
});

test("section 3: reduced motion carries no transition on the cursor; with motion allowed it eases", async ({ page }) => {
  await open(page); // the project asks for reduced motion
  await expect(page.getByTestId("home-cursor").locator("> g")).not.toHaveClass(/transition-transform/);
  await expect(page.getByTestId("home-dot").first()).not.toHaveClass(/transition-transform/);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(page.getByTestId("home-cursor").locator("> g")).toHaveClass(/transition-transform/);
});

test("section 3: the switch hides and the picture returns to expected when the server stops offering the stress", async ({ page }) => {
  await open(page, { stress: true });
  await page.getByTestId("home-scenario-late").click();
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-scenario", "late");
  // The books move (the plan runs): the new read has no stress, so the scenario is expected again and the switch is gone.
  await page.evaluate(() => sessionStorage.setItem("tl-mock-home-patch", JSON.stringify({ cash: { stress_available: false, stress: null } })));
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("home-scenario-late")).toHaveCount(0);
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-scenario", "expected");
});

test("section 4: a deals card with several rows is one line each, the card leads to Deals", async ({ page }) => {
  const rows = [
    { buyer: "Foshan Home Retail Co.", buyer_id: "BUYER-1", status_text: "Your response needed", request_text: "60-day terms + 1% rebate", recommendation_text: "Counter with Option A, estimated cost ¥3,027.77", href: "/deals?buyer=BUYER-1" },
    { buyer: "Dongguan Office Supplies Ltd.", buyer_id: "BUYER-2", status_text: "Awaiting the buyer", request_text: "30-day terms", recommendation_text: "", href: "/deals?buyer=BUYER-2" },
  ];
  await open(page, { patch: { deals_card: { rows, empty_text: "No deals are open.", href: "/deals" } } });
  const card = page.getByTestId("home-card-deals");
  await expect(card.getByTestId("home-card-deal")).toHaveCount(2);
  await expect(card.getByTestId("home-card-deal").first()).toContainText("Your response needed");
  await expect(card.getByTestId("home-card-deal").nth(1)).toContainText("Dongguan Office Supplies Ltd.");
  await expect(card.getByTestId("home-card-deal").nth(1)).toContainText("Awaiting the buyer");
  await expect(card.getByTestId("home-card-deals-none")).toHaveCount(0);
  await expect(card.getByTestId("home-card-deals-link")).toHaveAttribute("href", "/deals");
  await expect(card.locator("button, img")).toHaveCount(0);
});

test("the older Home renders exactly when the server sends none of the hybrid's fields, and nothing of the hybrid does", async ({ page }) => {
  await open(page, { patch: OLDER_SERVER });
  // The older pieces: the uppercase status pill, the next-step bar, the chips picture with its two lines and toggle, the deals rows read on their own, the section of changes.
  await expect(page.getByTestId("home-status-word")).toHaveClass(/uppercase/);
  await expect(page.getByTestId("home-status-word")).toHaveText("Action needed");
  await expect(page.getByTestId("home-headline")).toHaveText(day0.headline);
  await expect(page.getByTestId("home-note")).toHaveText(day0.note);
  await expect(page.getByTestId("home-next-action").getByTestId("next-action-title")).toHaveText("Secure ¥405k of funding");
  await expect(page.getByTestId("home-picture")).toBeVisible();
  await expect(page.getByTestId("picture-chips")).toContainText("Payroll");
  await expect(page.getByTestId("picture-view-plan")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("home-cash")).toHaveText("¥400k");
  await expect(page.getByTestId("home-floor")).toHaveText("¥300k");
  await expect(page.getByTestId("home-deals")).toBeVisible();
  await expect(page.getByTestId("home-deal-BUYER-1").locator("ol > li")).toHaveCount(5);
  await expect(page.locator("#home-receivables")).toBeVisible();
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("fix-result")).toContainText("2 executed");
  await expect(page.getByTestId("home-changes-list")).toContainText("drawn on the Bank credit line");
  await expect(page.locator("#home-changes")).toBeVisible();
  expect(await filledBrand(page)).toBeLessThanOrEqual(1);
  // Nothing of the hybrid.
  for (const id of ["home-attention", "home-event-picture", "home-facts", "home-assumptions", "home-cards", "home-card-deals", "home-card-receivables", "home-card-changes", "home-changes-fold", "home-rail", "home-legend", "home-funding"]) {
    await expect(page.getByTestId(id), id).toHaveCount(0);
  }
  expect(await page.getByTestId("home-radar").evaluate((el) => el.tagName)).toBe("SECTION");
});

test("a phone (390 x 844): the primary is in the first screen after the plan has run and in Chinese too", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { lang: "zh" });
  const zhRun = (await page.getByTestId("fix-open-ALERT-RESERVE-12").boundingBox())!;
  expect(zhRun.y + zhRun.height).toBeLessThanOrEqual(844 - 72);
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-12")).toBeInViewport();
  // Run it: what is next in the card (the landing, said quietly) is also in the first screen, and nothing scrolls sideways.
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("home-attention")).toHaveAttribute("data-state", "info");
  await expect(page.getByTestId("home-attention-link")).toBeInViewport();
  const link = (await page.getByTestId("home-attention-link").boundingBox())!;
  expect(link.y + link.height).toBeLessThanOrEqual(844 - 72);
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
});

test("a phone (390 x 844), English, after the plan has run: the landing line is in the first screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page);
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("home-attention-link")).toBeInViewport();
  const link = (await page.getByTestId("home-attention-link").boundingBox())!;
  expect(link.y + link.height).toBeLessThanOrEqual(844 - 72);
});

test("the plan line's legend is the server's: a question before the plan runs, the executed plan after", async ({ page }) => {
  await open(page);
  expect(day0.cash.plan_line_label).toBe("If you run FLOW's plan");
  await expect(page.getByTestId("home-legend-main")).toHaveText("If you run FLOW's plan");
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  expect(afterFund.cash.plan_line_label).toBe("With FLOW's plan");
  await expect(page.getByTestId("home-legend-main")).toHaveText("With FLOW's plan");
});

test("a landing that only the plan would bring says 'planned' beside its amount; once the plan has run the word is gone", async ({ page }) => {
  await open(page);
  const events = rail(day0);
  const planned = events.flatMap((e, i) => (e.planned ? [i] : []));
  expect(planned).toEqual([0, 1]); // the credit line draw and the invoice financing
  for (const i of planned) {
    await expect(page.getByTestId(`rail-planned-${i}`)).toHaveText("planned");
    await expect(page.getByTestId(`rail-row-${i}`)).toContainText("would arrive, if you run the plan");
  }
  await expect(page.locator('[data-testid^="rail-planned-"]')).toHaveCount(2);
  // A quiet word, not a badge: no fill, no border.
  await expect(page.getByTestId("rail-planned-0")).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  await expect(page.getByTestId("rail-planned-0")).toHaveCSS("border-top-width", "0px");
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  await expect(page.locator('[data-testid^="rail-row-"]').first()).toBeVisible();
  await expect(page.locator('[data-testid^="rail-planned-"]')).toHaveCount(0);
  await expect(page.getByTestId("rail-row-0")).toContainText("arrives");
  await expect(page.getByTestId("rail-row-0")).not.toContainText("would arrive");
});

test("the funding item has one fact per leg, and five facts fit the card on a desktop and wrap cleanly on a phone", async ({ page }) => {
  await open(page);
  const a = day0.attention.items[0];
  const legs = a.facts.filter((f) => /\(planned\)$/.test(f.value));
  expect(legs.map((f) => f.value)).toEqual(["¥150k today (planned)", "¥255k in 3 days (planned)"]);
  const facts = page.getByTestId("home-attention-facts");
  const legDds = facts.locator("dd").filter({ hasText: /\(planned\)/ });
  await expect(legDds).toHaveText(legs.map((f) => f.value));
  for (const f of legs) await expect(facts.locator("dt").filter({ hasText: f.label })).toHaveCount(1);
  // Five facts (the cap), the funding line saying none of them.
  const five = ["Credit line draw", "Invoice financing", "Second invoice financing", "Third invoice financing", "Fourth invoice financing"].map((label, i) => ({ label, value: `¥${(i + 1) * 100}k ${i === 0 ? "today" : `in ${i + 2} days`} (planned)`, tone: "neutral" }));
  const patched = { attention: { ...day0.attention, items: [{ ...a, facts: five }] } };
  for (const [w, h] of [
    [1440, 900],
    [390, 844],
  ] as const) {
    const ctx = await page.context().browser()!.newContext({ viewport: { width: w, height: h }, reducedMotion: "reduce", baseURL: new URL(page.url()).origin });
    const p = await ctx.newPage();
    await p.addInitScript(([key, value]) => {
      sessionStorage.setItem(key as string, JSON.stringify(value));
      sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: "mock-owner" }));
    }, [PATCH_KEY, patched] as const);
    await p.goto("/");
    const dl = p.getByTestId("home-attention-facts");
    await expect(dl.locator("dd")).toHaveCount(5);
    const box = (await dl.boundingBox())!;
    const card = (await p.getByTestId("home-next-action").boundingBox())!;
    expect(box.x + box.width).toBeLessThanOrEqual(card.x + card.width + 1);
    for (let i = 0; i < 5; i++) {
      const b = (await dl.locator("dd").nth(i).boundingBox())!;
      expect(b.x + b.width, `fact ${i} at ${w}`).toBeLessThanOrEqual(card.x + card.width + 1);
      expect(b.x, `fact ${i} at ${w}`).toBeGreaterThanOrEqual(card.x - 1);
    }
    expect(await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    if (w >= 1024) expect(box.height, "five facts take at most two lines on a desktop").toBeLessThanOrEqual(90);
    await ctx.close();
  }
});

test("every event's inspector shows the effect table (four rows, the server's) above its sentence", async ({ page }) => {
  await open(page);
  const events = rail(day0);
  for (const [i, e] of events.entries()) {
    await page.getByTestId(`rail-row-${i}`).click();
    const rows = page.getByTestId("rail-effect-row");
    expect(e.effect_rows).toHaveLength(4);
    await expect(rows).toHaveCount(4);
    await expect(rows.locator("th")).toHaveText(e.effect_rows.map((r) => r.label));
    await expect(rows.locator("td")).toHaveText(e.effect_rows.map((r) => r.display));
    await expect(page.getByTestId("rail-explain")).toHaveText(e.explain);
    // The table is above the paragraph.
    const t = (await page.getByTestId("rail-effect").boundingBox())!;
    const x = (await page.getByTestId("rail-explain").boundingBox())!;
    expect(t.y + t.height).toBeLessThanOrEqual(x.y + 1);
  }
  // Label left, figure right, tabular figures at 14 px.
  const cell = page.getByTestId("rail-effect-row").first().locator("td");
  await expect(cell).toHaveCSS("text-align", "right");
  await expect(cell).toHaveCSS("font-size", "14px");
  await expect(page.getByTestId("rail-effect")).toHaveCSS("font-variant-numeric", /tabular-nums/);
});

test("a phone (390 x 844): the effect table is the same four rows and stays inside the width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page);
  const e = rail(day0)[LOWEST];
  await page.getByTestId(`rail-row-${LOWEST}`).click();
  await expect(page.getByTestId("rail-effect-row")).toHaveCount(4);
  await expect(page.getByTestId("rail-effect-row").locator("td")).toHaveText(e.effect_rows.map((r) => r.display));
  const t = (await page.getByTestId("rail-effect").boundingBox())!;
  expect(t.x + t.width).toBeLessThanOrEqual(390);
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  await expect(page.getByTestId("rail-planned-0")).toBeVisible();
  const row = (await page.getByTestId("rail-row-1").boundingBox())!;
  expect(row.x + row.width).toBeLessThanOrEqual(390);
});

test("Chinese: the plan line's legend, the planned word, the lowest note, the leg facts and the effect table, as the Chinese read says them", async ({ page }) => {
  await open(page, { lang: "zh" });
  const c = day0Zh.cash;
  const events = c.events_rail;
  // The legend: a question before the plan runs, the executed plan after.
  expect(c.plan_line_label).toBe("如果您执行 FLOW 的方案");
  await expect(page.getByTestId("home-legend-main")).toHaveText("如果您执行 FLOW 的方案");
  // The planned word on the two landing rows.
  const planned = events.flatMap((e, i) => (e.planned ? [i] : []));
  expect(planned).toEqual([0, 1]);
  for (const i of planned) await expect(page.getByTestId(`rail-planned-${i}`)).toHaveText("计划中");
  await expect(page.locator('[data-testid^="rail-planned-"]')).toHaveCount(2);
  // The lowest row's note, the server's sentence.
  const low = events.findIndex((e) => e.kind === "lowest");
  await expect(page.getByTestId(`rail-note-${low}`)).toHaveText(events[low].note!);
  // One fact per leg.
  const a = day0Zh.attention.items[0];
  const legs = a.facts.filter((f) => /（计划中）$/.test(f.value));
  expect(legs).toHaveLength(2);
  await expect(page.getByTestId("home-attention-facts").locator("dd").filter({ hasText: /（计划中）/ })).toHaveText(legs.map((f) => f.value));
  // The effect table: the four rows of each event, equal to the read, above the sentence.
  for (const [i, e] of events.entries()) {
    await page.getByTestId(`rail-row-${i}`).click();
    await expect(page.getByTestId("rail-effect-row")).toHaveCount(4);
    await expect(page.getByTestId("rail-effect-row").locator("th")).toHaveText(e.effect_rows.map((r) => r.label));
    await expect(page.getByTestId("rail-effect-row").locator("td")).toHaveText(e.effect_rows.map((r) => r.display));
    await expect(page.getByTestId("rail-explain")).toHaveText(e.explain);
  }
  // After the plan has run: the executed plan's legend, and no planned word.
  await runPlan(page, "ALERT-RESERVE-12");
  expect(afterFundZh.cash.plan_line_label).toBe("采用 FLOW 的方案");
  await expect(page.getByTestId("home-legend-main")).toHaveText("采用 FLOW 的方案");
  await expect(page.locator('[data-testid^="rail-planned-"]')).toHaveCount(0);
});

test("a phone (390 x 844), Chinese: the effect table and the planned rows stay inside the width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, { lang: "zh" });
  await page.getByTestId("rail-row-2").click();
  await expect(page.getByTestId("rail-effect-row")).toHaveCount(4);
  const t = (await page.getByTestId("rail-effect").boundingBox())!;
  expect(t.x + t.width).toBeLessThanOrEqual(390);
  await expect(page.getByTestId("rail-planned-0")).toHaveText("计划中");
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
});

test("axe: no serious or critical finding on the hybrid Home, in both scenarios, at 1440 and at 390", async ({ page }) => {
  const scan = async (label: string) => {
    const result = await new AxeBuilder({ page }).analyze();
    const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`), label).toEqual([]);
  };
  await open(page, { stress: true });
  await page.getByTestId("home-assumptions").locator("> summary").click();
  await page.getByTestId(`rail-row-${LOWEST}`).click();
  await scan("expected, 1440");
  await page.getByTestId("fix-open-ALERT-RESERVE-12").click();
  await scan("confirming, 1440");
  await page.getByTestId("fix-cancel-ALERT-RESERVE-12").click();
  await page.getByTestId("home-scenario-late").click();
  await scan("late, 1440");
  await page.setViewportSize({ width: 390, height: 844 });
  await scan("late, 390");
  await page.getByTestId("home-scenario-expected").click();
  await scan("expected, 390");
});
