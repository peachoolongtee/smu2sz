import assert from "node:assert/strict";
import { test } from "node:test";
import { originOf, parseStress } from "../lib/cash-stress.ts";
import { buyerExposureQuery } from "../lib/live/exposure-query.ts";

test("the buyer read asks for the language, the light read and only the context parts it has, `from` included", () => {
  assert.equal(buyerExposureQuery("en"), "lang=en&spare=0");
  assert.equal(buyerExposureQuery("zh", { customer: "BUYER-1", invoice: null, decision: undefined }), "lang=zh&spare=0&customer=BUYER-1");
  const all = new URLSearchParams(buyerExposureQuery("en", { customer: "BUYER-1", invoice: "RCV-A", decision: "deal:OFF-1", path: "counter:0", from: "deal" }));
  assert.deepEqual(Object.fromEntries(all), { lang: "en", spare: "0", customer: "BUYER-1", invoice: "RCV-A", decision: "deal:OFF-1", path: "counter:0", from: "deal" });
});

test("only the three origins the server knows are passed on", () => {
  for (const v of ["deal", "invoice", "customer"]) assert.equal(originOf(v), v);
  for (const v of [null, "", "home", "Deal", "deal "]) assert.equal(originOf(v), null);
});

test("the stress link is the buyer and the delay; a buyer alone is a link; nothing is none", () => {
  assert.deepEqual(parseStress("BUYER-1:30"), { buyerId: "BUYER-1", days: 30 });
  assert.deepEqual(parseStress("BUYER-1"), { buyerId: "BUYER-1", days: null });
  assert.deepEqual(parseStress("A:B:7"), { buyerId: "A:B", days: 7 });
  assert.deepEqual(parseStress("A:B"), { buyerId: "A:B", days: null });
  assert.equal(parseStress(null), null);
  assert.equal(parseStress("  "), null);
});
