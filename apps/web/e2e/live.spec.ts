import type { APIRequestContext, Page } from "@playwright/test";
import { DEMO_TOKEN, expect, test } from "./fixtures";
import { runPlan, walkStory, sendCounter } from "./helpers";

/** Live-mode only: owner-token handling, the 401 state, borrower-file downloads and owner approval. */

const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
const TOKEN = DEMO_TOKEN;

/** Walks the first `steps` steps of the guided Demo (the late-payment loop, eleven steps; lib/demo.ts): 2 = the buyer asks and FLOW decides, 7 = the cure is queued for the owner. */
async function walkTo(page: Page, steps: number) {
  await page.goto("/demo");
  await walkStory(page, steps);
}

test("every API request carries the owner token", async ({ page }) => {
  const seen: { url: string; token: string | undefined }[] = [];
  page.on("request", (r) => {
    if (r.url().startsWith(API) && r.method() !== "OPTIONS") seen.push({ url: r.url(), token: r.headers()["x-owner-token"] });
  });
  await walkTo(page, 2); // reset, compile, evaluate and the plan the Debt Desk priced
  await expect(page).toHaveURL(/\/deals/);
  expect(seen.length).toBeGreaterThan(5);
  // GET /clock is the one credential-free read (the day is public to the Demo's control strip); every other request carries the token.
  for (const r of seen.filter((x) => !x.url.endsWith("/clock"))) expect(r.token, r.url).toBe(TOKEN);
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
  // The capex question (an optional scene) evaluates and prepares the read-only borrower file; the application is the owner's click.
  await page.goto("/demo");
  await page.getByTestId("more-run-capex").click();
  await expect(page).toHaveURL(/\/capex/);
  await page.getByTestId("capex-apply").click();
  await expect(page.getByTestId("capex-applied")).toBeVisible();

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
  await walkTo(page, 2); // reset, compile, evaluate
  await page.goto("/verdict");
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
  // Business chat has no general prompts (they live in Demo): the owner types the request.
  await page.getByRole("textbox", { name: "Message" }).fill("Fund the cash gap");
  await page.getByTestId("chat-send").click();
  const first = page.getByTestId("chat-turn").first();
  // "Fund the cash gap" only proposes; every action says when its cash lands.
  // A Business turn is the server's owner template: the plan in words, its cost and when each part arrives, no ids and no tier words.
  await expect(first.getByTestId("chat-reply")).toContainText("arriving in 3 days");
  await expect(first.getByTestId("chat-reply")).toContainText("estimated cost ¥3,113.93");
  await expect(first.getByTestId("chat-reply")).not.toContainText(/TIER|Tier \d/);
  await expect(first.getByTestId("chat-goahead")).toHaveText("Yes, run it");
  await expect(first.getByTestId("chat-ops")).toHaveCount(0);
  await first.getByTestId("chat-goahead").click();
  const second = page.getByTestId("chat-turn").nth(1);
  await expect(second.getByTestId("chat-reply")).toContainText("¥150,000.00");

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

/**
 * The same calls scripts/demo_run.py makes: the deal, the receipt on day 2 (with the bank's reference), then the clock to day 34.
 * `receipt` is what the buyer paid on day 2: all of what the server expected, half of it (the part-kept promise), or nothing.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Post = (path: string, data: object, headers?: Record<string, string>) => Promise<any>;

async function walkToDay34(request: APIRequestContext, receipt: "full" | "half" | "none") {
  const owner = { "X-Owner-Token": TOKEN };
  const post: Post = async (path, data, headers = owner) => {
    const res = await request.post(`${API}${path}`, { headers, data });
    expect(res.ok(), path).toBeTruthy();
    return res.json();
  };
  await post("/demo/reset", {});
  const { offer } = await post("/offers", { fixture_id: "EX01_PACKAGE" });
  const verdict = await post(`/offers/${offer.offer_id}/evaluate`, { fixture_id: "EX01_PACKAGE" });
  // The send is bound to what was shown, as the Deals page binds it: the verdict, the first counter and the books' version.
  const deal = await post(`/negotiate/${offer.offer_id}`, { buyer_profile: "cooperative", verdict_id: verdict.id, counter_id: verdict.counters[0].id, state_version: verdict.state_version });
  expect(deal.outcome).toBe("DEAL");
  expect(deal.decision_id).toBe(`deal:${offer.offer_id}`);
  await dayTwoToDay34(request, receipt, post);
  return { post, offerId: offer.offer_id as string };
}

/** From the deal to day 34: the clock to day 2, the buyer's receipt (or none), then day 30 and day 34. */
async function dayTwoToDay34(request: APIRequestContext, receipt: "full" | "half" | "none", post: Post) {
  const owner = { "X-Owner-Token": TOKEN };
  const bank = { "X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key" };
  await post("/clock/advance", { to_day: 2 });
  if (receipt !== "none") {
    const recon = await (await request.get(`${API}/reconciliation`, { headers: owner })).json();
    const promised = recon.reconciliation.promised[0]; // the server's own expected receipt
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
        // Test setup for the bank feed, not a figure on screen: half of what the server expected is a part-kept promise.
        amount_fen: receipt === "half" ? Math.floor(promised.expected_fen / 2) : promised.expected_fen,
        bank_reference: "E2E-RCPT-1",
      },
      bank,
    );
  }
  await post("/clock/advance", { to_day: 30 });
  await post("/clock/advance", { to_day: 34 });
}

