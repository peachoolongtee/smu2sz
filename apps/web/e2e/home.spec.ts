import type { Page } from "@playwright/test";
import { expect, proseOf, test } from "./fixtures";
import { filledBrand, runPlan, verdictHeading } from "./helpers";

/**
 * The Business home (`/`) in mock mode, as a dashboard: the status sentence as the heading, three cards (cash available, planned funding, the lowest
 * cash ahead, which opens into the full range), who funds the business as a ring, the shortcuts and the recent activity. One server read (GET /home)
 * answers it; the mock replays summaries recorded from the real API on the demo path (the opening books, the quiet books after the plan ran, day 34
 * with the late invoice, the queued fix, the approved fix), so every sentence and amount here is a server string. The clock is a Demo-mode control.
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

/** The story page's clock moves the simulated day; the home is then opened directly. */
async function advanceTo34(page: Page) {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
}

test("the Business home answers safe, do and cost on the opening books in three cards, without a demo control", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "ACTION_NEEDED");
  await expect(page.getByTestId("home-status-word")).toContainText("Action needed");
  await expect(page.getByTestId("home-headline")).toHaveText("Your cash reserve becomes unsafe in 12 days.");
  // The three cards, largest first: the cash available, the planned funding, the lowest cash ahead.
  await expect(page.getByTestId("home-cards").locator("> article, > button")).toHaveCount(3);
  await expect(page.getByTestId("home-cash-value")).toHaveText("¥400k");
  await expect(page.getByTestId("home-card-cash")).toContainText("¥100k above your minimum");
  await expect(page.getByTestId("home-card-cash")).toContainText("Minimum reserve ¥300k");
  const plan = page.getByTestId("home-card-funding");
  await expect(plan).toHaveAttribute("data-state", "plan");
  await expect(page.getByTestId("home-plan-value")).toHaveText("¥405k");
  await expect(plan).toContainText("Bank credit line");
  await expect(plan).toContainText("¥150,000.00");
  await expect(plan).toContainText("¥255,000.00");
  await expect(plan).toContainText("¥3,113.93");
  await expect(plan).toContainText("Ready to run");
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-12")).toHaveText("Run funding plan");
  await expect(page.getByTestId("home-action-secondary")).toHaveAttribute("href", "/cash#cash-options");
  await expect(page.getByTestId("home-lowest-value")).toHaveText("−¥105k");
  await expect(page.getByTestId("home-card-lowest")).toContainText("in 30 days");
  // Business words only: no day numbers, no agent, no ids.
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
  await expect(plan).not.toContainText("agent");
  // One product in the header, Approvals as an attention badge (absent while nothing waits), one account menu.
  await expect(page.getByTestId("demo-data-indicator")).toHaveCount(1);
  await expect(page.getByRole("banner").getByRole("link", { name: /FLOW/ })).toBeVisible();
  await expect(page.getByTestId("approvals-badge")).toHaveCount(0);
  await expect(page.getByTestId("account-menu")).toBeVisible();
  // Nothing from the demo on the owner's screen: no stepper, no clock, no mock pill, no engine navigation.
  await expect(page.getByRole("region", { name: "Guided demo" })).toHaveCount(0);
  await expect(page.getByTestId("home-advance")).toHaveCount(0);
  await expect(page.getByText("Mock data")).toHaveCount(0);
  await expect(page.getByRole("navigation").getByRole("link", { name: "Trajectory" })).toHaveCount(0);
  // Nothing besides the funding needs the owner, so the strip above the cards is not there.
  await expect(page.getByTestId("home-attention-strip")).toHaveCount(0);
});

test("the plan's calculation on Cash & funding: the title, the parts, the cost by part, who decides, what if nothing, and why", async ({ page }) => {
  // The details the Home card leaves to "Review the plan": the same plan bar, on the page that compares the options.
  await page.goto("/");
  await expect(page.getByTestId("home-action-secondary")).toHaveAttribute("href", "/cash#cash-options");
  await page.goto("/cash");
  const action = page.getByTestId("home-next-action");
  const fold = page.getByTestId("next-action-details");
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
  await expect(page.getByTestId("next-action-why")).toContainText("A fallback also exists");
  await expect(page.getByTestId("next-action-why")).toContainText("FLOW recommends the plan above.");
  await expect(page.getByTestId("next-action-why")).not.toContainText("A committed cure exists");
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-12")).toHaveText("Run funding plan");
});

