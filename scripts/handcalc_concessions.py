#!/usr/bin/env python3
"""Independent hand calculation of the forward-concession valuation rules.

Standalone: standard library only (fractions), no import of `app.*`.

    PYTHONUTF8=1 python scripts/handcalc_concessions.py                 # print every section
    PYTHONUTF8=1 python scripts/handcalc_concessions.py --section NAME  # one section
    PYTHONUTF8=1 python scripts/handcalc_concessions.py --list          # section names
    PYTHONUTF8=1 python scripts/handcalc_concessions.py --check DOC.md  # every table row printed
                                                                        # here must appear verbatim in DOC.md

Conventions: money is integer fen, rates are exact Fractions, days are integers, year = 365 days,
posting = round half up to the fen: post(x) = floor(x + 1/2) on the signed value.
Inputs come from the golden scenario (fixtures/scenarios/golden_sme.json): recurring invoice face
42,000,000 fen every 30 days, next_issue_day 2, terms_days 45; mandate horizon 365 days; invoice
financing 780 bp a year plus 25 bp per 30-day period (FAC-IF).
"""
from __future__ import annotations

import sys
from fractions import Fraction
from math import ceil, floor

# --------------------------------------------------------------------------- inputs
F = 42_000_000          # golden recurring face, fen (CNY 420,000)
S0 = 2                  # golden next_issue_day
E = 30                  # golden every_days
TERMS = 45              # golden terms_days
H_GOLD = 365            # golden forward_concession_horizon_days
DELTA = 15              # extension under test, days
YEAR = 365

R10 = Fraction(1, 10)
# golden marginal rate = invoice financing all-in: rate + per-period fee annualised over 365 days
RATE_IF = Fraction(780, 10_000)
FEE_IF = Fraction(25, 10_000)
PERIOD = 30
RG = RATE_IF + FEE_IF * Fraction(YEAR, PERIOD)      # = 1301/12000 = 10.84166...%
RATES = (("10%", R10), ("golden 10.8417%", RG))

P_IF = 10_000_000       # break-even principal, fen (CNY 100,000)


# --------------------------------------------------------------------------- helpers
def post(x) -> int:
    """Round half up to the fen on the signed value."""
    return floor(Fraction(x) + Fraction(1, 2))


def yuan(fen: int) -> str:
    sign = "-" if fen < 0 else ""
    a = abs(fen)
    return f"{sign}¥{a // 100:,}.{a % 100:02d}"


def fen(x: int) -> str:
    return f"{x:,}"


def frac(x: Fraction) -> str:
    return str(x) if x.denominator != 1 else f"{x.numerator}"


def pct(x: Fraction, places: int = 4) -> str:
    """x as a percentage rounded half up to `places` decimals."""
    scaled = post(x * 100 * 10**places)
    s = f"{abs(scaled):0{places + 1}d}"
    out = f"{s[:-places]}.{s[-places:]}" if places else s
    return ("-" if scaled < 0 else "") + out + "%"


def issue_days(lo: int, hi: int) -> list[int]:
    """Recurring issue days S0 + k*E (k >= 0) inside the closed interval [lo, hi]."""
    return [d for d in range(S0, hi + 1, E) if d >= lo]


def scope(kind: str, today: int, horizon: int, eff: int | None = None,
          n: int | None = None, end_day: int | None = None) -> list[int]:
    """Dated invoice list of an obligation.  Window W = [today, today + horizon], closed."""
    lo = max(today, today if eff is None else eff)
    days = issue_days(lo, today + horizon)
    if kind == "ONE_OFF":
        return days[:1]
    if kind == "COUNT":
        return days[: int(n)]
    if kind == "DATE":
        return [d for d in days if d <= int(end_day)]
    if kind == "PERP":
        return days
    raise ValueError(kind)


def ext_each(face: int, delta: int, r: Fraction) -> Fraction:
    return Fraction(face * delta) * r / YEAR


def ext_total(days: list[int], delta: int, r: Fraction) -> tuple[Fraction, int, int]:
    """(exact fen, posted once, sum of per-invoice postings)."""
    each = ext_each(F, delta, r)
    exact = each * len(days)
    return exact, post(exact), len(days) * post(each)


def price_value(days: list[int], p_bp: int) -> int:
    """value = - sum post(p * F_i); positive p = supplier gains."""
    return -sum(post(Fraction(p_bp * F, 10_000)) for _ in days)


