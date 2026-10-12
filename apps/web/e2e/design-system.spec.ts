import { expect, test } from "./fixtures";

/**
 * The design-system wave (#112): the motion tokens, and under reduced motion only opacity transitions remain. The later items of the wave
 * (the three cards, SegmentedTabs, StateWord, the type scale, the sidebar) add their own tests to this file.
 */

const TOKENS = { "--dur-instant": 80, "--dur-fast": 140, "--dur": 220, "--dur-expanded": 280, "--dur-scenario": 350, "--dur-narrative": 500 } as const;

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "mock-mode spec, at the desktop width");
});

/** A probe element that transitions `transform` over a token, read back through getComputedStyle. */
async function probe(page: import("@playwright/test").Page, token: string) {
  return page.evaluate((t) => {
    const el = document.createElement("div");
    el.style.transition = `transform var(${t}) var(--ease-ui)`;
    document.body.append(el);
    const s = getComputedStyle(el);
    const out = { property: s.transitionProperty, duration: s.transitionDuration, root: getComputedStyle(document.documentElement).getPropertyValue(t).trim() };
    el.remove();
    return out;
  }, token);
}

test("the six motion tokens are the scale, and every duration in the stylesheet is one of them", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("h1").first()).toBeVisible();
  for (const [token, ms] of Object.entries(TOKENS)) {
    const got = await probe(page, token);
    expect(Number.parseFloat(got.duration) * 1000, token).toBeCloseTo(ms, 5);
  }
  const easings = await page.evaluate(() => ["--ease-ui", "--ease-select"].map((t) => getComputedStyle(document.documentElement).getPropertyValue(t).trim()));
  expect(easings.every((e) => e.startsWith("cubic-bezier"))).toBe(true);
  // No rule in the shipped stylesheets names a duration that is not a token (a delay of 30 ms steps in a stagger and the 0.001 ms of a finished animation aside).
  const stray = await page.evaluate(() => {
    const found = new Set<string>();
    const walk = (rules: CSSRuleList) => {
      for (const r of Array.from(rules)) {
        if ("cssRules" in r && (r as CSSGroupingRule).cssRules) walk((r as CSSGroupingRule).cssRules);
        if (r instanceof CSSStyleRule) {
          for (const prop of ["transition-duration", "animation-duration"]) {
            const v = r.style.getPropertyValue(prop);
            if (v && /\d(ms|s)\b/.test(v) && !v.includes("var(")) found.add(`${r.selectorText} { ${prop}: ${v} }`);
          }
        }
      }
    };
    for (const sheet of Array.from(document.styleSheets)) {
      try {
        walk(sheet.cssRules);
      } catch {
        /* cross-origin sheet */
      }
    }
    return Array.from(found).filter((x) => !x.includes("0.001ms"));
  });
  expect(stray).toEqual([]);
});

test("reduced motion: one transition per token keeps only opacity, at its own token's duration; with no preference it keeps its property", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("h1").first()).toBeVisible();
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const [token, ms] of Object.entries(TOKENS)) {
    const got = await probe(page, token);
    expect(got.property, `${token} under reduced motion`).toBe("opacity");
    expect(Number.parseFloat(got.duration) * 1000, token).toBeCloseTo(ms, 5);
  }
  await page.emulateMedia({ reducedMotion: "no-preference" });
  for (const token of Object.keys(TOKENS)) {
    expect((await probe(page, token)).property, `${token} with no preference`).toBe("transform");
  }
});

test("three card types: a standard card has a hairline and no shadow, the decision card one soft shadow and no frost, the selected card the tint and a 3 px rule", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-next-action").first()).toBeVisible({ timeout: 15_000 });
  const styles = await page.evaluate(() => {
    const read = (el: Element) => {
      const s = getComputedStyle(el);
      return { shadow: s.boxShadow, radius: s.borderTopLeftRadius, border: s.borderTopWidth, borderColor: s.borderTopColor, bg: s.backgroundColor, left: s.borderLeftWidth, leftColor: s.borderLeftColor, blur: s.backdropFilter };
    };
    const probe = (cls: string) => {
      const el = document.createElement("div");
      el.className = cls;
      document.body.append(el);
      const out = read(el);
      el.remove();
      return out;
    };
    const live = document.querySelector('[data-testid="home-next-action"]');
    return { standard: probe("card-standard"), decision: probe("card-decision"), selected: probe("card-selected"), live: live ? read(live) : null };
  });
  expect(styles.standard.shadow).toBe("none");
  expect(styles.standard.radius).toBe("14px");
  expect(styles.standard.borderColor).toBe("rgb(230, 233, 239)");
  expect(styles.decision.radius).toBe("16px");
  expect(styles.decision.shadow).toContain("rgba(16, 24, 40, 0.06) 0px 1px 2px");
  expect(styles.decision.shadow).toContain("rgba(16, 24, 40, 0.06) 0px 8px 24px");
  expect(styles.selected.bg).toBe("rgb(230, 241, 255)");
  expect(styles.selected.left).toBe("3px");
  expect(styles.selected.leftColor).toBe("rgb(3, 104, 233)");
  // The attention card on Home is the decision card: solid, one soft shadow, no frost.
  expect(styles.live?.shadow).toBe(styles.decision.shadow);
  expect(styles.live?.blur).toBe("none");
  expect(styles.live?.bg).toBe("rgb(255, 255, 255)");
});

