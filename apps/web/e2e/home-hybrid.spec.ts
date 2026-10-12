import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { filledBrand } from "./helpers";
import recorded from "../mocks/home_summary_day0.json";

/**
 * The Home hybrid (board "Home E"): the position, the attention card, the picture with the event rail, the three cards.
 *
 * TEMPORARY PATCH: the recorded home read (mocks/home_summary_day0.json) has none of the hybrid's server fields yet (they are added by the
 * API branch feat/home-hybrid-api and the mocks are re-recorded by the lead after both merge). Until then this spec lays the new optional fields,
 * written the way the API's spec describes them, over the recorded read through the mock's session key `tl-mock-home-patch`
 * (lib/mock/handlers.ts `withHomePatch`). Nothing in a recording is edited. When the mocks are re-recorded, delete `patchFor` and the key and read
 * the fields from the recording; the assertions stay.
 */
const KEY = "tl-mock-home-patch";

type Lang = "en" | "zh";

/** The words of the patch, by language. Server strings: the app shows them as they are. */
const WORDS = {
  en: {
    statusWord: "Covered, but tight",
    heading: "Your cash is covered on the current plan.",
    note: "Cash stays at or above your ¥300k minimum for the next 120 days, assuming the financing arrives in 3 days and Foshan pays in 32 days as scheduled. It touches the minimum in 30 days.",
    assumptions: ["¥255k of invoice financing arrives in 3 days.", "Foshan Home Retail Co. pays ¥420k in 32 days.", "The scheduled payroll, supplier and debt payments as entered."],
    facts: [
      { key: "today", label: "Cash today", short: "¥400k", display: "¥400,000.00", note: "¥100k above your minimum", tone: "ok" },
      { key: "lowest", label: "Lowest point ahead", short: "¥300k", display: "¥300,000.00", note: "¥0 above your minimum, in 30 days", tone: "warn" },
      { key: "arriving", label: "Arriving next", short: "¥255k", display: "¥255,000.00", note: "Invoice financing, in 3 days", tone: "ok" },
    ],
    counterfactual: "without FLOW's financing plan (a comparison, not a choice you still have)",
    rail: [
      { label: "Invoice financing arrives", amount: "+¥255k", when: "in 3 days", explain: "Cash rises from ¥550k to ¥805k when the invoice financing lands. Your minimum is ¥300k." },
      { label: "Payroll", amount: "−¥340k", when: "in 12 days", explain: "Cash falls from ¥805k to ¥465k. Your minimum is ¥300k, so ¥165k of room remains. Without the financing, payroll would have taken cash to ¥60k, below your minimum." },
      { label: "Supplier payment", amount: "−¥120k", when: "in 20 days", explain: "Cash falls from ¥465k to ¥345k. ¥45k of room remains above your minimum." },
      { label: "Lowest point", amount: "−¥45k", when: "in 30 days", explain: "Cash touches ¥300k after the equipment loan payment, exactly your minimum. Without the financing it would be ¥105k below zero.", note: "¥0 above your minimum" },
      { label: "Foshan pays, financing repaid", amount: "+¥163k", when: "in 32 days", explain: "Foshan pays ¥420k, ¥257k repays the financing and ¥163k reaches your cash, which rises to ¥312k." },
    ],
    stress: {
      buyer: "Foshan",
      assumption: "Assumes Foshan Home Retail Co. pays 30 days after the due date, and every other payment arrives as scheduled.",
      plan: "FLOW would draw the rest of your credit line first.",
    },
    attention: {
      eyebrow: "1 deal needs your response",
      title: "Foshan asked for 60-day terms and a 1% rebate. FLOW recommends countering with Option A.",
      facts: [
        { label: "Cost of Option A", value: "¥3,027.77", tone: "ok" },
        { label: "As asked", value: "over your ¥5,000 limit", tone: "bad" },
      ],
      primary: "Review the counter",
      secondary: "Why this?",
      second: "Chase Ningbo Foods, 12 days late",
      none: "No urgent action required.",
    },
    funding: {
      text: "Funding arranged · ¥255k of invoice financing expected in 3 days, repaid from Foshan's receipt in 32 days.",
      leg: "Invoice-financing cost",
      total: "the whole plan, with the ¥150k credit-line draw already made,",
      authority: "Within your signed limits; nothing for you to do.",
    },
    deals: { status: "Your response needed", request: "60-day terms + 1% rebate", recommendation: "Counter with Option A, estimated cost ¥3,027.77" },
    receivables: { next: "Foshan, ¥420k in 32 days", note: "Part of this receipt will repay the ¥255k invoice financing; about ¥163k reaches your cash." },
    changes: ["Invoice financing of ¥255k was arranged.", "Credit line draw of ¥150k was made."],
    ui: { window60: "60 days", expected: "Expected payments", late: "Foshan 30 days late", assumptions: "Forecast assumptions", dealsTitle: "Your deals", recv: "Receivables", recent: "Recent changes", also: "Also waiting", fold: "What changed", radar: "Also on your radar" },
  },
  zh: {
    statusWord: "已覆盖，但较紧",
    heading: "按当前方案，您的现金是够的。",
    note: "未来 120 天现金都不低于您的 ¥300k 最低储备，前提是融资 3 天后到账、佛山按期 32 天后付款。30 天后会触及最低储备。",
    assumptions: ["¥255k 发票融资 3 天后到账。", "佛山家居零售有限公司 32 天后支付 ¥420k。", "按已录入的计划支付工资、供应商和债务款项。"],
    facts: [
      { key: "today", label: "今日现金", short: "¥400k", display: "¥400,000.00", note: "高于最低储备 ¥100k", tone: "ok" },
      { key: "lowest", label: "未来最低点", short: "¥300k", display: "¥300,000.00", note: "高于最低储备 ¥0，30 天后", tone: "warn" },
      { key: "arriving", label: "即将到账", short: "¥255k", display: "¥255,000.00", note: "发票融资，3 天后", tone: "ok" },
    ],
    counterfactual: "不采用 FLOW 融资方案（仅作对比，不是您还能选的路）",
    rail: [
      { label: "发票融资到账", amount: "+¥255k", when: "3 天后", explain: "发票融资到账后，现金由 ¥550k 升至 ¥805k。您的最低储备是 ¥300k。" },
      { label: "发放工资", amount: "−¥340k", when: "12 天后", explain: "现金由 ¥805k 降至 ¥465k，高于最低储备 ¥165k。若没有这笔融资，发工资会让现金降到 ¥60k，低于最低储备。" },
      { label: "支付供应商", amount: "−¥120k", when: "20 天后", explain: "现金由 ¥465k 降至 ¥345k，仍高于最低储备 ¥45k。" },
      { label: "最低点", amount: "−¥45k", when: "30 天后", explain: "还完设备贷款这笔后现金正好是 ¥300k，等于您的最低储备。若没有这笔融资，会低于零 ¥105k。", note: "高于最低储备 ¥0" },
      { label: "佛山付款，融资还清", amount: "+¥163k", when: "32 天后", explain: "佛山支付 ¥420k，其中 ¥257k 用于还清融资，¥163k 进入您的现金，升至 ¥312k。" },
    ],
    stress: {
      buyer: "佛山",
      assumption: "假设佛山家居零售有限公司在到期日后 30 天才付款，其余款项都按期到账。",
      plan: "FLOW 会先动用您信用额度的剩余部分。",
    },
    attention: {
      eyebrow: "有 1 笔交易需要您回复",
      title: "佛山要求 60 天账期和 1% 返利。FLOW 建议用方案 A 还价。",
      facts: [
        { label: "方案 A 的成本", value: "¥3,027.77", tone: "ok" },
        { label: "按对方要求", value: "超出您的 ¥5,000 额度", tone: "bad" },
      ],
      primary: "查看还价",
      secondary: "为什么这样建议？",
      second: "催收宁波食品，已逾期 12 天",
      none: "目前没有需要紧急处理的事项。",
    },
    funding: {
      text: "融资已安排 · ¥255k 发票融资预计 3 天后到账，将用佛山 32 天后的回款偿还。",
      leg: "发票融资成本",
      total: "整个方案（含已提取的 ¥150k 信用额度）",
      authority: "在您已签署的额度内，无需您操作。",
    },
    deals: { status: "需要您回复", request: "60 天账期 + 1% 返利", recommendation: "用方案 A 还价，预计成本 ¥3,027.77" },
    receivables: { next: "佛山，32 天后 ¥420k", note: "这笔回款中的一部分将用于偿还 ¥255k 发票融资，约 ¥163k 进入您的现金。" },
    changes: ["已安排 ¥255k 发票融资。", "已提取 ¥150k 信用额度。"],
    ui: { window60: "60 天", expected: "按预期收款", late: "佛山晚付 30 天", assumptions: "预测所依据的假设", dealsTitle: "您的交易", recv: "应收款", recent: "近期变化", also: "还在等您", fold: "有什么变化", radar: "您还需留意" },
  },
} as const;

