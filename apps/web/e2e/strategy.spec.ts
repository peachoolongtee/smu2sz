import type { APIRequestContext, Page } from "@playwright/test";
import { DEMO_TOKEN, expect, proseOf, test } from "./fixtures";
import { checkedDeal, filledBrand, openStoryFold, resetBooks, runPlan, openOperatorTools } from "./helpers";

/**
 * The strategy MVP surfaces (wayfinder map #47, Wave 5): the cash price sentence on Cash & funding, the collections worth on
 * Receivables (ranking note, "Worth collecting" and "Action" per invoice), the top action on the home and, on Deals, the "Before
 * they ask" card (the Safe Deal Envelope). Everything shown is the server's string; a Business page never says "day N".
 *
 * Gated: the surfaces exist only in a build with NEXT_PUBLIC_STRATEGY_MVP=1, so the spec runs only with E2E_STRATEGY=1, which
 * playwright.config.ts turns into that build flag and, for the live target, into FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1
 * on the API it starts. Run:
 *
 *   mock  E2E_STRATEGY=1 E2E_PORT=3112 E2E_TARGET=mock pnpm exec playwright test e2e/strategy.spec.ts
 *   live  E2E_STRATEGY=1 E2E_TARGET=live E2E_API_PORT=8016 E2E_LIVE_PORT=3016 pnpm exec playwright test e2e/strategy.spec.ts
 *         (the config starts the API itself with the flags; nothing may already hold E2E_API_PORT)
 *
 * The envelope card's testids: envelope-ceiling-terms / -early / -rebate (the three tiles), envelope-caption / -reason / -money, envelope-details (the fold), envelope-levers
 * (the table on desktop, envelope-levers-list on a phone), envelope-packages, envelope-zone, envelope-loading, envelope-error.
 *
 * Desktop (mock and live) checks the table; the phone project checks the list rows. Testids: the table cells are
 * recv-worth-<id> / recv-action-<id>; the phone list's are recv-list-worth-<id> / recv-list-action-<id> (both lists are in the
 * page, one hidden by the breakpoint, so the ids differ).
 */

test.skip(process.env.E2E_STRATEGY !== "1", "set E2E_STRATEGY=1 (the build flag NEXT_PUBLIC_STRATEGY_MVP=1 and the API's strategy flags)");

const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
const DAY_N = /\bday \d/i;

test.beforeEach(async ({ request }) => {
  await resetBooks(request);
});

/** The mock: the story page's clock moves the simulated day. */
async function advanceMockTo34(page: Page) {
  await page.goto("/demo");
  await openStoryFold(page, "story-today");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
}

/** The live API: the same calls scripts/demo_run.py and e2e/live.spec.ts make (the deal, the receipt on day 2, then the clock to day 34). */
async function advanceLiveTo34(request: APIRequestContext) {
  const owner = { "X-Owner-Token": DEMO_TOKEN };
  const bank = { "X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key" };
  const post = async (path: string, data: object, headers: Record<string, string> = owner) => {
    const res = await request.post(`${API}${path}`, { headers, data });
    expect(res.ok(), path).toBeTruthy();
    return res.json();
  };
  const { offer } = await post("/offers", { fixture_id: "EX01_PACKAGE" });
  await post(`/offers/${offer.offer_id}/evaluate`, { fixture_id: "EX01_PACKAGE" });
  expect((await post(`/negotiate/${offer.offer_id}`, { buyer_profile: "cooperative" })).outcome).toBe("DEAL");
  await post("/clock/advance", { to_day: 2 });
  const recon = await (await request.get(`${API}/reconciliation`, { headers: owner })).json();
  const promised = recon.reconciliation.promised[0];
  const mandate = await (await request.get(`${API}/mandate`, { headers: owner })).json();
  await post(
    "/operations",
    { kind: "RECEIVE_PAYMENT", op_id: "e2e-receipt-1", idempotency_key: "e2e-receipt-1", mandate_version: mandate.mandate.version, requested_by: "SYSTEM", receivable_id: promised.receivable_id, amount_fen: promised.expected_fen, bank_reference: "E2E-RCPT-1" },
    bank,
  );
  await post("/clock/advance", { to_day: 30 });
  await post("/clock/advance", { to_day: 34 });
}

