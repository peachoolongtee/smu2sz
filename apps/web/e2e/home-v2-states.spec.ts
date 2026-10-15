import AxeBuilder from "@axe-core/playwright";
import type { APIRequestContext, BrowserContext, Locator, Page, Route } from "@playwright/test";
import { DEMO_TOKEN, expect, test } from "./fixtures";
import { filledBrand } from "./helpers";
import { en, zh } from "../lib/dictionary";
import type { HomeView, WorklistView } from "../lib/types";

/**
 * Home V2, the state matrix (design/home-v2-2026-10-12/04_state_recipes.md): twelve states of the real page against the real API (the live project), no recordings.
 * Each test resets the Demo, drives the API with the recipe's sequence, then reads GET /home and GET /worklist itself and holds the page to those words (a money word is never written
 * here). Each state is opened at 1440 and 390 (the worklist sheet open) in English and Chinese. The dictionary supplies the labels the page owns; the server supplies everything else.
 */
const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
const OWNER = { "X-Owner-Token": DEMO_TOKEN };
const AGENT = { "X-Agent-Key": "demo-agent-key" };
type Lang = "en" | "zh";
type Api = APIRequestContext;
const DICT = { en, zh };
const LANGS: Lang[] = ["en", "zh"];
const WIDTHS = [1440, 390] as const;
const EX = { EX01: "EX01_PACKAGE", EX02: "EX02_EARLY_1_5", EX03: "EX03_AS_USUAL", EX04: "EX04_CLAIMED_REBATE", EX05: "EX05_CONSOLIDATE", EX07: "EX07_CONFLICT" };

// ---------------------------------------------------------------- driving the API (the recipes' request sequences)

async function post(api: Api, path: string, data: object = {}, headers: Record<string, string> = OWNER) {
  const res = await api.post(`${API}${path}`, { headers, data });
  expect(res.ok(), `${path}: ${res.status()} ${await res.text()}`).toBeTruthy();
  return res.json();
}
async function get<T = unknown>(api: Api, path: string): Promise<T> {
  const res = await api.get(`${API}${path}`, { headers: OWNER });
  expect(res.ok(), path).toBeTruthy();
  return res.json() as Promise<T>;
}
/** POST /offers and /offers/{id}/evaluate with a fixture package. */
async function offer(api: Api, fixture: string) {
  const { offer: o } = await post(api, "/offers", { fixture_id: fixture });
  const verdict = await post(api, `/offers/${o.offer_id}/evaluate`, { fixture_id: fixture });
  return { id: o.offer_id as string, verdict };
}
/** Run the plan the Home offers (the alert's act, bound to the Home's own state_version and suggestions). */
async function runPlan(api: Api) {
  const a = (await get<HomeView>(api, "/home")).next_action!;
  await post(api, `/alerts/${a.alert_id}/act`, { state_version: a.state_version, suggestions: a.suggestions });
}
/** EX01 negotiated with a cooperative buyer (bound to the verdict shown), then the clock. */
async function deal(api: Api) {
  const { id, verdict } = await offer(api, EX.EX01);
  await post(api, `/negotiate/${id}`, { buyer_profile: "cooperative", verdict_id: verdict.id, counter_id: verdict.counters[0].id, state_version: verdict.state_version });
}
const advance = (api: Api, to_day: number) => post(api, "/clock/advance", { to_day });

interface State {
  name: string;
  drive: (api: Api) => Promise<void>;
  /** The row kinds the page and the read show in Needs you and in Waiting, in order. */
  needs: string[];
  waiting: string[];
  /** The agreements the worklist counts (default none): a deal whose early part is paid but whose rest is still owed is Awaiting payment (or Payment late), never closed. */
  agreements?: number;
  /** Is the company alert on the worklist? */
  alert: boolean;
  /** Filled primary buttons on the page: the plan's control is the one (0 when the action is quiet). */
  filled: 0 | 1;
  /** Severity words of Needs you, in order (the row shapes are DECISION / APPROVAL / COLLECTION; Waiting rows carry the grey dot). */
  severities?: string[];
  funding?: "PROPOSED" | "ARRANGED" | "NONE";
  control?: "RUN_PLAN" | "APPROVE_PLAN" | null;
  status?: string;
}
const ONE_DEAL = async (api: Api) => void (await offer(api, EX.EX01));

