import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { resetBooks } from "./helpers";
import destinations from "./ask-destinations.json";

/**
 * Ask FLOW, redesigned (the owner's decision of 17 Oct: A, the refined side panel, and B, the full page through Expand). Runs in mock (the
 * recorded answers, mocks/nl_ask.json) and live (the real API). The owner's explicit requirement is that the buttons work: every link an
 * answer card can carry is clicked from a real answer and must land on a page that shows what the chip names (the section in view, or the
 * filter applied); a destination no answer on these books reaches is opened by its address, so none goes unchecked. The header buttons,
 * the suggestion chips and cards, send, Enter, Shift+Enter, the IME guard and Escape are pressed too, in English and Chinese, at 1440 px and
 * at a 390 px phone; axe finds nothing serious. With SHOTS_DIR set it also saves the screenshots of the panel and the page.
 */

const isLive = () => test.info().project.name === "live";
const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
const SHOTS = process.env.SHOTS_DIR;
type Dest = (typeof destinations.destinations)[number];

test.beforeEach(async ({ page, request }, testInfo) => {
  test.skip(testInfo.project.name === "phone", "the phone width is set by the specs themselves");
  await resetBooks(request);
  await page.addInitScript(() => sessionStorage.setItem("tl-welcomed", "1"));
});

const panelOf = (page: Page, name = "Ask FLOW") => page.getByRole("dialog", { name });
const turns = (scope: Page | Locator) => scope.getByTestId("chat-turn");

/** Opens the side panel by the keyboard (the header's icon keeps a mouse click from taking the focus), so the focus returns to it on close. */
async function openPanel(page: Page, name = "Ask FLOW"): Promise<Locator> {
  await page.getByTestId("chat-open").focus();
  await page.keyboard.press("Enter");
  const panel = panelOf(page, name);
  await expect(panel).toBeVisible();
  return panel;
}

/** FLOW's opener has settled: its turn is shown (something needs the owner) or the empty state is (nothing does). */
async function openerSettled(scope: Page | Locator) {
  await expect(scope.getByTestId("chat-busy")).toHaveCount(0, { timeout: 30_000 });
}

/** Types a question in the composer and sends it with Enter; returns FLOW's answer to it. */
async function ask(scope: Page | Locator, text: string): Promise<Locator> {
  const before = await turns(scope).count();
  const box = scope.getByRole("textbox", { name: "Message" }).or(scope.getByRole("textbox", { name: "消息" }));
  await box.fill(text);
  await box.press("Enter");
  await expect(turns(scope)).toHaveCount(before + 1, { timeout: 30_000 });
  return turns(scope).last();
}

