import assert from "node:assert/strict";
import { test } from "node:test";
import { DEFAULT_TIMEOUT_MS, kindOf, LONG_TIMEOUT_MS, runWithTimeout, timeoutFor } from "../lib/live/timeout.ts";

test("every route has a timeout: 20 s by default, 60 s for the model, the evaluation and the strategy reads", () => {
  assert.equal(timeoutFor("/home?lang=en"), DEFAULT_TIMEOUT_MS);
  assert.equal(timeoutFor("/approvals/queue"), DEFAULT_TIMEOUT_MS);
  for (const p of ["/nl", "/nl/opener", "/offers/OFF-1/evaluate?lang=zh", "/cash/price-curve?lang=en", "/receivables/worth", "/buyers/BUYER-1/envelope?zone=1"]) {
    assert.equal(timeoutFor(p), LONG_TIMEOUT_MS, p);
  }
  assert.equal(timeoutFor("/nl", 500), 500, "the test build's override wins");
});

test("a timed-out request is a read, a write that may have landed, or a model reply", () => {
  assert.equal(kindOf("GET", "/home"), "read");
  assert.equal(kindOf("POST", "/router/plan"), "read");
  assert.equal(kindOf("POST", "/offers/OFF-1/evaluate"), "read");
  assert.equal(kindOf("POST", "/nl"), "reply");
  for (const p of ["/alerts/ALERT-1/act", "/approvals/APR-000001", "/negotiate/OFF-1", "/offers", "/capex/apply", "/clock/advance", "/demo/reset"]) {
    assert.equal(kindOf("POST", p), "write", p);
  }
});

test("the signal fires after the time and the failure becomes the timeout error", async () => {
  const mark = new Error("timeout");
  const started = Date.now();
  await assert.rejects(
    runWithTimeout((signal) => new Promise((_, reject) => signal.addEventListener("abort", () => reject(new Error("aborted")))), 40, () => mark),
    (e) => e === mark,
  );
  assert.ok(Date.now() - started >= 35);
});

test("a request that finishes in time is returned, and one that fails in time keeps its own error", async () => {
  assert.equal(await runWithTimeout(async () => 7, 1000, () => new Error("late")), 7);
  const own = new Error("refused");
  await assert.rejects(runWithTimeout(async () => { throw own; }, 1000, () => new Error("late")), (e) => e === own);
});
