"""Figure 11b: what happened after Option A was agreed, as the demo runs it, days 0 to 62.

Render (from this folder):
    uv run --no-project --with matplotlib --with pillow python fig11b_cash_disruption.py

Three series of docs/deliverables/submission/work/fin/daily_cash.csv, all Option A (0.85% early payment on 260,000, terms
stay 45 days, credit line 147,210 drawn on day 0):
  option_a_as_quoted_cny                        as quoted on day 0 (reference; the same series as A3 in fig11a)
  option_a_as_quoted_plus_month2_payroll_cny    the bookkeeper's month-2 payroll (200,000 on day 42) added, the 160,000
                                                residual paid on time, no cure: what the payroll alone does
  demo_actual_option_a_late_residual_cure_cny   as the demo runs: the payroll added on day 25, the residual unpaid on day 32
                                                and paid on day 36, the 200,000 cure proposed on day 34 (32.5% a year, above
                                                the 15% ceiling, so queued as APR-000001 and approved by the owner), landing
                                                on day 37 and repaid on day 47
Events: work/fin/events.csv (scenario "demo"); the cost lines: work/fin/financial_audit.md sections 4.4 to 4.9. Day-62 cash
reconciles to the fen and is asserted below.
"""

from __future__ import annotations

import csv
from pathlib import Path

from flowstyle import AMBER, AMBER_INK, AMBER_SOFT, BUILD_FINAL, GREY, INK, INK_2, PURPLE, chart, save, stamp

FIN = Path(__file__).resolve().parents[2] / "submission" / "work" / "fin"
rows = list(csv.DictReader((FIN / "daily_cash.csv").open(encoding="utf-8")))
days = [int(r["day"]) for r in rows]
series = {k: [float(r[k]) for r in rows] for k in rows[0] if k != "day"}

RESERVE = 300_000.0
END_NO_ACTION, PAYROLL2 = 590_000.00, 200_000.00
# (column, id, label, payroll 2 included, cost in CNY, colour, line style, marker, line width)
LINES = [
    ("option_a_as_quoted_cny", "B0", "Option A as quoted (reference)", False, 3035.99, GREY, (0, (6, 2, 1.5, 2)), "D", 2.4),
    ("option_a_as_quoted_plus_month2_payroll_cny", "B1", "+ payroll 2; residual on time; no cure", True, 3035.99, AMBER,
     (0, (6, 2.5)), "s", 2.8),
    ("demo_actual_option_a_late_residual_cure_cny", "B2", "As the demo ran", True, 5205.36, PURPLE, "-", "^", 3.4),
]
for k, _i, _l, pay2, cost, *_ in LINES:
    assert round(series[k][-1], 2) == round(END_NO_ACTION - (PAYROLL2 if pay2 else 0) - cost, 2), (k, series[k][-1])
assert round(5205.36 - 3035.99, 2) == round(387.18 + 1782.19, 2)  # the overrun: line 15 days longer + the cure

fig, ax = chart(11.8, xlabel="day of the scenario (day 0 = 1 Oct 2026)", ylabel="closing cash (CNY)",
                rect=(0.145, 0.545, 0.815, 0.435))
ax.axhspan(0, RESERVE, color=AMBER_SOFT, zorder=0)
ax.axhline(RESERVE, color=INK, lw=2.0, ls=(0, (6, 3)), zorder=2)
ax.text(61.5, RESERVE - 12_000, "reserve ¥300,000 (signed mandate)", ha="right", va="top", fontsize=13.5, color=INK,
        bbox=dict(fc=AMBER_SOFT, ec="none", pad=1.0), zorder=5)
for n, (k, _i, _l, _p, _c, color, ls, mk, lw) in enumerate(LINES):
    ax.step(days, series[k], where="post", color=color, ls=ls, lw=lw, zorder=3 + n)
    marks = [d + n for d in (5, 15, 22, 39, 50, 56)]
    ax.plot(marks, [series[k][d] for d in marks], ls="none", marker=mk, ms=9, color=color, mec="white", mew=1.0,
            zorder=6)

ax.set_xlim(0, 62)
ax.set_ylim(0, 1_000_000)
ax.set_xticks(range(0, 61, 10))
ticks = range(0, 800_001, 100_000)
ax.set_yticks(ticks)
ax.set_yticklabels([f"¥{v // 1000}k" for v in ticks])

demo, pay = series[LINES[2][0]], series[LINES[1][0]]
ax.annotate("B2, day 42: ¥460,000 after the\npayroll; the reserve held", xy=(43, demo[42]), xytext=(52, 760_000),
            fontsize=13.5, color=PURPLE, va="center", ha="center", arrowprops=dict(arrowstyle="-", color=PURPLE, lw=1.2),
            bbox=dict(fc="white", ec="none", pad=1.0))
ax.annotate(f"B1, days 42–46: ¥{pay[42]:,.2f},\n¥{RESERVE - pay[42]:,.2f} short", xy=(44, pay[42]),
            xytext=(24, 95_000), fontsize=13.5, color=AMBER_INK, va="center", ha="center",
            arrowprops=dict(arrowstyle="-", color=AMBER_INK, lw=1.2), bbox=dict(fc=AMBER_SOFT, ec="none", pad=1.0))
