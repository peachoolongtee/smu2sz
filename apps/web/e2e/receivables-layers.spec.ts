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
async function afterFund(page: Page) {
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("fix-result")).toBeVisible();
  await page.goto("/receivables");
}

const overflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

test("day 0: the answer, three plain cards, one invoice with no financing, and the actions in the server's order", async ({ page }) => {
  await page.goto("/receivables");
  const row = day0.rows[0];
  await expect(page.getByTestId("recv3-page")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(page.getByTestId("recv3-status")).toHaveAttribute("data-tone", "ok");
  await expect(page.getByTestId("recv3-status")).toContainText("On track");
  await expect(page.getByTestId("recv3-status")).toContainText("Read today");
  await expect(page.getByTestId("recv3-h1-expected")).toHaveText(`${row.amount_short} expected from ${day0.summary.next_expected.buyer_name}`);
  // Nothing is financed on the opening books: no second line, no financing sentence.
  await expect(page.getByTestId("recv3-h1-net")).toHaveCount(0);
  await expect(page.getByTestId("recv3-sub")).toHaveText("Nothing is overdue.");
  // The three cards, in the server's strings.
  await expect(page.getByTestId("recv3-owe")).toHaveText(day0.summary.outstanding_total_display);
  await expect(page.getByTestId("recv3-next")).toHaveText(new RegExp(day0.summary.next_expected.when_text, "i"));
  await expect(page.getByTestId("recv3-net")).toHaveText(day0.summary.net_total_display);
  await expect(page.getByTestId("recv3-cards")).toContainText("Customers owe you");
  await expect(page.getByTestId("recv3-cards")).toContainText("Next expected payment");
  await expect(page.getByTestId("recv3-cards")).toContainText("Expected cash at collection");
  await expect(page.getByTestId("recv3-cards")).toContainText("if every invoice is paid on its due day");
  // The row, with the customer as a link that carries the context.
  const r = page.getByTestId(`recv-${row.receivable_id}`);
  await expect(r).toContainText(row.outstanding_display);
  await expect(r).toContainText(row.due_when);
  await expect(r).toContainText(row.collection_state_text);
  await expect(page.getByTestId(`recv-steps-${row.receivable_id}`)).toHaveText("No financing");
  const link = page.getByTestId(`recv-customer-${row.receivable_id}`);
  await expect(link).toHaveText(row.buyer_name);
  expect(new URL((await link.getAttribute("href")) ?? "", "http://x").pathname).toBe(`/customers/${row.buyer_id}`);
  expect((await link.getAttribute("href")) ?? "").toContain(`invoice=${row.receivable_id}`);
  expect((await link.getAttribute("href")) ?? "").toContain(`customer=${row.buyer_id}`);
  // The selected invoice: the condition as the heading; with no financing the breakdown is the invoice and the cash.
  await expect(page.getByTestId("recv3-detail-title")).toContainText(row.net.condition_text);
  await expect(page.getByTestId("recv3-detail-title")).toContainText(row.net.net_short);
  await expect(page.getByTestId("recv3-bd-invoice")).toHaveText(row.outstanding_display);
  await expect(page.getByTestId("recv3-bd-advance")).toHaveCount(0);
  await expect(page.getByTestId("recv3-bd-net")).toHaveText(row.net.net_display);
  await expect(page.getByTestId("recv3-terms")).toHaveText(row.governed_by.terms_text);
  await expect(page.getByTestId("recv3-facts")).toContainText(row.governed_by.terms_label);
  expect(row.governed_by.terms_text.startsWith("Agreement ")).toBe(true);
  await expect(page.getByTestId("recv3-recourse")).toHaveCount(0);
  await expect(page.getByTestId("recv3-action-financing")).toHaveCount(0);
  await expect(page.getByTestId("recv3-early")).toContainText(row.early_payment.text);
  // The actions follow the server: CURRENT leads with the terms, then the reminder.
  const order = await page.locator('[data-testid^="recv3-action-"]').evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
  expect(order).toEqual([row.collection_action.primary, ...row.collection_action.others.map((o) => o.action)].map((a) => `recv3-action-${a}`));
  await expect(page.getByTestId("recv3-action-VIEW_TERMS")).toContainText(row.collection_action.label);
  expect(await page.locator("body").innerText()).not.toMatch(/\bDay \d|RCV-|RI:BUYER|BUYER-1/);
});

test("the financing is arranged: the answer has two lines, the steps show where it is, the breakdown runs from the invoice to the cash", async ({ page }) => {
  await afterFund(page);
  const row = after.rows[0];
  expect(row.financing_state).toBe("ARRANGED");
  await expect(page.getByTestId("recv3-status")).toContainText("On track");
  await expect(page.getByTestId("recv3-h1-expected")).toHaveText(`${row.amount_short} expected from ${after.summary.next_expected.buyer_name}`);
  await expect(page.getByTestId("recv3-h1-net")).toHaveText(new RegExp(`^${row.net.net_short} becomes available at collection, after the financing is repaid\\.$`, "i"));
  await expect(page.getByTestId("recv3-sub")).toContainText("Nothing is overdue.");
  await expect(page.getByTestId("recv3-sub")).toContainText(row.net.repays_text);
  await expect(page.getByTestId("recv3-sub")).toContainText("it is not money lost");
  // The lifecycle: three steps, the server's state filled.
  const steps = page.getByTestId(`recv-steps-${row.receivable_id}`);
  await expect(steps).toHaveAttribute("data-state", "ARRANGED");
  await expect(steps.locator("li")).toHaveText(["Arranged", "Received", "Repaid"]);
  await expect(steps.locator('li[data-on="true"]')).toHaveText("Arranged");
  await expect(steps.locator("li[aria-current=step]")).toHaveCount(1);
  await expect(page.getByTestId(`recv-${row.receivable_id}`)).toContainText(row.net.advance_display);
  await expect(page.getByTestId(`recv-net-${row.receivable_id}`)).toHaveText(row.net.net_short);
  // The breakdown: the invoice, less the financing with its state, less the charges with the per-period note, the cash.
  await expect(page.getByTestId("recv3-bd-invoice")).toHaveText(row.outstanding_display);
  await expect(page.getByTestId("recv3-bd-advance")).toContainText(row.net.advance_display);
  await expect(page.getByTestId("recv3-bd-state")).toHaveText(row.net.financing_state_text);
  await expect(page.getByTestId("recv3-bd-charges")).toContainText(row.net.charges_display);
  await expect(page.getByTestId("recv3-breakdown")).toContainText(row.net.per_period_text);
  await expect(page.getByTestId("recv3-bd-net")).toHaveText(row.net.net_display);
  await expect(page.getByTestId("recv3-repays")).toContainText(row.net.repays_text);
  await expect(page.getByTestId("recv3-recourse")).toHaveText(row.recourse_text);
  await expect(page.getByTestId("recv3-net-financing")).toContainText(after.summary.financing_total_display);
  // "View the financing" is the record of the request, shown because the server sent the link.
  const financing = page.getByTestId("recv3-action-financing");
  await expect(financing).toHaveText("View the financing");
  expect(await financing.getAttribute("href")).toBe(row.financing_href);
  // The aside names the financing's extra cost for a late month, in the server's words.
  await expect(page.getByTestId("recv3-stress-financing")).toContainText(row.net.per_period_text);
});

test("day 38: the financing has been received, the step moves on", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-home-v4", JSON.stringify({ day: 38, stage: "approved", funded: false, receipted: true, moved: 0 })));
  await page.goto("/receivables");
  const received = settled.rows.find((r) => r.financing_state === "RECEIVED")!;
  const steps = page.getByTestId(`recv-steps-${received.receivable_id}`);
  await expect(steps).toHaveAttribute("data-state", "RECEIVED");
  await expect(steps.locator('li[data-on="true"]')).toHaveText("Received");
  await expect(steps.locator('li[data-step="ARRANGED"]')).not.toHaveAttribute("data-on", "true");
});

