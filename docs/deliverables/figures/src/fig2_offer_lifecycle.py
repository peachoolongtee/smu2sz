"""Figure 2: one buyer request from message to money. Render: uv run --no-project --with matplotlib --with pillow python fig2_offer_lifecycle.py

Checked against dev (975e082f), services/api:
- POST /offers (app/api/offers.py) stores and compiles the message; POST /offers/{id}/evaluate (app/api/decide.py) gives the
  verdict, Outcome in app/domain/models.py: ACCEPT, COUNTER, REJECT, NO_DEAL, NEEDS_OWNER_APPROVAL, NO_VERDICT;
- counters are built and verified by app/verifier/counters.py;
- the owner answers a request without a counter with POST /offers/{id}/accept or /decline (app/api/accept.py);
- POST /negotiate/{id} (app/api/decide.py) sends the chosen counter to the simulated buyer kernel (app/counterparties);
- POST .../counters/{cid}/offered and .../buyer-accepted (app/api/outbound.py): the owner sent it outside FLOW and records the
  buyer's yes; the executor's AcceptOffer screens it against the verdict and re-verifies it on today's books
  (app/operations/executor.py `_screen_commitment`, `reverify`), queuing Tier 2 for the owner;
- the commitment carries a nonce and a terms hash (app/commitments, `terms_hash`, `check_acceptance`);
- cash events are RECEIVE_PAYMENT (bank feed, simulated), DRAW_FACILITY and SUBMIT_INVOICE_FOR_FINANCING on the simulated bank;
- reconciliation, app/alerts/reconcile.py, PromiseStatus: AWAITED, RECEIVED, LAPSED, SETTLED_OTHERWISE.
"""

from matplotlib.patches import FancyBboxPatch

from flowstyle import (BLUE, BLUE_SOFT, GREY, GREY_SOFT, INK, INK_2, PURPLE, PURPLE_INK, PURPLE_SOFT, arrow, canvas,
                       save)

AUTO = dict(fill=BLUE_SOFT, edge=BLUE, ink=INK)
OWNER = dict(fill=PURPLE_SOFT, edge=PURPLE, ink=PURPLE_INK)
SIM = dict(fill=GREY_SOFT, edge=GREY, ink=INK)

H = 10.25
S, D = 0.5, 0.72  # single- and two-line row heights
fig, ax = canvas(H)
X0, X1 = 0.25, 5.25  # main column
RX = 5.45  # code references
MID = (X0 + X1) / 2


def step(x0, x1, y, h, n, text, kind, ref=None, pt=14):
    ax.add_patch(FancyBboxPatch((x0, y), x1 - x0, h, boxstyle="round,pad=0,rounding_size=0.07", fc=kind["fill"],
                                ec=kind["edge"], lw=2.0, zorder=3))
    ax.text(x0 + 0.12, y + h / 2, n, ha="left", va="center", fontsize=15, fontweight="bold", color=kind["edge"], zorder=4)
    ax.text(x0 + 0.48, y + h / 2, text, ha="left", va="center", fontsize=pt, color=kind["ink"], zorder=4, linespacing=1.2)
    if ref:
        ax.text(RX, y + h / 2, ref, ha="left", va="center", fontsize=13.5, color=INK_2, zorder=4, linespacing=1.2,
                family="Consolas")


# legend
for i, (k, t) in enumerate([(AUTO, "automatic"), (OWNER, "the owner"), (SIM, "simulated")]):
    x = 0.25 + i * 1.75
    ax.add_patch(FancyBboxPatch((x, H - 0.42), 0.34, 0.24, boxstyle="round,pad=0,rounding_size=0.04", fc=k["fill"],
                                ec=k["edge"], lw=2.0))
    ax.text(x + 0.45, H - 0.30, t, va="center", fontsize=14)
ax.text(RX, H - 0.30, "where in the code", va="center", fontsize=14, color=INK_2, fontweight="bold")

