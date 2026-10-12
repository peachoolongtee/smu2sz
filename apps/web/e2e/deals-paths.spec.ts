import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { filledBrand, resetBooks, sendCounter } from "./helpers";

/**
 * The Deals page's three paths on one chart (the offer as asked and the two replies), tied to three columns, with a day cursor you can step or play
 * through, and the reply in the one raised bar. Mock mode replays the recorded picture of the package offer (EX01): paths, moments and the axis are
 * the server's. Every word asserted here is the server's string.
 */

// Live mode keeps the books between tests: every test starts from the opening books (mock mode starts empty on its own).
test.beforeEach(async ({ request }) => {
  await resetBooks(request);
});

async function checked(page: Page) {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("paths-picture")).toBeVisible();
}

test("three ghosts, the recommended reply picked first, its thick line, its band and its reply in the bar", async ({ page }) => {
  await checked(page);
  for (const i of [0, 1, 2]) await expect(page.getByTestId(`path-ghost-${i}`)).toHaveCount(1);
  await expect(page.getByTestId("path-ghost-3")).toHaveCount(0);
  // The recommended path (Option A, the second column) is picked; the thick line is its own.
  const cols = page.getByTestId("path-columns");
  await expect(cols).toHaveAttribute("role", "radiogroup");
  await expect(page.getByTestId("path-col-pick-1")).toHaveAttribute("aria-checked", "true");
  await expect(page.getByTestId("path-col-pick-1")).toContainText("Showing on the chart");
  await expect(page.getByTestId("path-col-pick-0")).toContainText("Show this path");
  await expect(page.getByTestId("path-line")).toHaveCount(1);
  const key = await page.getByTestId("path-line").getAttribute("data-key");
  expect(key).toMatch(/^CTR-/);
  await expect(page.getByTestId("path-band")).toHaveCount(1);
  // The server's words for the band are always said, as the subtitle above the chart (the label inside the band is only where it fits).
  await expect(page.getByTestId("path-band-text")).toHaveText("The next invoice is paid 15 days sooner than as asked");
  await expect(page.getByTestId("path-lowest")).toContainText("Lowest ¥300k");
  // The bar: Option A's own sentence and the page's one filled call to action.
  const bar = page.getByTestId("path-reply");
  await expect(bar).toContainText("Your reply · Option A");
  await expect(bar).toContainText("Terms stay at 45 days, no rebate.");
  await expect(bar.getByTestId("deal-send")).toHaveText("Send Option A (simulated buyer reply)");
  // Business mode shows no id.
  await expect(page.locator("main")).not.toContainText("CTR-");
});

test("picking a column moves the thick line, the band and the reply bar; the asked path cannot be sent", async ({ page }) => {
  await checked(page);
  const line = page.getByTestId("path-line");
  const keyA = await line.getAttribute("data-key");
  const dA = await line.getAttribute("d");
  await page.getByTestId("path-col-pick-2").click();
  await expect(page.getByTestId("path-col-pick-2")).toHaveAttribute("aria-checked", "true");
  await expect(page.getByTestId("path-col-pick-1")).toHaveAttribute("aria-checked", "false");
  expect(await line.getAttribute("data-key")).not.toBe(keyA);
  expect(await line.getAttribute("d")).not.toBe(dA);
  await expect(page.getByTestId("path-band")).toHaveCount(1);
  const bar = page.getByTestId("path-reply");
  await expect(bar).toContainText("Your reply · Option B · you approve first");
  await expect(page.getByTestId("path-reply-text")).not.toBeEmpty();
  await expect(bar.getByTestId("deal-send-Option-B")).toHaveClass(/bg-brand-600/);
  // The asked path: its line is thick, its band is where it is under the minimum, and there is nothing to send.
  await page.getByTestId("path-col-pick-0").click();
  await expect(line).toHaveAttribute("data-key", "asked");
  await expect(page.getByTestId("path-band")).toHaveCount(1);
  await expect(page.getByTestId("path-band-text")).toHaveText("Below your minimum for 15 days");
  await expect(bar).toContainText("Not a reply you can send");
  await expect(bar).toContainText("Cannot be accepted within your signed limits.");
  await expect(bar.getByTestId("deal-send")).toHaveCount(0);
  await expect(bar.getByRole("button", { name: /^Send/ })).toHaveCount(0);
  // Back to the recommended reply from the bar.
  await bar.getByTestId("path-reply-back").click();
  await expect(page.getByTestId("path-col-pick-1")).toHaveAttribute("aria-checked", "true");
  await expect(bar.getByTestId("deal-send")).toBeVisible();
  // Pressing a path's end label picks its column too.
  await page.getByTestId("path-name-2").dispatchEvent("click");
  await expect(page.getByTestId("path-col-pick-2")).toHaveAttribute("aria-checked", "true");
  // A column is a radio: the arrow keys move the pick.
  await page.getByTestId("path-col-pick-2").focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByTestId("path-col-pick-1")).toHaveAttribute("aria-checked", "true");
});

