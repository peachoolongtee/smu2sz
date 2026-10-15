import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { openCompare, openStoryFold, STORY_STEPS, verdictHeading, walkStory, openOperatorTools } from "./helpers";

/** Runs on a phone viewport (and desktop): no page may scroll sideways, the story bar stays reachable in Demo mode, and the Business home puts the answer first. */

const ENGINE_ROUTES = ["/demo", "/chat", "/mandate", "/inbox", "/documents", "/trajectory", "/funding", "/verdict", "/capex", "/ledger", "/approvals", "/security", "/evidence"];
const BUSINESS_ROUTES = ["/", "/deals", "/documents", "/cash", "/receivables", "/approvals", "/activity", "/limits", "/customers/BUYER-1", "/customers/BUYER-1/inputs"];

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

test("Business navigation: the sections and the two doors (Sandbox, Capex) in the rail on a desktop, the six sections as tabs on a phone, the mode switch and Ask FLOW always visible", async ({ page }) => {
  await page.goto("/");
  const phone = (page.viewportSize()?.width ?? 1440) < 1024;
  // The rail holds the sections and the doors to the sandbox and the old capex screen; a phone's bar keeps the six sections (the doors are reached from Cash there).
  const names = ["Home", "Deals", "Attach deals", "Cash & funding", "Sandbox", "Capex", "Receivables", "Activity"];
  const phoneNames = ["Home", "Deals", "Attach deals", "Cash & funding", "Receivables", "Activity"];
  const bar = page.getByTestId(phone ? "tab-bar" : "nav-pills");
  await expect(bar).toBeVisible();
  await expect(page.getByTestId(phone ? "nav-pills" : "tab-bar")).toBeHidden();
  await expect(bar.getByRole("link")).toHaveText(phone ? ["Home", "Deals", "Attach", "Cash", "Receivables", "Activity"] : names);
  for (const n of phone ? phoneNames : names) await expect(bar.getByRole("link", { name: n, exact: true })).toBeVisible();
  await expect(bar.locator('[aria-current="page"]')).toHaveText(phone ? "Home" : "Home");
  // Buy equipment and What-if are doors from Cash & funding, not sections; no hamburger in Business mode.
  await expect(page.getByRole("button", { name: "Open navigation" })).toHaveCount(0);
  await expect(page.getByRole("radio", { name: "Business" })).toBeAttached();
  await expect(page.getByTestId("chat-open")).toHaveAttribute("aria-label", "Ask FLOW");
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
    // The h1 is there before the page's data is: wait for the reads to settle, then scroll and measure until the measure holds (content that arrives late grows the page under the scroll).
    await page.waitForLoadState("networkidle");
    const measure = () =>
      page.evaluate(() => {
      window.scrollTo(0, document.documentElement.scrollHeight);
      const chat = document.querySelector('[data-testid="chat-open"]')!.getBoundingClientRect();
      const chatInHeader = Boolean(document.querySelector('[data-testid="chat-open"]')!.closest("header"));
      const bar = document.querySelector('[data-testid="tab-bar"]');
      const barTop = bar && getComputedStyle(bar).display !== "none" ? bar.getBoundingClientRect().top : innerHeight;
      // Every control in main, at the end of the page, sits above the bar and outside the Ask FLOW box.
      // A control inside a fold that is closed is not on screen (its box is clipped, not removed): the fold's own summary is.
      const folded = (el: Element) => Boolean((el.tagName === "SUMMARY" ? el.parentElement?.parentElement : el)?.closest("details:not([open])"));
      return Array.from(document.querySelectorAll("main a[href], main button, main summary, main input")).filter((el) => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0 || folded(el)) return false;
        // Ask FLOW sits in the sticky header on a desktop (content scrolls under the header, which is not the pill covering it); on a phone it is a cell of the bar, where it must not cover a control.
        const hitsChat = !chatInHeader && r.left < chat.right && r.right > chat.left && r.top < chat.bottom && r.bottom > chat.top;
        return hitsChat || r.bottom > barTop;
      }).length;
    });
    await expect.poll(measure, { message: `${route}: controls under the bar or Ask FLOW at the end of the page`, timeout: 8000 }).toBe(0);
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
      // On Receivables the links are checked too (every customer name is a link that carries its own 44 px hit area).
      const links = location.pathname === "/receivables" ? ", main a" : "";
      return Array.from(document.querySelectorAll(`header a, header button, header summary, header label, main button, main summary, nav[data-testid=tab-bar] a${links}`))
        .filter((el) => (el as HTMLElement).offsetParent !== null && !(el.closest("details:not([open])") && el.tagName !== "SUMMARY"))
        .filter((el) => {
          // Measured where a finger would meet it: scrolled to the middle of the window, clear of the fixed tab bar.
          el.scrollIntoView({ block: "center" });
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

test("the document review fits the viewport", async ({ page }) => {
  await page.goto("/documents");
  await page.getByTestId("fixture-read-FHR_SUPPLY_AGREEMENT").click();
  await expect(page.getByTestId("doc-review")).toHaveAttribute("data-status", "PROPOSED");
  expect(await overflowX(page), "the review screen overflows horizontally").toBeLessThanOrEqual(1);
  await page.getByTestId("doc-confirm").click();
  await expect(page.getByTestId("doc-review")).toHaveAttribute("data-status", "CONFIRMED");
  expect(await overflowX(page), "the confirmed review overflows horizontally").toBeLessThanOrEqual(1);
});

test("the story's strip and the app's navigation are reachable on an engine view; the engine views open from the Demo's Operator tools", async ({ page }) => {
  await page.goto("/mandate");
  await expect(page.getByTestId("demo-next")).toBeInViewport();
  await expect(page.getByTestId(page.viewportSize()!.width >= 1024 ? "nav-pills" : "tab-bar")).toBeVisible();
  await page.goto("/demo");
  await openOperatorTools(page);
  await page.getByTestId("demo-tools-engine").getByRole("link", { name: "Debt Desk" }).click();
  await expect(page).toHaveURL(/\/funding/);
  await expect(page.getByTestId("demo-next")).toBeInViewport();
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
  // The heading is the buyer's ask from the first read, so the check is done when the recommendation is there.
  await page.getByTestId("queue-recommends").waitFor();
  await expect(verdictHeading(page)).toContainText(/Foshan asks for early settlement|Don't accept as asked|Counter instead of accepting as asked/);
  // The buyer's messages are the deal's Messages tab: no inbox card is under the queue while a deal is selected.
  await expect(page.getByTestId("deals-inbox")).toHaveCount(0);
  // The page's order on the Overview: the verdict, what they ask, FLOW's reply, the terms by scope.
  // (The ask is one line when the deals read has the open offer, else the buyer's own message.)
  const overview = ["queue-heading", "queue-recommends", "deal-choices"];
  await page.getByTestId("deal-choices").waitFor();
  const orderTops = await page.evaluate((list) => list.map((id) => (document.querySelector(`[data-testid="${id}"]`)?.getBoundingClientRect().top ?? -1e9) + scrollY), overview);
  expect(orderTops.every((y) => y >= 0)).toBe(true);
  expect(orderTops).toEqual([...orderTops].sort((a, b) => a - b));
  await openCompare(page);
  expect(await overflowX(page), "/deals overflows horizontally").toBeLessThanOrEqual(1);
  await page.getByTestId("deal-tab-cash").click();
  await expect(page.getByTestId("deal-chart")).toBeVisible();
  expect(await overflowX(page), "/deals cash impact overflows horizontally").toBeLessThanOrEqual(1);
  await page.goto("/cash");
  await expect(page.getByTestId("cash-options-list")).toBeVisible();
  expect(await overflowX(page), "/cash overflows horizontally").toBeLessThanOrEqual(1);
  const narrow = (page.viewportSize()?.width ?? 1440) < 1024;
  if (narrow) {
    for (const [route, ready] of [["/deals", "deals-inbox"], ["/cash", "cash-options-list"]] as const) {
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
  // The Home's card opens the plan on Cash & funding ("Check funding plan"); the plan's own two presses are on Cash.
  const run = page.getByTestId("home-check-plan");
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
  // The heading is the buyer's ask from the first read, so the check is done when the recommendation is there.
  await page.getByTestId("queue-recommends").waitFor();
  await expect(verdictHeading(page)).toContainText(/Foshan asks for early settlement|Don't accept as asked|Counter instead of accepting as asked/);
  const rec = (await topOf(page, "queue-heading"))!;
  const send = await page.getByTestId("queue-review-open").boundingBox();
  const asks = (await topOf(page, "queue-heading"))!;
  // The buyer's messages are the deal's Messages tab: no inbox row is under the queue while a deal is selected.
  await expect(page.getByTestId("deals-inbox")).toHaveCount(0);
  await expect(page.getByTestId("deal-steps")).toHaveCount(0);
  await expect(page.getByTestId("deal-state-chip")).toContainText("Counter ready");
  expect(rec.top, "the recommendation card starts in the first screen").toBeLessThan(915);
  expect(send, "the review button is on the page").not.toBeNull();
  expect(send!.y + send!.height, "the review button is inside the first 915 px").toBeLessThanOrEqual(915);
  expect(send!.y + send!.height, "and above the tab bar").toBeLessThanOrEqual(tab.y);
  expect(asks.top, "the ask comes before the reply card (the board's order)").toBeLessThan((await topOf(page, "queue-recommends"))!.top);
  measured.deals = { recommendation: rec, send: { top: Math.round(send!.y), bottom: Math.round(send!.y + send!.height) }, asks, pageHeight: await page.evaluate(() => document.documentElement.scrollHeight) };

  // Cash: the answer, the plan, the picture, then the comparison; its options list starts inside the first three screens.
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
  // The picture now leads the page's content (pages A1), so the options sit under it, inside the first three screens.
  expect(options.top, "the options list starts inside the first three screens").toBeLessThan(3 * 915);
  expect(chart.top).toBeLessThan(options.top);
  measured.cash = { answer: await topOf(page, "cash-answer"), plan, primary: { top: Math.round(cashBox.y), bottom: Math.round(cashBox.y + cashBox.height) }, facts: await topOf(page, "cash-figures"), options, chart, pageHeight: await page.evaluate(() => document.documentElement.scrollHeight) };

  // The three numbers the review asks for: the bottom edge of each page's primary action (all inside 915).
  measured.primaryBottomEdges = { home: (measured.home as { primary: { bottom: number } }).primary.bottom, deals: (measured.deals as { send: { bottom: number } }).send.bottom, cash: (measured.cash as { primary: { bottom: number } }).primary.bottom };

  if (process.env.PHONE_MEASURE_OUT) {
    const { writeFileSync } = await import("node:fs");
    writeFileSync(process.env.PHONE_MEASURE_OUT, JSON.stringify({ viewport: "412x915", ...measured }, null, 1) + "\n");
  }
});

test("on a desktop the deal is its own full-width page: no queue beside it, All deals at its top, and the list comes back in the same place", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "phone", "a desktop check");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await page.getByTestId("queue-recommends").waitFor();
  await expect(verdictHeading(page)).toContainText(/Foshan asks for early settlement|Don't accept as asked|Counter instead of accepting as asked/);
  // The list is not beside the deal (it is kept hidden), and the deal's page takes the content's width.
  await expect(page.getByTestId("deals-queue")).toBeHidden();
  const top = (await page.getByTestId("deal-topbar").boundingBox())!;
  const pane = (await page.getByTestId("deal-pane").boundingBox())!;
  expect(pane.width, "the deal takes the content's width, not a side pane's").toBeGreaterThan(900);
  expect(Math.abs(pane.x - top.x), "under its top line, left-aligned with it").toBeLessThan(2);
  expect(top.y, "All deals is above the deal").toBeLessThan(pane.y);
  await page.getByTestId("deal-back-all").click();
  await expect(page.getByTestId("deals-queue")).toBeVisible();
  await expect(page.getByTestId("deal-pane")).toHaveCount(0);
});

/**
 * Wave 8 part C: on a phone every primary ends above y 840 at 412 x 915 (the tab bar starts at 858, and a primary that ends against it reads as covered),
 * on day 0 and on day 34 (the cure waits for the owner), including the approval's own buttons. On a 1366 x 768 laptop Home's primary ends in the first screen.
 */
async function toDay34(page: Page) {
  await page.goto("/demo");
  await openStoryFold(page, "story-today");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
}

async function bottomOf(page: Page, testId: string): Promise<number> {
  const box = (await page.getByTestId(testId).first().boundingBox())!;
  return Math.round(box.y + box.height);
}

test("phone: every primary ends above y 840, on day 0 and on day 34 (Home, Cash); the approval's button follows its terms", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "phone", "the phone's first screen");
  await page.setViewportSize({ width: 412, height: 915 });
  await page.goto("/cash");
  await expect(page.getByTestId("home-next-action")).toBeVisible();
  const alert0 = (await page.getByTestId("home-next-action").getAttribute("data-alert"))!;
  expect(await bottomOf(page, `fix-open-${alert0}`), "Cash day 0").toBeLessThanOrEqual(840);
  await toDay34(page);
  await page.goto("/");
  const alert34 = (await page.getByTestId("home-next-action").getAttribute("data-alert"))!;
  expect(await bottomOf(page, "home-check-plan"), "Home day 34").toBeLessThanOrEqual(840);
  await page.goto("/cash");
  await expect(page.getByTestId(`fix-open-${alert34}`)).toBeVisible();
  expect(await bottomOf(page, `fix-open-${alert34}`), "Cash day 34").toBeLessThanOrEqual(840);
  await page.getByTestId(`fix-open-${alert34}`).click();
  await page.getByTestId(`fix-${alert34}`).click();
  await expect(page.getByTestId(`alert-waiting-${alert34}`)).toBeVisible();
  await page.goto("/approvals");
  const approve = page.getByRole("button", { name: /^Authorize/ }).first();
  await expect(approve).toBeVisible();
  // The approval's terms come before its one button at every width (ticket #128, audit UX03), so on a phone the button is no longer in the first screen: it is after the terms,
  // and still reachable (not hidden, not behind the tab bar once scrolled to).
  await approve.scrollIntoViewIfNeeded();
  await expect(approve).toBeInViewport();
  const terms = page.getByTestId("approval-facts-APR-000001");
  if (await terms.count()) {
    const [t, b] = [(await terms.boundingBox())!, (await approve.boundingBox())!];
    expect(t.y + t.height, "the facts end before the button begins").toBeLessThanOrEqual(b.y);
  }
});

test("a 1366 x 768 laptop: Home's primary ends in the first screen, under the plan bar's own 16 px of air", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "phone", "a laptop check");
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  const alertId = (await page.getByTestId("home-next-action").getAttribute("data-alert"))!;
  expect(await bottomOf(page, "home-check-plan")).toBeLessThanOrEqual(700);
  // The three cards are one row in the page's flow (not sticky) and the whole row, today's cash among them, is inside the first screen.
  await expect(page.getByTestId("home-kpi-cash-value")).toBeVisible();
  for (const id of ["hv2-cash-card", "hv2-action", "hv2-outlook-card"]) {
    const box = (await page.getByTestId(id).boundingBox())!;
    expect(box.y + box.height, id).toBeLessThanOrEqual(768);
  }
});

test("at tablet width (820) the open invoices are one card each, so no column is clipped", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "phone", "the phone has its own check");
  await page.setViewportSize({ width: 820, height: 1180 });
  await page.goto("/receivables");
  await expect(page.getByTestId("recv3-list")).toBeVisible();
  await expect(page.getByRole("columnheader").first()).toBeHidden();
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
});

