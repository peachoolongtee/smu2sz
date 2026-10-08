import type { Page } from "@playwright/test";
import { expect, proseOf, test } from "./fixtures";
import { runPlan } from "./helpers";

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


/** The Business header keeps the language switch and sign-out inside the account menu; open it when it is there. */
async function openAccountMenu(page: Page) {
  const menu = page.getByTestId("account-menu");
  if ((await menu.count()) && !(await menu.evaluate((el) => (el as HTMLDetailsElement).open))) await menu.locator("> summary").click();
}

/** The story page's clock moves the simulated day; the home is then opened through the mode switch. */
async function advanceTo34(page: Page) {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
}

test("the Business home answers safe, do and cost on the opening books, without a demo control", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "ACTION_NEEDED");
  await expect(page.getByTestId("home-status-word")).toHaveText("Action needed");
  // Business words: the reserve, days as distances from today, authority as the owner's signed limits; no "Day N" anywhere.
  // Conclusion first, then the detail, the worst point and what is driving it; figures in overview precision.
  await expect(page.getByTestId("home-headline")).toHaveText("Your cash reserve becomes unsafe in 12 days.");
  await expect(page.getByTestId("home-note")).toHaveText("Cash falls to ¥60k, ¥240k below your ¥300k minimum cash reserve.");
  await expect(page.getByTestId("home-worst")).toHaveText("Worst point: −¥105k in 30 days if you do nothing.");
  await expect(page.getByTestId("home-drivers")).toContainText("Payroll of ¥340k falls due in 12 days.");
  await expect(page.getByTestId("home-breach-cash")).toHaveText("¥60k");
  await expect(page.getByTestId("home-lowest-when")).toHaveText("in 30 days");
  await expect(page.getByTestId("demo-data-indicator")).toHaveCount(1);
  // One product in the header, Approvals as an attention badge (absent while nothing waits), one account menu.
  await expect(page.getByRole("banner").getByRole("link", { name: /FLOW/ })).toBeVisible();
  await expect(page.getByRole("banner")).not.toContainText("Terms Guard");
  await expect(page.getByTestId("approvals-badge")).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Approvals" })).toHaveCount(0);
  await expect(page.getByTestId("account-menu")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
  await expect(page.getByTestId("home-cash")).toHaveText("¥400k");
  await expect(page.getByTestId("home-lowest")).toHaveText("−¥105k");
  // The hero: today's cash large, three tiles (the reserve, the first breach, the worst point), the "why" folded.
  await expect(page.getByTestId("home-status").locator("dl").first().locator("dt")).toHaveText(["Minimum cash reserve", "Cash at first breach", "Worst point"]);
  await expect(page.getByTestId("home-why")).not.toHaveAttribute("open", "");
  await expect(page.getByTestId("home-worst")).toBeHidden();
  await page.getByTestId("home-why").locator("> summary").click();
  await expect(page.getByTestId("home-worst")).toBeVisible();
  await expect(page.getByTestId("home-drivers")).toBeVisible();
  // The best next action: what, how much, cost, when, who decides, what if nothing, after.
  const action = page.getByTestId("home-next-action");
  // The recommendation is the router's cheapest runnable plan, priced all-in (every leg, the basis in words): the
  // same figure the Cash & funding options, the chat and the documents quote.
  await expect(action.getByTestId("next-action-title")).toHaveText("Secure ¥405k of funding");
  await expect(action.getByTestId("next-action-components")).toContainText("¥150k");
  await expect(action.getByTestId("next-action-components")).toContainText("¥255k");
  await expect(action.getByTestId("next-action-operation")).toContainText("Draw ¥150,000.00 on Bank credit line and finance ¥255,000.00 of the ¥420,000.00 invoice to Foshan Home Retail Co.");
  await expect(action.getByTestId("next-action-after-lowest")).toHaveText("¥300k");
  await expect(action).toContainText("¥405,000.00");
  await expect(action.getByTestId("next-action-cost")).toContainText("¥3,113.93");
  await expect(action.getByTestId("next-action-cost-breakdown")).toContainText("¥841.64");
  await expect(action.getByTestId("next-action-cost-breakdown")).toContainText("¥2,272.29");
  await expect(action.getByTestId("next-action-cost-basis")).toContainText("expected repayment of the Bank credit line in 32 days");
  await expect(action).not.toContainText("not included");
  await expect(action.getByTestId("next-action-lands")).toHaveText("in 3 days");
  await expect(action.getByTestId("next-action-within-limits")).toHaveText("Within your signed limits. No additional approval required.");
  await expect(action).not.toContainText("agent");
  await expect(action.getByTestId("next-action-if-nothing")).toContainText("¥240,000.00 below your minimum cash reserve in 12 days");
  await expect(action.getByTestId("next-action-after")).toContainText("Cash stays above your minimum cash reserve for the next 120 days");
  // "Why this" never quotes another plan's amounts as this plan's: the alert's own cure is said as a fallback.
  await expect(action.getByTestId("next-action-why")).toContainText("A fallback also exists");
  await expect(action.getByTestId("next-action-why")).toContainText("FLOW recommends the plan above.");
  await expect(action.getByTestId("next-action-why")).not.toContainText("A committed cure exists");
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-12")).toHaveText("Run funding plan");
  // Nothing from the demo on the owner's screen: no stepper, no clock, no mock pill, no engine navigation.
  await expect(page.getByRole("region", { name: "Guided demo" })).toHaveCount(0);
  await expect(page.getByTestId("home-advance")).toHaveCount(0);
  await expect(page.getByText("Mock data")).toHaveCount(0);
  await expect(page.getByRole("navigation").getByRole("link", { name: "Trajectory" })).toHaveCount(0);
  // Nothing needs a decision, so the section is not there at all.
  await expect(page.locator("#home-decisions")).toHaveCount(0);
  await expect(page.getByTestId("home-next-receipt")).toContainText("Foshan Home Retail Co.");
  await expect(page.getByTestId("home-next-receipt")).toContainText("¥420,000.00");
  await expect(page.getByTestId("home-next-receipt")).toContainText("in 32 days");
});

