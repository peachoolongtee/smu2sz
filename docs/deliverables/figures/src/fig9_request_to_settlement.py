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
"""

import matplotlib.patches as mp
from matplotlib.patches import FancyBboxPatch

from flowstyle import (AMBER, AMBER_INK, AMBER_SOFT, BLUE, BLUE_DEEP, BLUE_SOFT, BUILD, GREY, GREY_HATCH, GREY_SOFT, INK,
                       INK_2, MIN_PT, PURPLE, PURPLE_INK, PURPLE_SOFT, WHITE, arrow, canvas, save, stamp)

K = {
    "code": dict(fill=BLUE_SOFT, edge=BLUE, ink=INK, badge=BLUE_DEEP, shape="square"),
    "model": dict(fill=AMBER_SOFT, edge=AMBER, ink=AMBER_INK, badge=AMBER_INK, shape="diamond"),
    "owner": dict(fill=PURPLE_SOFT, edge=PURPLE, ink=PURPLE_INK, badge=PURPLE, shape="circle"),
    "sim": dict(fill=GREY_SOFT, edge=GREY, ink=INK, badge="#5b6679", shape="hexagon"),
}

H = 11.25
fig, ax = canvas(H)
X0, X1 = 0.05, 5.95  # the steps
SX = 6.1  # the status column
MID = (X0 + X1) / 2
XA1, XB0 = 2.93, 3.07  # the split rows
GAP = 0.17


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


def step(x0, x1, y, h, n, title, body, kind):
    k = K[kind]
    ax.add_patch(FancyBboxPatch((x0, y), x1 - x0, h, boxstyle="round,pad=0,rounding_size=0.07", fc=k["fill"], ec=k["edge"],
                                lw=2.0, zorder=3))
    if kind == "sim":
        ax.add_patch(FancyBboxPatch((x0, y), x1 - x0, h, boxstyle="round,pad=0,rounding_size=0.07", fc="none",
                                    ec=GREY_HATCH, lw=0, hatch="//", zorder=3.2))
    badge(x0 + 0.3, y + h / 2, n, kind)
    tx = x0 + 0.6
    lines = body.count("\n") + 1 if body else 0
    lh_t, lh_b = 15 * 1.22 / 72, MIN_PT * 1.22 / 72
    top = y + h / 2 + (lh_t + (lines * lh_b + 0.02 if body else 0)) / 2
    ax.text(tx, top, title, ha="left", va="top", fontsize=15, fontweight="bold", color=k["ink"], zorder=6,
            bbox=dict(fc=k["fill"], ec="none", pad=0.5) if kind == "sim" else None)
    if body:
        ax.text(tx, top - lh_t - 0.02, body, ha="left", va="top", fontsize=MIN_PT, color=k["ink"], zorder=6,
                linespacing=1.22, bbox=dict(fc=k["fill"], ec="none", pad=0.5) if kind == "sim" else None)


rows = []  # (bottom, top) of each row, top to bottom
y = H - 0.12


def row(h):
    global y
    top, y = y, y - h
    rows.append((y, top))
    bottom = y
    y -= GAP
    return bottom


TWO, THREE, SPLIT = 0.64, 0.88, 0.84
r = row(TWO); step(X0, X1, r, TWO, "1", "Buyer request arrives", "simulated buyer, or pasted by the owner; origin recorded", "sim")
r = row(TWO); step(X0, X1, r, TWO, "2", "Reading", "typed terms, each with its exact quote, or abstain", "model")
r = row(THREE); step(X0, X1, r, THREE, "3", "Verdict and counters, on today's books",
                     "cash reserve, covenants, break-even, mandate → one of six\nverdicts; counters priced below the cost of funds", "code")
r = row(TWO); step(X0, X1, r, TWO, "4", "Owner gate", "picks a counter, accepts as asked, or declines", "owner")
r5 = row(SPLIT)
step(X0, XA1, r5, SPLIT, "5a", "Send", "simulated channel,\negress-checked", "sim")
step(XB0, X1, r5, SPLIT, "5b", "Send", "real buyer: the owner\ncopies it, marks it sent", "owner")
r6 = row(SPLIT)
step(X0, XA1, r6, SPLIT, "6a", "Reply", "simulated buyer\nanswers", "sim")
step(XB0, X1, r6, SPLIT, "6b", "Reply", "owner-reported, bound\nto the message sent", "owner")
r = row(THREE); step(X0, X1, r, THREE, "7", "Acceptance screened by the executor",
                     "nonce, terms hash, verdict; re-verified on today's books;\nTier 2 waits for the owner", "code")
r = row(TWO); step(X0, X1, r, TWO, "8", "Commitment recorded", "in the hash-chained log, with its terms hash", "code")
r = row(THREE); step(X0, X1, r, THREE, "9", "Funding plan",
                     "cheapest admissible draws and advances; the executor\nruns them at Tier 1, or queues them for the owner", "code")
r = row(TWO); step(X0, X1, r, TWO, "10", "Bank-feed receipt", "the payment, posted by the bank feed as SYSTEM", "sim")
r = row(TWO); step(X0, X1, r, TWO, "11", "Reconciliation", "promises marked received, lapsed or settled otherwise", "code")

# arrows between rows
CA, CB = (X0 + XA1) / 2, (XB0 + X1) / 2
for i in range(len(rows) - 1):
    (b0, _), (_, t1) = rows[i], rows[i + 1]
    m = b0 - GAP / 2
    if i == 3:  # 4 -> 5a / 5b
        arrow(ax, [(MID, b0), (MID, m), (CA, m), (CA, t1)], lw=2.0)
        arrow(ax, [(MID, m), (CB, m), (CB, t1)], lw=2.0)
    elif i == 4:
        arrow(ax, [(CA, b0), (CA, t1)], lw=2.0)
        arrow(ax, [(CB, b0), (CB, t1)], lw=2.0)
    elif i == 5:  # 6a / 6b -> 7
        arrow(ax, [(CA, b0), (CA, m), (MID, m), (MID, t1)], lw=2.0)
        ax.plot([CB, CB, MID], [b0, m, m], color=INK, lw=2.0, zorder=2)
    else:
        arrow(ax, [(MID, b0), (MID, t1)], lw=2.0)


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
    ax.text(x + 0.22, top, name, ha="left", va="top", fontsize=MIN_PT, fontweight="bold", color=INK, linespacing=1.2)
    ax.text(x + 0.22, top - nl * lh, note, ha="left", va="top", fontsize=MIN_PT, color=INK, linespacing=1.2)


status(0, 5, "PROPOSED\nTERMS", "nothing binds;\nno money\nmoves", "dotted")
status(6, 6, "AUTHORISED", "operation", "solid")
status(7, 7, "RECORDED", "commitment", "double")
status(8, 8, "AUTHORISED", "funding\noperations", "solid")
status(9, 10, "ACTUAL\nSETTLEMENT", "cash the bank\nfeed reported", "bar")

# ---------------------------------------------------------------- legend and identifier
LY = 0.8
leg = [("code", "deterministic code"), ("model", "model-assisted"), ("owner", "the owner"), ("sim", "simulated")]
xs = [0.05, 2.55, 4.75, 6.4]
for (kind, text), x in zip(leg, xs):
    badge(x + 0.2, LY, "", kind)
    ax.text(x + 0.5, LY, text, va="center", fontsize=MIN_PT, color=INK)
ax.text(0.1, 0.4, "A refusal at any gate leaves the terms proposed, and is logged.",
        va="center", fontsize=MIN_PT - 1.5, color=INK_2)
stamp(fig, f"Checked against the code on {BUILD} · synthetic data", y_in=0.02)

save(fig, "fig9-request-to-settlement.png")