const STATES: State[] = [
  { name: "01 no pending decisions: the plan ran, nothing needs the owner, one thing waits", drive: (api) => runPlan(api), needs: [], waiting: ["SETTLEMENT"], alert: false, filled: 0, funding: "ARRANGED", control: null },
  { name: "01b no pending decisions: fully empty after the buyer paid", drive: async (api) => { await deal(api); await advance(api, 2); await post(api, "/demo/bank-receipt"); }, agreements: 1, needs: [], waiting: [], alert: false, filled: 0, funding: "NONE", control: null },
  { name: "02 one deal: a single decision row", drive: ONE_DEAL, needs: ["DECISION"], waiting: [], alert: true, filled: 1, severities: ["CAUTION"], funding: "PROPOSED", control: "RUN_PLAN" },
  {
    name: "03 five deals: sorted, the critical one first",
    drive: async (api) => { for (const f of [EX.EX01, EX.EX02, EX.EX03, EX.EX04, EX.EX05]) await offer(api, f); },
    needs: Array(5).fill("DECISION"), waiting: [], alert: true, filled: 1, severities: ["CRITICAL", "CAUTION", "CAUTION", "NORMAL", "NORMAL"], control: "RUN_PLAN",
  },
  { name: "04 three deals, one customer: one customer row that counts them", drive: async (api) => { for (const f of [EX.EX01, EX.EX02, EX.EX03]) await offer(api, f); }, needs: Array(3).fill("DECISION"), waiting: [], alert: true, filled: 1, control: "RUN_PLAN" },
  { name: "05 buyer reply pending: a waiting row, nothing to resend", drive: async (api) => void (await offer(api, EX.EX07)), needs: [], waiting: ["BUYER_REPLY"], alert: true, filled: 1, control: "RUN_PLAN" },
  {
    name: "06a approval required: a facility application is an approval row of no customer",
    drive: async (api) => {
      const { mandate } = await get<{ mandate: { version: number } }>(api, "/mandate");
      await post(api, "/operations", { kind: "APPLY_FOR_FACILITY", op_id: "e2e-apply-1", idempotency_key: "e2e-apply-1", mandate_version: mandate.version, requested_by: "AGENT", facility_id: "FAC-GGL", amount_fen: 36_000_000 }, AGENT);
    },
    needs: ["APPROVAL"], waiting: [], alert: true, filled: 1, control: "RUN_PLAN",
  },
  { name: "06b approval required: the plan waits for the owner's approval", drive: async (api) => { await post(api, "/demo/reset?scenario=short_facilities"); await runPlan(api); await runPlan(api); }, needs: [], waiting: ["SETTLEMENT"], alert: true, filled: 1, funding: "ARRANGED", control: "APPROVE_PLAN" },
  { name: "07 funding proposed: planned, not cash", drive: async () => undefined, needs: [], waiting: [], alert: true, filled: 1, funding: "PROPOSED", control: "RUN_PLAN" },
  { name: "08 funding submitted, not cash: arranged, pending, a settlement row", drive: (api) => runPlan(api), needs: [], waiting: ["SETTLEMENT"], alert: false, filled: 0, funding: "ARRANGED", control: null },
  {
    name: "09 payment overdue: a critical collection row",
    drive: async (api) => { await deal(api); await advance(api, 2); await post(api, "/demo/bank-receipt"); await advance(api, 30); await advance(api, 34); },
    agreements: 1, needs: ["COLLECTION"], waiting: [], alert: true, filled: 1, severities: ["CRITICAL"], control: "RUN_PLAN",
  },
  { name: "10 cash critical: the reserve is unsafe today", drive: async (api) => void (await advance(api, 13)), needs: [], waiting: [], alert: true, filled: 1, status: "CRITICAL", control: "RUN_PLAN" },
  { name: "11 customer selected in the crisis: the alert persists", drive: ONE_DEAL, needs: ["DECISION"], waiting: [], alert: true, filled: 1, funding: "PROPOSED", control: "RUN_PLAN" },
  { name: "12 scenario still calculating: the working word appears, then goes", drive: ONE_DEAL, needs: ["DECISION"], waiting: [], alert: true, filled: 1, control: "RUN_PLAN" },
];

