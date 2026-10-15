import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { filledBrand, STORY_STEPS, walkStory } from "./helpers";
import type { TrackerView } from "../lib/tracker";

/**
 * The deal tracker (map #148): /decisions/{id}/tracker, one agreed deal, what was expected at agreement against what has happened. Mock mode serves the
 * recordings of GET /decisions/{id}/tracker (mocks/tracker/<moment>.json, scripts/record-mocks.mjs --tracker) by the story the stepper walks; every
 * assertion compares the screen with the recorded read's own fields (never a figure typed here). Live mode walks the real API to the approval, with the
 * owner's own click, and compares the page with the API's own answer.
 */

type Moment = "offer" | "agreed" | "receipt" | "late" | "pending" | "approved" | "settled" | "ended";
const recorded = (m: Moment): { en: TrackerView; zh: TrackerView } => JSON.parse(readFileSync(join(__dirname, "..", "mocks", "tracker", `${m}.json`), "utf8"));
/** The demo story's steps (lib/demo.ts) after which each moment is on the books: agree 3, bank 5, time 6, queue 7, approve 8, settle 9. */
const AFTER: [Moment, number][] = [["agreed", 3], ["receipt", 5], ["late", 6], ["pending", 7], ["approved", 8], ["settled", 9]];
const trackerUrl = (id: string) => `/decisions/${encodeURIComponent(id)}/tracker`;
const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;

async function setLang(page: Page, lang: "en" | "zh") {
  await page.addInitScript((l) => localStorage.setItem("tl-lang", JSON.stringify({ lang: l })), lang);
}

