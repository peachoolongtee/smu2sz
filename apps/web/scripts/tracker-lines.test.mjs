// The deal tracker's cost lines (lib/tracker-lines.ts): which line is in the table and the bar and which is shown apart, outside the deal's cost.
// The reads are the recorded ones (mocks/tracker/*.json, scripts/record-mocks.mjs --tracker); the story never reaches a related line the server will not
// count (the switch is the server's), so the uncounted layout is covered here by overriding one field of a recorded line IN THE TEST, never in the files.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { inTotal, isAgreementLine, isOutside, outsideLines, tableLines } from "../lib/tracker-lines.ts";

const here = dirname(fileURLToPath(import.meta.url));
const read = (m) => JSON.parse(readFileSync(join(here, "..", "mocks", "tracker", `${m}.json`), "utf8")).en;
const clone = (v) => JSON.parse(JSON.stringify(v));

test("on the golden story every line is in the table; the agreement's two components sum to the expected cost's parts, the cure counts once approved", () => {
  const approved = read("approved").cost.lines;
  assert.deepEqual(approved.map((l) => l.key), ["terms", "planned_funding", "funding"]);
  assert.equal(outsideLines(approved).length, 0);
  assert.equal(tableLines(approved).length, 3);
  assert.deepEqual(approved.filter(isAgreementLine).map((l) => l.key), ["terms", "planned_funding"]);
  assert.ok(approved.every(inTotal));
});

test("the cure queued for approval is in the table (it counts once approved), not outside the deal's cost", () => {
  const funding = read("pending").cost.lines.find((l) => l.key === "funding");
  assert.equal(funding.counted, false);
  assert.equal(funding.counted_note_text, null);
  assert.equal(isOutside(funding), false);
  assert.equal(inTotal(funding), false); // no figure in the total yet: no bar segment
});

test("a related line the server does not count is taken out of the table and the bar and shown apart (one field overridden in the test)", () => {
  const lines = clone(read("approved").cost.lines);
  const funding = lines.find((l) => l.key === "funding");
  funding.counted = false;
  funding.actual_fen = null;
  funding.actual_display = null;
  funding.counted_note_text = "FLOW is set not to count related funding in a deal's cost, so this is shown but not counted.";
  assert.deepEqual(outsideLines(lines).map((l) => l.key), ["funding"]);
  assert.deepEqual(tableLines(lines).map((l) => l.key), ["terms", "planned_funding"]);
  assert.deepEqual(lines.filter(inTotal).map((l) => l.key), ["terms", "planned_funding"]);
  // its own figure survives for the block
  assert.ok(outsideLines(lines)[0].figure_display);
  for (const relation of ["after_late_payment", "secured_on_invoice"]) {
    funding.relation = relation;
    assert.equal(isOutside(funding), true);
  }
});

test("an agreement component is never outside the cost, whatever it carries", () => {
  const terms = clone(read("approved").cost.lines[0]);
  terms.counted = false;
  terms.counted_note_text = "x";
  assert.equal(isOutside(terms), false);
  terms.relation = "none";
  assert.equal(isOutside(terms), false);
});
