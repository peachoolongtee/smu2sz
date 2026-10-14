// Slice B round three (docs/design/flow-mockup-2026-10-13/05_slice_b_round_three.md), the web half, as plain functions: the tabs and their address, the chart's chosen lines (never more than three), the pair words
// of the inspector (the per-reply map, the old strip beside it, two replies), the comparison's rows and the headroom plot's geometry. The components are TSX; what is tested is their model. Run: pnpm test:unit
import assert from "node:assert/strict";
import { register } from "node:module";
import test from "node:test";

register("./ts-resolve-hook.mjs", import.meta.url);
const m = await import("../components/deals/flow/deal-model.ts");
const { pairWords } = await import("../lib/point-comparison.ts");
const { en, zh } = await import("../lib/dictionary.ts");

const params = (q) => new URLSearchParams(q);
const path = (key, o = {}) => ({ key, kind: key === "asked" ? "asked" : "reply", label: key, recommended: false, terms: [], first_breach_when: null, lowest_fen: null, lowest_short: null, lowest_when: null, ...o });

test("the address: view= names the tab; the retired keys land on Compare responses; nothing is Overview", () => {
  assert.deepEqual(m.viewOf(params("decision=deal:x")), { view: "overview", legacy: false });
  assert.deepEqual(m.viewOf(params("view=cash")), { view: "cash", legacy: false });
  for (const old of ["investigate=1", "compare=1", "chart=1", "show=cost"]) assert.deepEqual(m.viewOf(params(old)), { view: "compare", legacy: true }, old);
  assert.deepEqual(m.viewOf(params("view=terms&show=cash")), { view: "terms", legacy: true });
  assert.deepEqual(m.viewOf(params("view=nonsense")), { view: "overview", legacy: false });
  assert.ok(m.WIDE_VIEWS.has("compare") && m.WIDE_VIEWS.has("cash") && !m.WIDE_VIEWS.has("overview") && !m.WIDE_VIEWS.has("messages"));
});

test("the tabs: four before agreement, three from it; a deal with nothing to draw has no comparison tab; a tab the deal lacks is the Overview", () => {
  assert.deepEqual(m.tabsOf({ agreed: false, analysis: true }), ["overview", "compare", "cash", "messages"]);
  assert.deepEqual(m.tabsOf({ agreed: false, analysis: false }), ["overview", "messages"]);
  assert.deepEqual(m.tabsOf({ agreed: true, analysis: true }), ["overview", "terms", "messages"]);
  assert.equal(m.viewIn("compare", m.tabsOf({ agreed: true, analysis: true })), "overview");
  assert.equal(m.viewIn("terms", m.tabsOf({ agreed: true, analysis: false })), "terms");
});

test("the chart's lines: the request and the recommended reply by default; the address's choice in its order; never more than three; unknown keys and repeats dropped", () => {
  const four = [path("asked"), path("A", { recommended: true }), path("B"), path("C")];
  assert.equal(m.MAX_LINES, 3);
  assert.deepEqual(m.chosenLines(four, null), ["asked", "A"]);
  assert.deepEqual(m.chosenLines(four, ""), ["asked", "A"]);
  assert.deepEqual(m.chosenLines(four, "B,asked"), ["B", "asked"]);
  assert.deepEqual(m.chosenLines(four, "asked,A,B,C"), ["asked", "A", "B"], "a fourth line is never drawn");
  assert.deepEqual(m.chosenLines(four, "A,A,nope,C,B,asked"), ["A", "C", "B"], "repeats and unknown keys do not take a place");
  assert.equal(m.chosenLines(four, "asked,A,B,C").length, 3);
  // No recommended reply: the first reply stands in for it.
  assert.deepEqual(m.chosenLines([path("asked"), path("X"), path("Y")], null), ["asked", "X"]);
  // A choice that names nothing the deal has falls back to the default.
  assert.deepEqual(m.chosenLines(four, "ghost"), ["asked", "A"]);
});

const point = (comparison, comparison_pairs) => ({ day: 0, closing_fen: 0, closing_display: "", events: [], comparison, comparison_pairs });
const A = { key: "A", kind: "reply", recommended: true };
const B = { key: "B", kind: "reply", recommended: false };
const ASKED = { key: "asked", kind: "asked" };