/** The page against the read: every figure, word and state on screen is the read's own field. */
async function expectRead(page: Page, d: TrackerView): Promise<void> {
  await expect(page.getByTestId("tracker")).toBeVisible();
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.getByTestId("tracker-headline")).toHaveText(d.headline_text as string);
  await expect(page.getByTestId("tracker-state")).toContainText(d.state_word as string);
  const cost = d.cost!;
  await expect(page.getByTestId("tracker-expected-figure")).toHaveText(cost.expected.amount_display as string);
  await expect(page.getByTestId("tracker-actual-figure")).toHaveText(cost.actual.amount_display);
  await expect(page.getByTestId("tracker-actual")).toContainText(cost.actual.note_text as string);
  if ((cost.unmeasured_fen ?? 0) > 0) await expect(page.getByTestId("tracker-unmeasured-figure")).toHaveText(cost.unmeasured_display as string);
  else await expect(page.getByTestId("tracker-unmeasured")).toHaveCount(0);
  if (cost.to_come.amount_display) await expect(page.getByTestId("tracker-to-come-figure")).toHaveText(cost.to_come.amount_display);
  await expect(page.getByTestId("tracker-to-come")).toContainText(cost.to_come.note_text);
  // The actual figure's tone always has its note beside it: a tone is never the only channel.
  expect((await page.getByTestId("tracker-actual").innerText()).trim().length).toBeGreaterThan(cost.actual.amount_display.length);
  // The agreement's own components (the terms, the funding planned at agreement) are both lines of the table; the eyebrow says when it was agreed.
  expect(cost.lines.filter((l) => !l.relation || l.relation === "none").map((l) => l.key)).toEqual(["terms", "planned_funding"]);
  await expect(page.getByTestId("tracker-eyebrow")).toContainText(d.agreed_text as string);
  for (const l of cost.lines) {
    // A related line the server does not count is shown apart, outside the deal's cost, with its own figure and why it is not counted.
    if (l.relation && l.relation !== "none" && !l.counted && l.counted_note_text) {
      const out = page.getByTestId(`tracker-outside-${l.key}`);
      await expect(out).toContainText(l.figure_display as string);
      await expect(out).toContainText(l.counted_note_text);
      await expect(page.getByTestId(`tracker-line-${l.key}`)).toHaveCount(0);
      continue;
    }
    const row = page.getByTestId(`tracker-line-${l.key}`);
    await expect(row).toHaveAttribute("data-certainty", l.certainty);
    await expect(row).toContainText(l.certainty_text);
    if (l.expected_display) await expect(row).toContainText(l.expected_display);
    // So far: the figure, or the server's note when there is none (never a dash or a zero in its place).
    if (l.actual_display) await expect(row).toContainText(l.actual_display);
    else await expect(page.getByTestId(`tracker-line-${l.key}-actual`)).toHaveText(l.actual_note_text as string);
  }
  if (!cost.lines.some((l) => l.relation && l.relation !== "none" && !l.counted && l.counted_note_text)) await expect(page.getByTestId("tracker-outside")).toHaveCount(0);
  await expect(page.getByTestId("tracker-method")).toHaveText(cost.method_text);
  for (const s of d.stages) {
    const stage = page.getByTestId(`tracker-stage-${s.key}`);
    await expect(stage).toHaveAttribute("data-state", s.state);
    await expect(stage).toContainText(s.state_text);
  }
  for (const [i, p] of d.promises.entries()) {
    const row = page.getByTestId(`tracker-promise-${i}`);
    await expect(row).toHaveAttribute("data-state", p.state);
    await expect(row).toHaveAttribute("data-party", p.party);
    await expect(row).toContainText(p.title_text);
    await expect(row).toContainText(p.state_word);
  }
  if (d.buyer!.text) await expect(page.getByTestId("tracker-buyer")).toContainText(d.buyer!.text);
  if (d.promise_counts) await expect(page.getByTestId("tracker-buyer")).toContainText(d.promise_counts.text);
  for (const [i, p] of d.promises.entries()) if (p.state === "paid_late") await expect(page.getByTestId(`tracker-promise-${i}`)).toContainText(p.state_word);
  // The back link is the page's first control; the close-out, when there is one, is its own card after the header (never above the back link).
  const back = await page.getByTestId("tracker-back").boundingBox();
  const head = await page.getByTestId("tracker-headline").boundingBox();
  expect(back!.y).toBeLessThan(head!.y);
  if (d.closeout_text) {
    await expect(page.getByTestId("tracker-closeout")).toHaveText(d.closeout_text);
    const closeout = await page.getByTestId("tracker-closeout").boundingBox();
    expect(closeout!.y).toBeGreaterThan(head!.y);
    await expect(page.getByTestId("tracker-headline")).toContainText(/clos/i);
  } else {
    // A deal that is still live shows no close-out and its headline never says it closed.
    await expect(page.getByTestId("tracker-closeout")).toHaveCount(0);
    expect(d.headline_text).not.toMatch(/clos|已结束|已完结/i);
  }
  // One filled button at most: the next step when there is one, none when there is not.
  if (d.next) {
    await expect(page.getByTestId("tracker-next-action")).toHaveText(d.next.label);
    expect(await filledBrand(page)).toBe(1);
    // The page is in the `.flow-f` scope, so the one filled button is the ink colour, not the brand blue.
    expect(await page.getByTestId("tracker-next-action").evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(23, 29, 30)");
  } else {
    await expect(page.getByTestId("tracker-next-action")).toHaveCount(0);
    expect(await filledBrand(page)).toBe(0);
  }
  // A tone never without its word: every pill carries its server word.
  for (const pill of await page.locator("[data-state-tone]").all()) expect(((await pill.textContent()) ?? "").trim().length).toBeGreaterThan(0);
  // No ids, codes or raw enums on the page.
  const prose = await page.getByTestId("tracker").innerText();
  expect(prose).not.toMatch(/\b(RECORDED|QUOTED|ATTRIBUTED|in_force|OFF-|RCV-|ALERT-|deal:)/);
}

