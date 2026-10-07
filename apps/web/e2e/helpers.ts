import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";

/**
 * The home's and Cash & funding's "Run funding plan" / "Prepare it for my approval": the first press opens the
 * confirmation, the second sends the bound act. The alerts page's own button sends at once and does not use this.
 */
export async function runPlan(scope: Page | Locator, alertId: string): Promise<void> {
  await scope.getByTestId(`fix-open-${alertId}`).click();
  await scope.getByTestId(`fix-${alertId}`).click();
}
import { DEMO_TOKEN } from "./fixtures";

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
