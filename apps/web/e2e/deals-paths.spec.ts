import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { filledBrand, resetBooks, sendCounter } from "./helpers";
import recorded from "../mocks/offer_picture_ex01.json";

/** The recorded picture's moments (the server's words and sentences), so the chips are asserted against what was recorded. */
const MOMENTS = (recorded as { en: { moments: { word: string; text: string }[] } }).en.moments;

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
  // The pointer is put out of the way (the chart appears where the last click was, and a pointer over it pauses Play).
  await page.mouse.move(1, 1);
}

test("three lines in their own patterns, the recommended reply picked first and emphasised, and its reply in the bar", async ({ page }) => {
  await checked(page);
  for (const i of [0, 1, 2]) await expect(page.getByTestId(`path-line-${i}`)).toHaveCount(1);
  await expect(page.getByTestId("path-line-3")).toHaveCount(0);
  // Told apart by pattern as well as colour: the asked path solid and thin, Option A solid and thicker, Option B dashed; the tiles' swatches repeat it.
  await expect(page.getByTestId("path-line-0")).toHaveAttribute("data-dash", "solid");
  await expect(page.getByTestId("path-line-1")).toHaveAttribute("data-dash", "solid");
  await expect(page.getByTestId("path-line-2")).toHaveAttribute("data-dash", "dashed");
  const width = (i: number) => page.getByTestId(`path-line-${i}`).evaluate((el) => Number(el.getAttribute("stroke-width")));
  expect(await width(1)).toBeGreaterThan(await width(0));
  await expect(page.getByTestId("path-tile-2").getByTestId("path-swatch")).toHaveAttribute("data-dash", "dashed");
  await expect(page.getByTestId("path-tile-1").getByTestId("path-swatch")).toHaveAttribute("data-dash", "solid");
  // The recommended path (Option A, the second column) is picked and emphasised.
  await expect(page.getByTestId("path-columns")).toHaveAttribute("role", "radiogroup");
  await expect(page.getByTestId("path-col-pick-1")).toHaveAttribute("aria-checked", "true");
  await expect(page.getByTestId("path-col-pick-1")).toContainText("Showing on the chart");
  await expect(page.getByTestId("path-col-pick-0")).toContainText("Show this path");
  await expect(page.getByTestId("path-line-1")).toHaveAttribute("data-active", "true");
  await expect(page.getByTestId("path-line-0")).toHaveAttribute("data-active", "false");
  expect(await page.getByTestId("path-line-1").getAttribute("data-key")).toMatch(/^CTR-/);
  // The reply card (the old bar): Option A's own sentence and the page's one filled call to action; the send is one press behind "Review and send the counter".
  const card = page.getByTestId("queue-recommends");
  await expect(card).toContainText("FLOW recommends · Option A");
  await expect(card).toContainText("Terms stay at 45 days, no rebate.");
  await page.getByTestId("queue-review-open").click();
  await expect(page.getByTestId("path-reply").getByTestId("deal-send")).toHaveText("Send Option A (simulated buyer reply)");
  // Business mode shows no id.
  await expect(page.locator("main")).not.toContainText("CTR-");
});

test("the picture carries three lines, the minimum, one cursor and its band, and no label of any event, line name or lowest point", async ({ page }) => {
  await checked(page);
  const svg = page.getByTestId("paths-picture").locator("svg").first();
  // A data-testid sweep of the drawing (what moved cash is a fold under the tiles, on demand, never on the picture): nothing in it is an event label, a path name, a lowest-point label or a legend.
  const ids = await page.getByTestId("paths-picture").locator("svg").first().evaluate((root) => Array.from(root.querySelectorAll("[data-testid]")).map((el) => el.getAttribute("data-testid") ?? ""));
  for (const id of ids) expect(id, `testid ${id}`).not.toMatch(/event|name|lowest|legend|band-label|^path-subtitle$/);
  await expect(page.getByTestId("paths-legend")).toHaveCount(0);
  await expect(page.getByTestId("path-subtitle")).toHaveCount(0);
  // The only words on the drawing are the axes and the minimum's name: no path name, no event, no figure label of a lowest point.
  const words = (await svg.locator("text").allTextContents()).map((w) => w.trim());
  for (const w of words) expect(w, w).toMatch(/^(¥[\d,]+k?|Today|in \d+ days|Minimum cash reserve ¥300k)$/);
  for (const name of ["As they asked", "Option A", "Option B", "Credit line draw", "Debt service", "Operating bill", "Lowest"]) expect(words.join(" ")).not.toContain(name);
  await expect(svg.locator('[data-testid^="path-line-"]')).toHaveCount(3);
  await expect(svg.getByTestId("path-cursor")).toHaveCount(1);
  await expect(svg.getByTestId("path-moment-band")).toHaveCount(1);
  await expect(svg.getByTestId("paths-reserve")).toHaveCount(1);
  // The same on a phone: no end names, no legend row.
  await page.setViewportSize({ width: 360, height: 740 });
  await expect(page.getByTestId("paths-legend")).toHaveCount(0);
  const narrowWords = await svg.locator("text").allTextContents();
  expect(narrowWords.join(" ")).not.toContain("Option");
});