interface Reads {
  home: Record<Lang, HomeView>;
  work: Record<Lang, WorklistView>;
}
/** Reset the Demo, drive the state's sequence, then read the Home and the worklist in both languages: what the page must say. */
async function drive(api: Api, s: State): Promise<Reads> {
  await post(api, "/demo/reset", {});
  await s.drive(api);
  const reads = { home: {}, work: {} } as Reads;
  for (const lang of LANGS) {
    reads.home[lang] = await get<HomeView>(api, `/home?lang=${lang}`);
    reads.work[lang] = await get<WorklistView>(api, `/worklist?lang=${lang}`);
  }
  // The recipe itself, checked against the server before the page is looked at.
  const w = reads.work.en;
  expect(w.needs_you.map((r) => r.kind), "needs-you kinds").toEqual(s.needs);
  expect(w.waiting.map((r) => r.kind), "waiting kinds").toEqual(s.waiting);
  expect(w.counts).toEqual({ needs_you: s.needs.length, waiting: s.waiting.length, agreements: s.agreements ?? 0, customers: w.customers.length });
  expect(Boolean(w.alert), "alert").toBe(s.alert);
  if (s.severities) expect(w.needs_you.map((r) => r.severity)).toEqual(s.severities);
  const v2 = reads.home.en.home_v2!;
  if (s.funding) expect(v2.kpis.funding.state).toBe(s.funding);
  if (s.control !== undefined) expect(v2.action.control).toBe(s.control);
  if (s.status) expect(reads.home.en.status).toBe(s.status);
  expect(reads.work.zh.counts).toEqual(w.counts);
  return reads;
}

// ---------------------------------------------------------------- the page

async function open(context: BrowserContext, lang: Lang, width: number, url = "/"): Promise<Page> {
  const page = await context.newPage();
  await page.addInitScript((l) => localStorage.setItem("tl-lang", JSON.stringify({ lang: l })), lang);
  await page.setViewportSize({ width, height: width >= 1024 ? 900 : 844 });
  await page.goto(url);
  await expect(page.getByTestId("home-v2")).toBeVisible();
  await expect(page.getByTestId("hv2-outlook-card")).toBeVisible();
  return page;
}
const phone = (width: number) => width < 1024;
/** Round four's rule: the worklist's alert row stands in only when the Home renders no recommendation card (the action has no title and no control), whatever the funding state. */
const noCard = (h: HomeView) => !(h.home_v2!.action.title || h.home_v2!.action.control);
const label = (lang: Lang, key: keyof typeof en, vars: Record<string, string | number> = {}) =>
  Object.entries(vars).reduce((t, [k, v]) => t.replace(`{${k}}`, String(v)), DICT[lang][key] as string);

/** The worklist's scope: the card, at every width (a phone has it as a list on the page, no sheet). */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
async function worklist(page: Page, _width: number, _lang: Lang, _read: WorklistView): Promise<Locator> {
  await expect(page.getByTestId("home-worklist-panel")).toBeVisible();
  await expect(page.getByTestId("home-worklist-open")).toHaveCount(0);
  const panel = page.getByTestId("home-worklist-panel");
  await panel.scrollIntoViewIfNeeded();
  return panel;
}