const RAIL_DAYS = [3, 12, 20, 30, 32];
const RAIL_KINDS = ["landing", "payroll", "supplier", "lowest", "receipt"];
const RAIL_CASH = ["¥805k", "¥465k", "¥345k", "¥300k", "¥312k"];

interface Opts {
  stress?: boolean;
  queue?: "one" | "two" | "empty";
}

/** The new optional fields, laid over the recorded read. */
function patchFor(lang: Lang, { stress = false, queue = "one" }: Opts = {}) {
  const w = WORDS[lang];
  const plan = recorded.cash.plan_series as { day: number; closing_fen: number; closing_display: string; events: unknown[] }[];
  const late = plan
    .filter((p) => p.day >= 0)
    .map((p) => {
      const fen = p.day >= 32 && p.day < 62 ? p.closing_fen - 42_000_000 : p.closing_fen;
      return { ...p, closing_fen: fen, closing_display: `¥${Math.round(fen / 100000)}k`, events: [] };
    });
  const lateLow = Math.min(...late.map((p) => p.closing_fen));
  const primary = { key: "deal-foshan", kind: "deal", eyebrow: w.attention.eyebrow, title: w.attention.title, facts: w.attention.facts, primary: { label: w.attention.primary, href: "/deals" }, secondary: { label: w.attention.secondary, href: "/deals" } };
  const second = { key: "collect-ningbo", kind: "collection", eyebrow: "", title: w.attention.second, facts: [], primary: { label: "", href: "/receivables" }, secondary: null };
  const items = queue === "empty" ? [] : queue === "two" ? [primary, second] : [primary];
  return {
    cash: {
      status_word: w.statusWord,
      status_tone: "warn",
      headline_conditional: w.heading,
      headline_note: w.note,
      assumptions: w.assumptions,
      facts: w.facts.map((f) => ({ key: f.key, label: f.label, value_short: f.short, value_display: f.display, note: f.note, tone: f.tone })),
      counterfactual_label: w.counterfactual,
      stress_available: stress,
      stress: stress
        ? { delay_days: 30, buyer: w.stress.buyer, series: late, lowest_short: `¥${Math.round(lateLow / 100000)}k`, lowest_when: lang === "zh" ? "32 天后" : "in 32 days", breach_days: 14, need_short: "¥120k", plan_text: w.stress.plan, assumption_text: w.stress.assumption, window_days_needed: 62 }
        : null,
      events_rail: w.rail.map((e, i) => ({
        key: `ev-${i}`,
        day: RAIL_DAYS[i],
        when: e.when,
        kind: RAIL_KINDS[i],
        label: e.label,
        amount_short: e.amount,
        cash_after_short: RAIL_CASH[i],
        room_after_short: "note" in e ? e.note : null,
        tone: RAIL_KINDS[i] === "lowest" ? "warn" : "ok",
        explain: e.explain,
        net_short: null,
      })),
    },
    attention: { items, primary_key: queue === "empty" ? null : "deal-foshan", none_text: w.attention.none },
    funding_line: { state: "arranged", text: w.funding.text, cost_leg_display: "¥1,069.32", cost_leg_label: w.funding.leg, cost_total_display: "¥3,113.93", cost_total_label: w.funding.total, authority_text: w.funding.authority },
    deals_card: [{ buyer: lang === "zh" ? "佛山家居零售" : "Foshan Home Retail Co.", status_text: w.deals.status, request_text: w.deals.request, recommendation_text: w.deals.recommendation, href: "/deals" }],
    receivables_card: { outstanding_short: "¥840k", overdue_short: "¥0", next_text: w.receivables.next, financing_note: w.receivables.note, href: "/receivables" },
    changes_card: w.changes,
  };
}

