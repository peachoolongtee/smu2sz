"""Figure 6: reading Chinese contracts, by file format, tuned set against held-out set.

Render: uv run --no-project --with matplotlib --with pillow python fig6_contract_reading.py
Scores are answer-key fields matched (matched/key) over the text files; scans and phone photos are refused before any model
call (SCANNED_PDF: no OCR), so they score 0. Sources (session scratchpad of 16-17 Oct 2026, not in the repo):
- batch 1, CN-001..CN-040, tuned on: b2fix/b1-redact.log "By format" ALL row:
  pdf_digital (18 files) 310/314 99%, docx_draft (12) 192/200 96%; all 30 text files 502/514 98%; 10 scans refused;
  no phone photos in batch 1;
- batch 2, CN-041..CN-070, held out, before the fixes: contract-cn2/ run of 16 Oct (mismatches.csv: pdf_digital 40 keys
  missed of 178, docx_draft 30 of 107; 66 scan keys and 91 photo keys "OCR needed"), the same as b2fix/b2-base.log ALL rows:
  pdf_digital (10) 138/178 78%, docx_draft (7) 77/107 72%; all 17 text files 215/285 75%;
  6 scans and 7 phone photos refused (contract-cn2/README.md, formats pdf:10 scan:6 docx:7 photo:7);
- batch 2 after the fixes (no longer held out): b2fix/b2-redact.log ALL rows: pdf_digital 161/178 90%, docx_draft 85/107 79%;
  all 17 text files 246/285 86%.
"""

import matplotlib.pyplot as plt
import numpy as np

from flowstyle import BLUE, DPI, GREY, INK, INK_2, PURPLE, PURPLE_SOFT, WIDTH_IN, save

FORMATS = ["Digital PDF\n数字 PDF", "Word draft\nWord 草稿", "Scanned PDF\n扫描件", "Phone photo\n手机拍照", "All text\nfiles"]
# (matched, key) or None; batch 1 tuned, batch 2 held out before fixes, batch 2 after fixes
B1 = [(310, 314), (192, 200), "refused", None, (502, 514)]
B2_HELD = [(138, 178), (77, 107), "refused", "refused", (215, 285)]
B2_FIX = [(161, 178), (85, 107), "refused", "refused", (246, 285)]
FILES = ["18 · 10", "12 · 7", "10 · 6", "0 · 7", "30 · 17"]  # files in batch 1 · batch 2

SERIES = [("Batch 1 (tuned on)", B1, dict(color=PURPLE)),
          ("Batch 2, held out (before fixes)", B2_HELD, dict(color=BLUE)),
          ("Batch 2 after fixes (no longer held out)", B2_FIX, dict(color=PURPLE_SOFT, edgecolor=PURPLE, hatch="///",
                                                                    linewidth=1.5))]

fig = plt.figure(figsize=(WIDTH_IN, 6.6), dpi=DPI)
ax = fig.add_axes((0.125, 0.25, 0.86, 0.57))
x = np.arange(len(FORMATS))
w = 0.27
plt.rcParams["hatch.color"] = PURPLE
for i, (name, vals, style) in enumerate(SERIES):
    for j, v in enumerate(vals):
        xx = x[j] + (i - 1) * w
        if isinstance(v, tuple):
            p = 100 * v[0] / v[1]
            ax.bar(xx, p, w * 0.92, **style, label=name if j == 0 else None)
            ax.text(xx, p + 2, f"{p:.0f}", ha="center", va="bottom", fontsize=13.5, color=INK)
        elif v == "refused":
            ax.bar(xx, 0.8, w * 0.92, color=style.get("edgecolor", style["color"]))
            ax.text(xx, 3, "0", ha="center", va="bottom", fontsize=13.5, color=INK)
        else:
            ax.text(xx, 3, "–", ha="center", va="bottom", fontsize=13.5, color=INK_2)
ax.text(2.45, 40, "refused before any model call:\nno OCR for scans or photos", ha="center", va="center", fontsize=14,
        color=INK, linespacing=1.25)
ax.axvline(3.5, color=GREY, lw=1.2, ls=(0, (2, 3)))
ax.set_xticks(x)
ax.set_xticklabels(FORMATS, fontsize=14, linespacing=1.15)
ax.set_xlim(-0.55, 4.55)
ax.set_ylim(0, 112)
ax.set_yticks([0, 25, 50, 75, 100])
ax.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
ax.set_ylabel("fields read correctly")
ax.grid(axis="y", color="#e6e9ef", lw=1.0)
ax.set_axisbelow(True)
for j, f in enumerate(FILES):
    ax.text(x[j], -0.215, f, transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=13.5, color=INK_2)
fig.text(0.015, 0.03, "Files per format, batch 1 · batch 2 (shown under each label)", fontsize=13.5, color=INK_2,
         va="center")
ax.legend(loc="lower left", bbox_to_anchor=(-0.1, 1.03), ncol=1, frameon=False, fontsize=14, handlelength=1.6,
          labelspacing=0.3)

save(fig, "fig6-contract-reading.png")
