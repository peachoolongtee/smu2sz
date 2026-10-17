"""Figure 1: FLOW in one picture. Render: uv run --no-project --with matplotlib --with pillow python fig1_architecture.py

Checked against dev (975e082f):
- compiler (services/api/app/compiler): the only model-backed step; `redaction.py` redacts before any provider call,
  `grounding.py` keeps only verbatim quotes, `coverage.py` gives the coverage proof (`autonomy_eligible`, ADR-0005);
- verifier (app/verifier/evaluate.py): mandate, covenants (app/covenants), break-even, autonomy rule; reads no free text;
- trajectory engine (app/financial/trajectory.py) and funding router (app/funding/router.py) feed the verifier;
- executor (app/operations/executor.py): tiers (app/mandate/tiers.py), idempotency, re-verification; every outcome is
  appended to the hash-chained operations log;
- mandate: Ed25519-signed, pinned to the owner key (executor `trusted_owner_key_hex`); funding menu (app/funding/menu.py);
  bank feed: simulated, posts RECEIVE_PAYMENT as SYSTEM (app/api/auth.py BANK_FEED_KEY, app/api/demo_bank.py);
- surfaces: apps/web (owner) and POST /nl (app/nl), for the owner, buyers and the agent key.
"""

from matplotlib.patches import Rectangle

from flowstyle import (AMBER, AMBER_INK, AMBER_SOFT, BLUE, BLUE_SOFT, GREY, GREY_SOFT, INK, PURPLE, PURPLE_INK,
                       PURPLE_SOFT, WHITE, arrow, box, canvas, save, zone)

H = 7.2
fig, ax = canvas(H)
SMALL = dict(title_pt=15, body_pt=13.5)

# trust boundaries (dashed)
ZY0, ZY1 = 1.15, 5.85
zone(ax, 0.05, ZY0, 2.3, ZY1 - ZY0, "Untrusted text", AMBER_INK)
zone(ax, 2.5, ZY0, 3.05, ZY1 - ZY0, "Deterministic core", BLUE)
zone(ax, 5.7, ZY0, 2.25, ZY1 - ZY0, "Write path", INK)

# surfaces and owner inputs (top row)
TY0, TY1 = 6.3, 7.12
box(ax, 0.05, TY0, 2.3, TY1 - TY0, "Chat (/nl)", "buyers and owner", fill=GREY_SOFT, edge=GREY)
box(ax, 2.5, TY0, 3.05, TY1 - TY0, "Owner-signed mandate", "Ed25519 · limits · 3 tiers", fill=PURPLE_SOFT, edge=PURPLE,
    ink=PURPLE_INK)
box(ax, 5.7, TY0, 2.25, TY1 - TY0, "Web app (owner)", "reviews, approves", fill=GREY_SOFT, edge=GREY)

# main pipeline
box(ax, 0.2, 4.7, 2.0, 0.9, "Buyer message\nor document", None, fill=AMBER_SOFT, edge=AMBER, ink=AMBER_INK)
box(ax, 0.2, 1.35, 2.0, 2.95, "Compiler", "the only model step\nLLM or rules\nredaction first\nverbatim quotes\ncoverage proof",
    fill=WHITE, edge=AMBER, ink=INK)
box(ax, 2.65, 3.85, 2.75, 1.75, "Verifier",
    "no free text read\nmandate · covenants\nbreak-even · autonomy\nverdict, counters out", fill=BLUE_SOFT, edge=BLUE)
box(ax, 2.62, 1.35, 1.27, 1.6, "Trajectory\nengine", "daily cash", fill=BLUE_SOFT, edge=BLUE, title_pt=14.5, body_pt=13.5)
box(ax, 4.18, 1.35, 1.22, 1.6, "Funding\nrouter", "cheapest\nmix", fill=BLUE_SOFT, edge=BLUE, **SMALL)
box(ax, 5.85, 3.85, 1.95, 1.75, "Executor", "tiers 1 / 2 / 3\nidempotency\nre-verification", fill=WHITE, edge=INK)
box(ax, 5.85, 1.35, 1.95, 1.6, "Hash-chained\nlog", "every outcome,\nrefusals too", fill=GREY_SOFT, edge=INK)

# side inputs (bottom row)
BY0, BY1 = 0.08, 0.82
box(ax, 2.5, BY0, 1.5, BY1 - BY0, "Bank feed", "simulated", fill=GREY_SOFT, edge=GREY, **SMALL)
box(ax, 4.05, BY0, 1.6, BY1 - BY0, "Funding menu", "owner-approved", fill=PURPLE_SOFT, edge=PURPLE, ink=PURPLE_INK,
    title_pt=14, body_pt=13.5)

# flows
arrow(ax, [(1.95, TY0), (1.95, 5.6)])  # chat -> message
arrow(ax, [(1.2, 4.7), (1.2, 4.3)])  # message -> compiler
arrow(ax, [(2.2, 4.08), (2.65, 4.08)], color=BLUE)  # compiler -> verifier (typed obligations)
arrow(ax, [(5.4, 4.72), (5.85, 4.72)], color=INK)  # verifier -> executor (verdict, counters)
arrow(ax, [(6.82, 3.85), (6.82, 2.95)], color=INK)  # executor -> log
arrow(ax, [(3.26, 2.95), (3.26, 3.85)], color=BLUE)  # trajectory -> verifier
arrow(ax, [(4.79, 2.95), (4.79, 3.85)], color=BLUE)  # router -> verifier
arrow(ax, [(3.87, 2.15), (4.18, 2.15)], color=BLUE)  # trajectory -> router
arrow(ax, [(3.25, BY1), (3.25, 1.35)], color=GREY)  # bank feed -> trajectory (the books)
arrow(ax, [(4.8, BY1), (4.8, 1.35)], color=PURPLE)  # menu -> router
arrow(ax, [(4.85, TY0), (4.85, 5.6)], color=PURPLE)  # mandate -> verifier
arrow(ax, [(5.35, TY0), (5.35, 6.08), (7.05, 6.08), (7.05, 5.6)], color=PURPLE)  # mandate -> executor (signature, expiry)
arrow(ax, [(7.6, TY0), (7.6, 5.6)], color=PURPLE)  # web app -> executor (owner approvals)

# legend
for i, (c, t) in enumerate([(AMBER, "untrusted input"), (PURPLE, "owner authority")]):
    y = 0.62 - i * 0.36
    ax.add_patch(Rectangle((0.1, y - 0.1), 0.3, 0.2, fc=WHITE, ec=c, lw=2.4))
    ax.text(0.5, y, t, fontsize=13.5, color=INK, va="center")
for i, (c, t, dashed) in enumerate([(INK, "trust boundary", True), (BLUE, "deterministic code", False)]):
    y = 0.62 - i * 0.36
    if dashed:
        ax.plot([5.75, 6.15], [y, y], color=c, lw=2.2, ls=(0, (6, 3)))
    else:
        ax.add_patch(Rectangle((5.8, y - 0.1), 0.3, 0.2, fc=BLUE_SOFT, ec=c, lw=2.4))
    ax.text(6.25, y, t, fontsize=13.5, color=INK, va="center")

save(fig, "fig1-architecture.png")
