import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

/**
 * The owner home (`/`) in mock mode: eight sections (the deal and documents cards are in documents.spec.ts), the agent's opener after the clock reaches day 34, and the day-34 cure,
 * which is above the yearly cost ceiling (¥1,782.19 for 10 days = 32.5% a year): "Let the agent fix this" and "Go ahead" only
 * QUEUE it (PENDING_APPROVAL, the alert stays open); the owner approves on the approval card (or "approve APR-…" in the chat);
 * only then does it execute, the cash lands on day 37 and the alert clears. The mock replays answers recorded from the real API
 * on the demo path (deal, receipt on day 2, clock to day 34), so every amount here is a server string.
 */

test.beforeEach(async ({ context }, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded demo path (the live equivalent is in live.spec.ts)");
  // Owner calls need a token; mock mode accepts any non-empty one (the sign-in dialog is covered by chat.spec.ts).
  await context.addInitScript(() => {
    try {
      sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: "mock-owner" }));
    } catch {
      /* storage unavailable */
    }
  });
});

async function advanceTo34(page: Page) {
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
}

/** The state pill of an operation row must carry the warning look, never the success look. */
async function expectWaitingNotSuccess(row: ReturnType<Page["getByTestId"]>) {
  await expect(row).toHaveAttribute("data-status", "PENDING_APPROVAL");
  const pill = row.getByTestId("op-state");
  await expect(pill).toHaveAttribute("data-state", "PENDING_APPROVAL");
  await expect(pill).toContainText("Waiting for your approval");
  await expect(pill.locator(":scope > span")).toHaveClass(/text-warn-fg/);
  await expect(pill.locator(":scope > span")).not.toHaveClass(/text-ok-fg/);
  await expect(row).not.toContainText("Executed");
  await expect(row.getByTestId("op-waiting")).toContainText("APR-000001");
}

test("home renders the eight sections and the day-0 opener has a warning but nothing to approve", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Home", level: 1 })).toBeVisible();
  for (const name of ["Today", "What needs you", "Position", "Your deals", "Documents the agent has read", "Waiting for you", "At risk", "Done by the agent"]) {
    await expect(page.getByRole("heading", { name, level: 2 })).toBeVisible();
  }
  await expect(page.getByTestId("home-day")).toHaveText("Day 0");
  await expect(page.getByText("Demo control")).toBeVisible();
  await expect(page.getByTestId("home-opener")).toHaveAttribute("data-news", "true");
  await expect(page.getByTestId("home-opener")).toContainText("Reserve headroom thin on day 30");
  await expect(page.getByTestId("home-goahead")).toHaveCount(0);
  // Position: server display strings only; nothing is in transit on the opening books.
  await expect(page.getByTestId("home-waiting-empty")).toBeVisible();
  const position = page.locator("#home-position");
  await expect(position.getByText("¥400,000.00")).toBeVisible();
  await expect(position.getByText("¥300,000.00").first()).toBeVisible();
  await expect(position.getByTestId("in-transit")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Home" }).first()).toBeVisible();
});

