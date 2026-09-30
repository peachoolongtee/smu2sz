"""Covenant and mandate boundaries: exact, one fen (or one bp / one day) on the safe side, one on the unsafe
side. The limit must hold at exactly the threshold and break one unit past it.

DSCR, leverage, the reserve floor, the concession cap and the immediate-discount cap go through
`verifier.evaluate` with a typed offer on a modified golden state. Clean-down goes through
`financial.project` + `covenants.evaluate` (a line draw/repay pattern; the verifier only sees clean-down
through the router's own plans).
"""

from __future__ import annotations

from typing import Any

from evals.common import Failure, Metric, SuiteResult, quiet, ratio
from evals.forms import doc, form_offer

REPRO = "uv run --project services/api python scripts/evaluate.py --suite covenants"
CASH_NO_GAP = 80_000_000  # ¥800,000: the golden day-12 gap disappears, so no funding plan enters the months
REBATE_2000 = [{"type": "CONTINGENT_REBATE", "rate_bp": 50, "base_amount_fen": 40_000_000}]  # ¥2,000, under the cap


def _state_with(state: Any, **kw: Any) -> Any:
    upd: dict[str, Any] = {}
    if "cash_fen" in kw:
        upd["cash_fen"] = kw["cash_fen"]
    if "debt_service_fen" in kw or "principal_fen" in kw:
        debts = [d.model_copy(update={k: v for k, v in (("monthly_debt_service_fen", kw.get("debt_service_fen")),
                                                        ("principal_fen", kw.get("principal_fen"))) if v is not None})
                 for d in state.debts]
        upd["debts"] = debts
    return state.model_copy(update=upd)


def verifier_cases() -> list[dict[str, Any]]:
    """(id, state change, offer labels, code, expect_violation)."""
    out: list[dict[str, Any]] = []
    # DSCR = EBITDA 90,000 / DS; exactly 1.25x at DS = ¥72,000.00. More debt service is the unsafe side.
    for tag, ds, bad in (("exact", 7_200_000, False), ("safe_1fen", 7_199_999, False), ("unsafe_1fen", 7_200_001, True)):
        out.append({"id": f"dscr_{tag}", "group": "DSCR", "state": {"cash_fen": CASH_NO_GAP, "debt_service_fen": ds},
                    "offer": REBATE_2000, "code": "DSCR_BREACH", "violation": bad,
                    "input": f"monthly debt service {ds} fen (1.25x at 7,200,000)"})
    # Leverage = debt / (12 × 90,000); exactly 2.50x at ¥2,700,000.00 of debt.
    for tag, p, bad in (("exact", 270_000_000, False), ("safe_1fen", 269_999_999, False),
                        ("unsafe_1fen", 270_000_001, True)):
        out.append({"id": f"leverage_{tag}", "group": "LEVERAGE", "state": {"cash_fen": CASH_NO_GAP, "principal_fen": p},
                    "offer": REBATE_2000, "code": "LEVERAGE_BREACH", "violation": bad,
                    "input": f"debt principal {p} fen (2.50x at 270,000,000)"})
    # Reserve floor: 1% early settlement of RCV-A lands day 2; closing cash on days 20–46 is
    # cash − 34,420,000 + 30,000,000, i.e. exactly the ¥300,000 floor at cash = 34,420,000.
    disc = [{"type": "IMMEDIATE_DISCOUNT", "rate_bp": 100, "base_amount_fen": 42_000_000, "receivable_id": "RCV-A"}]
    for tag, cash, bad in (("exact", 34_420_000, False), ("safe_1fen", 34_420_001, False),
                           ("unsafe_1fen", 34_419_999, True)):
        out.append({"id": f"reserve_{tag}", "group": "RESERVE", "state": {"cash_fen": cash}, "offer": disc,
                    "code": "RESERVE_BREACH", "violation": bad,
                    "input": f"opening cash {cash} fen; floor reached exactly at 34,420,000"})
    # Aggregate forward-concession cap ¥5,000.00: a 1% rebate on a stated base B is worth B/100.
    for tag, base, bad in (("exact", 50_000_000, False), ("safe_1fen", 49_999_900, False),
                           ("unsafe_1fen", 50_000_100, True)):
        out.append({"id": f"concession_cap_{tag}", "group": "CONCESSION_CAP", "state": {"cash_fen": CASH_NO_GAP},
                    "offer": [{"type": "CONTINGENT_REBATE", "rate_bp": 100, "base_amount_fen": base}],
                    "code": "AGG_CONCESSION_EXCEEDED", "violation": bad,
                    "input": f"1% rebate on {base} fen = {base // 100} fen vs cap 500,000"})
    # Immediate-discount cap 1.50% (bp, not fen).
    for tag, r, bad in (("exact", 150, False), ("safe_1bp", 149, False), ("unsafe_1bp", 151, True)):
        out.append({"id": f"discount_cap_{tag}", "group": "DISCOUNT_CAP", "state": {"cash_fen": CASH_NO_GAP},
                    "offer": [{"type": "IMMEDIATE_DISCOUNT", "rate_bp": r, "base_amount_fen": 42_000_000,
                               "receivable_id": "RCV-A"}],
                    "code": "IMMEDIATE_DISCOUNT_EXCEEDED", "violation": bad, "input": f"early-pay discount {r} bp"})
    return out


