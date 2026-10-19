"""Figure 10: the authority matrix. Render: uv run --no-project --with matplotlib --with pillow python fig10_authority_matrix.py

Replaces fig3's upper half for the submission (fig3 keeps the executor's gate order). Every cell is an operation type of
app/domain/models.py placed by app/mandate/tiers.py `tier_for`, on docs/techdoc-chat-fixes @ 571ea64f:
- Tier 3 always: SignPersonalGuarantee, PledgeCollateral, IssueEquity, ChangeMandate; AddFacility unless requested_by OWNER;
  any operation type not in the known lists (fail closed).
- Tier 2 always: ApplyForFacility, CommitPurchase (ADR-0013), SetUpContractTerms and UndoContractTerms (ADR-0014); an
  AddFacility the owner requested; DrawFacility / SubmitInvoiceForFinancing on a facility that is not owner-approved and
  COMMITTED; ReceivePayment not from SYSTEM (the bank feed) or the owner; AcceptOffer / RecordCommitment that lengthens terms
  or is anything but an early payment on a named invoice, or worth more than tier2_single_commitment_fen.
- Tier 1 otherwise (_TIER1_BASE): AcceptOffer, CounterOffer, RejectOffer, RecordCommitment, DrawFacility, RepayFacility,
  SubmitInvoiceForFinancing, ReceivePayment, RequestOwnerApproval.
The mandate figures are the signed demo mandate, fixtures/scenarios/golden_sme.mandate.signed.json (version 1).
Revised 19 Oct 2026 to match the Security Self-Assessment's Table 5 and the submission build's code: a buyer cannot reach
/operations, so a receipt is Tier 2 only when the agent reports it; a draw on a facility that is not committed and
owner-approved is Tier 2; AddFacility by anyone but the owner is Tier 3; the ¥100,000 threshold compares a commitment's net
new future concessions (an early-payment discount has none, so it never limits invoice face).
"""

import matplotlib.patches as mp
from matplotlib.patches import FancyBboxPatch, Rectangle

from flowstyle import (AMBER, AMBER_INK, AMBER_SOFT, BLUE, BLUE_DEEP, BLUE_SOFT, BUILD, GREY_SOFT, INK, INK_2, MIN_PT,
                       PURPLE, PURPLE_INK, PURPLE_SOFT, WHITE, canvas, save, stamp)

LH = MIN_PT * 1.2 / 72
GAP_ITEM = 0.07
ROWS = [
    ("Buyer offers", [
        ["counter or reject\nan offer", "accept a plain early-\npayment discount on a\nnamed invoice (any face)"],
        ["rebates; changes to\nterms, price or volume", "a commitment whose\nfuture concessions\nexceed ¥100,000"],
        [],
    ]),
    ("Funding", [
        ["draw or advance on a\ncommitted, owner-\napproved facility at\nor below 15% a year", "repay a facility"],
        ["a draw the agent\nrequests above 15%", "draw on any other\nfacility", "apply for or add a\nfacility (the owner)"],
        ["add a facility, by\nanyone but the owner"],
    ]),
    ("Cash received", [
        ["book a receipt from\nthe bank feed or\nthe owner"],
        ["a receipt reported\nby the agent"],
        [],
    ]),
    ("Purchases and contracts", [
        ["ask the owner for\napproval (only queues)"],
        ["commit a purchase\n(owner only)", "set up or undo a\ncontract's terms\n(owner only)"],
        [],
    ]),
    ("Ownership, control and anything unknown", [
        None,
        None,
        ["sign a personal\nguarantee", "pledge collateral,\nissue equity", "change the mandate\nthrough the API",
         "an unknown operation\ntype (fails closed)"],
    ]),
]
TIERS = [
    ("Tier 1", "FLOW may act, inside\nthe signed mandate", BLUE, BLUE_SOFT, BLUE_DEEP, "square", "s"),
    ("Tier 2", "needs the owner's\napproval; queued", PURPLE, PURPLE_SOFT, PURPLE_INK, "circle", "o"),
    ("Tier 3", "never, whoever asks,\nthe owner included", AMBER, AMBER_SOFT, AMBER_INK, "octagon", "8"),
]
BAND = 0.36  # the row's name


def cell_h(items):
    if not items:
        return LH + 0.2  # "none", or None: the row's note
    return sum((it.count("\n") + 1) * LH for it in items) + GAP_ITEM * (len(items) - 1) + 0.22


heights = [BAND + max(cell_h(c) for c in cells) for _, cells in ROWS]
HEAD, FOOT = 1.12, 2.15
H = 0.06 + HEAD + sum(heights) + FOOT
fig, ax = canvas(H)
X0, XR = 0.05, 7.95
CW = (XR - X0) / 3
XS = [X0 + i * CW for i in range(3)]


