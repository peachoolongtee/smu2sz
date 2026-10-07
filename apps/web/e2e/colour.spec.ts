import type { Locator, Page } from "@playwright/test";
import { expect, test } from "./fixtures";

/**
 * The colour direction (docs/research/colour-direction-2026-10-08.md), as computed styles in mock mode: the deep hero on the
 * Home alone, a status pill that changes while the block does not, one filled brand button per Business page, the Demo's
 * own strip, no gradients, no status green on a channel chip or the owner's disc, and the text pairs on the hero at AA.
 */

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec");
});

const BRAND_900 = "rgb(11, 31, 77)";
const BRAND_600 = "rgb(21, 88, 192)";
const BAD_BRIGHT = "rgb(255, 180, 171)";

const bg = (l: Locator) => l.evaluate((el) => getComputedStyle(el).backgroundColor);
const color = (l: Locator) => l.evaluate((el) => getComputedStyle(el).color);

/** WCAG contrast of two "rgb(r, g, b)" strings (the second is composited as opaque). */
function contrast(a: string, b: string): number {
  const lum = (c: string) => {
    const [r, g, bl] = (c.match(/\d+/g) ?? ["0", "0", "0"]).slice(0, 3).map((n) => {
      const v = Number(n) / 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

/** Visible elements filled with the brand blue: the page's primary actions. */
async function filledBrand(page: Page): Promise<number> {
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

test("the Home hero is one solid deep block; the status is the pill, and the pill word is dark on a bright fill", async ({ page }) => {
  await page.goto("/");
  const hero = page.getByTestId("home-status");
  expect(await bg(hero)).toBe(BRAND_900);
  expect(await hero.evaluate((el) => getComputedStyle(el).backgroundImage)).toBe("none");
  const pill = page.getByTestId("home-status-word");
  expect(await bg(pill)).toBe(BAD_BRIGHT);
  // At AA: the headline and the muted note on the deep block, the pill word on its fill.
  expect(contrast(await color(page.getByTestId("home-headline")), BRAND_900)).toBeGreaterThan(4.5);
  expect(contrast(await color(page.getByTestId("home-note")), BRAND_900)).toBeGreaterThan(4.5);
  expect(contrast(await color(pill), BAD_BRIGHT)).toBeGreaterThan(4.5);
  // The figures that are the status wear the bright red; the reserve stays white.
  expect(contrast(await color(page.getByTestId("home-breach-cash")), BRAND_900)).toBeGreaterThan(4.5);
  expect(await color(page.getByTestId("home-breach-cash"))).toBe(BAD_BRIGHT);
  expect(await color(page.getByTestId("home-floor"))).toBe("rgb(255, 255, 255)");
  // Calm when healthy: the block stays navy, only the pill turns green.
  await page.getByTestId("fix-open-ALERT-RESERVE-12").click();
  await page.getByTestId("fix-ALERT-RESERVE-12").click();
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  expect(await bg(page.getByTestId("home-status"))).toBe(BRAND_900);
  expect(await bg(page.getByTestId("home-status-word"))).toBe("rgb(245, 185, 66)");
});

test("one filled brand button per Business page, no gradient anywhere, the deep block only on the Home", async ({ page }) => {
  for (const [path, expected, loaded] of [
    ["/", 1, "[data-testid=home-next-action]"],
    ["/cash", 1, "[data-testid=cash-forecast]"],
    ["/receivables", 0, "[data-testid=recv-summary]"],
    ["/activity", 0, "#activity-timeline"],
  ] as const) {
    await page.goto(path);
    await expect(page.locator(loaded)).toBeVisible();
    expect(await filledBrand(page), path).toBe(expected);
    const gradients = await page.evaluate(() => Array.from(document.querySelectorAll("*")).filter((el) => getComputedStyle(el).backgroundImage.includes("gradient")).length);
    expect(gradients, `${path} has a gradient`).toBe(0);
    if (path !== "/") expect(await page.locator('[data-testid="home-status"]').count()).toBe(0);
  }
  // Deals once a deal is evaluated: "Send this counter" is the one; the next-step link is not filled.
  await page.goto("/deals");
  await page.getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-send")).toBeVisible();
  expect(await filledBrand(page)).toBe(1);
  // The channel chip is neutral, not the "fine" green.
  expect(await bg(page.getByTestId("inbox-msg-EX01").locator("span").first())).toBe("rgb(238, 242, 246)");
});

test("the day-34 pending home has one primary: the decision, and the owner's disc is brand, not green", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await page.getByTestId("fix-open-ALERT-RESERVE-42").click();
  await page.getByTestId("fix-ALERT-RESERVE-42").click();
  await expect(page.getByTestId("home-review-primary")).toBeVisible();
  expect(await filledBrand(page)).toBe(1);
  const disc = page.getByTestId("account-menu").locator("summary span").first();
  expect(await bg(disc)).toBe("rgb(234, 241, 252)");
});

test("the Demo shell says so in its own deep strip; the Business shell has none", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("demo-strip")).toHaveCount(0);
  await page.goto("/demo");
  const strip = page.getByTestId("demo-strip");
  await expect(strip).toContainText("DEMO");
  await expect(strip).toContainText("Synthetic data. No real funds move.");
  expect(await bg(strip)).toBe(BRAND_900);
  await expect(page.getByTestId("home-status")).toHaveCount(0);
});
