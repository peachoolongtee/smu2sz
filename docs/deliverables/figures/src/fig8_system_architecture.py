"""Figure 8: FLOW's system architecture. Render: uv run --no-project --with matplotlib --with pillow python fig8_system_architecture.py

Replaces fig1 for the submission: it shows the three model-assisted components the document names (02, "Where the model is
used"), the simulated parties, the egress guard and the storage. Checked against docs/techdoc-chat-fixes @ 571ea64f,
services/api:
- app/main.py: one FastAPI service; every tool is an HTTP route (offers, decide, outbound, operations, nl, documents,
  demo_bank, ...). Keys in app/api/auth.py: owner token, agent key, buyer keys, BANK_FEED_KEY (receipts post as SYSTEM).
- Model-assisted, each behind redaction (app/compiler/redaction.py, PRIV-1..3) and a backend chain: recorded cache by default,
  live DeepSeek / Claude only with LLM_MODE=live (app/compiler/backends.py), the rules grammar as fallback:
    1. compiler (app/compiler): buyer messages, term sheets and contracts -> typed terms with verbatim quotes, or abstain;
    2. intent classifier (app/nl/classifier.py): a chat message the rules parser did not understand -> one intent from a
       closed list with typed slots; it cannot name an operation, an amount to move or an approval;
    3. question router (app/nl/router, ADR-0015): an owner's question the deterministic answers missed -> at most three of
       the read-only tools of the closed catalogue with typed slots; the tools (code) write every word and figure.
- Deterministic: app/financial (trajectory), app/covenants, app/health; app/verifier (verdict, counters); app/funding/router.py;
  app/egress/guard.py (outbound text, POST /negotiate and the outbound message, app/api/decide.py and outbound.py);
  app/mandate (Ed25519-signed, pinned to the owner key); app/operations/executor.py (tiers, gates, the only writer of the
  books); app/operations/log.py + app/persistence/chain.py (hash-chained log).
- Simulated: the buyer (app/counterparties, deterministic kernel, or the owner pastes a real buyer's words), the lenders and
  facilities (effects inside the executor) and the bank feed (RECEIVE_PAYMENT as SYSTEM; app/api/demo_bank.py in demo mode).
- Storage: app/persistence: SqlLedgerStore (PostgreSQL via Docker or Supabase with RLS; SQLite locally) or InMemoryLedgerStore.
"""

from matplotlib import patheffects as pe
from matplotlib.patches import FancyBboxPatch, Rectangle

from flowstyle import (AMBER, AMBER_INK, AMBER_SOFT, BLUE, BLUE_SOFT, BUILD, GREY, GREY_HATCH, GREY_SOFT, INK, MIN_PT,
                       PURPLE, PURPLE_SOFT, WHITE, arrow, box, canvas, kbox, save, stamp)

H = 11.74
fig, ax = canvas(H)
W, G = 1.765, 0.1
X = [0.3 + i * (W + G) for i in range(4)]  # four columns
CX = [x + W / 2 for x in X]
XR = X[3] + W  # 7.66
LBUS, RBUS = 0.12, 7.86
HALO = [pe.withStroke(linewidth=7, foreground=WHITE), pe.Normal()]
T = dict(title_pt=14.5, body_pt=MIN_PT)


def a(pts, color=INK, label=None, at=None, halo=False, ha="center", **kw):
    arrow(ax, pts, color=color, label=label, label_xy=at, label_pt=MIN_PT, ha=ha, **kw)
    if halo:
        ax.patches[-1].set_path_effects(HALO)


def zone(y0, y1, name, desc, color, at="top-right"):
    """A dashed trust boundary; its name and rule on a white tab placed where no arrow crosses the border."""
    ax.add_patch(Rectangle((0.22, y0), 7.52, y1 - y0, fill=False, ec=color, lw=2.2, ls=(0, (6, 3)), zorder=1))
    x, ha = {"top-right": (7.6, "right"), "bottom-right": (7.6, "right"), "top-left": (1.32, "left")}[at]
    ax.text(x, y0 if at == "bottom-right" else y1, f"{name}\n{desc}", ha=ha, va="center", fontsize=MIN_PT, color=color, zorder=5, linespacing=1.15,
            fontweight="bold", bbox=dict(fc=WHITE, ec="none", pad=2.0))


# ---------------------------------------------------------------- actors and the API
AY0, AY1 = 10.74, 11.6
kbox(ax, X[0], AY0, W, AY1 - AY0, "Buyer", "requests, replies", "sim")
kbox(ax, X[1], AY0, W, AY1 - AY0, "Owner", "signs, approves", "owner", tag=False)
box(ax, X[2], AY0, W, AY1 - AY0, "Web app", "Next.js · apps/web", fill=GREY_SOFT, edge=GREY, title_pt=15, body_pt=MIN_PT)
kbox(ax, X[3], AY0, W, AY1 - AY0, "Bank feed", "receipts", "sim")
BY0, BY1 = 9.68, 10.33
box(ax, X[0], BY0, XR - X[0], BY1 - BY0, "FastAPI service · app/main.py",
    "every tool is a strict-schema HTTP route · owner, agent, buyer and bank-feed keys", fill=WHITE, edge=INK, title_pt=15,
    body_pt=MIN_PT, gap=0.03)