const toDay34 = (request: APIRequestContext) => walkToDay34(request, "full");
/** R07: day 34 on the books where the buyer never paid on day 2, so cash is under the reserve today. */
const toDay34NoReceipt = (request: APIRequestContext) => walkToDay34(request, "none");
const toDay34HalfReceipt = (request: APIRequestContext) => walkToDay34(request, "half");

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
    if (r.method() === "POST" && /\/alerts\/[^/]+\/act(\?|$)/.test(r.url())) acts.push(r.postDataJSON());
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
  // The queued cure is said once, by the next step's waiting tile in the warning look; the agent's answer is not a card when it only waits.
  const waiting = page.getByTestId("alert-waiting-ALERT-RESERVE-42");
  await expect(waiting).toHaveClass(/text-warn-fg/);
  await expect(page.getByTestId("fix-result")).toHaveCount(0);
  await expect(waiting).toHaveText("Waiting for your approval");
  await expect(page.getByTestId("home-next-action")).toBeVisible();
  // The question is the next step's card (cost, landing, the one primary); there is no second card saying it again.
  await expect(risk.getByTestId("next-action-lands")).toHaveText("in 3 days");
  await expect(page.locator('[data-testid^="home-approval-APR-"]')).toHaveCount(0);

  // The owner approves on the approval card: it executes and says when the cash lands.
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await expect(page).toHaveURL(/\/approvals#approval-APR-/);
  const approvalCard = page.locator('[id^="approval-APR-"]').first();
  // The price the owner is quoted is the one stored when the request was made (F13).
  await expect(approvalCard.getByTestId("approval-quote")).toContainText("Quoted when requested (today)");
  await expect(approvalCard.getByTestId("approval-cost")).toContainText("¥1,782.19");
  await approvalCard.getByRole("button", { name: "Approve" }).click();
  await expect(approvalCard.locator('[data-testid^="approval-result-"]')).toContainText("the cash lands in 3 days");
  await expect(approvalCard.locator('[data-testid^="approval-state-"]')).toContainText("Approved, cash arrives in 3 days");
  // Decided: the quote is still there (it does not vanish with the pending alert), behind its own fold, with what actually happened beside it.
  await expect(approvalCard.getByTestId("approval-cost")).toContainText("¥1,782.19");
  await approvalCard.locator('[data-testid^="approval-quoted-"] > summary').click();
  await expect(approvalCard.getByTestId("approval-quote-actual")).toContainText("¥200,000.00");
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
  // The cure is an open decision until its cash lands: the hero says what is on its way once (Waiting on does not list it again), and its record says the same.
  await expect(page.getByTestId("home-waiting-on-list")).toHaveCount(0);
  await page.goto("/approvals");
  await page.locator('[data-testid^="approval-record-"]').first().click();
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "SETTLEMENT_PENDING");
  await expect(page.getByTestId("record-settlement")).toContainText("¥200,000.00");
  // The clock moves: the record follows the books, and the lot has landed.
  await post("/clock/advance", { to_day: 38 });
  await page.reload();
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "SETTLED");

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
  // A pending approval to decide: the capex application (an optional scene, then the owner's own click on the Capex page).
  await page.goto("/demo");
  await page.getByTestId("more-run-capex").click();
  await page.getByTestId("capex-apply").click();
  await expect(page.getByTestId("capex-applied")).toBeVisible();
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
  await page.route(`${API}/router/plan**`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    const body = await response.json();
    for (const plan of [body.committed, body.expected]) {
      for (const a of plan.actions) if (a.kind === "FINANCE_INVOICE") a.lands_day = 9;
    }
    return route.fulfill({ response, json: body });
  });
  await walkTo(page, 2); // reset, compile, evaluate and the plan the Debt Desk priced: the funding page shows it
  await page.goto("/funding");
  const lands = page.getByTestId("plan-lands");
  await expect(lands).toHaveCount(2);
  await expect(lands.nth(0)).toHaveText("Day 0");
  await expect(lands.nth(1)).toHaveText("Day 9");
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

