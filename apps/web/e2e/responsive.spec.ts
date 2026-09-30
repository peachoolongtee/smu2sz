import { expect, test, type Page } from "@playwright/test";

/** Runs on a phone viewport (and desktop): no page may scroll sideways, and the stepper stays reachable. */

const ROUTES = ["/mandate", "/inbox", "/trajectory", "/funding", "/verdict", "/capex", "/ledger", "/approvals", "/security", "/evidence"];

async function overflowX(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

test("no page overflows horizontally after the demo has run", async ({ page }) => {
  await page.goto("/mandate");
  for (let i = 0; i < 15; i++) {
    const button = page.getByTestId("demo-next");
    await expect(button).toBeEnabled();
    await button.click();
  }
  await expect(page).toHaveURL(/\/evidence/);
  for (const route of ROUTES) {
    await page.goto(route);
    await expect(page.locator("h1")).toBeVisible();
    // Tables scroll inside their own region; the page itself must not.
    expect(await overflowX(page), `${route} overflows horizontally`).toBeLessThanOrEqual(1);
  }
});

test("the stepper and navigation are reachable", async ({ page }) => {
  await page.goto("/mandate");
  await expect(page.getByTestId("demo-next")).toBeInViewport();
  const menu = page.getByRole("button", { name: "Open navigation" });
  if (await menu.isVisible()) {
    await menu.click();
    await page.getByRole("link", { name: "Funding" }).click();
    await expect(page).toHaveURL(/\/funding/);
  } else {
    await page.getByRole("link", { name: "Funding" }).click();
    await expect(page).toHaveURL(/\/funding/);
  }
});
