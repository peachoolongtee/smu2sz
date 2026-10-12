import type { Page, Route } from "@playwright/test";
import { expect, test } from "./fixtures";
import { resetBooks } from "./helpers";

/**
 * Freshness and recovery (wayfinder #65 Wave 7, F21 and F23), live mode only: the web build used here gives every request 6 s
 * (NEXT_PUBLIC_REQUEST_TIMEOUT_MS in playwright.config.ts; 20 s and 60 s in production), and a Playwright route holds a request past it.
 * A read that hangs says "This is taking longer than usual…" with a Retry that reads it again. A WRITE that hangs may already have landed:
 * its Retry reads the state first and never sends the write again. A `partial` home says which supporting facts were not read. Each of
 * these is the server's real answer with one field added or one delay, never a made-up page.
 */

const API_PORT = String(process.env.E2E_API_PORT ?? 8000);
const SLOW_MS = 8_000;

const isApi = (path: RegExp) => (url: URL) => url.port === API_PORT && path.test(url.pathname);

/** Holds a request until the browser has given up on it, then lets the page's own abort stand. */
async function hold(route: Route) {
  await new Promise((r) => setTimeout(r, SLOW_MS));
  await route.abort().catch(() => undefined);
}

/** The real answer with `patch` merged into its JSON. */
async function withFields(route: Route, patch: Record<string, unknown>) {
  const response = await route.fetch();
  await route.fulfill({ response, json: { ...(await response.json()), ...patch } });
}

test.beforeEach(async ({ request }) => {
  await resetBooks(request);
});

test("a read that hangs shows the slow state, and Retry reads it again", async ({ page }) => {
  let held = 0;
  await page.route(isApi(/^\/home$/), async (route) => {
    if (held++ === 0) return hold(route);
    return route.continue();
  });
  await page.goto("/");
  const slow = page.getByTestId("slow-notice");
  await expect(slow).toContainText("This is taking longer than usual…", { timeout: 15_000 });
  await expect(slow).toHaveAttribute("role", "status");
  await slow.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByTestId("home-status")).toBeVisible();
  await expect(page.getByTestId("slow-notice")).toHaveCount(0);
});

test("a write that hangs may have landed: Retry reads the state first and sends nothing again", async ({ page }) => {
  await page.goto("/");
  const alertId = await page.getByTestId("home-next-action").getAttribute("data-alert");
  let acts = 0;
  await page.route(isApi(/^\/alerts\/[^/]+\/act$/), async (route) => {
    acts++;
    // The books are written, but the answer is held past the browser's patience: the owner cannot tell.
    await route.fetch();
    await hold(route);
  });
  await page.getByTestId(`fix-open-${alertId}`).click();
  await page.getByTestId(`fix-${alertId}`).click();
  const slow = page.getByTestId("slow-notice");
  await expect(slow).toContainText("The request may already have gone through", { timeout: 15_000 });
  await slow.getByRole("button", { name: "Retry" }).click();
  // The state was read again: the plan that ran is no longer offered to run, and the act was sent exactly once.
  await expect(page.getByTestId("slow-checked")).toContainText("Checked the current state");
  await expect(page.getByTestId(`fix-open-${alertId}`)).toHaveCount(0);
  expect(acts).toBe(1);
});

test("a partial home says which supporting facts were not read, with Retry; the freshness word sits beside the conclusion", async ({ page }) => {
  let partial = true;
  await page.route(isApi(/^\/home$/), (route) => (partial ? withFields(route, { partial: { missing: ["Buyer names", "Collections ranking"] } }) : route.continue()));
  await page.goto("/");
  await expect(page.getByTestId("home-read-when")).toHaveText(/^Read /);
  const warn = page.getByTestId("partial-read");
  await expect(warn).toContainText("Some supporting facts could not be read: Buyer names, Collections ranking.");
  await expect(warn).toHaveAttribute("role", "alert");
  partial = false;
  await warn.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByTestId("partial-read")).toHaveCount(0);
  await expect(page.getByTestId("home-status")).toBeVisible();
});

test("Cash, Receivables and Approvals carry the same freshness and partial lines", async ({ page }) => {
  await page.route(isApi(/^\/home$/), (route) => withFields(route, { partial: { missing: ["Buyer names"] } }));
  await page.route(isApi(/^\/approvals\/queue$/), (route) => withFields(route, { last_read_when: "today" }));
  await page.route(isApi(/^\/receivables$/), (route) => withFields(route, { partial: { missing: ["Buyer names"] } }));
  for (const [path, read] of [["/cash", "cash-read-when"], ["/receivables", "recv3-read-when"]] as const) {
    await page.goto(path);
    await expect(page.getByTestId(read)).toContainText("read today", { ignoreCase: true });
    await expect(page.getByTestId("partial-read")).toContainText("Buyer names");
  }
  await page.goto("/approvals");
  await expect(page.getByTestId("appr-read-when")).toHaveText("Read today");
});

test("a model reply that hangs says so, clears busy and Retry asks again with the same request", async ({ page }) => {
  const seen: string[] = [];
  let held = 0;
  await page.route(isApi(/^\/nl$/), async (route) => {
    seen.push((route.request().postDataJSON() as { request_id: string }).request_id);
    if (held++ === 0) return hold(route);
    return route.continue();
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Ask FLOW" }).first().click();
  const box = page.getByRole("textbox", { name: "Message" });
  await box.fill("What should I do first?");
  await box.press("Enter");
  await expect(page.getByText("This reply is taking longer than usual…")).toBeVisible({ timeout: 15_000 });
  await expect(box).toBeEnabled();
  await page.getByRole("button", { name: "Retry" }).click();
  await expect.poll(() => seen.length).toBe(2);
  expect(seen[1]).toBe(seen[0]);
});

async function strategyOnly(page: Page) {
  test.skip(process.env.E2E_STRATEGY !== "1", "the price curve is a strategy surface (E2E_STRATEGY=1)");
  void page;
}

test("a price curve that cannot be read is an error with Retry, not a quiet page", async ({ page }) => {
  await strategyOnly(page);
  let fail = true;
  await page.route(isApi(/^\/cash\/price-curve$/), (route) => (fail ? route.fulfill({ status: 500, json: { detail: "boom" }, headers: { "access-control-allow-origin": "*" } }) : route.continue()));
  await page.goto("/cash");
  const failed = page.getByTestId("cash-curve-failed");
  await expect(failed).toContainText("What earlier cash is worth could not be read.");
  fail = false;
  await failed.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByTestId("cash-curve-failed")).toHaveCount(0);
  await expect(page.getByTestId("cash-price-sentence")).toBeVisible();
});
