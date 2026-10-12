import type { Page } from "@playwright/test";
import { expect, proseOf, test } from "./fixtures";
import { filledBrand, runPlan, verdictHeading } from "./helpers";

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
  // The chart says the worst point (the lowest label) and the chips say what drives it; an unsafe state has no separate "worst" line.
  await expect(page.getByTestId("home-worst")).toHaveCount(0);
  await expect(page.getByTestId("picture-chips")).toContainText("Payroll");
  await expect(page.getByTestId("picture-chips")).toContainText("−¥340k");
  await expect(page.getByTestId("picture-chips")).toContainText("in 12 days");
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
  await expect(page.getByTestId("home-floor")).toHaveText("¥300k");
  // The picture: both lines, the lowest point and the reserve in the server's strings; no card around the headline.
  const picture = page.getByTestId("home-picture");
  await expect(picture.getByTestId("picture-line-nothing")).toHaveCount(1);
  await expect(picture.getByTestId("picture-line-plan")).toHaveCount(1);
  await expect(picture).toContainText("Lowest −¥105k");
  await expect(picture).toContainText("Minimum cash reserve ¥300k");
  // The best next action: what, how much, cost, when, who decides, what if nothing, after.
  const action = page.getByTestId("home-next-action");
  // The details are one fold ("See the calculation") under the bar, not inside it.
  const fold = page.getByTestId("next-action-details");
  // The recommendation is the router's cheapest runnable plan, priced all-in (every leg, the basis in words): the
  // same figure the Cash & funding options, the chat and the documents quote.
  await expect(action.getByTestId("next-action-title")).toHaveText("Secure ¥405k of funding");
  await expect(action.getByTestId("next-action-components")).toContainText("¥150k");
  await expect(action.getByTestId("next-action-components")).toContainText("¥255k");
  await expect(page.getByTestId("next-action-operation")).toContainText("Draw ¥150,000.00 on Bank credit line and finance ¥255,000.00 of the ¥420,000.00 invoice to Foshan Home Retail Co.");
  await expect(page.getByTestId("next-action-after-lowest")).toHaveText("¥300k");
  await expect(fold).toContainText("¥405,000.00");
  await expect(action.getByTestId("next-action-cost")).toContainText("¥3,113.93");
  await expect(page.getByTestId("next-action-cost-breakdown")).toContainText("¥841.64");
  await expect(page.getByTestId("next-action-cost-breakdown")).toContainText("¥2,272.29");
  await expect(page.getByTestId("next-action-cost-basis")).toContainText("expected repayment of the Bank credit line in 32 days");
  await expect(fold).not.toContainText("not included");
  await expect(page.getByTestId("next-action-lands")).toHaveText("in 3 days");
  await expect(action.getByTestId("next-action-within-limits")).toHaveText("Within your signed limits. No additional approval required.");
  await expect(action).not.toContainText("agent");
  await expect(fold).not.toContainText("agent");
  await expect(page.getByTestId("next-action-if-nothing")).toContainText("¥240,000.00 below your minimum cash reserve in 12 days");
  await expect(page.getByTestId("next-action-after")).toContainText("Cash stays at or above your minimum cash reserve for the next 120 days");
  // "Why this" never quotes another plan's amounts as this plan's: the alert's own cure is said as a fallback.
  await expect(page.getByTestId("next-action-why")).toContainText("A fallback also exists");
  await expect(page.getByTestId("next-action-why")).toContainText("FLOW recommends the plan above.");
  await expect(page.getByTestId("next-action-why")).not.toContainText("A committed cure exists");
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

