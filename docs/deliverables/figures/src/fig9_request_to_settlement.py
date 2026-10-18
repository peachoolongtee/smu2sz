"""Figure 9: one buyer request, from request to settlement. Render:
uv run --no-project --with matplotlib --with pillow python fig9_request_to_settlement.py

Replaces fig2 for the submission. It separates what is only proposed, what is authorised, what is recorded and what has
actually settled. Checked against docs/techdoc-chat-fixes @ 571ea64f, services/api:
1  POST /offers (app/api/offers.py), or a pasted reply (POST /offers/{id}/buyer-reply, app/api/outbound.py); how it arrived is
   kept as a ReceivedFact: owner, agent, buyer_key, buyer_reply or anonymous (outbound.py `_provenance_text`).
2  app/compiler: typed obligations with verbatim quotes (grounding.py), coverage proof (coverage.py), or abstain.
3  POST /offers/{id}/evaluate (app/api/decide.py, app/verifier/evaluate.py): Outcome ACCEPT, COUNTER, REJECT, NO_DEAL,
   NEEDS_OWNER_APPROVAL, NO_VERDICT (app/domain/models.py).
4  app/verifier/counters.py: counters priced from the marginal cost of funds.
5  the owner: POST /offers/{id}/accept or /decline (app/api/accept.py), or picks a counter to send.
6a POST /negotiate/{id} (decide.py): the deterministic buyer kernel (app/counterparties), text through app/egress/guard.py.
6b GET .../counters/{cid}/message then POST .../offered (outbound.py): the owner sends it outside FLOW and marks it sent.
7a the kernel's reply, recorded by /negotiate.  7b POST .../buyer-accepted (bound to the message hash) or .../buyer-reply.
8  the executor's AcceptOffer (app/operations/executor.py `_screen_commitment`: nonce, expiry, terms hash, mandate version,
   backing verdict; `reverify` on today's books; Tier 2 queued for the owner).
9  app/commitments (nonce, terms_hash); every outcome appended to the hash-chained log (app/operations/log.py).
10 POST /router/plan, the alert's act (app/api/alerts.py): DRAW_FACILITY, SUBMIT_INVOICE_FOR_FINANCING through the executor.
11 RECEIVE_PAYMENT posted with the bank-feed key as SYSTEM (app/api/auth.py; app/api/demo_bank.py in demo mode).
12 app/alerts/reconcile.py, PromiseStatus AWAITED, RECEIVED, LAPSED, SETTLED_OTHERWISE.

Revised 18 Oct 2026 against int/final3 @ 2ce5265c:
4a the autonomous Tier-1 branch. POST /nl with actor COUNTERPARTY and a valid X-Counterparty-Key (app/api/nl.py: the key binds
   the sender and sets COUNTERPARTY_AUTHENTICATED) runs app/nl/offers.py `counterparty_message` with execute=True: FLOW
   counters, rejects or accepts within Tier 1, which for an acceptance is only an early-payment discount on a named invoice
   (app/mandate/tiers.py `tier_for`, app/verifier/evaluate.py). No owner step; the reply leaves through the egress guard.
   Without a valid key the same message is a proposal only: nothing is executed.
9b "agreement recorded; funding incomplete": the commitment of step 8 stands while a funding leg is queued for the owner's
   approval (effective annual cost above the mandate's ceiling, Tier 2) or refused by the executor. app/api/accept.py
   ("Records the agreement now; no payment and no funding moves", `funding_next`), app/nl/plans.py `run_legs`.
"""

import matplotlib.patches as mp
from matplotlib.patches import FancyBboxPatch

from flowstyle import (AMBER, AMBER_INK, AMBER_SOFT, BLUE, BLUE_DEEP, BLUE_SOFT, BUILD_FINAL, GREY, GREY_HATCH, GREY_SOFT,
                       INK, INK_2, MIN_PT, PURPLE, PURPLE_INK, PURPLE_SOFT, WHITE, arrow, canvas, save, stamp)

K = {
    "code": dict(fill=BLUE_SOFT, edge=BLUE, ink=INK, badge=BLUE_DEEP, shape="square"),
    "model": dict(fill=AMBER_SOFT, edge=AMBER, ink=AMBER_INK, badge=AMBER_INK, shape="diamond"),
    "owner": dict(fill=PURPLE_SOFT, edge=PURPLE, ink=PURPLE_INK, badge=PURPLE, shape="circle"),
    "sim": dict(fill=GREY_SOFT, edge=GREY, ink=INK, badge="#5b6679", shape="hexagon"),
    "outcome": dict(fill=WHITE, edge=INK, ink=INK, badge=BLUE_DEEP, shape="square"),  # code, drawn as an end state
}

