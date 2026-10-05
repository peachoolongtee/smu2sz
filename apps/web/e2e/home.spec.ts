import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

/**
 * The Business home (`/`) in mock mode: one server read (GET /home) answers "am I safe", "what should I do", "what does it
 * cost", "what needs me", "what changed" and "who has not paid". The mock replays summaries recorded from the real API on the
 * demo path (the opening books, the quiet books after the deal, day 34 with the late invoice, the queued fix, the approved fix),
 * so every sentence and amount here is a server string. The clock is a Demo-mode control, on the story page.
 */

test.beforeEach(async ({ context }, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded demo path (the live equivalent is in live.spec.ts)");
  await context.addInitScript(() => {
    try {
      sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: "mock-owner" }));
    } catch {
      /* storage unavailable */
    }
  });
});

/** The story page's clock moves the simulated day; the home is then opened through the mode switch. */
async function advanceTo34(page: Page) {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
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

test("the Business home answers safe, do and cost on the opening books, without a demo control", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "ACTION_NEEDED");
  await expect(page.getByTestId("home-status-word")).toHaveText("Action needed");
  await expect(page.getByTestId("home-headline")).toHaveText("Cash falls ¥240,000.00 below your ¥300,000.00 safe level on day 12 (in 12 days).");
  await expect(page.getByTestId("home-note")).toContainText("can run it alone");
  await expect(page.getByTestId("home-cash")).toHaveText("¥400,000.00");
  await expect(page.getByTestId("home-lowest")).toHaveText("−¥105,000.00");
  // The best next action: what, how much, cost, when, who decides, what if nothing, after.
  const action = page.getByTestId("home-next-action");
  await expect(action.getByTestId("next-action-title")).toContainText("Draw ¥150,000.00 on Bank credit line and finance ¥336,000.00 of the ¥420,000.00 invoice to Foshan Home Retail Co.");
  await expect(action).toContainText("¥486,000.00");
  await expect(action).toContainText("¥2,994.08");
  await expect(action).toContainText("11.2% a year for 29 days");
  await expect(action).toContainText("Day 3");
  await expect(action).toContainText("The agent can do this alone");
  await expect(action.getByTestId("next-action-if-nothing")).toContainText("¥240,000.00 below your safe level on day 12");
  await expect(action.getByTestId("next-action-after")).toContainText("Cash stays above your safe level through day 31");
  await expect(page.getByTestId("fix-ALERT-RESERVE-12")).toHaveText("Go ahead");
  // Nothing from the demo on the owner's screen: no stepper, no clock, no mock pill, no engine navigation.
  await expect(page.getByRole("region", { name: "Guided demo" })).toHaveCount(0);
  await expect(page.getByTestId("home-advance")).toHaveCount(0);
  await expect(page.getByText("Mock data")).toHaveCount(0);
  await expect(page.getByRole("navigation").getByRole("link", { name: "Trajectory" })).toHaveCount(0);
  await expect(page.getByTestId("home-waiting-empty")).toBeVisible();
  await expect(page.getByTestId("home-next-receipt")).toContainText("¥420,000.00 from Foshan Home Retail Co. on day 32");
});

test("Go ahead on the opening books runs the fix alone, and the home turns calm with the advance on its way", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("fix-ALERT-RESERVE-12").click();
  const result = page.getByTestId("fix-result");
  await expect(result).toContainText("2 executed");
  await expect(result).toContainText("The alert is cleared.");
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  await expect(page.getByTestId("home-headline")).toHaveText("Cash stays above your ¥300,000.00 safe level for the next 120 days.");
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  await expect(page.getByTestId("home-in-transit")).toContainText("¥336,000.00 on its way");
  await expect(page.getByTestId("home-changes-list")).toContainText("Bank credit line");
  await expect(page.getByTestId("home-waiting-empty")).toBeVisible();
});

