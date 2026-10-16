import type { Locator } from "@playwright/test";
import { expect, test } from "./fixtures";
import { checkedDeal, filledBrand, openReview, openOperatorTools, runPlan } from "./helpers";

/**
 * The colour direction (docs/research/colour-direction-2026-10-08.md), as computed styles in mock mode: the Home headline on the
 * canvas with a light status pill and one frosted plan bar, one filled brand button per Business page, the Demo's
 * own strip, no gradients, no status green on a channel chip or the owner's disc, and the text pairs on the hero at AA.
 */

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec");
});

const BRAND_900 = "rgb(36, 50, 74)";
const CANVAS = "rgb(229, 232, 232)";
const PANEL = "rgb(248, 249, 249)";

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

test("the Home headline sits on the canvas with no card; the planned pill meets AA; the figures meet AA on the panel", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("hv2-plan-pill")).toBeVisible();
  const hero = page.getByTestId("home-status");
  // No card, no deep block, no gradient: the header is transparent on the owner's canvas.
  expect(await bg(hero)).toBe("rgba(0, 0, 0, 0)");
  expect(await hero.evaluate((el) => getComputedStyle(el).backgroundImage)).toBe("none");
  expect(await bg(page.locator("body"))).not.toBe("rgb(255, 255, 255)");
  expect(contrast(await color(page.getByTestId("home-headline")), CANVAS)).toBeGreaterThan(4.5);
  // The headline is one colour: the server's sentence is never parsed or part-coloured.
  expect(await page.getByTestId("home-headline").evaluate((el) => el.children.length)).toBe(0);
  // The planned pill is the lavender pair, AA.
  const planned = page.getByTestId("hv2-plan-pill");
  expect(await bg(planned)).toBe("rgb(235, 222, 250)");
  expect(contrast(await color(planned), await bg(planned))).toBeGreaterThan(4.5);
  // The cards are the panel tone, solid, with no frost and no gradient; the lowest figure is the one risk red and meets AA on the panel.
  const bar = page.getByTestId("hv2-action");
  const fill = await bg(bar);
  // The panel tone; while the cash would go negative the recommendation is an alarm card and takes the risk tint as its fill (owner, 15 Oct), with every text on it at 4.5:1.
  const alarm = (await bar.getAttribute("data-alarm")) === "true";
  if (alarm) {
    expect(fill).not.toBe(PANEL);
    const worst = await bar.evaluate((card) => {
      const c = document.createElement("canvas").getContext("2d", { willReadFrequently: true })!;
      const rgb = (css: string) => {
        c.clearRect(0, 0, 1, 1);
        c.fillStyle = "#000";
        c.fillStyle = css;
        c.fillRect(0, 0, 1, 1);
        return Array.from(c.getImageData(0, 0, 1, 1).data.slice(0, 3));
      };
      const lin = (v: number) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
      const lum = ([r, g, b]: number[]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
      // The ground of a text is the nearest solid fill under it (the card's tint, or a button's own fill).
      const groundOf = (el: Element) => {
        for (let n: Element | null = el; n; n = n.parentElement) {
          const b = getComputedStyle(n).backgroundColor;
          if (b !== "rgba(0, 0, 0, 0)" && b !== "transparent") return lum(rgb(b));
        }
        return lum(rgb(getComputedStyle(card).backgroundColor));
      };
      let min = 21;
      for (const el of Array.from(card.querySelectorAll("*"))) {
        if (![...el.childNodes].some((n) => n.nodeType === 3 && (n.textContent ?? "").trim())) continue;
        // The alarm strip is white on the solid risk red, not on the tint.
        if (el.closest('[data-testid="hv2-alarm"]')) continue;
        const fg = lum(rgb(getComputedStyle(el).color));
        const ground = groundOf(el);
        min = Math.min(min, (Math.max(fg, ground) + 0.05) / (Math.min(fg, ground) + 0.05));
      }
      return min;
    });
    expect(worst, "the lowest text contrast on the alarm tint").toBeGreaterThanOrEqual(4.5);
  } else expect(fill).toBe(PANEL);
  expect(await bar.evaluate((el) => getComputedStyle(el).backdropFilter)).toBe("none");
  expect(await bar.evaluate((el) => getComputedStyle(el).backgroundImage)).toBe("none");
  expect(await bar.evaluate((el) => getComputedStyle(el).borderTopLeftRadius)).toBe("24px");
  expect(await bar.evaluate((el) => getComputedStyle(el).boxShadow)).toContain("rgba(0, 0, 0, 0.08) 0px 1px 2px -1px");
  if (!alarm) expect(contrast(await color(page.getByTestId("home-action-text")), fill)).toBeGreaterThan(4.5); // on the alarm tint every text is measured above
  expect(await color(page.getByTestId("home-kpi-lowest-value"))).toBe("rgb(168, 50, 34)");
  expect(contrast(await color(page.getByTestId("home-kpi-lowest-value")), PANEL)).toBeGreaterThan(4.5);
  // The one filled button is the ink primary with white text.
  const run = page.getByTestId("home-check-plan"); // the Home card opens the plan on Cash; the ink primary is the same
  expect(await bg(run)).toBe("rgb(23, 29, 30)");
  expect(contrast(await color(run), await bg(run))).toBeGreaterThan(7);
  // Calm when healthy: the pill turns to the status word, and there is still no deep block.
  await runPlan(page, "ALERT-RESERVE-12");
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  expect(await bg(page.getByTestId("home-status"))).toBe("rgba(0, 0, 0, 0)");
  await expect(page.getByTestId("hv2-action")).toBeVisible();
});

