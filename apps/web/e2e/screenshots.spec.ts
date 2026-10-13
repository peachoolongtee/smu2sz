import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { openStoryFold, runPlan, STORY_STEPS, verdictHeading, walkStory, openOperatorTools } from "./helpers";

/**
 * The screenshot walk of the brief's section 44: every Business page in every state the recorded demo path reaches, and the
 * Demo pages, captured full-page at the project's viewport (desktop 1440 px, phone Pixel 7). It runs only when SHOTS_DIR
 * names the folder to write into (`SHOTS_DIR=$PWD/../../docs/screenshots/<name> E2E_TARGET=mock pnpm exec playwright test
 * e2e/screenshots.spec.ts`); the ordinary e2e run skips it. Beside the images it writes `manifest.json` with each page's
 * height in viewport screens, the measure of the brief's section 36. It asserts nothing about the product.
 */
const dir = process.env.SHOTS_DIR;
test.skip(!dir, "set SHOTS_DIR to take the screenshots");

type Shot = { name: string; url: string; viewport: string; height: number; screens: number };
const shots: Shot[] = [];

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock mode only");
});

async function shoot(page: Page, name: string, project: string) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(300);
  const vp = page.viewportSize()!;
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  const file = join(dir!, project, `${name}.png`);
  mkdirSync(join(dir!, project), { recursive: true });
  await page.screenshot({ path: file, fullPage: true });
  shots.push({ name, url: page.url().replace(/^https?:\/\/[^/]+/, ""), viewport: `${vp.width}x${vp.height}`, height, screens: Math.round((height / vp.height) * 10) / 10 });
}

async function advanceTo34(page: Page) {
  await page.goto("/demo");
  await openStoryFold(page, "story-today");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
}

test.afterAll(() => {
  if (!dir || !shots.length) return;
  const project = shots.length ? (shots[0].viewport === "1440x900" ? "desktop" : "phone") : "unknown";
  writeFileSync(join(dir, project, "manifest.json"), JSON.stringify(shots, null, 2));
});

test("Business pages on the opening books, after the deal is read and checked, and after the funding plan ran", async ({ page }, testInfo) => {
  const p = testInfo.project.name;
  await page.goto("/");
  await shoot(page, "01-home-day0", p);
  await page.goto("/deals");
  await shoot(page, "02-deals-inbox", p);
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("deal-ask-quote")).toBeVisible();
  await shoot(page, "03-deals-read", p);
  await page.getByRole("button", { name: "Check against my limits" }).click();
  await expect(verdictHeading(page)).toBeVisible();
  await shoot(page, "04-deals-evaluated", p);
  await page.goto("/cash");
  await expect(page.getByTestId("cash-options-list")).toBeVisible();
  await shoot(page, "05-cash-day0", p);
  await page.goto("/receivables");
  await shoot(page, "06-receivables-day0", p);
  await page.goto("/activity");
  await shoot(page, "07-activity-day0", p);
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("fix-result")).toBeVisible();
  await shoot(page, "08-home-after-go-ahead", p);
  await page.goto("/");
  await shoot(page, "09-home-funded", p);
  await page.goto("/cash");
  // The plan ran, so the page states the current funding; the comparison is folded away.
  await expect(page.locator("#cash-current")).toBeVisible();
  await shoot(page, "10-cash-funded", p);
  await page.goto("/activity");
  await shoot(page, "11-activity-funded", p);
});

test("Business pages on day 34: the fix needs approval, waits, then is approved", async ({ page }, testInfo) => {
  const p = testInfo.project.name;
  await advanceTo34(page);
  await page.goto("/");
  await shoot(page, "12-home-day34", p);
  await page.goto("/receivables");
  await shoot(page, "13-receivables-day34", p);
  await page.goto("/cash");
  await expect(page.getByTestId("cash-headline")).toBeVisible();
  await shoot(page, "13b-cash-day34", p);
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toBeVisible();
  await shoot(page, "14-home-day34-pending", p);
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await expect(page).toHaveURL(/\/approvals/);
  await shoot(page, "15-approvals-pending", p);
  await page.locator("#approval-APR-000001").getByRole("button", { name: /^Approve/ }).click();
  await expect(page.locator("#approval-APR-000001")).toContainText("Approved");
  await shoot(page, "16-approvals-approved", p);
  await page.goto("/");
  await shoot(page, "17-home-day34-approved", p);
  await page.goto("/cash");
  // The plan ran, so the page states the current funding; the comparison is folded away.
  await expect(page.locator("#cash-current")).toBeVisible();
  await shoot(page, "18-cash-day34-approved", p);
  await page.goto("/activity");
  await shoot(page, "19-activity-day34-approved", p);
});

test("Demo pages: the story, the stepper before and after the walk, and the engine views", async ({ page }, testInfo) => {
  const p = testInfo.project.name;
  await page.goto("/demo");
  await shoot(page, "20-demo-story", p);
  await page.goto("/mandate");
  await shoot(page, "21-demo-mandate-start", p);
  await page.goto("/demo");
  await walkStory(page, STORY_STEPS);
  await shoot(page, "22-demo-stepper-last-step", p);
  await page.goto("/verdict");
  await shoot(page, "23-demo-verdict", p);
  await page.goto("/funding");
  await shoot(page, "24-demo-funding", p);
  await page.goto("/trajectory");
  await shoot(page, "25-demo-trajectory", p);
  await page.goto("/deals");
  await expect(page.getByTestId("inbox-msg-EX01")).toBeVisible();
  await shoot(page, "26-deals-two-offers-demo-walked", p);
});