async function advanceTo34(page: Page, request: APIRequestContext) {
  if (test.info().project.name === "live") await advanceLiveTo34(request);
  else await advanceMockTo34(page);
}

/** The package offer read and checked on Deals, and Cash impact opened: the envelope sits at the foot of it. */
async function openEnvelope(page: Page) {
  await checkedDeal(page);
  await page.getByTestId("deal-tab-cash").click();
  await expect(page.getByTestId("deal-envelope-packages")).toBeVisible({ timeout: 30_000 });
}

test.describe("desktop", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(testInfo.project.name === "phone", "the phone project checks the list rows below");
  });

  test("Cash & funding: the price sentence sits once in the risk card, in the server's words, with no chart or bands", async ({ page }) => {
    await page.goto("/cash");
    await expect(page.getByTestId("cash-headline")).toBeVisible();
    const sentence = page.getByTestId("cash-price-sentence");
    await expect(sentence).toHaveCount(1);
    await expect(sentence).toContainText("%");
    await expect(sentence).toContainText("saves you ¥89.11 of funding cost per ¥10,000");
    await expect(page.locator("#cash-answer").getByTestId("cash-price-sentence")).toHaveCount(1);
    // One line: the first clause. The rest of the server's sentence is one fold away, closed.
    expect((await sentence.boundingBox())?.height ?? 99).toBeLessThanOrEqual(24);
    const more = page.getByTestId("cash-price-more");
    await expect(more).not.toHaveAttribute("open", "");
    await more.locator("> summary").click();
    await expect(page.getByTestId("cash-price-rest")).toContainText("after that, earlier cash saves nothing");
    expect(await sentence.innerText()).not.toMatch(DAY_N);
    expect(await proseOf(page)).not.toMatch(DAY_N);
    expect(await filledBrand(page)).toBeLessThanOrEqual(1);
  });

  test("Receivables day 0: the ranking note, a worth cell and an action cell for the open invoice; nothing brand-filled", async ({ page }) => {
    await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-absent", "1")); // the ranking table is the page of before (the fallback)
    await page.goto("/receivables");
    await expect(page.getByTestId("recv-RCV-A")).toBeVisible();
    await expect(page.getByTestId("recv-ranking-note")).toContainText("Ranked by what collecting each saves you");
    await expect(page.getByTestId("recv-worth-RCV-A")).toContainText("Saves ¥");
    await expect(page.getByTestId("recv-RCV-A")).not.toContainText("before any discount");
    // The sentence for the step is one chevron down, with the reason and the record id.
    await page.getByTestId("recv-toggle-RCV-A").click();
    const action = page.getByTestId("recv-action-RCV-A");
    await expect(action).toContainText("early payment");
    // The cell is one figure; the server's full worth sentence (the limit, the better rate) is the first line of the details.
    await expect(page.getByTestId("recv-worth-RCV-A")).not.toContainText("limit");
    await expect(page.getByTestId("recv-action-RCV-A-worth")).toContainText("% limit");
    await expect(page.getByTestId("recv-RCV-A")).toContainText("Offer early payment");
    expect(await proseOf(page)).not.toMatch(DAY_N);
    expect(await filledBrand(page)).toBe(0);
  });

  test("Receivables: when the collections ranking cannot be read the page says so and Retry brings the ranking back", async ({ page }) => {
    await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-absent", "1")); // the ranking table is the page of before (the fallback)
    test.skip(test.info().project.name === "live", "the failure is the mock's test hook");
    await page.addInitScript(() => sessionStorage.setItem("tl-mock-worth-fail", "1"));
    await page.goto("/receivables");
    await expect(page.getByTestId("recv-RCV-A")).toBeVisible();
    const failed = page.getByTestId("recv-worth-failed");
    await expect(failed).toContainText("The collections ranking could not be read.");
    await expect(page.getByTestId("recv-ranking-note")).toHaveCount(0);
    await page.evaluate(() => sessionStorage.removeItem("tl-mock-worth-fail"));
    await failed.getByRole("button", { name: "Retry" }).click();
    await expect(failed).toHaveCount(0);
    await expect(page.getByTestId("recv-ranking-note")).toContainText("Ranked by what collecting each saves you");
  });

  test("Receivables day 34: the late invoice leads with Call now, and the existing columns and ids are intact", async ({ page, request }) => {
    await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-absent", "1")); // the ranking table is the page of before (the fallback)
    await advanceTo34(page, request);
    await page.goto("/receivables");
    const rows = page.locator("#recv-open tbody tr:not([data-group])");
    await expect(rows.first()).toHaveAttribute("data-testid", "recv-RCV-A");
    // Ids are level 2: not in the row, the server's rank is a numeral, and the sentence opens from the row's chevron.
    await expect(rows.first()).not.toContainText("RCV-A");
    await expect(rows.first().locator("td").first()).toHaveText("1");
    // The overdue invoice is pinned under its own heading; the rest sit under the ranking's, and the server's ranking note stays.
    await expect(page.getByTestId("recv-group-overdue")).toHaveText("Overdue first");
    await expect(page.getByTestId("recv-group-rest")).toHaveText("Ranked by what collecting saves you");
    await expect(page.getByTestId("recv-ranking-note")).toHaveCount(1);
    await expect(page.getByTestId("recv-worth-RCV-A")).toContainText("Saves ¥");
    await page.getByTestId("recv-toggle-RCV-A").click();
    await expect(page.getByTestId("recv-action-RCV-A")).toContainText("Call Foshan Home Retail Co.");
    await expect(page.getByTestId("recv-detail-RCV-A")).toContainText("RCV-A");
    // The action word is the first thing in the action cell, as a pill from the dictionary.
    await expect(rows.first().locator("td").last()).toContainText("Call now");
    await expect(rows.first().locator("td").last().getByText("Call now", { exact: true })).toHaveCount(1);
    expect(await proseOf(page)).not.toMatch(DAY_N);
    expect(await filledBrand(page)).toBe(0);
  });

  test("Deals day 0: Compare responses ends with what the owner could answer instead, by who may send it, the rest behind 'more'", async ({ page }) => {
    await openEnvelope(page);
    // The card of what the owner can live with, then the packages by who may send them.
    const card = page.locator("#deal-envelope");
    await expect(card.getByTestId("envelope-ceiling-terms")).toContainText("55 days");
    await expect(card.getByTestId("envelope-caption")).toContainText("Your limits, not an opening offer");
    const env = page.getByTestId("deal-envelope-packages");
    await expect(env).toContainText("What you could answer instead");
    // The classes in the verifier's own order: what FLOW may send, what the owner approves first. A class with nothing in it is not drawn.
    await expect(env.getByTestId("envelope-class-flow_may")).toContainText("FLOW may send these");
    await expect(env.getByTestId("envelope-class-flow_may").getByTestId("envelope-package")).toHaveCount(1);
    await expect(env.getByTestId("envelope-class-flow_may")).toContainText("early payment 0.85% on ¥257,200.00");
    const owner = env.getByTestId("envelope-class-needs_owner");
    await expect(owner).toContainText("You approve these first");
    // The first three of a class are listed; the rest are one fold away, said with their count.
    await expect(owner.getByTestId("envelope-package")).toHaveCount(3 + 7);
    await expect(owner.getByTestId("envelope-more-needs_owner").locator("> summary")).toHaveText("7 more");
    await expect(owner.getByTestId("envelope-more-needs_owner").getByTestId("envelope-package").first()).toBeHidden();
    await expect(env.getByTestId("envelope-class-over_limit")).toHaveCount(0);
    // The owner's words: no engine day number, no filled button added by the section.
    expect(await env.evaluate((el) => el.textContent ?? "")).not.toMatch(DAY_N);
    expect(await filledBrand(page)).toBeLessThanOrEqual(1);
  });

  test("Deals: the 'more' fold opens and closes from the keyboard", async ({ page }) => {
    await openEnvelope(page);
    const fold = page.getByTestId("envelope-more-needs_owner");
    await fold.locator("> summary").focus();
    await page.keyboard.press("Enter");
    await expect(fold.getByTestId("envelope-package").first()).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(fold.getByTestId("envelope-package").first()).toBeHidden();
  });

  test("Cash day 34: once the owner has approved the cure, the price sentence is the post-approval one (mock)", async ({ page }) => {
    test.skip(test.info().project.name === "live", "the approval is walked through the mock's pages");
    await advanceMockTo34(page);
    await page.goto("/cash");
    const sentence = page.getByTestId("cash-price-sentence");
    await expect(sentence).toBeVisible();
    const before = await sentence.innerText();
    await page.goto("/");
    await runPlan(page, "ALERT-RESERVE-42");
    await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
    await page.locator("#approval-APR-000001").getByRole("button", { name: /^Authorize/ }).click();
    await expect(page.getByTestId("approval-result-APR-000001")).toContainText("the cash lands");
    await page.goto("/cash");
    await expect(sentence).toBeVisible();
    expect(await sentence.innerText()).not.toBe(before);
    await expect(sentence).toContainText("saves you nothing");
    expect(await proseOf(page)).not.toMatch(DAY_N);
  });

});

