import { expect, proseOf, test } from "./fixtures";
import type { Page } from "@playwright/test";
import { openOperatorTools, runPlan } from "./helpers";

/**
 * Activity on GET /activity (Slice D, ticket #145). The recorded demo path in mock mode: day 34, the owner queues the fix for approval, then approves it. The rows, the
 * summary and the words are the server's; the page only hides rows (search, category) and never removes one.
 */

const isLive = (info: { project: { name: string } }) => info.project.name === "live";

async function approvedDay34(page: Page) {
  await page.goto("/demo");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/cash"); // the plan is run, and its waiting approval linked, on Cash & funding
  await runPlan(page, "ALERT-RESERVE-42");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await page.locator("#approval-APR-000001").getByRole("button", { name: /^(Approve|Authorize)/ }).click();
  await expect(page.locator("#approval-APR-000001")).toContainText("Approved");
  await page.goto("/activity");
  await expect(page.getByTestId("activity-read")).toBeVisible();
}

test("one title, the state as a pill and a sentence, and the business rows first with why, what remains and the way to the decision", async ({ page }, info) => {
  test.skip(isLive(info), "mock-mode spec: the recorded demo path");
  await approvedDay34(page);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Activity");
  await expect(page.getByTestId("activity-state")).not.toBeEmpty();
  const rows = page.getByTestId("activity-list").getByTestId("activity-row");
  await expect(rows.first()).toBeVisible();
  const approved = rows.filter({ hasText: "You approved" }).first();
  await expect(approved.getByTestId("activity-event")).toContainText("You approved");
  // The status and the actor are one quiet line with a separator, in the server's words.
  await expect(approved.getByTestId("activity-meta")).toContainText(/\S · \S/);
  await expect(approved.getByTestId("activity-open-decision")).toHaveText("Open this decision");
  await expect(approved.getByTestId("activity-open-decision")).toHaveAttribute("href", /^\/decisions\/alert:ALERT-RESERVE-42/);
  // The sentence leads; why it matters and what remains are labelled; the record is audit detail, folded.
  const withWhy = rows.filter({ has: page.getByTestId("activity-why") }).first();
  await expect(withWhy.getByTestId("activity-why")).toContainText("Why it matters");
  await expect(page.getByTestId("activity-remains").first()).toContainText("What is left");
  await expect(page.locator('[data-testid="activity-evidence"][open]')).toHaveCount(0);
  // No row shows an id, an engine term or a day number in its prose; the evidence folds hold the audit level.
  const prose = await proseOf(page, ['[data-testid="activity-evidence"]', "summary"]);
  expect(prose).not.toMatch(/\bAPR-\d|\bOP-|\bday \d+\b/i);
  // The chain's words stay in the header, with what the check covers.
  await expect(page.getByTestId("chain-status")).toContainText("Record chain checks passed");
  await page.getByTestId("activity-chain-scope").locator("> summary").click();
  await expect(page.getByTestId("activity-chain-scope")).toContainText("This checks the log's own integrity; it does not confirm bank facts or buyer promises.");
  await expect(page.getByTestId("activity-kept")).toContainText("Every entry stays in the record");
});

test("an evidence link lands on the trust view with that entry marked, and Back to Activity returns", async ({ page }, info) => {
  test.skip(isLive(info), "mock-mode spec: the recorded demo path");
  await approvedDay34(page);
  const row = page.getByTestId("activity-list").getByTestId("activity-row").first();
  await row.getByTestId("activity-evidence").locator("> summary").click();
  await expect(row.getByTestId("activity-record-body")).toBeVisible();
  const link = row.getByTestId("activity-evidence-link");
  const href = (await link.getAttribute("href"))!;
  expect(href).toMatch(/^\/trust\?view=evidence&entry=\d+&from=activity$/);
  const seq = /entry=(\d+)/.exec(href)![1];
  await link.click();
  await expect(page).toHaveURL(/\/trust\?view=evidence/);
  await expect(page.getByTestId(`trust-entry-${seq}`)).toHaveAttribute("aria-current", "true");
  await expect(page.getByTestId("trust-back")).toHaveText("Back to Activity");
  await page.getByTestId("trust-back").click();
  await expect(page).toHaveURL(/\/activity$/);
});

