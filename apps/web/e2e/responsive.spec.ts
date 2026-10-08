import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { STORY_STEPS, walkStory } from "./helpers";

/** Runs on a phone viewport (and desktop): no page may scroll sideways, the story bar stays reachable in Demo mode, and the Business home puts the answer first. */

const ENGINE_ROUTES = ["/demo", "/chat", "/mandate", "/inbox", "/trajectory", "/funding", "/verdict", "/capex", "/ledger", "/approvals", "/security", "/evidence"];
const BUSINESS_ROUTES = ["/", "/deals", "/cash", "/receivables", "/approvals", "/activity", "/limits"];

async function overflowX(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

test("no page overflows horizontally after the demo has run", async ({ page }) => {
  await page.goto("/demo");
  await walkStory(page, STORY_STEPS);
  await expect(page).toHaveURL(/\/activity/);
  for (const route of ENGINE_ROUTES) {
    await page.goto(route);
    await expect(page.locator("h1")).toBeVisible();
    // Tables scroll inside their own region; the page itself must not.
    expect(await overflowX(page), `${route} overflows horizontally`).toBeLessThanOrEqual(1);
  }
  // The Business shell, with the deal of the demo on the books.
  await page.getByLabel("Business").click(); // the radio shows the shell on screen, so it changes once the route has
  await expect(page).toHaveURL(/\/$/);
  for (const route of BUSINESS_ROUTES) {
    await page.goto(route);
    await expect(page.locator("h1")).toHaveCount(1);
    expect(await overflowX(page), `${route} overflows horizontally`).toBeLessThanOrEqual(1);
  }
});

test("the Business home puts the status and the next action in the first screen, with no demo control", async ({ page }) => {
  await page.goto("/");
  const status = page.getByTestId("home-status");
  await expect(status).toBeInViewport();
  await expect(page.getByTestId("home-headline")).toBeInViewport();
  await expect(page.getByTestId("home-next-action")).toBeVisible();
  await expect(page.getByRole("region", { name: "Guided demo" })).toHaveCount(0);
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  const menu = page.getByRole("button", { name: "Open navigation" });
  if (await menu.isVisible()) {
    await menu.click();
    await page.getByRole("link", { name: "Cash & funding" }).click();
  } else {
    await page.getByRole("link", { name: "Cash & funding" }).click();
  }
  await expect(page).toHaveURL(/\/cash/);
});

test("Business navigation: five pills on a desktop, the same five tabs on a phone, the mode switch and Ask FLOW always visible", async ({ page }) => {
  await page.goto("/");
  const phone = (page.viewportSize()?.width ?? 1440) < 1024;
  const names = ["Home", "Deals", "Cash & funding", "Receivables", "Activity"];
  const bar = page.getByTestId(phone ? "tab-bar" : "nav-pills");
  await expect(bar).toBeVisible();
  await expect(page.getByTestId(phone ? "nav-pills" : "tab-bar")).toBeHidden();
  await expect(bar.getByRole("link")).toHaveText(phone ? ["Home", "Deals", "Cash", "Receivables", "Activity"] : names);
  for (const n of names) await expect(bar.getByRole("link", { name: n, exact: true })).toBeVisible();
  await expect(bar.locator('[aria-current="page"]')).toHaveText(phone ? "Home" : "Home");
  // Buy equipment and What-if are doors from Cash & funding, not sections; no hamburger in Business mode.
  await expect(page.getByRole("button", { name: "Open navigation" })).toHaveCount(0);
  await expect(page.getByRole("radio", { name: "Business" })).toBeAttached();
  await expect(page.getByTestId("chat-open")).toContainText("Ask FLOW");
  await expect(page.getByTestId("chat-open")).toBeInViewport();
  // Ask FLOW never covers content: on a phone it is the bar's last cell (beside the five tabs, not over one); from sm a pill above the bar.
  const chat = (await page.getByTestId("chat-open").boundingBox())!;
  if (phone) {
    const barBox = (await bar.boundingBox())!;
    expect(chat.y).toBeGreaterThanOrEqual(barBox.y - 1);
    for (const link of await bar.getByRole("link").all()) {
      const l = (await link.boundingBox())!;
      expect(l.x + l.width, "a tab runs under Ask FLOW").toBeLessThanOrEqual(chat.x + 1);
    }
  }
  await bar.getByRole("link", { name: "Deals", exact: true }).click();
  await expect(page).toHaveURL(/\/deals/);
  // Each page names its tab, and the document says its language.
  await expect(page).toHaveTitle("Deals · FLOW 流");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByTestId(phone ? "tab-bar" : "nav-pills").locator('[aria-current="page"]')).toHaveText("Deals");
  // The account sheet carries the identity and the limits.
  await page.getByTestId("account-menu").locator("> summary").click();
  await expect(page.getByTestId("account-identity")).toBeVisible();
  await page.getByTestId("account-limits").click();
  await expect(page).toHaveURL(/\/limits/);
});