test("the plan card's first press asks, Cancel runs nothing, and the calculation waits on Cash & funding", async ({ page }) => {
  await page.goto("/cash");
  const details = page.getByTestId("next-action-details");
  await expect(page.getByTestId("home-next-action").getByTestId("next-action-components")).toContainText("in 3 days");
  await expect(details).not.toHaveAttribute("open", "");
  await expect(details.locator("> summary")).toHaveText("See the calculation");
  await expect(page.getByTestId("next-action-if-nothing")).toBeHidden();
  await details.locator("> summary").click();
  await expect(page.getByTestId("next-action-if-nothing")).toBeVisible();
  // The first press asks, with what is received and what it costs; Cancel sends nothing.
  await page.goto("/");
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
  await expect(result.getByTestId("op-sentence").first()).toHaveText("¥150,000.00 drawn on the Bank credit line. Cash received today.");
  await expect(result.getByTestId("op-state").first()).toContainText("Executed");
  await expect(result.getByTestId("op-audit").first().getByTestId("op-raw")).toBeHidden();
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  await expect(page.getByTestId("home-headline")).toHaveText("Your cash is covered on the current plan.");
  await expect(page.getByTestId("home-status-word")).toContainText("Covered, but tight");
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  // The planned funding is now what landed and what is still on its way, beside the cash already in hand.
  const plan = page.getByTestId("home-card-funding");
  await expect(plan).toHaveAttribute("data-state", "arranged");
  await expect(plan).toContainText("On its way");
  await expect(plan).toContainText("¥255,000.00");
  await expect(plan).toContainText("in 3 days");
  await expect(page.getByTestId("home-cash-value")).toHaveText("¥550k");
  // Recent activity leads with the business sentence, never the executor's "Advance ¥… on RI:… from FAC-… on day 0".
  const recent = page.getByTestId("home-recent");
  await expect(recent).toContainText("¥150,000.00 drawn on the Bank credit line. Cash received today.");
  await expect(recent).toContainText("¥255,000.00 of invoice financing drawn against the Foshan Home Retail Co. invoice. Funds arrive in 3 days.");
  await expect(recent).not.toContainText("Advance ¥");
  await expect(recent).not.toContainText("RI:");
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
});

test("day 34: the fix needs approval; queuing it from the home runs nothing and the home says it waits", async ({ page }) => {
  await advanceTo34(page);
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "ACTION_NEEDED");
  await expect(page.getByTestId("home-headline")).toHaveText("Your cash reserve becomes unsafe in 8 days.");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
  const plan = page.getByTestId("home-card-funding");
  await expect(page.getByTestId("home-plan-value")).toHaveText("¥200k");
  await expect(plan).toContainText("¥1,782.19");
  await expect(plan).toContainText("Needs your approval");
  // The late buyer is the strip above the cards: the funding is the card's, the collection the strip's.
  const strip = page.getByTestId("home-attention-strip");
  await expect(strip).toContainText("Foshan is 2 days late on ¥163k.");
  await expect(strip.getByRole("link", { name: /Chase the payment/ })).toHaveAttribute("href", "/receivables");
  await expect(page.getByTestId("home-recent")).toContainText("was due 2 days ago");

  await expect(page.getByTestId("fix-open-ALERT-RESERVE-42")).toHaveText("Queue it for my approval");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("fix-result")).toHaveCount(0);
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toHaveText("Waiting for your approval");
  await expect(page.getByTestId("alert-approval-link-ALERT-RESERVE-42")).toHaveText("Review and decide");
  await expect(page.getByTestId("alert-approval-link-ALERT-RESERVE-42")).toHaveClass(/bg-brand-600/);
  await expect(page.getByTestId("approvals-badge")).toContainText("1 approval waiting");
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-42")).toHaveCount(0);
  await expect(plan).toContainText("Waiting for you");
  // The question is the card's one primary while the plan waits.
  expect(await filledBrand(page)).toBe(1);
  await expect(page.locator("main button.bg-brand-600")).toHaveCount(0);
  await expect(page.getByTestId("home-recent")).not.toContainText("Queued for owner approval");
  await expect(page.getByTestId("home-recent")).not.toContainText("RI:");
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
});

