import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { runPlan } from "./helpers";
import after from "../mocks/receivables/after_fund.json";
import afterZh from "../mocks/receivables/after_fund_zh.json";
import day0 from "../mocks/receivables/day0.json";
import day34 from "../mocks/receivables/day34.json";
import offer from "../mocks/receivables/offer.json";
import offerZh from "../mocks/receivables/offer_zh.json";
import settled from "../mocks/receivables/settled.json";
import day34Half from "../mocks/receivables/day34_half.json";
import day34NoReceipt from "../mocks/receivables/day34_noreceipt.json";
import home0 from "../mocks/home_summary_day0.json";
import exposure from "../mocks/receivables/exposure_offer.json";
import buyer from "../mocks/buyer_exposure.json";
import buyerZh from "../mocks/buyer_exposure_zh.json";
import buyer34 from "../mocks/buyer_exposure_day34.json";

/**
 * Receivables in three layers (map #110) in mock mode, on the recorded GET /receivables of each point of the demo path (mocks/receivables/*.json) and the
 * buyer exposure of the open offer's decision. Every figure and sentence asserted is read from those recordings, never typed here: the page shows the
 * server's strings, and so does this spec. The lifecycle states the demo path reaches are NONE (opening books), ARRANGED (after the day-0 fix) and
 * RECEIVED (day 38); REPAID and PROMISE_MISSED are not on the path, so their rendering is the same code with another enum value and is not recorded.
 */

test.beforeEach(async ({ context }, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded demo path");
  await context.addInitScript(() => {
    try {
      sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: "mock-owner" }));
    } catch {
      /* storage unavailable */
    }
  });
});

async function advanceTo34(page: Page, to = "/receivables") {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto(to);
}

/** The books after the day-0 funding plan ran (the financing is arranged, expected in a few days). */
const sm = (read: unknown) => (read as { summary: { count_text: string; headline: string; headline_second: string | null } }).summary;
const BRAND = "rgb(3, 104, 233)";
/** Visible links and buttons filled with the brand blue: the page's primaries. */
const filled = (page: Page) =>
  page.locator("main a, main button").evaluateAll((els, brand) => els.filter((e) => getComputedStyle(e).backgroundColor === brand && e.getClientRects().length > 0).map((e) => e.getAttribute("data-testid") ?? e.textContent?.trim() ?? ""), BRAND);

async function afterFund(page: Page) {
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("fix-result")).toBeVisible();
  await page.goto("/receivables");
}

const overflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
const patch = (page: Page, value: unknown) => page.addInitScript((v) => sessionStorage.setItem("tl-mock-receivables-patch", JSON.stringify(v)), value);

