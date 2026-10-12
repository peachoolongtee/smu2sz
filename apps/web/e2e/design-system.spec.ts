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
    const found: string[] = [];
    document.querySelectorAll("details").forEach((d) => (d.open = true));
    const walker = document.createTreeWalker(document.querySelector("main") ?? document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const text = (n.textContent ?? "").trim();
      const el = n.parentElement;
      if (!text || !el || el.closest("svg, script, style, sup") || !figure.test(text)) continue;
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
  expect(vars["--text-value"]).toBeGreaterThanOrEqual(28);
  expect(vars["--text-value"]).toBeLessThanOrEqual(36);
  // The Home headline is 34 px on a desktop, 30 px at tablet width and 24 px on a phone, and a major value is tabular.
  expect(await page.getByTestId("home-headline").evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBe(34);
  await page.setViewportSize({ width: 820, height: 900 });
  expect(await page.getByTestId("home-headline").evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBe(30);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.getByTestId("home-headline").evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBe(24);
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