const CONFLICT = {
  status: 409,
  contentType: "application/json",
  headers: { "access-control-allow-origin": `http://localhost:${process.env.E2E_LIVE_PORT ?? 3000}`, "retry-after": "1" },
  body: JSON.stringify({ detail: { code: "CONCURRENT_WRITE_CONFLICT", message: "busy", retry: true, retry_after_seconds: 1 } }),
};

test("a write that lost a race is sent once more after the hint, and succeeds", async ({ page }) => {
  await walkTo(page, 7);
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
  await walkTo(page, 7);
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
  // The set-aside line is the books' own: the ledger's count when something was refused, else the labelled example; its link is the real section.
  await expect(page.getByTestId("inbox-blocked")).toContainText(/set aside/);
  await expect(page.getByTestId("inbox-blocked").getByRole("link")).toHaveAttribute("href", "/activity#activity-refused");
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

test("day 34 with no receipt: the Home says below the reserve today, the promise is history, and no page says 'by today'", async ({ page, request }) => {
  const { post } = await toDay34NoReceipt(request);
  await page.goto("/");
  await expect(page.getByTestId("home-headline")).toHaveText("Below reserve today.");
  const hero = page.getByTestId("home-status");
  await expect(hero).toContainText("Below reserve today");
  await expect(hero).not.toContainText(/ago/);
  // The forecast starts today: the first unsafe day is today, not a closed day.
  await page.goto("/cash");
  await expect(page.getByTestId("cash-unsafe-when")).not.toHaveText(/ago/);
  await expect(page.getByTestId("cash-forecast")).toBeVisible();
  // The early-payment promise lapsed: it is said in the past, never as a deadline "by today".
  await page.goto("/receivables");
  const promised = page.getByTestId("promised-RCV-A");
  await expect(promised).toBeVisible();
  await expect(promised).toContainText(/ago/);
  await expect(promised).not.toContainText(/by today/);
  await expect(promised).not.toContainText(/CMT-/);
  await post("/demo/reset", {});
});

test("day 34 after a half receipt: the early-payment window for the rest is said as ended, not 'by today'", async ({ page, request }) => {
  const { post } = await toDay34HalfReceipt(request);
  await page.goto("/receivables");
  const receipt = page.getByTestId("receipt-e2e-receipt-1");
  await expect(receipt).toBeVisible();
  await expect(receipt).toContainText(/ended 32 days ago/);
  await expect(receipt).not.toContainText(/by today/);
  await page.goto("/");
  await expect(page.getByTestId("home-headline")).toHaveText("Below reserve today.");
  // The part-paid promise's row names its four facts under the sentence (F25).
  const more = page.getByTestId("home-changes-more");
  if (await more.count()) await more.locator("> summary").click();
  // Home says it once, in the server's sentence; the four named facts are on Receivables.
  await expect(page.getByTestId("home-change-facts")).toHaveCount(0);
  await expect(page.getByTestId("home-change-LATE").filter({ hasText: "the early-payment window has ended" })).toHaveCount(1);
  await post("/demo/reset", {});
});

test("day 34 after a half receipt: Chase payment opens the API's handoff, its balance is the API's own, and the receipt row names its four facts", async ({ page, request }) => {
  const { post } = await toDay34HalfReceipt(request);
  const owner = { "X-Owner-Token": TOKEN };
  const recon = (await (await request.get(`${API}/reconciliation`, { headers: owner })).json()).reconciliation;
  const owed: string = recon.outstanding.find((o: { receivable_id: string }) => o.receivable_id === "RCV-A").face_display;
  const handoff = await (await request.get(`${API}/receivables/RCV-A/chase`, { headers: owner })).json();
  expect(handoff.outstanding_display).toBe(owed);
  expect(handoff.late_days).toBe(2);

  await page.goto("/receivables");
  const facts = page.getByTestId("receipt-facts-e2e-receipt-1");
  await expect(facts.getByTestId("receipt-facts-e2e-receipt-1-received")).toContainText(recon.receipts[0].received_display);
  await expect(facts.getByTestId("receipt-facts-e2e-receipt-1-cleared")).toContainText(recon.receipts[0].face_cleared_display);
  await expect(facts.getByTestId("receipt-facts-e2e-receipt-1-remaining")).toContainText(owed);
  await expect(facts).toContainText("The early-payment window has ended");

  await page.getByTestId("chase-open-RCV-A").click();
  const dialog = page.getByTestId("chase-dialog-RCV-A");
  await expect(dialog.getByTestId("chase-fact-outstanding")).toContainText(owed);
  await expect(dialog.getByTestId("chase-request")).toHaveText(handoff.request_text);
  await expect(dialog.getByTestId("chase-thread")).toHaveAttribute("href", handoff.thread_href);
  await post("/demo/reset", {});
});

test("approving after the mandate has expired is refused: the card ends as 'could not run', with no buttons and no money moved", async ({ page, request }) => {
  const { post } = await toDay34NoReceipt(request);
  await page.goto("/");
  // The reserve alert's id carries the books' version, which differs without the receipt: read it from the page.
  const open = page.getByTestId("home-next-action").locator('[data-testid^="fix-open-ALERT-RESERVE"]');
  const alertId = ((await open.getAttribute("data-testid")) ?? "").replace("fix-open-", "");
  expect(alertId).toMatch(/^ALERT-RESERVE/);
  await runPlan(page.getByTestId("home-next-action"), alertId);
  await page.getByTestId(`alert-approval-link-${alertId}`).click();
  await expect(page).toHaveURL(/\/approvals#approval-APR-/);
  const card = page.locator('[id^="approval-APR-"]').first();
  const approve = card.getByRole("button", { name: /^Approve/ });
  await expect(approve).toBeEnabled();
  // The mandate's last day is 90: the owner is slow, and the executor refuses to run what they approve.
  await post("/clock/advance", { to_day: 91 });
  await approve.click();
  const refused = card.locator('[data-testid^="approval-refused-"]');
  await expect(refused).toContainText("You approved it, but it could not run:");
  await expect(refused).toContainText("No money moved.");
  await expect(refused).not.toContainText(/declined/i);
  await expect(card).toContainText("Approved");
  await expect(card.getByRole("button", { name: /^Approve/ })).toHaveCount(0);
  await expect(card.getByRole("button", { name: "Decline", exact: true })).toHaveCount(0);
  // The queue is the truth: after a reload the card is still terminal, and no cash was moved.
  await page.reload();
  await expect(page.locator('[id^="approval-APR-"]').first().locator('[data-testid^="approval-refused-"]')).toContainText("could not run");
  // The record agrees: FAILED is a final state of its own, and the quote taken when the request was made is still on the card.
  await expect(page.locator('[id^="approval-APR-"]').first().locator('[data-testid^="approval-quoted-"] > summary')).toContainText("Quoted when requested");
  await expect(page.locator('[id^="approval-APR-"]').first().locator('[data-testid^="approval-state-"]')).toHaveAttribute("data-tone", "bad");
  await page.locator('[id^="approval-APR-"]').first().locator('[data-testid^="approval-record-"]').click();
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "FAILED");
  await expect(page.getByTestId("record-execution")).toContainText("No money moved");
  const ledger = await (await request.get(`${API}/ledger`, { headers: { "X-Owner-Token": TOKEN } })).json();
  const funding = (ledger.operations as { kind: string; status: string; op_id: string }[]).filter((o) => o.op_id.startsWith("alert:"));
  expect(funding.some((o) => o.status === "EXECUTED")).toBe(false);
  await post("/demo/reset", {});
});

test("a buyer's agreement that expired before the owner looked cannot be approved: the card says why and keeps Decline", async ({ page, request }) => {
  const owner = { "X-Owner-Token": TOKEN };
  await request.post(`${API}/demo/reset`, { headers: owner, data: {} });
  const sent = await request.post(`${API}/nl`, {
    headers: { "X-Counterparty-Key": "demo-buyer-1-key" },
    data: { session_id: "e2e-agreement", actor: "COUNTERPARTY", counterparty_id: "BUYER-1", text: "We can pay the invoice early at 0.5%.", request_id: "e2e-agreement-1" },
  });
  expect(sent.ok()).toBeTruthy();
  await page.goto("/approvals");
  const card = page.locator('[id^="approval-APR-"]').first();
  // While it waits, the terms are on the card above the buttons.
  await expect(card.getByTestId("approval-terms")).toContainText("The buyer may pay early and take 0.50%");
  await expect(card.getByRole("button", { name: /^Approve/ })).toBeEnabled();
  // The agreement expires while the page is open; "Try again" reads the queue and the gate closes.
  await request.post(`${API}/clock/advance`, { headers: owner, data: { to_day: 60 } });
  await page.reload();
  const gap = page.locator('[id^="approval-APR-"]').first().getByTestId("approval-terms-unavailable");
  await expect(gap).toContainText("I can't safely present the full terms for review.");
  await expect(gap).toContainText("has expired");
  await expect(page.locator('[id^="approval-APR-"]').first().getByRole("button", { name: /^Approve/ })).toBeDisabled();
  await expect(page.locator('[id^="approval-APR-"]').first().getByRole("button", { name: "Decline", exact: true })).toBeEnabled();
  await request.post(`${API}/demo/reset`, { headers: owner, data: {} });
});

/** Reads the Deals page's first Foshan message and checks it against the limits. */
async function checkedDeal(page: Page) {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
}

const ownerPost = (request: APIRequestContext): Post => async (path, data, headers = { "X-Owner-Token": TOKEN }) => {
  const res = await request.post(`${API}${path}`, { headers, data });
  expect(res.ok(), path).toBeTruthy();
  return res.json();
};

test("Deals: Send carries what was shown, and the record's state follows: Agreed, then Fulfilled once the receipt came", async ({ page, request }) => {
  const post = ownerPost(request);
  await post("/demo/reset", {});
  const sends: { buyer_profile?: string; verdict_id?: string; counter_id?: string; state_version?: unknown }[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && /\/negotiate\//.test(r.url())) sends.push(r.postDataJSON());
  });
  await checkedDeal(page);
  const steps = page.getByTestId("deal-state-chip");
  await expect(steps).toContainText("Counter recommended");
  await expect(page.getByTestId("deal-send")).toHaveText("Send Option A (simulated buyer reply)");
  await sendCounter(page);
  await expect.poll(() => sends.length).toBe(1);
  // The browser sends ids and the shown books' version, never a figure.
  expect(sends[0].buyer_profile).toBe("cooperative");
  expect(sends[0].verdict_id).toMatch(/^VER-/);
  expect(sends[0].counter_id).toMatch(/^CTR-/);
  expect(typeof sends[0].state_version).toBe("number");
  await expect(steps).toHaveAttribute("data-state", "AGREED");
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Agreed");
  await expect(page.locator("#commitments").getByTestId("commitment-state")).toHaveText("Agreed");
  // The record knows what was sent.
  await page.goto("/ledger");
  const offerId = await page.evaluate(() => JSON.parse(sessionStorage.getItem("tl-demo-v3") ?? "{}").offerId as string);
  const record = await (await request.get(`${API}/decisions/${encodeURIComponent("deal:" + offerId)}`, { headers: { "X-Owner-Token": TOKEN } })).json();
  expect(record.response.sent.chosen_label).toBe("Option A");
  // The receipt came on day 2: the page reads the record again and the deal is Fulfilled.
  await dayTwoToDay34(request, "full", post);
  await page.goto("/deals");
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "FULFILLED");
  await expect(page.getByTestId("deal-state-chip")).toContainText("Fulfilled");
  await post("/demo/reset", {});
});