async function axe(page: Page, label: string) {
  await expect.poll(() => page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length)).toBe(0);
  const result = await new AxeBuilder({ page }).analyze();
  const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.help} ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`), label).toEqual([]);
}

async function shot(page: Page, name: string) {
  if (!SHOTS) return;
  mkdirSync(SHOTS, { recursive: true });
  await expect.poll(() => page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length)).toBe(0);
  await page.screenshot({ path: join(SHOTS, `${name}.png`) });
}

/** No sideways scroll on the page, and none inside the panel when it is open. */
async function noOverflow(page: Page) {
  const over = await page.evaluate(() => {
    const doc = document.documentElement.scrollWidth - document.documentElement.clientWidth;
    const d = document.querySelector('[data-testid="chat-panel"]') as HTMLElement | null;
    const panel = d && d.matches("[open]") ? d.scrollWidth - d.clientWidth : 0;
    return Math.max(doc, panel);
  });
  expect(over).toBeLessThanOrEqual(1);
}

// ---------------------------------------------------------------- A: the side panel

test("the panel: its header buttons, FLOW speaks first once, and an answer laid out as a card", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const openers: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && new URL(r.url()).pathname === "/nl/opener") openers.push(r.url());
  });
  await page.goto("/");
  const panel = await openPanel(page);
  // The header: FLOW's mark and name, then the three named icon buttons, each with its tooltip.
  await expect(panel.getByRole("heading", { name: "Ask FLOW" })).toBeVisible();
  await expect(panel.getByTestId("flow-mark").first()).toBeVisible();
  for (const [testId, name] of [["chat-new", "New conversation"], ["chat-expand", "Open as a full page"], ["chat-close", "Close chat"]]) {
    await expect(panel.getByTestId(testId)).toHaveAccessibleName(name);
    await expect(panel.getByTestId(testId)).toHaveAttribute("title", name);
  }
  // FLOW speaks first: on the opening books something needs the owner, so its opener is the first message, with its links.
  await openerSettled(panel);
  await expect(turns(panel)).toHaveCount(1);
  await expect(turns(panel).first().getByTestId("card-action").first()).toBeVisible();
  // The opener is laid out like an answer: a bold lead in the owner's words, never an id or "I" (the engine's sentence is not shown).
  const opener = turns(panel).first().getByTestId("chat-card");
  await expect(opener.getByTestId("card-lead")).toBeVisible();
  if (isLive()) {
    await expect(opener.getByTestId("card-lead")).toHaveText("Cash falls below your ¥300,000 reserve in 12 days, ¥240,000 short.");
    await expect(opener.getByTestId("card-figure")).toHaveCount(3);
    await expect(opener.getByTestId("card-body")).toContainText("FLOW's plan: draw ¥150,000 on the Bank credit line today and finance ¥255,000 of the ¥420,000 invoice to Foshan Home Retail Co.");
    await expect(turns(panel).first().getByTestId("chat-goahead")).toBeEnabled(); // the plan still waits for the go-ahead
  } else {
    await expect(opener.getByTestId("card-lead")).toHaveText("1 warning: Cash is close to your minimum in 30 days.");
  }
  const openerWords = await opener.evaluate((el) => (el as HTMLElement).innerText);
  expect(openerWords).not.toMatch(/RCV-|BUYER-|RI:|APR-|FAC-|\bI\b/);
  for (const a of await turns(panel).first().getByTestId("card-action").all()) expect(await a.getAttribute("href")).toMatch(/^\/[a-z#?]*/);
  await shot(page, "after-panel-desktop-en-opener");

  // Closed and opened again: the same conversation, and the opener is not asked twice.
  await panel.getByTestId("chat-close").click();
  await expect(panel).toBeHidden();
  await openPanel(page);
  await openerSettled(panel);
  await expect(turns(panel)).toHaveCount(1);
  if (isLive()) expect(openers).toHaveLength(1);

  // An answer with structure: the lead in bold, three key figures with their tone, the rest, the links, and how it was worked out.
  const safe = await ask(panel, "Are we safe?");
  const card = safe.getByTestId("chat-card");
  await expect(card.getByTestId("card-lead")).toHaveText(/^Not on today's books: without new funding, cash falls below your ¥300,000 reserve from day 12/);
  await expect(card.getByTestId("card-figure")).toHaveCount(3);
  await expect(card.getByTestId("card-figure").first()).toHaveAttribute("data-tone", "danger");
  await expect(card.getByTestId("card-figure").first()).toContainText("¥405,000");
  await expect(card.getByTestId("card-figure").first()).toContainText("Funding needed");
  await expect(card.getByTestId("card-body")).toContainText("FLOW's plan covers it for ¥3,113.93");
  await expect(card.getByTestId("card-action")).toHaveText(["See the cash forecast", "Open FLOW's plan"]);
  await expect(card.getByTestId("card-basis")).toBeHidden();
  await card.getByTestId("card-how").locator("summary").click();
  await expect(card.getByTestId("card-basis")).toContainText("Conservative forecast, today's books, day 0");
  await expect(card.getByTestId("card-all-figures")).toContainText("Your reserve");
  // The owner's message: the light bubble on the right, with no "You" label on screen.
  const mine = panel.getByTestId("chat-user").last();
  await expect(mine.locator("p")).toHaveText("Are we safe?");
  // Who said it is for a screen reader only: nothing but the question is drawn.
  await expect(mine.locator(":scope > div > :not(.sr-only)")).toHaveText(["Are we safe?"]);
  await expect(mine.locator(".sr-only")).toHaveText("You:");
  await shot(page, "after-panel-desktop-en-card");
  await axe(page, "the panel with an answer card");
});

test("the composer: Enter sends, Shift+Enter adds a line, Enter while composing Chinese does not send, Escape closes", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/cash");
  const panel = await openPanel(page);
  await openerSettled(panel);
  const n = await turns(panel).count();
  const box = panel.getByRole("textbox", { name: "Message" });
  // The suggestion chips sit above the box while it is empty, and give way once a question is being typed.
  await expect(panel.locator('[data-testid^="prompt-"]').first()).toBeVisible();
  await box.fill("line one");
  if (n > 0) await expect(panel.locator('[data-testid^="prompt-"]')).toHaveCount(0);
  await box.press("Shift+Enter");
  await box.pressSequentially("line two");
  await expect(box).toHaveValue("line one\nline two");
  // An IME's Enter (the candidate being confirmed) never sends: both the standard flag and the older engines' key code 229.
  await box.evaluate((el) => {
    el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true, isComposing: true }));
    el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", keyCode: 229, bubbles: true, cancelable: true }));
  });
  await expect(box).toHaveValue("line one\nline two");
  await expect(turns(panel)).toHaveCount(n);
  // The send button stays off for a blank box and sends the question.
  await box.fill("   ");
  await expect(panel.getByTestId("chat-send")).toBeDisabled();
  await box.fill("Are we inside our covenants?");
  await expect(panel.getByTestId("chat-send")).toHaveAccessibleName("Send");
  await panel.getByTestId("chat-send").click();
  await expect(turns(panel)).toHaveCount(n + 1, { timeout: 30_000 });
  await expect(turns(panel).last().getByTestId("card-lead")).toHaveText("Yes.");
  await expect(box).toHaveValue("");
  // Enter alone sends.
  await box.fill("How much debt do we have?");
  await box.press("Enter");
  await expect(turns(panel)).toHaveCount(n + 2, { timeout: 30_000 });
  await expect(turns(panel).last().getByTestId("card-lead")).toContainText("¥1,500,000");
  // Escape closes the panel and gives the focus back to the button that opened it.
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  await expect(page.getByTestId("chat-open")).toBeFocused();
});

test("Expand opens the same conversation as a full page that survives a reload; Back returns to the panel; New conversation starts over", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/activity");
  const panel = await openPanel(page);
  await openerSettled(panel);
  await ask(panel, "Which customer owes us the most?");
  const count = await turns(panel).count();
  await panel.getByTestId("chat-expand").click();
  await expect(page).toHaveURL(/\/ask$/);
  await expect(panelOf(page)).toBeHidden();
  const full = page.getByTestId("ask-page");
  await expect(full.getByRole("heading", { level: 1, name: "Ask FLOW" })).toBeVisible();
  await expect(turns(full)).toHaveCount(count);
  await expect(turns(full).last().getByTestId("card-lead")).toContainText("Foshan Home Retail Co.");
  // A reload keeps the conversation (this tab's session); its links still work, its old buttons are history.
  await page.reload();
  await expect(turns(full)).toHaveCount(count);
  await expect(turns(full).last().getByTestId("card-action").first()).toBeVisible();
  // Back to the side panel: the page Expand was pressed on, with the panel open on the same conversation.
  await full.getByTestId("chat-collapse").click();
  await expect(page).toHaveURL(/\/activity$/);
  await expect(panelOf(page)).toBeVisible();
  await expect(turns(panelOf(page))).toHaveCount(count);
  // New conversation: the transcript goes and the session ends on the server; FLOW does not speak again until the panel is opened again.
  const ended = isLive() ? page.waitForRequest((r) => r.method() === "POST" && new URL(r.url()).pathname === "/nl/session/reset") : null;
  await panelOf(page).getByTestId("chat-new").click();
  await expect(turns(panelOf(page))).toHaveCount(0);
  await expect(panelOf(page).getByTestId("chat-empty")).toBeVisible();
  if (ended) expect((await ended).postDataJSON()).toHaveProperty("session_id");
  await page.keyboard.press("Escape");
  await openPanel(page);
  await openerSettled(panelOf(page));
  await expect(turns(panelOf(page))).toHaveCount(1); // the opener, once, on the fresh conversation
});

// ---------------------------------------------------------------- B: the full page

test("the Ask FLOW page: the greeting, four question cards, the opener, and a card with a customer's links", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/ask");
  const full = page.getByTestId("ask-page");
  const welcome = full.getByTestId("ask-welcome");
  await expect(welcome.getByRole("heading", { name: "What would you like to know?" })).toBeVisible();
  const cards = welcome.locator('[data-testid^="prompt-ask-"]');
  await expect(cards).toHaveCount(4);
  await expect(cards.first()).toContainText("Are we safe?");
  await expect(cards.first()).toContainText("Your cash against your reserve, day by day");
  await openerSettled(full);
  await expect(turns(welcome)).toHaveCount(1);
  await shot(page, "after-page-desktop-en-empty");
  await axe(page, "the Ask FLOW page, empty");
  await full.getByTestId("prompt-ask-owes").click();
  await expect(full.getByTestId("ask-welcome")).toHaveCount(0);
  const owes = turns(full).last();
  await expect(owes.getByTestId("card-lead")).toContainText("Foshan Home Retail Co.: ¥420,000 on one invoice");
  await expect(owes.getByTestId("card-action")).toHaveText(["See Foshan Home Retail Co.'s invoices", "Open Foshan Home Retail Co."]);
  // The chips come back above the box once the conversation has begun.
  await expect(full.getByTestId("prompt-ask-safe")).toBeVisible();
  await shot(page, "after-page-desktop-en-card");
  await axe(page, "the Ask FLOW page with a card");
});

// ---------------------------------------------------------------- the buttons work: every link, from a real answer

/** One question per destination (the recorded set in mock, the same questions live), in English. */
const QUESTIONS = [
  "Are we safe?",
  "Are we inside our covenants?",
  "Which customer owes us the most?",
  "How much debt do we have?",
  "Is anything waiting for my approval?",
  "What did FLOW do recently?",
  "Can we afford the die-cutting machine?",
  "What can FLOW do without me?",
  "Should we take the early payment?",
];

function destOf(href: string): Dest {
  const template = href.replace(/(customer=)[A-Z0-9-]+$/, "$1{id}").replace(/(\/customers\/)[A-Z0-9-]+$/, "$1{id}");
  const d = destinations.destinations.find((x) => x.href === template);
  expect(d, `${href} is a destination the server may emit`).toBeTruthy();
  return d!;
}

/** The page the link opened shows what the chip names: its address, and the section in view (an anchor) or the page and its filter. */
async function landed(page: Page, href: string, label: string) {
  const d = destOf(href);
  const url = new URL(href, "http://x");
  await expect(page, label).toHaveURL((u) => u.pathname === url.pathname && u.search === url.search && u.hash === url.hash);
  const target = page.locator(d.target).first();
  await expect(target, `${label}: ${d.target}`).toBeVisible({ timeout: 20_000 });
  await expect(target, `${label}: ${d.target} in view`).toBeInViewport();
  if (d.target.startsWith("#")) {
    await expect(target).toHaveAttribute("data-landed", "true");
    if (await target.evaluate((el) => el.tagName === "DETAILS")) await expect(target).toHaveAttribute("open", "");
  }
  if (d.key === "customer" || d.key === "customer_invoices") await expect(target.or(page.locator("main h1")).first()).toContainText(/Foshan/);
  expect((await page.request.get(href.split("#")[0])).status(), `${href} answers 200`).toBe(200);
}

test("every link an answer can carry opens the page that shows what its chip names", async ({ page }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/ask");
  const full = page.getByTestId("ask-page");
  await openerSettled(full);
  const found = new Map<string, string>(); // href -> the chip's label
  for (const q of QUESTIONS) {
    const answer = await ask(full, q);
    await expect(answer.getByTestId("chat-card"), q).toBeVisible();
    const hrefs = await answer.getByTestId("card-action").evaluateAll((els) => els.map((el) => el.getAttribute("href") ?? ""));
    // Each link not yet opened is clicked from this answer; back on the page the conversation is still there (this tab's session), this answer last.
    for (const href of hrefs) {
      if (found.has(href)) continue;
      const chip = turns(full).last().locator(`[data-testid="card-action"][data-href="${href}"]`);
      const label = (await chip.innerText()).trim();
      found.set(href, label);
      await chip.click();
      await landed(page, href, `${q} -> ${label}`);
      await page.goto("/ask");
      await expect(turns(full).last().getByTestId("chat-card")).toBeVisible();
    }
  }
  // A destination no answer reaches on these books (the receivables list without a customer: every answer here names one) is opened by its address.
  const reached = new Set([...found.keys()].map((h) => destOf(h).key));
  for (const d of destinations.destinations) {
    if (reached.has(d.key)) continue;
    const href = d.href.replace("{id}", "BUYER-1");
    await page.goto(href);
    await landed(page, href, `${d.key} (by address)`);
  }
  expect([...reached].sort(), "the answers reach every destination but the plain list").toEqual(
    destinations.destinations.map((d) => d.key).filter((k) => k !== "receivables").sort(),
  );
});

test("a link opened from the panel closes it, and a link to a section of the page already open lands on that section", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/cash");
  const panel = await openPanel(page);
  await openerSettled(panel);
  const cov = await ask(panel, "Are we inside our covenants?");
  await cov.getByTestId("card-action").first().click();
  await expect(panel).toBeHidden();
  await landed(page, "/cash#cash-readings", "covenant readings from the panel on Cash");
});

// ---------------------------------------------------------------- Chinese, and the reply's language

test("Chinese: the panel, the page and the card speak Chinese; a question follows its own language whatever the page's", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  // The English app, a Chinese question: the answer, its card and its links are Chinese.
  await page.goto("/");
  let panel = await openPanel(page);
  await openerSettled(panel);
  const zhInEn = await ask(panel, "我们安全吗？");
  await expect(zhInEn.getByTestId("card-lead")).toContainText("按今日账目并不安全");
  await expect(zhInEn.getByTestId("card-figure").first()).toContainText("所需资金");
  await expect(zhInEn.getByTestId("card-action").first()).toHaveText("查看现金预测");
  await page.keyboard.press("Escape");

  // The Chinese app.
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.goto("/cash");
  panel = await openPanel(page, "询问 FLOW");
  await expect(panel.getByTestId("chat-expand")).toHaveAccessibleName("全屏打开");
  await expect(panel.getByTestId("chat-new")).toHaveAccessibleName("新对话");
  const zh = await ask(panel, "我们满足契约吗？");
  await expect(zh.getByTestId("card-lead")).toHaveText("满足。");
  await expect(zh.getByTestId("card-action")).toHaveText(["查看契约指标"]);
  await expect(zh.getByTestId("card-how").locator("summary")).toHaveText("FLOW 是如何得出的");
  // An English question in the Chinese app is answered in English.
  const enInZh = await ask(panel, "Are we safe?");
  await expect(enInZh.getByTestId("card-lead")).toContainText("Not on today's books");
  await expect(enInZh.getByTestId("card-action").first()).toHaveText("See the cash forecast");
  await shot(page, "after-panel-desktop-zh-card");
  await axe(page, "the panel in Chinese");
  await panel.getByTestId("chat-expand").click();
  await expect(page).toHaveURL(/\/ask$/);
  await expect(page.getByRole("heading", { level: 1, name: "询问 FLOW" })).toBeVisible();
  await page.getByTestId("chat-new").click();
  await page.reload();
  const welcome = page.getByTestId("ask-welcome");
  await expect(welcome.getByRole("heading", { name: "想了解什么？" })).toBeVisible();
  await expect(welcome.getByTestId("prompt-ask-need")).toContainText("我们需要融多少？");
  await openerSettled(page.getByTestId("ask-page"));
  await shot(page, "after-page-desktop-zh-empty");
  await welcome.getByTestId("prompt-ask-need").click();
  const need = turns(page.getByTestId("ask-page")).last();
  await expect(need.getByTestId("card-lead")).toContainText("需要 ¥405,000");
  await expect(need.getByTestId("card-action")).toHaveText(["查看 FLOW 的方案", "查看现金预测"]);
  await shot(page, "after-page-desktop-zh-card");
});

// ---------------------------------------------------------------- a phone

test("a 390 px phone: the panel and the page fit without sideways scroll, and the links work", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByTestId("chat-open").click();
  const panel = panelOf(page);
  await expect(panel).toBeVisible();
  await openerSettled(panel);
  const safe = await ask(panel, "Are we safe?");
  await expect(safe.getByTestId("card-figure")).toHaveCount(3);
  await noOverflow(page);
  await shot(page, "after-panel-phone-en-card");
  await axe(page, "the panel on a phone");
  await safe.getByTestId("card-action").first().click();
  await expect(panel).toBeHidden();
  await landed(page, "/cash#cash-chart", "the forecast from the phone's panel");
  await page.goto("/ask");
  await expect(page.getByTestId("ask-page")).toBeVisible();
  await noOverflow(page);
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.reload();
  await expect(turns(page.getByTestId("ask-page")).last().getByTestId("chat-card")).toBeVisible();
  await noOverflow(page);
  await shot(page, "after-page-phone-zh");
});

// ---------------------------------------------------------------- the server's side of it (live)

test("live: the opener and an answer card come from the server, owner only; the agent key gets no card", async ({ request }) => {
  test.skip(!isLive(), "the real API");
  const owner = { "X-Owner-Token": "demo-owner-token" };
  const opener = await (await request.post(`${API}/nl/opener`, { headers: owner, data: { session_id: "ask-live-opener", lang: "en" } })).json();
  expect(opener.has_news).toBe(true);
  expect(opener.card.actions.every((a: { kind: string }) => a.kind === "link")).toBe(true);
  const card = await (await request.post(`${API}/nl`, { headers: owner, data: { session_id: "ask-live-card", actor: "OWNER", text: "Are we safe?", lang: "en" } })).json();
  expect(card.card.lead).toMatch(/^Not on today's books/);
  const agent = await (await request.post(`${API}/nl`, { headers: { "X-Agent-Key": "demo-agent-key" }, data: { session_id: "ask-live-agent", actor: "OWNER", text: "Are we safe?", lang: "en" } })).json();
  expect(agent.card ?? null).toBeNull();
  expect(JSON.stringify(agent)).not.toContain("¥405,000");
});