test("the next step is three facts and a Details fold; the first press asks, Cancel runs nothing", async ({ page }) => {
  await page.goto("/");
  const action = page.getByTestId("home-next-action");
  await expect(action).toContainText("Recommended next step");
  // Three tiles: the estimated total cost, when the funds are available, who decides.
  await expect(action.locator("dl").first().locator("dt")).toHaveText(["Estimated cost", "Funds available", "Who decides"]);
  // Everything else waits behind "Details", closed.
  const details = action.getByTestId("next-action-details");
  await expect(details).not.toHaveAttribute("open", "");
  await expect(action.getByTestId("next-action-if-nothing")).toBeHidden();
  await details.locator("> summary").click();
  await expect(action.getByTestId("next-action-if-nothing")).toBeVisible();
  await expect(action.getByTestId("next-action-cost-breakdown")).toBeVisible();
  // The first press asks, with what is received and what it costs; Cancel sends nothing.
  let acts = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && /\/alerts\/[^/]+\/act(\?|$)/.test(r.url())) acts += 1;
  });
  await page.getByTestId("fix-open-ALERT-RESERVE-12").click();
  const confirm = page.getByTestId("fix-confirm-ALERT-RESERVE-12");
  await expect(confirm).toContainText("Run this plan now?");
  await expect(confirm).toContainText("¥405,000.00");
  await expect(confirm).toContainText("¥3,113.93");
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-12")).toHaveCount(0);
  await page.getByTestId("fix-cancel-ALERT-RESERVE-12").click();
  await expect(confirm).toHaveCount(0);
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-12")).toBeVisible();
  await expect(page.getByTestId("fix-result")).toHaveCount(0);
  expect(acts).toBe(0);
  // Pressing twice runs the plan.
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("fix-result")).toContainText("2 executed");
});