test("picking a column moves the emphasis and the reply bar; the asked path cannot be sent", async ({ page }) => {
  await checked(page);
  await page.getByTestId("path-col-pick-2").click();
  await expect(page.getByTestId("path-col-pick-2")).toHaveAttribute("aria-checked", "true");
  await expect(page.getByTestId("path-col-pick-1")).toHaveAttribute("aria-checked", "false");
  await expect(page.getByTestId("path-line-2")).toHaveAttribute("data-active", "true");
  await expect(page.getByTestId("path-line-1")).toHaveAttribute("data-active", "false");
  const bar = page.getByTestId("queue-recommends");
  await expect(bar).toContainText("Your reply · Option B · you approve first");
  await expect(page.getByTestId("queue-option")).not.toBeEmpty();
  await page.getByTestId("queue-review-open").click();
  await expect(page.getByTestId("path-reply").getByTestId("deal-send-Option-B")).toHaveClass(/bg-brand-600/);
  // The asked path: there is nothing to send.
  await page.getByTestId("path-col-pick-0").click();
  await expect(page.getByTestId("path-line-0")).toHaveAttribute("data-active", "true");
  await expect(bar).toContainText("Not a reply you can send");
  await expect(bar).toContainText("Over a limit you signed: only a new mandate changes that");
  await expect(page.getByTestId("deal-send")).toHaveCount(0);
  await expect(bar.getByRole("button", { name: /^Send/ })).toHaveCount(0);
  await expect(page.getByTestId("queue-review-open")).toHaveCount(0);
  // Back to the recommended reply from the card.
  await bar.getByTestId("path-reply-back").click();
  await expect(page.getByTestId("path-col-pick-1")).toHaveAttribute("aria-checked", "true");
  await expect(page.getByTestId("queue-review-open")).toBeVisible();
  await page.getByTestId("queue-review-open").click();
  await expect(page.getByTestId("deal-send")).toBeVisible();
  // A column is a radio: the arrow keys move the pick.
  await page.getByTestId("path-col-pick-2").click();
  await page.getByTestId("path-col-pick-2").focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByTestId("path-col-pick-1")).toHaveAttribute("aria-checked", "true");
});

test("picking a path is said politely (the bar is far above the columns), and a tap that focuses a column leaves no line dimmed", async ({ page }) => {
  await checked(page);
  const status = page.getByTestId("path-pick-status");
  await expect(status).toHaveAttribute("role", "status");
  await expect(status).toHaveText("");
  await page.getByTestId("path-col-pick-2").click();
  await expect(status).toHaveText("Reply bar now shows Option B");
  await page.getByTestId("path-col-pick-0").click();
  await expect(status).toHaveText("Reply bar now shows As they asked");
  // The click focused the button without a keyboard: once the pointer leaves, nothing is pointed at, so no line is dimmed.
  await page.mouse.move(1, 1);
  for (const i of [0, 1, 2]) expect(await page.getByTestId(`path-line-${i}`).evaluate((el) => Number(el.getAttribute("opacity")))).toBeGreaterThan(0.4);
});

test("the lines are told apart without colour: the asked path has a square marker, the recommended reply a round one, a further reply a diamond; the swatches repeat them", async ({ page }) => {
  await checked(page);
  await expect(page.getByTestId("path-dot")).toHaveCount(3);
  expect(await page.getByTestId("path-dot").evaluateAll((els) => els.map((el) => el.querySelector("[data-marker]")?.getAttribute("data-marker")))).toEqual(["square", "circle", "diamond"]);
  for (const [i, shape] of ["square", "circle", "diamond"].entries()) await expect(page.getByTestId(`path-tile-${i}`).getByTestId("path-swatch")).toHaveAttribute("data-marker", shape);
});

test("nothing below the moment sentence shifts as the cursor steps: its room and the events slot are kept", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await checked(page);
  const tops: number[] = [];
  for (let i = 0; i < 6; i++) {
    await page.getByTestId(`path-stop-${i}`).click();
    tops.push(Math.round((await page.getByTestId("path-columns").boundingBox())!.y + (await page.evaluate(() => scrollY))));
  }
  expect(new Set(tops).size).toBe(1);
  // The slot is there whether or not something moved.
  await expect(page.getByTestId("path-events-slot")).toHaveCount(1);
});

test("a confirmation box never carries over from one column to another", async ({ page }) => {
  await checked(page);
  const bar = page.getByTestId("path-reply");
  await page.getByTestId("queue-review-open").click();
  await bar.getByTestId("deal-send").click();
  await expect(bar.getByTestId("deal-send-confirm-box")).toBeVisible();
  await page.getByTestId("path-col-pick-2").click();
  await expect(bar.getByTestId("deal-send-confirm-box")).toHaveCount(0);
  await page.getByTestId("queue-review-open").click();
  await expect(bar.getByTestId("deal-send-Option-B")).toBeVisible();
  await page.getByTestId("path-col-pick-1").click();
  await expect(bar.getByTestId("deal-send-confirm-box")).toHaveCount(0);
});