test("the last content clears the bottom bar and Ask FLOW on every Business page", async ({ page }) => {
  for (const route of BUSINESS_ROUTES) {
    await page.goto(route);
    await expect(page.locator("h1")).toHaveCount(1);
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    const covered = await page.evaluate(() => {
      const chat = document.querySelector('[data-testid="chat-open"]')!.getBoundingClientRect();
      const bar = document.querySelector('[data-testid="tab-bar"]');
      const barTop = bar && getComputedStyle(bar).display !== "none" ? bar.getBoundingClientRect().top : innerHeight;
      // Every control in main, at the end of the page, sits above the bar and outside the Ask FLOW box.
      // A control inside a fold that is closed is not on screen (its box is clipped, not removed): the fold's own summary is.
      const folded = (el: Element) => Boolean((el.tagName === "SUMMARY" ? el.parentElement?.parentElement : el)?.closest("details:not([open])"));
      return Array.from(document.querySelectorAll("main a[href], main button, main summary, main input")).filter((el) => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0 || folded(el)) return false;
        const hitsChat = r.left < chat.right && r.right > chat.left && r.top < chat.bottom && r.bottom > chat.top;
        return hitsChat || r.bottom > barTop;
      }).length;
    });
    expect(covered, `${route}: controls under the bar or Ask FLOW at the end of the page`).toBe(0);
  }
});

test("a hard load names the tab: the title survives hydration", async ({ page }) => {
  for (const [route, title] of [["/deals", "Deals · FLOW 流"], ["/cash", "Cash & funding · FLOW 流"], ["/receivables", "Receivables · FLOW 流"], ["/limits", "Limits · FLOW 流"], ["/", "FLOW 流"]] as const) {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(title);
    await page.reload();
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(title);
  }
});

test("the account sheet closes on Escape (focus returns to its button) and on a press outside", async ({ page }) => {
  await page.goto("/");
  const menu = page.getByTestId("account-menu");
  const summary = menu.locator("> summary");
  await summary.click();
  await expect(menu).toHaveAttribute("open", "");
  await page.keyboard.press("Escape");
  await expect(menu).not.toHaveAttribute("open", "");
  await expect(summary).toBeFocused();
  await summary.click();
  await expect(menu).toHaveAttribute("open", "");
  // The far left edge, clear of the sheet (it hangs from the right).
  await page.mouse.click(2, 400);
  await expect(menu).not.toHaveAttribute("open", "");
});

test("a phone's controls reach 44 px (the pill itself may stay compact: its hit area is what a finger meets)", async ({ page }) => {
  test.skip((page.viewportSize()?.width ?? 1440) >= 1024, "a desktop keeps its compact controls");
  for (const route of ["/", "/cash", "/receivables"]) {
    await page.goto(route);
    await expect(page.locator("h1")).toHaveCount(1);
    const short = await page.evaluate(() => {
      const hit = (el: Element, x: number, y: number) => {
        const h = document.elementFromPoint(x, y);
        return !h || x < 0 || y < 0 || x >= innerWidth || y >= innerHeight || el.contains(h) || h.contains(el);
      };
      return Array.from(document.querySelectorAll("header a, header button, header summary, header label, main button, main summary, nav[data-testid=tab-bar] a"))
        .filter((el) => (el as HTMLElement).offsetParent !== null && !(el.closest("details:not([open])") && el.tagName !== "SUMMARY"))
        .filter((el) => {
          const r = el.getBoundingClientRect();
          const cx = r.x + r.width / 2;
          const cy = r.y + r.height / 2;
          const okW = r.width >= 44 || (hit(el, cx - 21, cy) && hit(el, cx + 21, cy));
          const okH = r.height >= 44 || (hit(el, cx, cy - 21) && hit(el, cx, cy + 21));
          return !(okW && okH);
        })
        .map((el) => `${el.tagName}:${(el.textContent ?? "").trim().slice(0, 24)}`);
    });
    expect(short, `${route}: controls a finger cannot hit at 44 px`).toEqual([]);
  }
});

test("the stepper and navigation are reachable in Demo mode", async ({ page }) => {
  await page.goto("/mandate");
  await expect(page.getByTestId("demo-next")).toBeInViewport();
  const menu = page.getByRole("button", { name: "Open navigation" });
  if (await menu.isVisible()) {
    await menu.click();
    await page.getByRole("link", { name: "Funding" }).click();
    await expect(page).toHaveURL(/\/funding/);
  } else {
    await page.getByRole("link", { name: "Funding" }).click();
    await expect(page).toHaveURL(/\/funding/);
  }
});