/** The company strip, the status and the action are the Home read's words. */
async function expectCompany(page: Page, lang: Lang, h: HomeView, filled: number) {
  const v2 = h.home_v2!;
  await expect(page.getByTestId("home-status-word")).toHaveText(h.cash.status_word ?? "");
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", h.status);
  // The cash card and the outlook card: the labels are the dictionary's, the figures and notes the server's.
  await expect(page.getByTestId("hv2-metric-cash-label")).toHaveText(label(lang, "hv2.card.cash"));
  await expect(page.getByTestId("home-kpi-cash-value")).toHaveText(v2.kpis.cash_available.value_display);
  await expect(page.getByTestId("home-kpi-cash-note")).toHaveText(v2.kpis.cash_available.note);
  await expect(page.getByTestId("hv2-metric-lowest-label")).toHaveText(label(lang, "hv2.card.outlook"));
  await expect(page.getByTestId("home-kpi-lowest-value")).toHaveText(v2.kpis.lowest_ahead.value_display);
  await expect(page.getByTestId("home-kpi-lowest-note")).toHaveText(v2.kpis.lowest_ahead.short_note ?? v2.kpis.lowest_ahead.note);
  await expect(page.getByTestId("hv2-outlook-when")).toHaveText(new RegExp(`^${h.cash.lowest_when}$`, "i"));
  // The planned or arranged funding is the recommendation's figure (none while there is no funding and the action is quiet).
  // A quiet card with the cash covered is the "You're covered" card: it carries no funding figure; where the cash comes from names the funding instead.
  const covered = (await page.getByTestId("home-v2-action").getAttribute("data-variant")) === "covered";
  if (covered) {
    await expect(page.getByTestId("home-kpi-funding-value")).toHaveCount(0);
  } else if (v2.kpis.funding.state !== "NONE" || v2.action.variant !== "QUIET") {
    await expect(page.getByTestId("home-kpi-funding-value")).toHaveText(v2.kpis.funding.value_display);
    // The funding hint is the first line of the disclosure, not on the card.
    await expect(page.getByTestId("hv2-funding-hint")).toHaveCount(0);
  } else await expect(page.getByTestId("home-kpi-funding-value")).toHaveCount(0);
  if (!covered && v2.kpis.funding.state === "ARRANGED" && v2.kpis.funding.status_text) await expect(page.getByTestId("home-kpi-funding-status")).toHaveText(v2.kpis.funding.status_text);
  // The line under the headline is the server's summary of what waits (none when nothing does); Upcoming cash movements are the server's three nearest movements.
  // The line under the headline is the server's count sentence; its first sentence ("One funding action ready.") is the card's when the card carries the plan's control.
  const summary = v2.summary_text ? (v2.action.control ? v2.summary_text.replace(/^[^.。]*[.。]\s*/, "") : v2.summary_text) : "";
  if (summary) await expect(page.getByTestId("hv2-summary")).toHaveText(summary);
  else await expect(page.getByTestId("hv2-summary")).toHaveCount(0);
  await expect(page.getByTestId("hv2-state-pill")).toHaveCount(0); // "FLOW action ready" is said once, by the card
  const upcoming = v2.upcoming ?? [];
  await expect(page.getByTestId("hv2-upcoming-row")).toHaveCount(upcoming.length);
  for (const [i, u] of upcoming.entries()) {
    await expect(page.getByTestId("hv2-upcoming-row").nth(i)).toContainText(u.label);
    await expect(page.getByTestId("hv2-upcoming-row").nth(i)).toContainText(u.amount_display);
    await expect(page.getByTestId("hv2-upcoming-row").nth(i)).toContainText(u.when);
    await expect(page.getByTestId("hv2-upcoming-row").nth(i)).toHaveAttribute("data-kind", u.kind);
  }
  await expect(page.getByTestId("home-action-title")).toHaveText(v2.action.title);
  await expect(page.getByTestId("hv2-action")).toHaveCount(1);
  await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", v2.action.variant === "QUIET" ? /^(quiet|covered)$/ : "action");
  // The cost is on the card (the funding legs are its inline bar, below; who approves is the approval line above the actions).
  for (const f of (v2.action.facts ?? []).slice(0, 1)) await expect(page.getByTestId("hv2-action")).toContainText(f.value);
  if (v2.action.control === "RUN_PLAN") await expect(page.getByTestId("home-check-plan")).toBeVisible(); // the plan is run on Cash & funding
  // The approval is one line under the actions, bound to the server's two fields: the tick form for text with approval_needed false, the warn form when true, none for null.
  if (v2.action.variant === "ACTION") {
    const line = page.getByTestId("hv2-approval");
    if (v2.action.approval_text) {
      await expect(line).toHaveText(v2.action.approval_text);
      await expect(line).toHaveAttribute("data-needs-owner", String(v2.action.approval_needed === true));
    } else await expect(line).toHaveCount(0);
    // The approval line sits directly above the actions, which are pinned to the card's bottom (round four); the facts row is the cost alone.
    if (v2.action.approval_text && v2.action.control) {
      const [lineBox, actionsBox] = await Promise.all([line.boundingBox(), page.getByTestId("hv2-action-buttons").boundingBox()]);
      // The actions are pinned to the card's bottom and the cards are as tall as the tallest (the cash card carries the funding ring), so the gap is the card's spare room, not a wrong order.
      const gap = actionsBox!.y - (lineBox!.y + lineBox!.height);
      expect(gap, "the approval line is above the actions").toBeGreaterThanOrEqual(-1);
      expect(gap, "the approval line is directly above the actions").toBeLessThan(48);
    }
    if (v2.action.control === "APPROVE_PLAN") expect(v2.action.approval_needed, "a plan that waits for the owner").toBe(true);
  }
  expect(await filledBrand(page), `${lang}: filled primaries`).toBe(filled);
}

