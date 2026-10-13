// Slice B round two (docs/design/flow-mockup-2026-10-13/04_slice_b_round_two.md), the web half: the Deals queue's model (negotiations only, lifecycle pill, sort, group, counts), the commercial terms
// table's rows, the timing diagram's bars and the cost table's rows, as plain functions. The components are TSX (node cannot strip JSX), so what is tested is their model. Run: pnpm test:unit
import assert from "node:assert/strict";
import { register } from "node:module";
import test from "node:test";

register("./ts-resolve-hook.mjs", import.meta.url);
const m = await import("../components/deals/flow/deal-model.ts");
const { en, zh } = await import("../lib/dictionary.ts");

const row = (o) => ({ key: o.key, kind: "DECISION", customer_id: "BUYER-1", subject_text: "Foshan · Early settlement on the ¥420k invoice", status_text: "Counter ready", consequence_text: "", severity: "NORMAL", href: "/deals", ...o });
const queue = (o = {}) => ({ counts: { needs_you: 9, waiting: 9, agreements: 9, customers: 9 }, alert: null, needs_you: [], waiting: [], agreements: [], customers: [], fallback: false, ...o });

test("the Deals queue lists negotiations only: an approval, a collection, a setup task and a settlement are other pages' rows; the promised payments stay under the agreements", () => {
  const q = queue({
    needs_you: [row({ key: "a" }), row({ key: "b", kind: "APPROVAL" }), row({ key: "c", kind: "COLLECTION" }), row({ key: "d", kind: "SETUP" })],
    waiting: [row({ key: "e", kind: "BUYER_REPLY" }), row({ key: "f", kind: "SETTLEMENT" }), row({ key: "g", kind: "PROMISE" })],
    agreements: [row({ key: "h", kind: "AGREEMENT" }), row({ key: "i", kind: "PROMISE" })],
  });
  assert.deepEqual(m.negotiationRows(q).map((x) => [x.tier, x.row.key]), [["needs_you", "a"], ["waiting", "e"], ["agreements", "h"], ["agreements", "i"]]);
});

test("the tabs' counts are the server's `queue.deals` when it sends them, else the negotiation rows held; the Customers tab is gone", () => {
  const q = queue({ needs_you: [row({ key: "a" }), row({ key: "b", kind: "APPROVAL" })], waiting: [row({ key: "e", kind: "BUYER_REPLY" })] });
  assert.deepEqual(m.dealTabCounts(q), { all: 2, needs_you: 1, waiting: 1, agreements: 0 });
  assert.deepEqual(m.dealTabCounts({ ...q, deals: { all: 5, needs_you: 3, waiting: 1, agreements: 1 } }), { all: 5, needs_you: 3, waiting: 1, agreements: 1 });
  assert.deepEqual(m.dealTabCounts({ ...q, deals: { counts: { needs_you: 2, waiting: 0, agreements: 0 } } }), { all: 2, needs_you: 2, waiting: 0, agreements: 0 });
  assert.equal(m.dealTabOf("customers"), null);
  assert.equal(m.dealTabOf("waiting"), "waiting");
});

test("the pill is the server's lifecycle word with a tone that says who acts; without a lifecycle the old 'state . who acts' is split and the tier decides the tone", () => {
  const ready = m.rowPill("needs_you", row({ key: "a", lifecycle: "counter_ready", status_text: "Counter ready" }));
  assert.deepEqual([ready.tone, ready.text, ready.next, ready.lifecycle], ["amber", "Counter ready", null, "counter_ready"]);
  assert.equal(m.rowPill("waiting", row({ key: "b", lifecycle: "Awaiting buyer", status_text: "Awaiting buyer" })).tone, "lavender");
  assert.equal(m.rowPill("agreements", row({ key: "c", lifecycle: "agreed", status_text: "Agreed" })).tone, "green");
  assert.equal(m.rowPill("agreements", row({ key: "d", lifecycle: "lapsed", status_text: "Lapsed" })).tone, "neutral");
  assert.equal(m.rowPill("needs_you", row({ key: "e", lifecycle: "more_info", status_text: "More information needed" })).tone, "amber");
  const old = m.rowPill("waiting", row({ key: "f", status_text: "Awaiting buyer · Nothing for you to do" }));
  assert.deepEqual([old.tone, old.text, old.next, old.lifecycle], ["lavender", "Awaiting buyer", "Nothing for you to do", null]);
  assert.equal(m.lifecycleOf({ lifecycle: "Something else" }), null);
  // The selected negotiation's pill follows the row's lifecycle, else the record's own state.
  assert.deepEqual(m.paneStatus(row({ key: "a", lifecycle: "counter_ready", status_text: "Counter ready" }), "Counter recommended", "RESPONSE_READY"), { tone: "amber", text: "Counter ready" });
  assert.deepEqual(m.paneStatus(null, "No deal: the buyer did not accept", "NO_DEAL"), { tone: "neutral", text: "No deal: the buyer did not accept" });
});

