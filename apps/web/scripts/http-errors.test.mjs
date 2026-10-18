// What the live transport makes of a failed request (lib/live/http.ts). Run: pnpm test:unit
// A crash on the server is a server error with its status, never "Cannot reach the API": the Cash page said the API was unreachable while
// it was running, because a 500 had no CORS headers and every fetch rejection was read as unreachable (fix/cash-unreachable).
import assert from "node:assert/strict";
import test from "node:test";
import { ApiError } from "../lib/errors.ts";
import { http } from "../lib/live/http.ts";

const realFetch = globalThis.fetch;
function answer(fn) {
  globalThis.fetch = async () => fn();
}
test.afterEach(() => {
  globalThis.fetch = realFetch;
});

async function failure(promise) {
  try {
    await promise;
  } catch (e) {
    return e;
  }
  assert.fail("the request should have failed");
}

test("the API's INTERNAL_ERROR 500 is a server error with its status, not unreachable", async () => {
  answer(() => new Response(JSON.stringify({ detail: { code: "INTERNAL_ERROR", message: "The service hit an error and could not answer." } }), { status: 500 }));
  const e = await failure(http("POST", "/router/plan", { body: {} }));
  assert.ok(e instanceof ApiError);
  assert.equal(e.status, 500);
  assert.equal(e.code, "server_error");
  assert.deepEqual(e.vars, { status: 500 });
  assert.match(e.message, /The service hit an error/);
});

test("a 500 with no words of its own (plain text) is a server error too", async () => {
  answer(() => new Response("Internal Server Error", { status: 500, statusText: "Internal Server Error" }));
  const e = await failure(http("GET", "/home?lang=en"));
  assert.equal(e.status, 500);
  assert.equal(e.code, "server_error");
});

test("a 5xx that explains itself keeps the server's words", async () => {
  answer(() => new Response(JSON.stringify({ detail: { code: "SETUP_FAILED", message: "Opening the books failed; the blank books are back." } }), { status: 500 }));
  const e = await failure(http("GET", "/setup/status"));
  assert.equal(e.status, 500);
  assert.equal(e.code, undefined);
  assert.equal(e.message, "Opening the books failed; the blank books are back.");
});

test("only a request that never got an answer is unreachable", async () => {
  answer(() => {
    throw new TypeError("Failed to fetch");
  });
  const e = await failure(http("GET", "/home?lang=en"));
  assert.equal(e.status, 0);
  assert.equal(e.code, "unreachable");
});