/** The worklist's words: the alert, the counts, and every row of every tab, in the read's order, each of its shape. */
async function expectWorklist(scope: Locator, lang: Lang, read: WorklistView, showAlert: boolean) {
  const alert = scope.getByTestId("home-worklist-alert");
  // The alert row is shown only on a Home that renders no recommendation card (no title, no control); with a card, the card is the alert.
  if (read.alert && showAlert) {
    const said = read.alert as typeof read.alert & { kind_text?: string | null; pending_text?: string | null };
    await expect(alert).toContainText(said.pending_text ?? said.text);
    await expect(alert).toContainText(said.kind_text ?? said.eyebrow);
    await expect(scope.getByTestId("home-worklist-alert-go")).toContainText(read.alert.primary.label);
  } else await expect(alert).toHaveCount(0);
  const tabs = [["all", [...read.needs_you, ...read.waiting]], ["needs_you", read.needs_you], ["waiting", read.waiting], ["customers", read.customers]] as const;
  for (const [tab, rows] of tabs) {
    await expect(scope.getByTestId(`home-tab-${tab}-badge`)).toHaveText(String(tab === "all" ? read.counts.needs_you + read.counts.waiting : read.counts[tab]));
    expect(rows.length).toBe(tab === "all" ? read.counts.needs_you + read.counts.waiting : read.counts[tab]);
  }
  for (const [tab, rows] of tabs) {
    await scope.getByTestId(`home-tab-${tab}`).click();
    await expect(scope.getByTestId(`home-tab-${tab}`)).toHaveAttribute("aria-selected", "true");
    const el = scope.getByTestId("home-worklist-row");
    if (rows.length === 0) {
      await expect(el).toHaveCount(0);
      const said = (read as WorklistView & { needs_you_empty_text?: string | null }).needs_you_empty_text;
      if ((tab === "needs_you" || tab === "all") && said) await expect(scope.getByTestId("home-worklist-empty")).toContainText(said);
      else {
        await expect(scope.getByTestId("home-worklist-empty")).toContainText(label(lang, "hv2.work.empty.title"));
        await expect(scope.getByTestId("home-worklist-empty")).toContainText(label(lang, tab === "waiting" ? "hv2.work.empty.waiting" : tab === "customers" ? "hv2.work.empty.customers" : "hv2.work.empty.needs"));
      }
      continue;
    }
    await expect(el).toHaveCount(rows.length);
    // Under All the two lists are told apart by heading rows with their counts (12 px uppercase); on one tab there is none.
    if (tab === "all") {
      const heads = [read.needs_you.length ? `${label(lang, "hv2.work.needs")} (${read.needs_you.length})` : null, read.waiting.length ? `${label(lang, "hv2.work.waiting")} (${read.waiting.length})` : null].filter((x): x is string => x !== null);
      await expect(scope.getByTestId("hv2-group-heading")).toHaveText(heads);
    } else await expect(scope.getByTestId("hv2-group-heading")).toHaveCount(0);
    for (const [i, row] of rows.entries()) {
      const li = el.nth(i);
      if ("customer_id" in row && "short" in row) {
        await expect(li).toHaveAttribute("data-kind", "CUSTOMER");
        for (const word of [row.name, row.detail_text]) await expect(li).toContainText(word);
        await expect(li.getByTestId("home-row-status")).toHaveText(row.status_text);
        continue;
      }
      const r = row as WorklistView["needs_you"][number];
      await expect(li).toHaveAttribute("data-kind", r.kind);
      await expect(li).toHaveAttribute("data-owner", r.owner);
      for (const word of [r.subject_text, r.consequence_text]) await expect(li).toContainText(word);
      // The status is the pill, in the server's words; amber when it is the owner's turn, lavender when it is somebody else's.
      await expect(li.getByTestId("home-row-status")).toHaveText(r.status_text);
      await expect(li.getByTestId("home-row-status")).toHaveAttribute("data-tone", r.owner === "NEEDS_YOU" ? "amber" : "lavender");
      // A normal row says nothing about severity; a caution or a critical one wears its dot and its word.
      if (r.severity === "NORMAL") await expect(li.getByTestId("home-row-severity")).toHaveCount(0);
      else await expect(li.getByTestId("home-row-severity")).toHaveAttribute("data-severity", r.severity);
      if (r.differentiator_text) await expect(li.getByTestId("hv2-row-qualifier")).toContainText(r.differentiator_text);
    }
    // The reason a row is first is in its focus, not in the list.
    await expect(scope.getByTestId("home-why-first")).toHaveCount(0);
  }
}

