// Wave 5 part A (map #65, ticket #74): which invoices offer "Chase payment", and the recordings that carry the handoff and the
// four receipt facts. The recordings are the API's own answers (scripts/record-mocks.mjs); nothing here edits them.
// Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { chaseIds, shortfallStretch } from "../lib/chase.ts";
import { en, zh } from "../lib/dictionary.ts";

const here = dirname(fileURLToPath(import.meta.url));
const mock = (n) => JSON.parse(readFileSync(join(here, "..", "mocks", n), "utf8"));

const inv = (receivable_id, due_day, past_due = false) => ({ receivable_id, counterparty_id: "B", face_fen: 1, face_display: "x", due_day, status: "OPEN", past_due });
const promise = (receivable_id, status) => ({ receivable_id, status });

test("a past-due invoice offers Chase payment; one that is not due and not at risk does not", () => {
  const ids = chaseIds([inv("late", 32, true), inv("calm", 77)], [], null);
  assert.deepEqual([...ids], ["late"]);
});

test("an invoice due inside the forecast's shortfall stretch offers it, one outside does not", () => {
  const stretch = shortfallStretch(40, 47);
  assert.deepEqual(stretch, { from: 40, to: 47 });
  const ids = chaseIds([inv("before", 39), inv("first", 40), inv("inside", 44), inv("lowest", 47), inv("after", 48)], [], stretch);
  assert.deepEqual([...ids].sort(), ["first", "inside", "lowest"]);
});

test("no shortfall means no stretch; a lowest day before the breach does not invert it", () => {
  assert.equal(shortfallStretch(null, 12), null);
  assert.equal(shortfallStretch(undefined, undefined), null);
  assert.deepEqual(shortfallStretch(10, 3), { from: 10, to: 10 });
});

test("a lapsed promise offers it, a kept or awaited one does not", () => {
  const ids = chaseIds([inv("a", 90), inv("b", 90), inv("c", 90)], [promise("a", "LAPSED"), promise("b", "RECEIVED"), promise("c", "AWAITED")], null);
  assert.deepEqual([...ids], ["a"]);
});

test("the chase dictionary lines exist in both languages", () => {
  for (const k of Object.keys(en).filter((x) => x.startsWith("biz.chase.") || x === "biz.recv.worth.failed" || x === "biz.recv.ranking.default")) {
    assert.ok(zh[k], k);
  }
  assert.equal(en["biz.chase.copied"], "Copied");
  assert.equal(en["biz.recv.worth.failed"], "The collections ranking could not be read.");
});

test("the recorded handoffs hold the server's figures for every open invoice, in both languages, with no record ids", () => {
  for (const [file, outstanding, late] of [["chase_day34.json", "¥160,000.00", 2], ["chase_day34_half.json", "¥290,000.00", 2], ["chase_day0.json", "¥420,000.00", 0]]) {
    const rec = mock(file);
    assert.deepEqual(Object.keys(rec.en), Object.keys(rec.zh), file);
    const a = rec.en["RCV-A"];
    assert.equal(a.outstanding_display, outstanding, file);
    assert.equal(a.late_days, late, file);
    assert.ok(a.request_text.includes(outstanding) && a.request_text.includes(a.buyer_name), file);
    assert.ok(rec.zh["RCV-A"].request_text.includes(outstanding), file);
    assert.doesNotMatch(JSON.stringify(rec), /CMT-|APR-|\bOP-/, file);
  }
  assert.equal(mock("chase_day34_half.json").en["RCV-A"].thread_href, "/deals?buyer=BUYER-1");
});

test("the recorded reconciliations carry the four facts on the receipt row", () => {
  const half = mock("home_reconciliation_day34_half.json").receipts[0];
  assert.deepEqual(
    [half.received_display, half.face_cleared_display, half.discount_display, half.remaining_display, half.window_state],
    ["¥128,895.00", "¥130,000.00", "¥1,105.00", "¥290,000.00", "ended"],
  );
  const full = mock("home_reconciliation_day34.json").receipts[0];
  assert.equal(full.window_state, "ended");
  assert.equal(full.remaining_display, "¥160,000.00");
});
