"""Shared style for FLOW's document figures (docs/deliverables/figures).

Every figure is 8 in wide at 300 dpi (2400 px). The document embeds it at 6.5 in, a scale of 0.8125, so the smallest
font here (MIN_PT = 13.5) prints at 11 pt. The palette is the FLOW brand (apps/web/app/globals.css): brand blue
--color-brand-600, ink --color-ink, purple --color-f-purple, amber --color-warn-solid and the neutral --color-line-ui.
Blue / amber / purple / grey stay distinct under deuteranopia, protanopia and tritanopia; no red-green pair is used.

Fonts: Microsoft YaHei (C:/Windows/Fonts/msyh.ttc), which has the Chinese glyphs; Noto Sans SC is the fallback.
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

OUT = Path(__file__).resolve().parents[1]  # docs/deliverables/figures
WIDTH_IN, DPI = 8.0, 300
MIN_PT = 13.5  # 11 pt at the document's 6.5 in
BODY_PT, TITLE_PT, HEAD_PT = 14, 16, 17

# FLOW brand (apps/web/app/globals.css)
BLUE = "#0368e9"  # --color-brand-600
BLUE_DEEP = "#0048a5"  # --color-brand-700
BLUE_SOFT = "#e6f1ff"  # --color-brand-50
INK = "#24324a"  # --color-ink / --color-brand-900
INK_2 = "#4d5767"  # --color-ink-2
PURPLE = "#9252dc"  # --color-f-purple
PURPLE_SOFT = "#ebdefa"  # --color-f-purple-soft
PURPLE_INK = "#4a2480"  # --color-f-purple-ink
AMBER = "#b7791f"  # --color-warn-solid
AMBER_INK = "#82490a"  # --color-warn-fg
AMBER_SOFT = "#fdf2d9"  # --color-warn-bg
GREY = "#768399"  # --color-line-ui
GREY_SOFT = "#eff3f8"  # --color-subtle
WHITE = "#ffffff"


def _font() -> str:
    candidates = [("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"),
                  ("C:/Windows/Fonts/NotoSansSC-VF.ttf", None),
                  ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")]
    for regular, bold in candidates:
        if os.path.exists(regular):
            fm.fontManager.addfont(regular)
            if bold and os.path.exists(bold):
                fm.fontManager.addfont(bold)
            return fm.FontProperties(fname=regular).get_name()
    raise SystemExit("no CJK-capable font found (Microsoft YaHei or Noto Sans CJK)")


FONT = _font()
plt.rcParams.update({
    "font.family": FONT, "font.size": BODY_PT, "axes.unicode_minus": False,
    "axes.edgecolor": GREY, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK, "text.color": INK,
    "axes.titlesize": TITLE_PT, "axes.labelsize": BODY_PT, "xtick.labelsize": BODY_PT, "ytick.labelsize": BODY_PT,
    "legend.fontsize": BODY_PT, "figure.facecolor": WHITE, "axes.facecolor": WHITE, "savefig.facecolor": WHITE,
    "axes.spines.top": False, "axes.spines.right": False,
})


def canvas(height_in: float):
    """A diagram canvas in inches: x 0..8, y 0..height_in, no axes."""
    fig = plt.figure(figsize=(WIDTH_IN, height_in), dpi=DPI)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, WIDTH_IN)
    ax.set_ylim(0, height_in)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, title, body=None, *, fill=BLUE_SOFT, edge=BLUE, ink=INK, title_pt=TITLE_PT, body_pt=BODY_PT,
        lw=2.0, align="center", gap=0.07):
    """A rounded box with a bold title and optional body lines, centred vertically."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08", fc=fill, ec=edge, lw=lw, zorder=3))
    lines_t = title.count("\n") + 1
    lines_b = 0 if not body else body.count("\n") + 1
    lh_t, lh_b = title_pt * 1.25 / 72, body_pt * 1.25 / 72
    total = lines_t * lh_t + (gap + lines_b * lh_b if body else 0)
    top = y + h / 2 + total / 2
    tx = x + w / 2 if align == "center" else x + 0.12
    ax.text(tx, top, title, ha=align, va="top", fontsize=title_pt, fontweight="bold", color=ink, zorder=4, linespacing=1.25)
    if body:
        ax.text(tx, top - lines_t * lh_t - gap, body, ha=align, va="top", fontsize=body_pt, color=ink, zorder=4,
                linespacing=1.25)


def zone(ax, x, y, w, h, label, color, *, label_side="top", pt=BODY_PT):
    """A dashed trust boundary with its label on a white tab."""
    ax.add_patch(Rectangle((x, y), w, h, fill=False, ec=color, lw=2.2, ls=(0, (6, 3)), zorder=1))
    ly = y + h if label_side == "top" else y
    ax.text(x + 0.12, ly, " " + label + " ", ha="left", va="center", fontsize=pt, fontweight="bold", color=color, zorder=5,
            bbox=dict(fc=WHITE, ec="none", pad=1.5))