/** Visible text smaller than 13 px that carries a figure (an amount, a rate, a multiple, a thousands group): the floor for a financial qualification is 13 px. */
const smallFinancialText = (page: import("@playwright/test").Page) =>
  page.evaluate(() => {
    const figure = /[¥$€%×]|\d,\d{3}/;
    // A chart's tick or line label that carries money or a date ("¥500k", "in 30 days", "Today") is a figure too.
    const chartFigure = /[¥$€%×]|\d,\d{3}|\d+k\b|\d+ days?\b|\btoday\b|天|今天/i;
    const found: string[] = [];
    document.querySelectorAll("details").forEach((d) => (d.open = true));
    const walker = document.createTreeWalker(document.querySelector("main") ?? document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const text = (n.textContent ?? "").trim();
      const el = n.parentElement;
      const inSvg = Boolean(el?.closest("svg"));
      if (!text || !el || el.closest("script, style, sup") || !(inSvg ? chartFigure : figure).test(text)) continue;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      const s = getComputedStyle(el);
      if (parseFloat(s.fontSize) < 13 && s.textTransform !== "uppercase") found.push(`${s.fontSize} ${el.closest("[data-testid]")?.getAttribute("data-testid") ?? el.tagName}: ${text.slice(0, 60)}`);
    }
    return found;
  });

test("type scale: the roles are variables, the headline steps with the screen, and no figure or qualification on the five pages is under 13 px", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-headline")).toBeVisible({ timeout: 15_000 });
  const vars = await page.evaluate(() => {
    const probe = (v: string) => {
      const el = document.createElement("div");
      el.style.fontSize = `var(${v})`;
      document.body.append(el);
      const px = parseFloat(getComputedStyle(el).fontSize);
      el.remove();
      return px;
    };
    return Object.fromEntries(["--text-meta", "--text-supporting", "--text-body", "--text-body-lg", "--text-card-title", "--text-section", "--text-value", "--text-headline"].map((v) => [v, probe(v)]));
  });
  expect(vars["--text-meta"]).toBe(12);
  expect(vars["--text-supporting"]).toBe(13);
  expect(vars["--text-body"]).toBe(14);
  expect(vars["--text-body-lg"]).toBe(15);
  expect(vars["--text-card-title"]).toBe(16);
  expect(vars["--text-section"]).toBeGreaterThanOrEqual(17);
  expect(vars["--text-section"]).toBeLessThanOrEqual(20);
  expect(vars["--text-value"]).toBe(30);
  // The Home headline is 36 px on a desktop, 34 px at tablet width and 26 px on a phone; a major value is 30, 28 and 24: the headline always dominates it.
  const size = (id: string) => page.getByTestId(id).evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  const head = async () => size("home-headline");
  expect(vars["--text-headline"]).toBe(36);
  expect(await head()).toBe(36);
  await page.setViewportSize({ width: 820, height: 900 });
  expect(await head()).toBe(34);
  expect(vars["--text-headline"]).toBeGreaterThan(vars["--text-value"]);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await head()).toBe(26);
  const phoneValue = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--text-value")) * 16);
  expect(phoneValue).toBe(24);
  await page.setViewportSize({ width: 1440, height: 900 });

  const found: Record<string, string[]> = {};
  for (const [name, path] of [["Home", "/"], ["Cash", "/cash"], ["Receivables", "/receivables"], ["Customer", "/customers/BUYER-1"]] as const) {
    await page.goto(path);
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15_000 });
    await page.waitForTimeout(400);
    found[name] = await smallFinancialText(page);
  }
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("queue-check-button").click();
  await expect(page.getByTestId("queue-heading")).toBeVisible({ timeout: 15_000 });
  found.Deals = await smallFinancialText(page);
  expect(found).toEqual({ Home: [], Cash: [], Receivables: [], Customer: [], Deals: [] });
});

const NAV = ["Home", "Deals", "Cash & funding", "Receivables", "Activity"];
const sidebarWidth = (page: import("@playwright/test").Page) => page.locator("aside").first().evaluate((el) => Math.round(el.getBoundingClientRect().width));

