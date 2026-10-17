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
  assert.equal(a.supplier_cost_display, "¥3,035.99");
  const b = v.counters.find((c) => c.label === "Option B");
  assert.equal(b.supplier_cost_display, "¥0.00");
  // EX01 Option B is now 55-day terms at 0.30% (0.30% x 420,000.00 = 1,260.00 per invoice). fixtures/golden still holds the old
  // 60-day figure (counter_b_price_adj_per_invoice), so the new per-invoice figure is pinned here as the server wrote it.
  assert.ok(b.formula.includes("0.30% → ¥1,260.00 per invoice"));
  assert.equal(b.text, "55-day terms accepted with a 0.30% price adjustment on future invoices, no rebate.");
});

test("the EX01 verdict, the counters and the buyer turns are the live API's, as recorded", () => {
  const v = mock("verdict_ex01.json");
  assert.deepEqual(
    v.violations.map((x) => x.code),
    ["AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH", "DISCOUNT_ABOVE_BREAK_EVEN", "EARLY_PAY_DEARER_THAN_PLAN"],
  );
  assert.equal(
    v.counters.find((c) => c.label === "Option A").text,
    "Terms stay at 45 days, no rebate. We will accept early settlement on up to ¥260,000 of this invoice at 0.85%, paid on or before day 2.",
  );
  assert.ok(Array.isArray(v.passed_checks) && v.autonomy && v.annualised);
  // Leverage is one definition now (actual drawn debt): the pro forma is 1.47x and the inputs name the month, the debt and the basis.
  const lev = v.passed_checks.find((c) => c.inputs && "pro_forma_leverage" in c.inputs)?.inputs;
  assert.equal(lev.pro_forma_leverage, "1.47x");
  assert.equal(lev.pro_forma_leverage_month, "1");
  assert.ok(lev.pro_forma_leverage_debt && lev.pro_forma_leverage_basis);
  assert.ok(!("committed_line_limits" in lev), "committed line limits are no longer in the verdict inputs");
  assert.ok(v.summary.includes("LEVERAGE_MAX 1.47x"));
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
  assert.equal(f.committed.total_cost_display, "¥3,113.93");
  assert.equal(f.committed.costs.reduce((n, c) => n + c.fen, 0), f.committed.total_cost_fen);
  // The API's landing day is on the plan's cash-in actions: the line lands the same day, the invoice advance on day 3.
  assert.deepEqual(f.committed.actions.map((a) => [a.kind, a.lands_day]), [["DRAW", 0], ["FINANCE_INVOICE", 3]]);
  assert.equal(f.marginal.extension_expected_12m_fen, golden.extension_expected_12m);
  assert.equal(f.marginal.break_even_display, golden.break_even_discount_display);
  assert.equal(f.marginal.rate_display, golden.if_all_in_rate_display);

  const t = mock("trajectory_conservative.json").trajectory;
  assert.equal(t.first_breach_day, 47);
  assert.equal(t.days[20].closing_fen, golden.cash_day20);
  assert.equal(t.days[47].closing_fen, golden.cash_day47_60d_terms);
  assert.equal(t.days[47].closing_display, "¥209,960.00");

  const c = mock("capex.json");
  assert.equal(c.npv_fen, golden.capex.npv);
  assert.equal(c.payback_month, golden.capex.payback_month);
  const s36 = c.structures.find((s) => s.id === "loan_36m");
  assert.equal(s36.monthly_payment_display, "¥18,144.62");
  assert.equal(c.selected_id, "loan_36m");
  // The capex leverage inputs carry the month-end debt, the month and the basis; no committed line limits.
  const inputs = c.structures.flatMap((x) => x.workings).filter((w) => w.inputs && "Debt_m" in w.inputs).map((w) => w.inputs);
  assert.ok(inputs.length > 0 && inputs.every((i) => i.month && i.basis && !("committed_line_limits" in i)));
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
  assert.equal(transit[0].principal_display, "¥255,000.00");
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
  assert.equal(approved.decided_day, 34, "the API records the day of the decision");
  assert.ok(approved.result_message.includes("the cash lands on day 37"));
  assert.equal(pending.decided_day, null);
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

test("every term, clause and flag in the recorded document readings quotes its document exactly", () => {
  const docs = mock("documents.json");
  assert.deepEqual(Object.keys(docs), mock("contracts_fixtures.json").map((f) => f.id));
  for (const [id, r] of Object.entries(docs)) {
    for (const view of [r.seeded, r.reread, r.confirmed.document, r.rejected.document]) {
      const text = view.document.text;
      const spans = [...(view.terms ?? []), ...(view.clauses ?? []), ...view.flags];
      assert.ok(spans.length > 0, id);
      for (const s of spans) assert.equal(text.slice(s.span.start, s.span.end), s.quote, `${id}: ${s.quote}`);
      assert.equal(view.doc_hash, r.seeded.doc_hash, `${id}: one text throughout`);
    }
    // A new reading is labelled as AI output until the owner confirms it; confirming is a logged owner operation that writes no books.
    assert.equal(r.reread.id, "DOC-000004");
    assert.equal(r.reread.status, "PROPOSED");
    assert.equal(r.reread.ai_label, "AI-generated, for reference");
    assert.equal(r.reread.can_confirm, true);
    assert.equal(r.confirmed.result.kind, "CONFIRM_DOCUMENT");
    assert.equal(r.confirmed.result.status, "EXECUTED");
    assert.equal(r.confirmed.result.tier, "TIER_2");
    assert.equal(r.confirmed.result.seq, 4);
    assert.ok(r.confirmed.result.message.includes("nothing in the books changed"), id);
    assert.equal(r.confirmed.document.status, "CONFIRMED");
    assert.equal(r.confirmed.document.label, "Read by the agent, confirmed by you");
    assert.equal(r.rejected.result.kind, "REJECT_DOCUMENT");
    assert.equal(r.rejected.document.status, "REJECTED");
  }
});

test("each decision on a document carries the server's outcome card in both languages, with no id or reference code in its words", () => {
  const docs = mock("documents.json");
  const codes = /(?:DOC|RCV|COM|FAC|BUYER|BANK|PLATFORM|OFF|CTR|VER|APR)-|FHR-2026|MB-CL|GBR-IF|\bday \d|CONFIRMED|REJECTED|_AGREEMENT|_CONTRACT/;
  for (const [id, r] of Object.entries(docs)) {
    const kinds = ["confirmed", "rejected", ...(r.confirmed.document.linked_facility_id ? ["confirmed_unlinked"] : [])];
    assert.deepEqual(Object.keys(r.outcomes).sort(), kinds.sort(), id);
    for (const key of kinds) {
      for (const lang of ["en", "zh"]) {
        const o = r.outcomes[key][lang];
        const words = [o.title, o.changed.title, o.unchanged.title, ...o.changed.lines, ...o.unchanged.lines, ...(o.link ? [o.link.label] : [])];
        for (const w of words) assert.ok(w && !codes.test(w), `${id} ${key} ${lang}: ${w}`);
        assert.equal(o.tone, key === "rejected" ? "mute" : "ok", `${id} ${key}`);
        assert.ok(o.unchanged.lines.length > 0, `${id} ${key}: what did not change is said`);
        if (key === "rejected") assert.equal(o.link, null);
      }
      // The answer's own card is the English one (the Chinese is the same decision asked again with lang=zh).
      if (key !== "confirmed_unlinked") assert.deepEqual(r[key].outcome, r.outcomes[key].en, `${id} ${key}`);
    }
    assert.match(r.outcomes.confirmed.en.title, /^Filed under /);
    assert.match(r.outcomes.confirmed.zh.title, /^已归档到/);
  }
  // A buyer contract links to that buyer's record; a lender agreement says the facility it was linked to only when it was.
  assert.equal(docs.FHR_SUPPLY_AGREEMENT.outcomes.confirmed.en.link.href, "/customers/BUYER-1");
  assert.ok(docs.MB_CREDIT_LINE_AGREEMENT.outcomes.confirmed.en.changed.lines.some((l) => l.startsWith("It is linked to")));
  assert.ok(!docs.MB_CREDIT_LINE_AGREEMENT.outcomes.confirmed_unlinked.en.changed.lines.some((l) => l.includes("linked")));
});

test("the demo opens on the three demo documents confirmed by the owner, the first three ledger entries", () => {
  const docs = mock("documents.json");
  const seeded = mock("contracts_fixtures.json").map((f) => docs[f.id]);
  assert.deepEqual(seeded.map((r) => [r.seeded.id, r.seeded.status, r.seeded.decided_day, r.seeded.decided_seq]), [
    ["DOC-000001", "CONFIRMED", 0, 1],
    ["DOC-000002", "CONFIRMED", 0, 2],
    ["DOC-000003", "CONFIRMED", 0, 3],
  ]);
  for (const r of seeded) {
    assert.equal(r.seeded.label, "Read by the agent, confirmed by you");
    assert.deepEqual([r.seeded_operation.kind, r.seeded_operation.status, r.seeded_operation.tier, r.seeded_operation.requested_by], ["CONFIRM_DOCUMENT", "EXECUTED", "TIER_2", "OWNER"]);
    assert.ok(r.seeded_operation.message.includes(`Document ${r.seeded.id}`) && r.seeded_operation.message.includes("nothing in the books changed"));
  }
  // The rest of the story is recorded from the same starting point: the deal's first operation comes after the confirmations.
  assert.equal(mock("negotiation_nodeal.json").operations[0].seq, 4);
});

test("the demo documents read as the demo books: the supply agreement's terms and both lender agreements against their facilities", () => {
  const docs = mock("documents.json");
  const fhr = docs.FHR_SUPPLY_AGREEMENT.seeded;
  const term = (f) => fhr.terms.find((t) => t.field === f);
  assert.equal(term("PRICE").amount_display, "¥420,000.00");
  assert.deepEqual([term("PAYMENT_TERMS").days, term("PAYMENT_TERMS").basis], [45, "INVOICE"]);
  assert.deepEqual([term("EARLY_PAYMENT").rate_bp, term("EARLY_PAYMENT").days], [120, 2]);
  assert.deepEqual([term("INVOICING").days, term("INVOICING").day], [30, 2]);
  assert.deepEqual([term("SCHEDULED_INVOICE").reference, term("SCHEDULED_INVOICE").day], ["RCV-A", -13]);
  assert.deepEqual(fhr.blanks.map((b) => b.field), ["MILESTONE", "RETENTION", "LATE_INTEREST"]);
  for (const [id, facility] of [["MB_CREDIT_LINE_AGREEMENT", "FAC-LINE"], ["GBR_INVOICE_FINANCING_AGREEMENT", "FAC-IF"]]) {
    const view = docs[id].seeded;
    assert.equal(view.compared_with, facility, id);
    assert.equal(view.linked_facility_id, facility, id);
    assert.ok(view.comparison.length > 0 && view.comparison.every((r) => r.same), `${id} differs from ${facility}`);
    assert.equal(docs[id].confirmed.document.linked_facility_id, facility);
  }
  assert.equal(docs.GBR_INVOICE_FINANCING_AGREEMENT.seeded.facility.all_in_rate_display, "10.84%");
});

test("the deal summary: the confirmed contract once the buyer agrees, then the day-34 story as the prototype shows it", () => {
  const day0 = mock("deals_day0.json").deals.find((d) => d.counterparty_id === "BUYER-1");
  assert.equal(day0.has_contract, true);
  assert.equal(day0.contract.record_id, "DOC-000001");
  assert.deepEqual(day0.pills.map((p) => p.label), ["On track"]);
  assert.deepEqual(day0.changes.map((c) => c.label), ["You confirmed"]);
  assert.ok(mock("deals_day0.json").deals.filter((d) => d.counterparty_id !== "BUYER-1").every((d) => !d.has_contract));
  // Deals shows the summary only once both parties have agreed: the "Terms negotiated" stage done.
  const negotiated = (d) => d.stages.find((s) => s.key === "negotiated").state;
  assert.notEqual(negotiated(day0), "done");
  const agreed = mock("deals_day0_agreed.json").deals.find((d) => d.counterparty_id === "BUYER-1");
  assert.equal(negotiated(agreed), "done");
  assert.ok(agreed.changes.some((c) => c.label === "Buyer accepted"));
  // Read again and confirmed: the deal follows the reading confirmed last.
  const again = mock("deals_day0_reconfirmed.json").deals.find((d) => d.counterparty_id === "BUYER-1");
  assert.equal(again.contract.record_id, "DOC-000004");
  const deal = mock("deals_day34_pending.json").deals.find((d) => d.counterparty_id === "BUYER-1");
  assert.deepEqual(deal.pills.map((p) => p.label), ["Payment overdue", "1 approval waiting"]);
  assert.deepEqual(deal.stages.map((s) => s.state), ["done", "done", "done", "now", "todo"]);
  assert.ok(deal.changes.some((c) => c.label === "Buyer accepted" && c.text.includes(fmtYuan(golden.counter_a_face))));
  const rcvA = deal.invoices.find((i) => i.id === "RCV-A");
  assert.deepEqual([rcvA.status, rcvA.outstanding_display, rcvA.status_text], ["LATE", "¥160,000.00", "2 days late"]);
  assert.equal(deal.invoices.find((i) => i.status === "ADVANCE_WAITING").label, "Invoice issued 32 days ago");
  // The sentence says the approval in words; the ids stay in their own fields.
  assert.ok(deal.next_action.text.includes("advance on the invoice issued 32 days ago"));
  assert.ok(!/(APR|RCV|OFF|DOC|VER)-/.test(deal.next_action.text));
  assert.ok(deal.checks.every((c) => c.status === "ok"));
  assert.equal(deal.owed_by_us.display_only, true);
  // Before the button the cure is not queued; after the owner approves it the invoice is financed.
  assert.deepEqual(mock("deals_day34_open.json").deals[0].pills.map((p) => p.label), ["Payment overdue"]);
  assert.equal(mock("deals_day34_approved.json").deals[0].invoices.find((i) => i.label === "Invoice issued 32 days ago").status, "FINANCED");
});
