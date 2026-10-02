"""Independent oracle for the TermsLedger golden values.

Written separately from the engine so tests compare two implementations.
Rules follow docs/adr/0002-rounding.md. Run: python3 fixtures/golden/compute_golden.py
Writes fixtures/golden/golden_values.json (all money in integer fen).
"""
from fractions import Fraction as F
import json, pathlib

def fen(x: F) -> int:
    """Round an exact yuan amount to integer fen, half-up (away from zero)."""
    v = x * 100
    sign = -1 if v < 0 else 1
    v = abs(v)
    q, r = divmod(v.numerator, v.denominator)
    if F(r, v.denominator) >= F(1, 2):
        q += 1
    return sign * q

def ratio2(x: F) -> str:
    """Display a ratio to 2 dp, half-up."""
    v = x * 100
    q, r = divmod(v.numerator, v.denominator)
    if F(r, v.denominator) >= F(1, 2):
        q += 1
    return f"{q // 100}.{q % 100:02d}"

Y = lambda s: F(s)  # yuan
bp = lambda n: F(n, 10000)

LINE_RATE = bp(640)
IF_RATE, IF_FEE = bp(780), bp(25)          # per 30-day advance
GL_RATE = bp(500)                           # 4.0% + 1.0% guarantee fee
out = {}