test("sidebar: on a laptop it collapses to icons with the label on hover and focus, the choice is kept and restored, and a wide screen is never collapsed", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  await expect(page.getByTestId("home-headline")).toBeVisible({ timeout: 15_000 });
  const toggle = page.getByTestId("sidebar-toggle");
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(toggle).toHaveAccessibleName("Collapse the sidebar");
  expect(await sidebarWidth(page)).toBe(240);
  await expect(page.getByRole("link", { name: "Receivables" }).locator(".side-label")).toBeVisible();

  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(toggle).toHaveAccessibleName("Expand the sidebar");
  expect(await sidebarWidth(page)).toBe(72);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("tl-sidebar") ?? "{}").collapsed)).toBe(true);
  // Icons only: every destination is still a link with its full name, and its word is hidden until hover or focus (opacity only).
  const nav = page.getByTestId("nav-pills");
  for (const name of NAV) await expect(nav.getByRole("link", { name })).toBeVisible();
  const label = nav.getByRole("link", { name: "Deals" }).locator(".side-label");
  await expect(label).toHaveCSS("opacity", "0");
  await nav.getByRole("link", { name: "Deals" }).hover();
  await expect(label).toHaveCSS("opacity", "1");
  await page.mouse.move(700, 400);
  await expect(label).toHaveCSS("opacity", "0");
  await nav.getByRole("link", { name: "Cash & funding" }).focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  await expect(nav.getByRole("link", { name: "Cash & funding" })).toBeFocused();
  await expect(nav.getByRole("link", { name: "Cash & funding" }).locator(".side-label")).toHaveCSS("opacity", "1");
  // The way out of the icons is by keyboard too: the toggle is the first stop, and Enter opens the sidebar again.
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(await sidebarWidth(page)).toBe(240);
  await toggle.click();

  // Restored on load: the attribute is on <html> before the app renders, and the sidebar is the narrow one on the next page.
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-sidebar", "collapsed");
  expect(await sidebarWidth(page)).toBe(72);
  await expect(page.getByTestId("sidebar-toggle")).toHaveAttribute("aria-expanded", "false");
  // The five destinations work from the icons, and the Customer drill-down (no destination of its own) sits beside the narrow sidebar.
  await page.getByTestId("nav-pills").getByRole("link", { name: "Receivables" }).click();
  await expect(page).toHaveURL(/\/receivables/);
  await expect(page.getByTestId("nav-pills").getByRole("link", { name: "Receivables" })).toHaveAttribute("aria-current", "page");
  await page.goto("/customers/BUYER-1");
  await expect(page.getByTestId("customer-overview")).toBeVisible({ timeout: 15_000 });
  expect(await sidebarWidth(page)).toBe(72);
  await expect(page.getByTestId("nav-pills").locator("[aria-current=page]")).toHaveCount(0);

  // A wide screen has no toggle and the full sidebar, whatever was chosen on the laptop.
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.getByTestId("sidebar-toggle")).toBeHidden();
  expect(await sidebarWidth(page)).toBe(240);
  await expect(page.getByTestId("nav-pills").getByRole("link", { name: "Deals" }).locator(".side-label")).toBeVisible();
});

test("sidebar: storage that throws never breaks the toggle, and the sidebar below the laptop width has none", async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.setItem = function () {
      throw new Error("blocked");
    };
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await expect(page.getByTestId("home-headline")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("sidebar-toggle").click();
  expect(await sidebarWidth(page)).toBe(72);
  await expect(page.getByTestId("sidebar-toggle")).toHaveAttribute("aria-expanded", "false");
  await page.setViewportSize({ width: 820, height: 900 });
  await expect(page.getByTestId("sidebar-toggle")).toBeHidden();
  await expect(page.locator("aside").first()).toBeHidden();
  await expect(page.getByTestId("tab-bar")).toBeVisible();
});