test("urgency sorts the owner's turn first, then severity, then the nearer deadline, and keeps the server's order on a tie; latest activity needs a day from the server", () => {
  const rows = [
    { tier: "waiting", row: row({ key: "w1", last_activity_day: 5 }) },
    { tier: "needs_you", row: row({ key: "n1", severity: "NORMAL", deadline_day: 9, last_activity_day: 1 }) },
    { tier: "needs_you", row: row({ key: "n2", severity: "CRITICAL", last_activity_day: 2 }) },
    { tier: "needs_you", row: row({ key: "n3", severity: "NORMAL", deadline_day: 3, last_activity_day: 3 }) },
    { tier: "agreements", row: row({ key: "g1" }) },
    { tier: "needs_you", row: row({ key: "n4", severity: "NORMAL", deadline_day: 3 }) },
  ];
  assert.deepEqual(m.sortRows(rows, "urgency").map((x) => x.row.key), ["n2", "n3", "n4", "n1", "w1", "g1"]);
  assert.deepEqual(m.sortRows(rows, "latest").map((x) => x.row.key), ["w1", "n3", "n2", "n1", "g1", "n4"]);
  assert.equal(m.canSortLatest(rows), true);
  assert.equal(m.canSortLatest([{ tier: "waiting", row: row({ key: "x" }) }]), false);
});

test("group by customer keeps the sort: a group is placed by its first row, a row with no customer stands alone", () => {
  const rows = [
    { tier: "needs_you", row: row({ key: "a", customer_id: "B2" }) },
    { tier: "needs_you", row: row({ key: "b", customer_id: "B1" }) },
    { tier: "waiting", row: row({ key: "c", customer_id: "B2" }) },
    { tier: "waiting", row: row({ key: "d", customer_id: null, subject_text: "Funding" }) },
  ];
  const groups = m.groupByCustomer(rows, (id, r) => id ?? r.subject_text);
  assert.deepEqual(groups.map((g) => [g.name, g.rows.map((x) => x.row.key)]), [["B2", ["a", "c"]], ["B1", ["b"]], ["Funding", ["d"]]]);
});

const term = (key, label, value_text, instead_of_text = null) => ({ key, label, value_text, instead_of_text });
const asked = { key: "asked", kind: "asked", label: "As they asked", terms: [term("payment_terms", "Payment terms", "60 days"), term("early_payment", "Early payment", "1.20% off ¥420,000.00"), term("rebate_or_price", "Rebate or price", "1.00% rebate")] };
const reply = { key: "CTR-1", kind: "reply", label: "Option A", terms: [term("payment_terms", "Payment terms", "45 days", "instead of 60"), term("early_payment", "Early payment", "0.85% off ¥257,200.00", "instead of 1.20% off ¥420,000.00"), term("rebate_or_price", "Rebate or price", null, "instead of a 1.00% rebate")] };

test("the terms table is grouped by scope (existing invoice, future invoices, next quarter), the server's labels and values, the changed ones flagged and an untouched term 'unchanged'", () => {
  const g = m.termsGroups([asked, reply]);
  assert.deepEqual(g.map((x) => [x.scope, x.rows.map((r) => r.label)]), [["existing", ["Early payment"]], ["future", ["Payment terms"]], ["quarter", ["Rebate or price"]]]);
  const pay = g[1].rows[0].cells;
  assert.deepEqual([pay[0].text, pay[0].changed, pay[1].text, pay[1].sub, pay[1].changed], ["60 days", true, "45 days", "instead of 60", true]);
  const rebate = g[2].rows[0].cells;
  assert.deepEqual([rebate[1].text, rebate[1].sub, rebate[1].changed], [null, "instead of a 1.00% rebate", true]);
  // A scope the ask does not touch says so; a term the server names for nobody is not drawn; an unknown key keeps the server's order under "other".
  const quiet = { ...asked, terms: [term("payment_terms", "Payment terms", null), term("odd_term", "Odd", "x"), term("nothing", "Nothing", null)] };
  const q = m.termsGroups([quiet]);
  assert.equal(q[0].rows[0].cells[0].unchanged, true);
  assert.deepEqual(q.map((x) => x.scope), ["future", "other"]);
});

