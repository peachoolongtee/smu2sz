import { expect, test, type Page } from "@playwright/test";
import { DEMO_TOKEN } from "./fixtures";
import { resetBooks } from "./helpers";

/**
 * /chat (POST /nl). Runs in both projects: mock replays replies recorded from the real API, live calls the
 * API. These specs import `test` from @playwright/test (not ./fixtures) because they sign in themselves,
 * through the dialog, exactly as a user would.
 */

const API = "http://localhost:8000";
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
  await expect(first.getByTestId("chat-reply")).toContainText("¥26,455.62");
  // The plan is a checklist with a status per step, and nothing has run yet.
  await expect(first.getByTestId("chat-plan").locator("li").first()).toHaveAttribute("data-status", "DONE");
  await expect(first.getByTestId("chat-plan")).toContainText("Proposed");
  await expect(first.getByTestId("chat-ops")).toHaveCount(0);
  await expect(first.getByTestId("chat-awaiting")).toContainText("Nothing has run yet");

  await first.getByTestId("chat-goahead").click();
  await expect(turns(page)).toHaveCount(2);
  const second = turns(page).nth(1);
  await expect(second.getByTestId("chat-intent")).toHaveText("Negotiate");
  const ops = second.getByTestId("chat-ops");
  await expect(ops).toBeVisible();
  await expect(ops.locator('[data-status="EXECUTED"]')).toHaveCount(4);
  await expect(second.getByTestId("chat-op-ACCEPT_OFFER")).toContainText("Executed");
  await expect(second.getByTestId("chat-op-ACCEPT_OFFER")).toContainText("Tier 1");
  await expect(second.getByTestId("chat-op-ACCEPT_OFFER")).toContainText(/seq \d+/);
  await expect(second.getByTestId("chat-negotiation")).toContainText("Option A");
  // The confirmation buttons on the answered turn are history now.
  await expect(turns(page).first().getByTestId("chat-goahead")).toBeDisabled();
});

test("buyer: the FastCapital message gives three security codes, executes nothing and sends no credential", async ({ page, request }) => {
  await resetBooks(request);
  const sent: (string | undefined)[] = [];
  page.on("request", (r) => {
    if (r.url() === `${API}/nl` && r.method() === "POST") sent.push(r.headers()["x-owner-token"]);
  });
  await page.goto("/chat");
  await signIn(page); // signed in as owner on purpose: a buyer turn must still carry no token

  await page.getByRole("radio", { name: "Buyer (counterparty)" }).check();
  await page.getByTestId("chat-counterparty").selectOption("FASTCAPITAL");
  await page.getByTestId("prompt-fastcapital").click();

  const turn = turns(page).last();
  await expect(turn.getByTestId("chat-intent")).toHaveText("Buyer message");
  await expect(turn.getByTestId("chat-outcome")).toContainText("REJECT");
  await expect(turn.locator('[data-testid^="chat-code-"]')).toHaveCount(3);
  for (const code of ["UNKNOWN_COUNTERPARTY", "UNEVIDENCED_PRIOR_CONCESSION", "DATA_EXTRACTION_REFUSED"]) {
    await expect(turn.getByTestId(`chat-code-${code}`)).toBeVisible();
  }
  await expect(turn.getByTestId("chat-security")).toContainText(/\d+ security events logged/);
  await expect(turn.getByTestId("chat-nothing-executed")).toBeVisible();
  await expect(turn.getByTestId("chat-ops")).toHaveCount(0);
  await expect(turn.getByTestId("chat-reply")).not.toContainText("300,000");

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
  await page.goto("/chat");
  await signIn(page);
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
          headers: { "access-control-allow-origin": "http://localhost:3000" },
          body: JSON.stringify({ detail: { code: "OWNER_TOKEN_NOT_CONFIGURED", message: "set OWNER_TOKEN (DEMO_MODE=0)" } }),
        }),
  );
  await send(page, "status again");
  await expect(page.getByTestId("chat-log").getByRole("alert").last()).toContainText("Server credentials not configured");
});
