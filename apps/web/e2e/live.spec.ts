import type { Page } from "@playwright/test";
import { DEMO_TOKEN, expect, test } from "./fixtures";

/** Live-mode only: owner-token handling, the 401 state, borrower-file downloads and owner approval. */

const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
const TOKEN = DEMO_TOKEN;

async function walkTo(page: Page, steps: number) {
  await page.goto("/mandate");
  for (let i = 0; i < steps; i++) {
    const button = page.getByTestId("demo-next");
    await expect(button).toBeEnabled();
    await button.click();
    await expect(page.getByRole("region", { name: "Guided demo" }).locator("[aria-live=polite]")).toContainText(`${i + 1}/15`);
  }
}

test("every API request carries the owner token", async ({ page }) => {
  const seen: { url: string; token: string | undefined }[] = [];
  page.on("request", (r) => {
    if (r.url().startsWith(API) && r.method() !== "OPTIONS") seen.push({ url: r.url(), token: r.headers()["x-owner-token"] });
  });
  await walkTo(page, 4); // reset, compile, evaluate, plan
  await expect(page).toHaveURL(/\/funding/);
  expect(seen.length).toBeGreaterThan(5);
  for (const r of seen) expect(r.token, r.url).toBe(TOKEN);
});

test("a 401 from the API opens the owner sign-in dialog instead of leaving a blank screen", async ({ page }) => {
  await page.route(`${API}/state`, (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "http://localhost:3000" },
      body: JSON.stringify({ detail: "owner token required" }),
    }),
  );
  await page.goto("/mandate");
  await expect(page.getByText(/rejected the owner token/i).first()).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Owner sign-in" })).toBeVisible();
});

test("the borrower file downloads as HTML and Word, and the owner approves both pending requests", async ({ page }) => {
  await walkTo(page, 13); // through the borrower file: capex apply + borrower file are both pending
  await expect(page).toHaveURL(/\/approvals/);

  await page.goto("/capex");
  await expect(page.getByTestId("borrower-file-downloads")).toBeVisible();
  const [html] = await Promise.all([page.waitForEvent("download"), page.getByTestId("download-html").click()]);
  expect(html.suggestedFilename()).toMatch(/^BF-.*\.html$/);
  const [docx] = await Promise.all([page.waitForEvent("download"), page.getByTestId("download-docx").click()]);
  expect(docx.suggestedFilename()).toMatch(/^BF-.*\.docx$/);

  await page.goto("/approvals");
  await expect(page.getByText("2 pending")).toBeVisible();
  const approve = page.getByRole("button", { name: "Approve" });
  await approve.first().click();
  await expect(page.getByText("1 pending")).toBeVisible();
  await approve.first().click();
  await expect(page.getByText("0 pending")).toBeVisible();
  await expect(page.getByText("Approved")).toHaveCount(2);

  await page.goto("/ledger");
  await expect(page.getByTestId("chain-status")).toContainText("Chain valid");
});

test("the EX01 verdict shows each early-pay discount as a yearly rate, the offer's and Counter A's", async ({ page }) => {
  await walkTo(page, 5); // reset, compile, trajectory, funding, verdict
  await expect(page).toHaveURL(/\/verdict/);
  const offer = page.getByTestId("annualised-offer");
  await expect(offer).toContainText("1.20%");
  await expect(offer).toContainText("14.78% a year for 30 days");
  await expect(offer).toContainText("against Bank credit line at 6.40%");
  const counterA = page.locator('[data-testid^="counter-"]').filter({ hasText: "Option A" });
  await expect(counterA).toContainText("10.43% a year for 30 days");
});

test("on day 34 the reserve alert states its cure's cost and flags the rate above the yearly cap", async ({ page, request }) => {
  const owner = { "X-Owner-Token": TOKEN };
  const bank = { "X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key" };
  const post = async (path: string, data: object, headers: Record<string, string> = owner) => {
    const res = await request.post(`${API}${path}`, { headers, data });
    expect(res.ok(), path).toBeTruthy();
    return res.json();
  };
  // The same calls scripts/demo_run.py makes: the deal, the receipt on day 2, then the clock to day 34.
  await post("/demo/reset", {});
  const { offer } = await post("/offers", { fixture_id: "EX01_PACKAGE" });
  await post(`/offers/${offer.offer_id}/evaluate`, { fixture_id: "EX01_PACKAGE" });
  const deal = await post(`/negotiate/${offer.offer_id}`, { buyer_profile: "cooperative" });
  expect(deal.outcome).toBe("DEAL");
  await post("/clock/advance", { to_day: 2 });
  const recon = await (await request.get(`${API}/reconciliation`, { headers: owner })).json();
  const promised = recon.reconciliation.promised[0]; // the server's own expected receipt: nothing is computed here
  const mandate = await (await request.get(`${API}/mandate`, { headers: owner })).json();
  await post(
    "/operations",
    {
      kind: "RECEIVE_PAYMENT",
      op_id: "e2e-receipt-1",
      idempotency_key: "e2e-receipt-1",
      mandate_version: mandate.mandate.version,
      requested_by: "SYSTEM",
      receivable_id: promised.receivable_id,
      amount_fen: promised.expected_fen,
    },
    bank,
  );
  await post("/clock/advance", { to_day: 30 });
  await post("/clock/advance", { to_day: 34 });

  await page.goto("/alerts");
  const card = page.locator("#alert-ALERT-RESERVE-42");
  await expect(card).toContainText("Cost ¥1,782.19");
  await expect(card).toContainText("× 365/13 = 25.0% a year");
  await expect(card.getByText("Above your yearly cap")).toBeVisible();
  await expect(card.getByTestId("fix-ALERT-RESERVE-42")).toBeVisible();

  await page.goto("/");
  const risk = page.getByTestId("home-alert-ALERT-RESERVE-42");
  await expect(risk).toContainText("Cost ¥1,782.19");
  await expect(risk.getByText("Above your yearly cap")).toBeVisible();

  await post("/demo/reset", {});
});

test("an approval is refused when the server does not recognise the owner", async ({ page }) => {
  await walkTo(page, 13);
  // Simulate a wrong token: the server treats the caller as the agent and the executor refuses.
  await page.route(`${API}/approvals/APR-*`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const headers = { ...route.request().headers(), "x-owner-token": "wrong-token" };
    return route.continue({ headers });
  });
  await page.goto("/approvals");
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByText(/only the owner may decide|rejected the owner token/i)).toBeVisible();
  await expect(page.getByText("2 pending")).toBeVisible();
});