test("phone: the Demo story keeps 'Operator tools' under one closed fold and the three books cards in the first screen, so the page is short", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "phone", "the folds are the phone's");
  await page.goto("/demo");
  await expect(page.getByTestId("demo-scenario-load-busy")).toBeInViewport();
  await expect(page.getByTestId("demo-alternate-fold")).toHaveCount(0);
  for (const id of ["demo-operator-tools"]) {
    const fold = page.getByTestId(id);
    await expect(fold).toBeAttached();
    await expect(fold).not.toHaveAttribute("open", "");
  }
  // The controls stay one tap away: a fold opens with the keyboard's Enter and shows what was behind it.
  await expect(page.getByTestId("more-run-capex")).toBeHidden();
  const tools = page.getByTestId("demo-operator-tools");
  await tools.locator("> summary").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("more-run-capex")).toBeVisible();
  await tools.locator("> summary").click();
  await expect(page.getByTestId("more-run-capex")).toBeHidden();
  await expect(page.getByTestId("home-day")).toBeAttached();
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  const view = page.viewportSize()?.height ?? 915;
  // Three one-line books, one current scene, six one-line scenes and one closed fold: the page is short.
  expect(height, `the story page is ${(height / view).toFixed(2)} screens`).toBeLessThanOrEqual(view * 3 + 16);
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
});
