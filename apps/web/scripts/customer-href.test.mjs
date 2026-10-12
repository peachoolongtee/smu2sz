// Ticket #108: the one helper every customer name uses, and the recording the mock overview serves. The recording is the API's own answer
// (scripts/record-mocks.mjs --overview); nothing here edits it.
// Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { contextQuery, customerHref, fromCustomer, readContext } from "../lib/customer-href.ts";
import { en, zh } from "../lib/dictionary.ts";

const here = dirname(fileURLToPath(import.meta.url));
const recording = JSON.parse(readFileSync(join(here, "..", "mocks", "customer_overview.json"), "utf8"));

test("a customer's href carries the decision, the path and the invoice, in that order, encoded", () => {
  assert.equal(customerHref("BUYER-1"), "/customers/BUYER-1");
  assert.equal(customerHref("BUYER-1", {}), "/customers/BUYER-1");
  assert.equal(customerHref("BUYER-1", { decision: "deal:OFF-1", path: "CTR-2" }), "/customers/BUYER-1?decision=deal%3AOFF-1&path=CTR-2");
  assert.equal(customerHref("BUYER-1", { invoice: "RCV-A", decision: "deal:OFF-1" }), "/customers/BUYER-1?decision=deal%3AOFF-1&invoice=RCV-A");
  assert.equal(customerHref("A B/1"), "/customers/A%20B%2F1");
  assert.equal(customerHref("BUYER-1", { decision: null, path: "", invoice: undefined }), "/customers/BUYER-1");
});

test("the stress link is marked as opened from the customer, the server's href kept", () => {
  assert.equal(fromCustomer("/cash?stress=BUYER-1:30&invoice=RCV-A", "BUYER-1"), "/cash?stress=BUYER-1:30&invoice=RCV-A&customer=BUYER-1&from=customer");
  assert.equal(fromCustomer("/cash", "A B"), "/cash?customer=A%20B&from=customer");
});

test("the context is read from a URL's query: only the three keys, only when set", () => {
  const ctx = readContext(new URLSearchParams("customer=BUYER-1&decision=deal%3AOFF-1&path=CTR-2&other=x&invoice="));
  assert.deepEqual(ctx, { decision: "deal:OFF-1", path: "CTR-2" });
  assert.deepEqual(readContext(null), {});
  assert.equal(contextQuery(ctx), "&decision=deal%3AOFF-1&path=CTR-2");
  // What a page's own URL holds is what its customer links carry onward.
  assert.equal(customerHref("BUYER-2", ctx), "/customers/BUYER-2?decision=deal%3AOFF-1&path=CTR-2");
});

test("the recording holds both languages at every moment, the four figures, and the back link of each query the specs use", () => {
  assert.deepEqual(Object.keys(recording).sort(), ["after_fund", "day34", "day34_after", "offer_evaluated", "offer_received", "quiet"]);
  for (const [moment, langs] of Object.entries(recording)) {
    for (const lang of ["en", "zh"]) {
      const { view, backs } = langs[lang];
      assert.equal(view.lang, lang, moment);
      assert.deepEqual(view.figures.map((f) => f.key), ["value", "outstanding", "financing", "share"], moment);
      assert.ok(view.exposure?.rows.length, `${moment}/${lang}: the exposure was recorded with its flag on`);
      assert.ok(backs.every((b) => b.back.href.startsWith("/")), moment);
    }
  }
  const { view, backs } = recording.offer_evaluated.en;
  assert.equal(view.decision.primary.label, "Review the counter");
  const decision = new URL(view.decision.primary.href, "http://x").searchParams;
  assert.ok(backs.some((b) => b.query.decision === decision.get("decision") && b.query.path === decision.get("path") && b.back.href === `/deals?decision=${encodeURIComponent(decision.get("decision"))}&path=${decision.get("path")}`));
  assert.equal(recording.quiet.en.view.decision, null);
  assert.ok(recording.quiet.en.view.none_text);
});

test("every word the page itself owns exists in both languages", () => {
  for (const key of Object.keys(en).filter((k) => k.startsWith("customer."))) assert.ok(zh[key], key);
});