test("day 0: the answer, three plain cards, one invoice with no financing, and the actions in the server's order", async ({ page }) => {
  await page.goto("/receivables");
  const row = day0.rows[0];
  await expect(page.getByTestId("recv3-page")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(page.getByTestId("recv3-status")).toHaveAttribute("data-tone", "ok");
  await expect(page.getByTestId("recv3-status")).toContainText("On track");
  await expect(page.getByTestId("recv3-status")).toContainText("Read today");
  // The two heading lines are the server's, verbatim. No sentence under them: the counts are the first card's.
  await expect(page.getByTestId("recv3-h1-expected")).toHaveText(sm(day0).headline);
  await expect(page.getByTestId("recv3-h1-net")).toHaveText(sm(day0).headline_second!);
  await expect(page.getByTestId("recv3-sub")).toHaveCount(0);
  await expect(page.getByTestId("recv3-count")).toHaveText(sm(day0).count_text);
  // The header carries no decorative icon chip.
  await expect(page.locator("header.motion-reveal").locator("span.rounded-pill")).toHaveCount(0);
  // The three cards, in the server's strings.
  await expect(page.getByTestId("recv3-owe")).toHaveText(day0.summary.outstanding_total_display);
  await expect(page.getByTestId("recv3-next")).toHaveText(new RegExp(day0.summary.next_expected.when_text, "i"));
  await expect(page.getByTestId("recv3-net")).toHaveText(day0.summary.net_total_display);
  await expect(page.getByTestId("recv3-cards")).toContainText("Customers owe you");
  await expect(page.getByTestId("recv3-cards")).toContainText("Next expected payment");
  await expect(page.getByTestId("recv3-cards")).toContainText("Expected cash at collection");
  await expect(page.getByTestId("recv3-cards")).toContainText("if every invoice is paid on its due day");
  // The row, with the customer as a link that carries the context and reaches 44 px by its hit area.
  const r = page.getByTestId(`recv-${row.receivable_id}`);
  await expect(r).toContainText(row.outstanding_display);
  await expect(r).toContainText(row.due_when);
  await expect(r).toContainText(row.collection_state_text);
  await expect(page.getByTestId(`recv-steps-${row.receivable_id}`)).toHaveText("No financing");
  const link = page.getByTestId(`recv-customer-${row.receivable_id}`);
  await expect(link).toHaveText(row.buyer_name);
  await expect(link).toHaveClass(/\bhit\b/);
  expect(new URL((await link.getAttribute("href")) ?? "", "http://x").pathname).toBe(`/customers/${row.buyer_id}`);
  // Every customer name is the shared CustomerName: it carries the context the URL holds (none here, so the plain link).
  expect(await link.getAttribute("href")).toBe(`/customers/${row.buyer_id}`);
  // The selected invoice: the condition as the heading; with no financing the breakdown is the invoice and the cash.
  await expect(page.getByTestId("recv3-detail-title")).toContainText(row.net.condition_text);
  await expect(page.getByTestId("recv3-detail-title")).toContainText(row.net.net_short);
  await expect(page.getByTestId("recv3-bd-invoice")).toHaveText(row.outstanding_display);
  await expect(page.getByTestId("recv3-bd-advance")).toHaveCount(0);
  await expect(page.getByTestId("recv3-bd-net")).toHaveText(row.net.net_display);
  await expect(page.getByTestId("recv3-terms")).toHaveText(row.governed_by.terms_text);
  await expect(page.getByTestId("recv3-facts")).toContainText("Governed by");
  expect(row.governed_by.terms_text.startsWith("Agreement ")).toBe(true);
  await expect(page.getByTestId("recv3-recourse")).toHaveCount(0);
  await expect(page.getByTestId("recv3-action-financing")).toHaveCount(0);
  await expect(page.getByTestId("recv3-early")).toContainText(row.early_payment.text);
  // The actions follow the server; CURRENT leads with the terms, then the reminder, in the dictionary's words (the board's).
  const order = await page.locator('[data-testid^="recv3-action-"]').evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
  expect(order).toEqual([row.collection_action.primary, ...row.collection_action.others.map((o) => o.action)].map((a) => `recv3-action-${a}`));
  await expect(page.getByTestId("recv3-action-VIEW_TERMS")).toHaveText("View payment terms");
  await expect(page.getByTestId("recv3-action-PREPARE_REMINDER")).toHaveText("Prepare a reminder");
  await expect(page.getByTestId("recv3-actions-note")).toBeVisible();
  // The invoice's FIRST action is the page's one filled primary; "Explore the cash impact" is outlined.
  expect(await filled(page)).toEqual(["View payment terms"]);
  expect(await page.getByTestId("recv3-explore").evaluate((e) => getComputedStyle(e).backgroundColor)).not.toBe(BRAND);
  expect(await page.locator("body").innerText()).not.toMatch(/\bDay \d|RCV-|RI:BUYER|BUYER-1/);
  // The section is named by an element that exists.
  const named = await page.getByTestId("recv3-selected").getAttribute("aria-labelledby");
  await expect(page.locator(`[id="${named}"]`)).toHaveCount(1);
});

test("the financing is arranged: the repayment is said in the answer and in the breakdown only, the steps show where it is", async ({ page }) => {
  await afterFund(page);
  const row = after.rows[0];
  expect(row.financing_state).toBe("ARRANGED");
  await expect(page.getByTestId("recv3-status")).toContainText("On track");
  await expect(page.getByTestId("recv3-h1-expected")).toHaveText(sm(after).headline);
  await expect(page.getByTestId("recv3-h1-net")).toHaveText(sm(after).headline_second!);
  expect(sm(after).headline_second).toContain("after the financing is repaid");
  // Said twice, never four times: no sub-sentence, no repeat on the cards, no separate paragraph under the breakdown.
  await expect(page.getByTestId("recv3-sub")).toHaveCount(0);
  await expect(page.getByTestId("recv3-net-financing")).toHaveCount(0);
  await expect(page.getByTestId("recv3-repays")).toHaveCount(0);
  // The lifecycle: three steps, the server's state filled; done steps carry a check, the current one a ring.
  const steps = page.getByTestId(`recv-steps-${row.receivable_id}`);
  await expect(steps).toHaveAttribute("data-state", "ARRANGED");
  await expect(steps.locator("li")).toHaveText(["Arranged", "Received", "Repaid"]);
  await expect(steps.locator('li[data-on="true"]')).toHaveText("Arranged");
  await expect(steps.locator("li[aria-current=step]")).toHaveCount(1);
  await expect(steps.locator('li[data-on="true"] span.ring-2')).toHaveCount(1);
  await expect(page.getByTestId(`recv-${row.receivable_id}`)).toContainText(row.net.advance_display);
  await expect(page.getByTestId(`recv-net-${row.receivable_id}`)).toHaveText(row.net.net_short);
  // The selected row has a 3 px left rule as well as its tint.
  expect(await page.getByTestId(`recv-${row.receivable_id}`).evaluate((e) => getComputedStyle(e).borderLeftWidth)).toBe("3px");
  // The breakdown: the invoice, less the financing with the server's repayment note, less the charges with the per-period note, the cash.
  await expect(page.getByTestId("recv3-bd-invoice")).toHaveText(row.outstanding_display);
  await expect(page.getByTestId("recv3-bd-advance")).toContainText(row.net.advance_display);
  await expect(page.getByTestId("recv3-bd-state")).toHaveText(row.net.repays_note);
  await expect(page.getByTestId("recv3-bd-charges")).toContainText(row.net.charges_display);
  await expect(page.getByTestId("recv3-breakdown")).toContainText(row.net.per_period_text);
  await expect(page.getByTestId("recv3-bd-net")).toHaveText(row.net.net_display);
  await expect(page.getByTestId("recv3-recourse")).toHaveText(row.recourse_text);
  // "View the financing" is the record of the request, shown because the server sent the link.
  const financing = page.getByTestId("recv3-action-financing");
  await expect(financing).toHaveText("View the financing");
  expect(await financing.getAttribute("href")).toBe(row.financing_href);
  // The aside is the buyer's one scope: it carries no line about this invoice's financing.
  await expect(page.getByTestId("recv3-stress-financing")).toHaveCount(0);
});

test("day 38: the financing has been received, the step moves on", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-home-v4", JSON.stringify({ day: 38, stage: "approved", funded: false, receipted: true, moved: 0 })));
  await page.goto("/receivables");
  const received = settled.rows.find((r) => r.financing_state === "RECEIVED")!;
  const steps = page.getByTestId(`recv-steps-${received.receivable_id}`);
  await expect(steps).toHaveAttribute("data-state", "RECEIVED");
  await expect(steps.locator('li[data-on="true"]')).toHaveText("Received");
  await expect(steps.locator('li[data-step="ARRANGED"]')).not.toHaveAttribute("data-on", "true");
  await expect(steps.locator('li[data-step="ARRANGED"] svg')).toHaveCount(1);
  // Each step's word is a StateWord (#112): a step already passed is green, the current one blue, the one to come quiet.
  await expect(steps.locator('li[data-step="ARRANGED"] [data-state="arranged"]')).toHaveAttribute("data-tone", "ok");
  await expect(steps.locator('li[data-step="RECEIVED"] [data-state="received"]')).toHaveAttribute("data-tone", "info");
  await expect(steps.locator('li[data-step="REPAID"] [data-state="repaid"]')).toHaveAttribute("data-tone", "neutral");
});