test.describe("mock", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(testInfo.project.name === "live", "mock-mode spec: the recordings of the tracker read (the live walk is below)");
  });

  test("each moment of the story shows the recorded read's own words and figures", async ({ page }) => {
    test.setTimeout(240_000);
    await page.goto("/demo");
    let walked = 0;
    for (const [moment, steps] of AFTER) {
      await walkStory(page, steps - walked, walked);
      walked = steps;
      const read = recorded(moment).en;
      await page.goto(trackerUrl(read.decision_id));
      await expectRead(page, read);
      // The track has at most one stage that is "now"; on the late day it is exactly one (collecting), with fulfilled still to come.
      await expect(page.locator('[data-testid^="tracker-stage-"][data-state="now"]')).toHaveCount(moment === "late" ? 1 : read.stages.filter((s) => s.state === "now").length);
      if (moment === "late") await expect(page.getByTestId("tracker-stage-fulfilled")).toHaveAttribute("data-state", "todo");
      await page.goto("/demo");
      if (walked < STORY_STEPS) await expect(page.getByTestId("demo-next")).toBeEnabled();
    }
  });

  test("once the rest of the invoice is paid the deal has ended: the close-out card after the header, and the Paid late promise with its word", async ({ page }) => {
    test.setTimeout(240_000);
    await page.goto("/demo");
    await walkStory(page, 9);
    await page.evaluate(() => sessionStorage.setItem("tl-mock-tracker-ended", "1"));
    const read = recorded("ended").en;
    expect(read.closeout_text).toBeTruthy();
    expect(read.promises.some((p) => p.state === "paid_late")).toBe(true);
    await page.goto(trackerUrl(read.decision_id));
    await expectRead(page, read);
    // Ended: all five stages are done and none is "now".
    expect(read.stages).toHaveLength(5);
    await expect(page.locator('[data-testid^="tracker-stage-"][data-state="done"]')).toHaveCount(5);
    await expect(page.locator('[data-testid^="tracker-stage-"][data-state="now"]')).toHaveCount(0);
    const late = read.promises.findIndex((p) => p.state === "paid_late");
    await expect(page.getByTestId(`tracker-promise-${late}`)).toContainText("Paid late");
  });

  test("a deal that is not agreed gets the server's words and a way back, never an error", async ({ page }) => {
    const read = recorded("offer").en;
    expect(read.available).toBe(false);
    await page.goto(trackerUrl(read.decision_id));
    await expect(page.getByTestId("tracker-unavailable")).toContainText(read.unavailable_text as string);
    await expect(page.locator("h1")).toHaveCount(1);
    // (Next's own route announcer is a role=alert outside the page's content; the page itself shows no error.)
    await expect(page.locator("main [role=alert]")).toHaveCount(0);
    expect(await filledBrand(page)).toBe(0);
    await page.getByTestId("tracker-unavailable").getByRole("link").click();
    // The server writes the record's address with the colon of the id as it is; either spelling is the record.
    await expect(page).toHaveURL(/\/decisions\/deal(:|%3A)[^/]+$/);
    // The record of a deal that is not agreed carries no link to the tracker.
    await expect(page.getByTestId("decision-tracker-link")).toHaveCount(0);
  });

  test("the decision record links to the tracker for an agreed deal, and the way back returns to the record", async ({ page }) => {
    await page.goto("/demo");
    await walkStory(page, 3);
    const read = recorded("agreed").en;
    await page.goto(`/decisions/${encodeURIComponent(read.decision_id)}`);
    const link = page.getByTestId("decision-tracker-link");
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL(/\/tracker/);
    await expect(page.getByTestId("tracker-headline")).toHaveText(read.headline_text as string);
    await page.getByTestId("tracker-back").click();
    await expect(page).toHaveURL(new RegExp(`/decisions/[^/]+$`));
    await expect(page.getByTestId("decision-tracker-link")).toBeVisible();
  });

  test("the late day in Chinese shows the zh read's own words and the same figures", async ({ page }) => {
    test.setTimeout(180_000);
    await page.goto("/demo");
    await walkStory(page, 6);
    const { en, zh } = recorded("late");
    await setLang(page, "zh");
    await page.goto(trackerUrl(zh.decision_id));
    await expectRead(page, zh);
    expect(zh.cost!.actual.amount_display).toBe(en.cost!.actual.amount_display);
  });

  test("on a phone the page is one column with no horizontal scroll, and it has no axe violations (after the approval)", async ({ page }) => {
    test.setTimeout(240_000);
    await page.goto("/demo");
    await walkStory(page, 8);
    const read = recorded("approved").en;
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(trackerUrl(read.decision_id));
    await expectRead(page, read);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(trackerUrl(read.decision_id));
    await expectRead(page, read);
    const result = await new AxeBuilder({ page }).include("main").analyze();
    expect(result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
  });
});