async function open(page: Page, lang: Lang = "en", opts: Opts = {}) {
  await page.context().addInitScript(
    ([key, patch, l]) => {
      sessionStorage.setItem(key as string, JSON.stringify(patch));
      localStorage.setItem("tl-lang", JSON.stringify({ lang: l }));
    },
    [KEY, patchFor(lang, opts), lang] as const,
  );
  await page.goto("/");
  await expect(page.getByTestId("home-event-picture")).toBeVisible();
  // The chart is measured after layout: wait for it to draw.
  await expect(page.getByTestId("rail-mark-0")).toBeAttached();
}

async function overflowX(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "mock-mode spec on the recorded story (the phone is measured inside it)");
});

test("section 1: the status word, one h1 with the conditional heading, the note, the assumptions and three facts", async ({ page }) => {
  await open(page);
  const w = WORDS.en;
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(w.heading);
  await expect(page.getByTestId("home-status-word")).toContainText("Covered, but tight");
  await expect(page.getByTestId("home-status-word")).toContainText("· read today");
  await expect(page.getByTestId("home-status-word")).not.toContainText("COVERED");
  await expect(page.getByTestId("home-note")).toHaveText(w.note);
  await expect(page.getByTestId("home-assumptions")).not.toHaveAttribute("open", "");
  await page.getByTestId("home-assumptions").locator("> summary").click();
  await expect(page.getByTestId("home-assumptions").locator("li")).toHaveText([...w.assumptions]);
  // Three tiles: label, the big figure, a note; the tone colours the figure only.
  const tiles = page.getByTestId("home-facts").locator("> div");
  await expect(tiles).toHaveCount(3);
  for (const [i, f] of w.facts.entries()) {
    await expect(tiles.nth(i)).toContainText(f.label);
    await expect(page.getByTestId(`home-fact-${f.key}`)).toHaveText(f.short);
    await expect(tiles.nth(i)).toContainText(f.note);
  }
  await expect(page.getByTestId("home-fact-lowest")).toHaveClass(/text-warn-fg/);
  await expect(page.getByTestId("home-fact-today")).not.toHaveClass(/text-(warn|bad|ok)-fg/);
  // Business words: no codes, ids or day numbers.
  await expect(page.locator("main")).not.toContainText(/\bDay \d|ALERT-|RI:/);
});

