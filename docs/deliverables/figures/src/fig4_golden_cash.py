"""Figure 4: the golden books' cash forecast, days 0 to 60.

Render: uv run --no-project --with matplotlib --with pillow python fig4_golden_cash.py
Refresh the numbers from the API (in-process, no server, no LLM, no database), from services/api:
    TERMSLEDGER_NO_DOTENV=1 LLM_MODE=cache DATABASE_URL=memory DEMO_MODE=1 \
        uv run python ../../docs/deliverables/figures/src/fig4_golden_cash.py --fetch
which prints the two series and the events below; paste them over the constants.

Source: GET /home on the golden books after `Runtime.reset()` (InMemoryLedgerStore, demo owner key), dev 975e082f,
17 Oct 2026. `cash.series` is the conservative projection of the current books (no new funding); `cash.plan_series` is the
same books with FLOW's recommended plan (Bank credit line draw ¥150,000 on day 0, invoice financing advance ¥255,000 on
day 3). Floor `cash.floor_fen` = ¥300,000; `first_breach_day` = 12 (¥60,000); `lowest_day` = 30 (−¥105,000). Values are
closing cash in yuan, day 0 to 60.
"""

import sys

# --- source values (GET /home, cash.series and cash.plan_series, closing_fen / 100) -----------------------------------
NO_FUNDING = [400000, 400000, 400000, 400000, 400000, 400000, 400000, 400000, 400000, 400000, 400000, 400000, 60000,
              60000, 60000, 60000, 60000, 60000, 60000, 60000, -60000, -60000, -60000, -60000, -60000, -60000, -60000,
              -60000, -60000, -60000, -105000, -105000, 315000, 315000, 315000, 315000, 315000, 315000, 315000, 315000,
              315000, 315000, 315000, 315000, 315000, 315000, 315000, 635000, 635000, 635000, 635000, 635000, 635000,
              635000, 635000, 635000, 635000, 635000, 635000, 635000, 590000]
WITH_PLAN = [550000, 550000, 550000, 805000, 805000, 805000, 805000, 805000, 805000, 805000, 805000, 805000, 465000,
             465000, 465000, 465000, 465000, 465000, 465000, 465000, 345000, 345000, 345000, 345000, 345000, 345000,
             345000, 345000, 345000, 345000, 300000, 300000, 311886, 311886, 311886, 311886, 311886, 311886, 311886,
             311886, 311886, 311886, 311886, 311886, 311886, 311886, 311886, 631886, 631886, 631886, 631886, 631886,
             631886, 631886, 631886, 631886, 631886, 631886, 631886, 631886, 586886]
FLOOR = 300000
# events (day, kind, label, yuan) as the API names them:
#  0 DRAW     Draw Bank credit line                                   +150,000 (plan)
#  3 ADVANCE  Advance on the ¥420,000 invoice to Foshan Home Retail Co. due in 32 days, invoice financing  +255,000 (plan)
# 12 FLOW     Payroll                                                 -340,000
# 20 FLOW     Supplier payment                                        -120,000
# 30 FLOW     Debt service (principal), existing equipment loan        -45,000
# 32 RECEIPT  the ¥420,000 invoice to Foshan Home Retail Co. (Receivable A)  +420,000; with the plan the same day also
#             repays the line (-150,000, interest -842) and the advance (-255,000, interest -1,635, fee -638)
# 47 RECEIPT  the second ¥420,000 Foshan invoice +420,000; FLOW Operating bill -100,000
# 60 FLOW     Debt service (principal), existing equipment loan        -45,000