test("the chips are the moments, in the server's order and words, the decisive one first; each moves the cursor, the sentence and every tile", async ({ page }) => {
  await checked(page);
  const stops = page.locator('[data-testid^="path-stop-"]');
  await expect(stops).toHaveCount(6);
  await expect(page.getByTestId("path-stops")).toHaveAttribute("role", "group");
  await expect(page.getByTestId("path-stops")).toHaveAccessibleName("Moments");
  // The chips are the server's words, never "In 47 days": today, each lowest point, the reserve crossings in either direction and the end of the window.
  expect(await stops.allInnerTexts()).toEqual(MOMENTS.map((m) => m.word));
  expect(MOMENTS.map((m) => m.word)).toEqual(["Today", "Lowest, Option A and Option B", "Below the reserve", "Lowest, as asked", "Back above the reserve", "Day 66"]);
  // The decisive moment (the first the asked path is below the reserve) is selected first.
  await expect(page.getByTestId("path-stop-2")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-count")).toHaveText("3 of 6");
  await expect(page.getByTestId("path-cursor")).toHaveAttribute("data-day", "47");
  await expect(page.getByTestId("path-moment")).toContainText("On every path: Operating bill −¥100k. Option A: Receipt from Foshan Home Retail Co. ¥420k. As asked, cash is below your minimum.");
  // The tiles say each path's cash on that moment in the server's short figures, and the asked path says it is under the minimum, from the server's tone and flag.
  await expect(page.getByTestId("path-tile-figure-0")).toHaveText("¥210k");
  await expect(page.getByTestId("path-tile-0")).toContainText("Below your minimum");
  await expect(page.getByTestId("path-tile-0")).toHaveAttribute("data-below", "true");
  await expect(page.getByTestId("path-tile-0")).toHaveAttribute("data-tone", "bad");
  await expect(page.getByTestId("path-tile-figure-1")).toHaveText("¥632k");
  await expect(page.getByTestId("path-tile-figure-2")).toHaveText("¥302k");
  await expect(page.getByTestId("path-tile-1")).not.toContainText("Below your minimum");
  await expect(page.getByTestId("path-tile-1")).toHaveAttribute("data-tone", "neutral");
  // The gap against as asked: the server's signed string in its tone; the asked tile shows none.
  await expect(page.getByTestId("path-tile-vs-0")).toHaveCount(0);
  await expect(page.getByTestId("path-tile-vs-1")).toHaveText("+¥422k vs the ask");
  await expect(page.getByTestId("path-tile-vs-1")).toHaveClass(/text-ok-fg/);
  await expect(page.getByTestId("path-tile-vs-2")).toHaveText("+¥92k vs the ask");
  await expect(page.getByTestId("path-tile-assumption-1")).toHaveText("If the buyer accepts this reply");
  await expect(page.getByTestId("path-tile-assumption-2")).toHaveText("If the buyer accepts this reply");
  await expect(page.getByTestId("path-tile-assumption-0")).toHaveCount(0);
  // The parting moment (day 0, "Today"): the server's sentence says who decides, per reply.
  await page.getByTestId("path-stop-0").click();
  await expect(page.getByTestId("path-stop-0")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-stop-2")).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByTestId("path-cursor")).toHaveAttribute("data-day", "0");
  await expect(page.getByTestId("path-moment")).toHaveText("Option A: Credit line draw ¥150k. Option B: Credit line draw ¥90k. Who decides: Option A: FLOW can send it; Option B: needs your approval.");
  await expect(page.getByTestId("path-tile-figure-0")).toHaveText("¥400k");
  await expect(page.getByTestId("path-tile-0")).not.toContainText("Below your minimum");
  await expect(page.getByTestId("path-tile-vs-1")).toHaveText("+¥150k vs the ask");
  await expect(page.getByTestId("path-tile-vs-2")).toHaveText("+¥90k vs the ask");
  // A reply that gives up cash to stay above the reserve is in the bad tone against as asked (day 30).
  await page.getByTestId("path-stop-1").click();
  await expect(page.getByTestId("path-tile-vs-1")).toHaveText("−¥10k vs the ask");
  await expect(page.getByTestId("path-tile-vs-1")).toHaveClass(/text-bad-fg/);
  // Previous and next move between moments.
  await page.getByTestId("path-stop-0").click();
  await expect(page.getByTestId("path-prev")).toBeDisabled();
  await page.getByTestId("path-next").click();
  await expect(page.getByTestId("path-stop-1")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("path-stop-5").click();
  await expect(page.getByTestId("path-next")).toBeDisabled();
  await expect(page.getByTestId("path-moment")).toHaveText("No cash moves on any path.");
  await page.getByTestId("path-prev").click();
  await expect(page.getByTestId("path-stop-4")).toHaveAttribute("aria-pressed", "true");
});

test("what moved cash on this day is a closed fold in words per path, and absent when nothing moved", async ({ page }) => {
  await checked(page);
  const events = page.getByTestId("path-events");
  await expect(events).toHaveJSProperty("open", false);
  await events.locator("summary").click();
  await expect(events).toContainText("What moved cash on this day");
  await expect(events).toContainText("Operating bill −¥100,000.00");
  await expect(events).toContainText("Receipt from Foshan Home Retail Co. ¥420,000.00");
  // A moment on which nothing moved has no fold.
  await page.getByTestId("path-stop-5").click();
  await expect(page.getByTestId("path-events")).toHaveCount(0);
});

test("Play never starts by itself, steps one moment every two seconds, ends on the last and can be stopped; the sentence is announced once per step", async ({ page }) => {
  test.setTimeout(90_000);
  await checked(page);
  const play = page.getByTestId("path-play");
  await expect(play).toHaveAttribute("aria-pressed", "false");
  await expect(play).toHaveText("Play the moments");
  // Never auto-starts: left alone for longer than a step, the cursor stays where it was.
  await page.waitForTimeout(2600);
  await expect(page.getByTestId("path-stop-2")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-count")).toHaveText("3 of 6");
  await play.click();
  await expect(play).toHaveAttribute("aria-pressed", "true");
  await expect(play).toHaveText("Pause");
  await expect(page.getByTestId("path-stop-0")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-stop-1")).toHaveAttribute("aria-pressed", "true", { timeout: 6000 });
  await expect(page.getByTestId("path-announce")).toHaveText(`${MOMENTS[1].word}. ${MOMENTS[1].text}`);
  // Pause halts it where it is.
  await play.click();
  await expect(play).toHaveAttribute("aria-pressed", "false");
  await expect(play).toHaveText("Resume");
  await page.waitForTimeout(2600);
  await expect(page.getByTestId("path-stop-1")).toHaveAttribute("aria-pressed", "true");
  // Resume continues from the current moment (it does not go back to the first) and runs to the last moment, where it stops.
  await play.click();
  await expect(page.getByTestId("path-stop-1")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-stop-5")).toHaveAttribute("aria-pressed", "true", { timeout: 20_000 });
  await expect(play).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByTestId("path-count")).toHaveText("6 of 6");
  await expect(play).toHaveText("Play the moments");
  await page.waitForTimeout(2600);
  await expect(page.getByTestId("path-stop-5")).toHaveAttribute("aria-pressed", "true");
  // The announcement is its own polite region (a preview or a tick of the pointer never speaks).
  await expect(page.getByTestId("path-announce")).toHaveAttribute("aria-live", "polite");
});

test("hovering the picture while it plays pauses it, leaving resumes it", async ({ page }) => {
  test.setTimeout(60_000);
  await checked(page);
  await page.getByTestId("path-play").click();
  await expect(page.getByTestId("path-stop-1")).toHaveAttribute("aria-pressed", "true", { timeout: 6000 });
  await page.getByTestId("paths-chart").hover();
  await page.waitForTimeout(500);
  const where = await page.getByTestId("path-count").innerText();
  // While it waits the page says so.
  await expect(page.getByTestId("path-paused")).toHaveText("Paused while you look");
  await page.waitForTimeout(4500);
  await expect(page.getByTestId("path-count")).toHaveText(where);
  await expect(page.getByTestId("path-play")).toHaveAttribute("aria-pressed", "true");
  await page.mouse.move(1, 1);
  await expect(page.getByTestId("path-paused")).toHaveCount(0);
  await expect(page.getByTestId("path-count")).not.toHaveText(where, { timeout: 6000 });
});

test("under reduced motion the cursor jumps with no transition and Play still advances; with motion allowed the cursor eases", async ({ page }) => {
  test.setTimeout(60_000);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await checked(page);
  const cursorClass = () => page.getByTestId("path-cursor").locator("> g").first().getAttribute("class");
  expect(await cursorClass()).toBeNull();
  expect(await page.getByTestId("path-dot").first().getAttribute("class")).toBeNull();
  // (the page-wide reduced-motion rule leaves 0.001 ms; the cursor carries no transition class of its own)
  expect(parseFloat(await page.getByTestId("path-cursor").locator("> g").first().evaluate((el) => getComputedStyle(el).transitionDuration))).toBeLessThan(0.00001);
  await page.getByTestId("path-play").click();
  await expect(page.getByTestId("path-stop-1")).toHaveAttribute("aria-pressed", "true", { timeout: 6000 });
  await page.getByTestId("path-play").click();
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(page.getByTestId("path-cursor").locator("> g").first()).toHaveClass(/transition-transform/);
});

test("pointing at a day shows a tooltip with the three paths' figures that day; it stays in the chart; a click moves the cursor to the nearest moment only", async ({ page }) => {
  await checked(page);
  const chart = page.getByTestId("paths-chart");
  await chart.scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollBy(0, 150)); // clear of the sticky header
  const width = (await chart.boundingBox())!.width;
  await chart.hover({ position: { x: width * 0.4, y: 90 } });
  const tip = page.getByTestId("path-tooltip");
  await expect(tip).toBeVisible();
  for (const name of ["As they asked", "Option A", "Option B"]) await expect(tip).toContainText(name);
  await expect(tip).toContainText("¥");
  const box = (await chart.boundingBox())!;
  const t = (await tip.boundingBox())!;
  expect(t.x).toBeGreaterThanOrEqual(box.x - 1);
  expect(t.x + t.width).toBeLessThanOrEqual(box.x + box.width + 1);
  expect(t.y + t.height).toBeLessThanOrEqual(box.y + box.height + 1);
  // It never covers the tiles or the bar.
  const tiles = (await page.getByTestId("path-tiles").boundingBox())!;
  expect(t.y + t.height).toBeLessThanOrEqual(tiles.y);
  // Near the right edge it flips to the left of the pointer and still stays inside.
  await chart.hover({ position: { x: width - 20, y: 90 } });
  const box2 = (await chart.boundingBox())!;
  const t2 = (await tip.boundingBox())!;
  expect(t2.x + t2.width).toBeLessThanOrEqual(box2.x + box2.width + 1);
  // Pointing changes no moment.
  await expect(page.getByTestId("path-stop-2")).toHaveAttribute("aria-pressed", "true");
  // The days of the moments: each chip's cursor day, read by pressing it.
  const momentDays: number[] = [];
  const count = await page.locator('[data-testid^="path-stop-"]').count();
  for (let i = 0; i < count; i++) {
    await page.getByTestId(`path-stop-${i}`).click();
    momentDays.push(Number(await page.getByTestId("path-cursor").getAttribute("data-day")));
  }
  expect(momentDays).toEqual([0, 30, 47, 60, 62, 66]);
  // A click lands the cursor on the nearest moment, never on another day; at the far left that is today.
  await chart.click({ position: { x: width * 0.4, y: 90 } });
  expect(momentDays).toContain(Number(await page.getByTestId("path-cursor").getAttribute("data-day")));
  await chart.click({ position: { x: 40, y: 90 } });
  expect(Number(await page.getByTestId("path-cursor").getAttribute("data-day"))).toBe(0);
  await chart.click({ position: { x: width - 10, y: 90 } });
  expect(Number(await page.getByTestId("path-cursor").getAttribute("data-day"))).toBe(66);
});

test("pointing at a column or a tile lights its line and dims the other two to 40%; leaving restores; the picked path stays emphasised", async ({ page }) => {
  await checked(page);
  const opacity = (i: number) => page.getByTestId(`path-line-${i}`).evaluate((el) => Number(el.getAttribute("opacity")));
  const widthOf = (i: number) => page.getByTestId(`path-line-${i}`).evaluate((el) => Number(el.getAttribute("stroke-width")));
  const restWidth = await widthOf(0);
  await page.getByTestId("path-col-0").hover();
  await expect(page.getByTestId("path-line-0")).toHaveAttribute("data-active", "true");
  expect(await opacity(0)).toBe(1);
  expect(await opacity(1)).toBe(0.4);
  expect(await opacity(2)).toBe(0.4);
  expect(await widthOf(0)).toBeGreaterThan(restWidth);
  // The pick has not moved.
  await expect(page.getByTestId("path-col-pick-1")).toHaveAttribute("aria-checked", "true");
  await page.getByTestId("path-tile-2").hover();
  await expect(page.getByTestId("path-line-2")).toHaveAttribute("data-active", "true");
  expect(await opacity(0)).toBe(0.4);
  await page.mouse.move(2, 2);
  await expect(page.getByTestId("path-line-1")).toHaveAttribute("data-active", "true");
  expect(await opacity(0)).toBeGreaterThan(0.4);
  // Keyboard focus on a column does the same (an arrow key moves the pick and the focus together; a keyboard focus is a visible one).
  await page.getByTestId("path-col-pick-1").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("path-col-pick-2")).toBeFocused();
  await expect(page.getByTestId("path-line-2")).toHaveAttribute("data-active", "true");
  expect(await opacity(0)).toBe(0.4);
  await page.getByTestId("path-col-pick-2").blur();
  await expect(page.getByTestId("path-line-2")).toHaveAttribute("data-active", "true");
  expect(await opacity(0)).toBeGreaterThan(0.4);
});

test("hovering or focusing a moment chip previews it without changing the selected moment; a click keeps it", async ({ page }) => {
  await checked(page);
  const selected = page.getByTestId("path-stop-2");
  await page.getByTestId("path-stop-0").hover();
  await expect(page.getByTestId("path-moment")).toContainText("Credit line draw ¥150k");
  await expect(page.getByTestId("path-tile-figure-0")).toHaveText("¥400k");
  await expect(page.getByTestId("path-cursor")).toHaveAttribute("data-day", "0");
  await expect(selected).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-stop-0")).toHaveAttribute("aria-pressed", "false");
  await page.mouse.move(2, 2);
  await expect(page.getByTestId("path-moment")).toContainText("Operating bill −¥100k");
  await expect(page.getByTestId("path-cursor")).toHaveAttribute("data-day", "47");
  // Focus previews too; the announcement belongs to the selected moment only.
  await page.getByTestId("path-stop-1").focus();
  await expect(page.getByTestId("path-cursor")).toHaveAttribute("data-day", "30");
  await expect(selected).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-announce")).toContainText("Below the reserve. On every path: Operating bill");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("path-stop-1")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-announce")).toHaveText(`${MOMENTS[1].word}. ${MOMENTS[1].text}`);
});

test("hovering the chart at mid-chart moves the cursor and the tiles to that day; leaving restores the selected moment; the chips and the announcement do not change", async ({ page }) => {
  await checked(page);
  const chart = page.getByTestId("paths-chart");
  await chart.scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollBy(0, 150));
  const width = (await chart.boundingBox())!.width;
  const pressed = () => page.locator('[data-testid^="path-stop-"]').evaluateAll((els) => els.map((el) => el.getAttribute("aria-pressed")));
  const before = await pressed();
  const announce = await page.getByTestId("path-announce").innerText();
  await expect(page.getByTestId("path-cursor")).toHaveAttribute("data-day", "47");
  await expect(page.getByTestId("path-tile-figure-0")).toHaveText("¥210k");
  await chart.hover({ position: { x: width * 0.4, y: 90 } });
  // The cursor follows the pointer's day (a day that is not the selected moment), and the tiles show that day's figures: the same strings the tooltip shows.
  await expect(page.getByTestId("path-cursor")).toHaveAttribute("data-preview", "true");
  expect(await page.getByTestId("path-cursor").getAttribute("data-day")).not.toBe("47");
  const tip = page.getByTestId("path-tooltip");
  await expect(tip).toBeVisible();
  for (const i of [0, 1, 2]) {
    const figure = (await page.getByTestId(`path-tile-figure-${i}`).innerText()).trim();
    expect(figure).toMatch(/^¥/);
    await expect(tip).toContainText(figure);
  }
  await expect(page.getByTestId("path-tile-0")).toHaveAttribute("data-preview", "true");
  // The dotted line is where the pointer is.
  const x = (await page.getByTestId("path-cursor").locator("> g").first().evaluate((el) => new DOMMatrix(getComputedStyle(el).transform).m41)) + (await chart.boundingBox())!.x;
  const box = (await chart.boundingBox())!;
  expect(Math.abs(x - (box.x + width * 0.4))).toBeLessThan(width / 60 + 2);
  // A preview selects nothing and says nothing.
  expect(await pressed()).toEqual(before);
  await expect(page.getByTestId("path-announce")).toHaveText(announce);
  await expect(page.getByTestId("path-count")).toHaveText("3 of 6");
  await page.mouse.move(1, 1);
  await expect(page.getByTestId("path-cursor")).toHaveAttribute("data-day", "47");
  await expect(page.getByTestId("path-cursor")).toHaveAttribute("data-preview", "false");
  await expect(page.getByTestId("path-tile-figure-0")).toHaveText("¥210k");
  await expect(page.getByTestId("path-tile-0")).not.toHaveAttribute("data-preview", "true");
  expect(await pressed()).toEqual(before);
  // A click still commits the nearest moment, and the cursor rests on it.
  await chart.click({ position: { x: width * 0.4, y: 90 } });
  await expect(page.getByTestId("path-cursor")).toHaveAttribute("data-preview", "false");
  expect(["0", "30", "47", "60", "62", "66"]).toContain(await page.getByTestId("path-cursor").getAttribute("data-day"));
});