test("the plan bar is the cost, who decides and one fold; the first press asks, Cancel runs nothing", async ({ page }) => {
  await page.goto("/");
  const action = page.getByTestId("home-next-action");
  await expect(action).toContainText("Recommended next step");
  // Two facts in the bar: the estimated total cost and your approval (who decides); the funds' landing is said with each part.
  await expect(action.locator("dl").first().locator("dt")).toHaveText(["Estimated cost", "Your approval"]);
  await expect(action.getByTestId("next-action-components")).toContainText("in 3 days");
  // Everything else waits behind "See the calculation", closed and outside the bar.
  const details = page.getByTestId("next-action-details");
  await expect(action.getByTestId("next-action-details")).toHaveCount(0);
  await expect(details).not.toHaveAttribute("open", "");
  await expect(details.locator("> summary")).toHaveText("See the calculation");
  await expect(page.getByTestId("next-action-if-nothing")).toBeHidden();
  await details.locator("> summary").click();
  await expect(page.getByTestId("next-action-if-nothing")).toBeVisible();
  await expect(page.getByTestId("next-action-cost-breakdown")).toBeVisible();
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
  await expect(page.getByTestId("home-note")).toContainText("Cash stays at or above your ¥300k minimum cash reserve for the next 120 days.");
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  // On its way: the server's headline, and "Arriving" beside the cash already in hand (two figures, never one).
  await expect(page.getByTestId("home-in-transit")).toContainText("¥255k funding arriving in 3 days");
  await expect(page.getByTestId("home-arriving")).toHaveText("¥255,000.00");
  await expect(page.getByTestId("home-cash")).toHaveText("¥550k");
  // The status label is the server's: a WATCH with thin headroom reads "Covered, but tight", and the headroom figures show.
  await expect(page.getByTestId("home-status-word")).toHaveText("Covered, but tight");
  await expect(page.getByTestId("home-floor")).toHaveText("¥300k");
  // A calm day with nothing to fix: the chart is one line and there is no toggle.
  await expect(page.getByTestId("picture-line-plan")).toHaveCount(0);
  await expect(page.getByTestId("picture-view-plan")).toHaveCount(0);
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
  await expect(page.getByTestId("next-action-operation")).toContainText("Finance ¥200,000.00 of the ¥420,000.00 invoice to Foshan Home Retail Co.");
  await expect(action).toContainText("¥1,782.19");
  await expect(action).toContainText("32.5% a year for 10 days");
  await expect(page.getByTestId("next-action-lands")).toHaveText("in 3 days");
  await expect(action.getByTestId("next-action-needs-owner")).toContainText("above the 15.00% limit you signed");
  await expect(page.getByTestId("next-action-after")).toContainText("Cash stays at or above your minimum cash reserve for the next 120 days");
  // The router's cheaper two-invoice plan would need two approvals, so the one-approval cure is recommended and the option named.
  await expect(page.getByTestId("next-action-cheaper")).toContainText("¥1,706.10");
  await expect(page.getByTestId("next-action-cheaper")).toContainText("2 separate approvals");
  // Who has not paid: the late buyer by name, with the days late.
  await expect(page.getByTestId("home-late-RCV-A")).toContainText("Foshan Home Retail Co.");
  await expect(page.getByTestId("home-late-RCV-A")).toContainText("2 days late");
  await expect(page.getByTestId("home-late-RCV-A")).not.toContainText("day(s)");
  // The first breach is also the worst point here (the same day): the picture says the lowest point once.
  await expect(page.getByTestId("home-picture")).toContainText("Lowest ¥100k");
  await expect(page.getByTestId("home-picture").getByText("Lowest ¥100k")).toHaveCount(1);
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
  await expect(page.getByTestId("next-action-lands")).toHaveText("in 3 days");
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
  await expect(page.getByTestId("approval-headline")).toHaveText("Approve ¥200,000.00 of invoice financing?");
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

  await card.getByRole("button", { name: /^Approve/ }).click();
  await expect(card.getByTestId("approval-result-APR-000001")).toContainText("the cash lands in 3 days");
  await expect(card).toContainText("Approved");
  await expect(card.getByTestId("approval-decided-APR-000001")).toHaveText("Decided today.");

  await page.getByRole("navigation").getByRole("link", { name: "Home", exact: true }).first().click();
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  await expect(page.getByTestId("home-in-transit")).toContainText("¥200k funding arriving in 3 days");
  await expect(page.getByTestId("home-arriving")).toHaveText("¥200,000.00");
  await expect(page.getByTestId("home-status-word")).toHaveText("Covered, but tight");
  await expect(page.locator("#home-decisions")).toHaveCount(0);
  await expect(page.getByTestId("home-changes-list")).toContainText("You approved ¥200,000.00 of invoice financing. Funds arrive in 3 days.");
  // The decision is the news: the entry that waited for it is not repeated beside it.
  await expect(page.getByTestId("home-changes-list")).not.toContainText("Waiting for your approval");
  await expect(page.getByTestId("home-change-WAITING")).toHaveCount(0);
  await expect(page.getByTestId("home-changes-list")).not.toContainText("Advance ¥");
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
});

