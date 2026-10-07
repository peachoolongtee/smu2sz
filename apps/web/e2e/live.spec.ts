import type { APIRequestContext, Page } from "@playwright/test";
import { DEMO_TOKEN, expect, test } from "./fixtures";
import { runPlan } from "./helpers";

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
      headers: { "access-control-allow-origin": `http://localhost:${process.env.E2E_LIVE_PORT ?? 3000}` },
      body: JSON.stringify({ detail: "owner token required" }),
    }),
  );
  await page.goto("/mandate");
  // In words, not an error code: the page asks for the sign-in, and the dialog is open.
  await expect(page.getByTestId("signin-needed")).toContainText("Sign in to see your books");
  await expect(page.getByTestId("signin-needed")).not.toContainText("401");
  await expect(page.getByRole("dialog", { name: "Owner sign-in" })).toBeVisible();
});

test("the borrower file downloads as HTML and Word, and the owner approves the one pending application", async ({ page }) => {
  await walkTo(page, 13); // through the capex application (pending) and the read-only borrower file (nothing pending)
  await expect(page).toHaveURL(/\/approvals/);

  await page.goto("/capex");
  await expect(page.getByTestId("borrower-file-downloads")).toBeVisible();
  const [html] = await Promise.all([page.waitForEvent("download"), page.getByTestId("download-html").click()]);
  expect(html.suggestedFilename()).toMatch(/^BF-.*\.html$/);
  const [docx] = await Promise.all([page.waitForEvent("download"), page.getByTestId("download-docx").click()]);
  expect(docx.suggestedFilename()).toMatch(/^BF-.*\.docx$/);

  await page.goto("/approvals");
  await expect(page.getByText("1 pending")).toBeVisible();
  const approve = page.getByRole("button", { name: "Approve" });
  await approve.first().click();
  await expect(page.getByText("0 pending")).toBeVisible();
  await expect(page.getByText("Approved")).toHaveCount(1);

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

test("the day-0 plan: 'go ahead' brings cash now and leaves the advance in transit until its landing day", async ({ page, request }) => {
  const owner = { "X-Owner-Token": TOKEN };
  expect((await request.post(`${API}/demo/reset`, { headers: owner, data: {} })).ok()).toBeTruthy();
  await page.goto("/chat");
  await page.getByTestId("prompt-fund").click();
  const first = page.getByTestId("chat-turn").first();
  // "Fund the cash gap" only proposes; every action says when its cash lands.
  await expect(first.getByTestId("chat-reply")).toContainText("lands on day 3");
  await expect(first.getByTestId("chat-ops")).toHaveCount(0);
  await first.getByTestId("chat-goahead").click();
  const second = page.getByTestId("chat-turn").nth(1);
  await expect(second.getByTestId("chat-reply")).toContainText("Cash in now");
  await expect(second.getByTestId("chat-reply")).toContainText("Still to land");

  // The Business home keeps cash in hand apart from the advance on its way (both are the server's strings).
  await page.goto("/");
  await expect(page.getByTestId("home-cash")).toHaveText("¥550k");
  await expect(page.getByTestId("home-in-transit")).toContainText("¥255k funding arriving in 3 days");
  // Once day 3 has passed the advance is cash.
  expect((await request.post(`${API}/clock/advance`, { headers: owner, data: { to_day: 4 } })).ok()).toBeTruthy();
  await page.goto("/");
  await expect(page.getByTestId("home-cash")).toHaveText("¥805k");
  await expect(page.getByTestId("home-in-transit")).toHaveCount(0);
  await request.post(`${API}/demo/reset`, { headers: owner, data: {} });
});

/** The same calls scripts/demo_run.py makes: the deal, the receipt on day 2 (with the bank's reference), then the clock to day 34. */
async function toDay34(request: APIRequestContext) {
  const owner = { "X-Owner-Token": TOKEN };
  const bank = { "X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key" };
  const post = async (path: string, data: object, headers: Record<string, string> = owner) => {
    const res = await request.post(`${API}${path}`, { headers, data });
    expect(res.ok(), path).toBeTruthy();
    return res.json();
  };
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
      bank_reference: "E2E-RCPT-1",
    },
    bank,
  );
  await post("/clock/advance", { to_day: 30 });
  await post("/clock/advance", { to_day: 34 });
  return { post };
}

