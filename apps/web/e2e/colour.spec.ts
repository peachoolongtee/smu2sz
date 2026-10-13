import type { Locator } from "@playwright/test";
import { expect, test } from "./fixtures";
import { filledBrand, openReview } from "./helpers";

/**
 * The colour direction (docs/research/colour-direction-2026-10-08.md), as computed styles in mock mode: the Home headline on the
 * canvas with a light status pill and one frosted plan bar, one filled brand button per Business page, the Demo's
 * own strip, no gradients, no status green on a channel chip or the owner's disc, and the text pairs on the hero at AA.
 */

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec");
});

const BRAND_900 = "rgb(36, 50, 74)";
const BAD_SOLID = "rgb(210, 54, 42)";
const WARN_SOLID = "rgb(183, 121, 31)";
const CANVAS = "rgb(245, 247, 251)";

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

test("the Home headline sits on the canvas with no card; the status is a tone dot and its word, and the word and the text meet AA", async ({ page }) => {
  await page.goto("/");
  const hero = page.getByTestId("home-status");
  // No card, no deep block, no gradient: the header is transparent on the canvas.
  expect(await bg(hero)).toBe("rgba(0, 0, 0, 0)");
  expect(await hero.evaluate((el) => getComputedStyle(el).backgroundImage)).toBe("none");
  // The status is a tone dot and its word in sentence case (the Home hybrid): the dot is the status colour and meets 3:1 on the canvas, the word and the text meet AA on it.
  const word = page.getByTestId("home-status-word");
  const dot = page.getByTestId("home-status-dot");
  expect(await bg(dot)).toBe(BAD_SOLID);
  expect(contrast(await bg(dot), CANVAS)).toBeGreaterThan(3);
  expect(contrast(await color(word), CANVAS)).toBeGreaterThan(4.5);
  expect(contrast(await color(page.getByTestId("home-headline")), CANVAS)).toBeGreaterThan(4.5);
  // The headline is one colour: the server's sentence is never parsed or part-coloured.
  expect(await page.getByTestId("home-headline").evaluate((el) => el.children.length)).toBe(0);
  // The recommendation is the one tinted block (Home V2's DecisionHighlight): a solid fill with no frost, no gradient and no shadow; its one line meets AA on it.
  const bar = page.getByTestId("hv2-action");
  const fill = await bg(bar);
  expect(fill).not.toBe("rgba(0, 0, 0, 0)");
  expect(await bar.evaluate((el) => getComputedStyle(el).backdropFilter)).toBe("none");
  expect(await bar.evaluate((el) => getComputedStyle(el).backgroundImage)).toBe("none");
  expect(await bar.evaluate((el) => getComputedStyle(el).boxShadow)).toBe("none");
  expect(contrast(await color(page.getByTestId("home-action-text")), fill)).toBeGreaterThan(4.5);
  // Calm when healthy: the dot turns amber, and there is still no deep block.
  await page.getByTestId("fix-open-ALERT-RESERVE-12").click();
  await page.getByTestId("fix-ALERT-RESERVE-12").click();
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  expect(await bg(page.getByTestId("home-status"))).toBe("rgba(0, 0, 0, 0)");
  expect(await bg(page.getByTestId("home-status-dot"))).toBe(WARN_SOLID);
  expect(contrast(await bg(page.getByTestId("home-status-dot")), CANVAS)).toBeGreaterThan(3);
});

test("one filled brand button per Business page, no gradient anywhere, the deep block only in the Demo strip", async ({ page }) => {
  for (const [path, expected, loaded] of [
    ["/", 1, "[data-testid=home-next-action]"],
    ["/cash", 1, "[data-testid=cash-forecast]"],
    ["/receivables", 1, "[data-testid=recv3-page]"], // the one primary is "Explore the cash impact"
    ["/activity", 0, "#activity-timeline"],
  ] as const) {
    await page.goto(path);
    await expect(page.locator(loaded)).toBeVisible();
    expect(await filledBrand(page), path).toBe(expected);
    const gradients = await page.evaluate(() => Array.from(document.querySelectorAll("*")).filter((el) => getComputedStyle(el).backgroundImage.includes("gradient")).length);
    expect(gradients, `${path} has a gradient`).toBe(0);
    if (path !== "/") expect(await page.locator('[data-testid="home-status"]').count()).toBe(0);
  }
  // Deals once a deal is evaluated: "Send this counter" is the one; the page has no other filled button.
  await page.goto("/deals");
  await page.getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  // (the queue's card carries the one filled button, "Review and send the counter"; opened, the send takes its place)
  await openReview(page);
  await expect(page.getByTestId("deal-send")).toBeVisible();
  expect(await filledBrand(page)).toBe(1);
  // The channel chip is neutral, not the "fine" green (the inbox is one row until it is asked for).
  await page.getByTestId("inbox-back").click();
  expect(await bg(page.getByTestId("inbox-msg-EX01").locator("span").first())).toBe("rgb(239, 243, 248)");
});

test("the day-34 pending home has one primary: the decision, and the owner's disc is brand, not green", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await page.getByTestId("fix-open-ALERT-RESERVE-42").click();
  await page.getByTestId("fix-ALERT-RESERVE-42").click();
  await expect(page.getByTestId("alert-approval-link-ALERT-RESERVE-42")).toBeVisible();
  expect(await filledBrand(page)).toBe(1);
  const disc = page.getByTestId("account-menu").locator("summary span").first();
  expect(await bg(disc)).toBe("rgb(230, 241, 255)");
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
