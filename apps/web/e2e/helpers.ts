import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { DEMO_TOKEN } from "./fixtures";

/**
 * The home's and Cash & funding's "Run funding plan" / "Queue it for my approval": the first press opens the confirmation,
 * the second sends the bound act. The alerts page's own button sends at once and does not use this.
 */
export async function runPlan(scope: Page | Locator, alertId: string): Promise<void> {
  await scope.getByTestId(`fix-open-${alertId}`).click();
  await scope.getByTestId(`fix-${alertId}`).click();
}

/**
 * Live mode shares one in-memory API across specs, so a spec that reads the books (alerts, what-if) resets
 * them first. In mock mode every browser context starts with an empty store, so this does nothing.
 */
export async function resetBooks(request: APIRequestContext): Promise<void> {
  if (test.info().project.name !== "live") return;
  const res = await request.post(`http://localhost:${process.env.E2E_API_PORT ?? 8000}/demo/reset`, {
    headers: { "X-Owner-Token": DEMO_TOKEN },
  });
  expect(res.ok()).toBeTruthy();
}

const BRAND_600 = "rgb(26, 95, 224)";

/** Visible elements filled with the brand blue: the page's primary actions. */
export async function filledBrand(page: Page): Promise<number> {
  return page.evaluate((brand) => {
    const visible = (el: Element) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
    };
    return Array.from(document.querySelectorAll("main button, main a")).filter((el) => visible(el) && getComputedStyle(el).backgroundColor === brand).length +
      Array.from(document.querySelectorAll('main [data-testid="home-review-primary"]')).filter((el) => visible(el) && getComputedStyle(el).backgroundColor === brand).length;
  }, BRAND_600);
}
