import { expect, test, type Page } from "@playwright/test";
import { DEMO_TOKEN } from "./fixtures";
import { resetBooks } from "./helpers";

/**
 * /chat (POST /nl). Runs in both projects: mock replays replies recorded from the real API, live calls the
 * API. These specs import `test` from @playwright/test (not ./fixtures) because they sign in themselves,
 * through the dialog, exactly as a user would.
 */

const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
const isLive = () => test.info().project.name === "live";

async function signIn(page: Page, token = DEMO_TOKEN) {
  await page.getByTestId("owner-signin-open").click();
  const dialog = page.getByRole("dialog", { name: "Owner sign-in" });
  await dialog.getByLabel("Owner token").fill(token);
  await dialog.getByRole("button", { name: "Sign in" }).click();
  await expect(dialog).toBeHidden();
}

async function send(page: Page, text: string) {
  await page.getByRole("textbox", { name: "Message" }).fill(text);
  await page.getByTestId("chat-send").click();
}

const turns = (page: Page) => page.getByTestId("chat-turn");

/** Demo mode keeps the general prompts and the buyer role-play; Business is the owner's alone (see the Business chat specs at the end). */
async function demoMode(page: Page) {
  await page.addInitScript(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "demo" })));
}

/** Already signed in as the owner, exactly where the sign-in dialog would put the token (these specs do not test sign-in). */
async function asOwner(page: Page) {
  const token = isLive() ? DEMO_TOKEN : "mock-owner";
  await page.addInitScript((tok) => sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: tok })), token);
}

/** The Business header keeps the language switch and sign-out inside the account menu; open it when it is there. */
async function openAccountMenu(page: Page) {
  const menu = page.getByTestId("account-menu");
  const summary = menu.locator("> summary");
  // The Demo shell keeps the language switch and sign-out in its header, so the menu is not always on screen.
  if ((await menu.count()) && (await summary.isVisible()) && !(await menu.evaluate((el) => (el as HTMLDetailsElement).open))) await summary.click();
}

test("owner: Evaluate EX01 is a REJECT, then go ahead lists the executed operations", async ({ page, request }) => {
  await resetBooks(request);
  await page.goto("/chat");
  await signIn(page);

  await send(page, "Evaluate EX01");
  const first = turns(page).nth(0);
  await expect(first.getByTestId("chat-outcome")).toContainText("REJECT");
  await expect(first.getByTestId("chat-intent")).toHaveText("Evaluate offer");
  await expect(first.getByTestId("chat-code-AGG_CONCESSION_EXCEEDED")).toBeVisible();
  await expect(first.getByTestId("chat-code-RESERVE_BREACH")).toBeVisible();
  await expect(first.getByTestId("chat-reply")).toContainText("¥28,326.92");
  // The plan is a checklist with a status per step, and nothing has run yet.
  await expect(first.getByTestId("chat-plan").locator("li").first()).toHaveAttribute("data-status", "DONE");
  await expect(first.getByTestId("chat-plan")).toContainText("Proposed");
  await expect(first.getByTestId("chat-ops")).toHaveCount(0);
  await expect(first.getByTestId("chat-awaiting")).toContainText("Nothing has run yet");
  // The confirmation stays at level 1 while the plan waits behind Details.
  await expect(first.getByTestId("chat-awaiting")).toBeVisible();
  await expect(first.getByTestId("chat-plan")).toBeHidden();

  await first.getByTestId("chat-goahead").click();
  await expect(turns(page)).toHaveCount(2);
  const second = turns(page).nth(1);
  await expect(second.getByTestId("chat-intent")).toHaveText("Negotiate");
  const ops = second.getByTestId("chat-ops");
  // The trace sits behind the Details disclosure: closed until the reader opens it.
  await expect(second.getByTestId("chat-details")).not.toHaveAttribute("open", "");
  await expect(ops).toBeHidden();
  await second.getByTestId("chat-details").locator("summary").first().click();
  await expect(ops).toBeVisible();
  await expect(ops.locator('[data-status="EXECUTED"]')).toHaveCount(4);
  await expect(second.getByTestId("chat-op-ACCEPT_OFFER")).toContainText("Executed");
  await expect(second.getByTestId("chat-op-ACCEPT_OFFER")).toContainText("Tier 1");
  await expect(second.getByTestId("chat-op-ACCEPT_OFFER")).toContainText(/seq \d+/);
  await expect(second.getByTestId("chat-negotiation")).toContainText("Option A");
  // The confirmation buttons on the answered turn are history now.
  await expect(turns(page).first().getByTestId("chat-goahead")).toBeDisabled();
});