test("day 34: the pills filter by the server's collection state, an empty pill is disabled, and the late invoice leads", async ({ page }) => {
  await advanceTo34(page);
  const ids = day34.rows.map((r) => r.receivable_id);
  for (const id of ids) await expect(page.getByTestId(`recv-${id}`)).toBeVisible();
  await expect(page.getByTestId("recv3-status")).toHaveAttribute("data-tone", "bad");
  await expect(page.getByTestId("recv3-status")).toContainText("Overdue");
  await expect(page.getByTestId("recv3-h1-expected")).toHaveText(sm(day34).headline);
  await expect(page.getByTestId("recv3-count")).toHaveText(sm(day34).count_text);
  const late = day34.rows.filter((r) => r.collection_state === "OVERDUE").length;
  const soon = day34.rows.filter((r) => r.collection_state === "DUE_SOON").length;
  await expect(page.getByTestId("recv-filter-all")).toHaveAttribute("aria-selected", "true");
  // Each tab says how many rows the server sent it holds, "0" included; a tab with none is disabled but still says so.
  await expect(page.getByTestId("recv-filter-overdue")).toContainText("Overdue");
  await expect(page.getByTestId("recv-filter-count-overdue")).toHaveText(String(late));
  await expect(page.getByTestId("recv-filter-count-overdue")).toHaveAttribute("data-tone", "alert");
  await expect(page.getByTestId("recv-filter-count-promises")).toHaveText("0");
  await expect(page.getByTestId("recv-filter-count-promises")).toHaveAttribute("data-tone", "neutral");
  await expect(page.getByTestId("recv-filter-count-all")).toHaveText(String(ids.length));
  if (soon === 0) await expect(page.getByTestId("recv-filter-soon")).toBeDisabled();
  await expect(page.getByTestId("recv-filter-promises")).toBeDisabled();
  await page.getByTestId("recv-filter-overdue").click();
  await expect(page.getByTestId("recv-filter-overdue")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator('[data-testid^="recv-state-"]')).toHaveCount(late);
  await expect(page.locator('[data-testid^="recv-state-"]').first()).toHaveText(day34.rows.find((r) => r.collection_state === "OVERDUE")!.collection_state_text);
  // The state is a StateWord (#112): the server's word, the state's tone and a glyph, so it is never colour alone; the lifecycle's words are StateWords too.
  await expect(page.locator('[data-testid^="recv-state-"]').first()).toHaveAttribute("data-state", "overdue");
  await expect(page.locator('[data-testid^="recv-state-"]').first()).toHaveAttribute("data-tone", "bad");
  await expect(page.locator('[data-testid^="recv-state-"]').first().locator("svg[aria-hidden=true]")).toHaveCount(1);
  await page.getByTestId("recv-filter-all").click();
  await expect(page.locator('[data-testid^="recv-state-"]')).toHaveCount(ids.length);
  // The late invoice is first in the server's order and is the one shown.
  await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", day34.rows[0].receivable_id);

  // The filter is a SegmentedTabs tablist (#112): one tab stop, 44 px tabs, the arrows move the choice and skip a pill with nothing behind it, and wrap.
  await expect(page.getByRole("tablist", { name: "Show invoices" })).toBeVisible();
  await expect(page.getByRole("tab")).toHaveCount(4);
  await expect(page.locator('[data-testid^="recv-filter-"][tabindex="0"]')).toHaveCount(1);
  for (const id of ["all", "overdue"]) expect((await page.getByTestId(`recv-filter-${id}`).boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await page.getByTestId("recv-filter-all").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId(soon === 0 ? "recv-filter-overdue" : "recv-filter-soon")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId(soon === 0 ? "recv-filter-overdue" : "recv-filter-soon")).toBeFocused();
  await page.keyboard.press("End");
  await expect(page.getByTestId("recv-filter-overdue")).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("recv-filter-all")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("recv-filter-all")).toBeFocused();
});