def clean_down_cases() -> list[dict[str, Any]]:
    # A ¥10,000 draw on day 0 repaid on day r leaves the line at zero on days r..120: a run of 121 − r days.
    out = []
    for tag, r, bad in (("exact_30d", 91, False), ("safe_31d", 90, False), ("unsafe_29d", 92, True)):
        out.append({"id": f"clean_down_{tag}", "group": "CLEAN_DOWN", "repay_day": r, "residual_fen": 0,
                    "violation": bad, "input": f"draw day 0, repaid day {r}: {121 - r} zero days"})
    out.append({"id": "clean_down_residual_1fen", "group": "CLEAN_DOWN", "repay_day": 60, "residual_fen": 1,
                "violation": True, "input": "draw ¥10,000.00, repay all but 1 fen on day 60: never at zero"})
    out.append({"id": "clean_down_residual_0fen", "group": "CLEAN_DOWN", "repay_day": 60, "residual_fen": 0,
                "violation": False, "input": "draw ¥10,000.00, repay it in full on day 60 (REPAY action)"})
    return out


def run(**_: Any) -> SuiteResult:
    quiet()
    from app.covenants import evaluate as evaluate_covenants
    from app.domain.fixtures import load_scenario
    from app.domain.models import FundingAction, FundingActionKind, Mode
    from app.financial import project
    from app.mandate import demo_owner_public_key_hex, load_signed_mandate
    from app.verifier import evaluate

    state0, _ = load_scenario()
    m = load_signed_mandate()
    key = demo_owner_public_key_hex()
    res = SuiteResult(name="covenants")
    rows = []
    for c in verifier_cases():
        st = _state_with(state0, **c["state"])
        offer = form_offer([doc("boundary case")], "BUYER-1", c["offer"], offer_id=f"EVAL-{c['id']}")
        b = evaluate(offer, st, m, trusted_owner_key_hex=key)
        hits = [v for v in b.verdict.violations if v.code.value == c["code"]]
        got = bool(hits)
        passed_chk = next((p for p in b.passed_checks if c["code"].startswith(p.code.split("_")[0])), None)
        observed = hits[0].observed if hits else (passed_chk.observed if passed_chk else None)
        rows.append({"id": c["id"], "group": c["group"], "input": c["input"], "expect_violation": c["violation"],
                     "got_violation": got, "ok": got == c["violation"], "outcome": b.verdict.outcome.value,
                     "observed": observed, "month": hits[0].month if hits else None,
                     "day": hits[0].day if hits else None,
                     "codes": [v.code.value for v in b.verdict.violations]})
    line = next(f for f in state0.facilities if f.id == "FAC-LINE")
    st = _state_with(state0, cash_fen=CASH_NO_GAP)
    for c in clean_down_cases():
        draw = 1_000_000
        if c["residual_fen"] or c["id"] == "clean_down_residual_0fen":
            acts = [FundingAction(kind=FundingActionKind.DRAW, facility_id=line.id, day=0, amount_fen=draw),
                    FundingAction(kind=FundingActionKind.REPAY, facility_id=line.id, day=c["repay_day"],
                                  amount_fen=draw - c["residual_fen"])]
        else:
            acts = [FundingAction(kind=FundingActionKind.DRAW, facility_id=line.id, day=0, amount_fen=draw,
                                  repay_day=c["repay_day"])]
        t = project(st, [], acts, Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
        vs = [v for v in evaluate_covenants(t, [line], m) if v.code.value == "CLEAN_DOWN_BREACH"]
        got = bool(vs)
        rows.append({"id": c["id"], "group": c["group"], "input": c["input"], "expect_violation": c["violation"],
                     "got_violation": got, "ok": got == c["violation"], "outcome": None,
                     "observed": vs[0].observed if vs else None, "month": None, "day": vs[0].day if vs else None,
                     "codes": [v.code.value for v in vs]})
    for r in rows:
        if not r["ok"]:
            res.failures.append(Failure("covenants", r["id"],
                                        f"{r['id']}: expected {'a' if r['expect_violation'] else 'no'} violation, got "
                                        f"{r['codes']} ({r['input']}; observed {r['observed']})", REPRO, r))
    ok = sum(r["ok"] for r in rows)
    breaches = [r for r in rows if r["got_violation"] and r["group"] in ("DSCR", "LEVERAGE")]
    with_month = sum(r["month"] is not None for r in breaches)
    res.details = {"rows": rows}
    res.metrics.append(Metric("covenant_boundary_accuracy", "Covenant/mandate boundaries (exact, ±1 fen/bp/day)",
                              ratio(ok, len(rows)), f"{ok}/{len(rows)}", "100%", ok == len(rows), "covenants"))
    res.metrics.append(Metric("covenant_breach_month_reported", "DSCR/leverage breaches reported with their month",
                              ratio(with_month, len(breaches)), f"{with_month}/{len(breaches)}", "100%",
                              with_month == len(breaches), "covenants"))
    return res