test("details are closed on a plain reply and open when the turn has a security event or a refused operation", async ({ page, request }) => {
  await resetBooks(request);
  await page.goto("/chat");
  await signIn(page);

  await send(page, "status");
  const plain = turns(page).nth(0);
  await expect(plain.getByTestId("chat-reply")).toBeVisible();
  await expect(plain.getByTestId("chat-details")).not.toHaveAttribute("open", "");
  await expect(plain.getByTestId("chat-intent")).toBeHidden();

  // A Tier-3 request is refused and logged as a security event: the trace is open without a click.
  await send(page, "Sign a personal guarantee for the bank loan");
  const refused = turns(page).nth(1);
  await expect(refused.getByTestId("chat-op-SIGN_PERSONAL_GUARANTEE")).toContainText("Refused");
  await expect(refused.getByTestId("chat-details")).toHaveAttribute("open", "");
  await expect(refused.getByTestId("chat-security")).toBeVisible();
  await expect(refused.getByTestId("chat-ops")).toBeVisible();
  await expect(refused.getByTestId("chat-nothing-executed")).toHaveCount(0);
});

test("buyer: the FastCapital message gets only the refusal reply, no verdict, and sends no credential", async ({ page, request }) => {
  await resetBooks(request);
  await demoMode(page);
  const sent: (string | undefined)[] = [];
  page.on("request", (r) => {
    if (r.url() === `${API}/nl` && r.method() === "POST") sent.push(r.headers()["x-owner-token"]);
  });
  await page.goto("/chat");
  await signIn(page); // signed in as owner on purpose: a buyer turn must still carry no token

  await page.getByRole("radio", { name: "Buyer (counterparty)" }).check();
  await page.getByTestId("chat-counterparty").selectOption("FASTCAPITAL");
  await page.getByTestId("prompt-fastcapital").click();

  // A buyer never sees the verdict: the reply is a refusal and nothing else.
  const turn = turns(page).last();
  await expect(turn.getByTestId("chat-intent")).toHaveText("Buyer message");
  await expect(turn.getByTestId("chat-reply")).toContainText("We are not able to share internal financial, facility or counterparty information.");
  await expect(turn.getByTestId("chat-reply")).not.toContainText("300,000");
  await expect(turn.getByTestId("chat-verdict")).toHaveCount(0);
  await expect(turn.getByTestId("chat-outcome")).toHaveCount(0);
  await expect(turn.locator('[data-testid^="chat-code-"]')).toHaveCount(0);
  await expect(turn.getByTestId("chat-security")).toHaveCount(0);
  await expect(turn.getByTestId("chat-ops")).toHaveCount(0);

  if (isLive()) {
    expect(sent.length).toBeGreaterThan(0);
    expect(sent.every((t) => t === undefined)).toBe(true);
  }
});