test("section 2: the deal is the one raised card and the page's only filled primary; the funding line sits beneath with both costs", async ({ page }) => {
  await open(page);
  const w = WORDS.en;
  const card = page.getByTestId("home-attention-card");
  await expect(card.getByTestId("home-attention-eyebrow")).toHaveText(w.attention.eyebrow);
  await expect(card.getByTestId("home-attention-eyebrow")).toHaveClass(/text-warn-fg/);
  await expect(card.getByTestId("home-attention-title")).toHaveText(w.attention.title);
  await expect(card.getByTestId("home-attention-facts")).toContainText("¥3,027.77");
  await expect(card.getByTestId("home-attention-facts")).toContainText("over your ¥5,000 limit");
  expect(await filledBrand(page)).toBe(1);
  await expect(card.getByTestId("home-attention-primary")).toHaveText("Review the counter");
  await expect(card.getByTestId("home-attention-primary")).toHaveCSS("background-color", "rgb(3, 104, 233)");
  await expect(card.getByTestId("home-attention-secondary")).toHaveText("Why this?");
  await expect(card.getByTestId("home-attention-secondary")).not.toHaveCSS("background-color", "rgb(3, 104, 233)");
  // The funding line: its sentence, the two costs each with their label, who decides.
  await expect(card.getByTestId("home-funding-text")).toHaveText(w.funding.text);
  await expect(card.getByTestId("home-funding-costs")).toContainText("Invoice-financing cost ¥1,069.32");
  await expect(card.getByTestId("home-funding-costs")).toContainText("the whole plan, with the ¥150k credit-line draw already made, ¥3,113.93");
  await expect(card.getByTestId("home-funding-authority")).toHaveText(w.funding.authority);
  // The old next-step card is gone while the queue is there.
  await expect(page.getByTestId("home-next-action")).toHaveCount(0);
  await expect(page.getByTestId("home-attention-queue")).toHaveCount(0);
});

test("section 2: a longer queue follows as a short list under the card, never as a second raised card", async ({ page }) => {
  await open(page, "en", { queue: "two" });
  await expect(page.getByTestId("home-attention-card")).toHaveCount(1);
  const queue = page.getByTestId("home-attention-queue");
  await expect(queue).toContainText("Also waiting");
  await expect(queue.locator("li")).toHaveText([WORDS.en.attention.second]);
  expect(await filledBrand(page)).toBe(1);
});

test("section 2: with nothing waiting the card shrinks to the funding line under a quiet line, and nothing is filled", async ({ page }) => {
  await open(page, "en", { queue: "empty" });
  await expect(page.getByTestId("home-attention-none")).toHaveText("No urgent action required.");
  await expect(page.getByTestId("home-attention-card")).toHaveCount(0);
  await expect(page.getByTestId("home-funding-text")).toHaveText(WORDS.en.funding.text);
  expect(await filledBrand(page)).toBe(0);
});

