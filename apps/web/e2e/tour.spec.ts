import { expect, test } from "./fixtures";
import type { Page } from "@playwright/test";

/**
 * The tour's card must not cover the part it explains. The spotlight (`tour-hole`) and the card (`tour-card`) are read as rectangles at each step, on a desktop
 * window and on a phone. A part taller than the window leaves the card no free place at all; that one case is allowed to overlap.
 */

async function openAccountMenu(page: Page) {
  const menu = page.getByTestId("account-menu");
  const summaries = menu.locator("> summary");
  for (let i = 0; i < (await summaries.count()); i++) {
    if (await summaries.nth(i).isVisible()) {
      if (!(await menu.nth(i).evaluate((el) => (el as HTMLDetailsElement).open))) await summaries.nth(i).click();
      return;
    }
  }
}

async function overlapsAcrossSteps(page: Page): Promise<{ step: number; overlap: boolean; tall: boolean }[]> {
  const out: { step: number; overlap: boolean; tall: boolean }[] = [];
  const tour = page.getByTestId("tour");
  for (let step = 1; step <= 12; step++) {
    await expect(tour).toBeVisible();
    // Let the card settle on its place (the part scrolls into view first).
    await page.waitForTimeout(450);
    const hole = page.getByTestId("tour-hole");
    if (await hole.count()) {
      const [h, c] = [(await hole.boundingBox())!, (await page.getByTestId("tour-card").boundingBox())!];
      const overlap = h.x < c.x + c.width && c.x < h.x + h.width && h.y < c.y + c.height && c.y < h.y + h.height;
      const vh = page.viewportSize()!.height;
      out.push({ step, overlap, tall: h.height > vh - c.height - 32 });
    }
    const next = page.getByTestId("tour-next");
    const last = (await next.textContent())?.match(/finish|done|完成/i);
    await next.click();
    if (last) break;
  }
  return out;
}

for (const [name, size] of [
  ["1280 px", { width: 1280, height: 800 }],
  ["390 px", { width: 390, height: 844 }],
] as const) {
  test.describe(`the tour at ${name}`, () => {
    test.use({ viewport: size });
    for (const path of ["/", "/deals", "/cash", "/receivables"]) {
      test(`${path}: the step card does not cover its part`, async ({ page }) => {
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await openAccountMenu(page);
        await page.getByTestId("account-tour").locator("visible=true").first().click();
        const steps = await overlapsAcrossSteps(page);
        expect(steps.length).toBeGreaterThan(0);
        for (const s of steps) if (!s.tall) expect(s.overlap, `step ${s.step} of ${path}`).toBe(false);
      });
    }
  });
}