test("Deals: with no receipt on day 2 the line says the early payment did not arrive, and the agreement stays listed", async ({ page, request }) => {
  const post = ownerPost(request);
  await post("/demo/reset", {});
  await checkedDeal(page);
  await sendCounter(page);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
  await dayTwoToDay34(request, "none", post);
  await page.goto("/deals");
  const steps = page.getByTestId("deal-state-chip");
  await expect(steps).toHaveAttribute("data-state", "MISSED");
  await expect(page.getByTestId("deal-state-chip")).toContainText("Early payment did not arrive");
  await expect(steps).not.toContainText("Agreed");
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Early payment did not arrive");
  await expect(page.locator("#commitments").getByTestId("commitment-state")).toHaveText("Early payment did not arrive");
  await expect(page.locator("#commitments")).toContainText("Agreement expired");
  // The same record is on the Activity page's rows, and the Demo verdict page's summary says what ran.
  await page.goto("/verdict");
  await expect(page.getByTestId("execution-agreement")).toContainText("Early payment did not arrive");
  await post("/demo/reset", {});
});

test("Deals: if the books moved after the proposal was shown, Send is refused, nothing is sent, and Check again gets a current one", async ({ page, request }) => {
  const post = ownerPost(request);
  await post("/demo/reset", {});
  await checkedDeal(page);
  // The books move behind the page's back (the clock), so the version the page holds is stale.
  await post("/clock/advance", { to_day: 1 });
  await sendCounter(page);
  const changed = page.getByTestId("deal-counter-changed");
  await expect(changed).toContainText("The books moved since this was shown");
  await expect(changed).toContainText("Nothing was sent.");
  await expect(page.getByTestId("deal-negotiation")).toHaveCount(0);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
  // Nothing was agreed or run on the books.
  const ledger = await (await request.get(`${API}/ledger`, { headers: { "X-Owner-Token": TOKEN } })).json();
  expect((ledger.operations as { kind: string }[]).filter((o) => o.kind === "ACCEPT_OFFER" || o.kind === "DRAW_FACILITY")).toEqual([]);
  expect(ledger.commitments).toEqual([]);
  // Checking again evaluates on the books as they are; the new proposal can be sent.
  await changed.getByTestId("deal-check-again").click();
  await expect(changed).toHaveCount(0);
  await expect(page.getByTestId("deal-send")).toBeVisible();
  await sendCounter(page);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
  await post("/demo/reset", {});
});

