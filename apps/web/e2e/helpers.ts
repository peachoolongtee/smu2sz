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

const BRAND_600 = "rgb(3, 104, 233)";

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
    // The owner's step: the strip only opens the approval; the decision is the card's one filled Approve, and then the strip moves the story on.
    if ((await button.textContent())?.includes("Open the approval")) {
      await button.click();
      await page.getByRole("button", { name: /^Approve/ }).click();
      await expect(page.getByText("0 pending")).toBeVisible();
      await expect(button).toHaveText("Next");
    }
    await button.click();
    await expect(stripOf(page)).toContainText(`step ${i + 1} of ${STORY_STEPS}`);
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

/** A counter's Send asks once, as Home's Run does: the first press shows what will happen, the second sends exactly that. `scope` holds the button. */
export async function sendCounter(scope: Page | Locator, option = ""): Promise<void> {
  await scope.getByTestId(option ? `deal-send-${option}` : "deal-send").click();
  await scope.getByTestId(option ? `deal-send-confirm-${option}` : "deal-send-confirm").click();
}

/**
 * The Demo story page on a phone folds "More to show", "Today" and "The books" (one closed Disclosure each, `story-fold-<card id>`); a desktop shows them as
 * cards. Opens the named fold when there is one and it is closed, so a spec can reach the controls inside on either layout.
 */
export async function openStoryFold(page: Page, card: "story-more" | "story-today" | "story-reset"): Promise<void> {
  // Below 1024 px the page swaps the cards for folds once it has hydrated; wait for them rather than find the cards still there.
  if ((page.viewportSize()?.width ?? 1440) >= 1024) return;
  const fold = page.getByTestId(`story-fold-${card}`);
  await expect(fold).toBeAttached();
  if (!(await fold.evaluate((el) => (el as HTMLDetailsElement).open))) await fold.locator("> summary").click();
}
