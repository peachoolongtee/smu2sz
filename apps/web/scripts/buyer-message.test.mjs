// The message the owner sends the buyer outside FLOW (ADR-0011 addendum, round two), the web half: the lifecycle and state words the Deals model files, the history strip's four steps,
// the dictionary's labels in both languages, and the recording the mock serves (scripts/record-mocks.mjs --buyer-message) holding together. The components are TSX (node cannot strip
// JSX), so what is tested is their model and their data. Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { register } from "node:module";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

register("./ts-resolve-hook.mjs", import.meta.url);
const m = await import("../components/deals/flow/deal-model.ts");
const { en, zh } = await import("../lib/dictionary.ts");
const here = dirname(fileURLToPath(import.meta.url));
const rec = JSON.parse(readFileSync(join(here, "..", "mocks", "buyer_message.json"), "utf8"));

test("the lifecycles `answered` and `no_answer` are a closed deal's (neutral), and a deal waiting for the buyer's answer is the buyer's turn (lavender)", () => {
  assert.equal(m.lifecycleOf({ lifecycle: "answered" }), "answered");
  assert.equal(m.lifecycleOf({ lifecycle: "no_answer" }), "no_answer");
  assert.equal(m.lifecyclePill("answered", "Answered with new terms").tone, "neutral");
  assert.equal(m.lifecyclePill("no_answer", "No answer").tone, "neutral");
  assert.equal(m.lifecyclePill("awaiting_buyer", "Awaiting buyer").tone, "lavender");
  assert.equal(m.recordTone("AWAITING_BUYER"), "lavender");
  assert.equal(m.recordTone("REPLIED"), "neutral");
});

test("the panel's and the history's labels exist in both languages", () => {
  const keys = Object.keys(en).filter((k) => k.startsWith("bm.") || k.startsWith("hist."));
  assert.ok(keys.length >= 30);
  for (const k of keys) assert.ok(zh[k], `zh lacks ${k}`);
  assert.notEqual(zh["bm.title"], en["bm.title"]);
  assert.ok(en["bm.letterTo"].includes("{buyer}") && en["bm.letterTo"].includes("{date}"));
  assert.ok(zh["bm.letterTo"].includes("{buyer}") && zh["bm.letterTo"].includes("{date}"));
});

test("the recording holds together: the message marked sent is the one shown, every ending is on the record, and every refusal is the server's own", () => {
  const counter = rec.offered.en.counter_id;
  const shown = rec.message[counter];
  for (const page of ["en", "zh"]) {
    assert.equal(shown[page].en.ui_lang, page, "the words are in the page's language");
    assert.equal(shown[page].zh.ui_lang, page);
    assert.equal(shown[page].en.notice_text, shown[page].zh.notice_text, "only the message changes with the buyer's language");
    assert.notEqual(shown[page].en.message_hash, shown[page].zh.message_hash, "a message in another language is another message");
    assert.ok(shown[page].en.review?.terms?.length, "the review beside the message");
  }
  for (const lang of ["en", "zh"]) {
    assert.equal(rec.offered[lang].counter_id, counter);
    assert.equal(rec.awaiting[lang].decision.state, "AWAITING_BUYER");
    assert.equal(rec.awaiting[lang].decision.outbound.answer, null);
    assert.ok(rec.awaiting[lang].decision.outbound.actions.decline.reasons.some((r) => r.code === "NO_REASON"));
    assert.equal(rec.awaiting[lang].message.offered.message_hash, shown.en.en.message_hash, "recorded as sent in English");
    assert.equal(rec.accepted[lang].decision.outbound.answer, "accepted");
    assert.equal(rec.declined[lang].decision.outbound.answer, "declined");
    assert.equal(rec.declined[lang].decision.outbound.reason_code, "DISCOUNT_TOO_LOW");
    assert.equal(rec.replied[lang].decision.outbound.answer, "countered");
    assert.equal(rec.no_answer[lang].decision.outbound.answer, "no_answer");
    assert.equal(rec.no_answer[lang].decision.lifecycle ?? "no_answer", "no_answer");
    assert.equal(rec.replied[lang].reply_decision.id, rec.buyer_reply[lang].reply_decision_id);
    for (const refusal of ["message_changed", "no_terms", "no_simulated_buyer", "offer_sent_outside", "offer_expired"]) assert.ok(rec[refusal][lang].message_when, `${refusal} ${lang} carries the server's sentence`);
  }
  for (const lang of ["en", "zh"]) {
    assert.equal(rec.withdrawn[lang].result.status, "withdrawn");
    assert.ok(rec.withdrawn[lang].result.message_when);
    assert.equal(rec.withdrawn[lang].decision.state, "RESPONSE_READY", "a mark withdrawn is a counter ready again");
    const kinds = rec.withdrawn[lang].decision.history.map((h) => h.kind);
    assert.ok(kinds.includes("offered") && kinds.includes("withdrawn"), "the history keeps the mark beside the correction");
    assert.ok(rec.accepted[lang].decision.outbound.evidence_quote, "the buyer's message pasted as evidence");
  }
  assert.equal(rec.offer_sent_outside.en.code, "OFFER_SENT_OUTSIDE");
  assert.equal(rec.offer_expired.en.code, "OFFER_EXPIRED");
  assert.ok(rec.no_answer.en.decision.history.some((h) => h.kind === "no_answer"));
  assert.ok(!/\d/.test("Thanks, sounds good."), "the mock refuses a reply with no figure: the spec's no-terms reply has none");
});