test("day 34: the approval card is a question with the cost, the landing day and the after-state; approving clears the home", async ({ page }) => {
  await advanceTo34(page);
  await runPlan(page, "ALERT-RESERVE-42");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await expect(page).toHaveURL(/\/approvals#approval-APR-000001/);
  const card = page.locator("#approval-APR-000001");
  await expect(page.getByTestId("approval-headline")).toHaveText("Approve ¥200,000.00 of invoice financing?");
  await expect(card).toContainText("the ¥420,000.00 invoice to Foshan Home Retail Co.");
  await expect(card).not.toContainText("Finance ¥200,000.00 of the ¥420,000.00 invoice");
  await expect(card.getByTestId("approval-state-APR-000001")).toContainText("Waiting for your approval");
  await expect(card.getByTestId("approval-cost")).toContainText("¥1,782.19");
  await expect(card.getByTestId("approval-lands")).toHaveText("If you approve today, the cash lands in 3 days.");
  await expect(card.getByTestId("approval-reason")).toContainText("32.5%");
  await expect(card.getByTestId("approval-reason")).not.toContainText("annualised");
  await expect(card.getByTestId("approval-after")).toContainText("for the next 120 days");
  await expect(card).toContainText("If you decline");
  expect(await proseOf(page, ["[data-testid^=\"approval-detail-\"]"])).not.toMatch(/\bday \d/i);
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
  await expect(page.getByTestId("home-card-funding")).toContainText("¥200,000.00");
  await expect(page.getByTestId("home-status-word")).toContainText("Covered, but tight");
  await expect(page.getByTestId("home-recent")).toContainText("You approved ¥200,000.00 of invoice financing. Funds arrive in 3 days.");
  await expect(page.getByTestId("home-recent")).not.toContainText("Advance ¥");
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
});

test("who funds you: the owner's share in the ring, one row per source, and a source opens its details", async ({ page }) => {
  await page.goto("/");
  const mix = page.getByTestId("home-mix");
  await expect(page.getByTestId("home-mix-own-share")).toHaveText("50%");
  const rows = mix.getByTestId("home-mix-row");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText("Your own money");
  await expect(rows.nth(1)).toContainText("Bank credit line");
  await expect(rows.nth(1)).toHaveAttribute("data-kind", "planned");
  await expect(mix).toContainText("Lighter colours: in FLOW's plan, not yet run.");
  // A row opens the source's details: the limit, what is in use, what is left and how fast its money lands; the ring then shows that source's share.
  await expect(mix.getByTestId("home-mix-details")).toHaveCount(0);
  await rows.nth(1).getByTestId("home-mix-toggle").click();
  await expect(rows.nth(1).getByTestId("home-mix-toggle")).toHaveAttribute("aria-expanded", "true");
  const details = mix.getByTestId("home-mix-details");
  await expect(details).toContainText("¥150,000.00");
  await expect(details).toContainText("Still available");
  await expect(details).toContainText("The day you draw");
  await expect(page.getByTestId("home-mix-own-share")).toHaveText("19%");
  // One source open at a time; its arc toggles it too.
  await rows.nth(0).getByTestId("home-mix-toggle").click();
  await expect(details).toContainText("Cash today");
  await expect(rows.nth(1).getByTestId("home-mix-toggle")).toHaveAttribute("aria-expanded", "false");
  await page.getByTestId("home-mix-arc").first().click();
  await expect(mix.getByTestId("home-mix-details")).toHaveCount(0);
  // After the plan ran the lenders are received or arriving, and the split is the same.
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("home-headline")).toHaveText("Your cash is covered on the current plan.");
  await expect(page.getByTestId("home-mix-own-share")).toHaveText("50%");
  await expect(rows.nth(1)).toHaveAttribute("data-kind", "lender");
  await expect(rows.nth(2)).toContainText("arriving in 3 days");
});

