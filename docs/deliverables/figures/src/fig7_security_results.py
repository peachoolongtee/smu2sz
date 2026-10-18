"""Figure 7: the attack catalogue, 279 stored cases by class, no harm-oracle violation.

Render: uv run --no-project --with matplotlib --with pillow python fig7_security_results.py
Source: services/api/evals/security/latest_report.json (regenerated on the round-five batch, int/round-five `0ff5b0d5`,
18 Oct 2026; a re-run on `1294e941` gives the same metrics and the same outcome for every case), read here directly:
`attacks` (128 through the API) and `nl_attacks` (151 through POST /nl as the owner, a buyer and the agent key). Each
case's `harm` field is used as recorded. The subtitle states the report's own measure: all 279 cases reach the path they
target, and of the 128 API cases 120 are stopped by the control they name and 8 by another control (known gaps, SEC-34).

Classes (the report's categories, grouped; the API grouping is the report's own "attack success rate" table):
- injection: prompt_injection, fake_lender, fake_prior_concession, social_engineering, nl_counterparty_injection,
  nl_owner_quoting_buyer
- exfiltration: mandate_exfiltration, reserve_facility_exfiltration, cross_buyer, canary_extraction,
  nl_counterparty_extraction, nl_oracle_probing
- escalation: privilege_escalation, nl_agent_channel
- replay: replay, expired_commitment, revoked_mandate, changed_offer, nl_replay_session
- consent: nl_owner_consent (negated, conditional or malformed instructions: the right result is that nothing runs;
  since round five also NL-TQ01..18, Tier-3 requests put as questions, which must be refused and logged)
- failure recovery: failure_recovery (partial writes, double execution, log integrity)
"""

import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

from flowstyle import BLUE, BLUE_SOFT, DPI, GREY, INK, INK_2, WIDTH_IN, save

REPORT = Path(__file__).resolve().parents[4] / "services/api/evals/security/latest_report.json"
CLASS = {
    "prompt_injection": "Injection", "fake_lender": "Injection", "fake_prior_concession": "Injection",
    "social_engineering": "Injection", "nl_counterparty_injection": "Injection", "nl_owner_quoting_buyer": "Injection",
    "mandate_exfiltration": "Exfiltration", "reserve_facility_exfiltration": "Exfiltration", "cross_buyer": "Exfiltration",
    "canary_extraction": "Exfiltration", "nl_counterparty_extraction": "Exfiltration", "nl_oracle_probing": "Exfiltration",
    "privilege_escalation": "Escalation", "nl_agent_channel": "Escalation",
    "replay": "Replay", "expired_commitment": "Replay", "revoked_mandate": "Replay", "changed_offer": "Replay",
    "nl_replay_session": "Replay",
    "nl_owner_consent": "Consent",
    "failure_recovery": "Failure recovery",
}
ORDER = ["Injection", "Exfiltration", "Escalation", "Replay", "Consent", "Failure recovery"]

rep = json.loads(REPORT.read_text(encoding="utf-8"))
n, det, harm, api, chat = Counter(), Counter(), Counter(), Counter(), Counter()
for key, entry in (("attacks", api), ("nl_attacks", chat)):
    for a in rep[key]:
        c = CLASS[a["category"]]  # a category not in the map fails loudly
        n[c] += 1
        entry[c] += 1
        det[c] += bool(a["detected"])
        harm[c] += bool(a["harm"])
total, total_det, total_harm = sum(n.values()), sum(det.values()), sum(harm.values())
api_n, api_det = len(rep["attacks"]), sum(bool(a["detected"]) for a in rep["attacks"])
api_def = sum(bool(a["defended"]) for a in rep["attacks"])
reached = sum(bool(a["reached"]) for key in ("attacks", "nl_attacks") for a in rep[key])
for c in ORDER:
    print(f"{c:<17} {n[c]:>3} (API {api[c]:>3}, chat {chat[c]:>3})  detected {det[c]:>3}  harm {harm[c]}")
print(f"total {total}, detected {total_det} ({100 * total_det / total:.1f}%), harm {total_harm}; "
      f"API {api_n}, detected {api_det} ({100 * api_det / api_n:.1f}%)")
assert total == 279 and api_n == 128 and api_det == 125 and total_harm == 0, "the report changed: update the figure's text"
assert reached == total and api_def == 120, "the subtitle's reached / stopped-by-the-named-control figures changed"

fig = plt.figure(figsize=(WIDTH_IN, 5.5), dpi=DPI)
ax = fig.add_axes((0.255, 0.215, 0.6, 0.535))
ys = list(range(len(ORDER)))[::-1]
for y, c in zip(ys, ORDER):
    ax.barh(y, n[c], color=BLUE, height=0.62)
    ax.text(n[c] + 1.5, y, f"{n[c]}", va="center", fontsize=14, color=INK, fontweight="bold")
ax.set_yticks(ys)
ax.set_yticklabels([f"{c}\nAPI {api[c]} · chat {chat[c]}" for c in ORDER], fontsize=14, linespacing=1.15)
for lab in ax.get_yticklabels():
    lab.set_color(INK)
ax.set_xlim(0, 85)
ax.set_xticks([0, 20, 40, 60, 80])
ax.set_xlabel("attacks")
ax.tick_params(axis="y", length=0)
ax.spines["left"].set_visible(False)
ax.grid(axis="x", color="#e6e9ef", lw=1.0)
ax.set_axisbelow(True)

# the harm column
hx = 0.925
fig.text(hx, 0.765, "harm", ha="center", va="bottom", fontsize=14, fontweight="bold", color=INK)
for y, c in zip(ys, ORDER):
    yf = ax.transData.transform((0, y))[1] / fig.bbox.height
    fig.text(hx, yf, str(harm[c]), ha="center", va="center", fontsize=15, fontweight="bold", color=INK)

# headline and legend
fig.text(0.015, 0.96, f"{total} attack cases ({api_n} API, {total - api_n} chat): {total_harm} with harm",
         fontsize=16, fontweight="bold", color=INK, va="center")
fig.text(0.015, 0.915, "Every case reached the path it targets. Of the 128 API cases, 120 were stopped" + chr(10) + "by the control they name and 8 by another control (known gaps, SEC-34).",
         fontsize=13.5, color=INK_2, va="top", linespacing=1.25)
save(fig, "fig7-security-results.png")
