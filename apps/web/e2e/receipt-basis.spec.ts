import { expect, test } from "./fixtures";
import type { Locator, Page } from "@playwright/test";
import { openReview, sendCounter, verdictHeading } from "./helpers";
import counterEn from "../mocks/home_summary_day0_counter.json";
import counterZh from "../mocks/home_summary_day0_counter_zh.json";
import quietEn from "../mocks/home_summary_quiet.json";
import receivablesDay0 from "../mocks/receivables/day0.json";

/**
 * Receipts say what they rest on (ticket #116, web half), in mock mode on the recorded story: the invoice is OWED (day 32), the recurring billing SCHEDULED (day 47 and
 * later), the pending counter is a dashed alternative with its sentence and receipts (never the plan line), and once the buyer accepts the moved receipts are AGREED and the
 * dashed line is gone. Home, Cash and Receivables say the same words for the same receipt. Every sentence asserted is read from the recording or is the golden one the
 * server's tests pin; none is composed in the browser. One test lays a SCHEDULED receipt over the recorded rail (the opening books' window ends before the first scheduled
 * receipt): a temporary in-spec patch of a recorded read through the home patch key, said where it is used.
 */
test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "mock-mode spec on the recorded story (the phone is measured inside it)");
});

const OWED_32 = "owed: invoiced 13 days ago, due in 32 days";
const SCHEDULED = "scheduled: not yet invoiced";
const AFTER_CHECK = /Don't accept as asked|Counter instead of accepting as asked/;
const HOME_PATCH_KEY = "tl-mock-home-patch";

async function lang(page: Page, l: "en" | "zh") {
  await page.addInitScript((v) => localStorage.setItem("tl-lang", JSON.stringify({ lang: v })), l);
}

/** The package offer received and read: the counter is ready and nothing is sent. */
async function readOffer(page: Page) {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(verdictHeading(page)).toContainText(AFTER_CHECK);
}

/** The counter sent, the simulated buyer open to it: the agreement is on the books. */
async function acceptCounter(page: Page) {
  await openReview(page);
  await sendCounter(page.locator("#counters"));
  await expect(page.getByTestId("deal-negotiation")).toContainText("The buyer accepted Option A.");
}

async function home(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("home-event-picture")).toBeVisible();
  await expect(page.getByTestId("rail-mark-0")).toBeAttached();
}

async function cash(page: Page) {
  await page.goto("/cash");
  await expect(page.getByTestId("cash-forecast")).toBeVisible();
  await expect(page.getByTestId("cash-receipts")).toBeVisible();
}

/** The font size of an element, as the browser resolved it. */
const px = (el: Locator) => el.evaluate((n) => parseFloat(getComputedStyle(n).fontSize));
const noSideways = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

test("day 0: the invoice is owed on the day-32 row, the later billing is scheduled, and no pending line or legend is drawn", async ({ page }) => {
  await home(page);
  // The rail's receipt row (day 32) says what it rests on, under the label, at 13 px; the rows that are not receipts say nothing.
  const owed = page.getByTestId("rail-basis-5");
  await expect(owed).toHaveText(OWED_32);
  await expect(owed).toHaveAttribute("data-basis", "OWED");
  await expect(owed).toHaveAttribute("data-state", "owed"); // a StateWord (#112)
  expect(await px(owed)).toBe(13);
  await expect(page.locator("[data-testid^='rail-basis-']")).toHaveCount(1);
  // The tooltip says it too: the keyboard moves the cursor to the receipt, and the day's words carry the sentence.
  await page.getByTestId("home-chart").focus();
  for (let i = 0; i < 5; i++) await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("home-tooltip-basis")).toHaveText(OWED_32);
  // The inspector's effect table is unchanged: the receipt's own panel still reads its explanation and its figures.
  await expect(page.getByTestId("rail-effect")).toBeVisible();
  // Nothing pending: no dashed line, no legend sentence, no rows.
  await expect(page.getByTestId("home-line-pending")).toHaveCount(0);
  await expect(page.getByTestId("home-legend-pending")).toHaveCount(0);
  await expect(page.getByTestId("home-receipts-legend")).toHaveCount(0);
  await expect(page.getByTestId("home-pending-rows")).toHaveCount(0);

  // Cash lists the receipts in its window with the same words: the invoice owed, the next billing scheduled (the window reaches day 47).
  await cash(page);
  const owedRow = page.locator("[data-testid='cash-receipts-row'][data-basis='OWED']");
  await expect(owedRow).toHaveCount(1);
  await expect(owedRow.getByTestId("cash-receipts-text")).toHaveText(OWED_32);
  const scheduled = page.locator("[data-testid='cash-receipts-row'][data-basis='SCHEDULED']");
  await expect(scheduled.first().getByTestId("cash-receipts-text")).toHaveText(SCHEDULED);
  expect(await px(scheduled.first().getByTestId("cash-receipts-text"))).toBe(13);
  await expect(scheduled.first().getByTestId("cash-receipts-text")).toHaveClass(/text-ink-3/);
  await expect(owedRow.getByTestId("cash-receipts-text")).toHaveClass(/text-ink-2/);
  await expect(page.getByTestId("picture-line-pending")).toHaveCount(0);
  await expect(page.getByTestId("cash-receipts-legend")).toHaveCount(0);
});

