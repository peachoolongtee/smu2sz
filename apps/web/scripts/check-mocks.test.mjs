// Guards the recorded mocks (scripts/record-mocks.mjs): every span matches its document, and the headline figures on
// screen are exactly the server-formatted golden values. The mocks are read as recorded; nothing here edits them.
// Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { fmtYuan } from "./mock-format.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const mock = (n) => JSON.parse(readFileSync(join(here, "..", "mocks", n), "utf8"));
const golden = JSON.parse(readFileSync(join(here, "..", "..", "..", "fixtures", "golden", "golden_values.json"), "utf8"));

test("every span in every mock offer matches its document text exactly", () => {
  for (const f of ["offer_ex01.json", "offer_ex01b.json", "offer_sec.json"]) {
    const { offer, documents } = mock(f);
    const docs = Object.fromEntries(documents.map((d) => [d.doc_id, d.text]));
    const spans = [
      ...offer.obligations.flatMap((o) => o.spans),
      ...offer.data_requests.map((d) => d.span),
      ...offer.authority_claims.map((d) => d.span),
      ...offer.funding_claims.map((d) => d.span),
    ];
    assert.ok(spans.length > 0, f);
    for (const s of spans) assert.equal(docs[s.doc_id].slice(s.start, s.end), s.text, `${f}: ${s.text}`);
  }
});

test("verdict figures are the golden values, server-formatted", () => {
  const v = mock("verdict_ex01.json");
  assert.equal(v.outcome, "REJECT");
  assert.equal(v.forward_concession_total_display, "¥28,326.92");
  assert.equal(v.forward_concession_total_display, fmtYuan(golden.forward_ledger_total));
  const reserve = v.violations.find((x) => x.code === "RESERVE_BREACH");
  assert.equal(reserve.day, 47);
  assert.equal(reserve.observed, fmtYuan(golden.cash_day47_60d_terms));
  assert.equal(reserve.cure_cost_fen, golden.reserve_cure_cost_if);
  // Counter ids are the server's (CTR-<hash>), so the cards are found by label.
  const a = v.counters.find((c) => c.label === "Option A");
  assert.equal(a.supplier_cost_fen, golden.counter_a_total);
  assert.equal(a.supplier_cost_display, "¥2,642.24");
  const b = v.counters.find((c) => c.label === "Option B");
  assert.equal(b.supplier_cost_display, "¥0.00");
  assert.ok(b.formula.includes(`${fmtYuan(golden.counter_b_price_adj_per_invoice)} per invoice`));
});

test("the EX01 verdict, the counters and the buyer turns are the live API's, as recorded", () => {
  const v = mock("verdict_ex01.json");
  assert.deepEqual(
    v.violations.map((x) => x.code),
    ["AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH", "DISCOUNT_ABOVE_BREAK_EVEN", "EARLY_PAY_DEARER_THAN_PLAN"],
  );
  assert.equal(
    v.counters.find((c) => c.label === "Option A").text,
    "Terms stay at 45 days, no rebate. We will accept early settlement on up to ¥211,900 of this invoice at 0.85%.",
  );
  assert.ok(Array.isArray(v.passed_checks) && v.autonomy && v.annualised);
  // The EX01B rewording reaches the same verdict, and a buyer's turn in the chat script carries no verdict.
  assert.deepEqual(mock("verdict_ex01b.json").violations.map((x) => x.code), v.violations.map((x) => x.code));
  const script = mock("nl_script.json");
  for (const k of ["fastcapital", "buyer_ex02", "buyer_rebate", "buyer_extraction", "buyer_extraction_zh", "buyer_injection_zh"]) {
    assert.equal(script[k].verdict, null, k);
    assert.deepEqual(script[k].operations, [], k);
  }
});

