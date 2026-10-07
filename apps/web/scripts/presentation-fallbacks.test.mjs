// The labels a page chooses when an older recording lacks the server's `status` or `business_action`
// (lib/presentation-fallbacks.ts). Run: pnpm test:unit
import assert from "node:assert/strict";
import test from "node:test";
import { businessAction, statusOf } from "../lib/presentation-fallbacks.ts";

test("the server's status wins over anything derived", () => {
  assert.equal(statusOf({ status: "blocked", result: "ADMISSIBLE", selected: true }), "blocked");
  assert.equal(statusOf({ status: "alternative", result: "SELECTED" }), "alternative");
});

test("without a status, a row that is not admissible is insufficient when it breaks the reserve, else unavailable", () => {
  assert.equal(statusOf({ result: "NOT_ADMISSIBLE", breach_day: 12 }), "insufficient");
  assert.equal(statusOf({ result: "NOT_ADMISSIBLE", breach_day: 0 }), "insufficient");
  assert.equal(statusOf({ result: "NOT_ADMISSIBLE", breach_day: null }), "unavailable");
  assert.equal(statusOf({ result: "NOT_ADMISSIBLE" }), "unavailable");
});

test("without a status, the selected row is recommended and an admissible one is an alternative", () => {
  assert.equal(statusOf({ result: "SELECTED" }), "recommended");
  assert.equal(statusOf({ selected: true }), "recommended");
  assert.equal(statusOf({ result: "ADMISSIBLE" }), "alternative");
  assert.equal(statusOf({}), "alternative");
});

test("the server's business action wins; an older verdict gets the rule from its outcome and counters", () => {
  assert.equal(businessAction({ business_action: "needs_owner", outcome: "ACCEPT", counters: [] }), "needs_owner");
  assert.equal(businessAction({ outcome: "ACCEPT", counters: [] }), "accept");
  assert.equal(businessAction({ outcome: "COUNTER", counters: [{}] }), "counter");
  assert.equal(businessAction({ outcome: "REJECT", counters: [{}, {}] }), "counter");
  assert.equal(businessAction({ outcome: "REJECT", counters: [] }), "decline");
  assert.equal(businessAction({ outcome: "NEEDS_OWNER_APPROVAL", counters: [] }), "needs_owner");
  assert.equal(businessAction({ outcome: "NO_VERDICT", counters: [] }), "cannot");
  assert.equal(businessAction({ outcome: "NO_DEAL", counters: [] }), "cannot");
});
