// Home V2, wave 2: where a worklist row leads, and the recordings the mock serves (taken by `scripts/record-mocks.mjs --home-v2`; nothing here edits them).
// Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { NO_SELECTION, offerOfDecision, readSelection, rowHref, rowSelection, selectionHref } from "../lib/home-v2-href.ts";
import { en, zh } from "../lib/dictionary.ts";

const here = dirname(fileURLToPath(import.meta.url));
const rec = (name) => JSON.parse(readFileSync(join(here, "..", "mocks", "home_v2", name), "utf8"));
const POINTS = ["day0", "offer", "after_fund"];

test("a decision row opens its deal; any other row of the Home's own URL opens the customer; a server href that is elsewhere stays", () => {
  assert.equal(rowHref({ kind: "DECISION", customer_id: "BUYER-1", href: "/?customer=BUYER-1&deal=deal%3AOFF-1" }), "/deals?customer=BUYER-1&decision=deal%3AOFF-1&from=home");
  assert.equal(rowHref({ kind: "COLLECTION", customer_id: "BUYER-1", href: "/?customer=BUYER-1" }), "/customers/BUYER-1");
  assert.equal(rowHref({ kind: "CUSTOMER", href: "/?customer=BUYER-2" }), "/customers/BUYER-2");
  assert.equal(rowHref({ kind: "APPROVAL", href: "/approvals#approval-APR-1" }), "/approvals#approval-APR-1");
  assert.equal(rowHref({ kind: "SETTLEMENT", href: "/cash" }), "/cash");
});

test("the three selections live in the address: read, written, and opened in place from a row", () => {
  const p = new URLSearchParams("customer=BUYER-1&decision=deal%3AOFF-1&scenario=counter%3A0");
  assert.deepEqual(readSelection(p), { customer: "BUYER-1", decision: "deal:OFF-1", scenario: "counter:0" });
  assert.deepEqual(readSelection(new URLSearchParams("")), NO_SELECTION);
  assert.equal(selectionHref({}), "/");
  assert.equal(selectionHref({ customer: "BUYER-1" }), "/?customer=BUYER-1");
  assert.equal(selectionHref({ customer: "BUYER-1", decision: "deal:OFF-1", scenario: "counter:0" }), "/?customer=BUYER-1&decision=deal%3AOFF-1&scenario=counter%3A0");
  assert.deepEqual(selectionHref(readSelection(p)), "/?customer=BUYER-1&decision=deal%3AOFF-1&scenario=counter%3A0");
  assert.deepEqual(rowSelection({ key: "deal:OFF-1", href: "/?customer=BUYER-1&deal=deal%3AOFF-1" }), { customer: "BUYER-1", decision: "deal:OFF-1" });
  assert.deepEqual(rowSelection({ key: "buyer-reply:OFF-2", customer_id: "BUYER-1", href: "/?customer=BUYER-1" }), { customer: "BUYER-1", decision: "deal:OFF-2" });
  assert.deepEqual(rowSelection({ key: "collection:BUYER-2", href: "/?customer=BUYER-2" }), { customer: "BUYER-2", decision: null });
  assert.equal(rowSelection({ key: "settlement:x", href: "/cash" }), null);
  assert.equal(offerOfDecision("deal:OFF-1"), "OFF-1");
});

test("every recorded Home V2 read is in both languages and carries the block the page draws", () => {
  for (const p of POINTS) {
    const home = rec(`home_${p}.json`);
    for (const lang of ["en", "zh"]) {
      const v2 = home[lang].home_v2;
      assert.ok(v2, `${p} ${lang}: home_v2`);
      assert.equal(Object.keys(v2.kpis).sort().join(), "cash_available,funding,lowest_ahead");
      assert.ok(v2.chart.legend.some((l) => l.kind === "current"));
      const w = rec(`worklist_${p}.json`)[lang];
      assert.equal(w.counts.needs_you, w.needs_you.length, `${p} ${lang}: the count is the rows`);
      assert.equal(w.counts.waiting, w.waiting.length);
      assert.equal(w.counts.customers, w.customers.length);
      const c = rec(`customers_${p}.json`)[lang];
      assert.equal(c.customers.length, w.customers.length);
      assert.equal(c.search_terms.length, c.customers.length);
    }
  }
});

test("the alert is counted nowhere and the funding state follows the plan: planned before the run, arranged after", () => {
  assert.equal(rec("home_day0.json").en.home_v2.kpis.funding.state, "PROPOSED");
  assert.equal(rec("home_after_fund.json").en.home_v2.kpis.funding.state, "ARRANGED");
  assert.ok(rec("worklist_offer.json").en.alert);
  assert.equal(rec("worklist_after_fund.json").en.alert, null);
});

test("every Home V2 label has both languages and no word of the banned list", () => {
  const keys = Object.keys(en).filter((k) => k.startsWith("hv2."));
  assert.ok(keys.length > 30);
  for (const k of keys) {
    assert.ok(zh[k] && zh[k].length, `zh ${k}`);
    assert.ok(!/Executive snapshot|Autonomous strategy|Retained yield|Treasury engine|Live stress simulation/i.test(en[k]));
  }
});