test("funding, trajectory and capex mocks match the golden values", () => {
  const f = mock("funding.json");
  assert.equal(f.committed.total_cost_fen, golden.v2_optimum_total);
  assert.equal(f.committed.total_cost_display, "¥2,712.94");
  assert.equal(f.committed.costs.reduce((n, c) => n + c.fen, 0), f.committed.total_cost_fen);
  assert.equal(f.marginal.extension_expected_12m_fen, golden.extension_expected_12m);
  assert.equal(f.marginal.break_even_display, golden.break_even_discount_display);
  assert.equal(f.marginal.rate_display, golden.if_all_in_rate_display);

  const t = mock("trajectory_conservative.json").trajectory;
  assert.equal(t.first_breach_day, 47);
  assert.equal(t.days[20].closing_fen, golden.cash_day20);
  assert.equal(t.days[47].closing_fen, golden.cash_day47_60d_terms);
  assert.equal(t.days[47].closing_display, "¥254,960.00");

  const c = mock("capex.json");
  assert.equal(c.npv_fen, golden.capex.npv);
  assert.equal(c.payback_month, golden.capex.payback_month);
  const s36 = c.structures.find((s) => s.id === "loan_36m");
  assert.equal(s36.monthly_payment_display, "¥18,144.62");
  assert.equal(c.selected_id, "loan_36m");
});

test("alerts and reconciliation mocks are the recorded server output for the opening books", () => {
  const a = mock("alerts.json");
  assert.equal(a.counts.CRITICAL, 1);
  assert.equal(a.alerts[0].day, 12);
  assert.equal(a.alerts[0].amount_fen, 24000000);
  assert.equal(a.alerts[0].amount_display, fmtYuan(24000000));
  assert.ok(a.alerts[0].suggested.every((s) => s.executes_automatically === false));
  // The suggestions are the cure from the funded facilities: the line, then invoice financing for the rest.
  assert.deepEqual(a.alerts[0].suggested.map((s) => s.operation_kind), ["DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"]);

  const r = mock("reconciliation.json");
  assert.equal(r.receipts.length, 0);
  assert.equal(r.outstanding[0].receivable_id, "RCV-A");
  assert.equal(r.outstanding[0].face_display, "¥420,000.00");
  assert.equal(r.chain_valid, true);
  // The promised early payments the API now returns: none on the opening books.
  assert.deepEqual(r.promised, []);
  assert.equal(r.lapsed_promises, 0);
});

test("funding lands later: the day-0 plan leaves the advance in transit, cash is only what has landed", () => {
  const state = mock("state_after_fund.json").state;
  const lots = state.lots;
  assert.ok(lots.length >= 2);
  const transit = lots.filter((l) => !l.settled);
  assert.equal(transit.length, 1);
  assert.equal(transit[0].facility_id, "FAC-IF");
  assert.equal(transit[0].request_day, 0);
  assert.equal(transit[0].arrival_day, 3);
  assert.equal(transit[0].principal_display, "¥210,000.00");
  assert.equal(state.cash_display, "¥550,000.00");
  const reply = mock("nl_script.json").fund_gap_go.reply;
  assert.ok(reply.includes("Cash in now") && reply.includes("Still to land") && reply.includes("lands on day 3"));
});

test("the day-34 cure waits for the owner: PENDING_APPROVAL, then EXECUTED on approval, cash on day 37", () => {
  const act = mock("home_act.json");
  assert.equal(act.results[0].status, "PENDING_APPROVAL");
  assert.equal(act.cured, false);
  assert.equal(act.pending_approval, 1);
  assert.match(act.results[0].approval_id, /^APR-/);
  const alert = mock("home_alerts_day34.json").alerts.find((a) => a.id.startsWith("ALERT-RESERVE"));
  assert.equal(alert.suggested[0].above_apr_cap, true);
  assert.equal(alert.suggested[0].cost_display, "¥1,782.19");
  const pending = mock("home_approval_pending.json");
  assert.equal(pending.status, "PENDING");
  assert.equal(pending.id, act.results[0].approval_id);
  assert.ok(pending.op_id.startsWith(`alert:${alert.id}:`));
  const approved = mock("home_approval_approved.json");
  assert.equal(approved.status, "APPROVED");
  assert.equal(approved.decided_day, null, "the API does not record the day of a decision");
  const done = mock("home_approve.json").operations[0];
  assert.equal(done.status, "EXECUTED");
  assert.ok(done.message.includes("the cash lands on day 37"));
  const after = mock("home_alerts_after.json");
  assert.ok(!after.alerts.some((a) => a.id.startsWith("ALERT-RESERVE")));
  const transit = after.alerts.find((a) => a.kind === "FUNDING_IN_TRANSIT");
  assert.equal(transit.severity, "INFO");
  assert.equal(transit.actionable, false);
  assert.equal(transit.day, 37);
  const lot = mock("home_state_after_approve.json").state.lots.find((l) => !l.settled);
  assert.equal(lot.arrival_day, 37);
});
