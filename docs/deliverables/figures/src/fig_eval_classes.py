"""Figure: FLOW's accuracy results grouped by evidence class, so an unseen figure is never read beside a tuned one.

Render: uv run --no-project --with matplotlib --with pillow python fig_eval_classes.py
Writes docs/deliverables/figures/fig-eval-classes.png.

Each bar is the share an item's own oracle scores right; the right-hand column is what that oracle scores wrong. The four
panels are the evidence classes of docs/deliverables/submission/work/evaluation.md (section 2):
- unseen held-out, first run: labels written before the code that is scored had seen them, scored once (rules path);
- after tuning on failures: the same sets re-scored after fixes were chosen by studying their misses (rules path);
- recorded model replay: DeepSeek readings recorded once and replayed from the cache, no network;
- live provider calls: DeepSeek `deepseek-flash` called live.
Sources (every value is printed here; nothing is fetched):
- held-out 3 first run: services/api/evals/heldout3_report.md (1 Oct 2026, rules, 33/63; 4 of 8 autonomous accepts wrong);
- held-out 2 first run: services/api/evals/heldout2_report.md (1 Oct 2026, dev e34af1a, rules, 28/47; 2 wrong autonomous
  accepts, H2A06 and H2X03);
- held-out 3 and 2 today, and held-out 3 against today's policy: scripts/evaluate.py --suite offers --heldout ... on
  docs/sub-evaluation @ 571ea64f, 18 Oct 2026 (44/63, 38/47; compiler outcome equal to the form-baseline outcome 50/63);
- everyday owner wording: services/api/scripts/owner_questions_general.py --part all on 571ea64f, 18 Oct 2026 (held-out
  127/142, 3 wrong topic; tuning part 199/203, 1 wrong); owner-question bank: owner_questions_baseline.py on 571ea64f
  (in-books turns 228/427 answered, 45 partly, 0 wrong; the 76 not-in-books turns are left out of this bar);
- contracts: recorded DeepSeek readings re-scored with services/api/scripts/eval_contracts.py `score` (session scratchpad
  b2fix/, 16-17 Oct 2026; not in the repo): batch 2 first reading 215/285 fields (12 scalar values stated wrongly, 18 stage
  items matching no key item), batch 2 after fixes 246/285 (3 + 18), batch 1 502/514 (0); text-layer contracts only;
- held-out 3 live: services/api/evals/heldout3_live_deepseek_report.md (1 Oct 2026, 389cfd9, 42/63, 0 wrong accepts);
- Ask router live: the 18 Oct 2026 live stress test (int/live-test 28738f19), docs/deliverables/submission/work/eval/
  live_router_outcomes.json: 33 router answers graded by one unblinded reviewer, 22 right, 10 partial, 1 wrong topic.
"""

import matplotlib.pyplot as plt
from matplotlib.transforms import blended_transform_factory

from flowstyle import AMBER, AMBER_INK, BLUE, DPI, GREY, INK, INK_2, PURPLE, WIDTH_IN, save

UNSEEN, TUNED, REPLAY, LIVE = BLUE, PURPLE, GREY, AMBER
# (panel title, colour, rows); row = (label, tag, right, of, wrong text, hatched?)
PANELS = [
    ("Unseen held-out, first run", UNSEEN, [
        ("Buyer messages, held-out 3", "rules · 1 Oct · verdicts", 33, 63, "4 of 8 accepts", False),
        ("Buyer messages, held-out 2", "rules · 1 Oct · verdicts", 28, 47, "2 accepts", False),
        ("Owner wording, held-out part", "rules · 18 Oct · topics", 127, 142, "3 topics", False),
    ]),
    ("After tuning on failures", TUNED, [
        ("Buyer messages, held-out 3", "rules · 18 Oct · verdicts", 44, 63, "0 of 1 accept", False),
        ("  same, vs today's policy", "rules · reading only", 50, 63, "", False),
        ("Buyer messages, held-out 2", "rules · 18 Oct · verdicts", 38, 47, "0 of 2 accepts", False),
        ("Owner wording, tuning part", "rules · 18 Oct · topics", 199, 203, "1 topic", False),
        ("Owner-question bank, in books", "rules · 18 Oct · answered", 228, 427, "0", False),
    ]),
    ("Recorded model replay (DeepSeek)", REPLAY, [
        ("Contracts, batch 2, 1st read", "unseen · fields", 215, 285, "12 + 18 stage", False),
        ("Contracts, batch 2, after fixes", "tuned on it · fields", 246, 285, "3 + 18 stage", True),
        ("Contracts, batch 1", "tuned on it · fields", 502, 514, "0", True),
    ]),
    ("Live provider calls (DeepSeek)", LIVE, [
        ("Buyer messages, held-out 3", "1 Oct · verdicts", 42, 63, "0 accepts", False),
        ("Ask router answers", "18 Oct · hand-graded", 22, 33, "1 (10 partial)", False),
    ]),
]