# --------------------------------------------------------------------------- scope catalogue
# id, today, horizon, kind, eff, n, end_day, description
CASES = [
    ("P90",   0, 90,  "PERP", None, None, None, "perpetual, H=90"),
    ("P180",  0, 180, "PERP", None, None, None, "perpetual, H=180"),
    ("P365",  0, 365, "PERP", None, None, None, "perpetual, H=365 (golden)"),
    ("P730",  0, 730, "PERP", None, None, None, "perpetual, H=730"),
    ("P360",  0, 360, "PERP", None, None, None, "perpetual, H=360 (last issue 332)"),
    ("P361",  0, 361, "PERP", None, None, None, "perpetual, H=361"),
    ("P362",  0, 362, "PERP", None, None, None, "perpetual, H=362 (issue day 362 on the edge of W)"),
    ("B90",   0, 90,  "COUNT", None, 3, None, "bounded N=3 (= invoices of P90), H=90"),
    ("B180",  0, 180, "COUNT", None, 6, None, "bounded N=6 (= invoices of P180), H=180"),
    ("B365",  0, 365, "COUNT", None, 13, None, "bounded N=13 (= invoices of P365), H=365"),
    ("B730",  0, 730, "COUNT", None, 25, None, "bounded N=25 (= invoices of P730), H=730"),
    ("Q365",  0, 365, "COUNT", None, 12, None, "bounded N=12 = floor(H/every), H=365"),
    ("Q730",  0, 730, "COUNT", None, 24, None, "bounded N=24 = floor(H/every), H=730"),
    ("T90",   0, 90,  "COUNT", None, 100, None, "bounded N=100, truncated by W, H=90"),
    ("D100",  0, 365, "DATE", None, None, 100, "date-bounded end_day=100, H=365"),
    ("D400",  0, 365, "DATE", None, None, 400, "date-bounded end_day=400, truncated by W, H=365"),
    ("O365",  0, 365, "ONE_OFF", None, None, None, "ONE_OFF, H=365"),
    ("O100",  0, 365, "ONE_OFF", 100, None, None, "ONE_OFF effective day 100 (first issue >= 100 is 122)"),
    ("N3",    0, 365, "COUNT", None, 3, None, "next 3, H=365"),
    ("N3e300", 0, 365, "COUNT", 300, 3, None, "next 3 from effective day 300 (302, 332, 362)"),
    ("N3e330", 0, 365, "COUNT", 330, 3, None, "next 3 from effective day 330, cut by W (332, 362)"),
    ("E100",  0, 365, "PERP", 100, None, None, "perpetual, effective day 100 (inside W)"),
    ("E362",  0, 365, "PERP", 362, None, None, "perpetual, effective day 362 (issue exactly on it)"),
    ("E363",  0, 365, "PERP", 363, None, None, "perpetual, effective day 363 (next issue 392 is outside W)"),
    ("E365",  0, 365, "PERP", 365, None, None, "perpetual, effective day 365 = today+H (edge of W)"),
    ("E1000", 0, 365, "PERP", 1000, None, None, "perpetual, effective day 1000 (beyond W)"),
    ("T34",   34, 365, "PERP", None, None, None, "today=34, perpetual, H=365"),
    ("T34h90", 34, 90, "PERP", None, None, None, "today=34, perpetual, H=90"),
    ("T34e100", 34, 365, "PERP", 100, None, None, "today=34, perpetual, effective day 100"),
    ("T34o",  34, 365, "ONE_OFF", None, None, None, "today=34, ONE_OFF"),
    ("T34n3", 34, 365, "COUNT", None, 3, None, "today=34, next 3"),
]
CASE_BY_ID = {c[0]: c for c in CASES}


def days_of(cid: str) -> list[int]:
    _, today, h, kind, eff, n, end_day, _ = CASE_BY_ID[cid]
    return scope(kind, today, h, eff, n, end_day)


def span(days: list[int]) -> str:
    if not days:
        return "none"
    if len(days) <= 4:
        return ",".join(map(str, days))
    return f"{days[0]},{days[1]},...,{days[-1]}"