test("the timing diagram has a bar for each path with a term in days, one scale, the server's words, and no diagram below two bars", () => {
  const a = { ...asked, terms_days: 60, terms_delta_text: "+15 days requested by buyer" };
  const r = { ...reply, terms_days: 45 };
  const t = m.timingOf({ current_terms_days: 45, current_terms_text: "45 days" }, a, r);
  assert.deepEqual(t.bars.map((b) => [b.key, b.days, b.text]), [["current", 45, "45 days"], ["asked", 60, "60 days"], ["reply", 45, "45 days"]]);
  assert.equal(t.max, 60);
  assert.equal(t.deltaText, "+15 days requested by buyer");
  assert.equal(m.timingOf({}, a, r)?.bars.length, 2);
  assert.equal(m.timingOf({}, a, { ...reply }), null); // the reply has no terms change: no bar
  assert.equal(m.timingOf({ current_terms_days: 45 }, { ...asked }, null), null);
  assert.equal(m.timingOf({ current_terms_days: 0 }, { ...asked, terms_days: 0 }, null), null);
});

test("the cost table aligns the components of the paths by key (else label); a path without one has no cell; the headline keeps its basis words", () => {
  const a = { cost_components: [{ key: "now", label: "Immediate discount", display: "¥5,040.00", basis_text: "once, now" }, { key: "fwd", label: "Longer terms", display: "¥16,217.95", basis_text: "over 12 months" }] };
  const r = { cost_components: [{ key: "now", label: "Immediate discount", display: "¥3,027.77", basis_text: "once, now" }] };
  const rows = m.costRows([a, r]);
  assert.deepEqual(rows.map((x) => [x.label, x.cells.map((c) => c?.display ?? null)]), [["Immediate discount", ["¥5,040.00", "¥3,027.77"]], ["Longer terms", ["¥16,217.95", null]]]);
  assert.deepEqual(m.costHeadline({ cost_forward_display: "¥28,326.92", cost_once_display: "¥5,040.00", cost_note: "two parts: once, and over 12 months" }), { display: "¥28,326.92", basis: "two parts: once, and over 12 months" });
  assert.deepEqual(m.costHeadline({ cost_total_display: "¥3,027.77", cost_basis_text: "once, nothing ongoing", cost_display: "x", cost_note: "y" }), { display: "¥3,027.77", basis: "once, nothing ongoing" });
});

test("a cost row's note (the funding the plan cannot incur today) rides with its cell, and a row with no amount is no cell", () => {
  const r = { cost_rows: [{ key: "immediate_discount", label: "Immediate discount", amount_display: "¥3,570.00", basis_text: "once", note: null }, { key: "funding", label: "Funding cost", amount_display: "¥2,919.20", basis_text: "once", note: "if the plan runs; it cannot run today" }, { key: "rebate", label: "Rebate", amount_display: null, basis_text: "over 12 months", note: null }, { key: "total", label: "Total", amount_display: "¥6,489.20", basis_text: "once, nothing ongoing", note: null }] };
  const rows = m.costRows([r]);
  assert.deepEqual(rows.map((x) => [x.key, x.cells[0]?.display, x.cells[0]?.note ?? null]), [["immediate_discount", "¥3,570.00", null], ["funding", "¥2,919.20", "if the plan runs; it cannot run today"]]);
});

test("every round-two label has a Chinese twin and no key is empty", () => {
  const keys = Object.keys(en).filter((k) => /^(deals\.(terms|timing|cost|card|cards|why|review|sort|group|view|controls|more|full|row|workspace)|customer\.(flow|review|others|otherTasks|explore|share|exposure\.compare)|appr\.(stage|lifecycle|summary|details|authority|list|quoted))/.test(k));
  assert.ok(keys.length > 40);
  for (const k of keys) {
    assert.ok(en[k].trim(), k);
    assert.ok(zh[k]?.trim(), `${k} has a Chinese twin`);
  }
});