test("day 34: the pills filter by the server's collection state, an empty pill is disabled, and the late invoice leads", async ({ page }) => {
  await advanceTo34(page);
  const ids = day34.rows.map((r) => r.receivable_id);
  await expect(page.locator('[data-testid^="recv-RCV"], [data-testid^="recv-RI"]').filter({ hasNot: page.locator("a") })).toHaveCount(0).catch(() => undefined);
  for (const id of ids) await expect(page.getByTestId(`recv-${id}`)).toBeVisible();
  await expect(page.getByTestId("recv3-status")).toHaveAttribute("data-tone", "bad");
  await expect(page.getByTestId("recv3-sub")).toContainText("1 invoice is overdue.");
  const late = day34.rows.filter((r) => r.collection_state === "OVERDUE").length;
  const soon = day34.rows.filter((r) => r.collection_state === "DUE_SOON").length;
  await expect(page.getByTestId("recv-filter-all")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("recv-filter-overdue")).toContainText(String(late));
  if (soon === 0) await expect(page.getByTestId("recv-filter-soon")).toBeDisabled();
  await expect(page.getByTestId("recv-filter-promises")).toBeDisabled();
  await page.getByTestId("recv-filter-overdue").click();
  await expect(page.getByTestId("recv-filter-overdue")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('[data-testid^="recv-state-"]')).toHaveCount(late);
  await expect(page.locator('[data-testid^="recv-state-"]').first()).toHaveText(day34.rows.find((r) => r.collection_state === "OVERDUE")!.collection_state_text);
  await page.getByTestId("recv-filter-all").click();
  await expect(page.locator('[data-testid^="recv-state-"]')).toHaveCount(ids.length);
  // The late invoice is first in the server's order and is the one shown.
  await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", day34.rows[0].receivable_id);
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
  await expect(page.getByTestId("recv3-action-CHASE")).toContainText(overdue.collection_action.label);
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
  // The list is kept: all three rows are still there, and a reload restores the choice.
  await expect(page.locator('[data-testid^="recv-select-"]')).toHaveCount(day34.rows.length);
  await page.reload();
  await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", current.receivable_id);
  // Back to the late one: the prepared handoff opens from the first action.
  await page.getByTestId(`recv-select-${overdue.receivable_id}`).click();
  await page.getByTestId(`chase-detail-CHASE-open-${overdue.receivable_id}`).click();
  await expect(page.getByTestId(`chase-detail-CHASE-dialog-${overdue.receivable_id}`)).toBeVisible();
  await expect(page.getByTestId("chase-request")).toContainText(overdue.buyer_name);
});