test("the filter moves the selection: when the chosen invoice leaves the visible set, the first visible one is chosen", async ({ page }) => {
  await advanceTo34(page);
  const [overdue, current] = [day34.rows[0], day34.rows[1]];
  await page.getByTestId(`recv-select-${current.receivable_id}`).click();
  await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", current.receivable_id);
  await page.getByTestId("recv-filter-overdue").click();
  await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", overdue.receivable_id);
  await expect(page).toHaveURL(new RegExp(`invoice=${encodeURIComponent(overdue.receivable_id)}`));
  await expect(page.getByTestId("recv3-strip")).toHaveCount(0);
  // Back to all: the choice stays on the overdue one (it is still visible).
  await page.getByTestId("recv-filter-all").click();
  await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", overdue.receivable_id);
});

test("selecting an invoice replaces the detail in place and sets ?invoice=; the actions follow the invoice: Chase payment first when overdue", async ({ page }) => {
  await advanceTo34(page);
  const [overdue, current] = [day34.rows[0], day34.rows[1]];
  expect(overdue.collection_state).toBe("OVERDUE");
  expect(current.collection_state).toBe("CURRENT");
  const actionOrder = () => page.locator('[data-testid^="recv3-action-"]').evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
  const expected = (r: typeof overdue) => [r.collection_action.primary, ...r.collection_action.others.map((o) => o.action)].map((a) => `recv3-action-${a}`);
  expect(await actionOrder()).toEqual(expected(overdue));
  expect((await actionOrder())[0]).toBe("recv3-action-CHASE");
  await expect(page.getByTestId("recv3-action-CHASE")).toHaveText("Chase payment");
  // Once overdue the standing note about the reminder is gone.
  await expect(page.getByTestId("recv3-actions-note")).toHaveCount(0);
  // The first action is the one filled primary.
  expect(await filled(page)).toEqual(["chase-detail-CHASE-open-" + overdue.receivable_id]);
  // Choose the other invoice with the keyboard: Tab to its button, Enter.
  const pick = page.getByTestId(`recv-select-${current.receivable_id}`);
  await pick.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`invoice=${encodeURIComponent(current.receivable_id).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`));
  await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", current.receivable_id);
  await expect(page.getByTestId(`recv-${current.receivable_id}`)).toHaveAttribute("data-selected", "true");
  await expect(page.getByTestId(`recv-select-${current.receivable_id}`)).toHaveAttribute("aria-current", "true");
  await expect(page.getByTestId(`recv-${overdue.receivable_id}`)).not.toHaveAttribute("data-selected", "true");
  await expect(page.getByTestId("recv3-announce")).toContainText(current.invoice);
  expect(await actionOrder()).toEqual(expected(current));
  expect((await actionOrder())[0]).toBe("recv3-action-VIEW_TERMS");
  await expect(page.getByTestId("recv3-action-CHASE")).toHaveCount(0);
  await expect(page.getByTestId("recv3-actions-note")).toBeVisible();
  // The list is kept: all three rows are still there, and a reload restores the choice.
  await expect(page.locator('[data-testid^="recv-select-"]')).toHaveCount(day34.rows.length);
  await page.reload();
  await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", current.receivable_id);
});