# --------------------------------------------------------------------------- sections
def sec_inputs() -> list[str]:
    out = ["| input | value |", "|---|---|"]
    out += [
        f"| face F | {fen(F)} fen ({yuan(F)}) |",
        f"| every_days e | {E} |",
        f"| next_issue_day s0 | {S0} |",
        f"| terms_days | {TERMS} |",
        f"| mandate horizon H | {H_GOLD} days |",
        f"| extension delta | {DELTA} days |",
        f"| rate r1 | 1/10 = {pct(R10, 4)} |",
        f"| golden marginal rate r2 = 780bp + 25bp x 365/30 | {frac(RG)} = {pct(RG, 6)} |",
        f"| per-invoice cost at r1, exact | {frac(ext_each(F, DELTA, R10))} fen = {float(ext_each(F, DELTA, R10)):.4f} fen |",
        f"| per-invoice cost at r2, exact | {frac(ext_each(F, DELTA, RG))} fen = {float(ext_each(F, DELTA, RG)):.4f} fen |",
        f"| per-invoice cost at r1, posted | {fen(post(ext_each(F, DELTA, R10)))} fen ({yuan(post(ext_each(F, DELTA, R10)))}) |",
        f"| per-invoice cost at r2, posted | {fen(post(ext_each(F, DELTA, RG)))} fen ({yuan(post(ext_each(F, DELTA, RG)))}) |",
    ]
    return out


def sec_scopes() -> list[str]:
    out = ["| id | today | H | W = [today, today+H] | scope | N | issue days in scope |",
           "|---|---|---|---|---|---|---|"]
    for cid, today, h, kind, eff, n, end_day, desc in CASES:
        d = days_of(cid)
        out.append(f"| {cid} | {today} | {h} | [{today}, {today + h}] | {desc} | {len(d)} | {span(d)} |")
    return out


def sec_equivalence() -> list[str]:
    out = ["| check | result |", "|---|---|"]
    for a, b in (("P90", "B90"), ("P180", "B180"), ("P365", "B365"), ("P730", "B730"),
                 ("P90", "T90"), ("P365", "D400")):
        out.append(f"| {a} and {b} give the same invoice list | {days_of(a) == days_of(b)} |")
    for a, b in (("P365", "Q365"), ("P730", "Q730")):
        da, db = days_of(a), days_of(b)
        out.append(f"| {a} ({len(da)} invoices) vs {b} ({len(db)} invoices) | same list {da == db}; "
                   f"extra invoice in {a}: day {sorted(set(da) - set(db))[0]} |")
    return out


def _ext_table(r: Fraction) -> list[str]:
    out = ["| id | N | exact total (fen) | posted once | sum of per-invoice postings | once minus per-invoice (fen) | posted once (CNY) |",
           "|---|---|---|---|---|---|---|"]
    for cid, *_ in CASES:
        d = days_of(cid)
        exact, once, each = ext_total(d, DELTA, r)
        out.append(f"| {cid} | {len(d)} | {frac(exact)} | {fen(once)} | {fen(each)} | {once - each} | {yuan(once)} |")
    return out


def sec_ext_r10() -> list[str]:
    return _ext_table(R10)


def sec_ext_rg() -> list[str]:
    return _ext_table(RG)


def sec_ext_gain() -> list[str]:
    out = ["| case | exact (fen) | posted once | note |", "|---|---|---|---|"]
    for name, r in RATES:
        d = days_of("P365")
        exact, once, _ = ext_total(d, -DELTA, r)
        out.append(f"| delta=-15, perpetual H=365, N={len(d)}, r={name} | {frac(exact)} | {fen(once)} | gain; mirror of the +15 cost, differs only when the exact value ends in .5 |")
    return out


def _price_table(p_bp: int) -> list[str]:
    out = [f"| id | N | per-invoice posting (fen) | value (fen) | value (CNY) |", "|---|---|---|---|---|"]
    per = post(Fraction(p_bp * F, 10_000))
    for cid, *_ in CASES:
        d = days_of(cid)
        v = price_value(d, p_bp)
        out.append(f"| {cid} | {len(d)} | {fen(per)} | {fen(v)} | {yuan(v)} |")
    return out


def sec_price_45() -> list[str]:
    return _price_table(45)


def sec_price_100() -> list[str]:
    return _price_table(100)


