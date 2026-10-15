import { expect, test } from "./fixtures";
import { checkedDeal } from "./helpers";

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
    return Array.from(found).filter((x) => !x.includes("0.001ms") && !/: 0s \}$/.test(x));
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
  await page.goto("/cash"); // the plan bar there is the page's decision card
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
  // The plan bar on Cash & funding is the decision card: solid, one soft shadow, no frost.
  expect(styles.live?.shadow).toBe(styles.decision.shadow);
  expect(styles.live?.blur).toBe("none");
  expect(styles.live?.bg).toBe("rgb(248, 249, 249)"); // the panel tone of the owner's mockup
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
  await page.goto("/cash"); // the page headline role (Home V2's own header is a fixed 20 / 28 px)
  await expect(page.getByTestId("cash-headline")).toBeVisible({ timeout: 15_000 });
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
  // The page headline is 36 px on a desktop, 34 px at tablet width and 26 px on a phone; a major value is 30, 28 and 24: the headline always dominates it.
  const size = (id: string) => page.getByTestId(id).evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  const head = async () => size("cash-headline");
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
  await checkedDeal(page);
  found.Deals = await smallFinancialText(page);
  expect(found).toEqual({ Home: [], Cash: [], Receivables: [], Customer: [], Deals: [] });
});

const NAV = ["Home", "Deals", "Attach deals", "Cash & funding", "Sandbox", "Capex", "Receivables", "Activity"];
type Pg = import("@playwright/test").Page;
/** The rail's grid column (the aside) and the panel that opens over the page. */
const railColumn = (page: Pg) => page.getByTestId("nav-rail").evaluate((el) => Math.round(el.getBoundingClientRect().width));
const panelWidth = (page: Pg) => page.getByTestId("nav-rail-panel").evaluate((el) => Math.round(el.getBoundingClientRect().width));
const mainBox = (page: Pg) => page.locator("main").evaluate((el) => { const r = el.getBoundingClientRect(); return { x: Math.round(r.x), w: Math.round(r.width) }; });

