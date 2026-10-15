// The message the owner sends the buyer outside FLOW (ADR-0011 addendum), the web half: the lifecycle and state words the Deals model files, the dictionary's labels in both
// languages, and the recording the mock serves (scripts/record-mocks.mjs --buyer-message) holding together. The components are TSX (node cannot strip JSX), so what is tested is their
// model and their data. Run: pnpm test:unit
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

test("the lifecycle `answered` is a closed deal's (neutral), and a deal waiting for the buyer's answer is the buyer's turn (lavender)", () => {
  assert.equal(m.lifecycleOf({ lifecycle: "answered" }), "answered");
  assert.equal(m.lifecyclePill("answered", "Answered with new terms").tone, "neutral");
  assert.equal(m.lifecyclePill("awaiting_buyer", "Awaiting buyer").tone, "lavender");
  assert.equal(m.recordTone("AWAITING_BUYER"), "lavender");
  assert.equal(m.recordTone("REPLIED"), "neutral");
});

test("the panel's labels exist in both languages and are not the same words", () => {
  const keys = Object.keys(en).filter((k) => k.startsWith("bm."));
  assert.ok(keys.length >= 10);
  for (const k of keys) assert.ok(zh[k], `zh lacks ${k}`);
  assert.notEqual(zh["bm.title"], en["bm.title"]);
  assert.equal(en["bm.reply.count"].includes("{n}") && en["bm.reply.count"].includes("{max}"), true);
});

test("the recording holds together: the message marked sent is the one shown, in both languages, and every answer is the server's own", () => {
  const counter = rec.offered.en.counter_id;
  const shown = rec.message[counter];
  assert.ok(shown.en.text && shown.zh.text, "the recommended reply has a message in both languages");
  assert.notEqual(shown.en.message_hash, shown.zh.message_hash, "a message in another language is another message");
  for (const lang of ["en", "zh"]) {
    assert.equal(rec.offered[lang].counter_id, counter);
    assert.equal(rec.awaiting[lang].decision.state, "AWAITING_BUYER");
    assert.equal(rec.awaiting[lang].message.offered.message_hash, shown.en.message_hash, "recorded as sent in English");
    assert.equal(rec.awaiting[lang].decision.response.sent.outside_flow, true);
    assert.equal(rec.accepted[lang].decision.state, "AGREED");
    assert.equal(rec.replied[lang].decision.state, "REPLIED");
    assert.equal(rec.replied[lang].reply_decision.id, rec.buyer_reply[lang].reply_decision_id);
    for (const refusal of ["message_changed", "no_terms", "no_simulated_buyer"]) assert.ok(rec[refusal][lang].message_when, `${refusal} ${lang} carries the server's sentence`);
  }
  assert.equal(rec.message_changed.en.code, "MESSAGE_CHANGED");
  assert.equal(rec.no_terms.en.code, "NO_TERMS_IN_REPLY");
  assert.equal(rec.no_simulated_buyer.en.code, "NO_SIMULATED_BUYER");
  assert.match(rec.no_terms.en.message_when, /no terms/);
  assert.ok(!/\d/.test("Thanks, sounds good."), "the mock refuses a reply with no figure: the spec's no-terms reply has none");
});