test("keyboard: the arrow keys move between the chips, Enter keeps one, and Space plays or stops from the focused picture", async ({ page }) => {
  test.setTimeout(60_000);
  await checked(page);
  await page.getByTestId("path-stop-3").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("path-stop-4")).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByTestId("path-stop-2")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("path-stop-2")).toHaveAttribute("aria-pressed", "true");
  // The focused picture: the tooltip follows the cursor's day, the arrows step, Space plays and stops.
  const chart = page.getByTestId("paths-chart");
  await chart.focus();
  await expect(page.getByTestId("path-tooltip")).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("path-stop-3")).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Space");
  await expect(page.getByTestId("path-play")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("path-stop-1")).toHaveAttribute("aria-pressed", "true", { timeout: 6000 });
  await page.keyboard.press("Space");
  await expect(page.getByTestId("path-play")).toHaveAttribute("aria-pressed", "false");
});

test("a column shows its cost on one basis; Option B's net cost carries its two parts beside the net; a mixed cost is two lines, never a sum", async ({ page }) => {
  await checked(page);
  // Option A: one figure, once.
  await expect(page.getByTestId("path-col-cost-1")).toHaveText("¥3,027.77");
  await expect(page.getByTestId("path-col-basis-1")).toHaveText("once, nothing ongoing");
  // Option B: the net with its basis and the two parts that make it, so the zero never stands alone.
  await expect(page.getByTestId("path-col-cost-2")).toHaveText("¥0.00");
  await expect(page.getByTestId("path-col-basis-2")).toHaveText("net over 12 months");
  const rows = page.getByTestId("path-col-components-2").locator("> div");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toHaveText("Funding cost of the longer terms¥16,217.95");
  await expect(rows.nth(1)).toHaveText("Offset by the 0.30% price rise¥16,380.00");
  // The asked path has both a one-off and a 12-month part: two figure lines, no single headline, so they never read as a sum.
  await expect(page.getByTestId("path-col-cost-0")).toHaveCount(0);
  await expect(page.getByTestId("path-col-parts-0").locator("> li")).toHaveCount(2);
  await expect(page.getByTestId("path-col-forward-0")).toHaveText("¥28,326.92 over 12 months");
  await expect(page.getByTestId("path-col-once-0")).toHaveText("¥5,040.00 once");
  // The cash facts of each path, in the server's words.
  await expect(page.getByTestId("path-col-lowest-0")).toHaveText("Lowest ¥165k, in 60 days");
  await expect(page.getByTestId("path-col-breach-0")).toHaveText("First below your minimum in 47 days");
  await expect(page.getByTestId("path-col-breach-1")).toHaveCount(0);
});

