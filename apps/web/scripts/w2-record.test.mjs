// Wave 2 (map #65): the durable decision record on the web. The deal's steps follow the record's state only, the execution summary is read
// from the record, a 409 COUNTER_CHANGED is recognised, and the recorded snapshots say what the screens depend on. Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { ApiError } from "../lib/errors.ts";
import { counterChanged, dealProgress, dealRecordId, decisionMissing } from "../lib/decision.ts";
import { agreementState, summaryFromRecord } from "../lib/execution-summary.ts";

const snaps = JSON.parse(readFileSync(fileURLToPath(new URL("../mocks/decisions.json", import.meta.url)), "utf8"));
const stories = JSON.parse(readFileSync(fileURLToPath(new URL("../mocks/w2_counter_changed.json", import.meta.url)), "utf8"));
const en = (name) => snaps[name].en;

test("a deal's record id is deal:{offer_id}", () => {
  assert.equal(dealRecordId("OFF-1"), "deal:OFF-1");
});

test("the steps: a response that is ready is not sent, and an acceptable offer is not agreed", () => {
  const ready = dealProgress("RESPONSE_READY");
  assert.deepEqual([ready.done, ready.reached], [3, false]);
  // The recorded EX01 offer that would be ACCEPT at Tier 1 reads "Acceptable, awaiting agreement" and the line has not reached an outcome.
  assert.equal(en("ready.accept").state, "RESPONSE_READY");
  assert.equal(en("ready.accept").state_text, "Acceptable, awaiting agreement");
  assert.equal(en("ready.accept").evaluation.outcome, "ACCEPT");
  assert.equal(dealProgress(en("ready.accept").state).reached, false);
});

test("the steps: each record state has its own place and tone", () => {
  assert.deepEqual(dealProgress("RECEIVED"), { done: 1, reached: false, tone: "open", stalled: false });
  assert.equal(dealProgress("NEEDS_CLARIFICATION").stalled, true);
  for (const s of ["AGREED", "FULFILLED"]) assert.deepEqual([dealProgress(s).reached, dealProgress(s).tone], [true, "good"]);
  for (const s of ["EXPIRED", "REVOKED", "NO_DEAL", "DECLINED"]) assert.equal(dealProgress(s).tone, "closed");
  for (const s of ["MISSED", "FAILED"]) assert.equal(dealProgress(s).tone, "bad");
  assert.equal(dealProgress("AUTHORIZATION_REQUIRED").tone, "open");
  // Only an agreement in force is "good": an expired or missed deal is never shown as agreed.
  assert.notEqual(dealProgress("EXPIRED").tone, "good");
  assert.notEqual(dealProgress("MISSED").tone, "good");
});

test("the steps follow the recorded story: agreed on day 0, fulfilled with the receipt, missed without it, no deal when the buyer walks", () => {
  assert.deepEqual([en("agreed_day0.ex01").state, en("agreed_day0.ex01").state_text], ["AGREED", "Agreed"]);
  assert.equal(en("fulfilled_day34.ex01").state, "FULFILLED");
  assert.equal(en("noreceipt_day34.ex01").state_text, "Early payment did not arrive");
  // The commitment lapsed (F06): the record says what the owner needs to read, never "Agreed".
  assert.equal(en("noreceipt_day34.ex01").agreement.status, "EXPIRED");
  assert.equal(en("noreceipt_day34.ex01").agreement.status_text, "Early payment did not arrive");
  assert.equal(en("nodeal.ex01").state, "NO_DEAL");
  assert.equal(en("nodeal.ex01").agreement, null);
  assert.equal(en("received.ex01").state, "RECEIVED");
});

test("the execution summary is read from the record: the agreement in the server's words, the funding it ran, the lots", () => {
  const agreed = summaryFromRecord(en("agreed_day0.ex01"));
  assert.equal(agreed.agreement, "agreed");
  assert.equal(agreed.agreement_text, "Agreed");
  assert.match(agreed.summary_text, /Agreement with .* recorded\. Funding of ¥147,210\.00 was requested and has landed\./);
  assert.ok(agreed.funding.some((f) => f.text.includes("¥147,210.00")));
  assert.equal(agreed.lots.length, 1);
  assert.equal(agreed.lots[0].landed, true);
  // A buyer who walked: no agreement, and the funding that ran anyway is listed.
  const walked = summaryFromRecord(en("nodeal.ex01"));
  assert.equal(walked.agreement, "none");
  assert.equal(walked.agreement_text, null);
  assert.ok(walked.funding.length >= 1);
  // Evaluation alone has done nothing, so there is no summary.
  assert.equal(summaryFromRecord(en("ready.ex01")), null);
  assert.equal(summaryFromRecord(en("received.ex01")), null);
});

test("the agreement tone follows the commitment status, never the verdict", () => {
  assert.equal(agreementState(en("fulfilled_day34.ex01").agreement.status), "settled");
  assert.equal(agreementState("EXPIRED"), "expired");
  assert.equal(agreementState(null), "none");
});

test("a 409 COUNTER_CHANGED is recognised with its counters or its re-evaluate flag; other errors are not", () => {
  const replaced = counterChanged(new ApiError(409, "m", stories.replaced));
  assert.equal(replaced.code, "COUNTER_CHANGED");
  assert.equal(replaced.reevaluate, false);
  assert.ok(replaced.counters.length >= 1 && replaced.counters.every((c) => c.send_scope));
  const moved = counterChanged(new ApiError(409, "m", stories.moved));
  assert.equal(moved.reevaluate, true);
  assert.deepEqual(moved.counters, []);
  assert.equal(counterChanged(new ApiError(409, "m", { code: "ALERT_CHANGED" })), null);
  assert.equal(counterChanged(new ApiError(404, "m", stories.moved)), null);
  assert.equal(counterChanged(new Error("x")), null);
});

test("a 404 DECISION_NOT_FOUND is a missing record, not a failure", () => {
  assert.equal(decisionMissing(new ApiError(404, "m", { code: "DECISION_NOT_FOUND", decision_id: "x" })), true);
  assert.equal(decisionMissing(new ApiError(404, "m", undefined, "offer_missing")), false);
  assert.equal(decisionMissing(new ApiError(500, "m")), false);
});

test("the recorded refused cure is FAILED and the stored quote survives the decision", () => {
  assert.equal(en("cure_failed").state, "FAILED");
  assert.equal(en("cure_approved").quote.recorded, true);
  assert.ok(en("cure_approved").quote.lines.length >= 1);
  assert.ok(Array.isArray(en("cure_approved").quote.actual));
  assert.equal(en("cure_pending").quote.recorded, true, "the price the owner was quoted is on the record before the decision too");
});