test("each stop moves the cursor and changes every column's cash; the asked path says it is under the minimum at the decisive stop", async ({ page }) => {
  await checked(page);
  const stops = page.locator('[data-testid^="path-stop-"]');
  await expect(stops).toHaveCount(6);
  // The decisive moment (in 47 days) is selected first, and its words are the server's.
  await expect(page.getByTestId("path-stop-3")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-moment")).toContainText("In 47 days");
  await expect(page.getByTestId("path-moment")).toHaveAttribute("aria-live", "polite");
  await expect(page.getByTestId("path-col-cash-0")).toContainText("¥209,960.00");
  await expect(page.getByTestId("path-col-cash-0")).toContainText("Below your minimum");
  await expect(page.getByTestId("path-col-cash-1")).toContainText("¥631,972.23");
  await expect(page.getByTestId("path-col-cash-1")).not.toContainText("Below your minimum");
  const decisiveDay = await page.getByTestId("path-cursor").getAttribute("data-day");
  const before = await page.getByTestId("path-col-cash-0").innerText();
  await page.getByTestId("path-stop-0").click();
  await expect(page.getByTestId("path-stop-0")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-stop-3")).toHaveAttribute("aria-pressed", "false");
  expect(await page.getByTestId("path-cursor").getAttribute("data-day")).not.toBe(decisiveDay);
  await expect(page.getByTestId("path-col-cash-0")).toContainText("¥400,000.00");
  expect(await page.getByTestId("path-col-cash-0").innerText()).not.toBe(before);
  await expect(page.getByTestId("path-col-cash-0")).not.toContainText("Below your minimum");
  await expect(page.getByTestId("path-moment")).toContainText("Today");
  await page.getByTestId("path-stop-5").click();
  await expect(page.getByTestId("path-col-cash-2")).toContainText("¥");
});

test("Play steps through the moments and ends on the last stop; Stop halts it", async ({ page }) => {
  test.setTimeout(90_000);
  await checked(page);
  await page.getByTestId("path-play").click();
  await expect(page.getByTestId("path-play")).toContainText("Stop");
  await expect(page.getByTestId("path-stop-0")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-stop-1")).toHaveAttribute("aria-pressed", "true", { timeout: 6000 });
  // Stop halts it where it is.
  await page.getByTestId("path-play").click();
  await expect(page.getByTestId("path-play")).toContainText("Play the comparison");
  await page.waitForTimeout(2600);
  await expect(page.getByTestId("path-stop-1")).toHaveAttribute("aria-pressed", "true");
  // Play again runs to the end and stops there.
  await page.getByTestId("path-play").click();
  await expect(page.getByTestId("path-stop-5")).toHaveAttribute("aria-pressed", "true", { timeout: 20_000 });
  await expect(page.getByTestId("path-play")).toContainText("Play the comparison");
});

test("the send from the bar still records the agreement", async ({ page }) => {
  const agreedAt = { on: false, pictureRequests: 0 };
  page.on("request", (r) => {
    if (agreedAt.on && /\/offers\/[^/]+\/picture/.test(r.url())) agreedAt.pictureRequests += 1;
  });
  await checked(page);
  const bar = page.getByTestId("path-reply");
  await bar.getByTestId("deal-send").click();
  await expect(bar.getByTestId("deal-send-confirm-box")).toContainText("The buyer's reply is simulated");
  await bar.getByTestId("deal-send-confirm").click();
  await expect(page.getByTestId("deal-negotiation")).toContainText("The buyer accepted Option A. The agreement is on your books.");
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
  // Once the deal has an outcome the page no longer asks for the offer's picture (live: a real request; the mock answers in the browser).
  agreedAt.on = true;
  await page.waitForTimeout(1500);
  expect(agreedAt.pictureRequests, "no picture read after the deal is agreed").toBe(0);
  // The picture and its columns give way to the answer.
  await expect(page.getByTestId("deal-paths")).toHaveCount(0);
  await expect(page.locator("#commitments")).toContainText("0.85% off");
});

test("one heading, one filled primary, and the bar never covers the chart at 1280 x 800", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await checked(page);
  await expect(page.locator("h1")).toHaveCount(1);
  expect(await filledBrand(page)).toBe(1);
  // The bar is in flow: wherever the page is scrolled it is not over the chart.
  const overlap = async () =>
    page.evaluate(() => {
      const chart = document.querySelector('[data-testid="paths-picture"] svg')!.getBoundingClientRect();
      const bar = document.querySelector('[data-testid="path-reply"]')!.getBoundingClientRect();
      return Math.max(0, Math.min(chart.bottom, bar.bottom) - Math.max(chart.top, bar.top)) > 0;
    });
  for (const y of [0, 400, 800, 1200, 1600]) {
    await page.evaluate((top) => window.scrollTo(0, top), y);
    expect(await overlap(), `scrolled to ${y}`).toBe(false);
  }
  expect(await page.evaluate(() => getComputedStyle(document.querySelector('[data-testid="path-reply"]')!).position)).not.toBe("sticky");
});

test("on a phone the reply bar follows the heading, the chart keeps its stops and Play, and nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await checked(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  await expect(page.getByTestId("path-stops")).toBeVisible();
  await expect(page.getByTestId("path-play")).toBeVisible();
  const tops = await page.evaluate(() => ["deal-recommendation-card", "counters", "paths-picture", "path-columns"].map((id) => (document.getElementById(id) ?? document.querySelector(`[data-testid="${id}"]`))!.getBoundingClientRect().top + scrollY));
  expect(tops).toEqual([...tops].sort((a, b) => a - b));
  // Every stop and the two buttons reach 44 px.
  const short = await page.evaluate(() => Array.from(document.querySelectorAll('[data-testid^="path-stop-"], [data-testid="path-play"], [data-testid^="path-col-pick-"]')).filter((el) => el.getBoundingClientRect().height < 44).length);
  expect(short).toBe(0);
});

test("in Chinese the paths, the stops and the reply read in Chinese", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button").click();
  await expect(page.getByTestId("paths-picture")).toBeVisible();
  await expect(page.getByTestId("path-play")).toContainText("播放对比");
  await expect(page.getByTestId("path-col-pick-1")).toContainText("已显示在图上");
  await expect(page.getByTestId("path-col-cost-1")).toContainText("¥");
  await expect(page.getByTestId("path-moment")).toContainText(/[一-鿿]/);
  await expect(page.getByTestId("path-reply")).toContainText("你的回复");
  await expect(page.getByTestId("path-col-0")).toContainText(/[一-鿿]/);
  await expect(page.locator("h1")).toHaveCount(1);
});