test("Go ahead on the opening books runs the fix alone, and the home turns calm with the advance on its way", async ({ page }) => {
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-12");
  const result = page.getByTestId("fix-result");
  await expect(result).toContainText("2 executed");
  await expect(result).toContainText("Solved: the alert is cleared.");
  // Each operation reads as its business sentence and its status; the engine's details wait behind "Audit details".
  await expect(result.getByTestId("op-sentence").first()).toHaveText("¥150,000.00 drawn on the Bank credit line. Cash received today.");
  await expect(result.getByTestId("op-state").first()).toContainText("Executed");
  await expect(result.getByTestId("op-audit").first().getByTestId("op-raw")).toBeHidden();
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");

  await expect(page.getByTestId("home-headline")).toHaveText("You're covered.");
  await expect(page.getByTestId("home-note")).toContainText("Cash stays above your ¥300k minimum cash reserve for the next 120 days.");
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  // On its way: the server's headline, and "Arriving" beside the cash already in hand (two figures, never one).
  await expect(page.getByTestId("home-in-transit")).toContainText("¥255k funding arriving in 3 days");
  await expect(page.getByTestId("home-arriving")).toHaveText("¥255,000.00");
  await expect(page.getByTestId("home-cash")).toHaveText("¥550k");
  // The status label is the server's: a WATCH with thin headroom reads "Covered, but tight", and the headroom figures show.
  await expect(page.getByTestId("home-status-word")).toHaveText("Covered, but tight");
  await expect(page.getByTestId("home-headroom")).toHaveText("¥250k above your minimum");
  await expect(page.getByTestId("home-headroom-lowest")).toHaveText("Lowest point: ¥0.00 above your minimum");
  // Recent changes lead with the business sentence, never the executor's "Advance ¥… on RI:… from FAC-… on day 0".
  const changes = page.getByTestId("home-changes-list");
  await expect(changes).toContainText("¥150,000.00 drawn on the Bank credit line. Cash received today.");
  await expect(changes).toContainText("¥255,000.00 of invoice financing drawn against the Foshan Home Retail Co. invoice. Funds arrive in 3 days.");
  await expect(changes).not.toContainText("Advance ¥");
  await expect(changes).not.toContainText("RI:");
  await expect(page.locator("#home-decisions")).toHaveCount(0);
  // The agent's answer and the changes carry no day numbers either: the executor's "on day 0; lands on day 3" is said from today.
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
});

