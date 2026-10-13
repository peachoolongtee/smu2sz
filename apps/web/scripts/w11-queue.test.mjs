// Ticket #109 (the Deals decision queue): the exposure recording's shape and the dictionary's two languages (the queue itself is components/deals/flow, tested in slice-b.test.mjs). The recordings are the API's own answers (node scripts/record-mocks.mjs --exposure); nothing here edits them.
// Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { en, zh } from "../lib/dictionary.ts";

const here = dirname(fileURLToPath(import.meta.url));
const mock = (n) => JSON.parse(readFileSync(join(here, "..", "mocks", n), "utf8"));

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