test("rail: a 56 px icon rail by default from a laptop up, an overlay on hover and on focus that never moves the page, closing after it is left; the pin persists", async ({ page }) => {
  for (const [width, height] of [[1366, 768], [1440, 900]] as const) {
    await page.setViewportSize({ width, height });
    await page.goto("/");
    await expect(page.getByTestId("home-headline")).toBeVisible({ timeout: 15_000 });
    const nav = page.getByTestId("nav-pills");
    // Collapsed by default: 56 px of icons, every destination a link with its full name, its word hidden, no toggle word.
    expect(await railColumn(page), `${width}`).toBe(56);
    expect(await panelWidth(page)).toBe(56);
    await expect(page.getByTestId("nav-rail")).toHaveAttribute("data-rail", "closed");
    for (const name of NAV) await expect(nav.getByRole("link", { name, exact: true })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Deals", exact: true }).locator(".side-label")).toHaveCSS("opacity", "0");
    const before = await mainBox(page);

    // Collapsed, the rail shows icons and the pin only: no text of any kind is visible in it (the Demo note, the words, the count's number), and the Ask FLOW pill is its icon.
    const visibleText = () =>
      page.getByTestId("nav-rail").evaluate((root) => {
        const out: string[] = [];
        const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        for (let n = walk.nextNode(); n; n = walk.nextNode()) {
          const text = (n.textContent ?? "").trim();
          const el = n.parentElement;
          if (!text || !el) continue;
          const cs = getComputedStyle(el);
          const r = el.getBoundingClientRect();
          if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.fontSize) === 0 || r.width <= 1 || r.height <= 1 || parseFloat(cs.opacity) === 0) continue;
          out.push(text);
        }
        return out;
      });
    expect(await visibleText(), `${width} collapsed rail text`).toEqual([]);
    await expect(page.getByTestId("chat-open").locator(".ask-label")).toBeHidden();
    // The pointer on the rail opens the panel to 200 px over the page: the main column neither moves nor changes width.
    await nav.getByRole("link", { name: "Deals", exact: true }).hover();
    await expect(page.getByTestId("nav-rail")).toHaveAttribute("data-rail", "open");
    await expect.poll(() => panelWidth(page)).toBe(200);
    await expect(nav.getByRole("link", { name: "Deals", exact: true }).locator(".side-label")).toHaveCSS("opacity", "1");
    expect(await railColumn(page)).toBe(56);
    expect(await mainBox(page)).toEqual(before);
    expect((await visibleText()).length, "the open rail says its words").toBeGreaterThan(3);
    // Leaving it closes it after a short moment, not at once.
    await page.mouse.move(width - 300, 400);
    await expect(page.getByTestId("nav-rail")).toHaveAttribute("data-rail", "closed");
    await expect.poll(() => panelWidth(page)).toBe(56);
    // The whole 56 px column is the target, its footer included: the real pointer at x = 15 near the bottom opens it, and so does the top edge.
    for (const y of [height - 90, 120]) {
      await page.mouse.move(width - 300, 400);
      await expect.poll(() => panelWidth(page)).toBe(56);
      await page.mouse.move(15, y);
      await expect.poll(() => panelWidth(page), `${width} at (15, ${y})`).toBe(200);
      await page.mouse.move(width - 300, 400);
      await expect.poll(() => panelWidth(page)).toBe(56);
    }

    // Keyboard: focus in the rail opens it, every destination is reached with Tab, and focus out closes it again.
    for (let i = 0; i < 8 && !(await nav.getByRole("link", { name: "Home" }).evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press("Tab");
    await expect(nav.getByRole("link", { name: "Home" })).toBeFocused();
    await expect(page.getByTestId("nav-rail")).toHaveAttribute("data-rail", "open");
    for (const name of NAV.slice(1)) {
      await page.keyboard.press("Tab");
      await expect(nav.getByRole("link", { name, exact: true })).toBeFocused();
    }
    expect(await mainBox(page)).toEqual(before);
    await page.locator("main").focus();
    await expect(page.getByTestId("nav-rail")).toHaveAttribute("data-rail", "closed");
  }

  // The rail never covers the page's primary button at rest: collapsed it is 56 px at 1280 and 1440; opened by the pointer it is a layer over the page that may overlap (it is open
  // only while the pointer or focus is on it, and closes after they leave); pinned, the page is laid out beside it (no overlap at 1280).
  for (const width of [1280, 1440] as const) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByTestId("home-headline")).toBeVisible({ timeout: 15_000 });
    const primary = page.getByTestId("home-check-plan");
    await expect(primary).toBeVisible();
    expect((await primary.boundingBox())!.x, `${width} collapsed`).toBeGreaterThan(56);
    await page.getByTestId("nav-pills").getByRole("link", { name: "Deals", exact: true }).hover();
    await expect.poll(() => panelWidth(page)).toBe(200);
    // The open rail reads as a layer: a soft shadow, and only while it is open.
    expect(await page.getByTestId("nav-rail-panel").evaluate((el) => getComputedStyle(el).boxShadow)).not.toBe("none");
    // (Home is fluid, its content starts at the rail's edge plus a 32 px gutter, so the open layer may lie over its left edge at any laptop width; it closes when the pointer leaves, and pinned the page is laid out beside it, below.)
    await page.mouse.move(width - 100, 600);
    await expect.poll(() => panelWidth(page)).toBe(56);
    expect(await page.getByTestId("nav-rail-panel").evaluate((el) => getComputedStyle(el).boxShadow)).toBe("none");
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  await page.getByTestId("sidebar-toggle").click();
  await expect(page.getByTestId("sidebar-toggle")).toHaveAttribute("aria-pressed", "true");
  await page.mouse.move(900, 600);
  const pinnedPrimary = page.getByTestId("home-check-plan");
  await expect(pinnedPrimary).toBeVisible();
  expect((await pinnedPrimary.boundingBox())!.x, "1280 pinned").toBeGreaterThan(200);
  await page.getByTestId("sidebar-toggle").click();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page.getByTestId("home-headline")).toBeVisible({ timeout: 15_000 });

  // "Keep open" pins it: the old open layout (the page laid out beside it), the choice kept and restored before the first paint.
  const pin = page.getByTestId("sidebar-toggle");
  await expect(pin).toHaveAccessibleName("Keep open");
  await expect(pin).toHaveAttribute("aria-pressed", "false");
  await pin.click();
  await expect(pin).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("html")).toHaveAttribute("data-sidebar", "pinned");
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("tl-sidebar") ?? "{}").pinned)).toBe(true);
  await page.mouse.move(900, 600);
  expect(await railColumn(page)).toBe(200);
  expect(await panelWidth(page)).toBe(200);
  await expect(page.getByTestId("nav-pills").getByRole("link", { name: "Deals", exact: true }).locator(".side-label")).toHaveCSS("opacity", "1");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-sidebar", "pinned");
  expect(await railColumn(page)).toBe(200);
  await expect(page.getByTestId("sidebar-toggle")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("nav-pills").getByRole("link", { name: "Receivables" }).click();
  await expect(page).toHaveURL(/\/receivables/);
  expect(await railColumn(page)).toBe(200);
  await page.getByTestId("sidebar-toggle").click();
  await expect(page.locator("html")).not.toHaveAttribute("data-sidebar", "pinned");
  expect(await railColumn(page)).toBe(56);
});