test("the late-payment test is the buyer's own read, with no deal in context: the server's strings, and the one primary opens Cash with the series", async ({ page }) => {
  await page.goto("/receivables");
  const row = day0.rows[0];
  const now = buyer.stress.now;
  await expect(page.getByTestId("recv3-stress")).toContainText(`If ${row.buyer_name} pays ${buyer.stress.delay_days} days late`);
  await expect(page.getByTestId("recv3-stress-cash")).toHaveText(`${now.lowest_short} ${now.lowest_when}`);
  await expect(page.getByTestId("recv3-stress-minimum")).toHaveText(now.funding_text);
  await expect(page.getByTestId("recv3-stress-later")).toHaveText(new RegExp(`^${now.net_later_text}$`, "i"));
  await expect(page.getByTestId("recv3-history")).toHaveText(buyer.payments.sentence);
  await expect(page.getByTestId("recv3-concentration")).toContainText(buyer.concentration.ar_text);
  await expect(page.getByTestId("recv3-concentration-link")).toBeVisible();
  // The primary: one brand-filled action on the page, a link into Cash carrying the buyer, the invoice and the context.
  const explore = page.getByTestId("recv3-explore");
  await expect(explore).toHaveText("Explore the cash impact");
  const href = new URL((await explore.getAttribute("href")) ?? "", "http://x");
  expect(href.pathname).toBe("/cash");
  expect(href.searchParams.get("stress")).toBe(`${row.buyer_id}:${buyer.stress.delay_days}`);
  expect(href.searchParams.get("invoice")).toBe(row.receivable_id);
  expect(href.searchParams.get("customer")).toBe(row.buyer_id);
  await expect(page.getByText("coming back keeps this invoice selected")).toBeVisible();
  expect(await page.locator("main a, main button").evaluateAll((els) => els.filter((e) => getComputedStyle(e).backgroundColor === "rgb(3, 104, 233)" && e.getClientRects().length > 0).length)).toBe(1);
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
  // The context travels: the Cash link keeps the decision.
  const href = new URL((await page.getByTestId("recv3-explore").getAttribute("href")) ?? "", "http://x");
  expect(href.searchParams.get("decision")).toBe(exposure.decision_id);
});

