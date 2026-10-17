"""Figure 5: the compiler's held-out results, honestly labelled.

Render: uv run --no-project --with matplotlib --with pillow python fig5_heldout_results.py
Sources, one row each (the same rows as the technical document's Table 8):
- First run and live DeepSeek: services/api/evals/accuracy_summary.md (1 Oct 2026, commit 389cfd9).
- Today (rules) and form baseline: docs/deliverables/evidence/EVIDENCE_PACK.md section 1 (dev 975e082f, 17 Oct 2026).

| Set | Independence | Path | Verdict agreement | Material error rate | Wrong autonomous accepts |
| Held-out 3, first run (1 Oct, before ADR-0005) | independent, unseen | rules | 33/63 (52%) | 4/51 (7.8%) | 4 of 8 |
| Held-out 3, today (17 Oct) | its failure classes guided later fixes | rules | 44/63 (70%) | 3/51 (5.9%) | 0 |
| Held-out 3, after round 3 (1 Oct) | the prompt was not tuned on it | live DeepSeek (deepseek-flash) | 42/63 (67%) | 3/51 (5.9%) | 0 |
| Held-out 2, today (17 Oct) | its classes guided round 2 | rules | 38/47 (81%) | 0/37 | 0 |
| Form baseline, today (labels typed in) | - | no compiler | 56/63 (89%) | - | - |

Only the first held-out-3 row is an untuned figure. The form baseline is below 100% because the 1 Oct labels predate the
early-payment rule (ADR-0007), which now counters some offers the labels accept.
"""

import matplotlib.pyplot as plt
from matplotlib.transforms import blended_transform_factory

from flowstyle import BLUE, DPI, GREY, INK, INK_2, PURPLE, WIDTH_IN, save

ROWS = [  # label, tag, colour, agreement (n, d), material errors (n, d) or None, wrong accepts text, wrong accepts value
    ("Held-out 3, first run (1 Oct)", "rules · unseen", BLUE, (33, 63), (4, 51), "4 of 8", 4),
    ("Held-out 3, today (17 Oct)", "rules · tuned on its misses", PURPLE, (44, 63), (3, 51), "0", 0),
    ("Held-out 3, round 3 (1 Oct)", "live DeepSeek · prompt untuned", PURPLE, (42, 63), (3, 51), "0", 0),
    ("Held-out 2, today (17 Oct)", "rules · tuned on its misses", PURPLE, (38, 47), (0, 37), "0", 0),
    ("Form baseline, today", "labels typed in, no compiler", GREY, (56, 63), None, "n/a", None),
]

fig = plt.figure(figsize=(WIDTH_IN, 6.2), dpi=DPI)
L, R, B, T = 0.4, 0.985, 0.2, 0.86
gap = 0.03
pw = (R - L - 2 * gap) / 3
axes = [fig.add_axes((L + i * (pw + gap), B, pw, T - B)) for i in range(3)]
ys = list(range(len(ROWS)))[::-1]
lab = blended_transform_factory(fig.transFigure, axes[0].transData)

for ax, title in zip(axes, ["Verdict\nagreement", "Material\nerrors", "Wrong\nauto-accepts"]):
    ax.set_title(title, fontsize=14.5, fontweight="bold", color=INK, loc="left", pad=10, linespacing=1.1)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_ylim(-0.6, len(ROWS) - 0.4)
    ax.tick_params(axis="x", labelsize=13.5)

for y, (name, tag, c, agr, err, wtxt, wval) in zip(ys, ROWS):
    pa = 100 * agr[0] / agr[1]
    axes[0].barh(y, pa, color=c, height=0.6)
    axes[0].text(pa + 3, y, f"{pa:.0f}%", va="center", fontsize=14, color=INK)
    if err is None:
        axes[1].text(0.3, y, "n/a", va="center", fontsize=14, color=INK_2)
    else:
        pe = 100 * err[0] / err[1]
        axes[1].barh(y, pe, color=c, height=0.6)
        axes[1].text(pe + 0.4, y, f"{pe:.1f}%" if pe else "0%", va="center", fontsize=14, color=INK)
    if wval is None:
        axes[2].text(0.2, y, wtxt, va="center", fontsize=14, color=INK_2)
    else:
        axes[2].barh(y, wval, color=c, height=0.6)
        axes[2].text(wval + 0.25, y, wtxt, va="center", fontsize=14, color=INK, fontweight="bold" if wval else None)
    fig.text(0.012, y + 0.17, name, transform=lab, ha="left", va="center", fontsize=14, fontweight="bold", color=INK)
    fig.text(0.012, y - 0.2, tag, transform=lab, ha="left", va="center", fontsize=13.5, color=c if c != GREY else INK_2)

axes[0].set_xlim(0, 130)
axes[0].set_xticks([0, 50, 100])
axes[0].set_xticklabels(["0", "50%", "100%"])
axes[1].set_xlim(0, 12)
axes[1].set_xticks([0, 5, 10])
axes[1].set_xticklabels(["0", "5%", "10%"])
axes[2].set_xlim(0, 7.5)
axes[2].set_xticks([0, 2, 4])

# legend: what the colours mean
LEG = [(BLUE, "unseen: the only untuned figure"), (PURPLE, "tuned on: its misses guided a fix round"),
       (GREY, "baseline: no compiler")]
for i, (c, t) in enumerate(LEG):
    y = 0.095 - i * 0.042 if i < 2 else 0.095
    x = 0.012 if i < 2 else 0.6
    fig.patches.append(plt.Rectangle((x, y - 0.013), 0.02, 0.026, transform=fig.transFigure, fc=c, ec="none"))
    fig.text(x + 0.03, y, t, va="center", fontsize=13.5, color=INK)

save(fig, "fig5-heldout-results.png")
