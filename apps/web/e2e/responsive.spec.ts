import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

/** Runs on a phone viewport (and desktop): no page may scroll sideways, the story bar stays reachable in Demo mode, and the Business home puts the answer first. */

const ENGINE_ROUTES = ["/demo", "/chat", "/mandate", "/inbox", "/trajectory", "/funding", "/verdict", "/capex", "/ledger", "/approvals", "/security", "/evidence"];
const BUSINESS_ROUTES = ["/", "/deals", "/cash", "/receivables", "/approvals", "/activity", "/limits"];

async function overflowX(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

test("no page overflows horizontally after the demo has run", async ({ page }) => {
  await page.goto("/mandate");
  for (let i = 0; i < 15; i++) {
    const button = page.getByTestId("demo-next");
    await expect(button).toBeEnabled();
    await button.click();
    // Wait for the step to finish: a click while the stepper is busy is ignored.
    await expect(page.getByRole("region", { name: "Guided demo" }).locator("[aria-live=polite]")).toContainText(`${i + 1}/15`);
  }
  await expect(page).toHaveURL(/\/evidence/);
  for (const route of ENGINE_ROUTES) {
    await page.goto(route);
    await expect(page.locator("h1")).toBeVisible();
    // Tables scroll inside their own region; the page itself must not.
    expect(await overflowX(page), `${route} overflows horizontally`).toBeLessThanOrEqual(1);
  }
  // The Business shell, with the deal of the demo on the books.
  await page.getByLabel("Business").check();
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
  const panel = page.getByRole("dialog", { name: "Chat with the agent" });
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