ax.annotate("B2, days 32–35: held at\n¥300,000, line not repaid", xy=(33.5, RESERVE), xytext=(19, 215_000),
            fontsize=13.5, color=PURPLE, va="center", ha="center", arrowprops=dict(arrowstyle="-", color=PURPLE, lw=1.2),
            bbox=dict(fc=AMBER_SOFT, ec="none", pad=1.0))

MARKS = [(0, "1", 0), (2, "2", 1), (12, "3", 0), (25, "4", 0), (32, "5", 0), (34, "6", 1), (36, "7", 2), (37, "8", 0),
         (42, "9", 1), (47, "10", 0), (60, "11", 0)]
for d, n, lvl in MARKS:
    ax.text(d, 950_000 - lvl * 62_000, n, ha="center", va="center", fontsize=12, fontweight="bold", color="white",
            zorder=7, bbox=dict(boxstyle="circle,pad=0.18", fc=INK, ec="none"), clip_on=False)
    ax.axvline(d, color="#c9d0db", lw=0.9, zorder=1)
KEY = [
    ("1", "day 0: Option A agreed; credit line ¥147,210 drawn"),
    ("2", "day 2: buyer pays ¥257,790 early (¥260,000 at 0.85%); ¥160,000 residual due day 32"),
    ("3", "days 12, 20, 30: payroll −¥340,000, supplier −¥120,000, loan −¥45,000"),
    ("4", "day 25: the bookkeeper schedules a month-2 payroll of ¥200,000 for day 42 (B1, B2)"),
    ("5", "day 32: B2: the ¥160,000 residual is not paid; the line cannot be repaid"),
    ("6", "day 34: B2: FLOW proposes ¥200,000 invoice financing (¥1,782.19; 32.5% a year,\n"
          "above the 15% ceiling): queued as APR-000001, the owner approves; no cash moves"),
    ("7", "day 36: B2: the late ¥160,000 arrives"),
    ("8", "day 37: B2: the ¥200,000 advance lands"),
    ("9", "day 42: month-2 payroll −¥200,000 (B1, B2)"),
    ("10", "day 47: invoice +¥420,000; bill −¥100,000; B2 repays the advance\n"
           "(¥201,782.19) and the line (¥148,423.17)"),
    ("11", "day 60: loan payment −¥45,000"),
]
yy = 0.465
for n, t in KEY:
    two = "\n" in t
    fig.text(0.035, yy, n, ha="center", va="center", fontsize=11, fontweight="bold", color="white",
             bbox=dict(boxstyle="circle,pad=0.18", fc=INK, ec="none"))
    fig.text(0.062, yy + (0.0085 if two else 0), t, ha="left", va="top" if two else "center", fontsize=12.5, color=INK,
             linespacing=1.25)
    yy -= 0.041 if two else 0.0185

y0 = yy - 0.03
for x, h in ((0.70, "lowest"), (0.845, "day 62"), (0.975, "cost")):
    fig.text(x, y0 + 0.021, h, ha="right", fontsize=12.5, fontweight="bold", color=INK, va="center")
for i, (k, ident, label, _p, cost, color, ls, mk, lw) in enumerate(LINES):
    y = y0 - i * 0.022
    ln = fig.add_axes((0.012, y - 0.007, 0.05, 0.014))
    ln.axis("off")
    ln.set_xlim(0, 1)
    ln.set_ylim(-1, 1)
    ln.plot([0, 1], [0, 0], color=color, ls=ls, lw=lw)
    ln.plot([0.5], [0], marker=mk, ms=9, color=color, mec="white", mew=1.0)
    fig.text(0.07, y, ident, ha="left", va="center", fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.108, y, label, ha="left", va="center", fontsize=12.5, color=INK)
    fig.text(0.70, y, f"¥{min(series[k]):,.2f}", ha="right", va="center", fontsize=12.5, color=INK)
    fig.text(0.845, y, f"¥{series[k][-1]:,.2f}", ha="right", va="center", fontsize=12.5, color=INK)
    fig.text(0.975, y, f"¥{cost:,.2f}", ha="right", va="center", fontsize=12.5, color=INK)
fig.text(0.012, y0 - 3 * 0.022 - 0.004,
         "Day 62 = ¥590,000.00 − ¥200,000.00 month-2 payroll (B1, B2) − cost.\n"
         "B2 costs ¥2,169.37 more than quoted: ¥387.18 because the line stayed out\n"
         "15 days longer and ¥1,782.19 for the cure. The ¥2,210.00 discount is in every series.",
         ha="left", va="top", fontsize=12.5, color=INK_2, linespacing=1.3)
stamp(fig, "Golden books (synthetic), mandate v1, request EX01, Option A, demo clock; CNY.\n"
           "Data: work/fin/daily_cash.csv, events.csv (= the engine to the fen) · " + BUILD_FINAL)
save(fig, "fig11b-cash-disruption.png")