test("the failed sign-ins are one line apart from the real alert, their rows under a fold, and every row of the read is reachable with All and no search", async ({ page }, info) => {
  test.skip(isLive(info), "mock-mode spec: the recorded demo path");
  await approvedDay34(page);
  // The security scene in the mock puts the recorded 'security' books on the page: two refused sign-ins beside real alerts.
  await page.goto("/trust?view=security");
  await page.getByTestId("trust-security-run").click();
  await expect(page.locator('[data-testid^="event-SEC"]').first()).toBeVisible();
  await page.goto("/activity");
  await expect(page.getByTestId("activity-security")).toBeVisible();
  const benign = page.getByTestId("activity-benign");
  await expect(benign).toContainText("failed sign-in attempts today, all refused");
  await expect(benign.getByTestId("activity-benign-rows")).not.toHaveAttribute("open", "");
  await expect(page.getByTestId("activity-alert").first().getByTestId("activity-event")).toBeVisible();
  // Every row the read carries is on the page: the business rows, each alert, and the benign rows inside the fold (rendered, closed).
  const total = Number(/\d+/.exec((await page.getByTestId("activity-filter-all").textContent()) ?? "")![0]);
  await benign.getByTestId("activity-benign-rows").locator("> summary").click();
  const rendered = (await page.getByTestId("activity-row").count()) + (await page.getByTestId("activity-alert").count());
  expect(rendered).toBe(total);
  // A failed sign-in's evidence link lands on its event too, marked, with the security view showing every event.
  const attempts = page.getByTestId("activity-benign-rows").getByTestId("activity-row").first();
  await attempts.getByTestId("activity-evidence").locator("> summary").click();
  const authHref = (await attempts.getByTestId("activity-evidence-link").getAttribute("href"))!;
  const authId = /event=([^&]+)/.exec(authHref)![1];
  expect(authId).toMatch(/^SEC-AUTH-/);
  await attempts.getByTestId("activity-evidence-link").click();
  await expect(page.getByTestId(`event-${authId}`)).toHaveAttribute("aria-current", "true");
  await expect(page.getByText("No security events yet")).toHaveCount(0);
  await page.goto("/activity");
  await page.getByTestId("activity-benign-rows").locator("> summary").click();
  // An alert's evidence link names an event the security view has: it lands on it, marked.
  const alert = page.getByTestId("activity-alert").first();
  await alert.getByTestId("activity-evidence").locator("> summary").click();
  const href = (await alert.getByTestId("activity-evidence-link").getAttribute("href"))!;
  const id = /event=([^&]+)/.exec(href)![1];
  await alert.getByTestId("activity-evidence-link").click();
  await expect(page.getByTestId(`event-${id}`)).toHaveAttribute("aria-current", "true");
  await expect(page.getByTestId("trust-back")).toHaveText("Back to Activity");
});

test("search and each category only hide rows; a filter that leaves nothing says nothing was removed", async ({ page }, info) => {
  test.skip(isLive(info), "mock-mode spec: the recorded demo path");
  await approvedDay34(page);
  const total = await page.getByTestId("activity-row").count();
  const tabs = page.getByTestId("activity-filters").getByRole("tab");
  const n = await tabs.count();
  expect(n).toBeGreaterThan(1);
  for (let i = 1; i < n; i++) {
    await tabs.nth(i).click();
    expect(await page.getByTestId("activity-row").count()).toBeLessThanOrEqual(total);
  }
  await page.getByTestId("activity-filter-all").click();
  expect(await page.getByTestId("activity-row").count()).toBe(total);
  await page.getByTestId("activity-search").fill("Foshan");
  const found = await page.getByTestId("activity-row").count();
  expect(found).toBeGreaterThan(0);
  expect(found).toBeLessThan(total);
  await page.getByTestId("activity-search").fill("zzzz-nothing-matches");
  await expect(page.getByTestId("activity-filter-none")).toContainText("No entry was removed");
  await page.getByTestId("activity-search").fill("");
  expect(await page.getByTestId("activity-row").count()).toBe(total);
});

test("the set-aside line on Deals lands on the refused section of Activity", async ({ page }, info) => {
  test.skip(isLive(info), "mock-mode spec: the recorded demo path");
  await page.goto("/deals");
  const line = page.getByTestId("inbox-blocked");
  await expect(line).toBeVisible();
  const link = line.getByRole("link", { name: "See what was refused" });
  await expect(link).toHaveAttribute("href", "/activity#activity-refused");
  await link.click();
  await expect(page).toHaveURL(/\/activity#activity-refused/);
});

test("in Chinese the title, the search and the tabs are Chinese; at 390 px nothing scrolls sideways", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/activity");
  await expect(page.getByTestId("activity-read")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText("Activity");
  await expect(page.getByTestId("activity-search")).toHaveAttribute("placeholder", "搜索记录");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
});

test("the page's order: the state, then the search, then the business rows", async ({ page }) => {
  await page.goto("/activity");
  await expect(page.getByTestId("activity-read")).toBeVisible();
  const order = await page.evaluate(() => ["activity-state", "activity-search", "activity-list"].map((id) => document.querySelector(`[data-testid="${id}"]`)?.getBoundingClientRect().top ?? -1));
  expect(order[0]).toBeGreaterThan(-1);
  expect(order[0]).toBeLessThan(order[1]);
  expect(order[1]).toBeLessThan(order[2]);
});

test("the tour's Activity step names the fold the page has: Evidence, not Audit details", async ({ page }, info) => {
  test.skip(isLive(info), "mock-mode spec: the recorded demo path");
  await approvedDay34(page);
  const menu = page.getByTestId("account-menu");
  if ((await menu.count()) && !(await menu.evaluate((el) => (el as HTMLDetailsElement).open))) await menu.locator("> summary").click();
  await page.getByTestId("account-tour").locator("visible=true").first().click();
  const card = page.getByTestId("tour-card");
  // The tour walks the page part by part; the record's step is the one that names the fold.
  for (let i = 0; i < 8 && !(await card.innerText()).includes("The record"); i++) await page.getByTestId("tour-next").click();
  await expect(card).toContainText("The record");
  await expect(card).toContainText("Evidence shows");
  await expect(card).not.toContainText("Audit details");
  await expect(page.getByTestId("activity-evidence").first().locator("> summary")).toHaveText("Evidence");
});
