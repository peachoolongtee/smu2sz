import { expect, test } from "./fixtures";

/**
 * The Deals page lists every offer of the session (here EX01 and its reworded twin EX01B), newest first, and shows the picked
 * one's recommendation below. Mock mode: the guided demo is walked to step 11, where both offers are compiled and evaluated.
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
    await expect(row).toContainText("Day");
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

  const rewordedId = await reworded.getAttribute("data-offer-id");
  await reworded.click();
  await expect(reworded).toHaveAttribute("aria-pressed", "true");
  await expect(original).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByTestId("deal-recommendation")).toBeVisible();
  await expect.poll(() => page.evaluate(() => sessionStorage.getItem("tl-demo-v2"))).toContain(`"offerId":"${rewordedId}"`);
});