H = 14.85
fig, ax = canvas(H)
X0, X1 = 0.05, 6.15  # the steps
SX = 6.28  # the status column
MID = (X0 + X1) / 2
XT1 = 2.5  # the Tier-1 column: X0..XT1
XO0 = 2.64  # the owner's lane: XO0..X1
XOA1, XOB0 = 4.325, 4.465  # the owner's lane, split
X91, X9B0 = 3.85, 4.12  # row 9: the funding plan and the outcome
GAP = 0.17
LH_T, LH_B = 15 * 1.22 / 72, MIN_PT * 1.22 / 72


def badge(x, y, n, kind):
    k = K[kind]
    r = 0.2
    if k["shape"] == "square":
        p = mp.Rectangle((x - r, y - r), 2 * r, 2 * r, fc=k["badge"], ec="none")
    elif k["shape"] == "diamond":
        p = mp.RegularPolygon((x, y), 4, radius=r * 1.38, fc=k["badge"], ec="none")
    elif k["shape"] == "circle":
        p = mp.Circle((x, y), r * 1.08, fc=k["badge"], ec="none")
    else:
        p = mp.RegularPolygon((x, y), 6, radius=r * 1.15, fc=k["badge"], ec="none")
    p.set_zorder(5)
    ax.add_patch(p)
    ax.text(x, y, n, ha="center", va="center", fontsize=MIN_PT if len(n) < 3 else 12, fontweight="bold", color=WHITE,
            zorder=6)


def frame(x0, x1, y, h, kind):
    k = K[kind]
    ax.add_patch(FancyBboxPatch((x0, y), x1 - x0, h, boxstyle="round,pad=0,rounding_size=0.07", fc=k["fill"], ec=k["edge"],
                                lw=2.0, zorder=3, ls=(0, (5, 2.5)) if kind == "outcome" else "-"))
    if kind == "sim":
        ax.add_patch(FancyBboxPatch((x0, y), x1 - x0, h, boxstyle="round,pad=0,rounding_size=0.07", fc="none",
                                    ec=GREY_HATCH, lw=0, hatch="//", zorder=3.2))


def _bb(kind):
    return dict(fc=K[kind]["fill"], ec="none", pad=0.5) if kind == "sim" else None


def step(x0, x1, y, h, n, title, body, kind):
    """A wide step: badge on the left, title and body beside it, centred vertically."""
    k = K[kind]
    frame(x0, x1, y, h, kind)
    badge(x0 + 0.3, y + h / 2, n, kind)
    tx = x0 + 0.6
    lines = body.count("\n") + 1 if body else 0
    top = y + h / 2 + (LH_T + (lines * LH_B + 0.02 if body else 0)) / 2
    ax.text(tx, top, title, ha="left", va="top", fontsize=15, fontweight="bold", color=k["ink"], zorder=6, bbox=_bb(kind))
    if body:
        ax.text(tx, top - LH_T - 0.02, body, ha="left", va="top", fontsize=MIN_PT, color=k["ink"], zorder=6,
                linespacing=1.22, bbox=_bb(kind))


def nstep(x0, x1, y, h, n, title, body, kind):
    """A narrow step: badge and title on the first line, the body below across the full width."""
    k = K[kind]
    frame(x0, x1, y, h, kind)
    lines = body.count("\n") + 1
    block = 0.42 + lines * MIN_PT * 1.42 / 72  # YaHei's line box is taller than 1.22 em
    top = y + h / 2 + block / 2
    badge(x0 + 0.3, top - 0.2, n, kind)
    ax.text(x0 + 0.58, top - 0.2, title, ha="left", va="center", fontsize=15, fontweight="bold", color=k["ink"], zorder=6,
            bbox=_bb(kind))
    ax.text(x0 + 0.12, top - 0.46, body, ha="left", va="top", fontsize=MIN_PT, color=k["ink"], zorder=6, linespacing=1.22,
            bbox=_bb(kind))


rows = []  # (bottom, top) of each row, top to bottom
y = H - 0.12