# ---------------------------------------------------------------- zones
MZ0, MZ1 = 7.02, 9.2
CZ0, CZ1 = 4.75, 6.7
PZ0, PZ1 = 2.3, 4.1
zone(MZ0, MZ1, "Model-assisted", "sees redacted text only", AMBER_INK)
zone(CZ0, CZ1, "Deterministic core", "computes every figure", BLUE, at="bottom-right")
zone(PZ0, PZ1, "Action path", "only the executor writes", INK, at="top-left")

# model row: router, classifier, compiler, backend
MY0, MY1 = 7.32, 8.88
kbox(ax, X[0], MY0, W, MY1 - MY0, "Question\nrouter", "Ask FLOW, live:\npicks ≤ 3 of 40\nread-only tools", "model", **T)
kbox(ax, X[1], MY0, W, MY1 - MY0, "Intent\nclassifier", "chat the rules\nmissed → one\nintent, closed list", "model", **T)
kbox(ax, X[2], MY0, W, MY1 - MY0, "Compiler", "buyer messages,\ncontracts → terms\nwith exact quotes,\nor abstains",
     "model", **T)
box(ax, X[3], MY0 + 0.08, W, MY1 - 0.4 - MY0, "Model backend", "recorded cache\n(default), rules;\nlive: opt-in",
    fill=WHITE, edge=AMBER, ink=AMBER_INK, lw=2.0, **T)
# the bus: each model-assisted step sends redacted text to the backend and gets strict JSON back
BUSY = 7.17
for i in range(3):
    ax.plot([X[i] + 0.3, X[i] + 0.3], [MY0, BUSY], color=AMBER, lw=1.8, ls=(0, (3, 2)), zorder=1.5)
ax.plot([X[0] + 0.3, CX[3]], [BUSY, BUSY], color=AMBER, lw=1.8, ls=(0, (3, 2)), zorder=1.5)
a([(CX[3], BUSY), (CX[3], MY0)], color=AMBER, lw=1.8)
ax.text(X[3] - 0.04, BUSY, "redacted text", ha="right", va="center", fontsize=12, color=AMBER_INK, zorder=5,
        bbox=dict(fc=WHITE, ec="none", pad=0.6))

# core row: tools, engine, verifier, funding router
CY0, CY1 = 4.95, 6.3
box(ax, X[0], CY0, W, CY1 - CY0, "Read-only\ntools", "code writes every\nword and figure", fill=BLUE_SOFT, edge=BLUE, **T)
box(ax, X[1], CY0, W, CY1 - CY0, "Financial\nengine", "daily cash,\ncovenants, health", fill=BLUE_SOFT, edge=BLUE, **T)
box(ax, X[2], CY0, W, CY1 - CY0, "Verifier", "tests the mandate\nand covenants →\nverdict, counters", fill=BLUE_SOFT,
    edge=BLUE, **T)
box(ax, X[3], 5.22, W, CY1 - 5.22, "Funding router", "cheapest\nadmissible mix", fill=BLUE_SOFT, edge=BLUE, **T)

# action row: egress guard, mandate, executor, log
PY0, PY1 = 2.5, 3.78
box(ax, X[0], PY0, W, PY1 - PY0, "Egress guard", "template text;\nblocks protected\nfigures", fill=BLUE_SOFT, edge=BLUE,
    **T)
kbox(ax, X[1], PY0, W, PY1 - PY0, "Signed\nmandate", "Ed25519 · limits\n3 tiers", "owner", **T)
box(ax, X[2], PY0, W, PY1 - PY0, "Executor", "tiers and gates,\nre-verification;\nthe only writer", fill=WHITE, edge=INK,
    lw=2.6, **T)
box(ax, X[3], PY0, W, PY1 - PY0 - 0.08, "Hash-chained\nlog", "every outcome,\nrefusals too", fill=GREY_SOFT, edge=INK,
    **T)

# bottom: simulated lenders, storage
SY0, SY1 = 0.98, 1.85
kbox(ax, X[0], SY0, W, SY1 - SY0, "Lenders", "facilities, bank", "sim")
box(ax, X[1], SY0, XR - X[1], SY1 - SY0, "Storage · app/persistence",
    "PostgreSQL (Docker, or Supabase with RLS)\nSQLite (local) · in-memory (demo, tests)", fill=WHITE, edge=INK, title_pt=15,
    body_pt=MIN_PT, gap=0.03)

# ---------------------------------------------------------------- flows
# actors <-> API
YA = (AY0 + BY1) / 2
a([(CX[0], AY0), (CX[0], BY1)], label="requests", at=(CX[0] + 0.1, YA), ha="left")
a([(X[1] + W, (AY0 + AY1) / 2), (X[2], (AY0 + AY1) / 2)], color=PURPLE)
a([(CX[2], AY0), (CX[2], BY1)], color=PURPLE)
a([(CX[3], AY0), (CX[3], BY1)], color=GREY, label="as SYSTEM", at=(CX[3] + 0.1, YA), ha="left")
# API -> the three model-assisted steps
YM = (BY0 + MY1) / 2 + 0.02
for i, lab in enumerate(["question", "chat", "text, files"]):
    a([(CX[i], BY0), (CX[i], MY1)], label=lab, at=(CX[i] + 0.1, YM), ha="left")