test("day 34: the fix needs approval; queuing it from the home runs nothing and the home says it waits", async ({ page }) => {
  await advanceTo34(page);
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "ACTION_NEEDED");
  await expect(page.getByTestId("home-headline")).toHaveText("Cash falls ¥200,000.00 below your ¥300,000.00 safe level on day 42 (in 8 days).");
  await expect(page.getByTestId("home-note")).toContainText("needs your approval because of its cost");
  const action = page.getByTestId("home-next-action");
  await expect(action.getByTestId("next-action-title")).toContainText("Finance ¥200,000.00 of the ¥420,000.00 invoice to Foshan Home Retail Co.");
  await expect(action).toContainText("¥1,782.19");
  await expect(action).toContainText("32.5% a year for 10 days");
  await expect(action).toContainText("Day 37");
  await expect(action.getByTestId("next-action-needs-owner")).toContainText("above your 15.00% limit");
  await expect(action.getByTestId("next-action-after")).toContainText("through day 46");
  // Who has not paid: the late buyer by name, with the days late.
  await expect(page.getByTestId("home-late-RCV-A")).toContainText("Foshan Home Retail Co.");
  await expect(page.getByTestId("home-late-RCV-A")).toContainText("2 day(s) late");
  await expect(page.getByTestId("home-change-LATE")).toContainText("was due on day 32");

  const button = page.getByTestId("fix-ALERT-RESERVE-42");
  await expect(button).toHaveText("Queue it for my approval");
  await button.click();
  const op = page.getByTestId("fix-result").getByTestId("chat-op-SUBMIT_INVOICE_FOR_FINANCING");
  await expectWaitingNotSuccess(op);
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toContainText("Waiting for your approval (APR-000001)");
  await expect(page.getByTestId("fix-ALERT-RESERVE-42")).toHaveCount(0);
  // Needs your decision: the question, the cost and the landing day, and a link to the card.
  const decision = page.getByTestId("home-approval-APR-000001");
  await expect(decision).toContainText("Approve ¥200,000.00 of invoice financing?");
  await expect(decision).toContainText("Cost ¥1,782.19");
  await expect(decision).toContainText("lands day 37");
  await expect(page.getByTestId("home-change-WAITING")).toBeVisible();
  await expect(page.getByTestId("home-in-transit")).toHaveCount(0);
});

test("day 34: the approval card is a question with the cost, the landing day and the after-state; approving clears the home", async ({ page }) => {
  await advanceTo34(page);
  await page.getByTestId("fix-ALERT-RESERVE-42").click();
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await expect(page).toHaveURL(/\/approvals#approval-APR-000001/);
  const card = page.locator("#approval-APR-000001");
  await expect(card.getByTestId("approval-headline")).toHaveText("Approve ¥200,000.00 of invoice financing?");
  await expect(card).toContainText("Finance ¥200,000.00 of the ¥420,000.00 invoice to Foshan Home Retail Co.");
  await expect(card.getByTestId("approval-cost")).toContainText("¥1,782.19");
  await expect(card.getByTestId("approval-lands")).toHaveText("Day 37");
  await expect(card.getByTestId("approval-reason")).toContainText("32.52%");
  await expect(card.getByTestId("approval-after")).toContainText("through day 46");
  await expect(card).toContainText("If you decline");
  // The ids and the tier are audit details, closed by default.
  await expect(card.getByTestId("approval-detail-APR-000001")).toHaveCount(0);
  await card.getByTestId("approval-toggle-APR-000001").click();
  await expect(card.getByTestId("approval-detail-APR-000001")).toContainText("Tier 2");
  await expect(card.getByTestId("approval-detail-APR-000001")).toContainText("alert:ALERT-RESERVE-42:v7:0");

  await card.getByRole("button", { name: "Approve" }).click();
  await expect(card.getByTestId("approval-result-APR-000001")).toContainText("the cash lands on day 37");
  await expect(card).toContainText("Approved");
  await expect(card.getByTestId("approval-decided-APR-000001")).toHaveText("Decided on day 34.");

  await page.getByRole("navigation").getByRole("link", { name: "Home", exact: true }).first().click();
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  await expect(page.getByTestId("home-in-transit")).toContainText("¥200,000.00 on its way");
  await expect(page.getByTestId("home-waiting-empty")).toBeVisible();
  await expect(page.getByTestId("home-changes-list")).toContainText("lands on day 37");
});

test("the Chinese labels switch while the server's sentences stay", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("中文").check();
  await expect(page.getByTestId("home-status-word")).toHaveText("需要行动");
  await expect(page.getByRole("navigation").getByRole("link", { name: "现金与融资" })).toBeVisible();
  await page.getByLabel("English").check();
  await expect(page.getByTestId("home-status-word")).toHaveText("Action needed");
});