test("Home: a cure that cannot restore the reserve leaves a remaining task with the routes it names, and the invoice link lands on its row", async ({ page, request }) => {
  const { post } = await toDay34NoReceipt(request);
  await page.goto("/");
  const open = page.getByTestId("home-next-action").locator('[data-testid^="fix-open-ALERT-RESERVE"]');
  const alertId = ((await open.getAttribute("data-testid")) ?? "").replace("fix-open-", "");
  await runPlan(page.getByTestId("home-next-action"), alertId);
  await page.getByTestId(`alert-approval-link-${alertId}`).click();
  await page.locator('[id^="approval-APR-"]').first().getByRole("button", { name: /^Approve/ }).click();
  await expect(page.locator('[id^="approval-APR-"]').first().locator('[data-testid^="approval-decided-"]')).toBeVisible();
  // While the cash is on its way the record waits for the lender; once it has landed the reserve is still short and the owner is asked.
  await post("/clock/advance", { to_day: 38 });
  await page.goto("/");
  const task = page.locator("#home-remaining");
  await expect(task.getByTestId("home-remaining-text")).toContainText("Your minimum cash reserve is still");
  await expect(task.getByTestId("home-remaining-text")).toContainText("This needs your decision.");
  await expect(task.getByRole("link", { name: "Compare your funding options" })).toHaveAttribute("href", "/cash#cash-options");
  await expect(task.getByRole("link", { name: "Review your limits" })).toHaveAttribute("href", "/limits");
  await task.getByRole("link", { name: "See the record" }).click();
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "SETTLED");
  await expect(page.getByTestId("record-remaining")).toContainText("This needs your decision.");
  // The invoice link lands on that invoice's row once the page has loaded.
  await page.goto("/");
  await page.locator("#home-remaining").getByRole("link", { name: /^Open the .* invoice/ }).click();
  await expect(page).toHaveURL(/\/receivables#/);
  const id = decodeURIComponent(new URL(page.url()).hash.slice(1));
  const row = page.locator(`[id="${id}"]:visible`);
  await expect(row).toHaveCount(1);
  await expect(row).toBeInViewport();
  await post("/demo/reset", {});
});