def row(h, gap=GAP):
    global y
    top, y = y, y - h
    rows.append((y, top))
    bottom = y
    y -= gap
    return bottom


TWO, THREE, SPLIT = 0.64, 0.88, 1.6
r = row(TWO); step(X0, X1, r, TWO, "1", "Buyer request arrives",
                   "simulated buyer, or pasted by the owner; origin recorded", "sim")
r = row(TWO); step(X0, X1, r, TWO, "2", "Reading", "typed terms, each with its exact quote, or abstain", "model")
r = row(THREE, gap=0.46); step(X0, X1, r, THREE, "3", "Verdict and counters, on today's books",
                               "cash reserve, covenants, break-even, mandate → one of six\nverdicts; counters priced below the cost of funds", "code")
r4 = row(THREE); step(XO0, X1, r4, THREE, "4b", "Owner gate", "picks a counter, accepts\nas asked, or declines", "owner")
r5 = row(SPLIT)
nstep(XO0, XOA1, r5, SPLIT, "5a", "Send", "simulated\nchannel,\negress-checked", "sim")
nstep(XOB0, X1, r5, SPLIT, "5b", "Send", "real buyer:\nthe owner\ncopies it and\nmarks it sent", "owner")
r6 = row(SPLIT)
nstep(XO0, XOA1, r6, SPLIT, "6a", "Reply", "the simulated\nbuyer answers", "sim")
nstep(XOB0, X1, r6, SPLIT, "6b", "Reply", "owner-reported,\nbound to the\nmessage sent", "owner")
# 4a: the autonomous Tier-1 branch spans rows 4 to 6
t_top, t_bot = rows[3][1], rows[5][0]
nstep(X0, XT1, t_bot, t_top - t_bot, "4a", "Tier 1, alone",
      "a registered buyer\nwriting on its own\nchannel key: FLOW\ncounters, declines\nor accepts a plain\nearly-payment\n"
      "discount inside\nthe signed mandate;\nno owner step.\nCounters and declines\ngo back on the channel,\negress-checked;\nnothing binds.", "code")
r = row(THREE); step(X0, X1, r, THREE, "7", "Acceptance screened by the executor",
                     "nonce, terms hash, verdict; re-verified on today's books;\nTier 2 waits for the owner; a refusal records nothing", "code")
r = row(TWO); step(X0, X1, r, TWO, "8", "Commitment recorded", "in the hash-chained log, with its terms hash", "code")
H9 = 1.9
r9 = row(H9)
step(X0, X91, r9, H9, "9", "Funding plan", "cheapest admissible draws\nand advances; the executor\nruns them at Tier 1, or\nqueues them for the owner", "code")
nstep(X9B0, X1, r9, H9, "9b", "Outcome", "agreement\nrecorded; funding\nincomplete: a leg\nqueued or refused\nafter step 8", "outcome")
r = row(TWO); step(X0, X1, r, TWO, "10", "Bank-feed receipt", "the payment, posted by the bank feed as SYSTEM", "sim")
r = row(TWO); step(X0, X1, r, TWO, "11", "Reconciliation", "promises marked received, lapsed or settled otherwise", "code")

# ---------------------------------------------------------------- arrows
CT, CO = (X0 + XT1) / 2, (XO0 + X1) / 2
CA, CB = (XO0 + XOA1) / 2, (XOB0 + X1) / 2
C9 = (X0 + X91) / 2


def gap_mid(i):
    return rows[i][0] - (rows[i][0] - rows[i + 1][1]) / 2


