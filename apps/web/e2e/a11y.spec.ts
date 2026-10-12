import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { resetBooks, runPlan, sendCounter } from "./helpers";
import { openStoryFold, STORY_STEPS } from "./helpers";

/**
 * The accessibility re-check (wayfinder #65 Wave 7, section 29): axe on every Business page and on the blocks added since the last
 * check (the execution summary, the approval terms, the receipt facts, the chase dialog, the decision page, the remaining task and Waiting on,
 * the chat panel, the Demo story), at the phone's 412 px and the desktop's 1440 px (the two projects). Zero serious or critical findings.
 * This is an automated rule check, one input to a review; it is not a claim of conformance to any standard, and it does not replace
 * a screen-reader session or a zoom and reflow check.
 */

async function scan(page: Page, label: string) {
  const result = await new AxeBuilder({ page }).analyze();
  const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  const text = bad.map((v) => `${v.id} (${v.impact}): ${v.help}\n  ${v.nodes.slice(0, 4).map((n) => n.target.join(" ")).join("\n  ")}`);
  expect(result.passes.length, `${label}: axe ran its rules`).toBeGreaterThan(10);
  expect(text, `${label}: serious or critical findings`).toEqual([]);
}

async function checkedDeal(page: Page) {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-recommendation")).toContainText(/Don't accept as asked|Counter instead of accepting as asked/);
}

async function advanceTo(page: Page, day: number) {
  await page.goto("/demo");
  await openStoryFold(page, "story-today");
  await page.getByTestId("home-days").fill(String(day));
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText(`Day ${day}`);
}

test.beforeEach(async ({ request }, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded pages, at the desktop and phone widths");
  await resetBooks(request);
});

test("Home, Cash, Receivables, Activity and Approvals at day 0", async ({ page }) => {
  for (const [path, ready] of [["/", "home-next-action"], ["/cash", "cash-options-list"], ["/receivables", "recv3-cards"], ["/activity", ""], ["/approvals", ""]] as const) {
    await page.goto(path);
    await expect(page.locator("h1").first()).toBeVisible();
    if (ready) await expect(page.getByTestId(ready).first()).toBeVisible({ timeout: 15_000 });
    await scan(page, path);
  }
});

test("Deals: the inbox, a checked deal with its priced response, and the decision page", async ({ page }) => {
  await page.goto("/deals");
  await expect(page.getByTestId("inbox-list")).toBeVisible();
  await scan(page, "/deals inbox");
  await checkedDeal(page);
  await scan(page, "/deals checked");
  // Everything the page folds, opened: the audit level is read too.
  const advanced = page.getByTestId("deal-advanced");
  await advanced.locator("summary").first().click();
  await page.getByTestId("deal-adv-audit_evidence").locator("summary").click();
  await scan(page, "/deals advanced open");
  await page.getByTestId("deal-audit-evidence").getByRole("link").first().click();
  await expect(page).toHaveURL(/\/decisions\//);
  await expect(page.locator("h1").first()).toBeVisible();
  await scan(page, "decision page");
});

test("contract ingestion and the send step: the documents and a review, the buyer choice, the deal summary, the borrower file", async ({ page }) => {
  await page.goto("/documents");
  await expect(page.getByTestId("fixture-read-FHR_SUPPLY_AGREEMENT")).toBeVisible();
  await scan(page, "/documents");
  await page.getByTestId("fixture-read-FHR_SUPPLY_AGREEMENT").click();
  await expect(page.getByTestId("doc-review")).toHaveAttribute("data-status", "PROPOSED");
  await scan(page, "/documents review");
  await checkedDeal(page);
  const response = page.locator("#counters");
  await response.getByTestId("deal-send").click();
  await response.getByTestId("deal-send-confirm-box").getByLabel("Holds firm").check();
  await scan(page, "/deals the send step");
  await response.getByTestId("deal-send-confirm-box").getByLabel("Open to a counter").check();
  await response.getByTestId("deal-send-confirm").click();
  await expect(page.getByTestId("deal-summary-BUYER-1")).toBeVisible();
  await scan(page, "/deals the deal summary");
  await page.getByTestId("deal-details-BUYER-1").locator("summary").click();
  await expect(page.getByTestId("deal-stages")).toBeVisible();
  await scan(page, "/deals the deal summary, unfolded");
  await page.goto("/capex");
  await page.getByRole("button", { name: "Evaluate the ¥600k machine" }).click();
  await page.getByTestId("capex-file").click();
  await expect(page.getByTestId("file-sections")).toBeVisible();
  await scan(page, "/capex the borrower file");
});

test("an approval waiting, the chase dialog and the remaining task at day 34", async ({ page }) => {
  await checkedDeal(page);
  await sendCounter(page.locator("#counters"));
  await advanceTo(page, 34);
  await page.goto("/");
  await expect(page.getByTestId("home-next-action")).toBeVisible();
  await scan(page, "/ day 34");
  await page.goto("/receivables");
  // The first action of the selected invoice: Chase payment, as it is overdue.
  const chase = page.locator('[data-testid^="chase-detail-CHASE-open-"]:visible').first();
  await expect(chase).toBeVisible();
  await scan(page, "/receivables day 34");
  await chase.click();
  await expect(page.locator('[data-testid^="chase-detail-CHASE-dialog-"][open]').first()).toBeVisible();
  await scan(page, "chase dialog");
  await page.keyboard.press("Escape");
  await page.goto("/activity");
  await expect(page.locator("h1").first()).toBeVisible();
  await scan(page, "/activity day 34");
});

test("the chat panel and the Demo story", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("chat-open").click();
  await expect(page.getByRole("dialog", { name: "Ask FLOW" })).toBeVisible();
  await scan(page, "chat panel");
  await page.keyboard.press("Escape");
  await page.goto("/demo");
  await expect(page.locator("h1").first()).toBeVisible();
  await scan(page, "/demo");
  // The guided story part-way through (the stepper bar is on every engine page).
  await page.goto("/mandate");
  for (let i = 0; i < 4; i++) {
    await page.getByTestId("demo-next").click();
    await expect(page.getByRole("region", { name: "Guided demo" }).locator("[aria-live=polite]")).toContainText(`step ${i + 1} of ${STORY_STEPS}`);
  }
  await scan(page, "Demo story, step 4");
});