test("Deals: the workspace is the API's, in its order, and ?buyer= selects the buyer's deal", async ({ page, request }) => {
  const post = ownerPost(request);
  await post("/demo/reset", {});
  await page.goto("/deals?buyer=BUYER-1");
  await expect(page.locator("#deal-selected")).toContainText("Foshan Home Retail Co.");
  await expect(page.getByTestId("inbox-collapsed")).toBeVisible();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Counter recommended");
  // Every sentence below is the server's: the asks, the lines, the reasons.
  await expect(page.getByTestId("deal-ask-IMMEDIATE_DISCOUNT")).toContainText("The buyer may pay early and take 1.20% off the ¥420,000.00 invoice");
  await expect(page.getByTestId("deal-impact-immediate").getByTestId("deal-impact-amount")).toHaveText("¥5,040.00");
  await expect(page.getByTestId("deal-impact-total")).toHaveText("¥28,326.92");
  await expect(page.getByTestId("deal-impact-forward")).not.toContainText("¥5,040.00");
  await expect(page.getByTestId("deal-why-reasons")).toContainText("Accepted as asked, cash would fall below your minimum");
  await expect(page.getByTestId("deal-evaluated")).toHaveText("Evaluated today");
  const tops = await page.evaluate(() => ["deal-selected", "deal-recommendation-card", "counters", "deal-ask", "deal-impact"].map((id) => document.getElementById(id)?.getBoundingClientRect().top ?? -1));
  expect(tops).toEqual([...tops].sort((a, b) => a - b));
  expect((await page.locator("main").innerText()).match(/60-day payment terms/g)).toHaveLength(1);
  await post("/demo/reset", {});
});