test.describe("phone", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "desktop and live check the table above");
  });

  test("Receivables day 34: each list row carries the action pill, what it is worth and the sentence", async ({ page, request }) => {
    await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-absent", "1")); // the ranking table is the page of before (the fallback)
    await advanceTo34(page, request);
    await page.goto("/receivables");
    const list = page.getByTestId("recv-open-list");
    await expect(list).toBeVisible();
    await expect(page.getByTestId("recv-ranking-note")).toBeVisible();
    await expect(page.getByTestId("recv-list-worth-RCV-A")).toContainText("Saves ¥");
    await list.locator("li").first().locator("summary").first().click();
    await expect(page.getByTestId("recv-list-action-RCV-A-reason")).not.toBeEmpty();
    await expect(page.getByTestId("recv-list-action-RCV-A")).toContainText("Call Foshan Home Retail Co.");
    await expect(list.locator("li").first()).toContainText("Call now");
    // No horizontal overflow at phone width.
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    expect(await filledBrand(page)).toBe(0);
    // Chase payment on the late row: a 44 px control, and a dialog that fits the screen with Copy as its one filled button.
    const chase = page.getByTestId("chase-list-open-RCV-A");
    expect((await chase.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
    await chase.click();
    const dialog = page.getByTestId("chase-list-dialog-RCV-A");
    await expect(dialog.getByTestId("chase-request")).toBeVisible();
    const box = await dialog.boundingBox();
    expect(box && box.x >= 0 && box.x + box.width <= (page.viewportSize()?.width ?? 0)).toBe(true);
    await expect(dialog.getByTestId("chase-copy")).toBeVisible();
  });

  test("Deals day 0: the envelope on a phone lists the packages, keeps the fold in reach and does not overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openEnvelope(page);
    const env = page.getByTestId("deal-envelope-packages");
    await expect(env.getByTestId("envelope-package").first()).toBeVisible();
    await expect(env.getByTestId("envelope-more-needs_owner")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    expect(await filledBrand(page)).toBeLessThanOrEqual(1);
  });
});