test("the send and its confirmation are clicked the moment they appear, three times in a row, and never lose the click to a re-render", async ({ page, request }) => {
  test.setTimeout(120_000);
  for (let i = 0; i < 3; i++) {
    await resetBooks(request);
    await page.goto("/");
    await page.evaluate(() => sessionStorage.clear());
    await page.goto("/deals");
    await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
    await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
    // No wait for the chart: the reply area is a placeholder until the picture is read, then the bar; the send is clicked as soon as it is there.
    await sendCounter(page.getByTestId("path-reply"));
    await expect(page.getByTestId("deal-negotiation")).toContainText("The buyer accepted Option A", { timeout: 15_000 });
  }
});

test("while the picture is on its way the reply area is a placeholder, never the counter cards; then the paths and the bar arrive and stay", async ({ page }) => {
  if (test.info().project.name === "live") {
    await page.route("**/offers/*/picture*", async (route) => {
      await new Promise((r) => setTimeout(r, 1500));
      await route.continue();
    });
  } else {
    await page.addInitScript(() => sessionStorage.setItem("tl-mock-picture-slow", "1500"));
  }
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("paths-loading")).toBeVisible();
  await expect(page.getByTestId("deal-recommendation")).toBeVisible();
  // Neither the counter cards nor a send control exist while it loads.
  await expect(page.locator("#counters")).toHaveCount(0);
  await expect(page.getByTestId("deal-send")).toHaveCount(0);
  await expect(page.getByTestId("deal-option-Option-A")).toHaveCount(0);
  await expect(page.getByTestId("path-reply")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("paths-loading")).toHaveCount(0);
  // The bar keeps its identity when the stop or the pick changes: an open confirmation survives a stop.
  await page.getByTestId("path-reply").getByTestId("deal-send").click();
  await expect(page.getByTestId("deal-send-confirm-box")).toBeVisible();
  await page.getByTestId("path-stop-0").click();
  await expect(page.getByTestId("deal-send-confirm-box")).toBeVisible();
});