test("Cash: the comparison arrives grouped and ordered by the API, and the forecast says what it counts", async ({ page, request }) => {
  await ownerPost(request)("/demo/reset", {});
  await page.goto("/cash");
  await expect(page.getByTestId("cash-options-order")).toContainText("The recommended plan first");
  expect(await page.getByTestId("cash-options-list").locator("[data-group]").evaluateAll((els) => els.filter((el) => (el.getAttribute("data-testid") ?? "").startsWith("cash-options-")).map((el) => el.getAttribute("data-group")))).toEqual([
    "RECOMMENDED",
    "CONDITIONAL_ON_BUYER",
    "INSUFFICIENT",
    "NOT_AVAILABLE_YET",
  ]);
  await expect(page.getByTestId("cash-options-RECOMMENDED")).toContainText("#1");
  await expect(page.getByTestId("cash-options-CONDITIONAL_ON_BUYER")).not.toContainText("#");
  await expect(page.locator("#cash-chart")).toContainText("Expected invoice payments at their due dates and committed funding; overdue payments are excluded");
  await expect(page.getByTestId("cash-read-when")).toHaveText("Cash read today");
  await page.getByTestId("forecast-horizon-120").click();
  await expect(page.getByTestId("cash-forecast")).toContainText("Net ¥320k");
});

test("Activity: each row says what changed, why it matters (Now) and what remains; the approval request is history with a link; the chain words are the API's", async ({ page, request }) => {
  const { post } = await toDay34(request);
  await page.goto("/");
  await runPlan(page.getByTestId("home-next-action"), "ALERT-RESERVE-42");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await page.locator('[id^="approval-APR-"]').first().getByRole("button", { name: "Approve" }).click();
  await expect(page.locator('[id^="approval-APR-"]').first()).toContainText("Approved");
  await page.goto("/activity");
  const approved = page.getByTestId("activity-SUBMIT_INVOICE_FOR_FINANCING").filter({ hasText: "You approved" });
  await expect(approved.getByTestId("activity-event")).toHaveText("You approved ¥200,000.00 of invoice financing. Funds arrive in 3 days.");
  // Today's forecast is said once above the timeline, labelled Now; the row does not repeat it.
  await expect(page.getByTestId("activity-now")).toContainText("Now");
  await expect(approved.getByTestId("activity-why")).toHaveCount(0);
  await expect(approved.getByTestId("activity-remains")).toContainText("Waiting for");
  const requested = page.getByTestId("activity-SUBMIT_INVOICE_FOR_FINANCING").filter({ hasText: "Approval requested:" });
  await expect(requested.getByTestId("activity-approval")).toContainText("Approval requested");
  await expect(requested.getByTestId("activity-approval-state")).not.toContainText("Waiting for your approval");
  await requested.getByTestId("activity-record").click();
  await expect(page).toHaveURL(/\/decisions\/alert/);
  await expect(page.getByTestId("record-state")).toBeVisible();
  await page.goto("/activity");
  await expect(page.getByTestId("chain-status")).toContainText("Record chain checks passed");
  await post("/demo/reset", {});
});
