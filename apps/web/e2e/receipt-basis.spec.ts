import { expect, test } from "./fixtures";
import type { Locator, Page } from "@playwright/test";
import { openReview, sendCounter, verdictHeading } from "./helpers";
import counterEn from "../mocks/home_summary_day0_counter.json";
import counterZh from "../mocks/home_summary_day0_counter_zh.json";
import receivablesDay0 from "../mocks/receivables/day0.json";

/**
 * Receipts say what they rest on (ticket #116, web half), in mock mode on the recorded story: the invoice is OWED (day 32), the recurring billing SCHEDULED (day 47 and
 * later), the pending counter is a dashed alternative with its sentence and receipts (never the plan line), and once the buyer accepts the moved receipts are AGREED and the
 * dashed line is gone. Cash and Receivables say the same words for the same receipt (Home V2's forecast draws no receipt rows; its planned and proposed legend words are in home-v2.spec.ts). Every sentence asserted is read from the recording or is the golden one the
 * server's tests pin; none is composed in the browser.
 */
test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "mock-mode spec on the recorded story (the phone is measured inside it)");
});

const OWED_32 = "owed: invoiced 13 days ago, due in 32 days";
const SCHEDULED = "scheduled: not yet invoiced";
const AFTER_CHECK = /Don't accept as asked|Counter instead of accepting as asked/;

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

async function cash(page: Page) {
  await page.goto("/cash");
  await expect(page.getByTestId("cash-forecast")).toBeVisible();
  await expect(page.getByTestId("cash-receipts")).toBeVisible();
}

/** The font size of an element, as the browser resolved it. */
const px = (el: Locator) => el.evaluate((n) => parseFloat(getComputedStyle(n).fontSize));
const noSideways = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

test("day 0: Cash says the invoice is owed, the later billing is scheduled, and no pending line or legend is drawn", async ({ page }) => {
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

test("Receivables says the same words as Cash, and the summary says the recurring billing is not owed yet", async ({ page }) => {
  await page.goto("/receivables");
  const row = receivablesDay0.rows[0];
  const text = page.getByTestId(`recv-basis-${row.receivable_id}`);
  await expect(text).toHaveText(OWED_32);
  const words = (await text.textContent()) ?? "";
  expect(await px(text)).toBe(13);
  await expect(page.getByTestId("recv3-scheduled-note")).toHaveText(receivablesDay0.summary.scheduled_note);
  await expect(page.getByTestId("recv3-scheduled-note")).toHaveText("¥420,000 more is scheduled to be invoiced in 2 days; it is not owed yet");
  await cash(page);
  await expect(page.locator("[data-testid='cash-receipts-row'][data-basis='OWED']").getByTestId("cash-receipts-text")).toHaveText(words);
});

test("with the counter ready: Cash draws the pending line dashed at 60%, with its legend, sentence and receipts", async ({ page }) => {
  await readOffer(page);
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

test("after the buyer accepts: the dashed line is gone and the moved receipts are agreed; Cash and Receivables say the same word", async ({ page }) => {
  await readOffer(page);
  await acceptCounter(page);
  await cash(page);
  await expect(page.getByTestId("picture-line-pending")).toHaveCount(0);
  await expect(page.getByTestId("cash-receipts-legend")).toHaveCount(0);
  const cashAgreed = page.locator("[data-testid='cash-receipts-row'][data-basis='AGREED']");
  await expect(cashAgreed.first()).toBeVisible();
  await expect(cashAgreed.first().getByTestId("cash-receipts-text")).toHaveText("under the agreement made today");
  await expect(page.locator("[data-testid='cash-receipts-row'][data-basis='SCHEDULED']").first()).toBeVisible();
  // Receivables agrees.
  await page.goto("/receivables");
  await expect(page.locator("[data-testid^='recv-basis-']").first()).toHaveText("under the agreement made today");
});

test("a counter the buyer refuses changes nothing: no pending line, the terms in force stand", async ({ page }) => {
  // The simulated buyer's lean is the Demo's control.
  await page.addInitScript(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "demo" })));
  await readOffer(page);
  await openReview(page);
  const box = page.locator("#counters").getByTestId("deal-send-confirm-box");
  await box.getByLabel("Holds firm").check();
  await sendCounter(page);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "NO_DEAL");
  await cash(page);
  await expect(page.getByTestId("picture-line-pending")).toHaveCount(0);
  await expect(page.getByTestId("cash-receipts-legend")).toHaveCount(0);
  // (the refusal funds the gap anyway, so the picture has moved on: the receipt is still the owed invoice, under the terms in force)
  await expect(page.locator("[data-testid='cash-receipts-row'][data-basis='OWED']").getByTestId("cash-receipts-text")).toHaveText(OWED_32);
  await expect(page.locator("[data-testid='cash-receipts-row'][data-basis='AGREED']")).toHaveCount(0);
});

test("Chinese: the words, the legend and the pending rows are the server's, on Cash and Receivables", async ({ page }) => {
  await readOffer(page);
  await lang(page, "zh");
  await cash(page);
  await expect(page.getByTestId("picture-pending-legend")).toHaveText("如果 Foshan 接受方案 A");
  await expect(page.getByTestId("cash-pending-rows-text").first()).toHaveText("如果 Foshan 接受方案 A：报价后 2 天收到 ¥257,200");
  await expect(page.locator("[data-testid='cash-receipts-row'][data-basis='OWED']").getByTestId("cash-receipts-text")).toHaveText(counterZh.cash.events_rail[5].basis_text!);
  await expect(page.locator("[data-testid='cash-receipts-row'][data-basis='OWED']").getByTestId("cash-receipts-text")).toHaveText("应收：13 天前开票，32 天后到期");
  await expect(page.getByTestId("cash-receipts-legend")).toContainText("虚线：如果 Foshan 接受方案 A");
  await expect(page.getByRole("heading", { name: "您的收款依据" })).toBeVisible();
  await expect(page.locator("[data-testid='cash-receipts-row'][data-basis='SCHEDULED']").first().getByTestId("cash-receipts-text")).toHaveText("按计划：尚未开票");
  await page.goto("/receivables");
  await expect(page.getByTestId("recv3-scheduled-note")).toHaveText("另有 ¥420,000 计划于 2 天后开票；目前尚未应收");
  // No English leaks into the basis words.
  const said = await page.getByTestId("recv3-list").innerText();
  expect(said).not.toMatch(/owed:|scheduled:|under the agreement/);
});

test("phone 390x844: the pending picture, its sentence and rows fit, with no sideways scroll, on Cash and Receivables", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await readOffer(page);
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