# model -> core: typed output only
YC = (MZ0 + CY1) / 2 + 0.05
for i, lab in enumerate(["tool + slots", "intent + slots", "typed terms"]):
    a([(CX[i], MY0), (CX[i], CY1)], color=BLUE, label=lab, at=(CX[i] + 0.1, YC), ha="left", halo=True, label_color=INK)
# inside the core
YE = 5.42
a([(X[1], YE), (X[0] + W, YE)], color=BLUE)  # engine -> tools
a([(X[1] + W, YE), (X[2], YE)], color=BLUE)  # engine -> verifier
a([(X[3], YE), (X[2] + W, YE)], color=BLUE)  # funding router -> verifier
a([(X[2] + W, 5.85), (X[3], 5.85)], color=BLUE)  # verifier -> funding router (the gap to fund)
# core -> action path, three levels in the gap between the zones
LB, LC, LA = 4.58, 4.45, 4.32
a([(X[2] + 0.3, CY0), (X[2] + 0.3, LB), (CX[0], LB), (CX[0], PY1)], color=BLUE, label="counters", at=(2.1, LB))
a([(X[1] + W - 0.25, PY1), (X[1] + W - 0.25, LA), (X[2] + 0.6, LA), (X[2] + 0.6, CY0)], color=PURPLE)  # mandate -> verifier
a([(CX[2], CY0), (CX[2], PY1)], color=INK, label="verdict", at=(CX[2] + 0.08, 4.86), ha="left")
a([(XR, (BY0 + BY1) / 2), (RBUS, (BY0 + BY1) / 2), (RBUS, LC), (X[2] + W - 0.25, LC), (X[2] + W - 0.25, PY1)], color=INK)
ax.text(RBUS, 7.6, "operations, approvals, receipts", rotation=90, ha="center", va="center", fontsize=MIN_PT, color=INK,
        zorder=5, bbox=dict(fc=WHITE, ec="none", pad=1.0))
# action path
YP = 3.1
a([(X[1] + W, YP), (X[2], YP)], color=PURPLE)  # mandate -> executor
a([(X[2] + W, YP), (X[3], YP)], color=INK)  # executor -> log
a([(X[2] + 0.3, PY0), (X[2] + 0.3, 2.1), (CX[0], 2.1), (CX[0], SY1)], color=GREY, label="draw · advance · repay",
  at=(2.55, 2.1))
a([(CX[2] + 0.2, PY0), (CX[2] + 0.2, SY1)], color=INK, label="books", at=(CX[2] + 0.28, 2.08), ha="left")
a([(CX[3], PY0), (CX[3], SY1)], color=INK, label="log", at=(CX[3] + 0.08, 2.08), ha="left")
# egress guard -> buyer, out through every boundary
a([(X[0], YP), (LBUS, YP), (LBUS, (AY0 + AY1) / 2), (X[0], (AY0 + AY1) / 2)], color=BLUE)
ax.text(LBUS, 6.0, "counter text out: to the simulated buyer, or the owner copies it", rotation=90, ha="center",
        va="center", fontsize=MIN_PT, color=INK, zorder=5, bbox=dict(fc=WHITE, ec="none", pad=1.0))

# ---------------------------------------------------------------- legend and identifier
LY = [0.66, 0.36]
items = [("model step", AMBER_SOFT, AMBER, False, 0.3, LY[0]), ("deterministic code", BLUE_SOFT, BLUE, False, 2.6, LY[0]),
         ("owner authority", PURPLE_SOFT, PURPLE, False, 5.25, LY[0]),
         ("simulated party (hatched)", GREY_SOFT, GREY, True, 0.3, LY[1])]
for text, fill, edge, hatch, x, y in items:
    ax.add_patch(FancyBboxPatch((x, y - 0.1), 0.34, 0.2, boxstyle="round,pad=0,rounding_size=0.04", fc=fill, ec=edge,
                                lw=2.0, zorder=3))
    if hatch:
        ax.add_patch(Rectangle((x, y - 0.1), 0.34, 0.2, fc="none", ec=GREY_HATCH, lw=0, hatch="//", zorder=3.5))
    ax.text(x + 0.44, y, text, va="center", fontsize=MIN_PT, color=INK)
ax.plot([3.4, 3.74], [LY[1], LY[1]], color=INK, lw=2.2, ls=(0, (6, 3)))
ax.text(3.84, LY[1], "trust boundary", va="center", fontsize=MIN_PT, color=INK)
ax.plot([5.25, 5.59], [LY[1], LY[1]], color=AMBER, lw=1.8, ls=(0, (3, 2)))
ax.text(5.69, LY[1], "redacted text to model", va="center", fontsize=MIN_PT, color=INK)
stamp(fig, f"Checked against the code on {BUILD} · synthetic data, no real money", y_in=0.03)

save(fig, "fig8-system-architecture.png")
