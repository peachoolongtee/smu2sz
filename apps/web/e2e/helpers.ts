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

/** The guided Demo is eleven steps in six scenes (lib/demo.ts DEMO_STEPS): the late-payment loop. */
export const STORY_STEPS = 11;

/** The stepper's strip: its progress ("3/11"), the step's title and what the server told it. */
export const stripOf = (page: Page): Locator => page.getByRole("region", { name: "Guided demo" }).locator("[aria-live=polite]");

/**
 * Next, one press at a time, each waited for (a press while the stepper is busy is swallowed): steps `from + 1` to `from + steps` of the story.
 * The owner's own step (the eighth) is also pressed here, because its button is the owner's click; specs that are about that click do it themselves.
 */
export async function walkStory(page: Page, steps: number, from = 0): Promise<void> {
  for (let i = from; i < from + steps; i++) {
    const button = page.getByTestId("demo-next");
    await expect(button).toBeEnabled();
    await button.click();
    await expect(stripOf(page)).toContainText(`${i + 1}/${STORY_STEPS}`);
  }
}

/**
 * The books of the optional scene "The buyer walks away", then "The same offer, other words": EX01 and its reworded twin evaluated on the opening
 * books, the hard-line buyer refused every counter and the gap funded anyway. It replaces the books, so the story is at its start afterwards.
 */
export async function walkAway(page: Page): Promise<void> {
  await page.goto("/demo");
  await page.getByTestId("more-run-walk").click();
  await expect(page).toHaveURL(/\/verdict/);
  await page.goto("/demo");
  await page.getByTestId("more-run-reworded").click();
  await expect(page).toHaveURL(/\/verdict/);
}
