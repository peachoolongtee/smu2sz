// The live transport's one retry of a write that lost a race (lib/live/retry.ts). Run: pnpm test:unit
import assert from "node:assert/strict";
import test from "node:test";
import { BOOKS_BUSY, isWriteConflictDetail, retryWaitMs, sendWriteWithRetry } from "../lib/live/retry.ts";

const conflict = (extra = {}, headers = { "Retry-After": "1" }) =>
  new Response(JSON.stringify({ detail: { code: "CONCURRENT_WRITE_CONFLICT", message: "busy", retry: true, retry_after_seconds: 1, ...extra } }), { status: 409, headers });
const ok = () => new Response(JSON.stringify({ ok: true }), { status: 200 });

function sender(...answers) {
  const calls = { n: 0 };
  const send = async () => {
    const next = answers[Math.min(calls.n, answers.length - 1)];
    calls.n += 1;
    return next();
  };
  return { send, calls };
}

test("a conflict is retried once after the hint, and the second answer is returned", async () => {
  const waits = [];
  const { send, calls } = sender(conflict, ok);
  const res = await sendWriteWithRetry(send, async (ms) => void waits.push(ms));
  assert.equal(res.status, 200);
  assert.equal(calls.n, 2);
  assert.deepEqual(waits, [1000]);
});

test("a second conflict is returned as it is: no third attempt", async () => {
  const waits = [];
  const { send, calls } = sender(conflict);
  const res = await sendWriteWithRetry(send, async (ms) => void waits.push(ms));
  assert.equal(res.status, 409);
  assert.equal(calls.n, 2);
  assert.equal(waits.length, 1);
  assert.equal(isWriteConflictDetail((await res.json()).detail), true);
});

test("another 409 (already decided, alert changed) and other statuses are not retried", async () => {
  for (const make of [
    () => new Response(JSON.stringify({ detail: { code: "ALERT_CHANGED" } }), { status: 409 }),
    () => new Response(JSON.stringify({ detail: "Approval APR-1 is already APPROVED." }), { status: 409 }),
    () => new Response("not json", { status: 409 }),
    () => new Response(JSON.stringify({ detail: "boom" }), { status: 500 }),
    ok,
  ]) {
    const { send, calls } = sender(make);
    const res = await sendWriteWithRetry(send, async () => assert.fail("must not wait"));
    assert.equal(calls.n, 1);
    assert.equal(res.status, make().status);
  }
});

test("the first answer body stays readable by the caller", async () => {
  const { send } = sender(() => new Response(JSON.stringify({ detail: { code: "ALERT_CHANGED" } }), { status: 409 }));
  const res = await sendWriteWithRetry(send, async () => {});
  assert.equal((await res.json()).detail.code, "ALERT_CHANGED");
});

test("the wait follows the hint in the body, then the header, defaults to one second and is capped", () => {
  assert.equal(retryWaitMs({ retry_after_seconds: 2 }, "1"), 2000);
  assert.equal(retryWaitMs({}, "3"), 3000);
  assert.equal(retryWaitMs(undefined, null), 1000);
  assert.equal(retryWaitMs({ retry_after_seconds: "x" }, "soon"), 1000);
  assert.equal(retryWaitMs({ retry_after_seconds: 600 }, null), 5000);
});

test("the error text says the books were busy", () => {
  assert.match(BOOKS_BUSY, /books were busy/);
});