test("Receivables says the same words as the picture, and the summary says the recurring billing is not owed yet", async ({ page }) => {
  await page.goto("/receivables");
  const row = receivablesDay0.rows[0];
  const text = page.getByTestId(`recv-basis-${row.receivable_id}`);
  await expect(text).toHaveText(OWED_32);
  const words = (await text.textContent()) ?? "";
  expect(await px(text)).toBe(13);
  await expect(page.getByTestId("recv3-scheduled-note")).toHaveText(receivablesDay0.summary.scheduled_note);
  await expect(page.getByTestId("recv3-scheduled-note")).toHaveText("¥420,000 more is scheduled to be invoiced in 2 days; it is not owed yet");
  await home(page);
  await expect(page.getByTestId("rail-basis-5")).toHaveText(words);
});

test("a scheduled receipt on the rail is a grey mark and a quieter word (a temporary in-spec patch of the recorded rail)", async ({ page }) => {
  // The opening books' window ends before the first scheduled receipt, so the recorded rail has none: the last row is laid over as a scheduled one.
  const rail = counterEn.cash.events_rail.map((e, i, all) => (i === all.length - 1 ? { ...e, basis: "SCHEDULED", basis_text: SCHEDULED } : e));
  await page.addInitScript(([k, v]) => sessionStorage.setItem(k, v), [HOME_PATCH_KEY, JSON.stringify({ cash: { events_rail: rail } })]);
  await home(page);
  await expect(page.getByTestId("rail-mark-5")).toHaveAttribute("data-mark", "grey");
  const word = page.getByTestId("rail-basis-5");
  await expect(word).toHaveText(SCHEDULED);
  await expect(word).toHaveClass(/text-ink-3/);
});

test("an owed receipt keeps the green mark and the stronger word", async ({ page }) => {
  await home(page);
  await expect(page.getByTestId("rail-mark-5")).toHaveAttribute("data-mark", "green");
  await expect(page.getByTestId("rail-basis-5")).toHaveClass(/text-ink-2/);
});

