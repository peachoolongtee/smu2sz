import { expect, test } from "./fixtures";

/**
 * The `touch:` variant (globals.css) reaches 44 px on a narrow screen AND under a coarse pointer at any width. Before the fix the
 * coarse branch compiled to an invalid selector and was dropped, so a tablet-width touch screen kept 32 and 40 px controls.
 * Also: under reduced motion (set for every spec in playwright.config.ts) a loading button shows an ellipsis, not a frozen arc.
 */

async function buttonHeight(page: import("@playwright/test").Page): Promise<number> {
  await page.goto("/inbox");
  const box = await page.getByRole("button", { name: "Compile" }).boundingBox();
  expect(box).not.toBeNull();
  return box!.height;
}

test("a button is 40 px with a mouse at desktop width", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.emulateMedia({ media: "screen" });
  expect(await page.evaluate(() => matchMedia("(pointer: coarse)").matches)).toBe(false);
  expect(await buttonHeight(page)).toBeLessThan(44);
});

test("a button reaches 44 px at 412 wide", async ({ page }) => {
  await page.setViewportSize({ width: 412, height: 915 });
  expect(await buttonHeight(page)).toBeGreaterThanOrEqual(44);
});

test("a button reaches 44 px under a coarse pointer at 1280 wide", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const cdp = await page.context().newCDPSession(page);
  // Touch emulation is what makes `(pointer: coarse)` match in Chromium.
  await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 1 });
  expect(await page.evaluate(() => matchMedia("(pointer: coarse)").matches)).toBe(true);
  expect(await buttonHeight(page)).toBeGreaterThanOrEqual(44);
});

test("under reduced motion the busy ellipsis is shown and the frozen arc is hidden", async ({ page }) => {
  await page.goto("/inbox");
  expect(await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches)).toBe(true);
  // The Spinner's markup, as Button renders it, in the page's own stylesheet.
  const display = () =>
    page.evaluate(() => {
      const host = document.createElement("div");
      host.innerHTML = '<svg class="spinner animate-spin"></svg><span class="spinner-dots">…</span>';
      document.body.append(host);
      const read = (sel: string) => getComputedStyle(host.querySelector(sel)!).display;
      const out = { arc: read(".spinner"), dots: read(".spinner-dots") };
      host.remove();
      return out;
    });
  expect(await display()).toEqual({ arc: "none", dots: "inline" });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  expect((await display()).dots).toBe("none");
});