test("on day 34 the cure needs the owner: the alert says so, the click queues it, approval runs it, the cash lands on day 37", async ({ page, request }) => {
  const { post } = await toDay34(request);

  // The agreed early payment arrived on day 2: reconciliation shows it as received (and none lapsed).
  await page.goto("/reconciliation");
  await expect(page.getByTestId("promised-RCV-A")).toHaveAttribute("data-status", "RECEIVED");
  await expect(page.getByText("Lapsed promises: 0")).toBeVisible();
  await expect(page.getByTestId("receipt-ref-e2e-receipt-1")).toContainText("E2E-RCPT-1");

  await page.goto("/alerts");
  const card = page.locator("#alert-ALERT-RESERVE-42");
  await expect(card).toContainText("Cost ¥1,782.19");
  await expect(card).toContainText("× 365/10 = 32.5% a year");
  await expect(card.getByText("Needs your approval").first()).toBeVisible();
  await expect(card.getByTestId("alert-needs-approval-ALERT-RESERVE-42")).toContainText("15.00%");
  await expect(card.getByTestId("fix-ALERT-RESERVE-42")).toBeVisible();

  // The act is always bound to what was shown: state_version and the alert's suggestions, in order.
  const acts: { state_version: unknown; suggestions: { operation_kind: string; amount_fen: number | null }[] }[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && /\/alerts\/[^/]+\/act$/.test(r.url())) acts.push(r.postDataJSON());
  });
  await page.goto("/");
  const risk = page.getByTestId("home-next-action");
  await expect(risk).toContainText("¥1,782.19");
  await expect(risk.getByTestId("next-action-needs-owner")).toContainText("15.00%");
  await expect(risk.getByTestId("fix-open-ALERT-RESERVE-42")).toHaveText("Queue it for my approval");

  // The click queues it: PENDING_APPROVAL with an id, never styled as success, and the action stays on the home.
  await runPlan(risk, "ALERT-RESERVE-42");
  await expect.poll(() => acts.length).toBe(1);
  expect(typeof acts[0].state_version).toBe("number");
  expect(acts[0].suggestions.some((x) => x.operation_kind === "SUBMIT_INVOICE_FOR_FINANCING" && typeof x.amount_fen === "number")).toBeTruthy();
  const op = page.getByTestId("fix-result").getByTestId("chat-op-SUBMIT_INVOICE_FOR_FINANCING");
  await expect(op).toHaveAttribute("data-status", "PENDING_APPROVAL");
  await expect(op.getByTestId("op-state")).toContainText("Waiting for your approval");
  await expect(op.getByTestId("op-state").locator(":scope > span")).not.toHaveClass(/text-ok-fg/);
  const waiting = page.getByTestId("alert-waiting-ALERT-RESERVE-42");
  await expect(waiting).toHaveText(/^Waiting for your approval\s*Open the approval card$/);
  await expect(page.getByTestId("home-next-action")).toBeVisible();
  await expect(page.locator('[data-testid^="home-approval-APR-"]').first()).toContainText("Approve ¥200,000.00 of invoice financing?");

  // The owner approves on the approval card: it executes and says when the cash lands.
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await expect(page).toHaveURL(/\/approvals#approval-APR-/);
  const approvalCard = page.locator('[id^="approval-APR-"]').first();
  await approvalCard.getByRole("button", { name: "Approve" }).click();
  await expect(approvalCard.locator('[data-testid^="approval-result-"]')).toContainText("the cash lands in 3 days");
  await expect(approvalCard).toContainText("Approved");
  // The decision day is the API's `decided_day` (the clock is on day 34).
  await expect(approvalCard.locator('[data-testid^="approval-decided-"]')).toHaveText("Decided today.");
  // After a reload the card still has both, because the queue itself carries `decided_day` and `result_message`.
  await page.reload();
  const reloaded = page.locator('[id^="approval-APR-"]').first();
  await expect(reloaded.locator('[data-testid^="approval-decided-"]')).toHaveText("Decided today.");
  await expect(reloaded.locator('[data-testid^="approval-result-"]')).toContainText("the cash lands in 3 days");

  await page.goto("/");
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  await expect(page.getByTestId("home-in-transit")).toContainText("¥200k funding arriving in 3 days");
  await expect(page.getByTestId("home-changes-list")).toContainText("You approved ¥200,000.00 of invoice financing. Funds arrive in 3 days.");

  await post("/demo/reset", {});
});