test("with the counter ready: the pending line is dashed in the brand colour at 60% beside the solid plan line, with its legend, sentence and receipts", async ({ page }) => {
  await readOffer(page);
  await home(page);
  const pending = counterEn.cash.pending;
  const plan = page.getByTestId("home-line-plan");
  const dashed = page.getByTestId("home-line-pending");
  await expect(dashed).toHaveCount(1);
  await expect(dashed).toHaveAttribute("stroke-dasharray", "6 5");
  await expect(dashed).toHaveAttribute("opacity", "0.6");
  await expect(dashed).toHaveClass(/stroke-brand-600/);
  // The plan line is still the solid one, and it is not the pending path.
  await expect(plan).not.toHaveAttribute("stroke-dasharray", /./);
  expect(await plan.getAttribute("d")).not.toBe(await dashed.getAttribute("d"));
  // Its name in the legend, the server's sentence under the picture, and the receipts it would move.
  await expect(page.getByTestId("home-legend-pending")).toHaveText(pending.label);
  await expect(page.getByTestId("home-legend-pending")).toHaveText("If Foshan accepts Option A");
  await expect(page.getByTestId("home-receipts-legend")).toHaveText(counterEn.cash.receipts_legend_text);
  await expect(page.getByTestId("home-receipts-legend")).toHaveText("Solid: money owed or scheduled under today's terms. Dashed: if Foshan accepts Option A.");
  expect(await px(page.getByTestId("home-receipts-legend"))).toBe(13);
  const rows = page.getByTestId("home-pending-rows-row");
  await expect(rows).toHaveCount(pending.receipt_rows.length);
  for (const [i, r] of pending.receipt_rows.entries()) {
    await expect(rows.nth(i)).toHaveAttribute("data-basis", "PENDING");
    await expect(rows.nth(i).getByTestId("home-pending-rows-text")).toHaveText(r.basis_text);
  }
  // The solid rail row is still the terms in force: the day-32 receipt is owed, not pending.
  await expect(page.getByTestId("rail-basis-5")).toHaveText(OWED_32);
  // The late scenario is the stressed plan: the dashed alternative is left out while it is on, and back after.
  // (the recording has the stress off; the scenario switch is absent, so the line stays)
  await expect(page.getByTestId("home-scenario-late")).toHaveCount(0);

  // Cash draws the same alternative and the same sentences.
  await cash(page);
  await expect(page.getByTestId("picture-line-pending")).toHaveAttribute("stroke-dasharray", "6 5");
  await expect(page.getByTestId("picture-line-pending")).toHaveAttribute("opacity", "0.6");
  await expect(page.getByTestId("picture-pending-legend")).toHaveText("If Foshan accepts Option A");
  await expect(page.getByTestId("cash-receipts-legend")).toHaveText(counterEn.cash.receipts_legend_text);
  const cashRows = page.getByTestId("cash-pending-rows-row");
  await expect(cashRows).toHaveCount(3);
  await expect(cashRows.first().getByTestId("cash-pending-rows-text")).toHaveText("if Foshan accepts Option A: ¥257,200 paid 2 days after the offer");
  await expect(page.locator("[data-testid='cash-receipts-row'][data-basis='PENDING']")).toHaveCount(0);
  await expect(page.getByTestId("picture-line-nothing")).not.toHaveAttribute("stroke-dasharray", /./);
});

test("after the buyer accepts: the dashed line is gone and the moved receipts are agreed; Home and Cash say the same word", async ({ page }) => {
  await readOffer(page);
  await acceptCounter(page);
  await home(page);
  await expect(page.getByTestId("home-line-pending")).toHaveCount(0);
  await expect(page.getByTestId("home-receipts-legend")).toHaveCount(0);
  await expect(page.getByTestId("home-pending-rows")).toHaveCount(0);
  const agreed = quietEn.cash.events_rail.filter((e) => e.basis === "AGREED");
  expect(agreed.length).toBe(2);
  const homeWords: string[] = [];
  for (const e of agreed) {
    const i = quietEn.cash.events_rail.indexOf(e);
    const word = page.getByTestId(`rail-basis-${i}`);
    await expect(word).toHaveText("under the agreement made today");
    await expect(word).toHaveAttribute("data-basis", "AGREED");
    homeWords.push((await word.textContent()) ?? "");
  }
  await cash(page);
  await expect(page.getByTestId("picture-line-pending")).toHaveCount(0);
  await expect(page.getByTestId("cash-receipts-legend")).toHaveCount(0);
  const cashAgreed = page.locator("[data-testid='cash-receipts-row'][data-basis='AGREED']");
  await expect(cashAgreed.first()).toBeVisible();
  for (const w of homeWords) await expect(cashAgreed.first().getByTestId("cash-receipts-text")).toHaveText(w);
  await expect(page.locator("[data-testid='cash-receipts-row'][data-basis='SCHEDULED']").first()).toBeVisible();
  // Receivables agrees.
  await page.goto("/receivables");
  await expect(page.locator("[data-testid^='recv-basis-']").first()).toHaveText("under the agreement made today");
});

test("a counter the buyer refuses changes nothing: no pending line, the terms in force stand", async ({ page }) => {
  await readOffer(page);
  await openReview(page);
  const response = page.locator("#counters");
  await response.getByTestId("deal-send").click();
  const box = response.getByTestId("deal-send-confirm-box");
  await box.getByLabel("Holds firm").check();
  await box.getByTestId("deal-send-confirm").click();
  await expect(page.getByTestId("deal-recommendation")).toHaveAttribute("data-outcome", "NO_DEAL");
  await home(page);
  await expect(page.getByTestId("home-line-pending")).toHaveCount(0);
  await expect(page.getByTestId("home-receipts-legend")).toHaveCount(0);
  // (the refusal funds the gap anyway, so the rail has moved on: the receipt is still the owed invoice, under the terms in force)
  await expect(page.locator("[data-testid^='rail-basis-'][data-basis='OWED']")).toHaveText(OWED_32);
  await expect(page.locator("[data-testid^='rail-basis-'][data-basis='AGREED']")).toHaveCount(0);
});

