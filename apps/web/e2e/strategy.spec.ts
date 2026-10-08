import type { APIRequestContext, Page } from "@playwright/test";
import { DEMO_TOKEN, expect, proseOf, test } from "./fixtures";
import { filledBrand, resetBooks } from "./helpers";

/**
 * The strategy MVP surfaces (wayfinder map #47, Wave 5A): the cash price sentence on Cash & funding, the collections worth on
 * Receivables (ranking note, "Worth collecting" and "Action" per invoice) and the top action on the home. Everything shown is
 * the server's string; a Business page never says "day N".
 *
 * Gated: the surfaces exist only in a build with NEXT_PUBLIC_STRATEGY_MVP=1, so the spec runs only with E2E_STRATEGY=1, which
 * playwright.config.ts turns into that build flag and, for the live target, into FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1
 * on the API it starts. Run:
 *
 *   mock  E2E_STRATEGY=1 E2E_PORT=3112 E2E_TARGET=mock pnpm exec playwright test e2e/strategy.spec.ts
 *   live  E2E_STRATEGY=1 E2E_TARGET=live E2E_API_PORT=8016 E2E_LIVE_PORT=3016 pnpm exec playwright test e2e/strategy.spec.ts
 *         (the config starts the API itself with the flags; nothing may already hold E2E_API_PORT)
 *
 * Desktop (mock and live) checks the table; the phone project checks the list rows. Testids: the table cells are
 * recv-worth-<id> / recv-action-<id>; the phone list's are recv-list-worth-<id> / recv-list-action-<id> (both lists are in the
 * page, one hidden by the breakpoint, so the ids differ).
 */

test.skip(!process.env.E2E_STRATEGY, "set E2E_STRATEGY=1 (the build flag NEXT_PUBLIC_STRATEGY_MVP=1 and the API's strategy flags)");

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
    await expect(page.locator("#cash-answer").getByTestId("cash-price-sentence")).toHaveCount(1);
    expect(await sentence.innerText()).not.toMatch(DAY_N);
    expect(await proseOf(page)).not.toMatch(DAY_N);
    expect(await filledBrand(page)).toBeLessThanOrEqual(1);
  });

  test("Receivables day 0: the ranking note, a worth cell and an action cell for the open invoice; nothing brand-filled", async ({ page }) => {
    await page.goto("/receivables");
    await expect(page.getByTestId("recv-RCV-A")).toBeVisible();
    await expect(page.getByTestId("recv-ranking-note")).toContainText("Ranked by what collecting each saves you");
    await expect(page.getByTestId("recv-worth-RCV-A")).toContainText("¥");
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
    await expect(page.getByTestId("recv-worth-RCV-A")).toContainText("¥");
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
    await expect(page.getByTestId("recv-list-worth-RCV-A")).toContainText("¥");
    await expect(page.getByTestId("recv-list-action-RCV-A")).toContainText("Call Foshan Home Retail Co.");
    await expect(list.locator("li").first()).toContainText("Call now");
    // No horizontal overflow at phone width.
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    expect(await filledBrand(page)).toBe(0);
  });
});
