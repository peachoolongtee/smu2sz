import { test } from "./fixtures";
import { checkedDeal } from "./helpers";
// scratch only, never committed
test("shot", async ({ page }) => {
  test.skip(test.info().project.name !== "desktop");
  await checkedDeal(page);
  for (const v of (process.env.SHOT_VIEWS ?? "overview").split(",")) {
    await page.getByTestId("deal-tab-" + v).click();
    await page.waitForTimeout(700);
    if (process.env.SHOT_SCROLL) await page.getByTestId(process.env.SHOT_SCROLL).scrollIntoViewIfNeeded().then(() => page.evaluate(() => window.scrollBy(0, -160))).then(() => page.waitForTimeout(500));
    await page.screenshot({ path: "C:/Users/ian/AppData/Local/Temp/claude/C--Users-ian-Documents-Projects-smu2sz/30a88467-ee2d-4b9e-8bcf-aaa58c1419a6/scratchpad/r3-web/shot-" + v + "-" + (process.env.SHOT_TAG ?? "x") + ".png", fullPage: false });
    if (await page.getByTestId("deal-scope-terms").count()) await page.getByTestId("deal-scope-terms").screenshot({ path: "C:/Users/ian/AppData/Local/Temp/claude/C--Users-ian-Documents-Projects-smu2sz/30a88467-ee2d-4b9e-8bcf-aaa58c1419a6/scratchpad/r3-web/shot-" + v + "-" + (process.env.SHOT_TAG ?? "x") + ".png".replace(".png", "-terms.png") });
  }
});