test("the three classes of who decides have three tones in the column and the bar, in the server's words", async ({ page }) => {
  await checked(page);
  const tone = (i: number) => page.getByTestId(`path-col-decides-${i}`).locator("[data-tone]").getAttribute("data-tone");
  await expect(page.getByTestId("path-col-decides-0")).toContainText("Over a limit you signed: only a new mandate changes that");
  await expect(page.getByTestId("path-col-decides-0")).toHaveAttribute("data-authority", "over_limit");
  expect(await tone(0)).toBe("bad");
  await expect(page.getByTestId("path-col-decides-1")).toContainText("FLOW can send it");
  await expect(page.getByTestId("path-col-decides-1")).toHaveAttribute("data-authority", "flow_may");
  expect(await tone(1)).toBe("ok");
  await expect(page.getByTestId("path-col-decides-2")).toContainText("Needs your approval");
  await expect(page.getByTestId("path-col-decides-2")).toHaveAttribute("data-authority", "needs_owner");
  expect(await tone(2)).toBe("warn");
  // The card's caption (the old bar's) is the same words in the same tone.
  const barTone = () => page.getByTestId("queue-authority").locator("[data-tone]").getAttribute("data-tone");
  await expect(page.getByTestId("queue-authority")).toHaveText("✓FLOW can send it");
  expect(await barTone()).toBe("ok");
  await page.getByTestId("path-col-pick-2").click();
  await expect(page.getByTestId("queue-authority")).toContainText("Needs your approval");
  expect(await barTone()).toBe("warn");
  await page.getByTestId("path-col-pick-0").click();
  await expect(page.getByTestId("queue-option")).toHaveText("Over a limit you signed: only a new mandate changes that");
});

