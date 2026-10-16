import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import rec from "../mocks/buyer_message.json";
import { expect, test } from "./fixtures";
import { checkedDeal, openOperatorTools, openReview } from "./helpers";

/**
 * The message the owner sends the buyer outside FLOW (ADR-0011 addendum, round two): FLOW transmits nothing. The deal is ONE state, whatever the server says happened.
 *   Send (RESPONSE_READY): what they asked beside what the owner offers, then the letter in the buyer's language; Copy is the filled button until copied, then "I've sent it".
 *   Waiting (AWAITING_BUYER): the lavender banner, what was sent, and "What did {buyer} say?" with three tiles: accept, counter, decline.
 *   Endings: accepted (the agreement and its receipt), countered (a request of its own), declined (with a reason), no answer (the clock past the day it was open until).
 * Mock mode, on the API's own recordings (scripts/record-mocks.mjs --buyer-message): every sentence below is the server's, read from that file. The test hooks are sessionStorage keys:
 *   tl-mock-message-changed = 1     the next mark is refused with the recorded 409 MESSAGE_CHANGED
 *   tl-mock-no-simulated-buyer = 1  the next simulated send is refused with the recorded 409 NO_SIMULATED_BUYER
 */

const COUNTER = rec.offered.en.counter_id;
const before = rec.message[COUNTER as keyof typeof rec.message].en;
const waiting = rec.awaiting.en.decision.outbound!;
/** What the clipboard holds, with the platform's line endings read as the message's own. */
const clipboard = (page: Page) => page.evaluate(() => navigator.clipboard.readText()).then((t) => t.replace(/\r\n/g, "\n"));
const literal = (s: string) => new RegExp(`${s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`);

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded reads");
});