# 7.4 router table
line_int = fen(Y(150000) * LINE_RATE * 32 / 365)
def if_cost(amount, days, period=30):
    """Invoice financing bills interest and fee in whole 30-day periods (ADR-0003)."""
    periods = -(-days // period)
    return fen(amount * IF_RATE * periods * period / 365) + fen(amount * IF_FEE * periods)

if_cost_210k_30d = if_cost(Y(210000), 29)  # advance lands day 3 (lead time), repaid day 32
face_12 = fen(Y(210000) / (1 - bp(120)))            # grossed-up face, fen
disc_12 = face_12 - 21000000
face_15 = fen(Y(210000) / (1 - bp(150)))
disc_15 = face_15 - 21000000
out["full_discount_1_2pct"] = fen(Y(420000) * bp(120))
out["line_interest_150k_32d"] = line_int
out["if_cost_210k_30d"] = if_cost_210k_30d
out["v1_partial_face"] = face_12
out["v1_partial_discount"] = disc_12
out["v1_optimum_total"] = line_int + disc_12
out["v2_optimum_total"] = line_int + if_cost_210k_30d
out["example2_line_plus_partial_1_5pct"] = line_int + disc_15
out["funding_need_before_day_32"] = 46000000 + 30000000 - 40000000

# break-even early-pay discount: d/(1-d) < c  =>  d < c/(1+c), c = IF cost share for 30 days
c = IF_RATE * 30 / 365 + IF_FEE
be = c / (1 + c)
out["if_30d_cost_share_bp_x100"] = round(c * 1000000)   # 0.891% -> 8911 (hundredths of a bp)
out["break_even_discount_bp"] = int(be * 10000)          # truncated: must be strictly below
out["break_even_discount_display"] = f"{be*100:.2f}%"

# 7.5 terms extension as a loan, valued on the dated invoices of the window (docs/FINANCIAL_SEMANTICS.md section 6)
# Window W = [today, today + H), half-open. Golden: today = 0, H = 365 (mandate forward_concession_horizon_days);
# the buyer's recurring invoice issues on day 2 and every 30 days after, face 420,000 yuan, terms 45 days.
TODAY, HORIZON, FIRST_ISSUE, EVERY, DELTA = 0, 365, 2, 30, 15
issue_days = [d for d in range(FIRST_ISSUE, TODAY + HORIZON, EVERY) if d >= TODAY]   # 2, 32, ..., 362
n_inv = len(issue_days)                                  # 13 invoices in the window, not floor(365/30) = 12
per_exact = Y(420000) * DELTA / 365                      # one invoice, exact yuan
if_all_in = IF_RATE + IF_FEE * F(365, 30)
# pro forma (steady state): extra debt = face x delta / invoice interval; monthly service = extra debt x r / 12
extra_debt_exact = Y(420000) * DELTA / EVERY
out["extension_extra_receivables"] = fen(extra_debt_exact)
out["extension_monthly_service"] = fen(extra_debt_exact * if_all_in / 12)
out["extension_notional_line_per_invoice"] = fen(per_exact * LINE_RATE)
out["extension_notional_line_12m"] = fen(n_inv * per_exact * LINE_RATE)   # key name kept: the 12-month horizon
out["extension_committed_per_invoice"] = fen(per_exact * if_all_in)
out["extension_committed_12m"] = fen(n_inv * per_exact * if_all_in)
out["if_all_in_rate_display"] = f"{if_all_in*100:.4f}%"
# expected plan: 21-day invoice-financing bridge, then guaranteed loan for the rest of the year
out["extension_expected_12m"] = fen(n_inv * per_exact * (if_all_in * 21 + GL_RATE * (365 - 21)) / 365)

# 6.5 verdict
rebate_max = fen(Y(400000) * bp(100))
out["rebate_max"] = rebate_max
out["forward_ledger_total"] = rebate_max + out["extension_committed_12m"]
out["concession_cap"] = 500000

# day-47 timeline (ADR-0003): accept full package, no new funding
cash = 40000000 + (42000000 - out["full_discount_1_2pct"])  # day 2
cash -= 34000000   # day 12 payroll
cash -= 12000000   # day 20 supplier
day47_45 = cash + 42000000 - 10000000
day47_60 = cash - 10000000
out["cash_day20"] = cash
out["cash_day47_45d_terms"] = day47_45
out["cash_day47_60d_terms"] = day47_60
out["reserve_shortfall_day47"] = 30000000 - day47_60
# cure: carry the shortfall on the committed marginal permanent source (invoice financing), requested
# on day 0 against the day-2 invoice: lands day 5 (lead 3), repaid day 62 -> 57 days -> 2 periods (ADR-0003)
sf = F(out["reserve_shortfall_day47"], 100)
out["reserve_cure_cost_if"] = if_cost(sf, 57)

# Counter A
# face = the exact gross-up of the gap net of the committed line, rounded UP to a whole 100 yuan (so it nets
# at least the gap); the rest of the gap is carried on the committed line, whose cost is the funding cost
ca_face = -(-(Y(210000) / (1 - bp(85))) // 100) * 100
out["counter_a_discount"] = fen(ca_face * bp(85))
ca_line_draw = Y(360000) - (ca_face - F(out["counter_a_discount"], 100))
out["counter_a_total"] = out["counter_a_discount"] + fen(ca_line_draw * LINE_RATE * 32 / 365)
# Counter B
out["counter_b_price_adj_per_invoice"] = fen(Y(420000) * bp(45))
# A gain is dated like a cost: on the invoice's ISSUE day (so the same 13 invoices). Shortening mirrors the extension.
out["extension_shortening_gain_12m"] = -out["extension_committed_12m"]
out["counter_b_price_gain_12m"] = -n_inv * out["counter_b_price_adj_per_invoice"]
out["counter_b_net_12m"] = out["extension_committed_12m"] + out["counter_b_price_gain_12m"]

# 7.6 covenants (exact comparisons; display 2 dp)
ebitda_m, ds_m = Y(90000), Y(45000)
debt_base = Y(1500000) + Y(150000)
ext_int_m = F(out["extension_monthly_service"], 100)
out["dscr_base"] = ratio2(ebitda_m / ds_m)
out["dscr_after_extension"] = ratio2(ebitda_m / (ds_m + ext_int_m))
out["leverage_base"] = ratio2(debt_base / (ebitda_m * 12))
out["leverage_after_extension"] = ratio2((debt_base + F(out["extension_extra_receivables"], 100)) / (ebitda_m * 12))

# 7.7 capex
def pmt(p, annual, n):
    r = annual / 12
    # exact annuity factor via Fraction power
    return p * r / (1 - 1 / (1 + r) ** n)

def schedule(p, annual, n):
    """Payments rounded half-up to fen each period; final payment clears the balance."""
    pay = fen(pmt(p, annual, n))
    bal = fen(p) ; r = annual / 12 ; total_int = 0
    for k in range(1, n + 1):
        i = fen(F(bal, 100) * r)
        total_int += i
        princ = pay - i if k < n else bal
        bal -= princ
    return pay, total_int

cap = {}
for key, rate, n in (("loan_18m", bp(560), 18), ("loan_36m", bp(560), 36), ("lease_48m", bp(720), 48)):
    pay, ti = schedule(Y(600000), rate, n)
    pf = F(pay, 100)
    cap[key] = {
        "monthly_payment": pay,
        "total_interest": ti,
        "dscr_m1_3": ratio2(ebitda_m / (ds_m + pf)),
        "dscr_m4_on": ratio2((ebitda_m + 22000) / (ds_m + pf)),
        "dscr_m1_3_passes": ebitda_m / (ds_m + pf) >= F(125, 100),
    }
cap["lease_minus_36m_interest"] = cap["lease_48m"]["total_interest"] - cap["loan_36m"]["total_interest"]
# NPV at a 10% annual hurdle, discounted monthly at the effective rate (1.10)^(1/12) - 1.
# The rate is irrational, so use 50-digit Decimal and round once to fen (ADR-0002).
from decimal import Decimal, getcontext
getcontext().prec = 50
rm = Decimal("1.10") ** (Decimal(1) / Decimal(12)) - 1
npv_d = -Decimal(600000) + sum(Decimal(22000) / (1 + rm) ** m for m in range(4, 61))
cap["npv"] = fen(F(npv_d))
cum, payback = -600000, None
for m in range(1, 61):
    if m >= 4: cum += 22000
    if cum >= 0 and payback is None: payback = m
cap["payback_month"] = payback
cap["leverage_financed"] = ratio2((debt_base + Y(600000)) / (ebitda_m * 12))
cap["leverage_financed_plus_extension"] = ratio2((debt_base + Y(600000) + F(out["extension_extra_receivables"], 100)) / (ebitda_m * 12))
cap["cash_above_reserve"] = 40000000 - 30000000 + 15000000
out["capex"] = cap

for k, v in cap.items():
    if isinstance(v, dict): v["dscr_m1_3_passes"] = bool(v["dscr_m1_3_passes"])
p = pathlib.Path(__file__).with_name("golden_values.json")
p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
