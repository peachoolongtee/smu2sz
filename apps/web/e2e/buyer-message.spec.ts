import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import rec from "../mocks/buyer_message.json";
import { expect, test } from "./fixtures";
import { checkedDeal, openReview } from "./helpers";

/**
 * The message the owner sends the buyer outside FLOW (ADR-0011 addendum, phase 3): FLOW transmits nothing. In the send review, the message FLOW prepared for the reply, in the buyer's
 * language; the owner copies it, sends it themself and marks it sent; the deal then waits for the buyer, whose yes the owner records (the agreement, with its receipt) or whose reply the
 * owner pastes (a request of its own). Mock mode, on the API's own recordings (scripts/record-mocks.mjs --buyer-message): every sentence below is the server's, read from that file.
 * The test hooks are sessionStorage keys, as the other tl-mock-* ones:
 *   tl-mock-message-changed = 1     the next mark is refused with the recorded 409 MESSAGE_CHANGED
 *   tl-mock-no-simulated-buyer = 1  the next simulated send is refused with the recorded 409 NO_SIMULATED_BUYER
 */

const COUNTER = rec.offered.en.counter_id;
const before = rec.message[COUNTER as keyof typeof rec.message];
/** The waiting deal's row in the queue: the deal's pill is the server's lifecycle word on it. */
const waitingRow = (lang: "en" | "zh") => rec.awaiting[lang].worklist.waiting.find((r) => r.key === `buyer-reply:${rec.offered.en.offer_id}`)!;
/** What the clipboard holds, with the platform's line endings read as the message's own. */
const clipboard = (page: Page) => page.evaluate(() => navigator.clipboard.readText()).then((t) => t.replace(/\r\n/g, "\n"));

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
}

test("copy: the message for this reply in the buyer's language, beside the server's notice, how the request arrived and the day it is open until", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const panel = await messagePanel(page);
  await expect(panel.getByRole("heading", { name: "Message to the buyer" })).toBeVisible();
  await expect(panel.getByTestId("buyer-message-notice")).toHaveText(before.en.notice_text);
  await expect(panel.getByTestId("buyer-message-provenance")).toHaveText(before.en.provenance.text);
  await expect(panel.getByTestId("buyer-message-until")).toContainText(before.en.valid_until_date);
  await expect(panel.getByTestId("buyer-message-text")).toHaveText(before.en.text!);
  await expect(panel.getByTestId("buyer-message-copy")).toHaveText(before.en.copy_label);
  await expect(panel.getByTestId("buyer-message-mark-sent")).toHaveText(before.en.mark_sent_label);
  await panel.getByTestId("buyer-message-copy").click();
  await expect(panel.getByTestId("buyer-message-copy-status")).toHaveText("Copied");
  expect(await clipboard(page)).toBe(before.en.text);

  // The buyer's language, not the page's: the message is in Chinese, every word around it stays in English; what was copied is another message, so the status clears.
  await panel.getByTestId("buyer-message-lang").getByText("中文").click();
  await expect(panel.getByTestId("buyer-message-text")).toHaveAttribute("data-lang", "zh");
  await expect(panel.getByTestId("buyer-message-text")).toHaveText(before.zh.text!);
  await expect(panel.getByTestId("buyer-message-copy-status")).toHaveText("");
  await expect(panel.getByTestId("buyer-message-notice")).toHaveText(before.en.notice_text);
  await panel.getByTestId("buyer-message-copy").click();
  expect(await clipboard(page)).toBe(before.zh.text);
  // Copying records nothing: the deal is still the owner's to answer.
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
  await scan(page, "send review with the message");
});

test("mark sent: refused when the message changed (nothing recorded), then recorded, and the deal waits for the buyer", async ({ page }) => {
  const panel = await messagePanel(page);
  await page.evaluate(() => sessionStorage.setItem("tl-mock-message-changed", "1"));
  await panel.getByTestId("buyer-message-mark-sent").click();
  await expect(panel.getByTestId("buyer-message-refused")).toHaveText(rec.message_changed.en.message_when);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");

  await panel.getByTestId("buyer-message-mark-sent").click();
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AWAITING_BUYER");
  await expect(page.getByTestId("deal-state-chip")).toHaveText(waitingRow("en").status_text);
  await expect(page.getByTestId("deal-marked-sent-when")).toHaveText(rec.offered.en.message_when);
  await expect(page.getByTestId("deal-marked-sent-effect")).toHaveText(rec.offered.en.mark_sent_effect_text);
  // The review is gone (nothing more to send) and the record says what it waits for, with the two ways to record the buyer's answer.
  await expect(page.getByTestId("queue-review")).toHaveCount(0);
  await expect(page.locator('[data-testid="deal-review-slot"] .flow-card')).toHaveCount(0);
  await expect(page.getByTestId("deal-waiting")).toHaveText(rec.awaiting.en.decision.waiting_for.text);
  const sent = rec.awaiting.en.decision.response.sent as { text: string };
  await expect(page.getByTestId("deal-sent-outside")).toHaveText(sent.text);
  await expect(page.getByTestId("buyer-accepted-open")).toHaveText(rec.awaiting.en.message.accepted_label);
  await expect(page.getByTestId("buyer-reply-open")).toHaveText(rec.awaiting.en.message.reply_label);
  await scan(page, "awaiting the buyer");

  // The decision record says the counter went out outside FLOW, not that it was not recorded.
  await page.getByTestId("deal-record-link").click();
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "AWAITING_BUYER");
  await expect(page.getByTestId("record-sent-outside")).toHaveText(sent.text);
  await expect(page.getByTestId("record-sent")).not.toContainText("was not recorded");
});

