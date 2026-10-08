import type { APIRequestContext, Page } from "@playwright/test";
import { DEMO_TOKEN, expect, proseOf, test } from "./fixtures";
import { filledBrand, resetBooks, runPlan } from "./helpers";

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
 * The envelope card's testids: envelope-primary / -reason / -money, envelope-open-a / -b, envelope-details (the fold), envelope-levers
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

/** Read the EX01 message the way the owner does: open it in the inbox (the Deals thread shows the ask and the card under it). */
async function openEx01(page: Page) {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("deal-ask-IMMEDIATE_DISCOUNT")).toBeVisible();
}

/** The ids of the Deals sections that matter, in page order. */
async function sectionOrder(page: Page): Promise<string[]> {
  return page.evaluate(() => [...document.querySelectorAll("#deal-ask, #deal-envelope, #deal-recommendation-card")].map((el) => el.id));
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
    expect(await sentence.innerText()).not.toMatch(DAY_N);
    expect(await proseOf(page)).not.toMatch(DAY_N);
    expect(await filledBrand(page)).toBeLessThanOrEqual(1);
  });

  test("Receivables day 0: the ranking note, a worth cell and an action cell for the open invoice; nothing brand-filled", async ({ page }) => {
    await page.goto("/receivables");
    await expect(page.getByTestId("recv-RCV-A")).toBeVisible();
    await expect(page.getByTestId("recv-ranking-note")).toContainText("Ranked by what collecting each saves you");
    await expect(page.getByTestId("recv-worth-RCV-A")).toContainText("Saves ¥");
    await expect(page.getByTestId("recv-RCV-A")).not.toContainText("before any discount");
    const action = page.getByTestId("recv-action-RCV-A");
    await expect(action).toContainText("early payment");
    await expect(page.getByTestId("recv-RCV-A")).toContainText("Offer early payment");
    expect(await proseOf(page)).not.toMatch(DAY_N);
    expect(await filledBrand(page)).toBe(0);
  });

  test("Receivables day 34: the late invoice leads with Call now, and the existing columns and ids are intact", async ({ page, request }) => {
    await advanceTo34(page, request);
    await page.goto("/receivables");
    const rows = page.locator("#recv-open tbody tr");
    await expect(rows.first()).toHaveAttribute("data-testid", "recv-RCV-A");
    await expect(rows.first().locator("td").first().locator("span.block")).toHaveText("RCV-A");
    await expect(page.getByTestId("recv-ranking-note")).toHaveCount(1);
    await expect(page.getByTestId("recv-worth-RCV-A")).toContainText("Saves ¥");
    await expect(page.getByTestId("recv-action-RCV-A")).toContainText("Call Foshan Home Retail Co.");
    // The action word is the first thing in the action cell, as a pill from the dictionary.
    await expect(rows.first().locator("td").last()).toContainText("Call now");
    await expect(rows.first().locator("td").last().getByText("Call now", { exact: true })).toHaveCount(1);
    expect(await proseOf(page)).not.toMatch(DAY_N);
    expect(await filledBrand(page)).toBe(0);
  });

  test("Home day 34: one line says what to do about the invoice that saves the most", async ({ page, request }) => {
    await advanceTo34(page, request);
    await page.goto("/");
    await expect(page.getByTestId("home-late-RCV-A")).toBeVisible();
    const line = page.getByTestId("home-top-action");
    await expect(line).toHaveCount(1);
    await expect(line).toContainText("Call Foshan Home Retail Co.");
    await expect(page.locator("#home-receivables").getByTestId("home-top-action")).toHaveCount(1);
    expect(await proseOf(page)).not.toMatch(DAY_N);
    expect(await filledBrand(page)).toBeLessThanOrEqual(1);
  });
  test("Deals day 0: the Before they ask card answers in the server's words, opens its details and Option B, and adds no filled button", async ({ page }) => {
    await openEx01(page);
    const card = page.locator("#deal-envelope");
    // The card is there as soon as the message is read, before the check; it has no options to open yet.
    await expect(card.getByTestId("envelope-primary")).toContainText("You can live with", { timeout: 30_000 });
    await expect(card.getByTestId("envelope-primary")).toContainText("55-day");
    await expect(card.getByTestId("envelope-primary")).toContainText("0.85%");
    await expect(card.getByTestId("envelope-reason")).not.toBeEmpty();
    await expect(card.getByTestId("envelope-money")).toContainText("¥");
    await expect(card).toContainText("The most you can give");
    await expect(card.getByTestId("envelope-caption")).toContainText("Your limits, not an opening offer");
    await expect(card).toContainText("Estimate");
    await expect(card).not.toContainText("Hypothetical");
    await expect(card.getByTestId("envelope-open-a")).toHaveCount(0);
    expect(await sectionOrder(page)).toEqual(["deal-ask", "deal-envelope"]);

    await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
    await expect(page.getByTestId("deal-recommendation")).toBeVisible();
    // The card sits right after the ask card and before the decision.
    expect(await sectionOrder(page)).toEqual(["deal-ask", "deal-envelope", "deal-recommendation-card"]);

    // Details: the levers (six), the approved packages and, where the server gave it, the terms-and-price zone.
    await expect(card.getByTestId("envelope-levers")).toBeHidden();
    await card.getByTestId("envelope-details").locator("summary").first().click();
    await expect(card.getByTestId("envelope-levers").locator("tbody tr")).toHaveCount(6);
    await expect(card.getByTestId("envelope-lever-terms_alone")).toContainText("45 days");
    await expect(card.getByTestId("envelope-lever-terms_alone")).toContainText("your budget for what you give buyers");
    await expect(card.getByTestId("envelope-lever-terms_alone")).toContainText("50 days: over your limits; its funding cannot run today");
    await expect(card.getByTestId("envelope-lever-terms_with_price")).toContainText("55 days, price up 0.30%");
    await expect(card.getByTestId("envelope-lever-terms_with_price")).toContainText("your cash floor");
    await expect(card.getByTestId("envelope-lever-early_pay_whole")).toContainText("0.70% on ¥420,000.00");
    await expect(card.getByTestId("envelope-lever-early_pay_counter")).toContainText("0.85% on ¥257,200.00");
    await expect(card.getByTestId("envelope-lever-early_pay_counter")).toContainText("0.90% on ¥257,200.00: over your limits");
    await expect(card.getByTestId("envelope-lever-rebate")).toContainText("1.25%");
    const packages = card.getByTestId("envelope-packages").getByTestId("envelope-package");
    expect(await packages.count()).toBeGreaterThan(3);
    await expect(packages.first()).toContainText(" · ");
    await expect(card.getByTestId("envelope-packages")).toContainText("55-day terms · price up 0.25% · rebate 0.60%");
    await expect(card.getByRole("heading", { name: "Within your limits" })).toBeVisible();
    await expect(card.getByTestId("envelope-packages")).toContainText("needs your approval");
    // The terms-and-price zone: the server's rows, in the mock and live alike.
    const zone = card.getByTestId("envelope-zone");
    await zone.locator("summary").first().click();
    await expect(zone.locator("summary").first()).toContainText("Terms and price table");
    await expect(zone.getByTestId("envelope-zone-row")).toHaveCount(13);
    await expect(zone.getByTestId("envelope-zone-row").first()).toContainText("no price rise needed");
    await expect(zone.getByTestId("envelope-zone-row").nth(3)).toContainText("no price rise needed");
    await expect(zone).toContainText("0.25%");
    await expect(zone).toContainText("none works");
    // Where no terms work the counter-price column shows a dash, not the rule price; the column is named for what it holds.
    await expect(zone).toContainText("Price that covers the cost");
    await expect(zone.getByTestId("envelope-zone-row").last().locator("td").nth(1)).toHaveText("—");
    await expect(zone).not.toContainText("0.00%");

    // Prose rules: the owner's words, no engine day numbers, no brand fill added.
    expect(await card.evaluate((el) => el.textContent ?? "")).not.toMatch(DAY_N);
    expect(await filledBrand(page)).toBeLessThanOrEqual(1);
    await expect(card.getByTestId("envelope-computed")).toHaveCount(0);

    // Option A: scroll to the response card. Option B: reveal it, then scroll to it. The card sends nothing.
    await expect(card.getByTestId("envelope-open-a")).toBeVisible();
    await expect(page.getByTestId("deal-option-Option-B")).toHaveCount(0);
    await card.getByTestId("envelope-open-a").click();
    await expect(page.getByTestId("deal-option-Option-A")).toBeInViewport();
    await expect(page.getByTestId("deal-option-Option-A")).toBeFocused();
    await expect(page.getByTestId("deal-option-Option-B")).toHaveCount(0);
    await card.scrollIntoViewIfNeeded();
    await card.getByTestId("envelope-open-b").click();
    await expect(page.getByTestId("deal-option-Option-B")).toBeVisible();
    await expect(page.getByTestId("deal-option-Option-B")).toBeInViewport();
    await expect(page.getByTestId("deal-compare")).toContainText("Hide");
    await expect(page.getByTestId("deal-negotiation")).toHaveCount(0);
    expect(await filledBrand(page)).toBe(1);
    await expect(page.getByTestId("deal-send")).toHaveClass(/bg-brand-600/);
    // The response card still toggles Option B by itself.
    await page.getByTestId("deal-compare").click();
    await expect(page.getByTestId("deal-option-Option-B")).toHaveCount(0);
  });

  test("Deals: the details open and close from the keyboard", async ({ page }) => {
    await openEx01(page);
    const card = page.locator("#deal-envelope");
    await expect(card.getByTestId("envelope-primary")).toBeVisible({ timeout: 30_000 });
    await card.getByTestId("envelope-details").locator("summary").first().focus();
    await page.keyboard.press("Enter");
    await expect(card.getByTestId("envelope-levers")).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(card.getByTestId("envelope-levers")).toBeHidden();
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
    await page.locator("#approval-APR-000001").getByRole("button", { name: "Approve" }).click();
    await expect(page.getByTestId("approval-result-APR-000001")).toContainText("the cash lands");
    await page.goto("/cash");
    await expect(sentence).toBeVisible();
    expect(await sentence.innerText()).not.toBe(before);
    await expect(sentence).toContainText("saves you nothing");
    expect(await proseOf(page)).not.toMatch(DAY_N);
  });

  test("Deals (live): while the server works the card says so and holds its place; a failure reads in one line with a retry", async ({ page }) => {
    test.skip(test.info().project.name !== "live", "the mock answers at once; the live API's first sweep takes seconds");
    await page.route("**/envelope?**", async (route) => {
      await new Promise((r) => setTimeout(r, 2500));
      await route.continue();
    });
    await openEx01(page);
    const loading = page.locator("#deal-envelope").getByTestId("envelope-loading");
    await expect(loading).toBeVisible();
    await expect(loading).toContainText("Working out what you can live with");
    await expect(page.locator("#deal-envelope").getByTestId("envelope-primary")).toBeVisible({ timeout: 30_000 });

    await page.unroute("**/envelope?**");
    await page.route("**/envelope?**", (route) => route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) }));
    await page.reload();
    const failed = page.locator("#deal-envelope").getByTestId("envelope-error");
    await expect(failed).toBeVisible({ timeout: 30_000 });
    await expect(failed).toContainText("could not work out");
    await page.unroute("**/envelope?**");
    await failed.getByRole("button", { name: "Retry" }).click();
    await expect(page.locator("#deal-envelope").getByTestId("envelope-primary")).toBeVisible({ timeout: 30_000 });
  });

});

