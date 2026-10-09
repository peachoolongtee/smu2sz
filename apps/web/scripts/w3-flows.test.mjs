// Wave 3 (map #65): the chart's day label, the comparison contract and the Activity causality in the recorded answers. Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { dayLabelCandidates } from "../lib/chart-helpers.ts";

const read = (name) => JSON.parse(readFileSync(fileURLToPath(new URL(`../mocks/${name}`, import.meta.url)), "utf8"));
const ev = (kind, label, fen, short) => ({ kind, label, label_short: label, amount_fen: fen, amount_display: short, amount_short: short });
const row = (events, net) => ({ day: 47, cash: 63500000, events, netFen: net?.[0] ?? null, netDisplay: net?.[1] ?? null, netShort: net?.[1] ?? null });

test("a day with one event is labelled by that event", () => {
  const c = dayLabelCandidates(row([ev("FLOW", "Payroll", -34000000, "−¥340k")], [-34000000, "−¥340k"]), "Net");
  assert.equal(c.length, 1);
  assert.equal(c[0].e.label, "Payroll");
});

test("a day with several events is labelled by the server's net, never by its largest component", () => {
  const events = [ev("RECEIPT", "Receipt from Foshan", 42000000, "¥420k"), ev("FLOW", "Operating bill", -10000000, "−¥100k")];
  const c = dayLabelCandidates(row(events, [32000000, "¥320k"]), "Net");
  assert.equal(c.length, 1);
  assert.equal(c[0].e.label, "Net");
  assert.equal(c[0].e.amount_short, "¥320k");
  assert.equal(c[0].e.amount_fen, 32000000);
  // The bill is the largest outflow but the day is a net inflow: no candidate may name it as the day's label.
  assert.ok(!c.some((x) => x.e.label === "Operating bill"));
});

test("a net that has the sign of the smaller event still labels the day by the net", () => {
  const events = [ev("RECEIPT", "Receipt", 10000000, "¥100k"), ev("FLOW", "Payroll", -34000000, "−¥340k")];
  const c = dayLabelCandidates(row(events, [-24000000, "−¥240k"]), "Net");
  assert.deepEqual(c.map((x) => [x.e.label, x.e.amount_short]), [["Net", "−¥240k"]]);
});

test("without a net (an older recording) each event stays its own candidate; a day with no mover has none", () => {
  const events = [ev("RECEIPT", "Receipt", 42000000, "¥420k"), ev("FLOW", "Operating bill", -10000000, "−¥100k")];
  assert.equal(dayLabelCandidates(row(events, null), "Net").length, 2);
  assert.equal(dayLabelCandidates(row([ev("INTEREST", "Interest", -100, "−¥1")], [-100, "−¥1"]), "Net").length, 0);
});

test("the recorded forecast: every day with several events carries the server's net", () => {
  for (const file of ["home_summary_day0.json", "home_summary_day34.json", "home_summary_after.json"]) {
    const cash = read(file).cash;
    assert.ok(cash.forecast_basis_text, file);
    for (const r of [...cash.series, ...(cash.plan_series ?? [])]) {
      assert.equal(typeof r.net_short, "string", `${file} day ${r.day}`);
      assert.equal(typeof r.net_display, "string");
    }
    assert.ok(cash.series.some((r) => r.events.length > 1), `${file} has a multi-event day`);
  }
});

test("the recorded comparison: the server's groups in its order, a rank only where it ranked", () => {
  for (const file of ["funding.json", "funding_day34.json"]) {
    const plan = read(file);
    assert.ok(plan.comparison_order_text, file);
    const order = ["RECOMMENDED", "ALTERNATIVE", "CONDITIONAL_ON_BUYER", "INSUFFICIENT", "NOT_AVAILABLE_YET", "BLOCKED"];
    const groups = plan.comparison.map((r) => order.indexOf(r.group));
    assert.deepEqual(groups, [...groups].sort((a, b) => a - b), `${file}: groups arrive in the server's order`);
    for (const r of plan.comparison) {
      const ranked = r.group === "RECOMMENDED" || r.group === "ALTERNATIVE";
      assert.equal(r.rank !== null, ranked, `${file} ${r.key}: rank only for the plans that can run now`);
      assert.ok(r.arrival_text, `${file} ${r.key}`);
      if (r.group === "CONDITIONAL_ON_BUYER") assert.ok(r.consent_text);
    }
    // The ranks run 1, 2, ... in the order sent.
    const ranks = plan.comparison.filter((r) => r.rank !== null).map((r) => r.rank);
    assert.deepEqual(ranks, ranks.map((_, i) => i + 1));
  }
});

test("the recorded ledger: causality on every row, the chain words and the refusal block", () => {
  for (const file of ["home_ledger_day34.json", "home_ledger_approved.json"]) {
    const l = read(file);
    assert.equal(l.chain_text, "Record chain checks passed");
    assert.match(l.chain_scope_text, /does not confirm bank facts or buyer promises/);
    assert.equal(l.refusals.anchor_id, "activity-refused");
    assert.equal(l.refusals.href, "/activity#activity-refused");
    for (const o of l.operations) {
      assert.ok(o.what_changed, `${file} ${o.kind}`);
      if (o.why_it_matters_as_of) assert.equal(o.why_it_matters_as_of, "now");
    }
  }
  const approved = read("home_ledger_approved.json").operations.filter((o) => o.kind === "SUBMIT_INVOICE_FOR_FINANCING");
  const asked = approved.find((o) => o.status === "PENDING_APPROVAL");
  assert.equal(asked.approval_label, "Approval requested");
  assert.ok(asked.current_decision_state);
  assert.match(asked.decision_link.href, /^\/decisions\//);
});

test("the recorded Deals workspace: the sections in the server's order, the immediate discount apart from the forward total", () => {
  const w = read("verdict_ex01.json").workspace;
  // Wave 7: the buyer, what FLOW recommends and the priced response come first; the agreements sit before the folded details.
  assert.deepEqual(w.order, ["buyer", "recommends", "priced_response", "buyer_asks", "financial_impact", "why_it_matters", "agreements", "advanced"]);
  const immediate = w.financial_impact.lines.filter((l) => l.horizon === "IMMEDIATE");
  const forward = w.financial_impact.lines.filter((l) => l.horizon === "FORWARD");
  assert.equal(immediate.length, 1);
  assert.equal(immediate[0].type, "IMMEDIATE_DISCOUNT");
  assert.ok(forward.length >= 1);
  assert.equal(w.financial_impact.forward_total_display, "¥28,326.92");
  assert.notEqual(w.financial_impact.forward_total_display, immediate[0].amount_display);
  assert.ok(w.priced_response.send_scope);
  assert.ok(w.priced_response.send_scope_lines.length >= 2, "the send says what it will do, one line each");
  assert.deepEqual(Object.keys(w.advanced.keys), ["parsed_obligations", "source_text", "checks", "formula", "engine_verdict", "audit_evidence"]);
});