def sec_cap() -> list[str]:
    cap = 500_000       # CNY 5,000
    rebate = 600_000    # CNY 6,000
    out = ["| case | rebate cost | price-adjustment value | net counted against cap | cap | result |",
           "|---|---|---|---|---|---|"]

    def row(name, gain_value, counts):
        net = rebate + (gain_value if counts else 0)
        res = "pass" if net <= cap else f"BREACH by {fen(net - cap)} fen ({yuan(net - cap)})"
        out.append(f"| {name} | {fen(rebate)} | {fen(gain_value)} | {fen(net)} | {fen(cap)} | {res} |")

    d1000 = scope("PERP", 0, 365, eff=1000)
    row("F-FIN-01: firm +1% from day 1000, H=365 (N=0)", price_value(d1000, 100), True)
    d100 = scope("PERP", 0, 365, eff=100)
    row("+1% from day 100, FIRM, H=365 (N=9)", price_value(d100, 100), True)
    row("+1% from day 100, NOT firm, H=365 (N=9)", price_value(d100, 100), False)
    d362 = scope("PERP", 0, 365, eff=362)
    row("+1% from day 362, FIRM, H=365 (N=1)", price_value(d362, 100), True)
    d363 = scope("PERP", 0, 365, eff=363)
    row("+1% from day 363, FIRM, H=365 (N=0)", price_value(d363, 100), True)
    return out


