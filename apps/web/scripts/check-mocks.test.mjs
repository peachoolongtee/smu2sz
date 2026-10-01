// Guards the mocks against drift: every span matches its document, and the headline figures on screen
// are exactly the server-formatted golden values. Run: pnpm test:unit
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
  assert.equal(v.forward_concession_total_display, "¥26,455.62");
  assert.equal(v.forward_concession_total_display, fmtYuan(golden.forward_ledger_total));
  const reserve = v.violations.find((x) => x.code === "RESERVE_BREACH");
  assert.equal(reserve.day, 47);
  assert.equal(reserve.observed, fmtYuan(golden.cash_day47_60d_terms));
  assert.equal(reserve.cure_cost_fen, golden.reserve_cure_cost_if);
  const a = v.counters.find((c) => c.id === "CTR-A");
  assert.equal(a.supplier_cost_fen, golden.counter_a_total);
  assert.equal(a.supplier_cost_display, "¥2,642.24");
  assert.equal(v.counters.find((c) => c.id === "CTR-B").obligations[1].amount_fen, golden.counter_b_price_adj_per_invoice);
});

test("funding, trajectory and capex mocks match the golden values", () => {
  const f = mock("funding.json");
  assert.equal(f.committed.total_cost_fen, golden.v2_optimum_total);
  assert.equal(f.committed.total_cost_display, "¥2,712.94");
  assert.equal(f.committed.costs.reduce((n, c) => n + c.fen, 0), f.committed.total_cost_fen);
  assert.equal(f.expected.costs.reduce((n, c) => n + c.fen, 0), golden.extension_expected_12m);
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
});
