import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { runPlan, openOperatorTools } from "./helpers";

/**
 * The page pattern of the A1 pass in mock mode (recorded demo path): the answer as the title, one picture, one raised action, unboxed sections.
 * Receivables: the "Who pays when" picture, the facts row, the chase bar. Activity: the rail. Home's open offer and the sidebar counts are in home.spec.ts.
 */

test.beforeEach(async ({ context }, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded demo path");
  await context.addInitScript(() => {
    try {
      sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: "mock-owner" }));
    } catch {
      /* storage unavailable */
    }
  });
});

async function advanceTo34(page: Page, to: string) {
  await page.goto("/demo");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto(to);
}

const overflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

// ---------------------------------------------------------------- Receivables

test("Receivables day 0: Who pays when has one mark, the facts are one unboxed row, no bar, one h1", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-absent", "1")); // the page of before (the fallback)
  await page.goto("/receivables");
  await expect(page.getByTestId("recv-picture-svg")).toBeVisible();
  await expect(page.getByTestId("recv-picture").getByRole("heading", { name: "Who pays when" })).toBeVisible();
  const marks = page.locator('[data-testid^="recv-mark-RCV"]');
  await expect(marks).toHaveCount(1);
  await expect(marks.first()).toHaveAttribute("data-state", "later");
  const facts = page.getByTestId("recv-summary");
  await expect(facts.getByTestId("recv-outstanding")).toHaveText("¥420,000.00");
  await expect(facts.locator("dl")).toHaveCount(1);
  await expect(facts.locator(".shadow-card")).toHaveCount(0);
  // Nobody is late: no raised bar and no Chase payment in it.
  await expect(page.getByTestId("recv-top-action")).toHaveCount(0);
  await expect(page.locator('[data-testid^="chase-top-open-"]')).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  // The picture has a table behind it for a screen reader.
  await expect(page.getByTestId("recv-picture-table").locator("tbody tr")).toHaveCount(1);
});

test("Receivables day 34: the late invoice is a filled mark left of Today, the others are outlined, and pressing a mark highlights its row", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-absent", "1")); // the page of before (the fallback)
  await advanceTo34(page, "/receivables");
  await expect(page.getByTestId("recv-picture-svg")).toBeVisible();
  await expect(page.locator('[data-testid^="recv-mark-"][data-state]')).toHaveCount(3);
  await expect(page.getByTestId("recv-mark-RCV-A")).toHaveAttribute("data-state", "late");
  await expect(page.locator('[data-testid^="recv-mark-"][data-state="soon"]')).toHaveCount(1);
  await expect(page.locator('[data-testid^="recv-mark-"][data-state="later"]')).toHaveCount(1);
  const today = await page.getByTestId("recv-today-line").boundingBox();
  const late = await page.getByTestId("recv-mark-RCV-A").locator("circle").nth(1).boundingBox();
  expect(late!.x + late!.width).toBeLessThan(today!.x + 1);
  // Late is filled; the others are outlined with the surface fill (shape and fill, not hue alone).
  const fills = await page.locator('[data-testid^="recv-mark-"][data-state]').evaluateAll((els) => els.map((el) => [el.getAttribute("data-state"), getComputedStyle(el.querySelectorAll("circle")[1]).fill]));
  const lateFill = fills.find((f) => f[0] === "late")![1];
  for (const [state, fill] of fills) if (state !== "late") expect(fill).not.toBe(lateFill);
  // The server's amount and the day in words, with the buyer's initials.
  await expect(page.getByTestId("recv-mark-label-RCV-A")).toContainText("¥160,000.00 · 2 days ago");
  await expect(page.getByTestId("recv-mark-label-RCV-A")).toContainText("FH");
  await page.getByTestId("recv-mark-RCV-A").click();
  await expect(page.getByTestId("recv-RCV-A")).toHaveAttribute("data-highlight", "true");
  await expect(page.getByTestId("recv-mark-RCV-A")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("recv-mark-RCV-A")).toHaveAttribute("aria-controls", "RCV-A");
  await expect(page.getByTestId("recv-RCV-A")).toBeInViewport();
  // The mark is a button for the keyboard too.
  await page.getByTestId("recv-mark-RCV-A").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("recv-RCV-A")).toHaveAttribute("data-highlight", "true");
});

test("Receivables day 34: the chase bar is the one raised surface, sticky from lg, in flow below it; one h1 and at most one filled primary", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-absent", "1")); // the page of before (the fallback)
  await page.setViewportSize({ width: 1280, height: 800 });
  await advanceTo34(page, "/receivables");
  const bar = page.getByTestId("recv-top-action");
  await expect(bar).toBeVisible();
  await expect(bar.getByRole("button", { name: /Chase payment/ })).toBeVisible();
  expect(await bar.evaluate((el) => getComputedStyle(el).position)).toBe("sticky");
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  const filled = await page.evaluate(() => Array.from(document.querySelectorAll("main button, main a")).filter((el) => getComputedStyle(el).backgroundColor === "rgb(3, 104, 233)").length);
  expect(filled).toBeLessThanOrEqual(1);
  await page.setViewportSize({ width: 800, height: 900 });
  expect(await bar.evaluate((el) => getComputedStyle(el).position)).not.toBe("sticky");
});

