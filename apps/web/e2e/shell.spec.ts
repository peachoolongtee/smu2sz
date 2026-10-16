import type { Page } from "@playwright/test";
import { expect, proseOf, test } from "./fixtures";
import { runPlan, verdictHeading, openOperatorTools } from "./helpers";

/**
 * What the shell around the Home says, in mock mode on the recorded story: the header and the navigation, the tour, and the sidebar's counts (the server's `needs_you_text` and
 * GET /nav/counts, recorded). Home V2 is the page they are read on; its own behaviour is in home-v2.spec.ts. The clock is a Demo-mode control, on the story page.
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
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
}

test("the Business home carries no demo control, no Day N and one product in the header", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-v2")).toBeVisible();
  await expect(page.getByTestId("demo-data-indicator")).toHaveCount(1);
  await expect(page.getByRole("banner").getByRole("link", { name: /FLOW/ })).toBeVisible();
  await expect(page.getByRole("banner")).not.toContainText("Terms Guard");
  await expect(page.getByTestId("approvals-badge")).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Approvals" })).toHaveCount(0);
  await expect(page.getByTestId("account-menu")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  expect(await proseOf(page)).not.toMatch(/\bday \d/i);
  // Nothing from the demo on the owner's screen: no stepper, no clock, no mock pill, no engine navigation.
  await expect(page.getByRole("region", { name: "Guided demo" })).toHaveCount(0);
  await expect(page.getByTestId("home-advance")).toHaveCount(0);
  await expect(page.getByText("Mock data")).toHaveCount(0);
  await expect(page.getByRole("navigation").getByRole("link", { name: "Trajectory" })).toHaveCount(0);
});

test("the language switch re-reads the Home in Chinese and back, and the shell follows", async ({ page }) => {
  await page.goto("/");
  await openAccountMenu(page);
  await page.getByLabel("中文").check();
  await expect(page.getByTestId("home-status-word")).toContainText("需要行动");
  await expect(page.getByTestId("home-headline")).toHaveText(/不再安全/);
  await expect(page.getByRole("navigation").getByRole("link", { name: "现金与融资" })).toBeVisible();
  await expect(page.getByTestId("chat-open")).toHaveAttribute("aria-label", "问 FLOW");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await openAccountMenu(page);
  await page.getByLabel("English").check();
  await expect(page.getByTestId("home-status-word")).toContainText("Action needed");
  await expect(page.getByTestId("chat-open")).toHaveAttribute("aria-label", "Ask FLOW");
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
  // The Home's tour walks each part of the page (its steps are counted by the page), and ends on the sections.
  await expect(tour).toContainText(/Home · step 1 of \d+/i);
  await expect(tour).toContainText("Where your cash stands");
  // The shell's parts close the walk, in this order: Ask FLOW, the sections, the account.
  const next = page.getByTestId("tour-next");
  for (let i = 0; i < 20 && !(await tour.getByRole("heading", { name: "Ask FLOW" }).isVisible().catch(() => false)) && !(await tour.innerText()).includes("Ask FLOW"); i++) await next.click();
  await expect(tour).toContainText("Ask FLOW");
  const sections = tour.getByTestId("tour-sections");
  for (let i = 0; i < 20 && !(await sections.isVisible()); i++) await next.click();
  // The sections, in the pages' own words; no Buy equipment among them.
  expect(await sections.locator("li").count()).toBeGreaterThanOrEqual(5);
  await expect(sections).toContainText("Cash & funding");
  await expect(sections).not.toContainText("Buy equipment");
  // Next walks on to the account, and from its last step closes the tour.
  for (let i = 0; i < 5 && (await tour.count()) > 0; i++) await next.click();
  await expect(tour).toHaveCount(0);
  // Esc closes it at any step; the cash page offers its own two.
  await page.goto("/cash");
  await openAccountMenu(page);
  await page.getByTestId("account-tour").click();
  await expect(page.getByTestId("tour")).toContainText(/step 1 of \d+/i);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("tour")).toHaveCount(0);
});

test("a quiet day: the sidebar carries no counts", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-v2")).toBeVisible();
  await expect(page.getByTestId("nav-pills").getByTestId("nav-count-deals")).toHaveCount(0);
  await expect(page.getByTestId("nav-pills").getByTestId("nav-count-receivables")).toHaveCount(0);
  await expect(page.getByTestId("nav-pills").getByRole("link", { name: "Deals", exact: true })).toBeVisible();
});

test("an offer waiting: the sidebar counts the deal, and Deals leads with FLOW's read after the check", async ({ page }) => {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("deals-inbox")).toHaveCount(0); // the buyer's messages are the deal's Messages tab
  await expect(page.getByTestId("next-step")).toBeVisible();
  const deal = page.url(); // the address is the selection
  await page.goto("/");
  const side = page.getByTestId("nav-pills");
  await expect(side.getByTestId("nav-count-deals")).toHaveText("1");
  await expect(side.getByRole("link", { name: "Deals, 1 needs you" })).toBeVisible();
  await expect(side.getByTestId("nav-count-receivables")).toHaveCount(0);

  // After FLOW's check: the read, the cost in the bad tone (it is over the owner's limit), the replies ready.
  await page.goto(deal);
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  // The heading is the buyer's ask from the first read, so the check is done when the recommendation is there.
  await page.getByTestId("queue-recommends").waitFor();
  await expect(verdictHeading(page)).toContainText(/Foshan · |Foshan asks for early settlement|Don't accept as asked|Counter instead of accepting as asked/);
  await page.goto("/");
  expect(await proseOf(page)).not.toMatch(/\bOFF-|\bVER-/);
});

test("day 34: the sidebar counts the late invoice and the approval, and the count follows the language", async ({ page }) => {
  await advanceTo34(page);
  const side = page.getByTestId("nav-pills");
  await expect(side.getByTestId("nav-count-receivables")).toHaveText("1");
  await expect(side.getByRole("link", { name: "Receivables, 1 is late" })).toBeVisible();
  await expect(side.getByTestId("nav-count-deals")).toHaveText("1");
  // The cure is queued from Cash & funding, which holds the plan's own control at day 34.
  await page.goto("/cash");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("approvals-badge")).toContainText("1 approval waiting");
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.reload();
  await expect(page.getByTestId("nav-pills").getByRole("link", { name: /应收款，1 笔已逾期/ })).toBeVisible();
});

test("day 34: the cure queued from Cash & funding waits on Approvals, where the card is a question; approving it clears the alert", async ({ page }) => {
  await advanceTo34(page);
  await page.goto("/cash");
  await expect(page.getByTestId("fix-open-ALERT-RESERVE-42")).toHaveText("Queue it for my approval");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toHaveText("Waiting for your approval");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await expect(page).toHaveURL(/\/approvals#approval-APR-000001/);
  const card = page.locator("#approval-APR-000001");
  await expect(page.getByTestId("approval-headline")).toHaveText("Request ¥200,000 of invoice financing");
  await expect(card.getByTestId("approval-cost")).toContainText("¥1,782.19");
  await expect(card.getByTestId("approval-lands")).toHaveText("If you approve today, the cash lands in 3 days.");
  await expect(card.getByTestId("approval-after")).toContainText("for the next 120 days");
  expect(await proseOf(page, ['[data-testid^="approval-detail-"]'])).not.toMatch(/\bday \d/i);
  await card.getByRole("button", { name: /^Authorize/ }).click();
  await expect(card.getByTestId("approval-result-APR-000001")).toContainText("the cash lands in 3 days");
  await expect(card.getByTestId("approval-decided-APR-000001")).toHaveText("Decided today.");
});