test("pair words: the request against a reply reads the reply's map entry; the old strip beside it is only the fallback for the recommended reply", () => {
  const map = { label: "Same day", asked_display: "¥400,000.00", recommended_display: "¥549,986.20", difference_display: "+¥149,986.20", A: { asked_display: "¥400,000.00", reply_display: "¥549,986.20", difference_display: "+¥149,986.20", cause_text: "Option A: draw ¥150k." }, B: { asked_display: "¥400,000.00", reply_display: "¥490,000.00", difference_display: "+¥90,000.00", cause_text: "Option B: draw ¥90k." } };
  const pointOf = (k) => (k === "A" || k === "B" ? point(map, {}) : undefined);
  assert.deepEqual(pairWords(ASKED, A, pointOf), { aDisplay: "¥400,000.00", bDisplay: "¥549,986.20", difference: "+¥149,986.20", differenceOf: "b", cause: "Option A: draw ¥150k.", causeLines: null, againstAsked: true });
  // Not the recommended reply: its own entry, not the strip.
  assert.equal(pairWords(ASKED, B, pointOf)?.difference, "+¥90,000.00");
  assert.equal(pairWords(ASKED, B, pointOf)?.cause, "Option B: draw ¥90k.");
  // The pair in the other order: the values swap, the difference stays the reply's.
  assert.deepEqual(pairWords(A, ASKED, pointOf), { aDisplay: "¥549,986.20", bDisplay: "¥400,000.00", difference: "+¥149,986.20", differenceOf: "a", cause: "Option A: draw ¥150k.", causeLines: null, againstAsked: true });
  // An older server: the single strip, the request against the recommended reply, with no cause.
  const strip = { label: "Same day", asked_display: "¥400,000.00", recommended_display: "¥549,986.20", difference_display: "+¥149,986.20" };
  const old = () => point(strip, undefined);
  assert.deepEqual(pairWords(ASKED, A, old), { aDisplay: "¥400,000.00", bDisplay: "¥549,986.20", difference: "+¥149,986.20", differenceOf: "b", cause: null, causeLines: null, againstAsked: true });
  assert.equal(pairWords(ASKED, B, old), null, "the strip says nothing of another reply");
  // Nothing written for the day: no words, and nothing is subtracted by the browser.
  assert.equal(pairWords(ASKED, A, () => point(null, {})), null);
  assert.equal(pairWords(ASKED, A, () => undefined), null);
  assert.equal(pairWords(ASKED, { key: "asked", kind: "asked" }, old), null);
});

test("pair words carry the server's cause_lines beside cause_text, and never split the string themselves", () => {
  const lines = [{ label: "As asked", items: ["Early payment ¥420k in 2 days"] }, { label: "Option A", items: ["Credit line draw ¥150k today", "Early payment ¥257k in 2 days"] }];
  const map = { A: { asked_display: "1", reply_display: "2", difference_display: "+1", cause_text: "As asked: Early payment ¥420k in 2 days. Option A: Credit line draw ¥150k today; Early payment ¥257k in 2 days.", cause_lines: lines } };
  const w = pairWords(ASKED, A, () => point(map, {}));
  assert.deepEqual(w.causeLines, lines);
  assert.match(w.cause, /^As asked: /);
  const old = pairWords(ASKED, A, () => point({ A: { ...map.A, cause_lines: undefined } }, {}));
  assert.equal(old.causeLines, null, "an older server sends none: the text is shown whole");
});

test("pair words: two replies read comparison_pairs on the first's point, in the server's order or the reverse, with whose difference it is", () => {
  const pairs = { "A:B": { asked_display: "¥549,986.20", reply_display: "¥490,000.00", difference_display: "−¥59,986.20", cause_text: "Option B: ¥90k drawn, not ¥150k." } };
  const pointOf = () => point(null, pairs);
  assert.deepEqual(pairWords(A, B, pointOf), { aDisplay: "¥549,986.20", bDisplay: "¥490,000.00", difference: "−¥59,986.20", differenceOf: "b", cause: "Option B: ¥90k drawn, not ¥150k.", causeLines: null, againstAsked: false });
  // Chosen the other way round: the server's pair is read reversed; the difference is still B's against A's.
  assert.deepEqual(pairWords(B, A, pointOf), { aDisplay: "¥490,000.00", bDisplay: "¥549,986.20", difference: "−¥59,986.20", differenceOf: "a", cause: "Option B: ¥90k drawn, not ¥150k.", causeLines: null, againstAsked: false });
  assert.equal(pairWords(A, { key: "C", kind: "reply" }, pointOf), null);
});

test("the headroom plot: positions scale from the fen numbers only; the reserve is a line; below it is flagged; a response that cannot be drawn has no dot", () => {
  const paths = [path("asked", { lowest_fen: 16_496_000, lowest_short: "¥165k", lowest_when: "in 60 days" }), path("A", { lowest_fen: 30_000_000, lowest_short: "¥300k", lowest_when: "in 30 days" }), path("B", { lowest_fen: 45_000_000, lowest_short: "¥450k", lowest_when: "in 30 days" }), path("C", { lowest_fen: null, lowest_short: null })];
  const plot = m.headroomPlot(paths, 30_000_000);
  assert.equal(plot.dots.length, 3, "C has no cash to draw");
  assert.deepEqual(plot.dots.map((d) => d.key), ["asked", "A", "B"]);
  assert.deepEqual(plot.dots.map((d) => d.below), [true, false, false], "on the reserve is not below it");
  assert.ok(plot.dots[0].at < plot.reserveAt && plot.reserveAt === plot.dots[1].at && plot.dots[1].at < plot.dots[2].at);
  for (const d of plot.dots) assert.ok(d.at >= 0 && d.at <= 100);
  assert.equal(plot.dots[0].short, "¥165k", "the label is the server's word");
  // One value only (every response on the reserve): the plot still draws, at the middle.
  const flat = m.headroomPlot([path("A", { lowest_fen: 100, lowest_short: "¥1" })], 100);
  assert.equal(flat.dots[0].at, 50);
  assert.equal(m.headroomPlot([path("A")], 100), null);
});