test("day 34: Chase payment opens the handoff, Copy copies the request, Escape returns focus to the button", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await advanceTo34(page);
  const overdue = day34.rows[0];
  const open = page.getByTestId(`chase-detail-CHASE-open-${overdue.receivable_id}`);
  await expect(open).toHaveText("Chase payment");
  expect((await open.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(40);
  await open.click();
  const dialog = page.getByTestId(`chase-detail-CHASE-dialog-${overdue.receivable_id}`);
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "Chase payment: Foshan Home Retail Co." })).toBeVisible();
  await expect(dialog.getByTestId("chase-fact-outstanding")).toContainText("¥162,800.00");
  await expect(dialog.getByTestId("chase-fact-late")).toContainText("2 days");
  await expect(dialog.getByTestId("chase-fact-promise-0")).toContainText("¥255,013.80");
  const request = dialog.getByTestId("chase-request");
  await expect(request).toContainText("¥162,800.00 remains outstanding");
  const asked = await request.innerText();
  expect(asked).not.toMatch(/CMT-|RCV-|\bday \d/);
  await dialog.getByTestId("chase-copy").click();
  await expect(dialog.getByTestId("chase-copy-status")).toHaveText("Copied");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(asked);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(open).toBeFocused();
});

test("day 34 in Chinese: the chase handoff and the request are the server's Chinese", async ({ page }) => {
  await advanceTo34(page);
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.goto("/receivables");
  await page.getByTestId(`chase-detail-CHASE-open-${day34.rows[0].receivable_id}`).click();
  await expect(page.getByTestId("chase-request")).toContainText("请确认付款日期");
});

test("day 34: what was promised early and what arrived stay under the layers, in the layers' heading style", async ({ page }) => {
  await advanceTo34(page);
  await expect(page.getByRole("heading", { name: "Expected early payments" })).toBeVisible();
  await expect(page.getByTestId("promised-RCV-A")).toContainText("¥255,013.80");
  await expect(page.getByTestId("promised-RCV-A")).toHaveAttribute("data-status", "RECEIVED");
  await expect(page.getByRole("heading", { name: "Payments received" })).toBeVisible();
  await expect(page.getByTestId("receipt-rec-receipt-1")).toContainText("Foshan Home Retail Co.");
  await expect(page.getByTestId("receipt-ref-rec-receipt-1")).toContainText("DEMO-RCPT-1");
  // 13 px at least for what the owner reads: the sections' captions are 14 px.
  expect(await page.getByTestId("promised-RCV-A").locator("span.block").first().evaluate((e) => parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(13);
  expect(await page.locator("#recv-promised h2").evaluate((e) => getComputedStyle(e).textTransform)).toBe("uppercase");
});

test("day 34 after the half receipt: the receipt names its four facts and the chase balance is the one the row shows", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-no-receipt", "half"));
  await advanceTo34(page);
  const row = day34Half.rows[0];
  await expect(page.getByTestId(`recv-${row.receivable_id}`)).toContainText(row.outstanding_display);
  await page.getByTestId(`chase-detail-CHASE-open-${row.receivable_id}`).click();
  const dialog = page.getByTestId(`chase-detail-CHASE-dialog-${row.receivable_id}`);
  await expect(dialog.getByTestId("chase-fact-outstanding")).toHaveText(new RegExp(row.outstanding_display.replace(/[.$]/g, "\\$&")));
  await dialog.getByTestId("chase-close").click();
  await expect(dialog).toBeHidden();
  const facts = page.getByTestId("receipt-facts-rec-receipt-1");
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-received")).toContainText("¥127,506.90");
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-cleared")).toContainText("¥128,600.00");
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-discount")).toContainText("¥1,093.10");
  await expect(facts.getByTestId("receipt-facts-rec-receipt-1-remaining")).toContainText("¥291,400.00");
  await expect(facts).toContainText("The early-payment window has ended");
});

test("day 34 with no receipt: the overdue invoice is first and the promise did not arrive", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-no-receipt", "1"));
  await advanceTo34(page);
  const first = day34NoReceipt.rows[0];
  await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", first.receivable_id);
  await expect(page.getByTestId("recv3-status")).toHaveAttribute("data-tone", "bad");
  await expect(page.getByTestId(`recv-state-${first.receivable_id}`)).toHaveText(first.collection_state_text);
  await expect(page.getByTestId("recv3-action-CHASE")).toHaveCount(1);
});