test("clarification: options are buttons, and the chosen one is sent", async ({ page, request }) => {
  await resetBooks(request);
  await page.goto("/chat");
  await signIn(page);

  await send(page, "help me sort out our cash");
  const ask = turns(page).nth(0);
  await expect(ask.getByTestId("chat-intent")).toHaveText("Needs clarification");
  const options = ask.getByTestId("chat-clarify").getByRole("button");
  await expect(options).toHaveText(["show cash status", "fund the projected gap", "get an invoice paid early"]);

  await options.first().click();
  await expect(turns(page)).toHaveCount(2);
  const answer = turns(page).nth(1);
  await expect(answer.getByTestId("chat-intent")).toHaveText("Status");
  await expect(answer.getByTestId("chat-reply")).toContainText("Reserve floor");
  // The chosen option shows as the user's message, and the old question can no longer be answered.
  await expect(page.getByTestId("chat-log")).toContainText("show cash status");
  await expect(ask.getByTestId("chat-clarify").getByRole("button").first()).toBeDisabled();
});

test("correction: 'actually make it 0.8%' amends the pending plan and is marked corrected", async ({ page, request }) => {
  await resetBooks(request);
  await demoMode(page);
  await page.goto("/chat");
  await signIn(page);

  await page.getByTestId("prompt-goal").click();
  const plan = turns(page).nth(0);
  await expect(plan.getByTestId("chat-reply")).toContainText("0.85%");
  await expect(plan.getByTestId("chat-corrected")).toHaveCount(0);

  await page.getByTestId("prompt-amend").click();
  await expect(turns(page)).toHaveCount(2);
  const amended = turns(page).nth(1);
  await expect(amended.getByTestId("chat-corrected")).toHaveText("Corrected");
  await expect(amended.getByTestId("chat-reply")).toContainText("0.80%");
  await expect(amended.getByTestId("chat-awaiting")).toBeVisible();
  await expect(amended.getByTestId("chat-ops")).toHaveCount(0);
});

test("a 401 opens the owner sign-in dialog, and signing in resends the refused message", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByTestId("chat-signed-out")).toBeVisible();

  await send(page, "status");
  const dialog = page.getByRole("dialog", { name: "Owner sign-in" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("status")).toContainText("owner token");
  await expect(page.getByTestId("chat-log").getByRole("alert")).toContainText(/sign-in required|401/i);

  if (isLive()) {
    // The real API refuses a wrong token and the dialog says so without closing.
    await dialog.getByLabel("Owner token").fill("not-the-token");
    await dialog.getByRole("button", { name: "Sign in" }).click();
    await expect(dialog.getByRole("alert")).toContainText("rejected");
    await expect(dialog).toBeVisible();
  }

  await dialog.getByLabel("Owner token").fill(DEMO_TOKEN);
  await dialog.getByRole("button", { name: "Sign in" }).click();
  await expect(dialog).toBeHidden();
  // The turn that was refused ran again with the token: no retyping.
  await expect(turns(page)).toHaveCount(1);
  await expect(turns(page).last().getByTestId("chat-intent")).toHaveText("Status");
  await expect(page.getByTestId("chat-signed-out")).toHaveCount(0);

  // The token is kept for this tab only (sessionStorage), and signing out removes it.
  expect(await page.evaluate(() => window.sessionStorage.getItem("tl-owner-auth"))).toContain(DEMO_TOKEN);
  expect(await page.evaluate(() => window.localStorage.getItem("tl-owner-auth"))).toBeNull();
  await openAccountMenu(page);
  await page.getByTestId("owner-signout").click();
  await expect(page.getByTestId("owner-signin-open")).toBeVisible();
  expect(await page.evaluate(() => window.sessionStorage.getItem("tl-owner-auth"))).not.toContain(DEMO_TOKEN);
});