test("the comparison's three rows are server words: the economic headline and the buyer status; the terms cells list each scope's own word", () => {
  const asked = path("asked", { economic_headline_text: "¥5,040.00 once, ¥28,326.92 over 12 months", economic_basis_text: "Two parts, not added together", authority_short_text: "Outside mandate", buyer_status_text: "Asked by Foshan", lowest_short: "¥165k", lowest_when: "in 60 days", reserve_state_text: "Breached by ¥135k for 15 days", first_breach_when: "in 47 days", terms: [{ key: "payment_terms", label: "Payment terms", value_text: "60 days", instead_of_text: null, scope: "future_invoices", scope_label: "Future invoices", cell_text: "60 days" }] });
  const reply = path("A", { economic_headline_text: "¥3,027.77", economic_basis_text: "One-off cost, nothing ongoing", authority_short_text: "FLOW can send", buyer_status_text: "Not yet sent", lowest_short: "¥300k", lowest_when: "in 30 days", reserve_state_text: "Held, no buffer at the lowest point", terms: [{ key: "payment_terms", label: "Payment terms", value_text: "45 days", instead_of_text: "instead of 60", scope: "future_invoices", scope_label: "Future invoices", cell_text: "45 days" }] });
  const rows = m.comparisonRows([asked, reply]);
  assert.deepEqual(rows.map((r) => r.key), ["terms", "economic", "status"], "the cash, the reserve and who may send it are the outcome table's");
  const by = Object.fromEntries(rows.map((r) => [r.key, r.cells]));
  assert.deepEqual(by.terms[1].lines, [{ scope: "Future invoices", text: "45 days" }]);
  assert.deepEqual([by.economic[0].value, by.economic[0].sub], ["¥5,040.00 once, ¥28,326.92 over 12 months", "Two parts, not added together"]);
  assert.deepEqual([by.status[0].value, by.status[1].value], ["Asked by Foshan", "Not yet sent"]);
});

test("terms by scope: the server's scope and cell word decide the row and the cell; a tinted cell is one that says what it stands instead of; an untouched row is the server's word, not blank", () => {
  const term = (o) => ({ key: "k", label: "L", value_text: null, instead_of_text: null, ...o });
  const asked = path("asked", { terms: [term({ key: "early_payment", scope: "existing_invoice", scope_label: "Existing invoice", value_text: "1.20% off ¥420,000.00", cell_text: "1.20% off ¥420,000.00" }), term({ key: "rebate_or_price", scope: "next_quarter", scope_label: "Next quarter", value_text: "1.00% rebate", cell_text: "1.00% rebate" })] });
  const reply = path("A", { kind: "reply", terms: [term({ key: "early_payment", scope: "existing_invoice", scope_label: "Existing invoice", value_text: "0.85% off ¥257,200.00", instead_of_text: "instead of 1.20% off ¥420,000.00", cell_text: "0.85% off ¥257,200.00" }), term({ key: "rebate_or_price", scope: "next_quarter", scope_label: "Next quarter", value_text: null, instead_of_text: "instead of a 1.00% rebate", cell_text: "Not offered" })] });
  const groups = m.termsGroups([asked, reply]);
  assert.deepEqual(groups.map((g) => [g.scope, g.label]), [["existing", "Existing invoice"], ["quarter", "Next quarter"]]);
  const quarter = groups[1].rows[0].cells;
  assert.deepEqual([quarter[1].text, quarter[1].sub], ["Not offered", "instead of a 1.00% rebate"]);
  assert.equal(quarter[1].changed, true);
  const untouched = m.termsGroups([asked, path("A", { kind: "reply", terms: [term({ key: "early_payment", scope: "existing_invoice", scope_label: "Existing invoice", cell_text: "Unchanged" })] })]);
  assert.deepEqual([untouched[0].rows[0].cells[1].text, untouched[0].rows[0].cells[1].unchanged], ["Unchanged", true]);
});

test("every new Deals word has its Chinese twin, and the rule sentence is the server's (its dictionary key is gone)", () => {
  const keys = Object.keys(en).filter((k) => /^deals\.(pane|rail|cmp|out|plot|insp|biz|chips|ov|diff|chart)\./.test(k) || k === "deals.review.counter" || k === "deals.why.differ");
  assert.ok(keys.length > 50);
  for (const k of keys) assert.ok(zh[k] && zh[k] !== en[k], `${k} has a zh twin`);
  assert.equal("deals.why.rule" in en, false);
  assert.equal("deals.why.rule" in zh, false);
});