test("when the books move after the alert was shown, the act answers 409 and the page says so without success styling", async ({ page, request }) => {
  const { post } = await toDay34(request);
  await page.goto("/");
  const fix = page.getByTestId("fix-open-ALERT-RESERVE-42");
  await expect(fix).toBeVisible();
  // The books move behind the page's back (the clock), so the state_version the page holds is stale.
  await post("/clock/advance", { to_day: 35 });
  await fix.click();
  await page.getByTestId("fix-ALERT-RESERVE-42").click();
  const changed = page.getByTestId("fix-changed");
  await expect(changed).toContainText("The books changed since this was shown");
  await expect(changed).toContainText("Nothing was run");
  await expect(page.getByTestId("fix-result")).toHaveCount(0);
  await expect(changed).not.toHaveClass(/text-ok-fg|bg-ok-bg/);
  // Nothing was queued: no approval holds an alert cure.
  const res = await request.get(`${API}/approvals/queue`, { headers: { "X-Owner-Token": TOKEN } });
  expect(res.ok()).toBeTruthy();
  const queue = (await res.json()) as { approvals: { op_id: string | null }[] };
  expect(queue.approvals.filter((a) => (a.op_id ?? "").startsWith("alert:"))).toEqual([]);
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
  await expect(page.getByText("1 pending")).toBeVisible();
});

test("the plan card shows the landing day the API sent, not one derived from the lead time", async ({ page }) => {
  // The real answer with the advance's landing day moved to 9 (the facility's lead time would give 3).
  await page.route(`${API}/router/plan`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    const body = await response.json();
    for (const plan of [body.committed, body.expected]) {
      for (const a of plan.actions) if (a.kind === "FINANCE_INVOICE") a.lands_day = 9;
    }
    return route.fulfill({ response, json: body });
  });
  await walkTo(page, 4); // reset, compile, evaluate, plan: the funding page
  await expect(page).toHaveURL(/\/funding/);
  const lands = page.getByTestId("plan-lands");
  await expect(lands).toHaveCount(2);
  await expect(lands.nth(0)).toHaveText("Day 0");
  await expect(lands.nth(1)).toHaveText("Day 9");
});

const CONFLICT = {
  status: 409,
  contentType: "application/json",
  headers: { "access-control-allow-origin": `http://localhost:${process.env.E2E_LIVE_PORT ?? 3000}`, "retry-after": "1" },
  body: JSON.stringify({ detail: { code: "CONCURRENT_WRITE_CONFLICT", message: "busy", retry: true, retry_after_seconds: 1 } }),
};

test("a write that lost a race is sent once more after the hint, and succeeds", async ({ page }) => {
  await walkTo(page, 13);
  let posts = 0;
  await page.route(`${API}/approvals/APR-*`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    posts += 1;
    return posts === 1 ? route.fulfill(CONFLICT) : route.continue();
  });
  await page.goto("/approvals");
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.locator('[id^="approval-APR-"]').first()).toContainText("Approved");
  expect(posts).toBe(2);
});

test("a second conflict is not retried again: the error says the books were busy", async ({ page }) => {
  await walkTo(page, 13);
  let posts = 0;
  await page.route(`${API}/approvals/APR-*`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    posts += 1;
    return route.fulfill(CONFLICT);
  });
  await page.goto("/approvals");
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByText(/books were busy/i)).toBeVisible();
  await expect(page.getByText("1 pending")).toBeVisible();
  expect(posts).toBe(2);
});

test("the Business inbox waits for the books before it shows any sender, and says so when they fail to load", async ({ page }) => {
  await page.route(`${API}/state`, async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.continue();
  });
  await page.goto("/deals");
  // Business mode, books still loading: a loading block, and no message row at all (the registry decides who is known).
  await expect(page.getByTestId("inbox-loading")).toBeVisible();
  await expect(page.locator('[data-testid^="inbox-msg-"]')).toHaveCount(0);
  await expect(page.getByTestId("inbox-thread-BUYER-1")).toBeVisible();
  await expect(page.getByTestId("inbox-msg-SEC")).toHaveCount(0);
  await expect(page.getByTestId("inbox-blocked")).toContainText("1 message from an unknown sender was set aside.");
  // The books fail to load: the error, never the unchecked list.
  await page.unroute(`${API}/state`);
  await page.route(`${API}/state`, (route) =>
    route.fulfill({
      status: 500,
      contentType: "application/json",
      headers: { "access-control-allow-origin": `http://localhost:${process.env.E2E_LIVE_PORT ?? 3000}` },
      body: JSON.stringify({ detail: "books unavailable" }),
    }),
  );
  await page.goto("/deals");
  await expect(page.getByTestId("inbox-error")).toBeVisible();
  await expect(page.locator('[data-testid^="inbox-msg-"]')).toHaveCount(0);
});