def badge(x, y, n, shape, color):
    r = 0.2
    if shape == "square":
        p = mp.Rectangle((x - r, y - r), 2 * r, 2 * r, fc=color, ec="none")
    elif shape == "circle":
        p = mp.Circle((x, y), r * 1.1, fc=color, ec="none")
    else:
        p = mp.RegularPolygon((x, y), 8, radius=r * 1.15, orientation=0.3927, fc=color, ec="none")
    p.set_zorder(5)
    ax.add_patch(p)
    ax.text(x, y, n, ha="center", va="center", fontsize=MIN_PT, fontweight="bold", color=WHITE, zorder=6)


# header: one card per tier
top = H - 0.06
for (name, sub, edge, fill, ink, shape, _mk), x in zip(TIERS, XS):
    ax.add_patch(FancyBboxPatch((x + 0.04, top - HEAD + 0.08), CW - 0.08, HEAD - 0.08,
                                boxstyle="round,pad=0,rounding_size=0.08", fc=fill, ec=edge, lw=2.2, zorder=2))
    badge(x + 0.32, top - 0.3, name[-1], shape, ink)
    ax.text(x + 0.62, top - 0.3, name, va="center", fontsize=17, fontweight="bold", color=ink, zorder=4)
    ax.text(x + 0.16, top - 0.56, sub, va="top", fontsize=MIN_PT, color=ink, zorder=4, linespacing=1.2)

# body: a named band per row, then the three cells
y = top - HEAD
for (label, cells), h in zip(ROWS, heights):
    ax.add_patch(Rectangle((X0, y - BAND), XR - X0, BAND, fc=GREY_SOFT, ec="none", zorder=0))
    ax.text(X0 + 0.12, y - BAND / 2, label, va="center", fontsize=14.5, fontweight="bold", color=INK, zorder=3,
            bbox=dict(fc=GREY_SOFT, ec="none", pad=1.5))
    for (name, sub, edge, fill, ink, shape, mk), x, items in zip(TIERS, XS, cells):  # noqa: B007
        yy = y - BAND - 0.11
        if items is None:
            if x == XS[0]:
                ax.text(x + 0.16, yy, "none: nobody can do these through FLOW,\nthe owner included", va="top",
                        fontsize=MIN_PT, color=INK_2, style="italic", linespacing=1.2, bbox=dict(fc=WHITE, ec="none", pad=2))
            continue
        if not items:
            ax.text(x + 0.16, yy, "none", va="top", fontsize=MIN_PT, color=INK_2, style="italic")
        for it in items:
            ax.plot([x + 0.22], [yy - LH * 0.5], marker=mk, ms=7.5, color=edge, zorder=4)
            ax.text(x + 0.38, yy, it, va="top", fontsize=MIN_PT, color=INK, linespacing=1.2, zorder=4)
            yy -= (it.count("\n") + 1) * LH + GAP_ITEM
    y -= h
for x in XS[1:]:
    ax.plot([x, x], [y, top - HEAD], color="#d5dbe5", lw=1.0, zorder=0)
ax.plot([X0, XR], [y, y], color="#c9d1dd", lw=1.2, zorder=1)

# the signed mandate and the rule
fy = y - 0.14
ax.add_patch(FancyBboxPatch((X0, fy - 1.45), XR - X0, 1.45, boxstyle="round,pad=0,rounding_size=0.08", fc=PURPLE_SOFT,
                            ec=PURPLE, lw=1.6, zorder=1))
ax.text(X0 + 0.14, fy - 0.1, "The signed demo mandate (version 1, Ed25519, days 0–90)", va="top", fontsize=14.5,
        fontweight="bold", color=PURPLE_INK)
ax.text(X0 + 0.14, fy - 0.42,
        "cash reserve ¥300,000 · discount ≤ 1.5% · future concessions ≤ ¥5,000 a year\n"
        "DSCR ≥ 1.25× · leverage ≤ 2.5× · the owner approves a draw the agent\n"
        "requests above 15% a year, and a commitment whose net new future concessions\n"
        "exceed ¥100,000 (the ¥5,000 cap binds first)",
        va="top", fontsize=MIN_PT, color=INK, linespacing=1.25)
ax.text(X0, 0.3, "No caller can set a tier. An approved Tier 2 operation passes every gate again.",
        va="bottom", fontsize=12, color=INK_2)
stamp(fig, "app/mandate/tiers.py, executor.py, golden-books mandate; checked on 5926ef29", y_in=0.03)

save(fig, "fig10-authority-matrix.png")