test("the slide-over chat opens from another page, keeps the conversation, and closes with Escape", async ({ page, request }) => {
  await resetBooks(request);
  await page.goto("/mandate");
  const signin = page.getByRole("dialog", { name: "Owner sign-in" });
  // Live: the Mandate screen's own requests get a 401 and open the dialog by themselves. Mock: the user opens it.
  if (isLive()) await expect(signin).toBeVisible();
  else await page.getByTestId("owner-signin-open").click();
  await signin.getByLabel("Owner token").fill(DEMO_TOKEN);
  await signin.getByRole("button", { name: "Sign in" }).click();
  await expect(signin).toBeHidden();

  await page.getByTestId("chat-open").click();
  const panel = page.getByRole("dialog", { name: "Chat with the agent" });
  await expect(panel).toBeVisible();
  await panel.getByRole("textbox", { name: "Message" }).fill("status");
  await panel.getByTestId("chat-send").click();
  await expect(panel.getByTestId("chat-turn").last().getByTestId("chat-intent")).toHaveText("Status");

  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  await expect(page.getByTestId("chat-open")).toBeFocused();

  // Same conversation on the full page.
  await page.getByRole("link", { name: "Chat", exact: true }).click();
  await expect(page).toHaveURL(/\/chat/);
  await expect(turns(page)).toHaveCount(1);
  await expect(page.getByTestId("chat-open")).toHaveCount(0);

  await page.getByTestId("chat-new").click();
  await expect(turns(page)).toHaveCount(0);
});

test("the Chinese UI offers Chinese prompts and gets a Chinese answer", async ({ page, request }) => {
  await resetBooks(request);
  await demoMode(page);
  await page.goto("/chat");
  await signIn(page);
  await openAccountMenu(page);
  await page.getByLabel("中文").check();
  await page.getByTestId("prompt-evaluate").click();
  const turn = turns(page).last();
  await expect(turn.getByTestId("chat-intent")).toHaveText("评估报价");
  await expect(turn.getByTestId("chat-outcome")).toContainText("拒绝");
  await expect(turn.getByTestId("chat-goahead")).toHaveText("执行");
});

test("network and credential failures are explained in the conversation and can be retried", async ({ page, request }) => {
  test.skip(!isLive(), "needs real network requests to intercept");
  await resetBooks(request);
  await page.goto("/chat");
  await signIn(page);

  // Offline once: the error bubble offers Retry, which resends the same request.
  let calls = 0;
  await page.route(`${API}/nl`, (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    calls += 1;
    return calls === 1 ? route.abort() : route.continue();
  });
  await send(page, "status");
  await expect(page.getByTestId("chat-log").getByRole("alert")).toContainText("Cannot reach the API");
  await page.getByTestId("chat-retry").click();
  await expect(turns(page).last().getByTestId("chat-intent")).toHaveText("Status");
  await expect(page.getByTestId("chat-log").getByRole("alert")).toHaveCount(0);
  await page.unroute(`${API}/nl`);

  // A server with no credentials configured answers 503.
  await page.route(`${API}/nl`, (route) =>
    route.request().method() === "OPTIONS"
      ? route.continue()
      : route.fulfill({
          status: 503,
          contentType: "application/json",
          headers: { "access-control-allow-origin": `http://localhost:${process.env.E2E_LIVE_PORT ?? 3000}` },
          body: JSON.stringify({ detail: { code: "OWNER_TOKEN_NOT_CONFIGURED", message: "set OWNER_TOKEN (DEMO_MODE=0)" } }),
        }),
  );
  await send(page, "status again");
  await expect(page.getByTestId("chat-log").getByRole("alert").last()).toContainText("Server credentials not configured");
});

