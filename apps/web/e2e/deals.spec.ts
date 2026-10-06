import { expect, test } from "./fixtures";

/**
 * The Deals page lists every offer of the session (here EX01 and its reworded twin EX01B), newest first, and shows the picked
 * one's recommendation below. Mock mode: the guided demo is walked to step 11, where both offers are compiled and evaluated.
 * A second spec opens a message from the simulated inbox the way the owner does in Business mode (no stepper).
 */

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the demo walk is recorded");
});

test("the Deals page lists both offers and shows the picked one's recommendation", async ({ page }) => {
  await page.goto("/mandate");
  for (let i = 0; i < 11; i++) {
    const button = page.getByTestId("demo-next");
    await expect(button).toBeEnabled();
    await button.click();
    // Wait for the step to finish: a click while the stepper is busy is ignored.
    await expect(page.getByRole("region", { name: "Guided demo" }).locator("[aria-live=polite]")).toContainText(`${i + 1}/15`);
  }

  await page.goto("/deals");
  const rows = page.getByTestId("deal-row");
  await expect(rows).toHaveCount(2);
  for (const row of await rows.all()) {
    // Received on the clock's day: a distance from today, never "Day 0".
    await expect(row).toContainText("today");
    await expect(row).not.toContainText("Day");
    await expect(row.getByTitle(/ACCEPT|COUNTER|REJECT|NEEDS_OWNER_APPROVAL|NO_VERDICT/)).toBeVisible();
  }

  // Step 11 selected the reworded offer (the newest, so the first row); pick the original, then the reworded one again.
  const reworded = rows.nth(0);
  const original = rows.nth(1);
  await expect(reworded).toHaveAttribute("aria-pressed", "true");
  await original.click();
  await expect(original).toHaveAttribute("aria-pressed", "true");
  await expect(reworded).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByTestId("deal-recommendation")).toBeVisible();
  // The deal leads with its consequence; the recommendation, the glance and the active commitments follow.
  await expect(page.getByTestId("deal-consequence")).toContainText("off for early payment");
  await expect(page.getByTestId("verdict-glance")).toContainText("What they asked for");
  await expect(page.locator("#commitments")).toContainText("Active commitments");
  await expect(page.getByTestId("deal-steps").getByRole("link", { name: /Respond/ })).toHaveAttribute("href", "/deals#counters");
  await expect(page.getByTestId("deal-steps").getByRole("link", { name: /Agreed/ })).toHaveAttribute("href", "/deals#commitments");

  const rewordedId = await reworded.getAttribute("data-offer-id");
  await reworded.click();
  await expect(reworded).toHaveAttribute("aria-pressed", "true");
  await expect(original).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByTestId("deal-recommendation")).toBeVisible();
  await expect.poll(() => page.evaluate(() => sessionStorage.getItem("tl-demo-v2"))).toContain(`"offerId":"${rewordedId}"`);
});

test("opening a simulated inbox message reads it, then the deal leads with what it means for the owner", async ({ page }) => {
  await page.goto("/deals");
  await expect(page.getByRole("heading", { name: "Simulated inbox" })).toBeVisible();
  const inbox = page.getByTestId("inbox-list");
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Foshan Home Retail Co.");
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Li Wei");
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("11:30");
  // FastCapital is not a company in the owner's registry.
  await expect(inbox.getByTestId("inbox-msg-SEC")).toContainText("Not in your contacts");
  await expect(page.getByTestId("deal-steps")).toBeVisible();
  await expect(page.getByTestId("deal-consequence")).toHaveCount(0);

  // Opening a message reads it (no separate button) and offers the one next step.
  await inbox.getByTestId("inbox-msg-EX01").click();
  await expect(inbox.getByTestId("inbox-msg-EX01")).toHaveAttribute("aria-current", "true");
  await expect(page.getByTestId("deal-ask-TERMS_EXTENSION")).toBeVisible();
  const next = page.getByTestId("next-step");
  await expect(next).toContainText("Next step");
  await next.getByRole("button", { name: "Check against my limits" }).click();

  // Consequence first, then the recommendation, then the glance and the detail.
  await expect(page.getByTestId("deal-recommendation")).toBeVisible();
  const consequence = page.getByTestId("deal-consequence");
  await expect(consequence).toContainText("off for early payment");
  await expect(consequence).toContainText("off for early payment");
  await expect(page.getByTestId("deal-fact-cash")).toContainText(/unsafe (in|today|tomorrow)|stays safe/);
  await expect(page.getByTestId("deal-fact-cost")).toContainText("¥");
  await expect(page.getByTestId("deal-fact-counter")).toContainText("costs us");
  const glance = page.getByTestId("verdict-glance");
  for (const column of ["What they asked for", "What we would offer back"]) await expect(glance).toContainText(column);
  // The next step is now to answer the buyer, and it points at the counters.
  await expect(next).toContainText("offer back");
  await expect(next.getByRole("link", { name: "See what we'd offer back" })).toHaveAttribute("href", "#counters");
  await expect(page.locator("#counters")).toBeVisible();
  // The consequence sits above the recommendation card.
  const above = await consequence.boundingBox();
  const below = await page.locator("#deal-recommendation-card").boundingBox();
  expect(above!.y).toBeLessThan(below!.y);
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // Reading the same message again costs nothing: it is shown, not read twice.
  await inbox.getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("deal-row")).toHaveCount(0);
  await expect(inbox.getByTestId("inbox-msg-EX01")).toContainText("Showing below");
});