rows = []  # (y, kind, payload)
y = 0.0
for title, colour, items in PANELS:
    rows.append((y, "head", (title, colour)))
    y -= 0.9
    for it in items:
        rows.append((y, "row", (colour, *it)))
        y -= 1.0
    y -= 0.35
y_min = y + 0.35

fig = plt.figure(figsize=(WIDTH_IN, 10.8), dpi=DPI)
L, R, B, T = 0.47, 0.775, 0.11, 0.935
ax = fig.add_axes((L, B, R - L, T - B))
ax.set_ylim(y_min - 0.2, 0.6)
ax.set_xlim(0, 100)
ax.set_yticks([])
ax.spines["left"].set_visible(False)
ax.set_xticks([0, 25, 50, 75, 100])
ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"], fontsize=13.5)
ax.grid(axis="x", color="#e6e9ef", lw=1.0)
ax.set_axisbelow(True)
lab = blended_transform_factory(fig.transFigure, ax.transData)
plt.rcParams["hatch.color"] = INK_2

for yy, kind, p in rows:
    if kind == "head":
        title, colour = p
        fig.text(0.012, yy, title, transform=lab, ha="left", va="center", fontsize=15, fontweight="bold",
                 color=AMBER_INK if colour == AMBER else colour if colour != GREY else INK)
        ax.axhline(yy - 0.42, color=colour, lw=1.4, alpha=0.6)
        continue
    colour, name, tag, k, n, wrong, hatched = p
    pct = 100 * k / n
    style = dict(color="white", edgecolor=colour, hatch="///", linewidth=1.5) if hatched else dict(color=colour)
    ax.barh(yy, pct, height=0.62, **style)
    inside = pct >= 80
    ax.text(pct - 1.2 if inside else pct + 1.2, yy, f"{pct:.0f}%", va="center", ha="right" if inside else "left",
            fontsize=13.5, color=INK if (hatched or not inside) else "white", fontweight="bold",
            bbox=dict(fc="white", ec="none", pad=0.6) if hatched else None)
    fig.text(0.012, yy + 0.2, name, transform=lab, ha="left", va="center", fontsize=13.5, fontweight="bold", color=INK)
    fig.text(0.012, yy - 0.24, f"{tag} · {k}/{n}", transform=lab, ha="left", va="center", fontsize=13.5, color=INK_2)
    fig.text(R + 0.02, yy, wrong or "–", transform=lab, ha="left", va="center", fontsize=13.5,
             color=INK if wrong and not wrong.startswith("0") else INK_2)

fig.text(R + 0.02, T + 0.012, "Wrong", ha="left", va="bottom", fontsize=14, fontweight="bold", color=INK)
fig.text(L, T + 0.012, "Right, by its own oracle", ha="left", va="bottom", fontsize=14, fontweight="bold",
         color=INK)
fig.text(0.012, 0.04, "Hatched: the reading was tuned on that set. Each bar is a share of its own\n"
         "row's denominator; rows with different oracles do not compare. Accepts =\n"
         "wrong autonomous Tier-1 accepts; stage = stage items matching no key item.", ha="left", va="center",
         fontsize=13.5, color=INK_2, linespacing=1.25)

save(fig, "fig-eval-classes.png")
