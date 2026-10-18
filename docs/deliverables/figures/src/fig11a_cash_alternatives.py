"""Figure 11a: the financing alternatives for Foshan's request EX01, like for like, days 0 to 62.

Render (from this folder):
    uv run --no-project --with matplotlib --with pillow python fig11a_cash_alternatives.py

Five series of docs/deliverables/submission/work/fin/daily_cash.csv that share the same events: the day-0 golden books
(payroll day 12, supplier day 20, loan payments days 30 and 60, bill day 47), every buyer invoice paid on its due day, no
month-2 payroll and no late payment. They differ only in the choice made on day 0:
  baseline_no_funding_cny               no action
  standing_plan_line150k_if255k_cny     FLOW's standing plan (credit line 150,000 + invoice financing 255,000)
  ex01_as_asked_no_funding_cny          the request accepted as asked (60-day terms, 1.2% early payment), no funding
  option_a_as_quoted_cny                Option A (0.85% early payment on 260,000, terms stay 45 days) + its 147,210 line
  option_b_with_its_funding_cny         Option B (55 days, +0.30%) + its 3,706.46 plan (line 90,000 + financing 315,000)
The columns with the month-2 payroll or the late residual are in fig11b. The values are the financial audit's independent
recomputation, equal to the engine replayed through the API to the fen (work/fin/compare.csv, 39 of 39). Day-62 cash
reconciles: 590,000.00 (no action) minus each choice's net cost, asserted below.
"""

from __future__ import annotations

import csv
from pathlib import Path

from flowstyle import AMBER, AMBER_INK, AMBER_SOFT, BLUE, BUILD_FINAL, GREY, INK, INK_2, PURPLE, chart, save, stamp

FIN = Path(__file__).resolve().parents[2] / "submission" / "work" / "fin"
rows = list(csv.DictReader((FIN / "daily_cash.csv").open(encoding="utf-8")))
days = [int(r["day"]) for r in rows]


def col(name: str) -> list[float]:
    return [float(r[name]) for r in rows]


RESERVE = 300_000.0
TEAL = "#0b7a75"  # a fifth series hue; it also has its own marker and dash, so colour is never the only cue
# (column, id, label, net cost of the choice in CNY, colour, line style, marker)
LINES = [
    ("baseline_no_funding_cny", "A0", "No action", 0.00, GREY, (0, (6, 2, 1.5, 2)), "D"),
    ("standing_plan_line150k_if255k_cny", "A1", "Standing plan (line + financing)", 3113.93, BLUE, "-", "o"),
    ("ex01_as_asked_no_funding_cny", "A2", "EX01 as asked, no funding", 5040.00, AMBER, (0, (6, 2.5)), "s"),
    ("option_a_as_quoted_cny", "A3", "Option A + line ¥147,210", 3035.99, PURPLE, (0, (2, 1.4)), "^"),
    ("option_b_with_its_funding_cny", "A4", "Option B + ¥3,706.46 plan", 3706.46 - 1260.00, TEAL,
     (0, (4, 1.5, 1, 1.5, 1, 1.5)), "v"),
]
END_NO_ACTION = 590_000.00
series = {k: col(k) for k, *_ in LINES}
for k, _i, _l, cost, *_ in LINES:  # day-62 cash = no action minus the choice's net cost, to the fen
    assert round(series[k][-1], 2) == round(END_NO_ACTION - cost, 2), (k, series[k][-1], cost)

fig, ax = chart(11.6, xlabel="day of the scenario (day 0 = 1 Oct 2026)", ylabel="closing cash (CNY)",
                rect=(0.145, 0.535, 0.815, 0.45))
ax.axhspan(-150_000, RESERVE, color=AMBER_SOFT, zorder=0)
ax.axhline(RESERVE, color=INK, lw=2.0, ls=(0, (6, 3)), zorder=2)
ax.text(61.5, RESERVE - 12_000, "reserve ¥300,000 (signed mandate)", ha="right", va="top", fontsize=13.5, color=INK,
        bbox=dict(fc=AMBER_SOFT, ec="none", pad=1.0), zorder=5)
ax.axhline(0, color=INK_2, lw=1.0, zorder=1)
for n, (k, _i, _l, _c, color, ls, mk) in enumerate(LINES):
    ax.step(days, series[k], where="post", color=color, ls=ls, lw=2.8, zorder=3)
    marks = [d + n for d in (4, 14, 23, 35, 49)]  # staggered, so coinciding lines still show each marker
    ax.plot(marks, [series[k][d] for d in marks], ls="none", marker=mk, ms=9, color=color, mec="white", mew=1.0,
            zorder=4)

ax.set_xlim(0, 62)
ax.set_ylim(-150_000, 1_000_000)
ax.set_xticks(range(0, 61, 10))
ticks = range(-100_000, 800_001, 100_000)
ax.set_yticks(ticks)
ax.set_yticklabels([("−" if v < 0 else "") + f"¥{abs(v) // 1000}k" for v in ticks])