test.describe("phone", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "desktop and live check the table above");
  });

  test("Receivables day 34: each list row carries the action pill, what it is worth and the sentence", async ({ page, request }) => {
    await advanceTo34(page, request);
    await page.goto("/receivables");
    const list = page.getByTestId("recv-open-list");
    await expect(list).toBeVisible();
    await expect(page.getByTestId("recv-ranking-note")).toBeVisible();
    await expect(page.getByTestId("recv-list-worth-RCV-A")).toContainText("Saves ¥");
    await expect(page.getByTestId("recv-list-action-RCV-A-reason")).not.toBeEmpty();
    await expect(page.getByTestId("recv-list-action-RCV-A")).toContainText("Call Foshan Home Retail Co.");
    await expect(list.locator("li").first()).toContainText("Call now");
    // No horizontal overflow at phone width.
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    expect(await filledBrand(page)).toBe(0);
  });

  test("Deals day 0: the Before they ask card on a phone lists the levers, keeps its buttons in reach and does not overflow", async ({ page }) => {
    await openEx01(page);
    const card = page.locator("#deal-envelope");
    await expect(card.getByTestId("envelope-primary")).toContainText("55-day", { timeout: 30_000 });
    await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
    await expect(card.getByTestId("envelope-open-b")).toBeVisible();
    await card.getByTestId("envelope-details").locator("summary").first().click();
    await expect(card.getByTestId("envelope-levers-list").locator("li")).toHaveCount(6);
    await expect(card.getByTestId("envelope-levers").locator("table")).toBeHidden();
    await expect(card.getByTestId("envelope-packages")).toBeVisible();
    await card.getByTestId("envelope-open-b").click();
    await expect(page.getByTestId("deal-option-Option-B")).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    expect(await filledBrand(page)).toBeLessThanOrEqual(1);
  });
});
