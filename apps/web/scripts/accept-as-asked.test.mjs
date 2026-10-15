// Accept as asked (map #121), the web half: the server's refusal read from a 409, the link that opens the review on arrival, and the new words in both languages. Run: pnpm test:unit
import assert from "node:assert/strict";
import { register } from "node:module";
import test from "node:test";

register("./ts-resolve-hook.mjs", import.meta.url);
const { acceptRefusal } = await import("../lib/accept.ts");
const { reviewHref } = await import("../lib/selection.ts");
const { ApiError } = await import("../lib/errors.ts");
const { en, zh } = await import("../lib/dictionary.ts");

test("a 409 with a code is the server's refusal: its own sentence in the owner's language, else its message; any other error is not", () => {
  const when = new ApiError(409, "msg", { code: "COUNTER_CHANGED", message: "The request changed.", message_when: "The request changed 2 minutes ago." });
  assert.deepEqual(acceptRefusal(when), { code: "COUNTER_CHANGED", text: "The request changed 2 minutes ago." });
  const plain = new ApiError(409, "msg", { code: "OVER_MANDATE", message: "Over a limit." });
  assert.deepEqual(acceptRefusal(plain), { code: "OVER_MANDATE", text: "Over a limit." });
  assert.equal(acceptRefusal(new ApiError(500, "boom", { code: "X", message: "m" })), null);
  assert.equal(acceptRefusal(new ApiError(409, "no code", { message: "m" })), null);
  assert.equal(acceptRefusal(new Error("network")), null);
});

test("a link to a request that needs review opens the review on arrival; another address, and one that says so already, are left as they are", () => {
  assert.equal(reviewHref("/deals?decision=deal%3AOFF-1"), "/deals?decision=deal%3AOFF-1&review=1");
  assert.equal(reviewHref("/deals"), "/deals?review=1");
  assert.equal(reviewHref("/deals?decision=a&review=1"), "/deals?decision=a&review=1");
  assert.equal(reviewHref("/deals?decision=a#top"), "/deals?decision=a&review=1#top");
  assert.equal(reviewHref("/receivables?invoice=RCV-1"), "/receivables?invoice=RCV-1");
});

test("the words the web adds are in both languages; the decline's one line and the empty workspace say what the owner asked", () => {
  for (const k of ["accept.review", "accept.review.close", "deals.review.cash", "accept.review.region", "accept.reading", "accept.terms", "accept.decline.confirm", "receipt.title.accept", "deals.select.body", "deals.select.body.above"]) {
    assert.ok(en[k], `en ${k}`);
    assert.ok(zh[k], `zh ${k}`);
  }
  assert.equal(en["accept.decline.confirm"], "Nothing moves; the request closes.");
  assert.equal(en["deals.select.body"], "Choose a request on the left to review it here");
  assert.equal(en["accept.review"], "Review the request");
  assert.equal(zh["accept.review.close"], "暂不决定");
  assert.equal(en["deals.review.cash"], "What it does to your cash");
});