test("section 3: the rail lists the events in order, the fourth is the lowest point, its mark fills when chosen and the panel reads its sentence", async ({ page }) => {
  await open(page);
  const w = WORDS.en.rail;
  const rows = page.locator('[data-testid^="rail-row-"]');
  await expect(rows).toHaveCount(5);
  for (const [i, e] of w.entries()) {
    const row = page.getByTestId(`rail-row-${i}`);
    await expect(row).toContainText(e.label);
    await expect(row).toContainText(e.when);
    await expect(page.getByTestId(`rail-amount-${i}`)).toHaveText(e.amount);
  }
  // The lowest row alone carries the amber note.
  await expect(page.getByTestId("rail-note-3")).toHaveText("¥0 above your minimum");
  await expect(page.getByTestId("rail-note-3")).toHaveClass(/text-warn-fg/);
  await expect(page.locator('[data-testid^="rail-note-"]')).toHaveCount(1);
  // The first event is chosen to begin with; its mark is filled, the others are outlines.
  await expect(page.getByTestId("rail-row-0")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("rail-mark-0")).toHaveAttribute("data-filled", "true");
  await expect(page.getByTestId("rail-mark-3")).toHaveAttribute("data-filled", "false");
  // Mark colours: the lowest point amber, a landing green, an outflow grey.
  await expect(page.getByTestId("rail-mark-3")).toHaveAttribute("data-mark", "amber");
  await expect(page.getByTestId("rail-mark-0")).toHaveAttribute("data-mark", "green");
  await expect(page.getByTestId("rail-mark-1")).toHaveAttribute("data-mark", "grey");
  // Clicking the fourth selects the lowest point and fills its mark; the panel is its sentence, word for word.
  await page.getByTestId("rail-row-3").click();
  await expect(page.getByTestId("rail-row-3")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("rail-row-0")).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByTestId("rail-mark-3")).toHaveAttribute("data-filled", "true");
  await expect(page.getByTestId("rail-mark-0")).toHaveAttribute("data-filled", "false");
  await expect(page.getByTestId("rail-explain")).toHaveText(w[3].explain);
  await expect(page.getByTestId("rail-panel-title")).toContainText("Lowest point");
  // The dotted cursor sits on the chosen event's day.
  await expect(page.getByTestId("home-cursor")).toHaveAttribute("data-day", "30");
  // One polite announcement of the title, for the chosen row.
  await expect(page.getByTestId("rail-announce")).toContainText("Lowest point");
});

test("section 3: pointing at or focusing a row previews it, leaving restores the chosen one", async ({ page }) => {
  await open(page);
  const w = WORDS.en.rail;
  await page.getByTestId("rail-row-3").click();
  await page.getByTestId("rail-row-1").hover();
  await expect(page.getByTestId("rail-mark-1")).toHaveAttribute("data-filled", "true");
  await expect(page.getByTestId("rail-explain")).toHaveText(w[1].explain);
  await expect(page.getByTestId("home-cursor")).toHaveAttribute("data-day", "12");
  // The chosen row is still the chosen one while another is previewed.
  await expect(page.getByTestId("rail-row-3")).toHaveAttribute("aria-pressed", "true");
  await page.mouse.move(5, 5);
  await expect(page.getByTestId("rail-explain")).toHaveText(w[3].explain);
  await expect(page.getByTestId("rail-mark-1")).toHaveAttribute("data-filled", "false");
  await expect(page.getByTestId("rail-mark-3")).toHaveAttribute("data-filled", "true");
  // Keyboard: focus previews (and Enter keeps it); blur returns.
  await page.getByTestId("rail-row-2").focus();
  await expect(page.getByTestId("rail-explain")).toHaveText(w[2].explain);
  await page.keyboard.press("ArrowDown");
  await expect(page.getByTestId("rail-row-3")).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("rail-row-2")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("rail-row-2").blur();
  await expect(page.getByTestId("rail-explain")).toHaveText(w[2].explain);
});

test("section 3: over the plot the dotted cursor follows the pointer with the lines' figures, and leaving returns it to the chosen event", async ({ page }) => {
  await open(page);
  await page.getByTestId("rail-row-3").click();
  const chart = page.getByTestId("home-chart");
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5);
  const tooltip = page.getByTestId("home-tooltip");
  await expect(tooltip).toBeVisible();
  // The figures are the series' own strings, for the plan line and the dashed comparison.
  await expect(tooltip).toContainText("With FLOW's plan");
  await expect(tooltip).toContainText(WORDS.en.counterfactual);
  await expect(tooltip).toContainText(/¥[\d,.]+/);
  const day = Number(await page.getByTestId("home-cursor").getAttribute("data-day"));
  expect(day).not.toBe(30);
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
  await expect.poll(async () => Number(await page.getByTestId("home-cursor").getAttribute("data-day"))).not.toBe(day);
  await page.mouse.move(5, 5);
  await expect(tooltip).toHaveCount(0);
  await expect(page.getByTestId("home-cursor")).toHaveAttribute("data-day", "30");
  // A click on the plot picks the nearest event.
  await page.mouse.click(box.x + box.width * 0.02, box.y + box.height * 0.5);
  await expect(page.getByTestId("rail-row-0")).toHaveAttribute("aria-pressed", "true");
  // Keyboard on the plot: the arrows step through the events.
  await chart.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("rail-row-1")).toHaveAttribute("aria-pressed", "true");
});