test("one filled brand button per Business page, no gradient anywhere, the deep block only in the Demo strip", async ({ page }) => {
  for (const [path, expected, loaded] of [
    ["/", 1, "[data-testid=home-next-action]"],
    ["/cash", 1, "[data-testid=cash-forecast]"],
    ["/receivables", 0, "[data-testid=recv3-page]"], // the customers' list has no primary
    ["/receivables?customer=BUYER-1", 1, "[data-testid=recv3-page]"], // a customer's page: the one primary is "Explore the cash impact"
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
  await checkedDeal(page);
  // The deal header carries the one filled button, "Review the counter"; opened, "Copy the message" takes its place (the page has no other filled button; the simulated send is the Demo's).
  expect(await filledBrand(page)).toBe(1);
  await openReview(page);
  await expect(page.getByTestId("buyer-message-copy")).toBeVisible();
  expect(await filledBrand(page)).toBe(1);
  // The channel chip is neutral, not the "fine" green (the inbox is one row until it is asked for).
  await page.getByTestId("deal-tab-messages").click();
  expect(await bg(page.getByTestId("inbox-msg-EX01").locator("span").first())).not.toBe("rgb(226, 246, 243)");
});

test("the day-34 pending home has one primary: the decision, and the owner's disc is brand, not green", async ({ page }) => {
  await page.goto("/demo");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/cash"); // the plan is run, and its waiting approval is linked, on Cash & funding
  await runPlan(page, "ALERT-RESERVE-42");
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

test("after the plan ran, the covered Home has no gradient anywhere and its title is solid ink", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-check-plan")).toBeVisible();
  await runPlan(page, "ALERT-RESERVE-12"); // the plan is run on Cash; the owner is back on the Home
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "covered");
  const gradients = await page.evaluate(() => Array.from(document.querySelectorAll("*")).filter((el) => getComputedStyle(el).backgroundImage.includes("gradient")).map((el) => el.getAttribute("data-testid") ?? el.tagName));
  expect(gradients, "gradients on the covered Home").toEqual([]);
  // The card's title is solid ink, not clipped text.
  const title = page.locator("#hv2-covered-title");
  expect(await title.evaluate((el) => getComputedStyle(el).backgroundImage)).toBe("none");
  expect(await title.evaluate((el) => getComputedStyle(el).color)).toBe(await page.getByTestId("home-headline").evaluate((el) => getComputedStyle(el).color)); // the ink of the headline
});