async function scan(page: Page, label: string) {
  await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished.catch(() => undefined))));
  const result = await new AxeBuilder({ page }).include('[data-testid="deal-pane"]').analyze();
  const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`), `${label}: serious or critical findings`).toEqual([]);
}

/** The package offer checked, its send review open on the reply FLOW recommends, and the message to the buyer read. */
async function messagePanel(page: Page) {
  await checkedDeal(page);
  await openReview(page);
  const panel = page.getByTestId("buyer-message");
  await expect(panel).toHaveAttribute("data-counter", COUNTER);
  await expect(panel.getByTestId("buyer-message-text")).toBeVisible();
  return panel;
}

/** Marked sent: the deal waits for the buyer. */
async function markedSent(page: Page) {
  const panel = await messagePanel(page);
  await panel.getByTestId("buyer-message-mark-sent").click();
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AWAITING_BUYER");
  await expect(page.getByTestId("outbound-waiting")).toBeVisible();
}

test("send: what they asked beside what you offer, the letter in the buyer's language, Copy then I've sent it, and no simulator in Business", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const panel = await messagePanel(page);
  // The header: the state in the server's word and the four steps, only the request reached.
  await expect(page.getByTestId("deal-history-strip")).toBeVisible();
  await expect(page.getByTestId("history-step-asked")).toContainText(rec.ready.en.history![0].date);
  await expect(page.getByTestId("history-step-sent")).toHaveAttribute("data-tone", "todo");

  const offer = page.getByTestId("buyer-message-offer");
  await expect(offer).toContainText("They asked");
  await expect(offer).toContainText(`You offer · ${before.en.counter_label_when}`);
  for (const term of before.en.review!.terms!) await expect(offer.getByTestId(`buyer-message-term-${term.key}`).getByTestId("buyer-message-term-offer")).toHaveText(literal(term.cell_text!));
  await expect(offer.getByTestId("buyer-message-cost")).toContainText(before.en.review!.cost_display!);
  await expect(offer.getByTestId("buyer-message-cost")).toHaveAttribute("data-within", "true");
  await expect(offer.getByTestId("buyer-message-decides")).toHaveText(before.en.review!.decides_text!);

  await expect(panel.getByRole("heading", { name: before.en.send_title_text })).toBeVisible();
  await expect(panel.getByTestId("buyer-message-notice")).toHaveText(before.en.notice_text);
  await expect(panel.getByTestId("buyer-message-provenance")).toHaveText(before.en.provenance.text);
  await expect(panel.getByTestId("buyer-message-provenance")).toHaveAttribute("data-verified", "true");
  await expect(panel.getByTestId("buyer-message-until")).toHaveText(`To ${before.en.buyer_name} · open until ${before.en.valid_until_date}`);
  await expect(panel.getByTestId("buyer-message-text")).toHaveText(before.en.text!);
  await expect(panel.getByTestId("buyer-message-effect")).toHaveText(before.en.mark_sent_effect_text);
  // Copy is the filled button until the message has been copied; then "I've sent it to the buyer" is.
  await expect(panel.getByTestId("buyer-message-copy")).toHaveAttribute("data-filled", "true");
  await expect(panel.getByTestId("buyer-message-mark-sent")).toHaveAttribute("data-filled", "false");
  await panel.getByTestId("buyer-message-copy").click();
  await expect(panel.getByTestId("buyer-message-copy-status")).toHaveText("Copied");
  expect(await clipboard(page)).toBe(before.en.text);
  await expect(panel.getByTestId("buyer-message-mark-sent")).toHaveAttribute("data-filled", "true");

  // The buyer's language, not the page's: the message is in Chinese, every word around it stays in English, and what was copied is another message.
  await panel.getByTestId("buyer-message-lang").getByText(before.en.languages![1].label).click();
  await expect(panel.getByTestId("buyer-message-text")).toHaveAttribute("data-lang", "zh");
  await expect(panel.getByTestId("buyer-message-text")).toHaveText(before.zh.text!);
  await expect(panel.getByTestId("buyer-message-notice")).toHaveText(before.zh.notice_text);
  expect(before.zh.notice_text).toBe(before.en.notice_text);
  await expect(panel.getByTestId("buyer-message-copy")).toHaveAttribute("data-filled", "true");
  await panel.getByTestId("buyer-message-copy").click();
  expect(await clipboard(page)).toBe(before.zh.text);

  // Business mode has no simulated send (the owner's choice): the simulator is the Demo's.
  await expect(page.getByTestId("deal-demo-send")).toHaveCount(0);
  await expect(page.getByTestId("deal-send")).toHaveCount(0);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
  await scan(page, "send review");
});

test("mark sent: refused when the message changed, then the deal waits for the buyer, in one lavender state", async ({ page }) => {
  const panel = await messagePanel(page);
  await page.evaluate(() => sessionStorage.setItem("tl-mock-message-changed", "1"));
  await panel.getByTestId("buyer-message-mark-sent").click();
  await expect(panel.getByTestId("buyer-message-refused")).toHaveText(rec.message_changed.en.message_when);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");

  await panel.getByTestId("buyer-message-mark-sent").click();
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AWAITING_BUYER");
  await expect(page.getByTestId("deal-state-chip")).toHaveText(rec.awaiting.en.decision.state_text);
  await expect(page.getByTestId("deal-marked-sent")).toHaveText(rec.offered.en.message_when);
  await expect(page.getByTestId("queue-review")).toHaveCount(0);
  await expect(page.getByTestId("history-step-sent")).toContainText(waiting.label_text!);
  await expect(page.getByTestId("history-step-answer")).toHaveAttribute("data-tone", "waiting");
  await expect(page.getByTestId("history-step-answer")).toContainText(waiting.closes_text!);

  const banner = page.getByTestId("outbound-banner");
  await expect(banner).toContainText(waiting.title_text);
  await expect(banner.getByTestId("outbound-closes")).toHaveText(waiting.closes_text!);
  await expect(banner.getByTestId("outbound-text")).toHaveText(waiting.text);
  await expect(banner.getByTestId("outbound-progress")).toHaveAttribute("aria-valuenow", String(Math.round(waiting.progress! * 100)));
  const sent = page.getByTestId("outbound-sent");
  await expect(sent.getByTestId("outbound-sent-text")).toHaveText(waiting.sent_text);
  await expect(sent.getByTestId("outbound-sent-terms")).toContainText(waiting.terms[0]);
  await sent.getByTestId("outbound-sent-message").locator("summary").click();
  await expect(sent.getByTestId("outbound-sent-message-text")).toHaveText(waiting.message_text!);
  await expect(page.getByTestId("outbound-answer")).toContainText(waiting.actions!.question_text);
  for (const k of ["accept", "counter", "decline"] as const) await expect(page.getByTestId(`outbound-tile-${k}`)).toContainText(waiting.actions![k].label);
  await scan(page, "waiting for the buyer");

  // The decision record says the counter went out outside FLOW.
  await page.getByTestId("deal-record-link").click();
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "AWAITING_BUYER");
  await expect(page.getByTestId("record-sent-outside")).toHaveText((rec.awaiting.en.decision.response!.sent as { text: string }).text);
});

test("they accepted: the terms, cost and authority, then the agreement with its receipt and the history", async ({ page }) => {
  await markedSent(page);
  await page.getByTestId("outbound-tile-accept").click();
  await expect(page.getByTestId("outbound-tile-accept")).toHaveAttribute("aria-pressed", "true");
  const confirm = page.getByTestId("outbound-confirm-accept");
  await expect(confirm.getByTestId("outbound-accept-cost")).toContainText(waiting.actions!.accept.review!.cost_display!);
  await expect(confirm.getByTestId("outbound-accept-authority")).toHaveText(waiting.actions!.accept.authority_text!);
  await confirm.getByTestId("outbound-confirm").click();

  const done = rec.accepted.en.decision;
  const ending = page.getByTestId("outbound-ending");
  await expect(ending).toHaveAttribute("data-answer", "accepted");
  await expect(ending.getByTestId("outbound-ending-title")).toHaveText(done.outbound!.title_text);
  await expect(ending.getByTestId("outbound-ending-text")).toHaveText(done.outbound!.text);
  await expect(ending.getByTestId("deal-history-accepted")).toContainText(done.history!.find((h) => h.kind === "accepted")!.text);
  await expect(ending.getByTestId("deal-agreement-receipt")).toBeVisible();
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
  await expect(page.getByTestId("history-step-outcome")).toHaveAttribute("data-tone", "ok");
  await expect(page.getByTestId("outbound-waiting")).toHaveCount(0);
});

test("they countered: refused with no terms, then their reply is a request of its own, and the deal it answered says so", async ({ page }) => {
  await markedSent(page);
  await page.getByTestId("outbound-tile-counter").click();
  const confirm = page.getByTestId("outbound-confirm-counter");
  const box = confirm.getByTestId("outbound-reply-text");
  await expect(box).toHaveAttribute("maxlength", "4000");
  await expect(box).toHaveAttribute("placeholder", waiting.actions!.counter.placeholder_text);
  await expect(confirm).toContainText(waiting.actions!.counter.effect_text);
  await expect(confirm.getByTestId("outbound-confirm")).toBeDisabled();
  await box.fill("Thanks, sounds good.");
  await expect(confirm.getByTestId("outbound-reply-count")).toHaveText("20 of 4000 characters");
  await confirm.getByTestId("outbound-confirm").click();
  await expect(page.getByTestId("outbound-refused")).toHaveText(rec.no_terms.en.message_when);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AWAITING_BUYER");

  await box.fill("We can pay the 420,000 invoice early, but only with a 1.2% discount, and we need 60-day terms on future invoices.");
  await confirm.getByTestId("outbound-confirm").click();
  const reply = rec.buyer_reply.en;
  await expect(page).toHaveURL((url) => url.searchParams.get("decision") === reply.reply_decision_id);
  await expect(page.getByTestId("deal-pane")).toHaveAttribute("data-decision", reply.reply_decision_id);
  await expect(page.getByTestId("deal-reply-arrived")).toHaveText(reply.message_when);

  // The deal it answered: one state, countered, with their words and the way to their new request.
  await page.goto(`/deals?decision=${encodeURIComponent(reply.decision_id)}`);
  const answered = rec.replied.en.decision.outbound!;
  const ending = page.getByTestId("outbound-ending");
  await expect(ending).toHaveAttribute("data-answer", "countered");
  await expect(ending.getByTestId("outbound-ending-title")).toHaveText(answered.title_text);
  await expect(ending.getByTestId("outbound-ending-quote")).toContainText(answered.reply_quote!);
  await expect(ending.getByTestId("outbound-ending-primary")).toHaveText(answered.links[0].label);
  await expect(ending.getByTestId("outbound-ending-primary")).toHaveAttribute("href", answered.links[0].href);
  await expect(page.getByTestId("deal-state-chip")).toHaveText(rec.replied.en.decision.state_text);
});

test("they declined: the reason chips, what is funded instead, then no deal with the reason and the way to Cash", async ({ page }) => {
  await markedSent(page);
  await page.getByTestId("outbound-tile-decline").click();
  const confirm = page.getByTestId("outbound-confirm-decline");
  await expect(confirm).toContainText(waiting.actions!.decline.reasons_label_text);
  await expect(confirm.getByTestId("outbound-reason-NO_REASON").locator("input")).toBeChecked();
  await confirm.getByTestId("outbound-reason-DISCOUNT_TOO_LOW").click();
  await expect(confirm.getByTestId("outbound-reason-DISCOUNT_TOO_LOW").locator("input")).toBeChecked();
  await expect(confirm.getByTestId("outbound-decline-effect")).toHaveText(waiting.actions!.decline.effect_text);
  await confirm.getByTestId("outbound-confirm").click();

  const done = rec.declined.en.decision;
  const ending = page.getByTestId("outbound-ending");
  await expect(ending).toHaveAttribute("data-answer", "declined");
  await expect(ending.getByTestId("outbound-ending-title")).toHaveText(done.outbound!.title_text);
  await expect(ending.getByTestId("outbound-ending-reason")).toHaveText(done.outbound!.reason_text!);
  await expect(ending.getByTestId("outbound-ending-primary")).toHaveText(done.outbound!.links[0].label);
  await expect(ending.getByTestId("deal-history-declined")).toContainText(done.history!.find((h) => h.kind === "declined")!.text);
  await expect(page.getByTestId("deal-state-chip")).toHaveText(done.state_text);
  await expect(page.getByTestId("history-step-answer")).toContainText("Declined");
  await expect(page.getByTestId("history-step-outcome")).toContainText("No deal");
  await scan(page, "declined");
});

test("no answer: once the clock passes the day the offer was open until, it closes as no deal on its own", async ({ page }) => {
  await markedSent(page);
  const decision = await page.getByTestId("deal-pane").getAttribute("data-decision");
  await page.goto("/demo");
  await openOperatorTools(page);
  await page.getByTestId("home-days").fill(String(waiting.closes.day + 1));
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText(`Day ${waiting.closes.day + 1}`);
  await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "business" })));
  await page.goto(`/deals?decision=${encodeURIComponent(decision!)}`);

  const done = rec.no_answer.en.decision;
  const ending = page.getByTestId("outbound-ending");
  await expect(ending).toHaveAttribute("data-answer", "no_answer");
  await expect(ending.getByTestId("outbound-ending-title")).toHaveText(done.outbound!.title_text);
  await expect(ending.getByTestId("outbound-ending-text")).toHaveText(done.outbound!.text);
  await expect(ending.getByTestId("deal-history-no_answer")).toContainText(done.history!.find((h) => h.kind === "no_answer")!.text);
  await expect(page.getByTestId("deal-state-chip")).toHaveText(done.state_text);
  await expect(page.getByTestId("outbound-waiting")).toHaveCount(0);
});

test("Demo mode: the simulated send is a dashed Demo-only row under the cards; a buyer with no simulated reply is refused in the server's words", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "demo" })));
  await messagePanel(page);
  const demo = page.getByTestId("deal-demo-send");
  await expect(demo).toContainText("Demo only");
  await expect(demo.getByTestId("deal-send")).toBeVisible();
  await page.evaluate(() => sessionStorage.setItem("tl-mock-no-simulated-buyer", "1"));
  await demo.getByTestId("deal-send").click();
  const refused = page.getByTestId("deal-no-simulated-buyer");
  await expect(refused).toContainText(rec.no_simulated_buyer.en.message_when!);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
  await refused.getByTestId("deal-to-message").click();
  await expect(page.getByTestId("buyer-message")).toBeFocused();
});

test("the page in Chinese: the panel's words, the waiting state and its answers are the server's Chinese", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  const panel = await messagePanel(page);
  const zh = rec.message[COUNTER as keyof typeof rec.message].zh;
  await expect(panel.getByRole("heading", { name: zh.zh.send_title_text })).toBeVisible();
  await expect(panel.getByTestId("buyer-message-notice")).toHaveText(zh.zh.notice_text);
  // The buyer's language starts at the page's; the owner can still pick English, and the words stay Chinese.
  await expect(panel.getByTestId("buyer-message-text")).toHaveText(zh.zh.text!);
  await panel.getByTestId("buyer-message-lang").getByText(zh.zh.languages![0].label).click();
  await expect(panel.getByTestId("buyer-message-text")).toHaveText(zh.en.text!);
  await expect(panel.getByTestId("buyer-message-notice")).toHaveText(zh.en.notice_text);
  await panel.getByTestId("buyer-message-mark-sent").click();
  await expect(page.getByTestId("deal-marked-sent")).toHaveText(rec.offered.zh.message_when);
  await expect(page.getByTestId("deal-state-chip")).toHaveText(rec.awaiting.zh.decision.state_text);
  await expect(page.getByTestId("outbound-answer")).toContainText(rec.awaiting.zh.decision.outbound!.actions!.question_text);
});