test("rail: the pin works when storage throws, and below the laptop width there is no rail, only the tab bar", async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.setItem = function () {
      throw new Error("blocked");
    };
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await expect(page.getByTestId("home-headline")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("sidebar-toggle").click();
  expect(await railColumn(page)).toBe(200);
  await expect(page.getByTestId("sidebar-toggle")).toHaveAttribute("aria-pressed", "true");
  await page.setViewportSize({ width: 820, height: 900 });
  await expect(page.getByTestId("nav-rail")).toBeHidden();
  await expect(page.getByTestId("tab-bar")).toBeVisible();
});

test("rail: reduced motion opens it at once, and axe finds nothing serious on the collapsed rail or the open one, with the page beside it", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const { default: AxeBuilder } = await import("@axe-core/playwright");
  for (const path of ["/", "/cash", "/receivables", "/customers/BUYER-1"]) {
    await page.goto(path);
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15_000 });
    expect(await railColumn(page)).toBe(56);
    await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => undefined))));
    const closed = await new AxeBuilder({ page }).analyze();
    for (let i = 0; i < 8 && !(await page.getByTestId("nav-pills").getByRole("link", { name: "Home" }).evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press("Tab");
    await expect(page.getByTestId("nav-rail")).toHaveAttribute("data-rail", "open");
    expect(await panelWidth(page)).toBe(200);
    const open = await new AxeBuilder({ page }).analyze();
    for (const result of [closed, open]) {
      const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`), path).toEqual([]);
    }
  }
});

test("SegmentedTabs: the pill never leaves the track, and choosing never scrolls the page (Deals' queue is underline tabs: the control lives on Home, Receivables and the deal's timing)", async ({ page }) => {
  // The pill stays inside the track across a jump between options (no overshoot): Home's window control, the compact form.
  await page.goto("/?expand=1");
  await expect(page.getByTestId("home-window-60")).toBeVisible({ timeout: 15_000 });
  const inside = () =>
    page.evaluate(() => {
      const t = document.querySelector('[role=tablist][aria-label="Days shown"]')!.getBoundingClientRect();
      const p = document.querySelector('[role=tablist][aria-label="Days shown"] > span[aria-hidden]')!.getBoundingClientRect();
      return p.left >= t.left - 0.5 && p.right <= t.right + 0.5;
    });
  expect(await inside()).toBe(true);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const poll = page.evaluate(async () => {
    const out: boolean[] = [];
    const t = document.querySelector('[role=tablist][aria-label="Days shown"]')!.getBoundingClientRect();
    for (let i = 0; i < 24; i++) {
      const p = document.querySelector('[role=tablist][aria-label="Days shown"] > span[aria-hidden]')!.getBoundingClientRect();
      out.push(p.left >= t.left - 0.5 && p.right <= t.right + 0.5);
      await new Promise((r) => requestAnimationFrame(r));
    }
    return out;
  });
  await page.getByTestId("home-window-120").click();
  expect((await poll).every(Boolean)).toBe(true);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?expand=1");
  await expect(page.getByTestId("home-window-60")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("home-window-60").scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollBy(0, -60));
  const y = await page.evaluate(() => window.scrollY);
  expect(y).toBeGreaterThan(0);
  await page.getByTestId("home-window-60").click();
  await page.getByTestId("home-window-120").click();
  expect(Math.abs((await page.evaluate(() => window.scrollY)) - y)).toBeLessThan(2);
});

test("the owner's mockup tokens: the canvas app-wide, the palette and its dark pairs, the 24 px card with the one soft shadow on Home, the ink primary, the rail's white pill, a quiet Ask FLOW", async ({ page }) => {
  await page.goto("/cash");
  await expect(page.locator("h1").first()).toBeVisible({ timeout: 15_000 });
  // The canvas is the mockup's on every page; nothing else of Home's palette leaks into another page's cards.
  expect(await page.evaluate(() => getComputedStyle(document.body.parentElement!).backgroundColor)).toBe("rgb(229, 232, 232)");
  const colours = await page.evaluate(() => {
    const read = (v: string) => {
      const el = document.createElement("div");
      el.style.color = `var(${v})`;
      document.body.append(el);
      const c = getComputedStyle(el).color;
      el.remove();
      return c;
    };
    return Object.fromEntries(["--color-panel", "--color-card", "--color-f-ink", "--color-f-muted", "--color-f-line", "--color-f-purple", "--color-f-purple-soft", "--color-f-green", "--color-f-green-ink", "--color-f-amber", "--color-f-amber-ink", "--color-f-risk", "--color-f-btn", "--color-f-btn-ink"].map((v) => [v, read(v)]));
  });
  expect(colours).toEqual({
    "--color-panel": "rgb(248, 249, 249)",
    "--color-card": "rgb(255, 255, 255)",
    "--color-f-ink": "rgb(21, 27, 28)",
    "--color-f-muted": "rgb(88, 100, 104)",
    "--color-f-line": "rgb(216, 221, 221)",
    "--color-f-purple": "rgb(146, 82, 220)",
    "--color-f-purple-soft": "rgb(235, 222, 250)",
    "--color-f-green": "rgb(199, 233, 179)",
    "--color-f-green-ink": "rgb(35, 66, 32)",
    "--color-f-amber": "rgb(249, 212, 145)",
    "--color-f-amber-ink": "rgb(96, 65, 14)",
    "--color-f-risk": "rgb(168, 50, 34)",
    "--color-f-btn": "rgb(23, 29, 30)",
    "--color-f-btn-ink": "rgb(255, 255, 255)",
  });
  // The dark pairs the mockup gives are there for <html data-theme="dark">: the same tokens, other values; the app is light without it.
  await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
  const dark = await page.evaluate(() => {
    const el = document.createElement("div");
    el.style.color = "var(--color-f-amber)";
    document.body.append(el);
    const c = getComputedStyle(el).color;
    el.remove();
    return [c, getComputedStyle(document.documentElement).backgroundColor];
  });
  expect(dark).toEqual(["rgb(80, 65, 43)", "rgb(28, 34, 38)"]);
  await page.evaluate(() => document.documentElement.removeAttribute("data-theme"));
  // The rail: a vertical pill group; the current section is the white pill with the soft shadow, the others sit on the canvas.
  const nav = page.getByTestId("nav-pills");
  const active = nav.getByRole("link", { name: "Cash & funding" });
  await expect(active).toHaveAttribute("aria-current", "page");
  expect(await active.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(255, 255, 255)");
  expect(await active.evaluate((el) => getComputedStyle(el).boxShadow)).toContain("rgba(0, 0, 0, 0.08) 0px 1px 2px -1px");
  expect(await nav.getByRole("link", { name: "Deals", exact: true }).evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgba(0, 0, 0, 0)");
  // Ask FLOW is a quiet outlined input in the header (round two), not a floating pill and not a second filled button; a phone keeps the bar's cell.
  const ask = page.getByTestId("ask-header");
  expect(await ask.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(255, 255, 255)");
  expect(await ask.evaluate((el) => getComputedStyle(el).borderTopWidth)).toBe("1px");
  expect(await ask.evaluate((el) => getComputedStyle(el).borderTopLeftRadius)).toBe("9999px");
  expect(await page.getByTestId("ask-input").evaluate((el) => getComputedStyle(el).color)).toBe("rgb(36, 50, 74)");
  await expect(page.locator(".ask-trigger")).toHaveCount(0);
  // Home: the cards are the panel tone, 24 px, with the one soft shadow; the white row on a card; the filled button is the ink primary.
  await page.goto("/");
  await expect(page.getByTestId("hv2-cash-card")).toBeVisible({ timeout: 15_000 });
  for (const id of ["hv2-cash-card", "hv2-action", "hv2-outlook-card", "home-worklist-panel", "hv2-upcoming"]) {
    const card = await page.getByTestId(id).evaluate((el) => ({ bg: getComputedStyle(el).backgroundColor, radius: getComputedStyle(el).borderTopLeftRadius, shadow: getComputedStyle(el).boxShadow }));
    // The recommendation is tinted with the risk red while the cash would go negative (the alarm card): only its radius is pinned then.
    expect(card, id).toMatchObject(id === "hv2-action" ? { radius: "24px" } : { bg: "rgb(248, 249, 249)", radius: "24px" });
    if (id !== "hv2-action") expect(card.shadow, id).toContain("rgba(0, 0, 0, 0.08) 0px 1px 2px -1px");
  }
  expect(await page.getByTestId("home-check-plan").evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(23, 29, 30)");
  // The page is light only unless the dark hook is set.
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).colorScheme)).toBe("light");
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
  // The owner's mockup selection: a lavender tint with a 3 px ink rule (the rule is why the selection is never colour alone).
  const want = { bg: "rgb(235, 222, 250)", rule: "3px", ruleColor: "rgb(23, 29, 30)" };
  await page.goto("/receivables?customer=BUYER-1"); // /receivables lists customers; the customer's page holds the invoices
  await expect(page.getByTestId("recv-RCV-A")).toBeVisible({ timeout: 15_000 });
  expect(await selected(page.getByTestId("recv-RCV-A"))).toEqual(want);
  // Every text on the selected row keeps 4.5:1 against the tint; the chosen row also says so to assistive tools (aria-current) besides the rule.
  await expect(page.getByTestId("recv-RCV-A").locator('[aria-current="true"]')).toHaveCount(1);
  const worst = await page.getByTestId("recv-RCV-A").evaluate((row) => {
    const c = document.createElement("canvas").getContext("2d", { willReadFrequently: true })!;
    const rgb = (css: string) => {
      c.clearRect(0, 0, 1, 1);
      c.fillStyle = "#000";
      c.fillStyle = css;
      c.fillRect(0, 0, 1, 1);
      return Array.from(c.getImageData(0, 0, 1, 1).data.slice(0, 3));
    };
    const lum = ([r, g, b]: number[]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    const lin = (v: number) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    const bg = lum(rgb(getComputedStyle(row).backgroundColor));
    let min = 21;
    for (const el of Array.from(row.querySelectorAll("*"))) {
      if (![...el.childNodes].some((n) => n.nodeType === 3 && (n.textContent ?? "").trim())) continue;
      const fg = lum(rgb(getComputedStyle(el).color));
      min = Math.min(min, (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05));
    }
    return min;
  });
  expect(worst, "the lowest text contrast on the selected row").toBeGreaterThanOrEqual(4.5);
  // Deals takes the owner's mockup look (a lavender row with a purple edge for the selection); the page raises no decision card.
  await checkedDeal(page);
  expect(await decisionCards()).toBe(0);
  // The deal is its own page, so the list is hidden while it is open; the open deal's row is still the one selected style there (the lavender tint), and it is what All deals comes back to.
  const chosen = page.locator('[data-testid="queue-row"][data-selected="true"] > div[aria-current="true"]');
  await expect(chosen).toHaveCount(1);
  expect(await chosen.evaluate((el) => getComputedStyle(el).backgroundColor), "a tinted row").not.toBe("rgba(0, 0, 0, 0)");
});

test("rail: a bad stored value cannot skip the language, and the folds open at once under reduced motion", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("tl-sidebar", "{not json");
    localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" }));
  });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page.locator("html")).not.toHaveAttribute("data-sidebar", "pinned");
  // A native <details> opens by height through ::details-content; reduced motion switches that transition off too.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/cash");
  await expect(page.locator("h1").first()).toBeVisible({ timeout: 15_000 });
  const transition = await page.evaluate(() => {
    const d = document.createElement("details");
    d.innerHTML = "<summary>x</summary><p>y</p>";
    document.body.append(d);
    const t = getComputedStyle(d, "::details-content").transitionProperty;
    d.remove();
    return t;
  });
  expect(["none", ""]).toContain(transition);
});

/**
 * The rail on every page (hover expansion that clipped or covered content). On Home, Deals, Customer, Approvals, Cash, Receivables and Activity, at 1280, 1440 and 1680:
 * collapsed, the first content element starts right of the 56 px rail plus a gutter and nothing is under the rail; hovered open, the panel is 200 px wide, inside the viewport, and
 * what the pointer would hit at its labels and its foot is the panel itself (no sticky header, page stacking context or scroll container above it); pinned open, the content
 * starts right of the 200 px track plus the gutter.
 */
const RAIL_PAGES = ["/", "/deals", "/customers/BUYER-1", "/approvals", "/cash", "/receivables", "/activity"] as const;
const GUTTER = 16;

/** The left edge of the page's first content: the first heading or card inside `main`, the box a reader sees start. */
const contentLeft = (page: Pg) =>
  page.locator("main").evaluate((main) => {
    const first = Array.from(main.querySelectorAll<HTMLElement>("h1, h2, [data-testid], section, article")).find((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 40 && r.height > 8 && getComputedStyle(el).visibility !== "hidden";
    });
    const r = (first ?? main).getBoundingClientRect();
    return Math.round(r.left);
  });

/** The open panel's box, and what the pointer meets at its foot and at each destination's label. */
const panelProbe = (page: Pg) =>
  page.getByTestId("nav-rail-panel").evaluate((panel) => {
    const r = panel.getBoundingClientRect();
    const hits = (el: Element | null) => {
      if (!el) return { ok: false, why: "missing" };
      const b = el.getBoundingClientRect();
      const x = Math.min(Math.max(b.left + 4, 0), innerWidth - 1);
      const y = Math.min(Math.max(b.top + b.height / 2, 0), innerHeight - 1);
      const top = document.elementFromPoint(x, y);
      return { ok: Boolean(top && panel.contains(top)), why: top ? `${top.tagName}.${String(top.className).slice(0, 40)}` : "none", inView: b.left >= 0 && b.right <= innerWidth && b.top >= 0 && b.bottom <= innerHeight };
    };
    const labels = Array.from(panel.querySelectorAll("#nav-pills .side-label")).map((el) => ({ text: el.textContent, ...hits(el), clippedByPanel: el.getBoundingClientRect().right > r.right }));
    // The whole 200 px box: a grid of points, each of which must hit the panel or something inside it (a page's positioned element, a z-index or a stacking context of its own must never paint over it).
    const covered: string[] = [];
    for (let y = r.top + 6; y < Math.min(r.bottom, innerHeight) - 2; y += 14) {
      for (let x = r.left + 6; x < r.right - 2; x += 14) {
        const top = document.elementFromPoint(x, y);
        if (!top || !panel.contains(top)) covered.push(`${Math.round(x)},${Math.round(y)} ${top ? `${top.tagName}.${String(top.className).slice(0, 30)}` : "none"}`);
      }
    }
    const foot = panel.querySelector(".side-foot");
    const toggle = panel.querySelector('[data-testid="sidebar-toggle"]');
    return {
      width: Math.round(r.width),
      left: Math.round(r.left),
      right: Math.round(r.right),
      bottom: Math.round(r.bottom),
      vw: innerWidth,
      vh: innerHeight,
      labels,
      covered: covered.slice(0, 5),
      foot: hits(foot),
      footText: foot?.textContent ?? "",
      footOverflows: foot ? foot.getBoundingClientRect().bottom > r.bottom || foot.scrollHeight > foot.clientHeight + 1 : true,
      toggle: hits(toggle),
    };
  });

test("rail: on every page the collapsed rail covers no content, the open panel is whole and on top, and pinned the content sits beside it", async ({ page }) => {
  test.setTimeout(240_000);
  for (const [width, height] of [[1280, 720], [1440, 900], [1680, 1000], [1440, 700]] as const) {
    await page.setViewportSize({ width, height });
    for (const path of RAIL_PAGES) {
      const at = `${path} at ${width}x${height}`;
      await page.goto(path);
      await expect(page.locator("main h1").first()).toBeVisible({ timeout: 15_000 });
      await page.mouse.move(width - 100, 500);
      await expect(page.getByTestId("nav-rail")).toHaveAttribute("data-rail", "closed");
      // Collapsed: the content starts right of the 56 px rail and a gutter.
      expect(await railColumn(page), `${at} column`).toBe(56);
      expect(await contentLeft(page), `${at} collapsed content left`).toBeGreaterThanOrEqual(56 + GUTTER);
      // Hovered open: 200 px wide, inside the window, its words and its foot not under anything else.
      await page.getByTestId("nav-pills").getByRole("link", { name: "Home" }).hover();
      await expect.poll(() => panelWidth(page), at).toBe(200);
      const open = await panelProbe(page);
      expect(open.left, `${at} open left`).toBe(0);
      expect(open.right, `${at} open right`).toBe(200);
      expect(open.bottom, `${at} open bottom within the window`).toBeLessThanOrEqual(open.vh);
      expect(open.labels.length, `${at} eight labels`).toBe(8); // the sections and the doors to the sandbox and the old capex screen
      for (const l of open.labels) {
        expect(l.ok, `${at} label ${l.text} is on top (${l.why})`).toBe(true);
        expect(l.clippedByPanel, `${at} label ${l.text} fits the panel`).toBe(false);
      }
      expect(open.footText, `${at} foot note`).toContain("simulated company");
      expect(open.covered, `${at} nothing paints over the open panel`).toEqual([]);
      expect(open.foot.ok, `${at} foot note on top (${open.foot.why})`).toBe(true);
      expect(open.footOverflows, `${at} foot note fits the panel`).toBe(false);
      expect(open.toggle.ok, `${at} Keep open on top (${open.toggle.why})`).toBe(true);
      // Scrolled to the foot of the page, the same: the panel stays whole and on top.
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      await page.mouse.move(width - 100, 500);
      await page.getByTestId("nav-pills").getByRole("link", { name: "Home" }).hover();
      await expect.poll(() => panelWidth(page), at).toBe(200);
      const scrolled = await panelProbe(page);
      expect(scrolled.covered, `${at} scrolled: nothing paints over the open panel`).toEqual([]);
      expect(scrolled.foot.ok && scrolled.toggle.ok, `${at} scrolled: the foot is on top`).toBe(true);
      // Pinned open: the content is laid out beside the 200 px track.
      await page.mouse.move(width - 100, 500);
      await page.getByTestId("sidebar-toggle").click({ force: true });
      await page.mouse.move(width - 100, 500);
      await expect(page.locator("html")).toHaveAttribute("data-sidebar", "pinned");
      expect(await railColumn(page), `${at} pinned column`).toBe(200);
      expect(await contentLeft(page), `${at} pinned content left`).toBeGreaterThanOrEqual(200 + GUTTER);
      const pinned = await panelProbe(page);
      expect(pinned.foot.ok && pinned.toggle.ok, `${at} pinned foot on top`).toBe(true);
      await page.getByTestId("sidebar-toggle").click();
      await expect(page.locator("html")).not.toHaveAttribute("data-sidebar", "pinned");
    }
  }
});