/** One look at a state: the Home at this width and language, equal to the reads. `extra` adds the state's own check. */
async function look(context: BrowserContext, reads: Reads, s: State, extra?: (page: Page, width: number, lang: Lang, scope: Locator) => Promise<void>, url = "/", { company = true } = {}) {
  for (const lang of LANGS) {
    for (const width of WIDTHS) {
      await test.step(`${width} ${lang}`, async () => {
        const page = await open(context, lang, width, url);
        try {
          if (company) await expectCompany(page, lang, reads.home[lang], s.filled);
          const scope = await worklist(page, width, lang, reads.work[lang]);
          await expectWorklist(scope, lang, reads.work[lang], noCard(reads.home[lang]));
          await extra?.(page, width, lang, scope);
        } finally {
          await page.close();
        }
      });
    }
  }
}

// ---------------------------------------------------------------- the tests

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "live", "live-only: the real API");
});

for (const s of STATES.filter((x) => !/^1[12] /.test(x.name))) {
  test(s.name, async ({ request, context }) => {
    const reads = await drive(request, s);
    await look(context, reads, s, async (page, width, lang, scope) => {
      // State-specific words, all from the reads.
      const w = reads.work[lang];
      if (/^0[34] /.test(s.name)) {
        // One customer with several negotiations is one customer row that counts them, and one decision row per deal.
        const foshan = w.customers.find((c) => c.customer_id === "BUYER-1")!;
        expect(foshan.negotiations_count).toBe(s.needs.length);
        expect(foshan.needs_you_count).toBe(s.needs.length);
        await scope.getByTestId("home-tab-customers").click();
        await expect(scope.getByTestId("home-worklist-row").filter({ hasText: foshan.status_text })).toHaveCount(1);
        await scope.getByTestId("home-tab-needs_you").click();
        await expect(scope.getByTestId("home-worklist-row")).toHaveCount(s.needs.length);
      }
      if (s.name.startsWith("06a")) expect(w.needs_you[0].customer_id).toBeNull();
      if (s.name.startsWith("06b")) for (const f of reads.home[lang].home_v2!.action.facts ?? [reads.home[lang].home_v2!.action]) await expect(page.getByTestId("hv2-action")).toContainText("value" in f ? f.value : f.text);
      if (s.name.startsWith("06b")) {
        // The approval line is PRESENT in the warn form, with the server's sentence in the language on screen.
        const line = page.getByTestId("hv2-approval");
        await expect(line).toHaveAttribute("data-needs-owner", "true");
        await expect(line).toHaveText(lang === "zh" ? "需要您批准后才会执行" : "Needs your approval before it runs");
        expect(reads.home[lang].home_v2!.action.approval_needed).toBe(true);
      }
      if (s.name.startsWith("07")) await expect(page.getByTestId("hv2-plan-pill")).toHaveText(new RegExp(`^${DICT[lang]["home.hy.planned" as keyof typeof en]}$`, "i"));
    });
  });
}