test("the cash picture draws both lines, the toggle hides and shows the plan, and a chip sets and clears the band", async ({ page }) => {
  await page.goto("/");
  const picture = page.getByTestId("home-picture");
  await expect(picture.getByTestId("picture-line-nothing")).toHaveCount(1);
  await expect(picture.getByTestId("picture-line-plan")).toHaveCount(1);
  // The plan is the default view; the toggle is a pair of pressed-state buttons.
  await expect(page.getByTestId("picture-view-plan")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("picture-view-nothing").click();
  await expect(page.getByTestId("picture-view-nothing")).toHaveAttribute("aria-pressed", "true");
  await expect(picture.getByTestId("picture-line-plan")).toHaveCount(0);
  await expect(picture.getByTestId("picture-line-nothing")).toHaveCount(1);
  await page.getByTestId("picture-view-plan").click();
  await expect(picture.getByTestId("picture-line-plan")).toHaveCount(1);
  // A chip lays a band over its day; pressing it again clears it.
  const chip = page.getByTestId("picture-chip-0");
  await expect(chip).toContainText("Payroll");
  await expect(page.getByTestId("picture-band")).toHaveCount(0);
  await chip.click();
  await expect(chip).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("picture-band")).toHaveCount(1);
  await chip.click();
  await expect(chip).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByTestId("picture-band")).toHaveCount(0);
  // The picture is an image with a sentence, and a table for a screen reader.
  await expect(picture.getByRole("img")).toHaveAttribute("aria-label", /unsafe in 12 days/);
  await expect(picture.getByTestId("picture-table")).toContainText("Payroll −¥340k");
});

test("Home lists the deals with the five-step track, and a deal without a contract says so", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-deals")).toBeVisible();
  await expect(page.getByTestId("home-deals-all")).toHaveAttribute("href", "/deals");
  const foshan = page.getByTestId("home-deal-BUYER-1");
  await expect(foshan).toContainText("Foshan Home Retail Co.");
  await expect(foshan).toContainText("On track");
  await expect(foshan.locator("ol > li")).toHaveCount(5);
  await expect(foshan).toContainText("Nothing needs you on this deal today.");
  const dongguan = page.getByTestId("home-deal-BUYER-2");
  await expect(dongguan).toContainText("Dongguan Office Supplies Ltd.");
  await expect(dongguan).toContainText("No contract on file yet");
  await expect(dongguan.getByRole("link", { name: "Add the contract" })).toHaveAttribute("href", "/documents");
});

test("the quiet day shows one line and no toggle", async ({ page }) => {
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("home-headline")).toHaveText("You're covered.");
  await expect(page.getByTestId("picture-line-nothing")).toHaveCount(1);
  await expect(page.getByTestId("picture-line-plan")).toHaveCount(0);
  await expect(page.getByTestId("picture-view-nothing")).toHaveCount(0);
});

test("one h1, one brand-filled primary, and nothing scrolls sideways on a phone; the plan sits above the chart", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByTestId("home-picture")).toBeVisible();
  await expect(page.locator("h1")).toHaveCount(1);
  expect(await filledBrand(page)).toBe(1);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  // The plan comes straight after the headline and above the chart, in the page's own flow.
  const bar = await page.getByTestId("home-next-action").boundingBox();
  const chart = await page.getByTestId("home-picture").boundingBox();
  const head = await page.getByTestId("home-status").boundingBox();
  expect(bar && chart && head).toBeTruthy();
  expect(bar!.y).toBeGreaterThan(head!.y);
  expect(bar!.y).toBeLessThan(chart!.y);
  expect(await page.getByTestId("home-next-action").evaluate((el) => getComputedStyle(el).position)).not.toBe("sticky");
});

test("at 1280 px the plan bar is sticky, and at 1366 x 768 the primary action is inside the first screen", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await expect(page.getByTestId("home-next-action")).toBeVisible();
  expect(await page.getByTestId("home-next-action").evaluate((el) => getComputedStyle(el).position)).toBe("sticky");
  await page.setViewportSize({ width: 1366, height: 768 });
  const box = await page.getByTestId("fix-open-ALERT-RESERVE-12").boundingBox();
  expect(box).toBeTruthy();
  expect(box!.y + box!.height).toBeLessThanOrEqual(768);
});