test("the lowest cash ahead opens into the full range; a key day's words show only while the pointer is on it", async ({ page }) => {
  await page.goto("/");
  const card = page.getByTestId("home-card-lowest");
  await expect(card).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByTestId("home-cash-ahead")).toHaveCount(0);
  await card.click();
  await expect(card).toHaveAttribute("aria-expanded", "true");
  const ahead = page.getByTestId("home-cash-ahead");
  await expect(ahead).toBeVisible();
  await expect(ahead).toContainText("Minimum reserve ¥300k");
  await expect(ahead).toContainText("If you run FLOW's plan");
  await expect(page.getByTestId("home-ahead-tip")).toHaveCount(0);
  const marks = ahead.getByTestId("home-ahead-mark");
  expect(await marks.count()).toBeGreaterThanOrEqual(5);
  await marks.nth(2).hover();
  const tip = page.getByTestId("home-ahead-tip");
  await expect(tip).toContainText(/payroll is paid/i);
  await expect(tip).toContainText("−¥340k");
  await expect(tip).toContainText(/in 12 days/i);
  // The keyboard reaches the same words.
  await page.mouse.move(0, 0);
  await expect(tip).toHaveCount(0);
  await marks.nth(0).focus();
  await expect(page.getByTestId("home-ahead-tip")).toBeVisible();
  // The window widens the range; Close folds it away.
  await ahead.getByTestId("home-ahead-window").getByRole("tab", { name: "120 days" }).click();
  await expect(ahead).toContainText("in 120 days");
  await page.getByTestId("home-ahead-close").click();
  await expect(page.getByTestId("home-cash-ahead")).toHaveCount(0);
});

test("one h1, one brand-filled primary, and nothing scrolls sideways on a phone; the cards come before who funds you", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByTestId("home-cards")).toBeVisible();
  await expect(page.locator("h1")).toHaveCount(1);
  expect(await filledBrand(page)).toBe(1);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  const head = (await page.getByTestId("home-status").boundingBox())!;
  const plan = (await page.getByTestId("home-card-funding").boundingBox())!;
  const mix = (await page.getByTestId("home-mix").boundingBox())!;
  expect(plan.y).toBeGreaterThan(head.y);
  expect(mix.y).toBeGreaterThan(plan.y);
  expect(await page.getByTestId("home-next-action").evaluate((el) => getComputedStyle(el).position)).not.toBe("sticky");
});

test("at 1366 x 768 the primary action is inside the first screen", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  const box = await page.getByTestId("fix-open-ALERT-RESERVE-12").boundingBox();
  expect(box).toBeTruthy();
  expect(box!.y + box!.height).toBeLessThanOrEqual(768);
});

test("in Chinese the whole home reads in Chinese: the labels and the server's recorded sentences", async ({ page }) => {
  await page.goto("/");
  await openAccountMenu(page);
  await page.getByLabel("中文").check();
  await expect(page.getByTestId("home-status-word")).toContainText("需要行动");
  await expect(page.getByTestId("home-headline")).toHaveText(/不再安全/);
  await expect(page.getByTestId("home-card-cash")).toContainText("可用现金");
  await expect(page.getByTestId("home-card-funding")).toContainText("计划融资");
  await expect(page.getByTestId("home-card-lowest")).toContainText("未来最低现金");
  await expect(page.getByTestId("home-mix")).toContainText("资金来源");
  await expect(page.getByRole("navigation").getByRole("link", { name: "现金与融资" }).first()).toBeVisible();
  await expect(page.getByTestId("chat-open")).toContainText("问 FLOW");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await page.goto("/cash");
  await expect(page.getByTestId("next-action-details").locator("> summary")).toHaveText("查看计算过程");
  await openAccountMenu(page);
  await page.getByLabel("English").check();
  await page.goto("/");
  await expect(page.getByTestId("home-status-word")).toContainText("Action needed");
  await expect(page.getByTestId("chat-open")).toContainText("Ask FLOW");
});

test("the tour is off by default, starts from the account sheet, has two steps on the home and can be closed", async ({ page }) => {
  await page.goto("/");
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
  // The six sections, in the pages' own words; no Buy equipment among them.
  const sections = tour.getByTestId("tour-sections");
  await expect(sections.locator("li")).toHaveCount(6);
  await expect(sections).toContainText("Cash & funding");
  await expect(sections).toContainText("Attach deals");
  await expect(sections).not.toContainText("Buy equipment");
  await expect(tour).toContainText("Ask FLOW");
  await expect(tour.getByTestId("tour-skip")).toHaveCount(0);
  await page.getByTestId("tour-next").click();
  await expect(tour).toHaveCount(0);
  await page.goto("/cash");
  await openAccountMenu(page);
  await page.getByTestId("account-tour").click();
  await expect(page.getByTestId("tour")).toContainText("How much risk");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("tour")).toHaveCount(0);
});

