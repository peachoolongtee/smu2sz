"""E3/E10 financial exactness: every value in fixtures/golden/golden_values.json, recomputed through the
modules' public interfaces (engine, router, verifier, covenants, capex), compared to the fen.

The golden file is written by an independent oracle (fixtures/golden/compute_golden.py); nothing here
reads a golden value to compute another one, except to choose *which* module output to read.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from evals.common import Failure, Metric, SuiteResult, quiet, ratio

REPRO = "uv run --project services/api python scripts/evaluate.py --suite financial"


def _fen(display: str) -> int:
    """'¥207,123.29' or '−¥50,000.00' -> fen."""
    s = display.replace("−", "-").replace("¥", "").replace(",", "").strip()
    neg = s.startswith("-")
    whole, _, frac = s.lstrip("-").partition(".")
    v = int(whole) * 100 + int((frac + "00")[:2])
    return -v if neg else v


def _x(text: str) -> str:
    return re.sub(r"x$", "", text.strip())


def _flatten(d: dict, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        else:
            out[key] = v
    return out


def compute() -> dict[str, tuple[Any, str]]:
    """{golden key: (value computed by the modules, which module produced it)}."""
    from app.capex import CapexRequest, evaluate_capex
    from app.compiler import compile_offer
    from app.covenants import pro_forma
    from app.domain.fixtures import load_scenario, offer_documents
    from app.domain.models import (
        BaseKind,
        Contingency,
        Duration,
        DurationKind,
        FacilityKind,
        FacilityStatus,
        FundingAction,
        FundingActionKind,
        Mode,
        Obligation,
        ObligationBase,
        ObligationType,
        SourceSpan,
        ViolationCode,
    )
    from app.domain.money import fmt_pct, round_half_up
    from app.financial import project, value_concessions
    from app.funding import (
        all_in_rate,
        break_even_discount,
        compare,
        extension_cost_bases,
        marginal_cost,
        plan,
    )
    from app.mandate import demo_owner_public_key_hex, load_signed_mandate
    from app.verifier import evaluate

    state, _ = load_scenario()
    m = load_signed_mandate()
    key = demo_owner_public_key_hex()
    H = m.horizon_days
    out: dict[str, tuple[Any, str]] = {}

    def put(k: str, fn: Callable[[], Any], src: str) -> None:
        try:
            out[k] = (fn(), src)
        except Exception as e:  # noqa: BLE001 - a crash is a miss, reported with its reason
            out[k] = (f"ERROR {type(e).__name__}: {e}", src)

    # router (spec §7.4)
    p = plan(state, [], m)
    costs = {c.facility_id: c.fen for c in p.costs}
    put("v2_optimum_total", lambda: p.total_cost_fen, "funding.plan().total_cost_fen")
    put("funding_need_before_day_32", lambda: p.need_fen, "funding.plan().need_fen")
    put("line_interest_150k_32d", lambda: costs["FAC-LINE"], "funding.plan().costs[FAC-LINE]")
    put("if_cost_plan_advance", lambda: costs["FAC-IF"], "funding.plan().costs[FAC-IF]")
    put("plan_advance", lambda: next(a.amount_fen for a in p.actions if a.kind == FundingActionKind.FINANCE_INVOICE),
        "funding.plan() FINANCE_INVOICE amount")
    # existing debt is cash (FINANCIAL_SEMANTICS §5): D-EQUIP's scheduled payments in the baseline projection
    t0 = project(state, [], [], Mode.CONSERVATIVE, H)
    debt_days = [(pt.day, -sum(e.amount_fen for e in pt.events if e.ref == "D-EQUIP")) for pt in t0.days]
    put("debt_service_day30", lambda: dict(debt_days)[30], "financial.project() day 30 D-EQUIP events")
    put("debt_payments_to_day120", lambda: [d for d, a in debt_days if a and d <= 120],
        "financial.project() days with D-EQUIP events")
    rows = {r.key: r for r in compare(state, [], m)}
    put("full_discount_1_2pct", lambda: rows["full_discount"].cost_fen, "funding.compare() full_discount")
    put("v1_optimum_total", lambda: rows["line_partial_early_pay"].cost_fen, "funding.compare() line_partial_early_pay")
    v1_ep = next(a for a in rows["line_partial_early_pay"].actions if a.kind == FundingActionKind.EARLY_PAY)
    put("v1_partial_face", lambda: v1_ep.amount_fen, "funding.compare() early-pay face")
    put("v1_partial_discount",
        lambda: project(state, [], [v1_ep], Mode.CONSERVATIVE, H).discounts_posted_fen,
        "financial.project(early-pay face).discounts_posted_fen")

    # break-even and rates
    d, be_bp = break_even_discount(state, m)
    rate, _ = marginal_cost(state, m)
    put("break_even_discount_bp", lambda: be_bp, "funding.break_even_discount()")
    put("break_even_discount_display", lambda: fmt_pct(d.value), "funding.break_even_discount()")
    put("if_30d_cost_share_bp_x100", lambda: round_half_up(rate.value * 30 / 365 * 1_000_000),
        "funding.marginal_cost() × 30/365")
    fac_if = next(f for f in state.facilities if f.kind == FacilityKind.INVOICE_FINANCING)
    put("if_all_in_rate_display", lambda: fmt_pct(all_in_rate(fac_if)[0], 4), "funding.all_in_rate(FAC-IF)")

    # terms extension priced as a loan (spec §7.5)
    span = [SourceSpan(doc_id="EVAL", start=0, end=0, text="")]
    ext = Obligation(id="EVAL-EXT", type=ObligationType.TERMS_EXTENSION, counterparty_id="BUYER-1", days_delta=15,
                     effective_day=0, base=ObligationBase(kind=BaseKind.FUTURE_INVOICES),
                     contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.RECURRING_PERPETUAL),
                     spans=span, confidence=1.0)
    bases = extension_cost_bases(state, ext, m)
    notional, committed = bases[0], bases[1]
    expected = bases[2] if len(bases) > 2 else None
    put("extension_notional_line_12m", lambda: notional.value_fen, "funding.extension_cost_bases()[notional]")
    put("extension_notional_line_per_invoice", lambda: notional.per_invoice_fen, "funding.extension_cost_bases()[notional]")
    put("extension_committed_12m", lambda: committed.value_fen, "funding.extension_cost_bases()[committed]")
    put("extension_committed_per_invoice", lambda: committed.per_invoice_fen, "funding.extension_cost_bases()[committed]")
    put("extension_expected_12m", lambda: expected.value_fen if expected else None,
        "funding.extension_cost_bases()[expected]")
    shortening = ext.model_copy(update={"id": "EVAL-SHORT", "days_delta": -15})
    put("extension_shortening_gain_12m",
        lambda: value_concessions([shortening], state, rate, "eval", m.forward_concession_horizon_days)[0].value_fen,
        "financial.value_concessions(shortening): the mirror of the extension")

    # EX01 through the compiler (cache) and the verifier (spec §6.5, §7.6)
    ex01 = compile_offer(offer_documents("EX01_PACKAGE"), "BUYER-1")
    b1 = evaluate(ex01, state, m, trusted_owner_key_hex=key)
    v1 = b1.verdict
    rebate = next(o for o in b1.bound_obligations if o.type == ObligationType.CONTINGENT_REBATE)
    put("rebate_max", lambda: next(cv.value_fen for cv in v1.concession_values if cv.obligation_id == rebate.id),
        "verifier EX01 concession_values[rebate]")
    put("forward_ledger_total", lambda: v1.forward_concession_total_fen, "verifier EX01 forward_concession_total_fen")
    put("concession_cap", lambda: m.max_aggregate_forward_concession_fen, "signed mandate")
    traj = b1.trajectory
    assert traj is not None
    put("cash_day20", lambda: traj.days[20].closing_fen, "verifier EX01 trajectory day 20")
    put("cash_day47_60d_terms", lambda: traj.days[47].closing_fen, "verifier EX01 trajectory day 47")
    put("cash_day60_60d_terms", lambda: traj.days[60].closing_fen, "verifier EX01 trajectory day 60")
    no_ext = [o for o in b1.bound_obligations if o.type != ObligationType.TERMS_EXTENSION]
    put("cash_day47_45d_terms",
        lambda: project(state, no_ext, [], Mode.CONSERVATIVE, H, m.min_cash_fen).days[47].closing_fen,
        "financial.project(EX01 without the extension) day 47")
    rb = next(v for v in v1.violations if v.code == ViolationCode.RESERVE_BREACH)
    put("reserve_shortfall_day47", lambda: int(rb.inputs["shortfall_fen"]), "verifier EX01 RESERVE_BREACH shortfall")
    put("reserve_shortfall_max", lambda: _fen(rb.inputs["max_shortfall"]), "verifier EX01 RESERVE_BREACH max_shortfall")
    put("reserve_cure_cost_if", lambda: rb.cure_cost_fen, "verifier EX01 RESERVE_BREACH cure_cost_fen")
    dscr_chk = next(pc for pc in b1.passed_checks if pc.code == "DSCR_MIN")
    lev_chk = next(pc for pc in b1.passed_checks if pc.code == "LEVERAGE_MAX")
    put("extension_extra_receivables", lambda: _fen(dscr_chk.inputs["extra_receivables"]),
        "verifier EX01 pro-forma extra_receivables")
    put("extension_monthly_service", lambda: _fen(dscr_chk.inputs["extra_monthly_debt_service"]),
        "verifier EX01 pro-forma extra_monthly_debt_service")
    put("dscr_after_extension", lambda: _x(dscr_chk.observed), "verifier EX01 DSCR_MIN pro forma")
    put("leverage_after_extension", lambda: _x(lev_chk.observed), "verifier EX01 LEVERAGE_MAX pro forma")
    line_limit = sum(f.limit_fen for f in state.facilities
                     if f.kind == FacilityKind.CREDIT_LINE and f.status == FacilityStatus.COMMITTED)
    dscr_b, lev_b = pro_forma(state, base_extra_debt_fen=line_limit)
    put("dscr_base", lambda: dscr_b.text if dscr_b else None, "covenants.pro_forma(state + committed line)")
    put("leverage_base", lambda: lev_b.text, "covenants.pro_forma(state + committed line)")
    line_drawn = FundingAction(kind=FundingActionKind.DRAW, facility_id="FAC-LINE", day=0, amount_fen=line_limit,
                               repay_day=45)
    put("leverage_month1_line_drawn",
        lambda: project(state, [], [line_drawn], Mode.CONSERVATIVE, H).months[0].leverage.text,
        "financial.project(line drawn) month 1 leverage")

    # counters (spec §6.6)
    opt = {c.label: c for c in v1.counters}
    a = opt["Option A"]
    put("counter_a_total", lambda: a.supplier_cost_fen, "verifier EX01 Option A supplier_cost_fen")
    put("counter_a_face", lambda: next(o.base.amount_fen for o in a.obligations
                                       if o.type == ObligationType.IMMEDIATE_DISCOUNT),
        "verifier EX01 Option A early-settlement face")
    put("counter_a_discount",
        lambda: project(state, list(a.obligations), [], Mode.CONSERVATIVE, H).discounts_posted_fen,
        "financial.project(Option A).discounts_posted_fen")
    pa = next(o for o in opt["Option B"].obligations if o.type == ObligationType.PRICE_ADJUSTMENT)
    put("counter_b_price_adj_per_invoice",
        lambda: -value_concessions([pa], state, rate, "eval", m.forward_concession_horizon_days)[0].per_invoice_fen,
        "financial.value_concessions(Option B price adjustment).per_invoice_fen")
    put("counter_b_price_gain_12m",
        lambda: value_concessions([pa], state, rate, "eval", m.forward_concession_horizon_days)[0].value_fen,
        "financial.value_concessions(Option B price adjustment): the same 13 invoices as the extension")
    put("counter_b_net_12m",
        lambda: sum(cv.value_fen for cv in value_concessions(
            list(opt["Option B"].obligations), state, rate, "eval", m.forward_concession_horizon_days)),
        "financial.value_concessions(Option B): extension + price adjustment, unfloored")

    # EX02: line + partial early pay at the offered 1.5%
    ex02 = compile_offer(offer_documents("EX02_EARLY_1_5"), "BUYER-1")
    b2 = evaluate(ex02, state, m, trusted_owner_key_hex=key)
    put("example2_line_plus_partial_1_5pct",
        lambda: next(r.cost_fen for r in b2.comparison if r.key == "line_partial_early_pay"),
        "verifier EX02 comparison line_partial_early_pay")

    # capex (spec §7.7)
    cap = evaluate_capex(CapexRequest(), state, m)
    by = {s.id: s for s in cap.structures}
    for sid in ("loan_18m", "loan_36m", "lease_48m"):
        s = by[sid]
        put(f"capex.{sid}.monthly_payment", lambda s=s: s.monthly_payment_fen, "capex.evaluate_capex()")
        put(f"capex.{sid}.total_interest", lambda s=s: s.total_interest_fen, "capex.evaluate_capex()")
        put(f"capex.{sid}.dscr_m1_3", lambda s=s: _x(s.dscr_by_month[0].dscr.text), "capex.evaluate_capex() month 1")
        put(f"capex.{sid}.dscr_m4_on", lambda s=s: _x(s.dscr_by_month[3].dscr.text), "capex.evaluate_capex() month 4")
        put(f"capex.{sid}.dscr_m1_3_passes", lambda s=s: bool(s.dscr_by_month[0].passes), "capex.evaluate_capex()")
    put("capex.lease_minus_36m_interest",
        lambda: by["lease_48m"].total_interest_fen - by["loan_36m"].total_interest_fen, "capex.evaluate_capex()")
    put("capex.selected", lambda: cap.selected_id, "capex.evaluate_capex().selected_id")
    put("capex.npv", lambda: cap.npv_fen, "capex.evaluate_capex()")
    put("capex.payback_month", lambda: cap.payback_month, "capex.evaluate_capex()")
    put("capex.leverage_financed", lambda: _x(cap.leverage_financed.text), "capex.evaluate_capex()")
    put("capex.leverage_financed_plus_extension", lambda: _x(cap.leverage_with_extension.text),
        "capex.evaluate_capex()")
    cash_line = next(s for s in cap.structures if s.kind == "CASH_LINE")
    put("capex.cash_above_reserve", lambda: _fen(cash_line.violations[0].inputs["available_above_reserve"]),
        "capex.evaluate_capex() cash+line violation")
    return out


def run(**_: Any) -> SuiteResult:
    quiet()
    from app.domain.fixtures import golden_values

    golden = _flatten(golden_values())
    got = compute()
    res = SuiteResult(name="financial")
    rows = []
    exact = 0
    for k in sorted(golden):
        want = golden[k]
        value, src = got.get(k, (None, "not computed"))
        ok = value == want
        exact += ok
        rows.append({"key": k, "golden": want, "computed": value, "source": src, "exact": ok})
        if not ok:
            res.failures.append(Failure("financial", k, f"{k}: computed {value!r} != golden {want!r} ({src})", REPRO))
    extra = sorted(set(got) - set(golden))
    total = len(golden)
    res.details = {"rows": rows, "computed_not_in_golden": extra}
    rate = ratio(exact, total)
    res.metrics.append(Metric("financial_exactness", "Financial exactness (golden values, to the fen)", rate,
                              f"{exact}/{total} ({(rate or 0):.1%})", "100%", exact == total, "financial"))
    capex_keys = [r for r in rows if r["key"].startswith("capex.") or "dscr" in r["key"] or "leverage" in r["key"]]
    ce = sum(r["exact"] for r in capex_keys)
    res.metrics.append(Metric("e10_covenant_capex_exactness", "E10 covenant + capex golden values", ratio(ce, len(capex_keys)),
                              f"{ce}/{len(capex_keys)}", "100%", ce == len(capex_keys), "financial"))
    return res