test("the chat button says Ask FLOW, and a Business page offers only the questions it can answer", async ({ page, request }) => {
  await resetBooks(request);
  await asOwner(page);
  await page.goto("/deals");

  const open = page.getByTestId("chat-open");
  await expect(open).toContainText("Ask FLOW");
  await expect(open).not.toContainText("Ask the agent");
  await open.click();
  const panel = page.getByRole("dialog", { name: "Chat with the agent" });
  const chips = panel.locator('[data-testid^="prompt-"]');
  // No deal has been evaluated on this page, so the questions about one are hidden rather than shown to fail.
  await expect(panel.getByTestId("prompt-page-waiting")).toHaveText("What are we waiting for?");
  await expect(chips).toHaveCount(1);
  await page.keyboard.press("Escape");

  // Another page, other questions: Receivables asks what is overdue (who to chase appears only when something is).
  await page.goto("/receivables");
  await page.getByTestId("chat-open").click();
  await expect(page.getByRole("dialog", { name: "Chat with the agent" }).getByTestId("prompt-page-overdue")).toHaveText("What is overdue?");
  await page.keyboard.press("Escape");

  // Home: what changed and what needs attention.
  await page.goto("/");
  await page.getByTestId("chat-open").click();
  const home = page.getByRole("dialog", { name: "Chat with the agent" });
  await expect(home.getByTestId("prompt-page-changed")).toHaveText("What changed today?");
  await expect(home.getByTestId("prompt-page-attention")).toHaveText("What needs my attention?");
});

test("Business chat is the owner's alone: no role switch, no Tier 1 hint, no fixture or approve-it chips", async ({ page, request }) => {
  await resetBooks(request);
  await asOwner(page);
  for (const route of ["/chat", "/"]) {
    await page.goto(route);
    if (route !== "/chat") await page.getByTestId("chat-open").click();
    const scope = route === "/chat" ? page.locator("main") : page.getByRole("dialog", { name: "Chat with the agent" });
    await expect(scope.getByTestId("chat-send")).toBeVisible();
    await expect(page.getByRole("radio", { name: "Buyer (counterparty)" })).toHaveCount(0);
    await expect(page.getByRole("radio", { name: "Owner", exact: true })).toHaveCount(0);
    await expect(page.getByTestId("chat-counterparty")).toHaveCount(0);
    await expect(page.locator("body")).not.toContainText("Owner channel. Tier 1 actions");
    for (const demoOnly of ["prompt-evaluate", "prompt-amend", "prompt-approve", "prompt-fund", "prompt-goal", "prompt-vague"]) {
      await expect(page.getByTestId(demoOnly)).toHaveCount(0);
    }
    expect(await scope.locator('[data-testid^="prompt-"]').count()).toBeLessThanOrEqual(4);
  }
  // Demo mode is where the buyer role-play and the general prompts live.
  await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "demo" })));
  await page.goto("/chat");
  await expect(page.getByRole("radio", { name: "Buyer (counterparty)" })).toBeVisible();
  await expect(page.getByTestId("prompt-evaluate")).toBeVisible();
});

test("the Deals question about the deal explains the verdict the page evaluated, and the panel says what it is discussing", async ({ page, request }) => {
  await resetBooks(request);
  await asOwner(page);
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Counter recommended");

  await page.getByTestId("chat-open").click();
  const panel = page.getByRole("dialog", { name: "Chat with the agent" });
  // The page holds an evaluated deal with counters, so all four Deals questions are offered.
  await expect(panel.locator('[data-testid^="prompt-"]')).toHaveText([
    "Why are we countering this?",
    "What if I accept their original terms?",
    "Why is Option A cheaper?",
    "What are we waiting for?",
  ]);
  await expect(panel.getByTestId("chat-discussing")).toHaveCount(0); // nothing asked yet, nothing used yet

  // The chat never evaluated anything: the answer is about the page's deal, named, with the server's own figures.
  await panel.getByTestId("prompt-page-counter").click();
  const why = panel.getByTestId("chat-turn").last();
  await expect(why.getByTestId("chat-reply")).toContainText("About the Foshan Home Retail Co. offer evaluated today:");
  await expect(why.getByTestId("chat-reply")).not.toContainText("no verdict to explain");
  await expect(why.getByTestId("chat-outcome")).toContainText("REJECT");
  await expect(panel.getByTestId("chat-discussing")).toHaveText("Discussing: the Foshan Home Retail Co. offer");

  await panel.getByTestId("prompt-page-original").click();
  const original = panel.getByTestId("chat-turn").last();
  await expect(original.getByTestId("chat-reply")).toContainText("FLOW would not accept their original terms as written.");
  await expect(original.getByTestId("chat-reply")).toContainText("¥28,326.92");
  await expect(original.getByTestId("chat-reply")).toContainText("Nothing has been accepted or sent.");
  await expect(original.getByTestId("chat-ops")).toHaveCount(0);

  await panel.getByTestId("prompt-page-option").click();
  const option = panel.getByTestId("chat-turn").last();
  await expect(option.getByTestId("chat-reply")).toContainText("Option A:");
  await expect(option.getByTestId("chat-reply")).toContainText("¥3,027.77");
});