// ---- the sidebar counts (GET /nav/counts, recorded) and the strip above the cards

test("a quiet day: the sidebar carries no counts", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-cards")).toBeVisible();
  await expect(page.getByTestId("nav-pills").getByTestId("nav-count-deals")).toHaveCount(0);
  await expect(page.getByTestId("nav-pills").getByTestId("nav-count-receivables")).toHaveCount(0);
  await expect(page.getByTestId("nav-pills").getByRole("link", { name: "Deals", exact: true })).toBeVisible();
  await expect(page.getByTestId("nav-pills").getByRole("link", { name: "Attach deals", exact: true })).toBeVisible();
});

test("an offer waiting: the sidebar counts the deal, and Deals leads with FLOW's read after the check", async ({ page }) => {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("inbox-collapsed")).toBeVisible();
  await expect(page.getByTestId("next-step")).toBeVisible();
  await page.goto("/");
  const side = page.getByTestId("nav-pills");
  await expect(side.getByTestId("nav-count-deals")).toHaveText("1");
  await expect(side.getByRole("link", { name: "Deals, 1 needs you" })).toBeVisible();
  await expect(side.getByTestId("nav-count-receivables")).toHaveCount(0);
  await page.goto("/deals");
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(verdictHeading(page)).toContainText(/Don't accept as asked|Counter instead of accepting as asked/);
  await page.goto("/");
  expect(await proseOf(page)).not.toMatch(/\bOFF-|\bVER-/);
});

test("a deal waiting for the owner is the strip above the cards, in the server's words, and leads to the deal", async ({ page }) => {
  // The attention queue as the API sends it with a reply waiting (laid over the recorded read; see the seam in lib/mock/handlers.ts).
  const item = { key: "deal:OFF-1", kind: "deal", eyebrow: "A buyer is waiting for your reply", title: "Foshan asks for early settlement at 1.20%.", primary: { label: "Open the deal", href: "/deals?buyer=BUYER-1" } };
  await page.context().addInitScript(([key, value]) => sessionStorage.setItem(key, JSON.stringify(value)), ["tl-mock-home-patch", { attention: { items: [item], primary_key: "deal:OFF-1", none_text: "No urgent action required." } }] as const);
  await page.goto("/");
  const strip = page.getByTestId("home-attention-strip");
  await expect(strip).toContainText("A buyer is waiting for your reply");
  await expect(strip).toContainText("Foshan asks for early settlement at 1.20%.");
  await expect(strip.getByRole("link", { name: /Open the deal/ })).toHaveAttribute("href", "/deals?buyer=BUYER-1");
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

// The lowest point must never be dropped: in the full range every key day's mark and the reserve's name are drawn inside the chart at every width.
for (const [w, h] of [
  [1280, 800],
  [1440, 900],
  [390, 844],
] as const) {
  test(`the key days and the reserve's name are inside the cash-ahead chart at ${w} px`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await page.goto("/");
    await page.getByTestId("home-card-lowest").click();
    const svg = page.getByTestId("home-cash-ahead").locator("svg[role=img]");
    await expect(svg).toBeVisible();
    const box = (await svg.boundingBox())!;
    const marks = page.getByTestId("home-ahead-mark");
    const n = await marks.count();
    expect(n).toBeGreaterThanOrEqual(5);
    for (let i = 0; i < n; i++) {
      const b = (await marks.nth(i).locator("circle").last().boundingBox())!;
      expect(b.x).toBeGreaterThanOrEqual(box.x - 1);
      expect(b.x + b.width).toBeLessThanOrEqual(box.x + box.width + 1);
      expect(b.y).toBeGreaterThanOrEqual(box.y - 1);
      expect(b.y + b.height).toBeLessThanOrEqual(box.y + box.height + 1);
    }
    const label = (await svg.locator("text", { hasText: "Minimum reserve ¥300k" }).boundingBox())!;
    expect(label.x).toBeGreaterThanOrEqual(box.x - 1);
    expect(label.x + label.width).toBeLessThanOrEqual(box.x + box.width + 1);
  });
}
