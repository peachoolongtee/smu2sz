"""Cut the product screenshots for the document. Render:
uv run --no-project --with pillow python crop_screens.py <raw dir from capture_screens.mjs>

Each frame is a crop of a 1440x900 capture (device scale 2, so 2 image px per CSS px) with numbered callouts and a legend band
underneath, in the style of docs/deliverables/screenshots (orange #E8590C filled circles). The legend's text is sized so it prints
at about 9 pt or more when the frame is embedded at 6.4 in. `screens/<name>.png` is annotated, `screens/<name>-raw.png` is the same
crop without annotations. Crop boxes and callout points are CSS px of the full-page capture.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAW = Path(sys.argv[1])
OUT = Path(__file__).resolve().parents[1] / "screens"
OUT.mkdir(exist_ok=True)
S = 2  # device scale
ORANGE = "#E8590C"
INK = "#24324a"
INK_2 = "#4d5767"
FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"
SCENARIO = "Mock mode, golden books (synthetic), docs/techdoc-chat-fixes @ 571ea64f, captured 18 Oct 2026 at 1440×900"

# name: (source file, crop box in CSS px (x0, y0, x1, y1), [(callout x, y in CSS px, legend text)])
FRAMES = {
    "screen1-home": ("01-home.png", (84, 136, 1412, 690), [
        (335, 226, "Without new funding, cash falls to −¥105,000 within 30 days."),
        (1392, 172, "The red recommendation card: action needed before payroll."),
        (1120, 308, "Secure ¥405,000 (credit line ¥150,000 today, invoice financing ¥255,000 in 3 days)."),
        (1205, 318, "What the plan costs: ¥3,113.93."),
        (1098, 547, "Inside the signed limits: no approval needed."),
    ]),
    "screen2-deal-verdict": ("02-deal-verdict.png", (150, 155, 1345, 1368), [
        (1215, 470, "FLOW's verdict: counter with Option A (45 days, early settlement at 0.85%)."),
        (360, 709, "Why not accept as asked: the reserve is breached by ¥135k for 15 days."),
        (1185, 636, "Within the signed mandate: no approval needed for Option A."),
        (715, 870, "Nothing is sent until the owner reviews and sends it."),
        (335, 982, "The priced choices side by side: as asked, Option A, Option B."),
    ]),
    "screen3-cash-plan": ("03-cash-plan.png", (225, 813, 1270, 1521), [
        (520, 870, "The plan: secure ¥405k from the credit line and invoice financing."),
        (880, 862, "Estimated cost ¥3,113.93, within the signed limits."),
        (1085, 891, "Run funding plan: one press opens the confirmation."),
        (898, 1482, "Without new funding cash falls to −¥105k; the plan keeps it at ¥300k or more."),
    ]),
    "screen4-ask-answer": ("04-ask-answer.png", (366, 96, 1134, 858), [
        (985, 328, "The owner's question."),
        (410, 382, "The answer leads, worked out from the books by code."),
        (1095, 452, "Three key figures, each a server value."),
        (760, 550, "Links to the forecast and the plan; nothing is acted on."),
    ]),
    "screen5-documents": ("05-documents-reading-viewport.png", (86, 78, 1390, 700), [
        (870, 412, "A term the agent read (Price), with its clause number and exact words."),
        (138, 506, "The focused term lights its clause in the contract text."),
        (240, 214, "Numbered markers: which terms each clause holds."),
    ]),
    "screen6-deal-tracker": ("06-deal-tracker.png", (70, 240, 1410, 1130), [
        (760, 352, "The agreed deal, on plan: the early part was paid."),
        (1112, 468, "Stages: read, negotiated, early payment in, collecting."),
        (330, 670, "Cost expected when agreed against the actual so far."),
        (565, 861, "Each cost line with how sure it is and its evidence."),
    ]),
    "screen7-activity": ("07-activity.png", (78, 218, 1417, 1118), [
        (1192, 252, "Record chain checks passed: the hash chain verifies."),
        (795, 770, "A Tier 2 request: 32.5% a year is above the 15% ceiling, so the owner decided."),
        (545, 985, "The log entry: its hash and the previous entry's hash."),
        (222, 1028, "The audit sentence the executor wrote."),
    ]),
}


# The submission refresh: `python crop_screens.py <raw dir> final` cuts the frames of `SET=final capture_screens.mjs`, taken from the
# build candidate int/final3 @ 2ce5265c. They replace the old docs/deliverables/screenshots frames of the same names.
if len(sys.argv) > 2 and sys.argv[2] == "final":
    SCENARIO = "Mock mode, golden books (synthetic), int/final3 @ 2ce5265c, captured 18 Oct 2026 at 1440×900"
    FRAMES = {
        "shot1-home": ("08-home.png", (84, 136, 1412, 690), [
            (330, 230, "Without new funding, cash falls to −¥105,000 within 30 days; with the plan it stays at ¥300,000."),
            (1392, 172, "The red card: action needed before payroll in 12 days."),
            (1120, 308, "The recommendation: secure ¥405,000."),
            (1205, 318, "What the plan costs: ¥3,113.93."),
            (1228, 461, "The split: credit line ¥150,000 today, invoice financing ¥255,000 in 3 days."),
            (1098, 547, "Inside the signed limits: no approval needed."),
        ]),
        "shot3-approval": ("09-approval.png", (84, 228, 870, 1010), [
            (644, 374, "Waiting for the owner's approval: the funding request is queued, not run."),
            (730, 491, "Why it needs the owner: 32.5% a year is above the 15% ceiling the owner signed."),
            (490, 551, "What it costs: ¥1,782.19 for ¥200,000."),
            (814, 888, "What a decline means: ¥200,000 below the reserve in 8 days."),
            (454, 966, "Nothing runs until the owner authorizes or declines."),
        ]),
        "shot6-capex": ("10-capex-quick.png", (84, 665, 1412, 1690), [
            (1398, 757, "The verdict: worth doing on the owner's estimate; finance with the 36-month term loan (Tier 2)."),
            (415, 895, "Key figures: NPV ¥380,885.77, payback in month 31, leverage 2.28× against a 2.50× limit."),
            (302, 1132, "A figure that does not apply reads \"—\", not \"None\": cash + credit line is infeasible."),
            (1302, 1230, "DSCR month by month: the 18-month loan fails months 1–3 (1.09× below 1.25×)."),
            (289, 1414, "Selected: the lowest total charges among the structures that hold every covenant."),
        ]),
        "shot9-attach": ("11-documents-attach.png", (84, 86, 1412, 975), [
            (191, 271, "What the file is: here, a contract with a buyer."),
            (900, 342, "Who it is with: a known customer, or add a new one."),
            (936, 475, "Drop a signed contract or lender agreement: PDF with text, Word or plain text, up to 5 MB."),
            (828, 555, "Upload and read: the agent reads the terms; nothing changes until the owner confirms them."),
            (1318, 803, "Documents already read, each confirmed by the owner."),
        ]),
        "shot10-ask-answer": ("12-ask-answer.png", (360, 92, 1138, 864), [
            (986, 329, "The owner's question (a recorded one)."),
            (403, 425, "The answer leads, worked out from the books by code."),
            (1098, 428, "Three key figures, each a server value."),
            (763, 550, "The plan's cost and links to the forecast and the plan; the answer acts on nothing."),
            (626, 596, "How FLOW worked this out: the reads behind the answer."),
            (1116, 670, "Suggested questions."),
        ]),
    }


def font(px: int, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, px)


def wrap(draw, text, f, width):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


for name, (src, (x0, y0, x1, y1), calls) in FRAMES.items():
    im = Image.open(RAW / src).convert("RGB")
    crop = im.crop((x0 * S, y0 * S, x1 * S, y1 * S))
    crop.save(OUT / f"{name}-raw.png", optimize=True)
    w, h = crop.size
    ann = crop.copy()
    d = ImageDraw.Draw(ann)
    r = 30
    fn = font(34, bold=True)
    for i, (cx, cy, _t) in enumerate(calls, 1):
        px, py = (cx - x0) * S, (cy - y0) * S
        d.ellipse((px - r, py - r, px + r, py + r), fill=ORANGE, outline="white", width=4)
        d.text((px, py + 1), str(i), font=fn, fill="white", anchor="mm")
    # legend band: about 9 pt at 6.4 in
    lp = max(30, round(w / 6.4 * 9.5 / 72))
    fl, fs = font(lp), font(round(lp * 0.8))
    pad = round(lp * 0.8)
    meas = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    rows = []
    for i, (_x, _y, t) in enumerate(calls, 1):
        rows.append((i, wrap(meas, t, fl, w - 2 * pad - 2.2 * lp)))
    lh = round(lp * 1.35)
    band_h = pad + sum(len(ls) * lh + round(lp * 0.25) for _, ls in rows) + round(lp * 0.2) + round(lp * 1.2) + pad
    out = Image.new("RGB", (w, h + band_h), "white")
    out.paste(ann, (0, 0))
    d = ImageDraw.Draw(out)
    d.line((0, h, w, h), fill="#c9d1dd", width=3)
    y = h + pad
    for i, ls in rows:
        cr = round(lp * 0.55)
        cx, cy = pad + cr, y + lh // 2
        d.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=ORANGE)
        d.text((cx, cy + 1), str(i), font=font(round(lp * 0.75), bold=True), fill="white", anchor="mm")
        for k, line in enumerate(ls):
            d.text((pad + 2.2 * lp, y + k * lh + lh // 2), line, font=fl, fill=INK, anchor="lm")
        y += len(ls) * lh + round(lp * 0.25)
    d.text((pad, y + round(lp * 0.2) + round(lp * 0.6)), SCENARIO, font=fs, fill=INK_2, anchor="lm")
    out.save(OUT / f"{name}.png", dpi=(300, 300), optimize=True)
    print(name, out.size)