test("buyer accepted: a review of the message that was sent, then the agreement with its receipt", async ({ page }) => {
  await markedSent(page);
  await page.getByTestId("buyer-accepted-open").click();
  const review = page.getByTestId("buyer-accepted-review");
  await expect(review.getByRole("heading", { name: "Record the buyer's yes" })).toBeVisible();
  await expect(review.getByTestId("buyer-accepted-message")).toHaveText(before.en.text!);
  await expect(review.getByTestId("buyer-accepted-until")).toContainText(rec.awaiting.en.message.offered!.valid_until_when);
  // Not now leaves the deal as it was.
  await review.getByTestId("buyer-answer-cancel").click();
  await expect(page.getByTestId("buyer-accepted-review")).toHaveCount(0);
  await page.getByTestId("buyer-accepted-open").click();
  await page.getByTestId("buyer-accepted-confirm").click();

  const result = page.getByTestId("deal-buyer-accepted");
  await expect(result).toHaveAttribute("data-status", rec.buyer_accepted.en.status);
  await expect(result).toContainText(rec.buyer_accepted.en.decision.state_text);
  await expect(page.getByTestId("deal-buyer-accepted-ran")).toHaveText(rec.buyer_accepted.en.execution.summary_text);
  await expect(page.getByTestId("deal-buyer-accepted-receipt")).toContainText(rec.buyer_accepted.en.receipt!.authority_text!);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
  await expect(page.getByTestId("buyer-answer")).toHaveCount(0);
});

test("the buyer's reply: refused when it holds no terms, then read as a request of its own, which the page opens", async ({ page }) => {
  await markedSent(page);
  await page.getByTestId("buyer-reply-open").click();
  const form = page.getByTestId("buyer-reply-form");
  const box = form.getByTestId("buyer-reply-text");
  await expect(box).toHaveAttribute("maxlength", "4000");
  await expect(form.getByTestId("buyer-reply-submit")).toBeDisabled();
  await box.fill("Thanks, sounds good.");
  await expect(form.getByTestId("buyer-reply-count")).toHaveText("20 of 4000 characters");
  await form.getByTestId("buyer-reply-submit").click();
  await expect(page.getByTestId("buyer-answer-refused")).toHaveText(rec.no_terms.en.message_when);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AWAITING_BUYER");

  await box.fill("We can pay the 420,000 invoice early, but only with a 1.2% discount, and we need 60-day terms on future invoices.");
  await form.getByTestId("buyer-reply-submit").click();
  const reply = rec.buyer_reply.en;
  await expect(page).toHaveURL((url) => url.searchParams.get("decision") === reply.reply_decision_id);
  await expect(page.getByTestId("deal-pane")).toHaveAttribute("data-decision", reply.reply_decision_id);
  await expect(page.getByTestId("deal-reply-arrived")).toHaveText(reply.message_when);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", rec.replied.en.reply_decision.state);

  // The deal it answered is closed as answered, in the server's words.
  await page.goto(`/decisions/${encodeURIComponent(reply.decision_id)}`);
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "REPLIED");
  await expect(page.getByTestId("record-state")).toContainText(rec.replied.en.decision.state_text);
});

test("a buyer with no simulated reply: the simulated send is refused in the server's words, with the way to the message", async ({ page }) => {
  await messagePanel(page);
  await page.evaluate(() => sessionStorage.setItem("tl-mock-no-simulated-buyer", "1"));
  await page.getByTestId("deal-send").click();
  const refused = page.getByTestId("deal-no-simulated-buyer");
  await expect(refused).toContainText(rec.no_simulated_buyer.en.message_when!);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
  await refused.getByTestId("deal-to-message").click();
  await expect(page.getByTestId("buyer-message")).toBeFocused();
});

test("the page in Chinese: the panel's words and the waiting deal are the server's Chinese", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  const panel = await messagePanel(page);
  await expect(panel.getByRole("heading", { name: "发给买方的消息" })).toBeVisible();
  await expect(panel.getByTestId("buyer-message-notice")).toHaveText(before.zh.notice_text);
  // The buyer's language starts at the page's; the owner can still pick English for an English-speaking buyer.
  await expect(panel.getByTestId("buyer-message-text")).toHaveText(before.zh.text!);
  await panel.getByTestId("buyer-message-lang").getByText("English").click();
  await expect(panel.getByTestId("buyer-message-text")).toHaveText(before.en.text!);
  await expect(panel.getByTestId("buyer-message-mark-sent")).toHaveText(before.zh.mark_sent_label);
  await panel.getByTestId("buyer-message-mark-sent").click();
  await expect(page.getByTestId("deal-marked-sent-when")).toHaveText(rec.offered.zh.message_when);
  await expect(page.getByTestId("deal-state-chip")).toHaveText(waitingRow("zh").status_text);
  await expect(page.getByTestId("buyer-accepted-open")).toHaveText(rec.awaiting.zh.message.accepted_label);
});
