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
