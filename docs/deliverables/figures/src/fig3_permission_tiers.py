"""Figure 3: who may do what. Render: uv run --no-project --with matplotlib --with pillow python fig3_permission_tiers.py

Facts from dev (975e082f), services/api:
- app/mandate/tiers.py `tier_for`: Tier 3 always for SignPersonalGuarantee, PledgeCollateral, IssueEquity, ChangeMandate, an
  AddFacility not requested by the owner, and any operation type it does not know (fail closed). Tier 2 always for
  ApplyForFacility and CommitPurchase (ADR-0013), an owner's AddFacility, a draw or invoice submission on a facility that is
  not owner-approved and COMMITTED, a receipt not from the bank feed (SYSTEM) or the owner, a new commitment above
  `tier2_single_commitment_fen`, and an AcceptOffer/RecordCommitment that lengthens terms or is anything but an early payment
  on a named invoice. Everything else in _TIER1_BASE is Tier 1.
- app/operations/executor.py `_run`, in order: 1 idempotency (`_duplicate`), 1b dating (op.day == clock day), 2 mandate
  (`_check_mandate`: signature pinned to the owner key, expiry, revocation, version), 3 Tier 3 refused, the counterparty
  circuit breaker (3 refusals in 7 days), the acceptance screen for AcceptOffer/RecordCommitment (`_screen_commitment`:
  nonce, expiry, terms hash, mandate version, the backing verdict), the Tier-2 queue (PENDING), 4 preconditions and effects
  (`_handle`: the admission check for funding operations, `_admitted`, and re-verification on today's books when the books
  moved since the verdict, `reverify`). Every outcome, refusals included, is appended to the hash-chained log.
  An owner-approved Tier-2 operation runs again through every gate except the queue (`decide`).
"""

from matplotlib.patches import FancyBboxPatch

from flowstyle import (AMBER, AMBER_INK, AMBER_SOFT, BLUE, BLUE_DEEP, BLUE_SOFT, GREY_SOFT, INK, INK_2, PURPLE,
                       PURPLE_INK, PURPLE_SOFT, arrow, canvas, save)

H = 9.0
fig, ax = canvas(H)
LH = 13.5 * 1.3 / 72

TIERS = [
    ("Tier 1", "on its own, inside\nthe signed mandate", BLUE, BLUE_SOFT, BLUE_DEEP, [
        "accept early payment\nof a named invoice\nat a discount",
        "counter or reject\nan offer",
        "draw or advance on\na committed facility",
        "repay a facility",
        "book a bank-feed\nreceipt",
    ]),
    ("Tier 2", "queued for the\nowner's approval", PURPLE, PURPLE_SOFT, PURPLE_INK, [
        "apply for a facility",
        "buy equipment",
        "accept longer terms\nor any concession",
        "commit above the\nsingle-commitment\nlimit",
        "draw on a facility\nnot yet committed",
        "a receipt reported\nby agent or buyer",
    ]),
    ("Tier 3", "always refused,\nwhoever asks", AMBER, AMBER_SOFT, AMBER_INK, [
        "sign a personal\nguarantee",
        "pledge collateral",
        "issue equity",
        "change the mandate",
        "add a facility,\nunless the owner asks",
        "any unknown\noperation\n(fails closed)",
    ]),
]

CW, CG, TOP, BOT = 2.5, 0.2, H - 0.08, 4.36
for i, (name, sub, edge, fill, ink, items) in enumerate(TIERS):
    x = 0.05 + i * (CW + CG)
    ax.add_patch(FancyBboxPatch((x, BOT), CW, TOP - BOT, boxstyle="round,pad=0,rounding_size=0.08", fc="white", ec=edge,
                                lw=2.2, zorder=1))
    ax.add_patch(FancyBboxPatch((x, TOP - 1.05), CW, 1.05, boxstyle="round,pad=0,rounding_size=0.08", fc=fill, ec=edge,
                                lw=2.2, zorder=2))
    ax.text(x + 0.15, TOP - 0.1, name, va="top", fontsize=18, fontweight="bold", color=ink, zorder=3)
    ax.text(x + 0.15, TOP - 0.47, sub, va="top", fontsize=14, color=ink, zorder=3, linespacing=1.15)
    y = TOP - 1.22
    for it in items:
        ax.text(x + 0.13, y, "•", va="top", fontsize=14, color=edge, fontweight="bold")
        ax.text(x + 0.33, y, it, va="top", fontsize=13.5, color=INK, linespacing=1.3)
        y -= LH * (it.count("\n") + 1) + 0.1

# the executor's gates: two columns of four, read down
ax.text(0.05, 4.1, "The executor's gates, in order", va="center", fontsize=16, fontweight="bold", color=INK)
ax.text(0.05, 3.8, "A refusal at any gate is logged and nothing moves.", va="center", fontsize=14, color=INK_2)
GATES = [
    ("1", "Idempotency", "same key, same answer"),
    ("2", "Dating", "day = the executor's day"),
    ("3", "Mandate", "signature, expiry, version"),
    ("4", "Tier 3", "refused for every caller"),
    ("5", "Circuit breaker", "3 refusals in 7 days"),
    ("6", "Acceptance screen", "nonce, expiry, terms hash"),
    ("7", "Tier 2", "queued for the owner"),
    ("8", "Admission, re-verification", "on today's books, then effects"),
]
GW, GH, GG = 3.75, 0.68, 0.17
XS = [0.05, 0.05 + GW + 0.4]
Y0 = 3.52  # top of the first row
for k, (n, t, s) in enumerate(GATES):
    c, r = divmod(k, 4)
    x, y = XS[c], Y0 - GH - r * (GH + GG)
    edge, fill = (AMBER, AMBER_SOFT) if t == "Tier 3" else (PURPLE, PURPLE_SOFT) if t == "Tier 2" else (INK, GREY_SOFT)
    ax.add_patch(FancyBboxPatch((x, y), GW, GH, boxstyle="round,pad=0,rounding_size=0.07", fc=fill, ec=edge, lw=2.0,
                                zorder=3))
    ax.text(x + 0.14, y + GH / 2, n, va="center", fontsize=17, fontweight="bold", color=edge, zorder=4)
    ax.text(x + 0.48, y + GH - 0.08, t, va="top", fontsize=14, fontweight="bold", color=INK, zorder=4)
    ax.text(x + 0.48, y + 0.07, s, va="bottom", fontsize=13.5, color=INK_2, zorder=4)
    if r < 3:
        arrow(ax, [(x + GW / 2, y), (x + GW / 2, y - GG)], lw=2.0)
# gate 4 (bottom of the left column) to gate 5 (top of the right column), up the gap between the columns
y4 = Y0 - GH - 3 * (GH + GG)
gx = XS[0] + GW + 0.2
arrow(ax, [(XS[0] + GW, y4 + GH / 2), (gx, y4 + GH / 2), (gx, Y0 - GH / 2), (XS[1], Y0 - GH / 2)], lw=2.0)

save(fig, "fig3-permission-tiers.png")