def arrow(ax, pts, color=INK, lw=2.2, label=None, label_xy=None, label_pt=BODY_PT, ha="center", va="center", style="-|>",
          dashed=False, label_color=None):
    """A polyline arrow through `pts` (orthogonal elbows), head at the last point."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if len(pts) > 2:
        ax.plot(xs[:-1], ys[:-1], color=color, lw=lw, zorder=2, solid_capstyle="butt", ls="--" if dashed else "-")
    ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle=style, mutation_scale=22, color=color, lw=lw, zorder=2,
                                 shrinkA=0, shrinkB=0, ls="--" if dashed else "-"))
    if label:
        ax.text(*label_xy, label, ha=ha, va=va, fontsize=label_pt, color=label_color or color, zorder=5, linespacing=1.2,
                bbox=dict(fc=WHITE, ec="none", pad=1.0))


def save(fig, name: str) -> Path:
    path = OUT / name
    fig.savefig(path, dpi=DPI, facecolor=WHITE)
    plt.close(fig)
    from PIL import Image

    with Image.open(path) as im:
        print(f"{path.name}: {im.size[0]}x{im.size[1]} px")
    return path


# ---------------------------------------------------------------- shared helpers added for the submission figures (18 Oct 2026)
# Non-colour channels: every category below also has a shape, a pattern or a word, so a figure printed in grey still reads.

BUILD = "docs/techdoc-chat-fixes @ 571ea64f"  # the build the submission figures were checked against
BUILD_FINAL = "int/final3 @ 2ce5265c"  # the submission build candidate (figures and screens refreshed 18 Oct 2026)
GREY_HATCH = "#b9c2d0"  # the hatch lines of a simulated party

# Kinds of component or step. `tag` is the word printed on the box's top edge; `hatch` marks the simulated parties.
KINDS = {
    "model": dict(fill=AMBER_SOFT, edge=AMBER, ink=AMBER_INK, tag="MODEL-ASSISTED", hatch=None),
    "code": dict(fill=BLUE_SOFT, edge=BLUE, ink=INK, tag=None, hatch=None),
    "owner": dict(fill=PURPLE_SOFT, edge=PURPLE, ink=PURPLE_INK, tag="OWNER", hatch=None),
    "sim": dict(fill=GREY_SOFT, edge=GREY, ink=INK, tag="SIMULATED", hatch="//"),
    "store": dict(fill=WHITE, edge=INK, ink=INK, tag=None, hatch=None),
}
TAG_PT = 11  # the word tag on a box edge; it repeats the legend, so it may sit below MIN_PT


def kbox(ax, x, y, w, h, title, body=None, kind="code", *, tag=True, title_pt=15, body_pt=MIN_PT, **kw):
    """A component box of one KINDS kind: its fill, edge, hatch (simulated) and word tag on the top edge."""
    k = KINDS[kind]
    if k["hatch"]:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08", fc=k["fill"], ec=GREY_HATCH,
                                    lw=0, hatch=k["hatch"], zorder=2.5))
        box(ax, x, y, w, h, title, body, fill="none", edge=k["edge"], ink=k["ink"], title_pt=title_pt, body_pt=body_pt, **kw)
    else:
        box(ax, x, y, w, h, title, body, fill=k["fill"], edge=k["edge"], ink=k["ink"], title_pt=title_pt, body_pt=body_pt,
            **kw)
    if tag and k["tag"]:
        ax.text(x + w - 0.1, y + h, k["tag"], ha="right", va="center", fontsize=TAG_PT, fontweight="bold",
                color=k["ink"], zorder=6,
                bbox=dict(boxstyle="round,pad=0.2,rounding_size=0.12", fc=WHITE, ec=k["edge"], lw=1.4))


def stamp(fig, text: str, *, y_in: float = 0.08):
    """The build / scenario identifier, bottom left."""
    h = fig.get_size_inches()[1]
    fig.text(0.08 / WIDTH_IN, y_in / h, text, ha="left", va="bottom", fontsize=12, color=INK_2)


# ---------------------------------------------------------------- charts
# For data figures (for example the financial chart of docs/sub-financial-audit): call chart(), plot each series with
# **SERIES[i] (colour + marker + line style, so series never differ by colour alone), format money with yuan / yuan_k,
# put the unit in the axis label, and stamp() the build and scenario. Example:
#
#     from flowstyle import BUILD, SERIES, chart, save, stamp, yuan_k
#     fig, ax = chart(5.2, xlabel="day of the scenario", ylabel="closing cash (¥ thousand)")
#     ax.plot(days, plan_k, label="with FLOW's plan", **SERIES[0])
#     ax.plot(days, cash_k, label="no new funding", **SERIES[1])
#     ax.yaxis.set_major_formatter(yuan_k)
#     ax.legend(frameon=False)
#     stamp(fig, "Golden books (synthetic) · GET /home · " + BUILD)
#     save(fig, "fig8-name.png")

SERIES = [
    dict(color=BLUE, marker="o", ls="-", lw=3.0, ms=6, markevery=5),
    dict(color=AMBER, marker="s", ls=(0, (6, 2.5)), lw=3.0, ms=6, markevery=5),
    dict(color=PURPLE, marker="^", ls=(0, (2, 1.6)), lw=3.0, ms=7, markevery=5),
    dict(color=GREY, marker="D", ls=(0, (6, 2, 1.5, 2)), lw=2.6, ms=6, markevery=5),
]
BAR_HATCHES = ["", "//", "..", "xx"]  # bars: pair with the SERIES colours so a grey print still separates them

from matplotlib.ticker import FuncFormatter  # noqa: E402


def _yuan(v: float, unit: str) -> str:
    return ("−" if v < 0 else "") + "¥" + f"{abs(v):,.0f}" + unit


yuan = FuncFormatter(lambda v, _p: _yuan(v, ""))  # tick values in yuan
yuan_k = FuncFormatter(lambda v, _p: _yuan(v, "k"))  # tick values in thousands of yuan


def chart(height_in: float, *, xlabel: str | None = None, ylabel: str | None = None, rect=(0.12, 0.16, 0.85, 0.78)):
    """A data chart 8 in wide in the house style: light horizontal grid, no top/right spines, units in the axis labels."""
    fig = plt.figure(figsize=(WIDTH_IN, height_in), dpi=DPI)
    ax = fig.add_axes(rect)
    ax.grid(axis="y", color="#e6e9ef", lw=1.0, zorder=0)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    return fig, ax