test.describe("live", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(testInfo.project.name !== "live", "live-mode spec: the walk through the real API");
  });

  test("after the owner's approval the page's figures are the API's own", async ({ page, request }) => {
    test.setTimeout(240_000);
    await request.post(`${API}/demo/reset`, { headers: { "X-Owner-Token": "demo-owner-token" } });
    await page.goto("/demo");
    // The eight steps of the story, the owner's own click on the approval included (walkStory presses it as the existing live specs do).
    await walkStory(page, 8);
    const headers = { "X-Owner-Token": "demo-owner-token" };
    const list = (await (await request.get(`${API}/decisions?family=DEAL&lang=en`, { headers })).json()) as { decisions: { id: string }[] };
    expect(list.decisions.length).toBeGreaterThan(0);
    const id = list.decisions[0].id;
    // The approval's effect lands a moment after the click: wait for the tracker's actual-cost line to carry it (the tone is neutral until then), then read.
    let read!: TrackerView;
    await expect
      .poll(async () => {
        read = (await (await request.get(`${API}/decisions/${encodeURIComponent(id)}/tracker?lang=en`, { headers })).json()) as TrackerView;
        return read.cost?.actual.tone;
      }, { timeout: 45_000 })
      .toBe("bad");
    expect(read.available).toBe(true);
    await page.goto(trackerUrl(id));
    await expectRead(page, read);
    expect(read.cost!.actual.tone).toBe("bad");
    expect((read.cost!.difference_fen ?? 0) > 0).toBe(true);
    // The record links here, and the link is the tracker's address.
    await page.goto(`/decisions/${encodeURIComponent(id)}`);
    await expect(page.getByTestId("decision-tracker-link")).toBeVisible();
    // Settled, then the rest of the invoice paid through the bank feed's own route: the deal has ended, and the close-out is the API's own words.
    await page.goto("/demo");
    await walkStory(page, 1, 8);
    const state = (await (await request.get(`${API}/state`, { headers })).json()) as { state: { receivables: { id: string; face_fen: number; settled_fen?: number }[] } };
    const rest = state.state.receivables.find((r) => r.id === "RCV-A")!;
    const mandate = (await (await request.get(`${API}/mandate`, { headers })).json()) as { mandate: { version: number } };
    const paid = await request.post(`${API}/operations`, {
      headers: { ...headers, "X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key" },
      data: { kind: "RECEIVE_PAYMENT", op_id: "e2e-rest", idempotency_key: "e2e-rest", mandate_version: mandate.mandate.version, requested_by: "SYSTEM", receivable_id: "RCV-A", amount_fen: rest.face_fen - (rest.settled_fen ?? 0), bank_reference: "E2E-REST" },
    });
    expect(paid.ok()).toBe(true);
    const ended = (await (await request.get(`${API}/decisions/${encodeURIComponent(id)}/tracker?lang=en`, { headers })).json()) as TrackerView;
    expect(ended.closeout_text).toBeTruthy();
    await page.goto(trackerUrl(id));
    await expectRead(page, ended);
  });
});