test("the new Home strings read in Chinese", async ({ page }) => {
  await page.goto("/");
  await openAccountMenu(page);
  await page.getByLabel("中文").check();
  await expect(page.getByTestId("home-picture")).toContainText("未来 36 天的现金");
  await expect(page.getByTestId("picture-ytick").first()).toBeVisible(); // the server's own y labels
  await expect(page.getByTestId("picture-view-plan")).toHaveText("采用 FLOW 方案");
  await expect(page.getByTestId("home-deals")).toContainText("您的交易");
  await expect(page.getByTestId("next-action-details").locator("> summary")).toHaveText("查看计算过程");
  await expect(page.getByTestId("home-deals-all")).toHaveText("全部交易");
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

// ---- pages A1: the open offer on the deal row and the sidebar counts (the server's `open_offer`, `needs_you_text` and GET /nav/counts, recorded)

test("a quiet day: the deal row has no offer and the sidebar carries no counts", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-deal-BUYER-1")).toBeVisible();
  await expect(page.getByTestId("home-deal-offer-BUYER-1")).toHaveCount(0);
  await expect(page.getByTestId("nav-pills").getByTestId("nav-count-deals")).toHaveCount(0);
  await expect(page.getByTestId("nav-pills").getByTestId("nav-count-receivables")).toHaveCount(0);
  await expect(page.getByTestId("nav-pills").getByRole("link", { name: "Deals", exact: true })).toBeVisible();
});

test("an offer waiting: the deal row leads with it, FLOW's read follows the check, and the sidebar counts the deal", async ({ page }) => {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("inbox-collapsed")).toBeVisible();
  await expect(page.getByTestId("next-step")).toBeVisible();
  await page.goto("/");
  const row = page.getByTestId("home-deal-BUYER-1");
  await expect(page.getByTestId("home-deal-needs-BUYER-1")).toHaveText(/An offer is waiting for your reply/);
  await expect(page.getByTestId("home-deal-needs-BUYER-1")).toHaveAttribute("data-tone", "warn");
  const track = page.getByTestId("home-deal-stages-BUYER-1");
  await expect(track.locator("li")).toHaveCount(5);
  await expect(track.locator("li").first()).toHaveAttribute("data-state", "now");
  await expect(row.getByTestId("home-deal-asks")).toContainText("early settlement of ¥420,000.00 at 1.20%");
  await expect(row.getByTestId("home-deal-read")).toHaveCount(0); // FLOW has not read it yet
  await expect(row.getByTestId("home-deal-action")).toHaveText("FLOW has not read it yet.");
  const side = page.getByTestId("nav-pills");
  await expect(side.getByTestId("nav-count-deals")).toHaveText("1");
  await expect(side.getByRole("link", { name: "Deals, 1 needs you" })).toBeVisible();
  await expect(side.getByTestId("nav-count-receivables")).toHaveCount(0);

  // After FLOW's check: the read, the cost in the bad tone (it is over the owner's limit), the replies ready.
  await page.goto("/deals");
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(verdictHeading(page)).toContainText(/Don't accept as asked|Counter instead of accepting as asked/);
  await page.goto("/");
  await expect(track.locator("li").nth(1)).toHaveAttribute("data-state", "done");
  await expect(track.locator("li").nth(2)).toHaveAttribute("data-state", "now");
  await expect(row.getByTestId("home-deal-read")).toContainText(/Don't accept as asked|Counter instead of accepting as asked/);
  await expect(row.getByTestId("home-deal-cost")).toHaveText("¥28,326.92");
  await expect(row.getByTestId("home-deal-cost")).toHaveCSS("color", "rgb(163, 36, 26)");
  await expect(row.getByTestId("home-deal-action")).toHaveText("Two replies are ready to send.");
  await expect(row.getByTestId("home-deal-open-BUYER-1")).toHaveAttribute("href", "/deals?buyer=BUYER-1");
  expect(await proseOf(page)).not.toMatch(/\bOFF-|\bVER-/);
});

test("day 34: the sidebar counts the late invoice and the approval, and the count follows the language", async ({ page }) => {
  await advanceTo34(page);
  const side = page.getByTestId("nav-pills");
  await expect(side.getByTestId("nav-count-receivables")).toHaveText("1");
  await expect(side.getByRole("link", { name: "Receivables, 1 is late" })).toBeVisible();
  await expect(side.getByTestId("nav-count-deals")).toHaveText("1");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("approvals-badge")).toContainText("1 approval waiting");
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.reload();
  await expect(page.getByTestId("nav-pills").getByRole("link", { name: /应收款，1 笔已逾期/ })).toBeVisible();
});

// The lowest points are the labels that must never be dropped: on the opening books both lines' lowest figures (the server's short strings) are drawn inside the picture at every width.
for (const [w, h, both] of [
  [1280, 800, true],
  [1440, 900, true],
  [390, 844, false],
] as const) {
  test(`the lowest points are labelled inside the cash picture at ${w} px`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await page.goto("/");
    const picture = page.getByTestId("home-picture");
    await expect(picture.getByTestId("picture-line-nothing")).toHaveCount(1);
    const svg = picture.locator("svg[role=img]");
    const box = (await svg.boundingBox())!;
    const inside = async (text: string) => {
      const label = svg.locator("text", { hasText: text });
      await expect(label).toHaveCount(1);
      const b = (await label.boundingBox())!;
      expect(b.x).toBeGreaterThanOrEqual(box.x - 1);
      expect(b.x + b.width).toBeLessThanOrEqual(box.x + box.width + 6);
      expect(b.y).toBeGreaterThanOrEqual(box.y);
      expect(b.y + b.height).toBeLessThanOrEqual(box.y + box.height);
    };
    await inside("Lowest −¥105k");
    if (both) await inside("Lowest ¥300k");
  });
}
