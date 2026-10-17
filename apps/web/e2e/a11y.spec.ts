import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { checkedDeal, demoMode, openCompare, openInbox, openOperatorTools, openReview, resetBooks, runPlan, sendCounter } from "./helpers";
import { openStoryFold } from "./helpers";

/**
 * The accessibility re-check (wayfinder #65 Wave 7, section 29): axe on every Business page and on the blocks added since the last
 * check (the execution summary, the approval terms, the receipt facts, the chase dialog, the decision page, the remaining task and Waiting on,
 * the chat panel, the Demo story), at the phone's 412 px and the desktop's 1440 px (the two projects). Zero serious or critical findings.
 * This is an automated rule check, one input to a review; it is not a claim of conformance to any standard, and it does not replace
 * a screen-reader session or a zoom and reflow check.
 */

async function scan(page: Page, label: string) {
  // Under reduced motion only opacity transitions remain (a fold opening fades in): axe must read the settled colours, not a frame of the fade.
  // Read the page until nothing in it is running (a fresh read each time). Awaiting the `finished` promises of the animations present at one instant can wait for ever on one whose
  // element the router removes half way through its fade (a detached animation never settles); an animation that really never ends still fails here.
  await expect.poll(() => page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length), { message: `${label}: animations still running` }).toBe(0);
  const result = await new AxeBuilder({ page }).analyze();
  const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  const text = bad.map((v) => `${v.id} (${v.impact}): ${v.help}\n  ${v.nodes.slice(0, 4).map((n) => n.target.join(" ")).join("\n  ")}`);
  expect(result.passes.length, `${label}: axe ran its rules`).toBeGreaterThan(10);
  expect(text, `${label}: serious or critical findings`).toEqual([]);
}

async function advanceTo(page: Page, day: number) {
  await page.goto("/demo");
  await openStoryFold(page, "story-today");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill(String(day));
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText(`Day ${day}`);
}

test.beforeEach(async ({ request }, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded pages, at the desktop and phone widths");
  await resetBooks(request);
});

test("Home, Cash, Receivables, Activity, Approvals and the customer overview at day 0", async ({ page }) => {
  for (const [path, ready] of [["/", "home-next-action"], ["/cash", "cash-summary"], ["/receivables", "recv3-page"], ["/activity", ""], ["/approvals", ""], ["/customers/BUYER-1", "customer-figures"], ["/customers/BUYER-1/inputs", "inputs-sheet"]] as const) {
    await page.goto(path);
    await expect(page.locator("h1").first()).toBeVisible();
    if (ready) await expect(page.getByTestId(ready).first()).toBeVisible({ timeout: 15_000 });
    await scan(page, path);
  }
});

test("Deals: the inbox, a checked deal with its priced response, and the decision page", async ({ page }) => {
  await page.goto("/deals");
  await expect(page.getByTestId("deals-list-view")).toBeVisible();
  await openInbox(page);
  await scan(page, "/deals inbox");
  await checkedDeal(page);
  await scan(page, "/deals checked");
  // Everything the page opens on request: the receipt, the full table of responses and the deal's chart, then the decision page the record lives on.
  await openReview(page);
  await scan(page, "/deals the receipt");
  await openCompare(page);
  await scan(page, "/deals compare open");
  await page.getByTestId("deal-tab-cash").click();
  await expect(page.getByTestId("deal-chart")).toBeVisible();
  await scan(page, "/deals cash impact: outcomes, chart and scenarios open");
  const offerId = await page.evaluate(() => JSON.parse(sessionStorage.getItem("tl-demo-v3") ?? "{}").offerId as string);
  await page.goto(`/decisions/${encodeURIComponent(`deal:${offerId}`)}`);
  await expect(page).toHaveURL(/\/decisions\//);
  await expect(page.locator("h1").first()).toBeVisible();
  await scan(page, "decision page");
});

test("contract ingestion and the send step: the documents and a review, the buyer choice, the deal summary, the borrower file", async ({ page }) => {
  await demoMode(page); // the simulated send is the Demo's only
  await page.goto("/documents");
  await expect(page.getByTestId("doc-dropzone")).toBeVisible();
  await scan(page, "/documents");
  // The upload's own message (no company typed yet), then a review. The mock reads no uploaded file, so the review is a
  // demo document the owner confirmed; a new reading waiting for a decision is covered by documents.spec.ts in the live project.
  await page.getByTestId("doc-upload").click();
  await expect(page.locator("#docs-read").getByRole("alert")).toBeVisible();
  await scan(page, "/documents upload message");
  await page.getByTestId("doc-row-DOC-000001").getByRole("button").click();
  await expect(page.getByTestId("doc-review")).toHaveAttribute("data-status", "CONFIRMED");
  await scan(page, "/documents review");
  await checkedDeal(page);
  await openReview(page);
  await scan(page, "/deals the send step");
  await sendCounter(page);
  // The agreements in force are under the list: All deals brings it back.
  await page.getByTestId("deal-back-all").click();
  // Each agreement is a folded row; opening it shows its terms and the deal summary.
  await page.locator("#commitments").getByTestId("commitment-toggle").first().click();
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
  await demoMode(page); // the simulated send is the Demo's only
  await checkedDeal(page);
  await openReview(page);
  await sendCounter(page);
  await advanceTo(page, 34);
  await page.goto("/");
  await expect(page.getByTestId("home-next-action")).toBeVisible();
  await scan(page, "/ day 34");
  await page.goto("/receivables?customer=BUYER-1"); // /receivables lists customers; the customer's page holds its invoices
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
    await expect(page.getByRole("region", { name: "Guided demo" }).locator("[aria-live=polite]")).toContainText(/Scene \d of 6|All 6 scenes/);
  }
  await scan(page, "Demo story, step 4");
});

test("the approval question, its decided card with the execution summary, the record, and Waiting on", async ({ page }) => {
  await advanceTo(page, 34);
  await page.goto("/cash"); // the plan is run on Cash & funding
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toBeVisible();
  await scan(page, "/cash with an approval waiting");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  const card = page.locator("#approval-APR-000001");
  await expect(card).toBeVisible();
  await scan(page, "/approvals pending");
  await card.getByRole("button", { name: /^Authorize/ }).click();
  await expect(card.getByTestId("approval-decided-APR-000001")).toBeVisible();
  await scan(page, "/approvals decided");
  await card.getByTestId("approval-record-APR-000001").click();
  await expect(page.getByTestId("record-state")).toBeVisible();
  await scan(page, "decision record");
  await page.goto("/");
  await expect(page.getByTestId("home-v2-action")).toBeVisible(); // the recommendation card is on the Home
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
  await expect(page.getByTestId("home-v2")).toBeVisible();
  await scan(page, "/ after a cure that left the reserve short");
  await page.goto("/cash");
  await expect(page.getByTestId("home-remaining-text")).toBeVisible();
  await scan(page, "/cash remaining task");
});

test("keyboard: Tab reaches the primary action and shows a focus ring; every button has a name", async ({ page }) => {
  await page.goto("/");
  const run = page.getByTestId("home-check-plan"); // the Home card is the plan's way in; its two presses are on Cash
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