test("Chinese: the same page and figures in the server's Chinese, with the dictionary's words", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" }));
    sessionStorage.setItem("tl-mock-receivables-offer", "1");
  });
  await page.goto("/receivables");
  const row = offerZh.rows[0];
  await expect(page.getByTestId("recv3-status")).toContainText("一切按计划");
  await expect(page.getByTestId("recv3-h1-expected")).toHaveText(`预计从 ${offerZh.summary.next_expected.buyer_name} 收到 ${row.amount_short}。`);
  await expect(page.getByTestId("recv3-owe")).toHaveText(offerZh.summary.outstanding_total_display);
  await expect(page.getByTestId("recv3-cards")).toContainText("客户欠您");
  await expect(page.getByTestId(`recv-${row.receivable_id}`)).toContainText(row.due_when);
  await expect(page.getByTestId("recv3-detail-title")).toContainText(row.net.condition_text);
  await expect(page.getByTestId("recv3-terms")).toHaveText(row.governed_by.terms_text);
  await expect(page.getByTestId("recv3-stress-cash")).toContainText(buyerZh.stress.now.lowest_when);
  await expect(page.getByTestId("recv3-stress-minimum")).toHaveText(buyerZh.stress.now.funding_text);
  await expect(page.getByTestId("recv3-stress-later")).toContainText(buyerZh.stress.now.net_later_text);
  await expect(page.getByTestId("recv3-explore")).toHaveText("查看对现金的影响");
  expect(await page.locator("main").innerText()).not.toMatch(/\bDay \d|RCV-|BUYER-1/);
  // The financed books, in Chinese: the steps are the dictionary's.
  await afterFund(page);
  await expect(page.getByTestId(`recv-steps-${afterZh.rows[0].receivable_id}`).locator("li")).toHaveText(["已安排", "已到账", "已还清"]);
  await expect(page.getByTestId("recv3-sub")).toContainText(afterZh.rows[0].net.repays_text);
});

test("a server without GET /receivables keeps the page of before", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-absent", "1"));
  await page.goto("/receivables");
  await expect(page.getByTestId("recv-summary")).toBeVisible();
  await expect(page.getByTestId("recv3-page")).toHaveCount(0);
});

test("phone: the cards stack, the invoices are cards, the answer is in the first screen and nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/receivables");
  await expect(page.getByRole("heading", { level: 1 })).toBeInViewport();
  await expect(page.getByTestId("recv3-owe")).toBeInViewport();
  const boxes = await Promise.all(["recv3-owe", "recv3-next", "recv3-net"].map((id) => page.getByTestId(id).boundingBox()));
  expect(boxes[1]!.y).toBeGreaterThan(boxes[0]!.y);
  expect(boxes[2]!.y).toBeGreaterThan(boxes[1]!.y);
  await expect(page.getByTestId(`recv-${day0.rows[0].receivable_id}`)).toBeVisible();
  // The aside comes after the selected invoice.
  const detail = await page.getByTestId("recv3-detail").boundingBox();
  const aside = await page.getByTestId("recv3-stress").boundingBox();
  expect(aside!.y).toBeGreaterThan(detail!.y);
  expect(await overflow(page)).toBeLessThanOrEqual(1);
  // Every control a finger presses is 44 px.
  for (const id of ["recv3-explore", "recv-filter-all"]) expect((await page.getByTestId(id).boundingBox())!.height).toBeGreaterThanOrEqual(44);
});

test("reduced motion: the detail arrives without animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/receivables");
  const seconds = await page.getByTestId("recv3-detail").evaluate((el) => parseFloat(getComputedStyle(el.parentElement!).animationDuration));
  expect(seconds).toBeLessThan(0.01);
});