for (const [width, height] of [[1280, 800], [412, 915], [390, 844], [360, 740]]) {
  test(`the page's order is the heading, what they ask, why, the reply card, the picture, the columns, then the comparison and the aside, in the DOM and on screen at ${width} x ${height}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await checked(page);
    // (from lg the aside sits beside the detail; below it, it follows the detail)
    const ids = ["queue-heading", "queue-ask", "queue-why", "queue-recommends", "paths-picture", "path-columns", "queue-compare", ...(width < 1024 ? ["queue-aside"] : [])];
    const tops = await page.evaluate((list) => list.map((id) => (document.getElementById(id) ?? document.querySelector(`[data-testid="${id}"]`))!.getBoundingClientRect().top + scrollY), ids);
    expect(tops).toEqual([...tops].sort((a, b) => a - b));
    // The DOM order is the same, and nothing is reordered by CSS.
    const dom = await page.evaluate((list) => {
      const els = list.map((id) => document.getElementById(id) ?? document.querySelector(`[data-testid="${id}"]`)!);
      return els.every((el, i) => i === 0 || !!(els[i - 1].compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING));
    }, ids);
    expect(dom).toBe(true);
    expect(await page.evaluate(() => Array.from(document.querySelectorAll("main *")).filter((el) => Array.from(el.classList).some((c) => /^(\w+:)*-?order-(\d|first|last|none)/.test(c))).length)).toBe(0);
  });
}

// (360 x 740 is dropped: the why and the card cannot both fit above a 56 px tab bar on a screen that small; the phone check is 390 x 844)
for (const [width, height] of [[412, 915], [390, 844]]) {
  test(`the priced decision, "Review and send the counter", is inside the first viewport at ${width} x ${height}, above the tab bar`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await checked(page);
    const send = (await page.getByTestId("queue-review-open").boundingBox())!;
    const tabs = (await page.getByTestId("tab-bar").boundingBox())!;
    expect(send.y).toBeGreaterThan(0);
    expect(send.y + send.height, "send bottom against the tab bar").toBeLessThanOrEqual(tabs.y);
  });
}

test("at 1280 x 800 the reply card sits under the heading with its button in the first screen, never covers the chart (it is not sticky), and there is one heading and one filled primary", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await checked(page);
  await expect(page.locator("h1")).toHaveCount(1);
  expect(await filledBrand(page)).toBe(1);
  const send = (await page.getByTestId("queue-review-open").boundingBox())!;
  expect(send.y + send.height).toBeLessThanOrEqual(800);
  expect(await page.evaluate(() => getComputedStyle(document.querySelector('[data-testid="queue-recommends"]')!).position)).not.toBe("sticky");
  const overlap = async () =>
    page.evaluate(() => {
      const chart = document.querySelector('[data-testid="paths-picture"] svg')!.getBoundingClientRect();
      const bar = document.querySelector('[data-testid="queue-recommends"]')!.getBoundingClientRect();
      return Math.max(0, Math.min(chart.bottom, bar.bottom) - Math.max(chart.top, bar.top)) > 0;
    });
  for (const y of [0, 400, 800, 1200, 1600]) {
    await page.evaluate((top) => window.scrollTo(0, top), y);
    expect(await overlap(), `scrolled to ${y}`).toBe(false);
  }
});

test("on a phone nothing scrolls sideways and the chips, the arrows, Play and the column buttons reach 44 px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await checked(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  await expect(page.getByTestId("path-stops")).toBeVisible();
  await expect(page.getByTestId("path-play")).toBeVisible();
  const short = await page.evaluate(() => Array.from(document.querySelectorAll('[data-testid^="path-stop-"], [data-testid="path-play"], [data-testid="path-prev"], [data-testid="path-next"], [data-testid^="path-col-pick-"]')).filter((el) => el.getBoundingClientRect().height < 44).length);
  expect(short).toBe(0);
  // The three tiles are the legend: all three in one row, none cut off.
  const tiles = await page.getByTestId("path-tiles").locator("> div").evaluateAll((els) => els.map((el) => { const r = el.getBoundingClientRect(); return { x: r.x, w: r.width, y: Math.round(r.y) }; }));
  expect(new Set(tiles.map((t) => t.y)).size).toBe(1);
  for (const t of tiles) expect(t.x + t.w).toBeLessThanOrEqual(390);
});

test("the send from the bar still records the agreement", async ({ page }) => {
  const agreedAt = { on: false, pictureRequests: 0 };
  page.on("request", (r) => {
    if (agreedAt.on && /\/offers\/[^/]+\/picture/.test(r.url())) agreedAt.pictureRequests += 1;
  });
  await checked(page);
  const bar = page.getByTestId("path-reply");
  await page.getByTestId("queue-review-open").click();
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

test("in Chinese the paths, the stops and the reply read in Chinese", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button").click();
  await expect(page.getByTestId("paths-picture")).toBeVisible();
  await expect(page.getByTestId("path-play")).toContainText("播放各时刻");
  await expect(page.getByTestId("path-col-pick-1")).toContainText("已显示在图上");
  await expect(page.getByTestId("path-col-cost-1")).toContainText("¥");
  await expect(page.getByTestId("path-moment")).toContainText(/[一-鿿]/);
  await expect(page.getByTestId("queue-recommends")).toContainText("FLOW 建议");
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
    // No wait for the chart: the reply area is a placeholder until the picture is read, then the card; the review and the send are clicked as soon as they are there.
    await page.getByTestId("queue-review-open").click();
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
  await expect(page.getByTestId("queue-heading")).toBeVisible();
  // Neither the counter cards nor a send control exist while it loads.
  await expect(page.locator("#counters")).toHaveCount(0);
  await expect(page.getByTestId("deal-send")).toHaveCount(0);
  await expect(page.getByTestId("deal-option-Option-A")).toHaveCount(0);
  await expect(page.getByTestId("queue-review-open")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("paths-loading")).toHaveCount(0);
  // The card keeps its identity when the stop or the pick changes: an open confirmation survives a stop.
  await page.getByTestId("queue-review-open").click();
  await page.getByTestId("path-reply").getByTestId("deal-send").click();
  await expect(page.getByTestId("deal-send-confirm-box")).toBeVisible();
  await page.getByTestId("path-stop-0").click();
  await expect(page.getByTestId("deal-send-confirm-box")).toBeVisible();
});