test("the late-payment test is the buyer's own read, with no deal in context: the server's strings in the buyer's short name, a breach in red", async ({ page }) => {
  await page.goto("/receivables");
  const row = day0.rows[0];
  const now = buyer.stress.now;
  const short = (buyer as { concentration: { buyer_name: string } }).concentration.buyer_name;
  await expect(page.getByTestId("recv3-stress")).toContainText(`If ${short} pays ${buyer.stress.delay_days} days late`);
  await expect(page.getByTestId("recv3-stress-cash")).toHaveText(`${now.lowest_short} ${now.lowest_when}`);
  await expect(page.getByTestId("recv3-stress-minimum")).toHaveText(now.funding_text);
  expect(now.first_breach_when).toBeTruthy();
  await expect(page.getByTestId("recv3-stress-cash")).toHaveClass(/text-bad-fg/);
  await expect(page.getByTestId("recv3-stress-minimum")).toHaveClass(/text-bad-fg/);
  await expect(page.getByTestId("recv3-stress-later")).toHaveText(new RegExp(`^${now.net_later_text}$`, "i"));
  await expect(page.getByTestId("recv3-history")).toHaveText(buyer.payments.sentence);
  await expect(page.getByTestId("recv3-concentration")).toContainText(buyer.concentration.ar_text);
  await expect(page.getByTestId("recv3-concentration-link")).toHaveClass(/\bhit\b/);
  // The explore link is secondary: a link into Cash carrying the buyer, the invoice and the context.
  const explore = page.getByTestId("recv3-explore");
  await expect(explore).toHaveText("Explore the cash impact");
  const href = new URL((await explore.getAttribute("href")) ?? "", "http://x");
  expect(href.pathname).toBe("/cash");
  expect(href.searchParams.get("stress")).toBe(`${row.buyer_id}:${buyer.stress.delay_days}`);
  expect(href.searchParams.get("invoice")).toBe(row.receivable_id);
  expect(href.searchParams.get("customer")).toBe(row.buyer_id);
  await expect(page.getByText("coming back keeps this invoice selected")).toBeVisible();
});

test("the customer link carries the context of the URL it is on, in the shared order", async ({ page }) => {
  await page.goto("/receivables?decision=deal%3AOFF-x&path=asked&invoice=RCV-A");
  await expect(page.getByTestId("recv-customer-RCV-A")).toHaveAttribute("href", "/customers/BUYER-1?decision=deal%3AOFF-x&path=asked&invoice=RCV-A");
});

test("day 34: the buyer read is the one taken on day 34's books", async ({ page }) => {
  await advanceTo34(page);
  await expect(page.getByTestId("recv3-stress-later")).toHaveText(new RegExp(`^${buyer34.stress.now.net_later_text}$`, "i"));
  await expect(page.getByTestId("recv3-stress-cash")).toHaveText(`${buyer34.stress.now.lowest_short} ${buyer34.stress.now.lowest_when}`);
});

test("a deal in the address (?decision=) is read for its own test; the counter's link carries the decision", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-offer", "1"));
  await page.goto(`/receivables?decision=${encodeURIComponent(exposure.decision_id)}`);
  const row = offer.rows[0];
  const now = exposure.stress.now;
  expect(row.pending_counter.decision_id).toBe(exposure.decision_id);
  await expect(page.getByTestId("recv3-stress-cash")).toHaveText(`${now.lowest_short} ${now.lowest_when}`);
  await expect(page.getByTestId("recv3-stress-minimum")).toHaveText(now.funding_text);
  await expect(page.getByTestId("recv3-counter")).toHaveText(row.pending_counter.text);
  const deal = new URL((await page.getByTestId("recv3-counter").getAttribute("href")) ?? "", "http://x");
  expect(deal.pathname).toBe("/deals");
  expect(deal.searchParams.get("decision")).toBe(exposure.decision_id);
  const href = new URL((await page.getByTestId("recv3-explore").getAttribute("href")) ?? "", "http://x");
  expect(href.searchParams.get("decision")).toBe(exposure.decision_id);
});

test("the stress figures are the very strings Home shows for the same buyer", async ({ page }) => {
  // Home's picture carries the late-payment scenario of its buyer (`hybrid.stress`); the aside reads the same server sentences.
  const stress = (home0 as { hybrid?: { stress?: { buyer_id?: string; lowest_short: string; lowest_when: string } | null } }).hybrid?.stress;
  test.skip(!stress, "the committed Home recording predates the Home hybrid's stress block: the lead re-records it");
  await page.goto("/receivables");
  expect(stress!.buyer_id).toBe(day0.rows[0].buyer_id);
  await expect(page.getByTestId("recv3-stress-cash")).toHaveText(`${stress!.lowest_short} ${stress!.lowest_when}`);
});

