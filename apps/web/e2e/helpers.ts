import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { DEMO_TOKEN } from "./fixtures";

/**
 * The home's and Cash & funding's "Run funding plan" / "Queue it for my approval": the first press opens the confirmation,
 * the second sends the bound act. The alerts page's own button sends at once and does not use this.
 */
export async function runPlan(scope: Page | Locator, alertId: string): Promise<void> {
  // The Home's card opens the plan on Cash & funding ("Check funding plan"); the two presses are there. The owner comes back to the page they started on.
  if ("goto" in scope) {
    const check = scope.getByTestId("home-check-plan");
    if (await check.isVisible().catch(() => false)) {
      const from = scope.url();
      await check.click();
      await scope.waitForURL(/\/cash/);
      await scope.getByTestId(`fix-open-${alertId}`).click();
      await scope.getByTestId(`fix-${alertId}`).click();
      await expect(scope.getByTestId(`fix-${alertId}`)).toHaveCount(0);
      await scope.goto(from);
      return;
    }
  }
  await scope.getByTestId(`fix-open-${alertId}`).click();
  await scope.getByTestId(`fix-${alertId}`).click();
}

/** Cash keeps the plans it weighed in a fold (closed until asked for): "Every option considered" when a gap is open, "Other plans considered" once covered. Open it so the list can be read. */
export async function openCashOptions(page: Page): Promise<void> {
  const fold = page.getByTestId("cash-options-all").or(page.getByTestId("cash-options")).first();
  await expect(fold).toBeAttached();
  if (!(await fold.evaluate((el) => el.hasAttribute("open")))) await fold.locator("summary").first().click();
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
/** The ink primary of the owner's mockup language (Home and the pages that have taken it): the same one filled button. */
const INK_BUTTON = "rgb(23, 29, 30)";

/** Visible elements filled with the brand blue (or, inside the mockup scope, the ink button): the page's primary actions. */
export async function filledBrand(page: Page): Promise<number> {
  return page.evaluate((fills) => {
    const visible = (el: Element) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
    };
    return Array.from(document.querySelectorAll("main button, main a")).filter((el) => visible(el) && fills.includes(getComputedStyle(el).backgroundColor)).length +
      Array.from(document.querySelectorAll('main [data-testid="home-review-primary"]')).filter((el) => visible(el) && fills.includes(getComputedStyle(el).backgroundColor)).length;
  }, [BRAND_600, INK_BUTTON]);
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
    if ((await button.textContent())?.match(/Open the approval|Review the approval/)) {
      await button.click();
      await page.getByRole("button", { name: /^Authorize/ }).click();
      await expect(page.getByText("0 pending")).toBeVisible();
      // The approval is the step: the server moves the story on by itself once it is answered (there is no second press for it).
      await expect(button).not.toHaveText(/approval/i);
      continue;
    }
    await button.click();
    // The first step starts the story over: books with work on them (an earlier spec, on the shared live API) are listed first, and this is the owner's confirmation.
    const dialog = page.getByTestId("books-dialog");
    await dialog.waitFor({ state: "visible", timeout: 1500 }).catch(() => undefined);
    if (await dialog.isVisible()) await page.getByTestId("books-dialog-confirm").click();
    await expect(stripOf(page)).toContainText(/Scene \d of 6|All 6 scenes/);
    await expect(page.getByTestId("demo-next")).toBeEnabled();
  }
}

/**
 * The books of the optional scene "The buyer walks away", then "The same offer, other words": EX01 and its reworded twin evaluated on the opening
 * books, the hard-line buyer refused every counter and the gap funded anyway. It replaces the books, so the story is at its start afterwards.
 */
export async function walkAway(page: Page): Promise<void> {
  await page.goto("/demo");
  await openOperatorTools(page);
  await page.getByTestId("more-run-walk").click();
  await expect(page).toHaveURL(/\/verdict/);
  await page.goto("/demo");
  await openOperatorTools(page);
  await page.getByTestId("more-run-reworded").click();
  await expect(page).toHaveURL(/\/verdict/);
}

/** Send, from the open review: the receipt on screen is the review and the one commit button sends (the page's "Review and send the counter" opens it first; `openReview`). `scope` holds the button. */
export async function sendCounter(scope: Page | Locator): Promise<void> {
  await scope.getByTestId("deal-send").click();
}

/**
 * The Demo story page on a phone folds "More to show", "Today" and "The books" (one closed Disclosure each, `story-fold-<card id>`); a desktop shows them as
 * cards. Opens the named fold when there is one and it is closed, so a spec can reach the controls inside on either layout.
 */
export async function openStoryFold(page: Page, _card: "story-more" | "story-today" | "story-reset"): Promise<void> {
  // The clock, the books and the optional scenes all sit in the Demo's "Operator tools" fold now, on a phone and on a desktop alike.
  void _card;
  await openOperatorTools(page);
}

/** The open deal's heading: the selected negotiation's `h2` (the verdict in a few words). */
export const verdictHeading = (page: Page): Locator => page.getByTestId("queue-heading");

/** "Review and send the counter" opens the commitment receipt in place above the one commit button. Waits for it, then opens the review. */
export async function openReview(page: Page): Promise<void> {
  const review = page.getByTestId("queue-review-open");
  await review.waitFor();
  await review.click();
  await page.getByTestId("queue-review").waitFor();
}

/** The choices table (Deals redesign: it replaced the Compare responses tab) is the Overview's: goes to the Overview when another section is open and waits for the table, or the stacked cards on a phone. */
export async function openCompare(page: Page): Promise<void> {
  const tab = page.getByTestId("deal-tab-overview");
  if (await tab.count()) await tab.click();
  await page.locator('[data-testid="deal-choices-table"]:visible, [data-testid="deal-choices-stack"]:visible').first().waitFor();
}

/** The inbox card opens on Deals while nothing needs the owner and no negotiation is selected, and folds to one row otherwise: opens it when it is folded. */
export async function openInbox(page: Page): Promise<void> {
  const fold = page.getByTestId("inbox-back");
  await page.getByTestId("deals-inbox").waitFor();
  if (await fold.count()) await fold.click();
  await page.getByTestId("inbox-list").waitFor();
}

/**
 * The package offer read on Deals as the owner does it: the inbox's first message opens the negotiation (the address then names it), "Check against my limits" reads it against the
 * limits, and the decision level appears. Leaves the page on the selected negotiation.
 */
export async function checkedDeal(page: Page, message = "EX01"): Promise<void> {
  await page.goto("/deals");
  await openInbox(page);
  await page.getByTestId(`inbox-msg-${message}`).click();
  await page.getByTestId("queue-check-button").click();
  await page.getByTestId("queue-recommends").waitFor();
}

/**
 * The Demo page keeps its clock, its reset and the engine views in "Operator tools", closed until wanted. Opens the fold when the page is the Demo and it is closed,
 * so a spec can reach the day field (`home-days`, `home-advance`) there. Anywhere else there is nothing to open.
 */
export async function openOperatorTools(page: Page): Promise<void> {
  const fold = page.getByTestId("demo-operator-tools");
  if (!new URL(page.url()).pathname.startsWith("/demo")) return;
  await fold.waitFor();
  if (!(await fold.evaluate((el) => (el as HTMLDetailsElement).open))) await fold.locator("> summary").click();
}
