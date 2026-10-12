// Ticket #109 (the Deals decision queue): how the deals read is filed into the four tabs, the context every link carries, the exposure recording's shape
// and the dictionary's two languages. The recordings are the API's own answers (node scripts/record-mocks.mjs --exposure); nothing here edits them.
// Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { contextQuery, openTab, queueRows, stressHref } from "../components/deals/queue/model.ts";
import { en, zh } from "../lib/dictionary.ts";

const here = dirname(fileURLToPath(import.meta.url));
const mock = (n) => JSON.parse(readFileSync(join(here, "..", "mocks", n), "utf8"));

test("the evaluated day-0 deals read files into one reply needed, one agreement in force and one customer to set up", () => {
  const rows = queueRows(mock("deals_day0_evaluated.json").deals);
  assert.deepEqual(rows.map((r) => r.tab), ["needs", "agreed", "setup"]);
  assert.equal(rows[0].offerId, mock("deals_day0_evaluated.json").deals[0].open_offer.offer_id);
  assert.equal(rows[1].offerId, null);
});

test("an open offer whose reply is out is awaiting the buyer; the tab opens on the address's tab, else the first with a line", () => {
  const deals = mock("deals_day0_evaluated.json").deals;
  const sent = structuredClone(deals);
  sent[0].open_offer.stages = sent[0].open_offer.stages.map((s) => ({ ...s, state: s.key === "sent" ? "now" : s.state }));
  assert.equal(queueRows(sent)[0].tab, "wait");
  assert.equal(openTab(null, queueRows(deals)), "needs");
  assert.equal(openTab("setup", queueRows(deals)), "setup");
  assert.equal(openTab("nonsense", queueRows(deals.slice(1))), "setup");
});

test("the context carries customer, decision and path; the stress link carries stress and the invoice", () => {
  const q = new URLSearchParams(contextQuery({ customer: "BUYER-1", decision: "deal:OFF-1", path: "CTR-1" }));
  assert.deepEqual([q.get("customer"), q.get("decision"), q.get("path")], ["BUYER-1", "deal:OFF-1", "CTR-1"]);
  const href = new URL(stressHref("BUYER-1", 30, "RCV-A", "customer=BUYER-1"), "http://x");
  assert.equal(href.pathname, "/cash");
  assert.equal(href.searchParams.get("stress"), "BUYER-1:30");
  assert.equal(href.searchParams.get("invoice"), "RCV-A");
  assert.equal(new URL(stressHref("BUYER-1", 30, null, "customer=BUYER-1"), "http://x").searchParams.has("invoice"), false);
});

test("the exposure recording holds both languages, every path's sentences and no stray timing", () => {
  const rec = mock("offer_exposure_ex01.json");
  for (const lang of ["en", "zh"]) {
    const v = rec[lang];
    assert.equal(v.lang, lang);
    for (const p of v.paths.filter((x) => x.kind !== "do_nothing")) assert.ok(v.band.by_path[p.key]?.stress, `${lang} ${p.key} has a stress sentence`);
    assert.equal(v.computed_in_seconds, 0);
    // The appended do-nothing path is words only (no band, stress or room entry); every path carries its table words; the aside has the customer's words.
    assert.equal(v.paths.at(-1).kind, "do_nothing");
    for (const p of v.paths) assert.ok(p.lowest_display && p.share_after_text, `${lang} ${p.key} has its table words`);
    // (the server keeps an explicit null for it in each map)
    assert.ok(v.band.by_path.do_nothing == null);
    assert.ok(v.stress.paths.do_nothing == null);
    assert.ok(v.capacity.do_nothing == null);
    assert.ok(v.customer_context.owes_display && v.customer_context.profile_href);
    assert.ok(v.capacity.asked.spare.x_star_display);
  }
});

test("every queue word is said in English and in Chinese", () => {
  const keys = Object.keys(en).filter((k) => k.startsWith("dq."));
  assert.ok(keys.length > 60);
  // ("¥0" is the same sign in both languages)
  for (const k of keys) assert.ok(zh[k] && (zh[k] !== en[k] || k === "dq.none"), `${k} is translated`);
});