test("day 34: the alert says the cure needs approval before the click; Go ahead queues it and nothing runs", async ({ page }) => {
  await page.goto("/");
  await advanceTo34(page);

  const opener = page.getByTestId("home-opener");
  await expect(opener).toHaveAttribute("data-news", "true");
  await expect(opener).toContainText("Day 34");
  await expect(opener).toContainText("¥200,000.00");
  await expect(opener).toContainText("needs your approval");
  await expect(page.getByTestId("home-goahead")).toBeVisible();
  await expect(page.getByTestId("home-notnow")).toBeVisible();

  // Before any click: the cost, the rate and "needs your approval" are on the alert itself.
  const critical = page.getByTestId("home-alert-ALERT-RESERVE-42");
  await expect(critical).toHaveAttribute("data-severity", "CRITICAL");
  await expect(critical).toContainText("Cost ¥1,782.19");
  await expect(critical).toContainText("32.5% a year");
  await expect(critical.getByTestId("alert-needs-approval-ALERT-RESERVE-42")).toContainText("above your 15.00% yearly ceiling");
  await expect(critical.getByText("Needs your approval").first()).toBeVisible();
  await expect(page.getByTestId("fix-ALERT-RESERVE-42")).toBeVisible();

  await page.getByTestId("home-goahead").click();
  const op = page.getByTestId("home-answer").getByTestId("chat-op-SUBMIT_INVOICE_FOR_FINANCING");
  await expectWaitingNotSuccess(op);
  // The alert is still open and now says it is waiting for the owner, with a link to the card; the opener no longer offers to queue it again.
  await expect(page.getByTestId("home-alert-ALERT-RESERVE-42")).toBeVisible();
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toContainText("Waiting for your approval (APR-000001)");
  await expect(page.getByTestId("fix-ALERT-RESERVE-42")).toHaveCount(0);
  await expect(page.getByTestId("home-opener")).toContainText("already waiting for your approval (APR-000001)");
  await expect(page.getByTestId("home-goahead")).toHaveCount(0);
  // The ledger rows: the queued request is not an executed action.
  const done = page.getByTestId("home-done-SUBMIT_INVOICE_FOR_FINANCING");
  await expect(done).toHaveCount(1);
  await expect(done).toHaveAttribute("data-status", "PENDING_APPROVAL");
  // Position: the books have not changed, nothing is in transit.
  await expect(page.locator("#home-position").getByTestId("in-transit")).toHaveCount(0);
});