test("Chinese: the same page and figures in the server's Chinese, with the dictionary's words", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" }));
    sessionStorage.setItem("tl-mock-receivables-offer", "1");
  });
  await page.goto("/receivables");
  const row = offerZh.rows[0];
  await expect(page.getByTestId("recv3-status")).toContainText("一切按计划");
  await expect(page.getByTestId("recv3-h1-expected")).toHaveText(sm(offerZh).headline);
  await expect(page.getByTestId("recv3-owe")).toHaveText(offerZh.summary.outstanding_total_display);
  await expect(page.getByTestId("recv3-cards")).toContainText("客户欠您");
  await expect(page.getByTestId(`recv-${row.receivable_id}`)).toContainText(row.due_when);
  await expect(page.getByTestId("recv3-detail-title")).toContainText(row.net.condition_text);
  await expect(page.getByTestId("recv3-terms")).toHaveText(row.governed_by.terms_text);
  await expect(page.getByTestId("recv3-facts")).toContainText("适用条款");
  await expect(page.getByTestId("recv3-action-VIEW_TERMS")).toHaveText("查看付款条款");
  await expect(page.getByTestId("recv3-stress-cash")).toContainText(buyerZh.stress.now.lowest_when);
  await expect(page.getByTestId("recv3-stress-minimum")).toHaveText(buyerZh.stress.now.funding_text);
  await expect(page.getByTestId("recv3-stress-later")).toContainText(buyerZh.stress.now.net_later_text);
  await expect(page.getByTestId("recv3-explore")).toHaveText("查看对现金的影响");
  expect(await page.locator("main").innerText()).not.toMatch(/\bDay \d|RCV-|BUYER-1/);
  // The financed books, in Chinese: the steps are the dictionary's, and the answer's second line reads as a sentence.
  await afterFund(page);
  await expect(page.getByTestId(`recv-steps-${afterZh.rows[0].receivable_id}`).locator("li")).toHaveText(["已安排", "已到账", "已还清"]);
  await expect(page.getByTestId("recv3-h1-net")).toHaveText(sm(afterZh).headline_second!);
  expect(sm(afterZh).headline_second).not.toContain("为 约");
});

test("a server without GET /receivables keeps the page of before; a failure is an error with Retry, never a silent fallback", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-absent", "1"));
  await page.goto("/receivables");
  await expect(page.getByTestId("recv-summary")).toBeVisible();
  await expect(page.getByTestId("recv3-page")).toHaveCount(0);
});

test("a failed read of the receivables says so with Retry, and Retry brings the page back", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-fail", "1"));
  await page.goto("/receivables");
  await expect(page.getByText("The receivables are unavailable")).toBeVisible();
  await expect(page.getByTestId("recv-summary")).toHaveCount(0);
  await expect(page.getByTestId("recv3-page")).toHaveCount(0);
  await page.evaluate(() => sessionStorage.removeItem("tl-mock-receivables-fail"));
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByTestId("recv3-page")).toBeVisible();
});

test("a failed read of the reconciliation shows the error with Retry under the layers, never a vanished section", async ({ page }) => {
  await advanceTo34(page, "/");
  await page.evaluate(() => sessionStorage.setItem("tl-mock-reconciliation-fail", "1"));
  await page.goto("/receivables");
  const failed = page.getByTestId("recv3-history-failed");
  await expect(failed).toBeVisible();
  await expect(page.getByTestId("recv3-page")).toBeVisible();
  await page.evaluate(() => sessionStorage.removeItem("tl-mock-reconciliation-fail"));
  await failed.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByTestId("promised-RCV-A")).toBeVisible();
  await expect(failed).toHaveCount(0);
});

// The three states below are not on the demo path, so they are seen through a temporary in-spec patch of the recorded read
// (the mock's tl-mock-receivables-patch hook) until the server's fields are recorded.

test("patched: an invoice marked financed with no financing on record says so in place of the net, and the section is still named", async ({ page }) => {
  await patch(page, { rows: { "RCV-A": { financing_state: "NONE", net: { financing_unrecorded: true, unrecorded_text: "This invoice is marked as financed but no financing is on record, so the net shown is before any financing." } } } });
  await page.goto("/receivables");
  await expect(page.getByTestId("recv3-unrecorded")).toHaveText("This invoice is marked as financed but no financing is on record, so the net shown is before any financing.");
  await expect(page.getByTestId("recv3-detail-title")).toHaveCount(0);
  await expect(page.getByTestId("recv3-breakdown")).toHaveCount(0);
  await expect(page.getByTestId("recv-net-RCV-A")).toContainText("no financing is on record");
  const named = await page.getByTestId("recv3-selected").getAttribute("aria-labelledby");
  await expect(page.locator(`[id="${named}"]`)).toHaveCount(1);
});