test("day 34: the fix needs approval; queuing it from the home runs nothing and the home says it waits", async ({ page }) => {
  await advanceTo34(page);
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "ACTION_NEEDED");
  await expect(page.getByTestId("home-headline")).toHaveText("Your cash reserve becomes unsafe in 8 days.");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
  await expect(page.getByTestId("home-note")).toHaveText("Cash falls to ¥100k, ¥200k below your ¥300k minimum cash reserve.");
  const action = page.getByTestId("home-next-action");
  await expect(action.getByTestId("next-action-title")).toHaveText("Secure ¥200k of funding");
  await expect(action.getByTestId("next-action-operation")).toContainText("Finance ¥200,000.00 of the ¥420,000.00 invoice to Foshan Home Retail Co.");
  await expect(action).toContainText("¥1,782.19");
  await expect(action).toContainText("32.5% a year for 10 days");
  await expect(action.getByTestId("next-action-lands")).toHaveText("in 3 days");
  await expect(action.getByTestId("next-action-needs-owner")).toContainText("above the 15.00% limit you signed");
  await expect(action.getByTestId("next-action-after")).toContainText("Cash stays above your minimum cash reserve for the next 120 days");
  // The router's cheaper two-invoice plan would need two approvals, so the one-approval cure is recommended and the option named.
  await expect(action.getByTestId("next-action-cheaper")).toContainText("¥1,706.10");
  await expect(action.getByTestId("next-action-cheaper")).toContainText("2 separate approvals");
  // Who has not paid: the late buyer by name, with the days late.
  await expect(page.getByTestId("home-late-RCV-A")).toContainText("Foshan Home Retail Co.");
  await expect(page.getByTestId("home-late-RCV-A")).toContainText("2 days late");
  await expect(page.getByTestId("home-late-RCV-A")).not.toContainText("day(s)");
  // The first breach is also the worst point here (the same day): one tile with the figure and the distance once, not two.
  await expect(page.getByTestId("home-status")).toContainText("Cash at first breach (also the lowest point)");
  await expect(page.getByTestId("home-breach-cash")).toHaveText("¥100k");
  await expect(page.getByTestId("home-lowest")).toHaveCount(0);
  await expect(page.getByTestId("home-status")).not.toContainText("Worst point");
  await expect(page.getByTestId("home-status").getByText("in 8 days", { exact: true })).toHaveCount(1);
  await expect(page.getByTestId("home-change-LATE")).toContainText("was due 2 days ago");

  await expect(page.getByTestId("fix-open-ALERT-RESERVE-42")).toHaveText("Queue it for my approval");
  await runPlan(page, "ALERT-RESERVE-42");
  // The agent's answer is not a card of its own when all that happened is "it waits for your approval": the next step's tile says that
  // once (with the link), the decision row says the question once, and Recent changes keeps its row. The operation's tier, sequence
  // and hash are under "Audit details" on the approval card (approvals.spec.ts and below).
  await expect(page.getByTestId("fix-result")).toHaveCount(0);
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toHaveText("Waiting for your approval");
  await expect(page.getByTestId("alert-approval-link-ALERT-RESERVE-42")).toHaveText("Review and decide");
  await expect(page.getByTestId("approvals-badge")).toContainText("1 approval waiting");
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-42")).toHaveCount(0);
  // Needs your decision: the question, the cost and the landing day, and a link to the card.
  // The next step's card holds the page's one primary action while the plan waits (nothing else is left to run), filled like "Run funding plan";
  // the decision row below is a plain row with a quiet "Review and decide" word.
  await expect(page.getByTestId("alert-approval-link-ALERT-RESERVE-42")).toHaveText("Review and decide");
  await expect(page.getByTestId("alert-approval-link-ALERT-RESERVE-42")).toHaveClass(/bg-brand-600/);
  await expect(page.getByTestId("home-review-primary")).toHaveCount(0);
  await expect(page.locator("main button.bg-brand-600")).toHaveCount(0);
  // The question is the next step's card (cost, landing, the one primary): the Decisions card and the "Waiting" change row would say it again, so they are gone.
  const decision = page.getByTestId("home-next-action");
  await expect(decision.getByTestId("next-action-cost")).toContainText("¥1,782.19");
  await expect(decision.getByTestId("next-action-lands")).toHaveText("in 3 days");
  await expect(page.getByTestId("home-approval-APR-000001")).toHaveCount(0);
  await expect(page.getByTestId("home-change-WAITING")).toHaveCount(0);
  await expect(page.getByTestId("home-in-transit")).toHaveCount(0);
  const shown = await page.locator("main").innerText();
  expect(shown.split("¥200,000.00 of invoice financing").length - 1).toBeLessThanOrEqual(1);
  expect(shown.split("Waiting for your approval").length - 1).toBeLessThanOrEqual(2); // the status pill and the next step's box
  await expect(page.getByTestId("home-changes-list")).not.toContainText("Queued for owner approval");
  await expect(page.getByTestId("home-changes-list")).not.toContainText("RI:");
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
});

