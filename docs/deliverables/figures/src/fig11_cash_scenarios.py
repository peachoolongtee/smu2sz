"""Figure 4 of the technical document: the demo company's closing cash under four scenarios, days 0 to 62.

Render (from this folder):
    uv run --no-project --with matplotlib --with pillow python fig11_cash_scenarios.py

Data: docs/deliverables/submission/work/fin/daily_cash.csv and events.csv, written by the financial audit's independent
recomputation (work/fin/independent.py, which reads only fixtures/scenarios/golden_sme.json and golden_sme.events.json).
The engine, replayed day by day through the API in process (work/fin/engine_probe2.py), gives the same values to the fen
(work/fin/compare.csv, 39 of 39). All amounts are CNY; day 0 is 1 Oct 2026 (the books' as-of date); one closing balance
per day. Only the demo series carries the month-2 payroll, which the bookkeeper adds on day 25.
"""

from __future__ import annotations

import csv
from pathlib import Path

from flowstyle import AMBER, AMBER_INK, AMBER_SOFT, BLUE, BUILD, GREY, INK, INK_2, PURPLE, chart, save, stamp

FIN = Path(__file__).resolve().parents[2] / "submission" / "work" / "fin"

rows = list(csv.DictReader((FIN / "daily_cash.csv").open(encoding="utf-8")))
days = [int(r["day"]) for r in rows]


def col(name: str) -> list[float]:
    return [float(r[name]) / 1000 for r in rows]  # thousands of CNY


RESERVE = col("reserve_cny")
LINES = [
    ("baseline_no_funding_cny", "Today's books, no new funding", GREY, (0, (6, 2, 1.5, 2)), 2.6),
    ("standing_plan_line150k_if255k_cny", "FLOW's standing plan: line ¥150k + invoice financing ¥255k (¥3,113.93)",
     BLUE, "-", 3.0),
    ("ex01_as_asked_no_funding_cny", "Buyer's request accepted as asked, no new funding", AMBER, (0, (6, 2.5)), 3.0),
    ("demo_actual_option_a_late_residual_cure_cny",
     "Option A as the demo runs it: ¥160k paid late, month-2 payroll,\n¥200k cure approved by the owner "
     "(total cost ¥5,205.36)", PURPLE, (0, (2, 1.4)), 3.0),
]

fig, ax = chart(10.2, xlabel="day of the scenario (day 0 = 1 Oct 2026)", ylabel="closing cash (CNY)",
                rect=(0.145, 0.455, 0.825, 0.53))
ax.axhspan(-150, 300, color=AMBER_SOFT, zorder=0)
ax.step(days, RESERVE, where="post", color=INK, lw=2.0, ls=(0, (6, 3)), zorder=2)
ax.text(13.2, 288, "reserve ¥300k\n(signed mandate)", fontsize=13.5, color=INK, va="top")
ax.axhline(0, color=INK_2, lw=1.0, zorder=1)
for key, label, color, ls, lw in LINES:
    ax.step(days, col(key), where="post", color=color, ls=ls, lw=lw, label=label, zorder=3)

ax.set_xlim(0, 62)
ax.set_ylim(-150, 900)
ax.set_xticks(range(0, 61, 10))
ax.set_yticks(range(-100, 901, 100))
ax.set_yticklabels([("−" if v < 0 else "") + f"¥{abs(v)}k" for v in range(-100, 901, 100)])

# reconciled values, read from the series themselves
val = {key: dict(zip(days, col(key))) for key, *_ in LINES}
base, ex01, demo = val[LINES[0][0]], val[LINES[2][0]], val[LINES[3][0]]
ax.annotate(f"−¥{-base[30]:.0f}k, days 30–31", xy=(30.5, base[30]), xytext=(34, -110), fontsize=13.5, color=INK_2,
            va="center", arrowprops=dict(arrowstyle="-", color=INK_2, lw=1.2))
ax.annotate(f"day 47: ¥{ex01[47]:,.2f}k\n(¥90.04k short)", xy=(47.3, ex01[47]), xytext=(48.5, 95), fontsize=13.5,
            color=AMBER_INK, va="center", arrowprops=dict(arrowstyle="-", color=AMBER_INK, lw=1.2))
ax.annotate(f"day 42: ¥{demo[42]:.0f}k after the\npayroll; reserve held", xy=(42.5, demo[42]), xytext=(24, 600),
            fontsize=13.5, color=PURPLE, va="center", ha="center",
            arrowprops=dict(arrowstyle="-", color=PURPLE, lw=1.2))

# numbered, dated events (all from events.csv), explained in the key below the plot
MARKS = [(2, "1"), (12, "2"), (25, "3"), (30, "4"), (32, "5"), (34, "6"), (37, "7"), (47, "8"), (60, "9")]
for d, n in MARKS:
    ax.text(d, 795 if n == "5" else 860, n, ha="center", va="center", fontsize=13, fontweight="bold", color="white",
            zorder=6, bbox=dict(boxstyle="circle,pad=0.2", fc=INK, ec="none"))
    ax.axvline(d, color="#c9d0db", lw=0.9, zorder=1)
KEY = [
    ("1", "day 2: buyer pays early (as asked ¥414,960; Option A ¥257,790)"),
    ("2", "day 12: payroll −¥340,000"),
    ("3", "day 25: bookkeeper adds month-2 payroll of ¥200,000 for day 42"),
    ("4", "day 30: loan payment −¥45,000"),
    ("5", "day 32: ¥420,000 invoice due; demo: ¥160,000 of it not paid"),
    ("6", "day 34: FLOW proposes a ¥200,000 advance (¥1,782.19, 32.5% a year); owner approves"),
    ("7", "day 37: the advance lands (the late ¥160,000 arrived on day 36)"),
    ("8", "day 47: invoice +¥420,000, bill −¥100,000; advance and line repaid"),
    ("9", "day 60: loan payment −¥45,000"),
]
for i, (n, t) in enumerate(KEY):
    y = 0.252 - i * 0.0215
    fig.text(0.035, y, n, ha="center", va="center", fontsize=12, fontweight="bold", color="white",
             bbox=dict(boxstyle="circle,pad=0.18", fc=INK, ec="none"))
    fig.text(0.06, y, t, ha="left", va="center", fontsize=12.5, color=INK)
fig.legend(loc="upper left", bbox_to_anchor=(0.012, 0.392), frameon=False, fontsize=12.5, handlelength=2.6,
           labelspacing=0.3)
stamp(fig, "Golden books (synthetic), mandate v1, request EX01; amounts in CNY. Data: work/fin/daily_cash.csv\n"
           "(independent recomputation, equal to the engine to the fen) · " + BUILD)
save(fig, "fig11-cash-scenarios.png")