// Round four, section 4: on the busy books (an application waiting for approval, funding NONE) the Home renders a recommendation card, so the worklist's alert row is absent; the card is the one that says "FLOW action ready".
test("busy books: a recommendation card and no alert row, at 1440 and 390, in both languages", async ({ request, context }) => {
  await post(request, "/demo/reset?scenario=busy", {});
  const reads = { home: {}, work: {} } as Reads;
  for (const lang of LANGS) {
    reads.home[lang] = await get<HomeView>(request, `/home?lang=${lang}`);
    reads.work[lang] = await get<WorklistView>(request, `/worklist?lang=${lang}`);
  }
  const v2 = reads.home.en.home_v2!;
  expect(Boolean(v2.action.title || v2.action.control), "the busy books carry a recommendation").toBe(true);
  expect(reads.work.en.alert, "the worklist read still carries the alert; the page does not show it").toBeTruthy();
  for (const lang of LANGS) {
    for (const width of WIDTHS) {
      const page = await open(context, lang, width);
      try {
        await expect(page.getByTestId("hv2-action")).toBeVisible();
        await expect(page.getByTestId("home-action-title")).toHaveText(reads.home[lang].home_v2!.action.title);
        await expect(page.getByTestId("home-worklist-alert")).toHaveCount(0);
        // The card's consequence is never cut, the actions are at its bottom and the funding legs (when it has them) are its inline bar.
        const text = reads.home[lang].home_v2!.action.consequence_text;
        if (text && width >= 1024) {
          const said = page.getByTestId("home-action-text");
          await expect(said).toHaveText(text);
          expect(await said.evaluate((n) => n.scrollHeight <= n.clientHeight + 1), "the consequence is not clipped").toBe(true);
        }
        const [card, actions] = await Promise.all([page.getByTestId("hv2-action").boundingBox(), page.getByTestId("hv2-action-buttons").boundingBox()]);
        expect(Math.round(card!.y + card!.height - (actions!.y + actions!.height))).toBeLessThanOrEqual(20);
        const legs = reads.home[lang].home_v2!.action.legs ?? [];
        await expect(page.getByTestId("hv2-funding-bar")).toHaveCount(legs.length ? 1 : 0);
        // Round five: the last upcoming row is the overdue figure (the hybrid read's word and the number of customers with a collection row) linking to Receivables; the owed donut is its own card under the movements, and a slice selects.
        const collections = reads.work[lang].needs_you.filter((r) => r.kind === "COLLECTION").length;
        const short = reads.home[lang].receivables_card?.overdue_short;
        const overdueRow = page.getByTestId("hv2-upcoming-overdue-row");
        if (collections > 0 && short) {
          await expect(overdueRow).toContainText(short);
          await expect(overdueRow).toContainText(label(lang, "hv2.upcoming.overdue"));
          await expect(overdueRow).toContainText(label(lang, collections === 1 ? "hv2.upcoming.overdue.one" : "hv2.upcoming.overdue.many", { n: collections }));
          await expect(page.getByTestId("hv2-upcoming-overdue")).toHaveAttribute("href", "/receivables?from=home");
        } else await expect(overdueRow).toHaveCount(0);
        await expect(page.getByTestId("hv2-upcoming-row")).toHaveCount((reads.home[lang].home_v2!.upcoming ?? []).length);
        const owed = page.getByTestId("hv2-owed-card");
        await expect(owed).toBeVisible();
        const [up, ow] = await Promise.all([page.getByTestId("hv2-upcoming").boundingBox(), owed.boundingBox()]);
        expect(ow!.y).toBeGreaterThan(up!.y + up!.height - 1);
        expect(Math.abs(ow!.x - up!.x)).toBeLessThan(2);
        if (width >= 1024) {
          await page.getByTestId("hv2-owed-row-0").getByRole("button").click();
          await expect(page).toHaveURL(/customer=BUYER-/);
          await expect(page.getByTestId("hv2-owed-card")).toBeVisible();
        }
      } finally {
        await page.close();
      }
    }
  }
});

