"""Independent recomputation of every headline financial figure in docs/deliverables/technical_document.md.

Pure Python (fractions, decimal). Reads only the demo books and the mandate from the fixture JSON; imports nothing
from the application and reads no golden value. Conventions are stated beside each figure and summarised in
docs/deliverables/submission/work/financial_audit.md. All money is CNY; integer fen inside, yuan when printed.

    python docs/deliverables/submission/work/fin/independent.py

Writes independent_values.json, daily_cash.csv and events.csv next to this file.
"""

from __future__ import annotations

import csv
import json
from decimal import Decimal, getcontext
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BOOKS = json.loads((ROOT / "fixtures/scenarios/golden_sme.json").read_text(encoding="utf-8"))
EVENTS = json.loads((ROOT / "fixtures/scenarios/golden_sme.events.json").read_text(encoding="utf-8"))
S, M = BOOKS["state"], BOOKS["mandate"]
FAC = {f["id"]: f for f in S["facilities"]}


def post(x: F) -> int:
    """Exact fen -> integer fen, half-up away from zero (the rounding is applied once, when a figure is posted)."""
    s = -1 if x < 0 else 1
    q, r = divmod(abs(x).numerator, abs(x).denominator)
    return s * (q + (1 if F(r, abs(x).denominator) >= F(1, 2) else 0))


def bp(n: int) -> F:
    return F(n, 10_000)


def y(fen: int | F) -> str:
    v = F(fen) / 100
    return f"{'-' if v < 0 else ''}{abs(float(v)):,.2f}"


R: dict[str, object] = {}


def put(key: str, fen_or_value, note: str = "", money: bool = True) -> None:
    money = money and isinstance(fen_or_value, int) and not isinstance(fen_or_value, bool)
    R[key] = {"value": fen_or_value,
              "cny": y(fen_or_value) if money else None, "note": note}


# ------------------------------------------------------------------ the books
CASH0 = S["cash_fen"]
RESERVE = M["min_cash_fen"]
LINE, IF, EP = FAC["FAC-LINE"], FAC["FAC-IF"], FAC["FAC-EARLYPAY"]
REC = S["recurring_invoices"][0]
FACE = REC["face_fen"]                       # 420,000 every 30 days, first issue day 2, 45-day terms
DEBT = S["debts"][0]                         # 1,500,000 at 0%, 45,000 every 30 days from day 30
EBITDA = S["monthly_ebitda_fen"]             # 90,000 a month: a fixture constant, not derived from the cash books
H = 120


def base_events(terms: int = 45, price_bp: int = 0, rcv_a: bool = True, horizon: int = 180) -> dict[int, list]:
    """Dated cash events of the untouched books: flows, RCV-A on day 32, the recurring invoices, debt service."""
    ev: dict[int, list] = {}

    def add(d, amt, label):
        ev.setdefault(d, []).append((amt, label))
    for f in S["flows"]:
        add(f["day"], f["amount_fen"], f["label"])
    if rcv_a:
        a = S["receivables"][0]
        add(a["issue_day"] + a["terms_days"], a["face_fen"], "RCV-A receipt")
    for k in range(10):
        issue = REC["next_issue_day"] + k * REC["every_days"]
        due = issue + terms
        if due <= horizon:
            add(due, FACE + post(bp(price_bp) * FACE), f"invoice issued day {issue} paid")
    bal, d = DEBT["principal_fen"], DEBT["next_payment_day"]
    while bal > 0 and d <= horizon:
        add(d, -DEBT["monthly_debt_service_fen"], "existing loan payment")
        bal -= DEBT["monthly_debt_service_fen"]
        d += DEBT["payment_every_days"]
    return ev


def path(ev: dict[int, list], horizon: int = H, opening: int = CASH0) -> list[int]:
    out, c = [], opening
    for d in range(horizon + 1):
        c += sum(a for a, _ in ev.get(d, []))
        out.append(c)
    return out


def merge(*evs):
    out: dict[int, list] = {}
    for e in evs:
        for d, rows in e.items():
            out.setdefault(d, []).extend(rows)
    return out


def line_int(amount: int, days: int) -> int:
    """Credit line: Actual/365 simple interest on the drawn lot, posted at repayment."""
    return post(F(amount) * bp(LINE["rate_bp"]) * days / 365)


