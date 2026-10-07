import { expect, test } from "./fixtures";
import { runPlan } from "./helpers";

// TEMPORARY: header layout check with a pending approval at several widths.
test("header fits with a pending approval", async ({ page }) => {
  test.skip(test.info().project.name !== "desktop");
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "business" })));
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("approvals-badge")).toBeVisible();
  for (const lang of ["en", "zh"]) {
    if (lang === "zh") { await page.evaluate(() => { for (const k of Object.keys(localStorage)) if (/lang/i.test(k)) console.log(k); }); }
    for (const w of [1024, 1180, 1280, 1440, 1535, 1536, 1792, 1920]) {
      await page.setViewportSize({ width: w, height: 900 });
      await page.waitForTimeout(150);
      const m = await page.evaluate(() => {
        const nav = document.querySelector("header nav") as HTMLElement;
        const badge = document.querySelector("[data-testid=approvals-badge]") as HTMLElement;
        const brand = document.querySelector("header a") as HTMLElement;
        const n = nav.getBoundingClientRect(), b = badge.getBoundingClientRect(), br = brand.getBoundingClientRect();
        return { clipped: nav.scrollWidth - nav.clientWidth, navRight: Math.round(n.right), badgeLeft: Math.round(b.left), brandRight: Math.round(br.right), navLeft: Math.round(n.left), badge: badge.innerText };
      });
      console.log(lang, w, JSON.stringify(m));
      await page.locator("header").screenshot({ path: `${process.env.SHOTS}/header-${lang}-${w}.png` });
      expect(m.clipped, `nav clipped at ${w}`).toBeLessThanOrEqual(0);
      expect(m.navRight).toBeLessThanOrEqual(m.badgeLeft);
      expect(m.brandRight).toBeLessThanOrEqual(m.navLeft + 4);
    }
    break;
  }
});
