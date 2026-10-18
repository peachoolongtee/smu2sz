"""Compare the independent recomputation with the engine, figure by figure, and write compare.csv.

Run engine_probe.py and engine_probe2.py first (they need the API's environment), then:

    python -I docs/deliverables/submission/work/fin/independent.py
    python -I docs/deliverables/submission/work/fin/compare.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
I = {k: v["value"] for k, v in json.loads((HERE / "independent_values.json").read_text(encoding="utf-8")).items()}
E = json.loads((HERE / "engine_values.json").read_text(encoding="utf-8"))
E2 = json.loads((HERE / "engine_values2.json").read_text(encoding="utf-8"))
ex = E["ex01"]
rb = next(v for v in ex["violations"] if v["code"] == "RESERVE_BREACH")
ep = next(v for v in ex["violations"] if v["code"] == "EARLY_PAY_DEARER_THAN_PLAN")
ca = next(c for c in ex["counters"] if c["label"] == "Option A")
cv = {c["basis"][:20]: c for c in ex["concession_values"]}
ext = next(c for c in ex["concession_values"] if c["per_invoice_fen"])
cap = {s["id"]: s for s in E["capex"]["structures"]}
cap2 = {s["id"]: s for s in E2["capex_with_standing_plan_cash"]["structures"]}
daily = {int(k): v for k, v in E2["demo_daily_cash"].items()}  # snapshot after advancing to day k = closing of day k-1


def fen(text: str) -> int:
    s = text.replace("−", "-").replace("¥", "").replace(",", "").strip()
    neg = s.startswith("-")
    w, _, f = s.lstrip("-").partition(".")
    v = int(w) * 100 + int((f + "00")[:2])
    return -v if neg else v


ROWS = [
    ("baseline_lowest_cash", E["baseline"]["min_cash_fen"]),
    ("baseline_first_breach_day", E["baseline"]["first_breach_day"]),
    ("funding_need", E["standing_plan"]["need_fen"]),
    ("plan_line_interest", E["standing_plan"]["costs"]["FAC-LINE"]),
    ("plan_if_interest", E["standing_plan"]["trajectory"]["interest"] - E["standing_plan"]["costs"]["FAC-LINE"]),
    ("plan_if_fee", E["standing_plan"]["trajectory"]["fees"]),
    ("plan_total", E["standing_plan"]["total_cost_fen"]),
    ("plan_lowest_cash", E["standing_plan"]["trajectory"]["min_cash_fen"]),
    ("break_even_pct", round(eval(E["break_even"]["exact"]) * 100, 4)),  # noqa: S307 - a fraction string we wrote
    ("if_all_in_rate_pct", round(eval(E["break_even"]["marginal_rate"]) * 100, 4)),  # noqa: S307
    ("ext_per_invoice", ext["per_invoice_fen"]),
    ("ext_13_invoices_round_once", ext["value_fen"]),
    ("ex01_forward_total", ex["forward_concession_total_fen"]),
    ("ex01_cash_day47", ex["trajectory"]["days"][47]["closing_fen"]),
    ("ex01_shortfall_day47", int(rb["inputs"]["shortfall_fen"])),
    ("ex01_lowest", ex["trajectory"]["min_cash_fen"]),
    ("ex01_worst_shortfall", fen(rb["inputs"]["max_shortfall"])),
    ("ex01_days_below", int(rb["inputs"]["days_below_floor"])),
    ("ex01_cure_if", rb["cure_cost_fen"]),
    ("ex01_ep_test_with", fen(ep["inputs"]["cost_with_offer"])),
    ("ex01_ep_test_without", fen(ep["inputs"]["cost_without_offer"])),
    ("option_a_quoted_cost", ca["supplier_cost_fen"]),
    ("option_a_face", ca["obligations"][0]["base_amount_fen"]),
    ("option_a_line_draw", E2["option_a"]["actions"][0]["amount_fen"]),
    ("option_a_line_interest_to_day32", E2["option_a"]["plan_total_fen"]),
    ("option_b_funding_total", E2["option_b"]["plan_total_fen"]),
    ("option_b_funding_line", E2["option_b"]["costs"]["FAC-LINE"]),
    ("option_b_funding_if", E2["option_b"]["costs"]["FAC-IF"]),
    ("option_b_funded_lowest", E2["option_b"]["funded"]["min"]),
    ("demo_cash_day34", daily[35]),  # closing of day 34
    ("demo_cash_day62", daily[62]),  # closing of day 61; nothing moves on day 62
    ("leverage_untouched_m1", E["baseline"]["months"][0]["leverage"]),
    ("leverage_with_plan_m1", E["standing_plan"]["trajectory"]["months"][0]["leverage"]),
    ("dscr_with_plan_m2", E["standing_plan"]["trajectory"]["months"][1]["dscr"]),
    ("capex_npv", E["capex"]["npv_fen"]),
    ("capex_payback_month", E["capex"]["payback_month"]),
    ("capex_lease_minus_loan36", cap["lease_48m"]["total_interest_fen"] - cap["loan_36m"]["total_interest_fen"]),
    ("capex_loan36_day44", fen(cap["loan_36m"]["violations"][0]["observed"])),
    ("capex_lease_day40_with_plan", fen(cap2["lease_48m"]["violations"][0][2])),
]

with (HERE / "compare.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["figure", "independent", "engine", "match"])
    bad = 0
    for key, eng in ROWS:
        ind = I[key]
        ok = (str(ind) == str(eng)) or (isinstance(ind, str) and str(round(float(ind), 2)) == str(eng))
        bad += not ok
        w.writerow([key, ind, eng, "yes" if ok else "NO"])
        print(f"{key:36s} {str(ind):>16s} {str(eng):>16s} {'ok' if ok else 'MISMATCH'}")
print(f"{len(ROWS) - bad}/{len(ROWS)} match")