def if_charges(amount: int, days: int) -> tuple[int, int, int]:
    """Invoice financing: interest AND the 0.25% fee are both billed in whole 30-day periods (at least one)."""
    per = IF["fee_period_days"]
    n = max(1, -(-days // per))
    return post(F(amount) * bp(IF["rate_bp"]) * n * per / 365), post(F(amount) * bp(IF["fee_bp_per_advance"]) * n), n


# ------------------------------------------------------------------ 1. untouched books
base = path(base_events())
low = min(base)
put("baseline_lowest_cash", low, f"day {base.index(low)}")
first_breach = next(d for d, c in enumerate(base) if c < RESERVE)
put("baseline_first_breach_day", first_breach, "first closing below the 300,000 reserve", money=False)
below = [d for d, c in enumerate(base) if c < RESERVE]
put("baseline_days_below_reserve", len(below), f"days {below[0]}-{below[-1]}", money=False)
put("baseline_peak_shortfall", RESERVE - low, "reserve - lowest cash (days 30-31)")
put("baseline_shortfall_day12", RESERVE - base[12], "shortfall on the first breach day only")
need = RESERVE - low
put("funding_need", need, "340,000 + 120,000 + 45,000 + 300,000 - 400,000")
put("due_next_30_days", 34_000_000 + 12_000_000 + 4_500_000, "payroll + supplier + loan payment, days 12/20/30")

# ------------------------------------------------------------------ 2. FLOW's standing plan (line 150k + IF 255k)
li = line_int(150_000_00, 32)                                  # day 0 -> day 32 (RCV-A receipt)
ii, fi, n = if_charges(255_000_00, 32 - (0 + IF["lead_time_days"]))  # requested day 0, lands day 3, repaid day 32
put("plan_line_interest", li, "150,000 x 6.4% x 32/365")
put("plan_if_interest", ii, f"255,000 x 7.8% x {n}x30/365 (29 days used, one whole period billed)")
put("plan_if_fee", fi, "255,000 x 0.25% x 1 period")
put("plan_total", li + ii + fi, "sum of posted parts")
put("plan_if_effective_rate_pct", str(round(float(F(ii + fi, 255_000_00) * 365 / 29) * 100, 4)), "on the 29 days held")
put("plan_if_within_advance_rate", 255_000_00 <= post(bp(IF["advance_rate_bp"]) * 420_000_00), "80% of 420,000 = 336,000")
plan_ev = {0: [(150_000_00, "line draw")], 3: [(255_000_00, "IF advance on RCV-A")],
           32: [(-(150_000_00 + li), "line repaid + interest"), (-(255_000_00 + ii + fi), "IF repaid + interest + fee")]}
plan_path = path(merge(base_events(), plan_ev))
put("plan_lowest_cash", min(plan_path), f"day {plan_path.index(min(plan_path))}")
put("full_discount_alternative", post(bp(120) * FACE), "1.2% of the whole 420,000 invoice")

# ------------------------------------------------------------------ 3. rates and break-even
all_in = bp(IF["rate_bp"]) + bp(IF["fee_bp_per_advance"]) * F(365, IF["fee_period_days"])
put("if_all_in_rate_pct", str(round(float(all_in) * 100, 4)), "7.8% + 0.25% x 365/30 (fee spread daily: a pricing convention)")
c30 = bp(IF["rate_bp"]) * 30 / 365 + bp(IF["fee_bp_per_advance"])
be = c30 / (1 + c30)
put("break_even_pct", str(round(float(be) * 100, 4)), "d < c/(1+c), c = 7.8% x 30/365 + 0.25% (one whole IF period)")
put("break_even_vs_line_pct", str(round(float((bp(640) * 30 / 365) / (1 + bp(640) * 30 / 365)) * 100, 4)),
    "the same test against the credit line, for comparison only")
put("ep_1_2pct_annualised_pct", str(round(float(bp(120) / (1 - bp(120)) * 365 / 30) * 100, 4)), "d/(1-d) x 365/30")
put("whole_invoice_0_75pct", post(bp(75) * FACE), "vs plan 3,113.93")
put("whole_invoice_0_74pct", post(bp(74) * FACE), "vs plan 3,113.93")

# ------------------------------------------------------------------ 4. the 45 -> 60 day extension
delta, every = 15, REC["every_days"]
issues = [d for d in range(REC["next_issue_day"], 365, every)]
put("invoices_issued_in_365_days", len(issues), f"issue days {issues[0]}..{issues[-1]}", money=False)
per_exact = F(FACE) * delta / 365 * all_in
put("ext_per_invoice", post(per_exact), "420,000 x 15/365 x 10.8417%")
put("ext_per_invoice_equivalence", post(F(210_000_00) * bp(780) * 30 / 365) + post(F(210_000_00) * bp(25)),
    "the same figure: ONE whole-period IF advance of 210,000 (half the face) for 30 days")
put("ext_13_invoices_round_once", post(len(issues) * per_exact), "engine convention: exact sum, rounded once")
put("ext_13_x_rounded_per_invoice", len(issues) * post(per_exact), "13 x 1,871.30: differs by 2 fen")
put("ext_12_invoices", post(12 * per_exact), "if 'a year' meant 12 monthly invoices")
extra_avg = F(FACE) * delta / every
put("ext_average_extra_receivables", post(extra_avg), "420,000 x 15/30: an average; the peak is 420,000 for 15 of every 30 days")
put("ext_steady_state_annual", post(extra_avg * all_in), "210,000 x 10.8417% x 365/365")
put("ext_monthly_service_estimate", post(extra_avg * all_in / 12), "steady-state interest only, used in the DSCR 1.92 estimate")
in_year = [d for d in issues if d + 45 < 365]
put("ext_first_365_days_cash_cost", post(len(in_year) * per_exact),
    f"only the {len(in_year)} invoices whose 15 extra days start inside days 0-364 (extra days fall 45-60 days after issue)")
max_adv = post(bp(IF["advance_rate_bp"]) * FACE)
ai, af, _ = if_charges(max_adv, 15)
put("ext_executable_if_per_invoice", ai + af,
    f"actually advancing the most the platform allows (80% = {y(max_adv)}) for the 15 extra days: one whole period")
put("ext_executable_if_uncovered", FACE - max_adv, "of each invoice's 420,000 peak, not advanceable at 80%")
put("rebate_max", post(bp(100) * 400_000_00), "1% of the 400,000 expected (not firm) next-quarter order, counted at its maximum")
put("ex01_forward_total", post(len(issues) * per_exact) + post(bp(100) * 400_000_00), "terms 24,326.92 + rebate 4,000")
put("ex01_immediate_discount", post(bp(120) * FACE), "1.2% x 420,000, paid in cash on day 2, outside the forward cap")
put("ex01_all_asks_first_year", post(len(issues) * per_exact) + post(bp(100) * 400_000_00) + post(bp(120) * FACE),
    "forward 28,326.92 + immediate 5,040 (what 'accept as asked' gives away, on FLOW's pricing)")
put("ex01_cap_multiple", str(round((post(len(issues) * per_exact) + 400_000) / M["max_aggregate_forward_concession_fen"], 2)),
    "forward total / 5,000 cap")

# ------------------------------------------------------------------ 5. EX01 as asked, no new funding
ex01_ev = base_events(terms=60, rcv_a=False)
ex01_ev = merge(ex01_ev, {2: [(FACE, "RCV-A paid early"), (-post(bp(120) * FACE), "1.2% discount")]})
ex01 = path(ex01_ev)
put("ex01_cash_day20", ex01[20])
put("ex01_cash_day47", ex01[47], "first breach day")
put("ex01_shortfall_day47", RESERVE - ex01[47])
put("ex01_lowest", min(ex01), f"day {ex01.index(min(ex01))}")
put("ex01_worst_shortfall", RESERVE - min(ex01))
bel = [d for d, c in enumerate(ex01) if c < RESERVE]
put("ex01_days_below", len(bel), f"days {bel[0]}-{bel[-1]}", money=False)
put("ex01_cash_day47_at_45_days", path(merge(base_events(rcv_a=False),
                                             {2: [(FACE, ""), (-post(bp(120) * FACE), "")]}))[47])
wsf = RESERVE - min(ex01)
ci, cf, cn = if_charges(wsf, 92 - 35)
put("ex01_cure_if", ci + cf, f"IF {y(wsf)} on the invoice issued day 32: lands day 35, repaid day 92 (60-day terms), {cn} periods")
put("ex01_cure_line", line_int(wsf, 62), "line 135,040 drawn day 0 (decision day), repaid day 62")
put("ex01_cure_line_just_in_time", line_int(wsf, 62 - 47), "the same draw made on day 47 instead: not what the router does")
put("ex01_ep_test_with", post(bp(120) * FACE) + line_int(wsf, 62), "discount + the plan that funds the offer")
c0i, c0f, _ = if_charges(270_000_00, 29)
put("ex01_ep_test_without", line_int(135_000_00, 62) + c0i + c0f,
    "same terms, no early payment: line 135,000 day 0->62 + IF 270,000 on RCV-A day 3->32 (one period)")

# ------------------------------------------------------------------ 6. Option A
rate_a = max(r for r in range(0, 200, 5) if bp(r) < be)
put("option_a_rate_bp", rate_a, "largest whole-5bp rate below break-even", money=False)
gap = need - LINE["limit_fen"]
gross = F(gap) / (1 - bp(rate_a))
face_a = min(-(-gross // 10_000_00) * 10_000_00, FACE)
disc_a = post(bp(rate_a) * face_a)
put("option_a_grossed_up_exact", post(gross), "255,000 / (1 - 0.85%)")
put("option_a_face", int(face_a), "rounded up to a whole 10,000")
put("option_a_discount", disc_a)
put("option_a_receipt_day2", int(face_a) - disc_a)
draw_a = need - (int(face_a) - disc_a)
put("option_a_line_draw", draw_a, "405,000 - 257,790")
put("option_a_line_interest_to_day32", line_int(draw_a, 32))
put("option_a_quoted_cost", disc_a + line_int(draw_a, 32))
put("option_a_saving_vs_plan", li + ii + fi - (disc_a + line_int(draw_a, 32)))
old_face = -(-gross // 100_00) * 100_00
put("option_a_old_100_yuan_face_cost", post(bp(85) * old_face) + line_int(need - (int(old_face) - post(bp(85) * old_face)), 32),
    f"stale figure: face rounded to 100 ({y(int(old_face))}), the version before the 16 Oct addendum")
oa_ev = merge(base_events(rcv_a=False), {0: [(draw_a, "line draw")], 2: [(int(face_a), "early part of RCV-A"),
                                                                          (-disc_a, "0.85% discount")],
                                         32: [(FACE - int(face_a), "RCV-A residual"),
                                              (-(draw_a + line_int(draw_a, 32)), "line repaid + interest")]})
oa = path(oa_ev)
put("option_a_lowest", min(oa), f"day {oa.index(min(oa))}")

# ------------------------------------------------------------------ 7. Option B (55 days + 0.30%)
per_b = F(FACE) * 10 / 365 * all_in
put("option_b_per_invoice_cost", post(per_b), "420,000 x 10/365 x 10.8417%")
rb = min(r for r in range(0, 200, 5) if post(bp(r) * FACE) >= post(per_b))
put("option_b_price_bp", rb, money=False)
put("option_b_13_ext", post(13 * per_b))
put("option_b_13_price_gain", -13 * post(bp(rb) * FACE))
put("option_b_net_13", post(13 * per_b) - 13 * post(bp(rb) * FACE))
ob_unf = path(base_events(terms=55, price_bp=rb))
put("option_b_unfunded_day47", ob_unf[47], "before any funding: the day-2 invoice now pays on day 57")
put("option_b_unfunded_lowest", min(ob_unf), f"day {ob_unf.index(min(ob_unf))}")
# price the engine's chosen plan legs independently: line 90,000 day 0->57 + IF 315,000 on RCV-A day 3->32
bl = line_int(90_000_00, 57)
bi, bf, _ = if_charges(315_000_00, 29)
put("option_b_funding_line", bl, "90,000 x 6.4% x 57/365")
put("option_b_funding_if", bi + bf, "315,000, one whole period")
put("option_b_funding_total", bl + bi + bf)
put("option_b_funding_vs_plan", bl + bi + bf - (li + ii + fi))
ob_f = path(merge(base_events(terms=55, price_bp=rb), {0: [(90_000_00, "")], 3: [(315_000_00, "")],
                                                      32: [(-(315_000_00 + bi + bf), "")],
                                                      57: [(-(90_000_00 + bl), "")]}))
put("option_b_funded_lowest", min(ob_f), f"day {ob_f.index(min(ob_f))}")

# ------------------------------------------------------------------ 8. the demo story as it runs (Option A agreed)
pay_m2 = EVENTS["events"][0]["flow"]
cure = 200_000_00
cui, cuf, cun = if_charges(cure, 47 - 37)
put("cure_if_interest", cui, "200,000 x 7.8% x 30/365 (10 days held, one period)")
put("cure_if_fee", cuf)
put("cure_cost", cui + cuf)
put("cure_effective_rate_pct", str(round(float(F(cui + cuf, cure) * 365 / 10) * 100, 3)), "all charges / 200,000 x 365/10")
put("cure_tariff_all_in_pct", str(round(float(all_in) * 100, 4)), "the same facility's tariff, for contrast")
day34_cash = CASH0 + draw_a + (int(face_a) - disc_a) - 34_000_000 - 12_000_000 - 4_500_000
put("demo_cash_day34", day34_cash, "residual 160,000 overdue since day 32; line still drawn")
put("demo_day42_without_cure", day34_cash + pay_m2["amount_fen"], "the 200,000 month-2 payroll the bookkeeper added on day 25")
put("demo_day42_if_residual_on_time", oa[32] + pay_m2["amount_fen"],
    "even if the 160,000 had arrived on day 32 (and the line been repaid), day 42 would still breach")
lr = line_int(draw_a, 47)
put("demo_line_interest_day47", lr, "147,210 x 6.4% x 47/365: the line stayed out 15 days longer than quoted")
put("demo_total_charges", disc_a + lr + cui + cuf, "discount + line interest + cure interest + cure fee")
put("demo_overrun_vs_quote", disc_a + lr + cui + cuf - (disc_a + line_int(draw_a, 32)))
demo_ev = merge(base_events(rcv_a=False),
                {0: [(draw_a, "line draw 147,210")], 2: [(int(face_a) - disc_a, "early receipt 257,790")],
                 36: [(FACE - int(face_a), "late residual 160,000")], 37: [(cure, "cure advance lands")],
                 pay_m2["day"]: [(pay_m2["amount_fen"], "payroll month 2 (added day 25)")],
                 47: [(-(cure + cui + cuf), "advance repaid + charges"), (-(draw_a + lr), "line repaid + interest")]})
demo = path(demo_ev)
put("demo_cash_day62", demo[62])
put("demo_lowest_after_deal", min(demo), f"day {demo.index(min(demo))}")
put("demo_cash_identity", CASH0 + 2 * FACE - 34_000_000 - 12_000_000 - 2 * 4_500_000 - 20_000_000 - 10_000_000
    - (disc_a + lr + cui + cuf), "cash day 62 = 400k + two receipts - all outflows - all charges")

# ------------------------------------------------------------------ 9. covenants
put("dscr_untouched", str(round(EBITDA / DEBT["monthly_debt_service_fen"], 2)), "90,000 / 45,000, month by month")
put("leverage_untouched_m1", str(round((DEBT["principal_fen"] - 4_500_000) / (12 * EBITDA), 4)), "1,455,000 / 1,080,000")
put("leverage_with_plan_m1", str(round((DEBT["principal_fen"] - 4_500_000 + 405_000_00) / (12 * EBITDA), 4)),
    "the line and the advance are still drawn at month-1 end (day 30)")
put("dscr_with_plan_m2", str(round(EBITDA / (4_500_000 + li + ii + fi), 4)), "plan charges posted in month 2")
ggl = 500_000_00
put("dscr_ggl_500k", str(round(EBITDA / (4_500_000 + ggl / 12 + ggl * 0.05 / 12), 4)), "bullet loan serviced on a level basis")
put("dscr_ebitda_minus_20", str(round(0.8 * EBITDA / (4_500_000 + li + ii + fi), 4)))
put("leverage_ebitda_minus_20", str(round((145_500_000 + 405_000_00) / (12 * 0.8 * EBITDA), 4)))

# ------------------------------------------------------------------ 10. stress: Foshan 10 days late
si, sf, sn = if_charges(255_000_00, 42 - 3)
put("stress_10d_late_cost", line_int(150_000_00, 42) + si + sf, "line to day 42 + advance day 3->42 (2 periods)")
put("stress_10d_late_advance_rate_pct", str(round(float(F(si + sf, 255_000_00) * 365 / 39) * 100, 2)))

# ------------------------------------------------------------------ 11. capex
getcontext().prec = 50


def schedule(p: int, rate_bp: int, n: int):
    r = bp(rate_bp) / 12
    pay = post(F(p) * r / (1 - 1 / (1 + r) ** n))
    bal, ti, pays = p, 0, []
    for k in range(1, n + 1):
        i = post(F(bal) * r)
        ti += i
        pr = pay - i if k < n else bal
        pays.append(pr + i)
        bal -= pr
    return pay, ti, pays


rm = Decimal("1.10") ** (Decimal(1) / Decimal(12)) - 1
cap = {}
for key, rate, n, lead in (("loan_18m", 560, 18, 14), ("loan_36m", 560, 36, 14), ("lease_48m", 720, 48, 10)):
    pay, ti, pays = schedule(600_000_00, rate, n)
    pv = sum(Decimal(p) / (1 + rm) ** k for k, p in enumerate(pays, 1))
    cap[key] = {"payment": pay, "interest": ti, "pv_payments_at_10pct": int(pv.quantize(Decimal(1))),
                "first_instalment_day": lead + 30, "dscr_m1": round(EBITDA / (4_500_000 + pay), 4)}
put("capex_structures", cap)
put("capex_lease_minus_loan36", cap["lease_48m"]["interest"] - cap["loan_36m"]["interest"], "undiscounted charges")
put("capex_lease_minus_loan36_pv", cap["lease_48m"]["pv_payments_at_10pct"] - cap["loan_36m"]["pv_payments_at_10pct"],
    "PV of the payments at the 10% hurdle (effective monthly), fen rounded")
npv = -Decimal(600_000_00) + sum(Decimal(22_000_00) / (1 + rm) ** k for k in range(4, 61))
put("capex_npv", int(npv.quantize(Decimal(1), rounding="ROUND_HALF_UP")),
    "-600,000 + 22,000 a month, months 4-60, at (1.10)^(1/12)-1; no residual value, tax or maintenance; unlevered")
cum, pb, dcum, dpb = -600_000_00, None, Decimal(-600_000_00), None
for k in range(1, 61):
    if k >= 4:
        cum += 22_000_00
        dcum += Decimal(22_000_00) / (1 + rm) ** k
    pb = pb or (k if cum >= 0 else None)
    dpb = dpb or (k if dcum >= 0 else None)
put("capex_payback_month", pb, "simple, undiscounted", money=False)
put("capex_discounted_payback_month", dpb, "at the 10% hurdle", money=False)
before_first = base[32]
put("capex_loan36_day44", before_first - cap["loan_36m"]["payment"], "untouched books after RCV-A (315,000) minus instalment")
put("capex_loan36_shortfall", RESERVE - (before_first - cap["loan_36m"]["payment"]))
put("capex_loan36_bridge", line_int(RESERVE - (before_first - cap["loan_36m"]["payment"]), 3), "3 days on the line")
put("capex_lease_day40_untouched", before_first - cap["lease_48m"]["payment"])
put("capex_lease_day40_with_plan", plan_path[32] - cap["lease_48m"]["payment"],
    "after FLOW's plan has paid its 3,113.93 on day 32: below the reserve")
put("capex_lease_shortfall_with_plan", RESERVE - (plan_path[32] - cap["lease_48m"]["payment"]))
put("capex_loan36_day44_with_plan", plan_path[32] - cap["loan_36m"]["payment"])
put("capex_lease_bridge_with_plan", line_int(RESERVE - (plan_path[32] - cap["lease_48m"]["payment"]), 7),
    "days 40-46 on the line (repaid on the day-47 receipt)")
put("capex_loan36_bridge_with_plan", line_int(RESERVE - (plan_path[32] - cap["loan_36m"]["payment"]), 3), "days 44-46")
put("capex_loan36_minus_lease_net_of_bridge", cap["lease_48m"]["interest"] - cap["loan_36m"]["interest"]
    - line_int(RESERVE - (before_first - cap["loan_36m"]["payment"]), 3))

(HERE / "independent_values.json").write_text(json.dumps(R, indent=1, ensure_ascii=False, default=str), encoding="utf-8")

# ------------------------------------------------------------------ chart series (days 0-62, closing cash, CNY)
series = {
    "baseline_no_funding": base,
    "standing_plan_line150k_if255k": plan_path,
    "ex01_as_asked_no_funding": ex01,
    "option_a_as_quoted": oa,
    "option_a_as_quoted_plus_month2_payroll": path(merge(oa_ev, {pay_m2["day"]: [(pay_m2["amount_fen"], "")]})),
    "option_b_with_its_funding": ob_f,
    "demo_actual_option_a_late_residual_cure": demo,
}
with (HERE / "daily_cash.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["day", "reserve_cny", *[f"{k}_cny" for k in series]])
    for d in range(0, 63):
        w.writerow([d, f"{RESERVE / 100:.2f}", *[f"{series[k][d] / 100:.2f}" for k in series]])

events = [
    (0, "all", "Decision day: FLOW reads Foshan's request (EX01)", ""),
    (0, "standing_plan", "Credit line drawn", 150_000_00),
    (0, "option_a/demo", "Credit line drawn", draw_a),
    (2, "ex01", "RCV-A paid early at 1.2% (discount 5,040.00)", FACE - post(bp(120) * FACE)),
    (2, "option_a/demo", "260,000 of RCV-A paid early at 0.85% (discount 2,210.00)", int(face_a) - disc_a),
    (3, "standing_plan", "Invoice-financing advance on RCV-A lands", 255_000_00),
    (12, "all", "Payroll", -34_000_000),
    (12, "baseline", "First day below the reserve", ""),
    (20, "all", "Supplier payment", -12_000_000),
    (30, "all", "Existing loan payment", -4_500_000),
    (30, "baseline", "Lowest cash -105,000.00 (405,000.00 below the reserve)", ""),
    (32, "baseline/standing_plan", "RCV-A due (420,000)", FACE),
    (32, "standing_plan", "Line and advance repaid; 3,113.93 of charges paid", -(405_000_00 + li + ii + fi)),
    (32, "demo", "RCV-A residual 160,000 due, not paid", ""),
    (25, "demo", "Bookkeeper schedules month-2 payroll of 200,000 for day 42", ""),
    (34, "demo", "FLOW proposes 200,000 invoice financing (1,782.19, 32.5% a year); queued, owner approves", ""),
    (36, "demo", "Late residual arrives", FACE - int(face_a)),
    (37, "demo", "Cure advance lands", cure),
    (42, "demo", "Payroll month 2", pay_m2["amount_fen"]),
    (47, "all", "Operating bill", -10_000_000),
    (47, "baseline/standing_plan/option_a/demo", "Invoice issued day 2 paid (45-day terms)", FACE),
    (47, "ex01", "First breach under 60-day terms: 209,960.00 (90,040.00 short)", ""),
    (47, "demo", "Advance repaid (201,782.19); line repaid (148,423.17)", -(cure + cui + cuf + draw_a + lr)),
    (57, "option_b", "Invoice issued day 2 paid at 55 days, +0.30%", FACE + post(bp(rb) * FACE)),
    (60, "all", "Existing loan payment", -4_500_000),
    (60, "ex01", "Lowest 164,960.00 (135,040.00 short)", ""),
    (62, "ex01", "Invoice issued day 2 paid (60-day terms); breach ends", FACE),
]
with (HERE / "events.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["day", "scenario", "event", "amount_cny"])
    for d, sc, e, a in sorted(events, key=lambda r: r[0]):
        w.writerow([d, sc, e, f"{a / 100:.2f}" if a != "" else ""])

for k, v in R.items():
    print(f"{k:45s} {v['cny'] if v['cny'] is not None else v['value']}   {v['note']}")