test("the slide-over chat fits the viewport with a long reply", async ({ page }) => {
  await page.goto("/mandate");
  // Already signed in as the owner by the fixture.
  await page.getByTestId("chat-open").click();
  const panel = page.getByRole("dialog", { name: "Ask FLOW" });
  await expect(panel).toBeVisible();
  await page.getByTestId("prompt-evaluate").click();
  await expect(panel.getByTestId("chat-awaiting")).toBeVisible();
  // The panel slides in (0.18 s) and the mock answers in 10 ms: measure once the slide has finished, not mid-way.
  await expect.poll(() => panel.evaluate((el) => el.getAnimations().every((a) => a.playState === "finished"))).toBe(true);
  const viewport = page.viewportSize()!;
  const box = (await panel.boundingBox())!;
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 1);
  expect(box.height).toBeLessThanOrEqual(viewport.height + 1);
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  expect(await panel.evaluate((el) => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(1);
  // The composer stays reachable while the reply is long.
  await expect(panel.getByRole("textbox", { name: "Message" })).toBeInViewport();
});

test("Deals (checked) and Cash on a phone: no sideways scroll, the folded inbox and the comparison fit, every control reaches 44 px", async ({ page }) => {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Counter recommended");
  await expect(page.getByTestId("inbox-collapsed")).toBeVisible();
  expect(await overflowX(page), "/deals overflows horizontally").toBeLessThanOrEqual(1);
  // One workspace order at every width, the server's: the folded inbox row, the buyer, what FLOW recommends, the priced response, then the asks and the costs.
  const ids = ["inbox-collapsed", "deal-selected", "deal-recommendation-card", "counters", "deal-ask", "deal-impact", "deal-advanced"];
  const tops = await page.evaluate((list) => list.map((id) => {
    const el = document.getElementById(id) ?? document.querySelector(`[data-testid="${id}"]`);
    return el ? el.getBoundingClientRect().top + scrollY : -1;
  }), ids);
  expect(tops.every((y) => y >= 0)).toBe(true);
  expect(tops).toEqual([...tops].sort((a, b) => a - b));
  await page.goto("/cash");
  await expect(page.getByTestId("cash-options-list")).toBeVisible();
  expect(await overflowX(page), "/cash overflows horizontally").toBeLessThanOrEqual(1);
  const narrow = (page.viewportSize()?.width ?? 1440) < 1024;
  if (narrow) {
    for (const [route, ready] of [["/deals", "inbox-collapsed"], ["/cash", "cash-options-list"]] as const) {
      await page.goto(route);
      await expect(page.getByTestId(ready)).toBeVisible();
      const short = await page.evaluate(() =>
        Array.from(document.querySelectorAll("main a, main button, main summary"))
          .filter((el) => (el as HTMLElement).offsetParent !== null && !(el.closest("details:not([open])") && el.tagName !== "SUMMARY"))
          // The horizon pills keep a compact look with a 44 px hit area (covered by the controls test above).
          .filter((el) => el.getBoundingClientRect().height < 44 && !el.matches("a:not([class*=button]), summary") && !el.closest("[role=group], [role=radiogroup]"))
          .map((el) => `${el.tagName}:${(el.textContent ?? "").trim().slice(0, 24)}`),
      );
      expect(short, `${route}: buttons under 44 px`).toEqual([]);
    }
  }
});

/**
 * Phone priority (wayfinder #65 Wave 7, F16). At 412 x 915 the owner's answer comes first: Home's primary action, Deals' recommendation and
 * priced response, Cash's options. The measurements are written to PHONE_MEASURE_OUT (a JSON path) when it is set. Desktop keeps the DOM order.
 */
const measured: Record<string, unknown> = {};

async function topOf(page: Page, id: string): Promise<{ top: number; bottom: number } | null> {
  return page.evaluate((i) => {
    const el = document.getElementById(i) ?? document.querySelector(`[data-testid="${i}"]`);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { top: Math.round(r.top + scrollY), bottom: Math.round(r.bottom + scrollY) };
  }, id);
}

test("phone priority: Home's primary action, Deals' priced response and Cash's options sit in the first screens at 412 x 915", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "phone", "the order is the narrow screen's; the desktop keeps the DOM order checked above");
  await page.setViewportSize({ width: 412, height: 915 });
  // Home: the status, then the priced action with its button above the tab bar, with no scroll.
  await page.goto("/");
  const alertId = await page.getByTestId("home-next-action").getAttribute("data-alert");
  const run = page.getByTestId(`fix-open-${alertId}`);
  await expect(run).toBeVisible();
  const box = (await run.boundingBox())!;
  const tab = (await page.getByTestId("tab-bar").boundingBox())!;
  expect(box.y + box.height, "the primary action is inside the first 915 px").toBeLessThanOrEqual(915);
  expect(box.y + box.height, "and is not behind the tab bar").toBeLessThanOrEqual(tab.y);
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  measured.home = { status: await topOf(page, "home-status"), action: await topOf(page, "home-next-action"), primary: { top: Math.round(box.y), bottom: Math.round(box.y + box.height) }, tabBarTop: Math.round(tab.y), pageHeight: await page.evaluate(() => document.documentElement.scrollHeight) };

  // Deals, evaluated: the recommendation card's top edge and the bound Send are inside the first screen; the inbox row and the asks come after.
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Counter recommended");
  const rec = (await topOf(page, "deal-recommendation-card"))!;
  const send = await page.getByTestId("deal-send").boundingBox();
  const inbox = (await topOf(page, "inbox-collapsed"))!;
  const asks = (await topOf(page, "deal-ask"))!;
  expect(inbox.top, "the inbox is one folded row above the buyer").toBeLessThan((await topOf(page, "deal-selected"))!.top);
  await expect(page.getByTestId("deal-steps")).toHaveCount(0);
  await expect(page.getByTestId("deal-state-chip")).toContainText("Counter recommended");
  expect(rec.top, "the recommendation card starts in the first screen").toBeLessThan(915);
  expect(send, "the bound Send is on the page").not.toBeNull();
  expect(send!.y + send!.height, "the Send button is inside the first 915 px").toBeLessThanOrEqual(915);
  expect(send!.y + send!.height, "and above the tab bar").toBeLessThanOrEqual(tab.y);
  expect(asks.top, "the asks come after the priced response").toBeGreaterThan(send!.y + send!.height);
  measured.deals = { recommendation: rec, send: { top: Math.round(send!.y), bottom: Math.round(send!.y + send!.height) }, inbox, asks, pageHeight: await page.evaluate(() => document.documentElement.scrollHeight) };

  // Cash: the position strip, the plan, then the comparison; its options list starts inside the first two screens.
  await page.goto("/cash");
  await expect(page.getByTestId("cash-options-list")).toBeVisible();
  const options = (await topOf(page, "cash-options-list"))!;
  const plan = (await topOf(page, "home-next-action"))!;
  const cashRun = page.getByTestId(`fix-open-${alertId}`);
  const cashBox = (await cashRun.boundingBox())!;
  expect(cashBox.y + cashBox.height, "Cash's primary action is inside the first 915 px").toBeLessThanOrEqual(915);
  expect(cashBox.y + cashBox.height, "and above the tab bar").toBeLessThanOrEqual(tab.y);
  expect((await topOf(page, "cash-figures"))!.top, "the four facts come after the plan").toBeGreaterThan(plan.top);
  const chart = (await topOf(page, "cash-chart"))!;
  expect((await topOf(page, "cash-answer"))!.top).toBeLessThan(plan.top);
  expect(plan.top).toBeLessThan(options.top);
  expect(options.top, "the options list starts inside the first two screens").toBeLessThan(2 * 915);
  expect(options.top).toBeLessThan(chart.top);
  measured.cash = { answer: await topOf(page, "cash-answer"), plan, primary: { top: Math.round(cashBox.y), bottom: Math.round(cashBox.y + cashBox.height) }, facts: await topOf(page, "cash-figures"), options, chart, pageHeight: await page.evaluate(() => document.documentElement.scrollHeight) };

  // The three numbers the review asks for: the bottom edge of each page's primary action (all inside 915).
  measured.primaryBottomEdges = { home: (measured.home as { primary: { bottom: number } }).primary.bottom, deals: (measured.deals as { send: { bottom: number } }).send.bottom, cash: (measured.cash as { primary: { bottom: number } }).primary.bottom };

  if (process.env.PHONE_MEASURE_OUT) {
    const { writeFileSync } = await import("node:fs");
    writeFileSync(process.env.PHONE_MEASURE_OUT, JSON.stringify({ viewport: "412x915", ...measured }, null, 1) + "\n");
  }
});

test("on a desktop the Deals workspace keeps the server's order and the inbox row stays above it", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "phone", "a desktop check");
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-recommendation")).toHaveText("Counter recommended");
  const inbox = (await topOf(page, "inbox-collapsed"))!;
  const selected = (await topOf(page, "deal-selected"))!;
  expect(inbox.top).toBeLessThan(selected.top);
});