test("day 34: the approval card is a question with the cost, the landing day and the after-state; approving clears the home", async ({ page }) => {
  await advanceTo34(page);
  await runPlan(page, "ALERT-RESERVE-42");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await expect(page).toHaveURL(/\/approvals#approval-APR-000001/);
  const card = page.locator("#approval-APR-000001");
  await expect(card.getByTestId("approval-headline")).toHaveText("Approve ¥200,000.00 of invoice financing?");
  // The Source and Invoice facts say what the request is, so there is no sentence under the title repeating it.
  await expect(card).toContainText("the ¥420,000.00 invoice to Foshan Home Retail Co.");
  await expect(card).not.toContainText("Finance ¥200,000.00 of the ¥420,000.00 invoice");
  await expect(card.getByTestId("approval-state-APR-000001")).toContainText("Waiting for your approval");
  await expect(card.getByTestId("approval-cost")).toContainText("¥1,782.19");
  // A waiting row's landing is a forecast, said as one by the server.
  await expect(card.getByTestId("approval-lands")).toHaveText("If you approve today, the cash lands in 3 days.");
  await expect(card.getByTestId("approval-reason")).toContainText("32.5%");
  await expect(card.getByTestId("approval-reason")).not.toContainText("annualised");
  await expect(card.getByTestId("approval-after")).toContainText("for the next 120 days");
  await expect(card).toContainText("If you decline");
  // No day number anywhere on the card as the owner first sees it (the executor's own sentence is an audit detail, below).
  expect(await proseOf(page, ["[data-testid^=\"approval-detail-\"]"])).not.toMatch(/\bday \d/i);
  // The ids and the tier are audit details, closed by default.
  await expect(card.getByTestId("approval-detail-APR-000001")).toBeHidden();
  await card.getByTestId("approval-toggle-APR-000001").locator("> summary").click();
  await expect(card.getByTestId("approval-detail-APR-000001")).toContainText("Tier 2");
  await expect(card.getByTestId("approval-detail-APR-000001")).toContainText("alert:ALERT-RESERVE-42:v7:0");

  await card.getByRole("button", { name: "Approve" }).click();
  await expect(card.getByTestId("approval-result-APR-000001")).toContainText("the cash lands in 3 days");
  await expect(card).toContainText("Approved");
  await expect(card.getByTestId("approval-decided-APR-000001")).toHaveText("Decided today.");

  await page.getByRole("navigation").getByRole("link", { name: "Home", exact: true }).first().click();
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  await expect(page.getByTestId("home-in-transit")).toContainText("¥200k funding arriving in 3 days");
  await expect(page.getByTestId("home-arriving")).toHaveText("¥200,000.00");
  await expect(page.getByTestId("home-status-word")).toHaveText("Covered, but tight");
  await expect(page.getByTestId("home-headroom")).toHaveText("¥0.00 above your minimum");
  await expect(page.getByTestId("home-headroom-lowest")).toHaveText("Lowest point: ¥0.00 above your minimum");
  await expect(page.locator("#home-decisions")).toHaveCount(0);
  await expect(page.getByTestId("home-changes-list")).toContainText("You approved ¥200,000.00 of invoice financing. Funds arrive in 3 days.");
  // The decision is the news: the entry that waited for it is not repeated beside it.
  await expect(page.getByTestId("home-changes-list")).not.toContainText("Waiting for your approval");
  await expect(page.getByTestId("home-change-WAITING")).toHaveCount(0);
  await expect(page.getByTestId("home-changes-list")).not.toContainText("Advance ¥");
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
});

test("in Chinese the whole home reads in Chinese: the labels and the server's recorded sentences", async ({ page }) => {
  await page.goto("/");
  await openAccountMenu(page);
  await page.getByLabel("中文").check();
  // The home is re-read in Chinese (GET /home?lang=zh, recorded): the status word, the headline and the plan are the server's own.
  await expect(page.getByTestId("home-status-word")).toHaveText("需要行动");
  await expect(page.getByTestId("home-headline")).toHaveText(/不再安全/);
  await expect(page.getByTestId("next-action-title")).toHaveText("筹措 ¥405k 资金");
  await expect(page.getByRole("navigation").getByRole("link", { name: "现金与融资" })).toBeVisible();
  await expect(page.getByTestId("chat-open")).toContainText("问 FLOW");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await openAccountMenu(page);
  await page.getByLabel("English").check();
  await expect(page.getByTestId("home-status-word")).toHaveText("Action needed");
  await expect(page.getByTestId("chat-open")).toContainText("Ask FLOW");
});

test("the tour is off by default, starts from the account sheet, has two steps on the home and can be closed", async ({ page }) => {
  await page.goto("/");
  // Nothing starts by itself, not even on a first visit.
  await page.waitForTimeout(1200);
  await expect(page.getByTestId("tour")).toHaveCount(0);
  await openAccountMenu(page);
  await page.getByTestId("account-tour").click();
  const tour = page.getByTestId("tour");
  await expect(tour).toBeVisible();
  await expect(tour).toContainText("Step 1 of 2");
  await expect(tour).toContainText("Am I safe?");
  await page.getByTestId("tour-next").click();
  await expect(tour).toContainText("Step 2 of 2");
  // The five sections, in the pages' own words; no Buy equipment among them.
  const sections = tour.getByTestId("tour-sections");
  await expect(sections.locator("li")).toHaveCount(5);
  await expect(sections).toContainText("Cash & funding");
  await expect(sections).not.toContainText("Buy equipment");
  await expect(tour).toContainText("Ask FLOW");
  await expect(tour.getByTestId("tour-skip")).toHaveCount(0);
  await page.getByTestId("tour-next").click();
  await expect(tour).toHaveCount(0);
  // Esc closes it at any step; the cash page offers its own two.
  await page.goto("/cash");
  await openAccountMenu(page);
  await page.getByTestId("account-tour").click();
  await expect(page.getByTestId("tour")).toContainText("How much risk");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("tour")).toHaveCount(0);
});
