// Wave 4 part A (map #65): Ask FLOW's suggested questions per page, the rule that a question the page cannot answer is hidden, and the
// context a turn carries (ids and a day, never a figure). Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { register } from "node:module";
import test from "node:test";
import { fileURLToPath } from "node:url";

// The app writes its imports without an extension; the same resolution hook the mock recorder uses lets Node load the TypeScript.
register("./ts-resolve-hook.mjs", import.meta.url);
const { demoStore } = await import("../lib/demo-store.ts");
const { NO_FACTS, nlContext, pageOf } = await import("../lib/chat-context.ts");
const { promptsFor } = await import("../lib/chat-prompts.ts");

const FULL = { verdict: true, counters: true, plan: true, overdue: true };
const business = (pathname, facts, lang = "en") => promptsFor("OWNER", lang, pathname, { business: true, facts });
const ids = (list) => list.map((p) => p.id);

test("Business shows two to four questions per page when the page holds what they ask about", () => {
  for (const page of ["/", "/deals", "/cash", "/receivables"]) {
    for (const lang of ["en", "zh"]) {
      const n = business(page, FULL, lang).length;
      assert.ok(n >= 2 && n <= 4, `${page} ${lang}: ${n}`);
    }
  }
  assert.deepEqual(ids(business("/", FULL)), ["page-changed", "page-attention"]);
  assert.deepEqual(ids(business("/deals", FULL)), ["page-counter", "page-original", "page-option", "page-waiting"]);
  assert.deepEqual(ids(business("/cash", FULL)), ["page-plan", "page-arrive", "page-late"]);
  assert.deepEqual(ids(business("/receivables", FULL)), ["page-chase", "page-overdue", "page-late"]);
});

test("a question whose prerequisite is missing is hidden, not shown to fail", () => {
  // no evaluated deal: the deal questions go, the one about what is open stays
  assert.deepEqual(ids(business("/deals", NO_FACTS)), ["page-waiting"]);
  // a deal without counters: no "Why is Option A cheaper?"
  assert.deepEqual(ids(business("/deals", { ...NO_FACTS, verdict: true })), ["page-counter", "page-original", "page-waiting"]);
  // no recommended plan: no "Why did FLOW choose this plan?"
  assert.deepEqual(ids(business("/cash", { ...FULL, plan: false })), ["page-arrive", "page-late"]);
  // nothing overdue: no "Who should I chase first?"
  assert.deepEqual(ids(business("/receivables", { ...FULL, overdue: false })), ["page-overdue", "page-late"]);
  // facts not known yet (the read has not arrived) hide the same questions
  assert.deepEqual(ids(business("/cash", undefined)), ["page-arrive", "page-late"]);
});

test("every other Business route gets the Home questions, and nothing from the Demo set", () => {
  for (const page of ["/approvals", "/activity", "/limits", "/chat", null, undefined]) {
    assert.deepEqual(ids(business(page, FULL)), ["page-changed", "page-attention"], String(page));
  }
  const all = JSON.stringify(["/", "/deals", "/cash", "/receivables"].flatMap((p) => business(p, FULL)));
  for (const demoOnly of ["EX01", "0.8%", "approve it", "go ahead", "fund the cash gap", "Tier 1"]) assert.ok(!all.includes(demoOnly), demoOnly);
});

test("Demo keeps the general prompts (fixtures, the amendment, approve it) and the buyer role-play", () => {
  const demo = promptsFor("OWNER", "en", "/demo");
  assert.ok(ids(demo).includes("evaluate") && ids(demo).includes("amend") && ids(demo).includes("approve"));
  assert.equal(demo.find((p) => p.id === "evaluate").text, "Evaluate EX01");
  assert.ok(promptsFor("COUNTERPARTY", "en", "/deals").every((p) => p.counterparty));
  // a Business route in Demo mode: the page's answerable questions first, then the general ones
  const onDeals = promptsFor("OWNER", "en", "/deals", { facts: NO_FACTS });
  assert.deepEqual(ids(onDeals).slice(0, 1), ["page-waiting"]);
  assert.ok(ids(onDeals).includes("evaluate"));
});

test("every suggested question is one the API's rules read (the same list as tests/nl/test_business_page_prompts.py)", () => {
  const py = readFileSync(fileURLToPath(new URL("../../../services/api/tests/nl/test_business_page_prompts.py", import.meta.url)), "utf8");
  for (const page of ["/", "/deals", "/cash", "/receivables"]) {
    for (const lang of ["en", "zh"]) {
      for (const p of business(page, FULL, lang)) assert.ok(py.includes(`"${p.text}"`), `${lang} ${p.text}`);
    }
  }
});

test("the page context carries ids and a day only", () => {
  assert.equal(pageOf("/deals"), "/deals");
  assert.equal(pageOf("/deals?x=1#top"), "/dealsx1top"); // never more than the API's pattern allows
  assert.equal(pageOf(""), "/");
  assert.ok(pageOf("/" + "a".repeat(200)).length <= 64);
  demoStore.set((s) => ({ ...s, offerId: null, verdicts: {} }));
  assert.deepEqual(Object.keys(nlContext("/deals")).filter((k) => k !== "since_day"), ["page"]); // no deal yet
  demoStore.set((s) => ({ ...s, offerId: "OFF-1", offers: {}, verdicts: { "OFF-1": { offer_id: "OFF-1", counters: [{ label: "Option A" }] } } }));
  const ctx = nlContext("/deals");
  assert.equal(ctx.page, "/deals");
  assert.equal(ctx.offer_id, "OFF-1");
  for (const key of Object.keys(ctx)) assert.ok(["page", "offer_id", "decision_id", "invoice_id", "since_day"].includes(key), key);
  assert.ok(!("invoice_id" in nlContext("/deals"))); // an invoice is named only from Receivables
});