test("section 3: no event labels or chips on the plot, the comparison line is named in the legend, the reserve and the axis stay", async ({ page }) => {
  await open(page);
  await expect(page.getByTestId("picture-chips")).toHaveCount(0);
  await expect(page.getByTestId("home-line-plan")).toHaveCount(1);
  await expect(page.getByTestId("home-line-counter")).toHaveCount(1);
  await expect(page.getByTestId("home-legend")).toContainText(WORDS.en.counterfactual);
  await expect(page.getByTestId("home-legend")).toContainText("With FLOW's plan");
  await expect(page.getByTestId("home-reserve")).toHaveCount(1);
  expect(await page.getByTestId("picture-ytick").count()).toBeGreaterThan(2);
  await expect(page.getByTestId("home-chart").locator("svg")).not.toContainText("Payroll");
  // No Play in Business mode.
  await expect(page.getByRole("button", { name: /Play/ })).toHaveCount(0);
});

test("section 3: the window switch widens the picture", async ({ page }) => {
  await open(page);
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-window", "36");
  await page.getByTestId("home-window-60").click();
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-window", "60");
  await expect(page.getByTestId("home-window-60")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("home-window-120").click();
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-window", "120");
});

test("section 3: the scenario switch is hidden without stress_available", async ({ page }) => {
  await open(page, "en", { stress: false });
  await expect(page.getByTestId("home-scenario-late")).toHaveCount(0);
  await expect(page.getByTestId("home-scenario-expected")).toHaveCount(0);
});

test("section 3: the late scenario draws the stress line dashed red, replaces the panel, widens the window and switching back restores", async ({ page }) => {
  await open(page, "en", { stress: true });
  const w = WORDS.en;
  await expect(page.getByTestId("home-scenario-expected")).toHaveText(w.ui.expected);
  await expect(page.getByTestId("home-scenario-late")).toHaveText(w.ui.late);
  await page.getByTestId("home-window-60").click();
  await page.getByTestId("rail-row-3").click();
  await page.getByTestId("home-scenario-late").click();
  const picture = page.getByTestId("home-event-picture");
  await expect(picture).toHaveAttribute("data-scenario", "late");
  await expect(page.getByTestId("home-line-late")).toHaveAttribute("stroke-dasharray", /\d/);
  await expect(page.getByTestId("home-line-late")).toHaveClass(/stroke-bad-solid/);
  await expect(page.getByTestId("home-line-plan")).toHaveCount(0);
  // The panel: the server's assumption and the stress sentence (lowest, breach days, need, plan).
  await expect(page.getByTestId("stress-assumption")).toHaveText(w.stress.assumption);
  const sentence = page.getByTestId("stress-sentence");
  await expect(sentence).toContainText("Cash would fall to");
  await expect(sentence).toContainText("in 32 days");
  await expect(sentence).toContainText("14 days");
  await expect(sentence).toContainText("¥120k");
  await expect(sentence).toContainText(w.stress.plan);
  await expect(page.getByTestId("rail-explain")).toHaveCount(0);
  // The window widened to the days needed, with one line saying so.
  await expect(picture).toHaveAttribute("data-window", "62");
  await expect(page.getByTestId("home-widened")).toHaveText("Showing 62 days so the late payment appears.");
  await expect(page.getByTestId("home-legend")).toContainText(w.ui.late);
  // The rail is inert while the expected events do not apply.
  await expect(page.getByTestId("rail-row-1")).toBeDisabled();
  await expect(page.locator('[data-testid^="rail-mark-"]')).toHaveCount(0);
  // Back: everything is as it was, including the chosen event and the owner's window.
  await page.getByTestId("home-scenario-expected").click();
  await expect(picture).toHaveAttribute("data-scenario", "expected");
  await expect(picture).toHaveAttribute("data-window", "60");
  await expect(page.getByTestId("home-widened")).toHaveCount(0);
  await expect(page.getByTestId("home-line-plan")).toHaveCount(1);
  await expect(page.getByTestId("rail-row-3")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("rail-explain")).toHaveText(WORDS.en.rail[3].explain);
});

test("section 4: three cards, each a link, with the deals, receivables and changes; the old rows are gone; radar and changes are folds", async ({ page }) => {
  await open(page);
  const w = WORDS.en;
  const cards = page.getByTestId("home-cards");
  await expect(cards.locator("> section")).toHaveCount(3);
  const deals = page.getByTestId("home-card-deals");
  await expect(deals).toContainText(w.ui.dealsTitle);
  await expect(deals.getByTestId("home-card-deal")).toHaveCount(1);
  await expect(deals).toContainText("Foshan Home Retail Co.");
  await expect(deals).toContainText(w.deals.status);
  await expect(deals).toContainText(w.deals.request);
  await expect(deals).toContainText(w.deals.recommendation);
  // No stages, no avatar, no button in a card.
  await expect(deals.locator("button")).toHaveCount(0);
  await expect(page.getByTestId("home-deals")).toHaveCount(0);
  await expect(deals.getByTestId("home-card-deals-link")).toHaveAttribute("href", "/deals");
  const recv = page.getByTestId("home-card-receivables");
  await expect(recv).toContainText(w.ui.recv);
  await expect(page.getByTestId("home-card-outstanding")).toHaveText("¥840k");
  await expect(page.getByTestId("home-card-overdue")).toHaveText("¥0");
  await expect(page.getByTestId("home-card-next")).toHaveText(w.receivables.next);
  await expect(page.getByTestId("home-card-financing")).toHaveText(w.receivables.note);
  await expect(page.getByTestId("home-card-financing")).toHaveCSS("font-size", "12px");
  await expect(recv.getByTestId("home-card-receivables-link")).toHaveAttribute("href", "/receivables");
  const changes = page.getByTestId("home-card-changes");
  await expect(changes).toContainText(w.ui.recent);
  await expect(changes.getByTestId("home-card-change")).toHaveText(w.changes);
  await expect(changes.getByTestId("home-card-changes-link")).toHaveAttribute("href", "/activity");
  // The old blocks the cards replace.
  await expect(page.locator("#home-receivables")).toHaveCount(0);
  // "Also on your radar" is a fold under the row.
  const radar = page.getByTestId("home-radar");
  await expect(radar.locator("> summary")).toHaveText(w.ui.radar);
  await expect(radar).not.toHaveAttribute("open", "");
  await expect(radar.locator("> summary")).toBeVisible();
  // The whole card is the link: clicking its body goes there.
  // (The link is stretched over the card, so the click is made at the figure's place, not on the figure.)
  await page.getByTestId("home-card-outstanding").scrollIntoViewIfNeeded();
  const figure = (await page.getByTestId("home-card-outstanding").boundingBox())!;
  await page.mouse.click(figure.x + figure.width / 2, figure.y + figure.height / 2);
  await expect(page).toHaveURL(/\/receivables/);
});

test("the old Home still shows when the server sends none of the hybrid's fields", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-next-action")).toBeVisible();
  await expect(page.getByTestId("home-attention")).toHaveCount(0);
  await expect(page.getByTestId("home-event-picture")).toHaveCount(0);
  await expect(page.getByTestId("home-cards")).toHaveCount(0);
  await expect(page.getByTestId("picture-chips")).toBeVisible();
});