def fetch() -> None:
    import os

    os.environ.update(TERMSLEDGER_NO_DOTENV="1", LLM_MODE="cache", DATABASE_URL="memory", DEMO_MODE="1")
    from fastapi.testclient import TestClient

    from app.api.runtime import Runtime, set_runtime
    from app.config import get_settings
    from app.main import app
    from app.mandate.fixture import demo_owner_public_key_hex
    from app.persistence import InMemoryLedgerStore

    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    cash = TestClient(app).get("/home", headers={"X-Owner-Token": "demo-owner-token"}).json()["cash"]
    for name, key in (("NO_FUNDING", "series"), ("WITH_PLAN", "plan_series")):
        rows = {r["day"]: r for r in cash[key]}
        print(name, "=", [rows[d]["closing_fen"] // 100 for d in range(61)])
        for d in range(61):
            for e in rows[d]["events"]:
                print(f"  {d:>2} {e['kind']:<9} {e['amount_fen'] // 100:>9}  {e['label']}")
    print("FLOOR =", cash["floor_fen"] // 100, "first_breach_day", cash["first_breach_day"], "lowest", cash["lowest_day"],
          cash["lowest_fen"] // 100)


if "--fetch" in sys.argv:
    fetch()
    raise SystemExit

from flowstyle import AMBER, AMBER_INK, AMBER_SOFT, BLUE, BLUE_DEEP, INK, INK_2, WIDTH_IN, DPI, save  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

days = list(range(61))
k = lambda v: v / 1000  # noqa: E731

fig = plt.figure(figsize=(WIDTH_IN, 6.4), dpi=DPI)
ax = fig.add_axes((0.115, 0.32, 0.865, 0.65))
ax.axhspan(-150, FLOOR / 1000, color=AMBER_SOFT, zorder=0)
ax.axhline(k(FLOOR), color=INK, lw=2.0, ls=(0, (6, 3)), zorder=2)
ax.axhline(0, color=INK_2, lw=1.0, zorder=1)
ax.step(days, [k(v) for v in NO_FUNDING], where="post", color=AMBER, lw=3.2, zorder=3, label="no new funding")
ax.step(days, [k(v) for v in WITH_PLAN], where="post", color=BLUE, lw=3.2, zorder=4,
        label="with FLOW's plan: credit line ¥150k\n(day 0) + invoice financing ¥255k\n(day 3), both repaid on day 32")
ax.set_xlim(0, 60)
ax.set_ylim(-150, 900)
ax.set_xticks(range(0, 61, 10))
ax.set_yticks(range(-100, 901, 100))
ax.set_yticklabels([("−" if v < 0 else "") + f"¥{abs(v)}k" for v in range(-100, 901, 100)])
ax.set_xlabel("day")
ax.grid(axis="y", color="#e6e9ef", lw=1.0, zorder=0)
ax.text(12.8, k(FLOOR) - 15, "minimum cash ¥300k\n(signed mandate)", ha="left", va="top", fontsize=14, color=INK)
ax.annotate("below the minimum\nfrom day 12; lowest\n−¥105k on days 30–31", xy=(31.2, -100), xytext=(37, 130),
            fontsize=14, color=AMBER_INK, va="center", arrowprops=dict(arrowstyle="-", color=AMBER_INK, lw=1.4))
ax.legend(loc="upper left", bbox_to_anchor=(0.215, 0.99), frameon=False, fontsize=14, handlelength=1.6, labelspacing=0.6)

# numbered events on the books (both lines), explained in the key below the chart
MARK = [(12, 60, "1", (1.4, -55)), (20, -60, "2", (1.4, -55)), (30, -105, "3", (5.0, 0)),
        (32, 315, "4", (1.6, 90)), (47, 635, "5", (2.0, 70)), (60, 590, "6", (-1.8, -60))]
for d, v, n, (dx, dy) in MARK:
    ax.text(d + dx, v + dy, n, ha="center", va="center", fontsize=14, fontweight="bold", color="white", zorder=6,
            bbox=dict(boxstyle="circle,pad=0.22", fc=AMBER_INK, ec="none"))

KEY = [("1", "day 12: payroll −¥340k"), ("2", "day 20: supplier payment −¥120k"), ("3", "day 30: loan payment −¥45k"),
       ("4", "day 32: Receivable A +¥420k"), ("5", "day 47: receipt +¥420k, bill −¥100k"),
       ("6", "day 60: loan payment −¥45k")]
for i, (n, t) in enumerate(KEY):
    c = AMBER_INK
    col, row = divmod(i, 3)
    x, y = 0.02 + col * 0.47, 0.19 - row * 0.065
    fig.text(x + 0.012, y, n, ha="center", va="center", fontsize=13.5, fontweight="bold", color="white",
             bbox=dict(boxstyle="circle,pad=0.2", fc=c, ec="none"))
    fig.text(x + 0.035, y, t, ha="left", va="center", fontsize=13.5, color=INK)

save(fig, "fig4-golden-cash.png")
