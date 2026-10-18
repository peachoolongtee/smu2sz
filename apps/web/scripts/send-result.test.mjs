// FUND-2 (round eight): the send result says "the agreement is on your books" only when the accept executed. A buyer's yes whose
// agreement waits for the owner's approval, or was refused, is told in the server's own words (or the web's fallback), never as
// recorded. Run: pnpm test:unit
import assert from "node:assert/strict";
import { register } from "node:module";
import test from "node:test";

register("./ts-resolve-hook.mjs", import.meta.url);
const { sendResultHead } = await import("../lib/send-result.ts");
const { en, zh } = await import("../lib/dictionary.ts");

const rounds = [{ round: 1, counter_id: "CTR-1", counter_label: "Option A", counter_label_when: "Option A", buyer_response: "ACCEPT", buyer_text: "ok" }];
const base = { offer_id: "OFF-1", outcome: "DEAL", rounds, accepted_counter_id: "CTR-1", commitment: null, operations: [], plan: null, message: "m" };
const text = (head, dict) => (head.text !== null ? head.text : dict[head.key].replace("{counter}", head.vars.counter));

test("an accept that executed (or an older recording without accept_status) says the agreement is on the books", () => {
  for (const n of [{ ...base, accept_status: "EXECUTED" }, { ...base }]) {
    const head = sendResultHead(n);
    assert.equal(head.key, "biz.deals.dealDone");
    assert.equal(text(head, en), "The buyer accepted Option A. The agreement is on your books.");
  }
});

test("an accept waiting for the owner's approval never says the agreement is on the books", () => {
  const waits = "Option A was accepted by the buyer; the agreement waits for your approval; the remaining gap is not funded until you approve.";
  const served = sendResultHead({ ...base, accept_status: "PENDING_APPROVAL", message_when: waits });
  assert.equal(served.text, waits, "the server's own words when it sent them");
  assert.equal(served.tone, "waiting");
  const fallback = sendResultHead({ ...base, accept_status: "PENDING_APPROVAL" });
  assert.equal(fallback.key, "biz.deals.dealWaits");
  for (const dict of [en, zh]) {
    const said = text(fallback, dict);
    assert.ok(!said.includes(en["biz.deals.dealDone"].split(". ")[1]) && !said.includes("协议已记入您的账目"), said);
  }
  assert.equal(text(fallback, en), "The buyer accepted Option A. The agreement waits for your approval; it is not on your books yet.");
  assert.equal(text(fallback, zh), "买方接受了Option A。协议正在等待您批准，尚未记入您的账目。");
});

test("a refused accept says the agreement was not recorded", () => {
  const refused = "Option A was accepted by the buyer, but the agreement was not recorded: the facility has no headroom for this amount; the remaining gap is not funded.";
  const served = sendResultHead({ ...base, accept_status: "REFUSED", message_when: refused });
  assert.equal(served.text, refused);
  assert.equal(served.tone, "refused");
  const fallback = sendResultHead({ ...base, accept_status: "REFUSED", message_when: null });
  assert.equal(fallback.key, "biz.deals.dealNotRecorded");
  assert.equal(text(fallback, en), "The buyer accepted Option A, but the agreement was not recorded.");
  assert.equal(text(fallback, zh), "买方接受了Option A，但协议未被记录。");
});

test("no deal is still no deal", () => {
  const head = sendResultHead({ ...base, outcome: "NO_DEAL", accepted_counter_id: null, accept_status: null, rounds: [{ ...rounds[0], buyer_response: "REFUSE" }] });
  assert.equal(head.key, "biz.deals.noDeal");
  assert.equal(head.text, null);
});

test("the new words are in both languages", () => {
  for (const k of ["biz.deals.dealWaits", "biz.deals.dealNotRecorded"]) {
    assert.ok(en[k], `en ${k}`);
    assert.ok(zh[k], `zh ${k}`);
  }
});
