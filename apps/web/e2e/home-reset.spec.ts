import type { APIRequestContext } from "@playwright/test";
import { DEMO_TOKEN, expect, test } from "./fixtures";
import type { HomeView, WorklistView } from "../lib/types";

/**
 * The Home on a long-running server (`pnpm demo:keep`), against the real API (the live project): the video recorder's findings of 17 Oct.
 * - Reset several times quickly: the Home reads at once (no skeleton left waiting on a warm-up), and Deals never lists a deal of the books a
 *   reset replaced (a new buyer message on the new books brought the log's counts back to the old ones, and the old answer with them).
 * - Day 77 of the golden story: the bank holds less than the minimum while the forecast closes every day above it (the money due today
 *   counts). The Home never says "You're covered!" or "All clear" then; it says what the figures say, in the server's words.
 * Run against an API started with DEMO_WARM_STRATEGY=1 (scripts/demo.mjs's environment) the first test also shows that the strategy warm-up
 * started by each reset never holds the Home up.
 */
const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
const OWNER = { "X-Owner-Token": DEMO_TOKEN };
const DEAL = /deal%3A(OFF-[0-9a-f]+)/g;
const FIRST = "We'll settle the ¥420k early at 1.2% if you extend our standard terms to 60 days going forward and give us 1% off next quarter.";
const SECOND = "We will pay the ¥420k invoice 10 days early for a 1% discount.";
const EX01 = { fixture_id: "EX01_PACKAGE" };

async function post(api: APIRequestContext, path: string, data: object = {}) {
  const res = await api.post(`${API}${path}`, { headers: OWNER, data });
  expect(res.ok(), `${path}: ${res.status()} ${await res.text()}`).toBeTruthy();
  return res.json();
}
async function get<T>(api: APIRequestContext, path: string): Promise<T> {
  const res = await api.get(`${API}${path}`, { headers: OWNER });
  expect(res.ok(), path).toBeTruthy();
  return res.json() as Promise<T>;
}
async function dealsOnWorklist(api: APIRequestContext): Promise<string[]> {
  const w = await get<WorklistView>(api, "/worklist?lang=en");
  return [...JSON.stringify([...w.needs_you, ...w.waiting]).matchAll(DEAL)].map((m) => m[1]);
}
const chat = (api: APIRequestContext, text: string) => post(api, "/nl", { actor: "COUNTERPARTY", counterparty_id: "BUYER-1", text, lang: "en" });

test("reset several times quickly: the Home reads at once and Deals never lists the replaced books' deal", async ({ page, request }) => {
  test.setTimeout(240_000);
  await post(request, "/demo/reset");
  await chat(request, FIRST);
  const [first] = await dealsOnWorklist(request);
  expect(first).toBeTruthy();
  await page.goto("/deals");
  await expect(page.getByTestId("queue-select").first()).toBeVisible();
  // The owner rehearses: the alternate books and back, quickly, each reset starting the strategy warm-up of its books.
  for (const scenario of ["busy", "golden_sme", "busy", "golden_sme"]) await post(request, `/demo/reset?scenario=${scenario}`);
  const started = Date.now();
  await page.goto("/");
  await expect(page.getByTestId("home-v2")).toBeVisible();
  await expect(page.getByTestId("hv2-outlook-card")).toBeVisible();
  const home = await get<HomeView>(request, "/home?lang=en");
  await expect(page.getByTestId("home-action-title")).toHaveText(home.home_v2!.action.title);
  expect(Date.now() - started, "the Home after the resets").toBeLessThan(15_000);
  // A different buyer message on the new books: the same counts in the log, other books.
  await chat(request, SECOND);
  const now = await dealsOnWorklist(request);
  expect(now).toHaveLength(1);
  expect(now).not.toContain(first);
  await page.goto("/deals");
  await page.getByTestId("queue-select").first().click();
  await expect(page.getByTestId("deal-pane")).toHaveAttribute("data-decision", `deal:${now[0]}`);
  await expect(page.getByTestId("deal-ask-which")).toHaveCount(0);
});

for (const lang of ["en", "zh"] as const) {
  test(`day 77 (${lang}): cash under the minimum today is never "covered", whatever the forecast`, async ({ page, request }) => {
    test.setTimeout(180_000);
    await post(request, "/demo/reset");
    const { offer } = await post(request, "/offers", EX01);
    const v = await post(request, `/offers/${offer.offer_id}/evaluate`, EX01);
    await post(request, `/negotiate/${offer.offer_id}`, { buyer_profile: "cooperative", verdict_id: v.id, counter_id: v.counters[0].id, state_version: v.state_version });
    await post(request, "/clock/advance", { to_day: 2 });
    await post(request, "/demo/bank-receipt");
    await post(request, "/clock/advance", { to_day: 34 });
    const h34 = await get<HomeView>(request, "/home?lang=en");
    const n = h34.next_action!;
    await post(request, `/alerts/${n.alert_id}/act`, { state_version: h34.state_version, suggestions: n.suggestions });
    const queue = await get<{ approvals: { id: string; status: string }[] }>(request, "/approvals/queue");
    // the owner's own decision on the cure (the story never presses it; this test is the owner)
    for (const a of queue.approvals.filter((r) => r.status === "PENDING")) await post(request, `/approvals/${a.id}`, { decision: "APPROVE" });
    for (const day of [38, 48, 77]) await post(request, "/clock/advance", { to_day: day });
    const h = await get<HomeView>(request, `/home?lang=${lang}`);
    // the take's state: under the minimum in the bank, no unsafe day in the forecast
    expect(h.cash.cash_fen).toBeLessThan(h.cash.floor_fen);
    expect(h.cash.first_breach_day).toBeNull();
    expect(h.cash.covered).toBe(false);
    expect(h.home_v2!.action.covered).toBe(false);
    await page.addInitScript((l) => localStorage.setItem("tl-lang", JSON.stringify({ lang: l })), lang);
    await page.goto("/");
    await expect(page.getByTestId("home-v2")).toBeVisible();
    await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "action");
    await expect(page.locator('[data-covered="true"]')).toHaveCount(0);
    await expect(page.getByTestId("hv2-covered-pill")).toHaveCount(0);
    await expect(page.getByTestId("home-action-title")).toHaveText(h.home_v2!.action.title);
    await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", h.status);
    expect(h.status).not.toMatch(/^(SAFE|WATCH)$/);
    if (lang === "en") {
      expect(h.headline).toBe("Below reserve today.");
      await expect(page.getByTestId("home-v2")).not.toContainText("You're covered");
      await expect(page.getByTestId("home-v2")).not.toContainText("All clear");
    } else {
      await expect(page.getByTestId("home-v2")).not.toContainText("您的现金很安全");
      await expect(page.getByTestId("home-v2")).not.toContainText("一切正常");
    }
  });
}