# 3 -> 4a / 4b, with the deciding fact on each branch
b3, t4 = rows[2][0], rows[3][1]
m = b3 - 0.13
arrow(ax, [(MID, b3), (MID, m), (CT, m), (CT, t4)], lw=2.0)
arrow(ax, [(MID, m), (CO, m), (CO, t4)], lw=2.0)
ax.text(CT + 0.1, (m + t4) / 2 - 0.03, "buyer's own channel key", ha="left", va="center", fontsize=12.5, color=INK, zorder=6)
ax.text(CO + 0.1, (m + t4) / 2 - 0.03, "any other sender", ha="left", va="center", fontsize=12.5, color=INK, zorder=6)
# 4b -> 5a / 5b
b4, t5 = rows[3][0], rows[4][1]
m = gap_mid(3)
arrow(ax, [(CO, b4), (CO, m), (CA, m), (CA, t5)], lw=2.0)
arrow(ax, [(CO, m), (CB, m), (CB, t5)], lw=2.0)
# 5 -> 6
arrow(ax, [(CA, rows[4][0]), (CA, rows[5][1])], lw=2.0)
arrow(ax, [(CB, rows[4][0]), (CB, rows[5][1])], lw=2.0)
# 6a / 6b and 4a (an acceptance) -> 7
b6, t7 = rows[5][0], rows[6][1]
m = gap_mid(5)
arrow(ax, [(CA, b6), (CA, m), (MID + 0.35, m), (MID + 0.35, t7)], lw=2.0)
ax.plot([CB, CB, MID + 0.35], [b6, m, m], color=INK, lw=2.0, zorder=2)
arrow(ax, [(CT, b6), (CT, t7)], lw=2.0)
ax.text(CT + 0.08, m, "accept", ha="left", va="center", fontsize=12.5, color=INK, zorder=6,
        bbox=dict(fc=WHITE, ec="none", pad=0.6))
# 7 -> 8 -> 9 -> 10 -> 11, and 9 -> 9b
arrow(ax, [(MID, rows[6][0]), (MID, rows[7][1])], lw=2.0)
arrow(ax, [(C9, rows[7][0]), (C9, rows[8][1])], lw=2.0)
arrow(ax, [(C9, rows[8][0]), (C9, rows[9][1])], lw=2.0)
arrow(ax, [(MID, rows[9][0]), (MID, rows[10][1])], lw=2.0)
yb = r9 + H9 / 2
arrow(ax, [(X91, yb), (X9B0, yb)], lw=2.0)


# ---------------------------------------------------------------- the status column: what the terms are at each stage
def status(first, last, name, note, style):
    y0, y1 = rows[last][0], rows[first][1]
    x = SX + 0.08
    if style == "dotted":
        ax.plot([x, x], [y0, y1], color=INK_2, lw=3.0, ls=(0, (1, 1.6)), solid_capstyle="round")
    elif style == "solid":
        ax.plot([x, x], [y0, y1], color=INK, lw=3.0)
    elif style == "double":
        ax.plot([x - 0.04, x - 0.04], [y0, y1], color=INK, lw=2.0)
        ax.plot([x + 0.04, x + 0.04], [y0, y1], color=INK, lw=2.0)
    else:  # thick bar
        ax.add_patch(mp.Rectangle((x - 0.07, y0), 0.14, y1 - y0, fc=INK, ec="none"))
    for yy in (y0, y1):
        ax.plot([x, x + 0.12], [yy, yy], color=INK, lw=2.0)
    nl, bl = name.count("\n") + 1, note.count("\n") + 1
    lh = MIN_PT * 1.2 / 72
    top = (y0 + y1) / 2 + (nl + bl) * lh / 2
    ax.text(x + 0.2, top, name, ha="left", va="top", fontsize=MIN_PT, fontweight="bold", color=INK, linespacing=1.2)
    ax.text(x + 0.2, top - nl * lh, note, ha="left", va="top", fontsize=MIN_PT, color=INK, linespacing=1.2)


status(0, 5, "PROPOSED\nTERMS", "nothing binds;\nno money\nmoves", "dotted")
status(6, 6, "AUTHORISED", "operation", "solid")
status(7, 7, "RECORDED", "commitment", "double")
status(8, 8, "AUTHORISED", "funding\noperations,\nor queued /\nrefused (9b)", "solid")
status(9, 10, "ACTUAL\nSETTLE-\nMENT", "cash the bank\nfeed reported", "bar")

# ---------------------------------------------------------------- legend and identifier
LY = 0.9
leg = [("code", "deterministic code"), ("model", "model-assisted"), ("owner", "the owner"), ("sim", "simulated")]
xs = [0.05, 2.55, 4.75, 6.4]
for (kind, text), x in zip(leg, xs):
    badge(x + 0.2, LY, "", kind)
    ax.text(x + 0.5, LY, text, va="center", fontsize=MIN_PT, color=INK)
ax.text(0.1, 0.47, "Every outcome, refusals included, goes to the hash-chained log. Dashed box: an end state.",
        va="center", fontsize=MIN_PT - 1.5, color=INK_2)
stamp(fig, f"Checked against the code on {BUILD_FINAL} · synthetic data", y_in=0.04)

save(fig, "fig9-request-to-settlement.png")
