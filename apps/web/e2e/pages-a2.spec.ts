import { expect, test } from "./fixtures";
import { filledBrand, runPlan } from "./helpers";

/**
 * Pages A1, part 2 (mock mode): every page touched by the second pass has one h1 (the page's own heading, or the server's sentence on Cash and
 * the question on Approvals), at most one brand-filled primary, and no horizontal scroll at 390 px.
 */
test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec");
});

const noSideScroll = (page: import("@playwright/test").Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

for (const [path, ready] of [
  ["/limits", "limits-rules"],
  ["/documents", "docs-list"],
  ["/whatif", "whatif-controls"],
  ["/capex", ""],
  ["/cash", "cash-forecast"],
] as const) {
  test(`${path}: one h1, at most one filled primary, no sideways scroll at 390 px`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(path);
    if (ready) await expect(page.getByTestId(ready).or(page.locator(`#${ready}`)).first()).toBeVisible();
    else await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    expect(await filledBrand(page)).toBeLessThanOrEqual(1);
    expect(await noSideScroll(page)).toBe(true);
  });
}

test("a decision's record: one h1, the waiting approval's review link is the one filled primary, no sideways scroll at 390 px", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toContainText("34");
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toBeVisible(); // the request has been answered before the page is left
  await page.goto("/decisions/" + encodeURIComponent("alert:ALERT-RESERVE-42:v7"));
  await expect(page.getByTestId("record-review")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  expect(await filledBrand(page)).toBe(1);
  expect(await noSideScroll(page)).toBe(true);
});