test("Receivables day 34: the buyer's name is on one line at 1440, and there is no sideways scroll at 390", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-absent", "1")); // the page of before (the fallback)
  await advanceTo34(page, "/receivables");
  const name = page.getByTestId("recv-RCV-A").locator("td span.break-words").first();
  expect((await name.boundingBox())!.height).toBeLessThan(24);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByTestId("recv-picture-svg")).toBeVisible();
  expect(await overflow(page)).toBeLessThanOrEqual(1);
});

test("Receivables day 34 in Chinese: the picture, its legend, the facts and the bar are in Chinese", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-receivables-absent", "1")); // the page of before (the fallback)
  await advanceTo34(page, "/receivables");
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.reload();
  await expect(page.getByTestId("recv-picture")).toContainText("谁何时付款");
  await expect(page.getByTestId("recv-picture-legend")).toContainText("已逾期");
  await expect(page.getByTestId("recv-picture")).toContainText("今天");
  await expect(page.getByTestId("recv-summary")).toContainText("逾期金额");
  await expect(page.getByTestId("recv-top-action")).toContainText("建议的下一步");
});

// ---------------------------------------------------------------- Activity

async function railAt34(page: Page) {
  await advanceTo34(page, "/cash"); // the plan is run on Cash & funding
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toBeVisible();
  await page.goto("/activity");
  await expect(page.getByTestId("activity-list")).toBeVisible();
}

test("Activity: a when-word per row, who acted and what became of it on one quiet line, time passing as a system row, one evidence fold per row", async ({ page }) => {
  await railAt34(page);
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  const rows = page.getByTestId("activity-list").getByTestId("activity-row");
  expect(await rows.count()).toBeGreaterThan(2);
  const whens = await rows.getByTestId("activity-when").allTextContents();
  expect(whens.every((w) => w.trim().length > 0)).toBe(true);
  await expect(rows.first().getByTestId("activity-when")).toHaveText(/today/i);
  expect(new Set(whens).size).toBeGreaterThan(1);
  // Every row names who acted, in the server's words, beside its status; the clock's row is the system's.
  for (const actor of await rows.getByTestId("activity-actor").allTextContents()) expect(actor.trim().length).toBeGreaterThan(0);
  const passed = page.locator('[data-testid="activity-row"][data-kind="system"]').first();
  await expect(passed.getByTestId("activity-event")).toContainText(/days? passed/);
  await expect(passed.getByTestId("activity-actor")).toHaveText("The system");
  await expect(rows.first().getByTestId("activity-meta")).toContainText(" · ");
  const entry = rows.first();
  await expect(entry.getByTestId("activity-evidence").locator("> summary")).toHaveText("Evidence");
  await entry.getByTestId("activity-evidence").locator("> summary").click();
  await expect(entry.getByTestId("activity-record-body")).toBeVisible();
});

test("Activity: the category tabs narrow the list by kind and never change its order", async ({ page }) => {
  await railAt34(page);
  const filters = page.getByTestId("activity-filters");
  await expect(filters.getByTestId("activity-filter-all")).toHaveAttribute("aria-selected", "true");
  for (const id of ["cash", "documents"]) await expect(filters.getByTestId(`activity-filter-${id}`)).toBeVisible();
  const order = () => page.getByTestId("activity-list").getByTestId("activity-event").allTextContents();
  const all = await order();
  await filters.getByTestId("activity-filter-documents").click();
  await expect(filters.getByTestId("activity-filter-documents")).toHaveAttribute("aria-selected", "true");
  const docs = await order();
  expect(docs.length).toBe(3);
  expect(await page.locator('[data-testid="activity-row"]:not([data-category="documents"])').count()).toBe(0);
  await filters.getByTestId("activity-filter-cash").click();
  const positions = (await order()).map((k) => all.indexOf(k));
  expect(positions.length).toBeGreaterThan(0);
  expect(positions.every((p) => p >= 0)).toBe(true);
  expect([...positions].sort((a, b) => a - b)).toEqual(positions);
  await filters.getByTestId("activity-filter-all").click();
  expect(await order()).toEqual(all);
});

test("Activity in Chinese: the tabs, the search and the evidence fold", async ({ page }) => {
  await railAt34(page);
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.reload();
  await expect(page.getByTestId("activity-filter-all")).toHaveText(/全部/);
  await expect(page.getByTestId("activity-search")).toHaveAttribute("placeholder", "按客户或事件搜索");
  await expect(page.getByTestId("activity-evidence").first().locator("> summary")).not.toHaveText("Evidence");
});

test("Activity: an empty record shows the empty state with no tabs, and the page has no sideways scroll at 390", async ({ page }) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("tl-mock-store-v2", JSON.stringify({ offers: {}, evaluated: [], negotiated: {}, ops: [], commitments: [], approvals: [], securityScene: false })),
  );
  await page.goto("/activity");
  await expect(page.getByTestId("activity-empty")).toBeVisible();
  await expect(page.getByTestId("activity-filters")).toHaveCount(0);
  await expect(page.getByTestId("chain-status")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await overflow(page)).toBeLessThanOrEqual(1);
});

test("Activity day 34: no sideways scroll at 390", async ({ page }) => {
  await railAt34(page);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await overflow(page)).toBeLessThanOrEqual(1);
});