test("Home's 'What changed today?' is a read of the books, not a list of what the agent can do", async ({ page, request }) => {
  await resetBooks(request);
  await asOwner(page);
  await page.goto("/");
  await page.getByTestId("chat-open").click();
  const panel = page.getByRole("dialog", { name: "Chat with the agent" });
  await panel.getByTestId("prompt-page-changed").click();
  const turn = panel.getByTestId("chat-turn").last();
  await expect(turn.getByTestId("chat-reply")).toContainText("Nothing has changed today; the forecast is unchanged:");
  await expect(turn.getByTestId("chat-reply")).not.toContainText("I can't do that");
  await expect(turn.getByTestId("chat-ops")).toHaveCount(0);
});

test("a refresh keeps the draft and the conversation, and a pending plan points to the Approvals page", async ({ page, request }) => {
  await resetBooks(request);
  await asOwner(page);
  await page.goto("/chat");
  await send(page, "Evaluate EX01");
  await expect(turns(page).first().getByTestId("chat-awaiting")).toBeVisible();
  const session = await page.evaluate(() => JSON.parse(sessionStorage.getItem("tl-chat-session") ?? "{}").convs?.OWNER?.sessionId as string | null);
  expect(session).toBeTruthy();

  await page.getByRole("textbox", { name: "Message" }).fill("what is the reserve fl");
  expect(await page.evaluate(() => sessionStorage.getItem("tl-chat-draft"))).toContain("what is the reserve fl");

  await page.reload();
  // The half-typed question is back, and so is the conversation, as history: the old buttons are gone.
  await expect(page.getByRole("textbox", { name: "Message" })).toHaveValue("what is the reserve fl");
  await expect(turns(page)).toHaveCount(1);
  await expect(turns(page).first().getByTestId("chat-reply")).toContainText("REJECT");
  await expect(turns(page).first().getByTestId("chat-goahead")).toHaveCount(0);
  await expect(turns(page).first().getByTestId("chat-restored-pending")).toContainText("Your pending approvals are on the Approvals page.");
  await expect(turns(page).first().getByRole("link", { name: "Open Approvals" })).toHaveAttribute("href", "/approvals");

  // The same server session continues: the next turn keeps the id (and, live, the server still remembers the pending plan).
  await page.getByRole("textbox", { name: "Message" }).fill("status");
  await page.getByTestId("chat-send").click();
  await expect(turns(page)).toHaveCount(2);
  expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem("tl-chat-session") ?? "{}").convs?.OWNER?.sessionId)).toBe(session);
  expect(await page.evaluate(() => sessionStorage.getItem("tl-chat-draft"))).not.toContain("reserve");
  if (isLive()) {
    await send(page, "go ahead");
    await expect(turns(page).last().getByTestId("chat-intent")).toHaveText("Negotiate");
  }

  // Signing out takes the conversation and the draft out of the browser with the token.
  await page.getByRole("textbox", { name: "Message" }).fill("a private note");
  await openAccountMenu(page);
  await page.getByTestId("owner-signout").click();
  await expect(page.getByTestId("owner-signin-open")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Message" })).toHaveValue("");
  await expect(turns(page)).toHaveCount(0);
});
