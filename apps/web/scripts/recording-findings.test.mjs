// Findings from the demo recording of 18 Oct: "1 security events logged". An English string that counts something says one thing in the
// singular: the dictionary's own plural pattern ("{n|event|events}"), never a bare plural after a count. Chinese has no plural and is unchanged.
// Run: pnpm test:unit
import assert from "node:assert/strict";
import test from "node:test";
import { en, zh } from "../lib/dictionary.ts";
import { setLang, tNow } from "../lib/i18n.ts";

test("the chat's security line counts one event in the singular, two in the plural, and Chinese is unchanged", () => {
  setLang("en");
  assert.equal(tNow("chat.security.title", { n: 1 }), "1 security event logged");
  assert.equal(tNow("chat.security.title", { n: 2 }), "2 security events logged");
  setLang("zh");
  assert.equal(tNow("chat.security.title", { n: 1 }), "已记录 1 个安全事件");
  setLang("en");
});

test("the other counted strings agree with their count too", () => {
  setLang("en");
  const said = (key, vars) => tNow(key, vars);
  assert.equal(said("common.days", { n: 1 }), "1 day");
  assert.equal(said("common.days", { n: 30 }), "30 days");
  assert.equal(said("biz.when.inDays", { n: 1 }), "in 1 day");
  assert.equal(said("biz.when.daysAgo", { n: 1 }), "1 day ago");
  assert.equal(said("ledger.entries", { n: 1 }), "1 entry");
  assert.equal(said("deal.checksAll", { n: 1 }), "All 1 check passes");
  assert.equal(said("deal.checksSome", { bad: 1, n: 3 }), "1 of 3 checks needs a look");
  assert.equal(said("deal.checksSome", { bad: 2, n: 3 }), "2 of 3 checks need a look");
  assert.equal(said("deal.progress.count", { done: 0, total: 1 }), "0 of 1 payment settled");
  assert.equal(said("finance.loans.term", { n: 1 }), "1 month");
  assert.equal(said("dq.band.late", { n: 1 }), "If paid 1 day late");
});

test("no English string puts a bare plural noun straight after a count", () => {
  // "{n} days", "{count} invoices": a number variable followed by a plural noun, with no {n|one|other} choice. Keys whose call site picks a
  // singular key of its own (a ".many" key beside a ".one") are left as they are.
  const COUNT = /\{(n|days|count|entries|total|base|terms)\} (days|entries|events|messages|invoices|months|payments|checks|combinations)\b/;
  const bare = Object.entries(en).filter(([key, value]) => COUNT.test(value) && !key.endsWith(".many") && !en[`${key}.one`]);
  assert.deepEqual(bare.map(([key]) => key), []);
  // the plural pattern is English-only: no Chinese string uses it
  assert.deepEqual(Object.entries(zh).filter(([, value]) => /\{\w+\|[^{}]*\|[^{}]*\}/.test(value)).map(([key]) => key), []);
});