test("a phone (390 x 844): the primary is in the first screen, the rail sits below the picture, nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, "en", { stress: true });
  const primary = page.getByTestId("home-attention-primary");
  await expect(primary).toBeInViewport();
  const box = (await primary.boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(844 - 72); // above the tab bar
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  const chart = (await page.getByTestId("home-chart").boundingBox())!;
  const panel = (await page.getByTestId("rail-panel").boundingBox())!;
  const rail = (await page.getByTestId("home-rail").boundingBox())!;
  expect(rail.y).toBeGreaterThanOrEqual(chart.y + chart.height);
  expect(rail.y).toBeGreaterThanOrEqual(panel.y + panel.height);
  // The cards stack in one column.
  const a = (await page.getByTestId("home-card-deals").boundingBox())!;
  const b = (await page.getByTestId("home-card-receivables").boundingBox())!;
  expect(b.y).toBeGreaterThan(a.y + a.height - 1);
  // The late scenario and the rail stay inside the width too.
  await page.getByTestId("home-scenario-late").click();
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  // Row targets are finger-sized.
  await page.getByTestId("home-scenario-expected").click();
  const row = (await page.getByTestId("rail-row-0").boundingBox())!;
  expect(row.height).toBeGreaterThanOrEqual(44);
  await page.getByTestId("rail-row-3").click();
  await expect(page.getByTestId("rail-explain")).toHaveText(WORDS.en.rail[3].explain);
  // The h1 is 24 px here.
  await expect(page.getByTestId("home-headline")).toHaveCSS("font-size", "24px");
});