test("day 34: approving on the approval card runs the cure, shows when the cash lands, and clears the alert", async ({ page }) => {
  await page.goto("/");
  await advanceTo34(page);
  await page.getByTestId("fix-ALERT-RESERVE-42").click();
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toContainText("APR-000001");

  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await expect(page).toHaveURL(/\/approvals#approval-APR-000001/);
  const card = page.locator("#approval-APR-000001");
  await expect(card).toBeVisible();
  await expect(card).toContainText("¥200,000.00");
  await expect(card.getByTestId("approval-reason")).toContainText("32.52%");
  await card.getByRole("button", { name: "Approve" }).click();
  await expect(card.getByTestId("approval-result-APR-000001")).toContainText("the cash lands on day 37");
  await expect(card).toContainText("Approved");
  // The decision day is the API's `decided_day` (the cure was queued and approved on day 34).
  await expect(card.getByTestId("approval-decided-APR-000001")).toHaveText("Decided on day 34.");

  // Home again: the critical alert is gone, funding in transit says when it lands, and the ledger shows it executed.
  await page.getByRole("navigation").getByRole("link", { name: "Home", exact: true }).first().click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await expect(page.getByTestId("home-alert-ALERT-RESERVE-42")).toHaveCount(0);
  const transit = page.getByTestId("home-alert-ALERT-TRANSIT-alert:ALERT-RESERVE-42:v7:0");
  await expect(transit).toHaveAttribute("data-severity", "INFO");
  await expect(transit).toContainText("requested on day 34");
  await expect(transit).toContainText("lands on day 37");
  await expect(transit.getByRole("button")).toHaveCount(0);
  const position = page.locator("#home-position");
  await expect(position.getByTestId("in-transit-lot")).toContainText("¥200,000.00 lands on day 37");
  await expect(position.getByText("Cash in hand today")).toBeVisible();
  const executed = page.getByTestId("home-done-SUBMIT_INVOICE_FOR_FINANCING").and(page.locator('[data-status="EXECUTED"]'));
  await expect(executed).toContainText("the cash lands on day 37");
  await expect(page.getByTestId("home-waiting-empty")).toBeVisible();
});

test("the conversation also appears in the chat panel; typing 'approve APR-000001' runs the queued cure", async ({ page }) => {
  await page.goto("/");
  await advanceTo34(page);
  await expect(page.getByTestId("home-goahead")).toBeVisible();
  await page.getByTestId("home-goahead").click();
  await expect(page.getByTestId("home-answer")).toBeVisible();
  // Chat state lives in memory, so go there through the navigation (a full page load starts a new conversation).
  await page.getByRole("navigation").getByRole("link", { name: "Chat", exact: true }).first().click();
  await expect(page).toHaveURL(/\/chat/);
  const turns = page.getByTestId("chat-turn");
  await expect(turns.first()).toContainText("Go ahead?");
  // The answer to "go ahead" is in the same conversation: queued, not executed.
  await expectWaitingNotSuccess(turns.getByTestId("chat-op-SUBMIT_INVOICE_FOR_FINANCING").first());

  await page.getByRole("textbox", { name: "Message" }).fill("approve APR-000001");
  await page.getByTestId("chat-send").click();
  const executed = page.getByTestId("chat-turn").getByTestId("chat-op-SUBMIT_INVOICE_FOR_FINANCING").and(page.locator('[data-status="EXECUTED"]'));
  await expect(executed).toContainText("the cash lands on day 37");
});

test("Let the agent fix this queues the cure from the alerts page; the waiting alert links to the card; approval clears it", async ({ page }) => {
  await page.goto("/");
  await advanceTo34(page);

  // The alerts page: the button is on the actionable alert only, with the approval notice above it.
  await page.getByRole("link", { name: "Alerts", exact: true }).click();
  await expect(page).toHaveURL(/\/alerts/);
  await expect(page.getByRole("heading", { name: "Reserve breach ahead on day 42" })).toBeVisible();
  await expect(page.getByTestId("alert-needs-approval-ALERT-RESERVE-42")).toBeVisible();
  await expect(page.getByRole("button", { name: "Let the agent fix this" })).toHaveCount(1);

  await page.getByTestId("fix-ALERT-RESERVE-42").click();
  const result = page.getByTestId("fix-result");
  await expect(result).toContainText("0 executed");
  await expect(result).toContainText("1 waiting for approval");
  await expectWaitingNotSuccess(result.getByTestId("chat-op-SUBMIT_INVOICE_FOR_FINANCING"));
  await expect(result).not.toContainText("The alert is cleared.");
  await expect(page.getByTestId("alert-count-CRITICAL")).toContainText("1 Critical");
  await expect(page.getByTestId("fix-ALERT-RESERVE-42")).toHaveCount(0);
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toContainText("Waiting for your approval (APR-000001)");

  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await expect(page).toHaveURL(/\/approvals/);
  await page.locator("#approval-APR-000001").getByRole("button", { name: "Approve" }).click();
  await expect(page.locator("#approval-APR-000001")).toContainText("Approved");

  await page.getByRole("navigation").getByRole("link", { name: "Alerts", exact: true }).first().click();
  await expect(page.getByTestId("alert-count-CRITICAL")).toContainText("0 Critical");
  await expect(page.getByTestId("alert-count-INFO")).toContainText("1 Info");
  const transit = page.locator("#alert-ALERT-TRANSIT-alert\\:ALERT-RESERVE-42\\:v7\\:0");
  await expect(transit).toContainText("lands on day 37");
  await expect(transit).toContainText("Funding in transit");
  await expect(transit.getByRole("button")).toHaveCount(0);
});

test("funding in transit shows after the day-0 plan: cash in hand and the advance's landing day are kept apart", async ({ page }) => {
  await page.goto("/chat");
  await page.getByTestId("prompt-fund").click();
  const first = page.getByTestId("chat-turn").first();
  // "Fund the cash gap" only proposes: each action carries the day the cash lands, and nothing has run.
  await expect(first.getByTestId("chat-reply")).toContainText("lands on day 3");
  await expect(first.getByTestId("chat-ops")).toHaveCount(0);
  await first.getByTestId("chat-goahead").click();
  const second = page.getByTestId("chat-turn").nth(1);
  await expect(second.getByTestId("chat-reply")).toContainText("Cash in now");
  await expect(second.getByTestId("chat-reply")).toContainText("Still to land");
  await expect(second.getByTestId("chat-reply")).toContainText("¥255,000.00 on FAC-IF");
  await expect(second.getByTestId("chat-op-SUBMIT_INVOICE_FOR_FINANCING")).toContainText("the cash lands on day 3");

  await page.getByRole("navigation").getByRole("link", { name: "Home", exact: true }).first().click();
  const position = page.locator("#home-position");
  await expect(position.getByText("Cash in hand today")).toBeVisible();
  await expect(position.getByText("¥550,000.00")).toBeVisible();
  await expect(position.getByTestId("in-transit-lot")).toContainText("¥255,000.00 lands on day 3");
  await expect(position.getByTestId("in-transit-lot")).toContainText("requested on day 0");
});