base, ex01 = series[LINES[0][0]], series[LINES[2][0]]
ax.annotate("A0: −¥105,000, days 30–31", xy=(30.5, base[30]), xytext=(36, -95_000), fontsize=13.5, color=INK_2,
            va="center", arrowprops=dict(arrowstyle="-", color=INK_2, lw=1.2))
ax.annotate("A2: ¥209,960 on day 47,\n¥164,960 on days 60–61", xy=(53, ex01[53]), xytext=(41, 90_000),
            fontsize=13.5, color=AMBER_INK, va="center", arrowprops=dict(arrowstyle="-", color=AMBER_INK, lw=1.2))
ax.annotate("A1, A3, A4 touch ¥300,000\non days 30–31", xy=(30.5, RESERVE), xytext=(17, 215_000), fontsize=13.5,
            color=INK, va="center", ha="center", arrowprops=dict(arrowstyle="-", color=INK, lw=1.2),
            bbox=dict(fc=AMBER_SOFT, ec="none", pad=1.0))

# dated events shared by every series, numbered on the plot and explained below it
MARKS = [(0, "1", 0), (2, "2", 1), (3, "3", 0), (12, "4", 0), (20, "5", 0), (30, "6", 0), (32, "7", 1), (47, "8", 0),
         (57, "9", 0), (60, "10", 1), (62, "11", 0)]
for d, n, lvl in MARKS:
    ax.text(d, 945_000 - lvl * 70_000, n, ha="center", va="center", fontsize=12, fontweight="bold", color="white",
            zorder=6, bbox=dict(boxstyle="circle,pad=0.18", fc=INK, ec="none"), clip_on=False)
    ax.axvline(d, color="#c9d0db", lw=0.9, zorder=1)
KEY = [
    ("1", "day 0: decision; lines drawn (A1 ¥150,000; A3 ¥147,210; A4 ¥90,000)"),
    ("2", "day 2: early payment on invoice RCV-A (A2 ¥414,960; A3 ¥257,790)"),
    ("3", "day 3: invoice financing lands (A1 ¥255,000; A4 ¥315,000)"),
    ("4", "day 12: payroll −¥340,000"),
    ("5", "day 20: supplier payment −¥120,000"),
    ("6", "day 30: loan payment −¥45,000"),
    ("7", "day 32: RCV-A due; A1, A3 and A4 repay their line or advance"),
    ("8", "day 47: day-2 invoice paid +¥420,000 (A2 on day 62, A4 on day 57); bill −¥100,000"),
    ("9", "day 57: A4's invoice paid at 55 days, +0.30% (+¥421,260)"),
    ("10", "day 60: loan payment −¥45,000"),
    ("11", "day 62: A2's invoice paid at 60 days (+¥420,000); A2 back above the reserve"),
]
for i, (n, t) in enumerate(KEY):
    yy = 0.455 - i * 0.0185
    fig.text(0.035, yy, n, ha="center", va="center", fontsize=11, fontweight="bold", color="white",
             bbox=dict(boxstyle="circle,pad=0.18", fc=INK, ec="none"))
    fig.text(0.062, yy, t, ha="left", va="center", fontsize=12.5, color=INK)

# the series key with reconciled values (lowest closing cash, day-62 cash, net cost)
y0 = 0.225
for x, h in ((0.66, "lowest"), (0.82, "day 62"), (0.975, "net cost")):
    fig.text(x, y0 + 0.021, h, ha="right", fontsize=12.5, fontweight="bold", color=INK, va="center")
for i, (k, ident, label, cost, color, ls, mk) in enumerate(LINES):
    yy = y0 - i * 0.022
    ln = fig.add_axes((0.012, yy - 0.007, 0.05, 0.014))
    ln.axis("off")
    ln.set_xlim(0, 1)
    ln.set_ylim(-1, 1)
    ln.plot([0, 1], [0, 0], color=color, ls=ls, lw=2.8)
    ln.plot([0.5], [0], marker=mk, ms=9, color=color, mec="white", mew=1.0)
    fig.text(0.07, yy, ident, ha="left", va="center", fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.108, yy, label, ha="left", va="center", fontsize=12.5, color=INK)
    low = min(series[k])
    fig.text(0.66, yy, ("−" if low < 0 else "") + f"¥{abs(low):,.2f}", ha="right", va="center", fontsize=12.5, color=INK)
    fig.text(0.82, yy, f"¥{series[k][-1]:,.2f}", ha="right", va="center", fontsize=12.5, color=INK)
    fig.text(0.975, yy, f"¥{cost:,.2f}", ha="right", va="center", fontsize=12.5, color=INK)
fig.text(0.012, y0 - 5 * 0.022 - 0.008, "Net cost = discount + interest + fees − premium received (A4: ¥3,706.46 − ¥1,260.00).\n"
         "Day 62 = ¥590,000.00 (no action) − net cost. A2 is below the reserve on days 47–61.", ha="left", va="top",
         fontsize=12.5, color=INK_2, linespacing=1.3)
stamp(fig, "Golden books (synthetic), mandate v1, request EX01; same events in every series; CNY.\n"
           "Data: work/fin/daily_cash.csv, events.csv (= the engine to the fen) · " + BUILD_FINAL)
save(fig, "fig11a-cash-alternatives.png")