test("desktop: the picture and the rail sit side by side with the rail 312 px wide, and the h1 is 34 px at weight 800", async ({ page }) => {
  await open(page);
  const chart = (await page.getByTestId("home-chart").boundingBox())!;
  const rail = (await page.getByTestId("home-rail").boundingBox())!;
  expect(rail.x).toBeGreaterThanOrEqual(chart.x + chart.width);
  expect(Math.round(rail.width)).toBe(312);
  await expect(page.getByTestId("home-headline")).toHaveCSS("font-size", "34px");
  await expect(page.getByTestId("home-headline")).toHaveCSS("font-weight", "800");
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
});

test("Chinese: the same sections, every label and word in Chinese", async ({ page }) => {
  await open(page, "zh", { stress: true });
  const w = WORDS.zh;
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(w.heading);
  await expect(page.getByTestId("home-status-word")).toContainText(w.statusWord);
  await expect(page.getByTestId("home-status-word")).toContainText("· 今天读取");
  await expect(page.getByTestId("home-assumptions").locator("> summary")).toHaveText(w.ui.assumptions);
  await expect(page.getByTestId("home-facts").locator("> div")).toHaveCount(3);
  await expect(page.getByTestId("home-attention-eyebrow")).toHaveText(w.attention.eyebrow);
  await expect(page.getByTestId("home-attention-primary")).toHaveText(w.attention.primary);
  await expect(page.getByTestId("home-funding-costs")).toContainText(`${w.funding.leg} ¥1,069.32`);
  await expect(page.getByTestId("home-funding-costs")).toContainText("；");
  expect(await filledBrand(page)).toBe(1);
  await expect(page.locator('[data-testid^="rail-row-"]')).toHaveCount(5);
  await page.getByTestId("rail-row-3").click();
  await expect(page.getByTestId("rail-explain")).toHaveText(w.rail[3].explain);
  await expect(page.getByTestId("home-scenario-expected")).toHaveText(w.ui.expected);
  await expect(page.getByTestId("home-scenario-late")).toHaveText(w.ui.late);
  await expect(page.getByTestId("home-window-60")).toHaveText(w.ui.window60);
  await expect(page.getByTestId("home-legend")).toContainText(w.counterfactual);
  await page.getByTestId("home-scenario-late").click();
  await expect(page.getByTestId("stress-assumption")).toHaveText(w.stress.assumption);
  await expect(page.getByTestId("stress-sentence")).toContainText("现金将");
  await expect(page.getByTestId("stress-sentence")).toContainText("14 天");
  await expect(page.getByTestId("home-widened")).toHaveText("为显示这笔晚到的款项，已展开到 62 天。");
  await expect(page.getByTestId("home-card-deals")).toContainText(w.ui.dealsTitle);
  await expect(page.getByTestId("home-card-receivables")).toContainText(w.ui.recv);
  await expect(page.getByTestId("home-card-changes")).toContainText(w.ui.recent);
  await expect(page.getByTestId("home-radar").locator("> summary")).toHaveText(w.ui.radar);
  // No English UI labels leak in.
  const text = (await page.locator("main").innerText()).replace(/FLOW|¥[\w,.]+|Foshan/g, "");
  for (const word of ["Forecast assumptions", "Also waiting", "Expected payments", "Key events", "Recent changes", "Your deals", "Receivables"]) expect(text).not.toContain(word);
});

test("axe: no serious or critical finding on the hybrid Home, in both scenarios, at 1440 and at 390", async ({ page }) => {
  const scan = async (label: string) => {
    const result = await new AxeBuilder({ page }).analyze();
    const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`), label).toEqual([]);
  };
  await open(page, "en", { stress: true, queue: "two" });
  await page.getByTestId("home-assumptions").locator("> summary").click();
  await page.getByTestId("rail-row-3").click();
  await scan("expected, 1440");
  await page.getByTestId("home-scenario-late").click();
  await scan("late, 1440");
  await page.setViewportSize({ width: 390, height: 844 });
  await scan("late, 390");
  await page.getByTestId("home-scenario-expected").click();
  await scan("expected, 390");
});