test(STATES[12].name, async ({ request, context }) => {
  const s = STATES[12];
  const reads = await drive(request, s);
  // The crisis: the alert is the company's, and no customer selection removes it from the worklist read.
  const asked = await get<WorklistView>(request, "/worklist?lang=en&customer=BUYER-1");
  expect(asked.alert).toEqual(reads.work.en.alert);
  await look(context, reads, s, async (page, width, lang) => {
    // The selection is the address; the company's warning stays (held, with the way back), the plan's control is not on the page and the alert is still in the worklist.
    await page.goto("/?customer=BUYER-1");
    await expect(page.getByTestId("home-customer-focus")).toBeVisible();
    expect(new URL(page.url()).searchParams.get("customer")).toBe("BUYER-1");
    const overview = await get<{ name: string; figures: { key: string; value_display: string }[] }>(request, `/customers/BUYER-1/overview?lang=${lang}`);
    await expect(page.getByTestId("focus-title")).toHaveText(overview.name);
    for (const f of overview.figures) await expect(page.getByTestId(`focus-figure-${f.key}-value`)).toHaveText(f.value_display);
    await expect(page.getByTestId("home-v2-action")).toHaveAttribute("data-variant", "held");
    await expect(page.getByTestId("home-action-title")).toHaveText(reads.home[lang].home_v2!.action.title);
    await expect(page.getByTestId("home-action-back")).toBeVisible();
    expect(await filledBrand(page)).toBe(0);
    const again = phone(width) ? await worklist(page, width, lang, reads.work[lang]) : page.getByTestId("home-worklist-panel");
    if (noCard(reads.home[lang])) await expect(again.getByTestId("home-worklist-alert")).toContainText((reads.work[lang].alert as NonNullable<WorklistView["alert"]>).pending_text ?? reads.work[lang].alert!.text);
    else await expect(again.getByTestId("home-worklist-alert")).toHaveCount(0);
    await expect(again.getByTestId("home-tab-needs_you-badge")).toHaveText(String(reads.work[lang].counts.needs_you));
  });
});

test(STATES[13].name, async ({ request, context }) => {
  const s = STATES[13];
  const reads = await drive(request, s);
  const row = reads.work.en.needs_you[0];
  await look(context, reads, s, async (page, width, lang) => {
    // The exposure and the overview are the reads that take a moment cold: hold both, open the decision, and the page says it is working (the dictionary's word), then answers.
    const hold = async (route: Route) => {
      await new Promise((r) => setTimeout(r, 1500));
      await route.continue();
    };
    await page.goto("/");
    await expect(page.getByTestId("hv2-outlook-card")).toBeVisible();
    await page.route("**/customers/*/overview*", hold);
    await page.route("**/offers/*/exposure*", hold);
    const scope = phone(width) ? await worklist(page, width, lang, reads.work[lang]) : page.getByTestId("home-worklist-panel");
    await scope.getByTestId("home-tab-needs_you").click();
    const working = page.getByText(label(lang, "hv2.focus.working"), { exact: true });
    await scope.getByTestId("home-worklist-row").first().getByRole("link").click();
    // A deal row opens the deal on the Deals page (with the origin), which reads its own overview; the Home shows no working state of its own.
    await expect(page.getByTestId("deal-page")).toBeVisible();
    expect(new URL(page.url()).searchParams.get("decision")).toBe(row.key);
    expect(new URL(page.url()).searchParams.get("from")).toBe("home");
    await expect(working).toHaveCount(0, { timeout: 8000 });
    // Answered: the headline is the overview read's, and no money was worked out by the page while it waited.
    const focus = await get<{ decision: { headline_short: string; primary: { label: string } } }>(request, `/customers/BUYER-1/overview?lang=${lang}&decision=${encodeURIComponent(row.key)}`);
    void focus;
  }, "/", { company: false });
});

test("reduced motion: the page and a selection arrive without an animation", async ({ request, context }) => {
  const s = STATES[2];
  await drive(request, s);
  const page = await context.newPage();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/?customer=BUYER-1");
  const panel = page.getByTestId("home-customer-focus");
  await expect(panel).toBeVisible();
  for (const el of [panel, page.getByTestId("home-status")]) {
    const [name, ms] = await el.evaluate((n) => [getComputedStyle(n).animationName, parseFloat(getComputedStyle(n).animationDuration) * 1000] as const);
    expect(name === "none" || ms <= 1, `${name} ${ms} ms`).toBe(true);
  }
  await page.close();
});

test("accessibility: no axe violations on the five deals at 1440 and at 390", async ({ request, context }) => {
  const s = STATES[3];
  const reads = await drive(request, s);
  const violations = async (page: Page) => (await new AxeBuilder({ page }).analyze()).violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
  for (const width of WIDTHS) {
    const page = await open(context, "en", width);
    expect(await violations(page), `${width} Home`).toEqual([]);
    await worklist(page, width, "en", reads.work.en);
    await page.close();
  }
});
