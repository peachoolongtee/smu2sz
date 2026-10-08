import type { APIRequestContext, Page } from "@playwright/test";
import { DEMO_TOKEN, expect, test } from "./fixtures";
import { resetBooks, runPlan } from "./helpers";

/**
 * Language parity on the Business pages (wayfinder #65 Wave 7, F28): in Chinese the approvals queue and the decision record say their sentences in
 * Chinese with the same amounts as in English. Mock mode replays the recorded `?lang=zh` answers; live mode asks the real API, so a route that did not
 * carry `lang` would answer in English here. Every request the page makes to a route that takes a language carries the language on screen.
 */

const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;

async function setLang(page: Page, lang: "en" | "zh") {
  await page.addInitScript((l) => localStorage.setItem("tl-lang", JSON.stringify({ lang: l })), lang);
}

/** Day 34 on the books that carry the approval: mock moves the story's clock, live replays the same calls the Demo makes. */
async function toDay34(page: Page, request: APIRequestContext) {
  if (test.info().project.name !== "live") {
    await page.goto("/demo");
    await page.getByTestId("home-days").fill("34");
    await page.getByTestId("home-advance").click();
    await expect(page.getByTestId("home-day")).toContainText("34");
    return;
  }
  const owner = { "X-Owner-Token": DEMO_TOKEN };
  const bank = { "X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key" };
  const post = async (path: string, data: object, headers: Record<string, string> = owner) => {
    const res = await request.post(`${API}${path}`, { headers, data });
    expect(res.ok(), path).toBeTruthy();
    return res.json();
  };
  const { offer } = await post("/offers", { fixture_id: "EX01_PACKAGE" });
  await post(`/offers/${offer.offer_id}/evaluate`, { fixture_id: "EX01_PACKAGE" });
  await post(`/negotiate/${offer.offer_id}`, { buyer_profile: "cooperative" });
  await post("/clock/advance", { to_day: 2 });
  const recon = await (await request.get(`${API}/reconciliation`, { headers: owner })).json();
  const promised = recon.reconciliation.promised[0];
  const mandate = await (await request.get(`${API}/mandate`, { headers: owner })).json();
  await post("/operations", { kind: "RECEIVE_PAYMENT", op_id: "e2e-lang-receipt", idempotency_key: "e2e-lang-receipt", mandate_version: mandate.mandate.version, requested_by: "SYSTEM", receivable_id: promised.receivable_id, amount_fen: promised.expected_fen, bank_reference: "E2E-LANG-1" }, bank);
  await post("/clock/advance", { to_day: 30 });
  await post("/clock/advance", { to_day: 34 });
}

test.beforeEach(async ({ request }) => {
  await resetBooks(request);
});

test("in Chinese the approvals queue and the decision record read in Chinese with the same amounts as in English", async ({ page, request }) => {
  await setLang(page, "zh");
  // What each route was last asked in. (The first paint is English until the stored language is read, so a page may ask once in English before it re-reads in Chinese; what matters is the read it ends on, and that no read leaves the language out.)
  const asked = new Map<string, string>();
  page.on("request", (r) => {
    const u = new URL(r.url());
    if (/^\/(home|alerts|approvals\/queue|reconciliation|ledger|audit|decisions)/.test(u.pathname) && u.port === String(new URL(API).port)) asked.set(u.pathname, u.searchParams.get("lang") ?? "none");
  });
  await toDay34(page, request);
  await page.goto("/");
  const alertId = await page.getByTestId("home-next-action").getAttribute("data-alert");
  await runPlan(page, alertId!);
  await expect(page.getByTestId(`alert-waiting-${alertId}`)).toBeVisible();
  await page.goto("/approvals");
  const card = page.locator('[id^="approval-APR-"]').first();
  await expect(card).toBeVisible();
  // Chinese sentences, English figures: the amount and the cost are the same figures the English queue shows.
  await expect(card.locator('[data-testid="approval-headline"]')).toContainText("批准");
  await expect(card.locator('[data-testid="approval-headline"]')).toContainText("¥200,000.00");
  await expect(card.locator('[data-testid^="approval-state-"]')).toContainText("等待您批准");
  await expect(card.locator('[data-testid="approval-cost"]')).toContainText("¥1,782.19");
  await expect(card.locator('[data-testid="approval-if-decline"]')).toContainText("最低现金储备");
  await expect(card.locator('[data-testid="approval-after"]')).not.toContainText("Cash stays above");
  // The decision record, one click away, says its state and what it waits for in Chinese.
  await card.locator('[data-testid^="approval-record-"]').click();
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "AUTHORIZATION_REQUIRED");
  await expect(page.getByTestId("record-state")).toContainText("您");
  await expect(page.getByTestId("record-waiting")).toContainText("您");
  // Live: no read the page made asked in English (the mock makes no requests, it replays the recorded Chinese answers).
  if (test.info().project.name === "live") {
    expect(asked.size).toBeGreaterThan(2);
    expect([...asked].filter(([, l]) => l !== "zh")).toEqual([]);
  }
});