test("patched: a partial read shows the notice with Retry", async ({ page }) => {
  await patch(page, { partial: { missing: ["reconciliation"], missing_text: ["the early-payment promises"], text: "Not everything could be read: the early-payment promises." } });
  await page.goto("/receivables");
  await expect(page.getByTestId("partial-read")).toContainText("the early-payment promises");
  await expect(page.getByTestId("partial-retry")).toBeVisible();
});

test("patched: a missed promise is overdue in tone, has its own pill, and Chase payment leads", async ({ page }) => {
  await patch(page, {
    rows: { "RCV-A": { collection_state: "PROMISE_MISSED", collection_state_text: "Promise missed", collection_action: { primary: "CHASE", label: "Chase payment", others: [{ action: "PREPARE_REMINDER", label: "Prepare reminder" }, { action: "VIEW_TERMS", label: "View terms" }] } } },
  });
  await page.goto("/receivables");
  await expect(page.getByTestId("recv3-status")).toHaveAttribute("data-tone", "bad");
  await expect(page.getByTestId("recv-state-RCV-A")).toHaveText("Promise missed");
  await expect(page.getByTestId("recv-filter-promises")).toBeEnabled();
  await page.getByTestId("recv-filter-promises").click();
  await expect(page.locator('[data-testid^="recv-state-"]')).toHaveCount(1);
  const order = await page.locator('[data-testid^="recv3-action-"]').evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
  expect(order).toEqual(["recv3-action-CHASE", "recv3-action-PREPARE_REMINDER", "recv3-action-VIEW_TERMS"]);
  await expect(page.getByTestId("recv3-actions-note")).toHaveCount(0);
});

test("phone: the primary is in the first screen, the cards stack, a tapped invoice brings its detail into view, nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/receivables");
  await expect(page.getByRole("heading", { level: 1 })).toBeInViewport();
  await expect(page.getByTestId("recv3-owe")).toBeInViewport();
  // The first action of the chosen invoice is the one filled primary, in a strip under the cards, inside the first screen.
  const primary = page.getByTestId("recv3-strip-action");
  await expect(primary).toBeInViewport();
  expect(await filled(page)).toEqual(["recv3-strip-action"]);
  expect((await primary.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect((await primary.boundingBox())!.y + (await primary.boundingBox())!.height).toBeLessThan(844);
  const boxes = await Promise.all(["recv3-owe", "recv3-next", "recv3-net"].map((id) => page.getByTestId(id).boundingBox()));
  expect(boxes[1]!.y).toBeGreaterThan(boxes[0]!.y);
  expect(boxes[2]!.y).toBeGreaterThan(boxes[1]!.y);
  await expect(page.getByTestId(`recv-${day0.rows[0].receivable_id}`)).toBeVisible();
  // The aside comes after the selected invoice.
  const detail = await page.getByTestId("recv3-detail").boundingBox();
  const aside = await page.getByTestId("recv3-stress").boundingBox();
  expect(aside!.y).toBeGreaterThan(detail!.y);
  expect(await overflow(page)).toBeLessThanOrEqual(1);
  for (const id of ["recv3-explore", "recv-filter-all"]) expect((await page.getByTestId(id).boundingBox())!.height).toBeGreaterThanOrEqual(44);
});

test("phone: tapping an invoice card brings its detail into view", async ({ page }) => {
  await advanceTo34(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/receivables");
  const current = day34.rows[1];
  await expect(page.getByTestId("recv3-detail")).not.toBeInViewport();
  await page.getByTestId(`recv-select-${current.receivable_id}`).click();
  await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", current.receivable_id);
  await expect(page.getByTestId("recv3-detail")).toBeInViewport();
  expect(await overflow(page)).toBeLessThanOrEqual(1);
});

test("reduced motion: the detail arrives without animation, and with motion allowed it does animate", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/receivables");
  const duration = () => page.getByTestId("recv3-detail").evaluate((el) => parseFloat(getComputedStyle(el.parentElement!).animationDuration));
  expect(await duration()).toBeLessThan(0.01);
  // The control: the same page without the media query has a real duration, so the assertion above measures the rule and not a missing class.
  await page.emulateMedia({ reducedMotion: "no-preference" });
  expect(await duration()).toBeGreaterThan(0.1);
});
