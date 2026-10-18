"""Three compact evaluation panels, one file each, so no cross-panel comparison is implied:
fig-eval-buyer.png (buyer-message verdicts), fig-eval-contracts.png (contract fields), fig-eval-questions.png (owner
questions). They replace fig-eval-classes.png in the technical document. Render:

    uv run --no-project --with matplotlib --with pillow python fig_eval_panels.py

Every bar is a share of its own row's denominator, printed beside it; the words under each bar repeat the split, so the
segments never differ by colour alone. A row whose set was tuned on is hatched and tagged TUNED.
Sources (every value is printed here; nothing is fetched):
- buyer: services/api/evals/heldout3_report.md and heldout2_report.md (first runs, 1 Oct 2026, rules path: 33/63 with 4 of
  8 autonomous accepts wrong; 28/47 with 2 wrong, H2A06 and H2X03); docs/deliverables/submission/work/eval/
  offline_reruns_20261018.json (571ea64f, 18 Oct: 44/63 with 0 of 1 accept wrong, 38/47 with 0 of 2; reading-only agreement
  with today's policy 50/63 and 44/47); services/api/evals/heldout3_live_deepseek_report.md (1 Oct, live DeepSeek, 42/63,
  0 wrong accepts);
- contracts: work/evaluation.md section 5 (batch 2 first reading, recorded DeepSeek readings re-scored offline: 17
  text-layer contracts, 285 key items, 215 correct, 58 missing, 12 wrong; 13 of 30 contracts are scans or photos, refused
  before reading, so 215/474 = 45% over all 30; decision fields 178 correct, 45 missing, 11 wrong of 234, plus 18 stage
  items matching no key item; after the fixes 198/234 with 2 wrong; batch 1 412/424 with 0 wrong);
- questions: offline_reruns_20261018.json (owner-question bank, 427 turns the books can answer: 228 answered, 45 partly,
  154 declined, 0 wrong; everyday wording 326/345 right, 4 wrong, 15 miss; held-out part 127/142, 3 wrong, 12 miss);
  work/eval/live_router_outcomes.json (18 Oct live run: 63 questions reached the router, 33 answered, 29 "cannot answer
  yet", 1 rejected; the 33 graded by one unblinded reviewer: 22 right, 10 partial, 1 wrong topic).
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from flowstyle import (AMBER, AMBER_INK, BLUE, BLUE_SOFT, BUILD_FINAL, DPI, GREY, GREY_SOFT, INK, INK_2, WHITE, WIDTH_IN,
                       save, stamp)

# segment kinds: fill, edge, text colour on the fill, and the word used in the breakdown line
SEG = {
    "right": dict(fc=BLUE, ec=BLUE, word="right"),
    "partial": dict(fc=BLUE_SOFT, ec=BLUE, word="partly"),
    "miss": dict(fc=WHITE, ec=GREY, word="missing"),
    "wrong": dict(fc=AMBER, ec=AMBER_INK, word="wrong"),
    "refused": dict(fc=GREY_SOFT, ec=GREY, word="refused"),
}

L, R = 0.34, 0.70  # the bar column, in figure fractions; then the share (to 0.80) and the wrong column
ROW_IN, GROUP_IN = 0.95, 0.5


def panel(name: str, title: str, rows: list, right_head: str, foot: str, words: dict | None = None):
    words = words or {}
    h_rows = sum(GROUP_IN if r[0] == "group" else ROW_IN for r in rows)
    n_foot = foot.count(chr(10)) + 1
    H = 0.75 + h_rows + 0.3 + n_foot * 0.23 + 0.35
    fig = plt.figure(figsize=(WIDTH_IN, H), dpi=DPI)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, H)
    ax.axis("off")
    plt.rcParams["hatch.linewidth"] = 1.2
    fig.text(0.012, (H - 0.28) / H, title, fontsize=16, fontweight="bold", color=INK, va="center")
    fig.text(0.80, (H - 0.62) / H, "right", ha="right", fontsize=12.5, fontweight="bold", color=INK, va="center")
    fig.text(0.82, (H - 0.62) / H, right_head, fontsize=12.5, fontweight="bold", color=INK, va="center")
    y = H - 0.75
    for r in rows:
        if r[0] == "group":
            y -= GROUP_IN
            ax.text(0.012, y + 0.2, r[1], fontsize=14.5, fontweight="bold", color=INK, va="center")
            ax.plot([0.012, 0.988], [y + 0.04, y + 0.04], color=GREY, lw=1.0)
            continue
        _k, label, sub, segs, tuned, right = r
        y -= ROW_IN
        mid = y + ROW_IN / 2 + 0.1
        denom = sum(c for _s, c in segs)
        ax.text(0.012, mid + 0.13, label, fontsize=13.5, fontweight="bold", color=INK, va="center")
        ax.text(0.012, mid - 0.15, sub, fontsize=12.5, color=INK_2, va="center")
        if tuned:
            ax.text(L - 0.012, mid - 0.15, "TUNED", ha="right", va="center", fontsize=11, fontweight="bold", color=INK,
                    bbox=dict(boxstyle="round,pad=0.2", fc=WHITE, ec=INK, lw=1.0))
        x = L
        bh = 0.3
        for kind, c in segs:
            if c == 0:
                continue
            w = (R - L) * c / denom
            s = SEG[kind]
            hatched = tuned and kind == "right"  # a tuned set: the right share is drawn hatched, not solid
            ax.add_patch(plt.Rectangle((x, mid - bh / 2), w, bh, fc=WHITE if hatched else s["fc"], ec=s["ec"], lw=1.2,
                                       hatch="///" if hatched else None, zorder=3))
            x += w
        right_n = sum(c for s, c in segs if s == "right")
        ax.text(L, mid - bh / 2 - 0.04, f"{right_n}/{denom} right · "
                + " · ".join(f"{c} {words.get(s, SEG[s]['word'])}" for s, c in segs if s != "right"),
                fontsize=12, color=INK, va="top")
        ax.text(0.80, mid, f"{100 * right_n / denom:.0f}%", ha="right", va="center", fontsize=15, fontweight="bold",
                color=INK)
        ax.text(0.82, mid, right, fontsize=13.5, color=INK if right and not right.startswith(("0", "—")) else INK_2,
                va="center", fontweight="bold" if right and not right.startswith(("0", "—")) else "normal")
    ax.text(0.012, 0.3 + n_foot * 0.23 + 0.05, foot, fontsize=12.5, color=INK_2, va="top", linespacing=1.3)
    stamp(fig, "Values as measured on the builds and dates named above; drawn on " + BUILD_FINAL)
    save(fig, name)


# ---------------------------------------------------------------- buyer messages: verdicts
panel(
    "fig-eval-buyer.png", "Buyer messages: is FLOW's verdict the labelled one?",
    [
        ("group", "Unseen held-out sets, first run (rules path, 1 Oct 2026)"),
        ("row", "Held-out 3", "63 labelled messages", [("right", 33), ("miss", 30)], False, "4 of 8 accepts"),
        ("row", "Held-out 2", "47 labelled messages", [("right", 28), ("miss", 19)], False, "2 accepts"),
        ("group", "Same sets after tuning on their misses (571ea64f, 18 Oct)"),
        ("row", "Held-out 3", "1 Oct labels", [("right", 44), ("miss", 19)], True, "0 of 1 accept"),
        ("row", "Held-out 2", "1 Oct labels", [("right", 38), ("miss", 9)], True, "0 of 2 accepts"),
        ("group", "Against today's policy (reading only, 18 Oct)"),
        ("row", "Held-out 3", "today's rule, true terms", [("right", 50), ("miss", 13)], True, "—"),
        ("row", "Held-out 2", "today's rule, true terms", [("right", 44), ("miss", 3)], True, "—"),
        ("group", "Live model call (DeepSeek, 1 Oct 2026)"),
        ("row", "Held-out 3, live", "63 labelled messages", [("right", 42), ("miss", 21)], False, "0 accepts"),
    ],
    "wrong\naccepts",
    "Right = the verdict matches the label, written 1 Oct before the code saw the set.\n"
    "Wrong autonomous accepts = Tier-1 accepts whose label is not accept or that carry a\n"
    "material error: 6 in the first runs, 0 of 3 today. The today's-policy rows separate a\n"
    "misreading from a policy change (7 labels per set predate ADR-0007).\n"
    "Each bar is a share of its own row; do not compare it with the other panels.",
    words={"miss": "other verdict"},
)

# ---------------------------------------------------------------- contracts: fields
panel(
    "fig-eval-contracts.png", "Contracts: are the extracted fields right?",
    [
        ("group", "Batch 2, first reading (unseen; recorded DeepSeek readings)"),
        ("row", "All scored fields", "17 text-layer contracts", [("right", 215), ("miss", 58), ("wrong", 12)],
         False, "12 values"),
        ("row", "Over all 30 contracts", "13 scans refused (no OCR)", [("right", 215), ("miss", 58),
                                                                                ("wrong", 12), ("refused", 189)],
         False, "12 values"),
        ("row", "Decision-critical fields", "amounts, stages, parties", [("right", 178), ("miss", 45),
                                                                                   ("wrong", 11)],
         False, "11 + 18 stage"),
        ("group", "Decision-critical fields on sets the reading was tuned on"),
        ("row", "Batch 2, after 5 fixes", "234 key items", [("right", 198), ("miss", 34), ("wrong", 2)], True,
         "2 + 18 stage"),
        ("row", "Batch 1", "424 key items", [("right", 412), ("miss", 12), ("wrong", 0)], True, "0"),
    ],
    "stated\nwrongly",
    "Missing = no value read for a key item; wrong = a value stated that differs from the key;\n"
    "refused = the fields of the 13 scanned contracts, never read. Stage = payment-stage items\n"
    "matching no key item. A reading changes nothing until the owner confirms it.\n"
    "Each bar is a share of its own row; do not compare it with the other panels.",
)

# ---------------------------------------------------------------- owner questions
panel(
    "fig-eval-questions.png", "Owner questions: does FLOW answer them?",
    [
        ("group", "Offline, rules path (571ea64f, 18 Oct 2026)"),
        ("row", "Owner-question bank", "427 in-books turns", [("right", 228), ("partial", 45), ("miss", 154),
                                                                          ("wrong", 0)], True, "0"),
        ("row", "Everyday wording, all", "345 phrasings", [("right", 326), ("miss", 15), ("wrong", 4)], True,
         "4 topics"),
        ("row", "Everyday wording, held out", "142 phrasings of the 345", [("right", 127), ("miss", 12), ("wrong", 3)],
         False, "3 topics"),
        ("group", "Live question router (DeepSeek, 18 Oct 2026; one unblinded grader)"),
        ("row", "Questions that reached it", "63 of 589 sweep questions", [("right", 22), ("partial", 10), ("wrong", 1),
                                                                           ("miss", 29), ("refused", 1)], False, "1 topic"),
        ("row", "Questions it answered", "33 of the 63", [("right", 22), ("partial", 10), ("wrong", 1)], False, "1 topic"),
    ],
    "wrong",
    "Right = the answer's topic (offline) or content (live, hand-graded) is right. Declined =\n"
    "declined, \"cannot answer yet\" or no matching answer; rejected = by the router's\n"
    "checks. The bank is the development target, so it is tuned. The router's tools are read-only.\n"
    "Each bar is a share of its own row; do not compare it with the other panels.",
    words={"miss": "declined", "refused": "rejected"},
)