G = 0.22  # arrow gap
rows = []
y = H - 0.65
def nxt(h):
    global y
    top = y
    y = y - h
    rows.append((y, top))
    yy = y
    y -= G
    return yy

r = nxt(S); step(X0, X1, r, S, "1", "Buyer message received (text or document)", AUTO, "POST /offers, /nl")
r = nxt(S); step(X0, X1, r, S, "2", "Read by the compiler: typed terms, or abstain", AUTO, "app/compiler")
r = nxt(0.85); step(X0, X1, r, 0.85, "3", "Verdict on today's books\nACCEPT · COUNTER · REJECT · NO_DEAL\nNEEDS_OWNER_APPROVAL · NO_VERDICT",
                  AUTO, "POST /offers/{id}/\nevaluate", pt=14)
r = nxt(S); step(X0, X1, r, S, "4", "Counters drafted and verified", AUTO, "verifier/counters.py")
r = nxt(D); step(X0, X1, r, D, "5", "Owner reviews: picks a counter,\nor accepts as asked, or declines", OWNER,
                  "/offers/{id}/accept\n/offers/{id}/decline")
XA1, XB0 = 2.65, 2.85
r6 = nxt(D)
step(X0, XA1, r6, D, "6a", "Sent to the\nbuyer kernel", SIM)
step(XB0, X1, r6, D, "6b", "Sent outside FLOW\nby the owner", OWNER)
ax.text(RX, r6 + D / 2, "a POST /negotiate/{id}\nb .../offered", ha="left", va="center", fontsize=13.5, color=INK_2,
        family="Consolas", linespacing=1.2)
r7 = nxt(D)
step(X0, XA1, r7, D, "7a", "Kernel's reply\nrecorded", SIM)
step(XB0, X1, r7, D, "7b", "Owner records\nthe buyer's yes", OWNER)
ax.text(RX, r7 + D / 2, "b .../buyer-accepted", ha="left", va="center", fontsize=13.5, color=INK_2, family="Consolas")
r = nxt(D); step(X0, X1, r, D, "8", "Terms re-verified on today's books;\nTier 2 waits for the owner", AUTO,
                  "executor:\nAcceptOffer")
r = nxt(S); step(X0, X1, r, S, "9", "Commitment recorded: nonce, terms hash", AUTO, "app/commitments")
r = nxt(D); step(X0, X1, r, D, "10", "Cash events on the simulated bank:\nearly payment · draw · advance", SIM,
                   "RECEIVE_PAYMENT\nDRAW · ADVANCE")
r = nxt(0.85); step(X0, X1, r, 0.85, "11", "Reconciliation of each promise\nAWAITED · RECEIVED · LAPSED\nSETTLED_OTHERWISE",
                   AUTO, "alerts/reconcile.py")

# arrows between rows
CA, CB = (X0 + XA1) / 2, (XB0 + X1) / 2
for i in range(len(rows) - 1):
    (b0, _), (_, t1) = rows[i], rows[i + 1]
    if i == 4:  # 5 -> 6a / 6b
        arrow(ax, [(MID, b0), (MID, b0 - G / 2), (CA, b0 - G / 2), (CA, t1)], color=INK)
        arrow(ax, [(MID, b0 - G / 2), (CB, b0 - G / 2), (CB, t1)], color=INK)
    elif i == 5:  # 6 -> 7, each side
        arrow(ax, [(CA, b0), (CA, t1)], color=INK)
        arrow(ax, [(CB, b0), (CB, t1)], color=INK)
    elif i == 6:  # 7a / 7b -> 8
        arrow(ax, [(CA, b0), (CA, b0 - G / 2), (MID, b0 - G / 2), (MID, t1)], color=INK)
        ax.plot([CB, CB, MID], [b0, b0 - G / 2, b0 - G / 2], color=INK, lw=2.2, zorder=2)
    else:
        arrow(ax, [(MID, b0), (MID, t1)], color=INK)

save(fig, "fig2-offer-lifecycle.png")