test("Chinese: the words, the legend and the pending rows are the server's, in both pages", async ({ page }) => {
  await readOffer(page);
  await lang(page, "zh");
  await home(page);
  const owedZh = counterZh.cash.events_rail[5].basis_text!;
  await expect(page.getByTestId("home-legend-pending")).toHaveText("如果 Foshan 接受方案 A");
  await expect(page.getByTestId("home-receipts-legend")).toHaveText("实线：按现行条款已应收或已按计划的款项。虚线：如果 Foshan 接受方案 A。");
  await expect(page.getByTestId("home-pending-rows-text").first()).toHaveText("如果 Foshan 接受方案 A：报价后 2 天收到 ¥257,200");
  await expect(page.getByTestId("rail-basis-5")).toHaveText(owedZh);
  await expect(page.getByTestId("rail-basis-5")).toHaveText("应收：13 天前开票，32 天后到期");
  await cash(page);
  await expect(page.getByTestId("cash-receipts-legend")).toContainText("虚线：如果 Foshan 接受方案 A");
  await expect(page.getByRole("heading", { name: "您的收款依据" })).toBeVisible();
  await expect(page.locator("[data-testid='cash-receipts-row'][data-basis='SCHEDULED']").first().getByTestId("cash-receipts-text")).toHaveText("按计划：尚未开票");
  await page.goto("/receivables");
  await expect(page.getByTestId("recv3-scheduled-note")).toHaveText("另有 ¥420,000 计划于 2 天后开票；目前尚未应收");
  // No English leaks into the basis words.
  const said = await page.getByTestId("recv3-list").innerText();
  expect(said).not.toMatch(/owed:|scheduled:|under the agreement/);
});

test("phone 390x844: the pending picture, its sentence and rows fit, with no sideways scroll, on Home and Cash", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await readOffer(page);
  await home(page);
  await expect(page.getByTestId("home-line-pending")).toBeAttached();
  await expect(page.getByTestId("home-receipts-legend")).toBeVisible();
  await expect(page.getByTestId("home-pending-rows-row").first()).toBeVisible();
  expect(await noSideways(page)).toBeLessThanOrEqual(1);
  const row = (await page.getByTestId("rail-basis-5").boundingBox())!;
  expect(row.x).toBeGreaterThanOrEqual(0);
  expect(row.x + row.width).toBeLessThanOrEqual(390);
  await cash(page);
  await expect(page.getByTestId("picture-line-pending")).toBeAttached();
  await expect(page.getByTestId("cash-receipts-legend")).toBeVisible();
  expect(await noSideways(page)).toBeLessThanOrEqual(1);
  await page.goto("/receivables");
  await expect(page.locator("[data-testid^='recv-basis-']").first()).toBeVisible();
  const note = (await page.getByTestId("recv3-scheduled-note").boundingBox())!;
  expect(note.x + note.width).toBeLessThanOrEqual(390);
  expect(await noSideways(page)).toBeLessThanOrEqual(1);
});

test("reduced motion: the pending line adds no transition and the cursor jumps; with motion the cursor eases", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await readOffer(page);
  await home(page);
  await expect(page.getByTestId("home-line-pending")).not.toHaveClass(/transition|animate/);
  await expect(page.getByTestId("home-cursor").locator("> g")).not.toHaveClass(/transition-transform/);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.reload();
  await expect(page.getByTestId("home-cursor").locator("> g")).toHaveClass(/transition-transform/);
});

test("the keyboard reaches the receipt row and its words are part of the row's name", async ({ page }) => {
  await home(page);
  const row = page.getByTestId("rail-row-5");
  await row.focus();
  await expect(row).toBeFocused();
  await expect(row).toContainText(OWED_32);
  await page.keyboard.press("Enter");
  await expect(row).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("rail-effect")).toBeVisible();
});
