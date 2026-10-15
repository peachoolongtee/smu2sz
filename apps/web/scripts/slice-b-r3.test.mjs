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

test("the address: view= names the tab; the retired keys are flagged and land on the Overview (Compare responses is gone); nothing is Overview", () => {
  assert.deepEqual(m.viewOf(params("decision=deal:x")), { view: "overview", legacy: false });
  assert.deepEqual(m.viewOf(params("view=cash")), { view: "cash", legacy: false });
  for (const old of ["investigate=1", "compare=1", "chart=1", "show=cost"]) assert.deepEqual(m.viewOf(params(old)), { view: "overview", legacy: true }, old);
  assert.deepEqual(m.viewOf(params("view=terms&show=cash")), { view: "terms", legacy: true });
  assert.deepEqual(m.viewOf(params("view=nonsense")), { view: "overview", legacy: false });
});

test("the sections: three before agreement (the choices table replaced Compare responses), three from it; a deal with nothing to draw has no cash section; a section the deal lacks is the Overview", () => {
  assert.deepEqual(m.tabsOf({ agreed: false, analysis: true }), ["overview", "cash", "messages"]);
  assert.deepEqual(m.tabsOf({ agreed: false, analysis: false }), ["overview", "messages"]);
  assert.deepEqual(m.tabsOf({ agreed: true, analysis: true }), ["overview", "terms", "messages"]);
  assert.equal(m.viewIn("compare", m.tabsOf({ agreed: true, analysis: true })), "overview");
  assert.equal(m.viewIn("terms", m.tabsOf({ agreed: true, analysis: false })), "terms");
});

test("the day-by-day lines: the series inside the picture's window, as positions along it; the labelled days are the picture's moments inside it", () => {
  const series = [0, 10, 30, 66, 90].map((day) => ({ day, closing_fen: day * 100, closing_display: "", events: [] }));
  const pts = m.lineWindow(series, 0, 66);
  assert.deepEqual(pts.map((p) => p.day), [0, 10, 30, 66], "day 90 is outside the window");
  assert.deepEqual(pts.map((p) => Math.round(p.x)), [0, 15, 45, 100]);
  assert.deepEqual(m.lineWindow(series, 10, 0).map((p) => p.day), [10, 30, 66, 90], "no window: every day from today");
  assert.deepEqual(m.lineWindow(null, 0, 66), []);
  const moments = [{ day: 0, when: "today" }, { day: 33, when: "in 33 days" }, { day: 66, when: "in 66 days" }, { day: 80, when: "in 80 days" }, { day: 5, when: null }];
  assert.deepEqual(m.dayTicks(moments, 0, 66, 1000).map((k) => [Math.round(k.x), k.label]), [[0, "today"], [50, "in 33 days"], [100, "in 66 days"]]);
  assert.deepEqual(m.dayTicks(moments, 0, 0, 1000), []);
  assert.deepEqual(m.dayTicks(moments, 0, 66, 0), [], "not measured yet: none");
  // The days crowd the right end (60, 62 and 66 of 66): no two labels overprint, at a desktop width and at a phone's; the first stays, the last only if it fits.
  const crowded = [0, 15, 30, 45, 60, 62, 66].map((day) => ({ day, when: day === 0 ? "today" : `in ${day} days` }));
  for (const width of [1000, 290]) {
    const ticks = m.dayTicks(crowded, 0, 66, width);
    assert.equal(ticks[0].label, "today");
    const boxes = ticks.map((k) => m.tickExtent(k.x, k.label, width));
    assert.deepEqual(ticks.map((k) => k.align), boxes.map((b) => b.align));
    for (let i = 1; i < boxes.length; i++) assert.ok(boxes[i].left >= boxes[i - 1].right + m.TICK_GAP_PX - 1e-9, `${width} px: "${ticks[i - 1].label}" and "${ticks[i].label}" do not touch`);
    for (const b of boxes) assert.ok(b.left >= -1e-9 && b.right <= width + 1e-9, "inside the row");
  }
  assert.ok(m.dayTicks(crowded, 0, 66, 1000).length > m.dayTicks(crowded, 0, 66, 290).length, "a narrower row keeps fewer");
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

test("the cash scale: positions come from the fen numbers only, widened to the server's labelled ticks; the minimum and a value on it share a place; one value draws at the middle", () => {
  const axis = { min_fen: 0, max_fen: 100_000_000, ticks: [0, 20_000_000, 40_000_000, 60_000_000, 80_000_000, 100_000_000].map((v) => ({ value_fen: v, label: `t${v / 1_000_000}` })) };
  const s = m.cashScale([16_496_000, 30_000_000, 30_000_000], axis);
  assert.equal(s.lo, 0);
  assert.equal(s.hi, 40_000_000, "the smallest tick at or above the highest value");
  assert.deepEqual(s.ticks.map((k) => k.label), ["t0", "t20", "t40"], "only the server's ticks inside the scale, with the server's words");
  assert.ok(s.at(16_496_000) < s.at(30_000_000) && s.at(30_000_000) === 75);
  assert.equal(s.at(-5), 0, "positions stay on the scale");
  const low = m.cashScale([-40_500_000, 30_000_000], { ...axis, ticks: [{ value_fen: -60_000_000, label: "-600" }, ...axis.ticks] });
  assert.equal(low.lo, -60_000_000, "a value below zero widens the scale to the tick under it");
  assert.equal(m.cashScale([100, 100], null).ticks.length, 0, "no axis, no labelled ticks");
  assert.equal(m.cashScale([], null).at(0), 50);
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
  const keys = Object.keys(en).filter((k) => /^deals\.(pane|rail|cmp|out|plot|insp|biz|chips|ov|diff|chart|top|rec|choices|sec|cash)\./.test(k) || k === "deals.review.counter" || k === "deals.why.differ");
  assert.ok(keys.length > 50);
  for (const k of keys) assert.ok(zh[k] && zh[k] !== en[k], `${k} has a zh twin`);
  assert.equal("deals.why.rule" in en, false);
  assert.equal("deals.why.rule" in zh, false);
});

test("the Agreed tab's count is the server's deals in force (awaiting payment + payment late), never the rows; closed is counted apart", () => {
  const row = (key, kind) => ({ key, kind, customer_id: "BUYER-1", subject_text: "Foshan", status_text: "Agreed", consequence_text: "", severity: "NORMAL", href: "/deals" });
  const q = { counts: { needs_you: 0, waiting: 0, agreements: 2, customers: 2 }, alert: null, needs_you: [], waiting: [], agreements: [row("agreement:deal:A", "AGREEMENT"), row("promise:CMT:O2", "PROMISE")], customers: [], fallback: false };
  // One deal, two rows (the agreement and its promised payment): the tab says 1.
  assert.equal(m.dealTabCounts({ ...q, deals: { needs_you: 0, waiting: 0, agreements: 2, awaiting_payment: 1, payment_late: 0, closed: 0 } }).agreements, 1);
  assert.equal(m.dealTabCounts({ ...q, deals: { needs_you: 0, waiting: 0, agreements: 3, awaiting_payment: 1, payment_late: 1, closed: 2 } }).agreements, 2, "closed is not in the tab's count");
  assert.equal(m.dealTabCounts({ ...q, deals: { needs_you: 1, waiting: 0, agreements: 3, awaiting_payment: 1, payment_late: 1, closed: 2 } }).all, 5, "All is every deal the queue lists, closed ones included");
  assert.deepEqual(m.afterGroupCounts({ ...q, deals: { awaiting_payment: 1, payment_late: 0, closed: 2 } }), { payment_late: 0, awaiting_payment: 1, closed: 2 });
});