def _dated_profile(every: int, ext_due_offset: int) -> tuple[int, int, Fraction]:
    """Charges (one per invoice, dated on the extended due day) per consecutive 30-day block."""
    first = S0 + TERMS + DELTA
    n_blocks = 1200
    counts = [0] * n_blocks
    d = first
    while d < 30 * n_blocks:
        counts[d // 30] += 1
        d += every
    steady = counts[10:n_blocks - 10]       # drop start-up and tail
    return min(steady), max(steady), Fraction(sum(steady), len(steady))


def sec_service_debt() -> list[str]:
    out = []
    for name, r in RATES:
        out += [f"Rate {name}.", "",
                "| every_days | per-invoice cost (exact fen) | annual cost = per-invoice x 365/e (exact fen) | monthly service = annual/12 (exact fen) | monthly service posted | monthly service (CNY) | extra debt F x delta / e (exact fen) | extra debt posted | extra debt (CNY) |",
                "|---|---|---|---|---|---|---|---|---|"]
        for e in (15, 30, 60, 365):
            each = ext_each(F, DELTA, r)
            annual = each * Fraction(YEAR, e)
            monthly = annual / 12
            debt = Fraction(F * DELTA, e)
            out.append(f"| {e} | {frac(each)} | {frac(annual)} | {frac(monthly)} | {fen(post(monthly))} | {yuan(post(monthly))} | {frac(debt)} | {fen(post(debt))} | {yuan(post(debt))} |")
        out.append("")
    return out[:-1]


def sec_identity() -> list[str]:
    out = ["| every_days | rate | monthly service posted | extra debt posted x r / 12 posted | equal |", "|---|---|---|---|---|"]
    for name, r in RATES:
        for e in (15, 30, 60, 365):
            monthly = ext_each(F, DELTA, r) * Fraction(YEAR, e) / 12
            via_debt = Fraction(F * DELTA, e) * r / 12
            out.append(f"| {e} | {name} | {fen(post(monthly))} | {fen(post(via_debt))} | {post(monthly) == post(via_debt)} |")
    return out


def sec_dated() -> list[str]:
    """Alternative to rule 6: sum of dated charges per 30-day month (charge dated on extended due day)."""
    out = []
    for name, r in RATES:
        each = post(ext_each(F, DELTA, r))
        out += [f"Rate {name}; one charge of {fen(each)} fen per invoice dated on the extended due day (issue + {TERMS} + {DELTA}).", "",
                "| every_days | charges per 30-day month: min | max | mean | peak month (fen) | mean month (exact fen) | steady-state (fen) | steady-state / mean |",
                "|---|---|---|---|---|---|---|---|"]
        for e in (15, 30, 60, 365):
            lo, hi, _sim_mean = _dated_profile(e, TERMS + DELTA)
            mean = Fraction(30, e)          # exact long-run charges per 30-day block
            exact_mean = ext_each(F, DELTA, r) * mean
            steady = ext_each(F, DELTA, r) * Fraction(YEAR, e) / 12
            out.append(f"| {e} | {lo} | {hi} | {float(mean):.4f} | {fen(hi * each)} | {float(exact_mean):.2f} | {fen(post(steady))} | {float(steady / exact_mean):.4f} |")
        out.append("")
    return out[:-1]


def finance_charges(p: int, n: int, upfront_bp: int) -> dict:
    k = max(1, ceil(n / PERIOD))
    interest = post(Fraction(p) * RATE_IF * PERIOD * k / YEAR)
    fee = post(Fraction(p) * FEE_IF * k)
    up = post(Fraction(p * upfront_bp, 10_000))
    total = interest + fee + up
    c = Fraction(total, p)
    return {"k": k, "interest": interest, "fee": fee, "upfront": up, "total": total, "c": c,
            "d": c / (1 + c)}


def _be_table(upfront_bp: int) -> list[str]:
    out = [f"Upfront fee {upfront_bp} bp (charged once).", "",
           "| n | k = max(1, ceil(n/30)) | interest (fen) | period fees (fen) | upfront (fen) | total charges (fen) | c(n) | d* = c/(1+c) |",
           "|---|---|---|---|---|---|---|---|"]
    for n in (1, 29, 30, 31, 59, 60, 61, 89, 90, 91):
        r = finance_charges(P_IF, n, upfront_bp)
        out.append(f"| {n} | {r['k']} | {fen(r['interest'])} | {fen(r['fee'])} | {fen(r['upfront'])} | {fen(r['total'])} | {pct(r['c'], 6)} | {pct(r['d'], 6)} |")
    return out


def sec_breakeven() -> list[str]:
    return _be_table(0) + [""] + _be_table(100)


def sec_breakeven_golden() -> list[str]:
    out = ["| n (period count k) | d* with no upfront fee, 4 dp | d* exact (no posting), 6 dp |", "|---|---|---|"]
    for n in (30, 60, 90):
        r = finance_charges(P_IF, n, 0)
        k = r["k"]
        c_exact = RATE_IF * PERIOD * k / YEAR + FEE_IF * k
        out.append(f"| {n} (k={k}) | {pct(r['d'], 4)} | {pct(c_exact / (1 + c_exact), 6)} |")
    return out


def sec_golden_extension() -> list[str]:
    """Golden extension valuation at r2 with the window-based invoice count."""
    each_exact = ext_each(F, DELTA, RG)
    out = ["| basis | N | exact (fen) | posted once | posted once (CNY) |", "|---|---|---|---|---|"]
    for label, cid in (("window count, today=0, H=365, anchor s0=2", "P365"),
                       ("floor(H/every) count (phase-blind)", "Q365")):
        d = days_of(cid)
        exact = each_exact * len(d)
        out.append(f"| {label} | {len(d)} | {frac(exact)} | {fen(post(exact))} | {yuan(post(exact))} |")
    out.append(f"| difference (13 minus 12 invoices) | 1 | {frac(each_exact)} | {fen(post(each_exact * 13) - post(each_exact * 12))} | |")
    return out


SECTIONS = {
    "inputs": sec_inputs,
    "scopes": sec_scopes,
    "equivalence": sec_equivalence,
    "ext_r10": sec_ext_r10,
    "ext_rg": sec_ext_rg,
    "ext_gain": sec_ext_gain,
    "price_45": sec_price_45,
    "price_100": sec_price_100,
    "cap": sec_cap,
    "service_debt": sec_service_debt,
    "identity": sec_identity,
    "dated": sec_dated,
    "breakeven": sec_breakeven,
    "breakeven_golden": sec_breakeven_golden,
    "golden_extension": sec_golden_extension,
}


def render(name: str) -> str:
    return "\n".join(SECTIONS[name]())


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--list" in argv:
        print("\n".join(SECTIONS))
        return 0
    if "--section" in argv:
        print(render(argv[argv.index("--section") + 1]))
        return 0
    if "--check" in argv:
        path = argv[argv.index("--check") + 1]
        with open(path, encoding="utf-8") as fh:
            doc = fh.read()
        rows = [ln for name in SECTIONS for ln in SECTIONS[name]() if ln.startswith("|")]
        missing = [ln for ln in rows if ln not in doc]
        print(f"checked {len(rows)} table rows against {path}: {len(missing)} missing")
        for ln in missing:
            print("MISSING:", ln)
        return 1 if missing else 0
    for name in SECTIONS:
        print(f"## {name}\n")
        print(render(name))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