test("the approval question, its decided card with the execution summary, the record, and Waiting on", async ({ page }) => {
  await advanceTo(page, 34);
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toBeVisible();
  await scan(page, "/ with an approval waiting");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  const card = page.locator("#approval-APR-000001");
  await expect(card).toBeVisible();
  await scan(page, "/approvals pending");
  await card.getByRole("button", { name: /^Approve/ }).click();
  await expect(card.getByTestId("approval-decided-APR-000001")).toBeVisible();
  await scan(page, "/approvals decided");
  await card.getByTestId("approval-record-APR-000001").click();
  await expect(page.getByTestId("record-state")).toBeVisible();
  await scan(page, "decision record");
  await page.goto("/");
  await expect(page.getByTestId("home-fact-arriving")).toBeVisible(); // the fact that says what is on its way
  await scan(page, "/ funding on its way");
  await page.goto("/cash");
  await expect(page.locator("h1").first()).toBeVisible();
  await scan(page, "/cash after the approval");
});

test("the remaining task, when the cure left the reserve short", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => sessionStorage.setItem("tl-mock-no-receipt", "residual"));
  await advanceTo(page, 34);
  await page.goto("/");
  await expect(page.getByTestId("home-remaining-text")).toBeVisible();
  await scan(page, "/ remaining task");
  await page.goto("/cash");
  await expect(page.getByTestId("home-remaining-text")).toBeVisible();
  await scan(page, "/cash remaining task");
});

test("keyboard: Tab reaches the primary action and shows a focus ring; every button has a name", async ({ page }) => {
  await page.goto("/");
  const alertId = await page.getByTestId("home-next-action").getAttribute("data-alert");
  const run = page.getByTestId(`fix-open-${alertId}`);
  for (let i = 0; i < 60; i++) {
    await page.keyboard.press("Tab");
    if (await run.evaluate((el) => el === document.activeElement)) break;
  }
  await expect(run).toBeFocused();
  // A visible ring: an outline or a box-shadow on the focused control.
  const ring = await run.evaluate((el) => {
    const c = getComputedStyle(el);
    return c.outlineStyle !== "none" && parseFloat(c.outlineWidth) > 0 ? "outline" : c.boxShadow !== "none" ? "shadow" : "none";
  });
  expect(ring).not.toBe("none");
  const unnamed = await page.evaluate(() =>
    Array.from(document.querySelectorAll("button, [role=button]"))
      .filter((el) => (el as HTMLElement).offsetParent !== null && !(el.getAttribute("aria-label") ?? el.textContent ?? "").trim() && !el.getAttribute("aria-labelledby"))
      .map((el) => el.outerHTML.slice(0, 80)),
  );
  expect(unnamed).toEqual([]);
});