test("sidebar: axe finds nothing serious on a collapsed sidebar, with the page beside it", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.addInitScript(() => localStorage.setItem("tl-sidebar", JSON.stringify({ collapsed: true })));
  const { default: AxeBuilder } = await import("@axe-core/playwright");
  for (const path of ["/", "/cash", "/receivables", "/customers/BUYER-1"]) {
    await page.goto(path);
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15_000 });
    expect(await sidebarWidth(page)).toBe(72);
    await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => undefined))));
    const result = await new AxeBuilder({ page }).analyze();
    const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`), path).toEqual([]);
  }
});

test("SegmentedTabs: the choice is not the pill alone, widths follow the labels, the pill never leaves the track, and choosing never scrolls the page", async ({ page }) => {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("queue-check-button").click();
  await expect(page.getByTestId("queue-tab-needs")).toBeVisible({ timeout: 15_000 });
  const tab = (k: string) => page.getByTestId(`queue-tab-${k}`);
  // Selected: weight 800 and a brand icon; the rest 600 in ink-2. The track has the line-ui hairline.
  const look = async (k: string) => tab(k).evaluate((el) => ({ weight: getComputedStyle(el).fontWeight, ink: getComputedStyle(el).color, icon: getComputedStyle(el.querySelector("svg")!).color }));
  expect(await look("needs")).toMatchObject({ weight: "800", icon: "rgb(3, 104, 233)" });
  expect(await look("wait")).toMatchObject({ weight: "600", ink: "rgb(77, 87, 103)" });
  const track = page.getByRole("tablist", { name: "Deals by status" });
  await expect(track).toHaveCSS("border-top-color", "rgb(118, 131, 153)");
  // Per-option widths: the four tabs follow their own labels; choosing one does not resize any.
  const widths = () => Promise.all(["needs", "wait", "agreed", "setup"].map(async (k) => Math.round((await tab(k).boundingBox())!.width)));
  const before = await widths();
  expect(new Set(before).size).toBeGreaterThan(1);
  await tab("setup").click();
  expect(await widths()).toEqual(before);
  // A jump across the tabs keeps the pill inside the track (no overshoot).
  const inside = () =>
    page.evaluate(() => {
      const t = document.querySelector("[role=tablist]")!.getBoundingClientRect();
      const p = document.querySelector("[role=tablist] > span[aria-hidden]")!.getBoundingClientRect();
      return p.left >= t.left - 0.5 && p.right <= t.right + 0.5;
    });
  expect(await inside()).toBe(true);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const seen: boolean[] = [];
  const poll = page.evaluate(async () => {
    const out: boolean[] = [];
    const t = document.querySelector("[role=tablist]")!.getBoundingClientRect();
    for (let i = 0; i < 24; i++) {
      const p = document.querySelector("[role=tablist] > span[aria-hidden]")!.getBoundingClientRect();
      out.push(p.left >= t.left - 0.5 && p.right <= t.right + 0.5);
      await new Promise((r) => requestAnimationFrame(r));
    }
    return out;
  });
  await tab("needs").click();
  seen.push(...(await poll));
  expect(seen.every(Boolean)).toBe(true);
  await page.emulateMedia({ reducedMotion: "reduce" });
  // On a phone choosing a tab never scrolls the window (the queue's own track scrolls by its scrollLeft; Home's window tabs sit mid-page).
  await page.setViewportSize({ width: 390, height: 844 });
  await tab("setup").click();
  await expect(tab("setup")).toBeInViewport();
  await page.goto("/");
  await expect(page.getByTestId("home-window-60")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("home-window-60").scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollBy(0, -60));
  const y = await page.evaluate(() => window.scrollY);
  expect(y).toBeGreaterThan(0);
  await page.getByTestId("home-window-60").click();
  await page.getByTestId("home-window-120").click();
  expect(Math.abs((await page.evaluate(() => window.scrollY)) - y)).toBeLessThan(2);
});

test("cards: a page has one decision card, and a chosen row, invoice or path is the one selected style (the tint and the 3 px rule)", async ({ page }) => {
  const decisionCards = () => page.locator(".card-decision:visible").count();
  for (const path of ["/", "/cash", "/receivables", "/customers/BUYER-1"]) {
    await page.goto(path);
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15_000 });
    await page.waitForTimeout(300);
    expect(await decisionCards(), path).toBeLessThanOrEqual(1);
  }
  const selected = (loc: import("@playwright/test").Locator) => loc.evaluate((el) => ({ bg: getComputedStyle(el).backgroundColor, rule: getComputedStyle(el).borderLeftWidth, ruleColor: getComputedStyle(el).borderLeftColor }));
  const want = { bg: "rgb(230, 241, 255)", rule: "3px", ruleColor: "rgb(3, 104, 233)" };
  await page.goto("/receivables");
  await expect(page.getByTestId("recv-RCV-A")).toBeVisible({ timeout: 15_000 });
  expect(await selected(page.getByTestId("recv-RCV-A"))).toEqual(want);
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("queue-check-button").click();
  await expect(page.getByTestId("queue-heading")).toBeVisible({ timeout: 15_000 });
  expect(await decisionCards()).toBeLessThanOrEqual(1);
  expect(await selected(page.locator('[data-testid="queue-row"][data-selected="true"]'))).toEqual(want);
  const picked = page.locator('[data-testid^="path-col-"][data-selected="true"]').first();
  if (await picked.count()) {
    const s = await selected(picked);
    expect(s.bg).toBe(want.bg);
    expect(s.ruleColor).toBe(want.ruleColor);
  }
});
