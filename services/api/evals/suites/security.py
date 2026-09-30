"""Security (E4/E7): a summary of services/api/evals/security/latest_report.json (written by
`uv run python -m app.security.attacks --report`). Not re-implemented here; this suite only reads it,
cross-checks it against the attack catalogue and the per-attack rows, and flags staleness."""

from __future__ import annotations

import json
from typing import Any

import yaml

from evals.common import EVALS, Failure, Metric, SuiteResult

REPORT = EVALS / "security" / "latest_report.json"
CATALOGUE = EVALS / "security" / "attacks.yaml"
REPRO = "cd services/api && uv run python -m app.security.attacks --report"


def run(**_: Any) -> SuiteResult:
    res = SuiteResult(name="security")
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    m = rep["metrics"]
    attacks = rep.get("attacks", [])
    cat = yaml.safe_load(CATALOGUE.read_text(encoding="utf-8"))
    cat_items = cat.get("attacks", cat) if isinstance(cat, dict) else cat
    cat_ids = {a["id"] for a in cat_items} if isinstance(cat_items, list) else set()
    rep_ids = {a["id"] for a in attacks}
    unauth_rows = sum(a.get("unauthorised_ops", 0) for a in attacks)
    harm = m["all_attacks_metrics"]
    unauth = max(harm["unauthorised_operations_executed"], unauth_rows)
    stale = sorted(cat_ids ^ rep_ids)
    res.details = {"llm_mode": rep.get("llm_mode"), "attacks": len(attacks), "catalogue": len(cat_ids),
                   "missing_from_report": sorted(cat_ids - rep_ids), "not_in_catalogue": sorted(rep_ids - cat_ids),
                   "harm": harm, "per_category": m.get("per_category", []), "outcomes": m.get("outcomes"),
                   "detection_rate": m.get("detection_rate"), "security_event_rate": m.get("security_event_rate"),
                   "text_attack_compiler_flag_rate": m.get("text_attack_compiler_flag_rate")}

    def rate(key: str, label: str, target: str = "0%") -> Metric:
        r = m[f"{key}_success_rate_incl_findings"]
        n = m[f"{key}_attempts_incl_findings"]
        return Metric(f"{key}_success_rate", f"{label} success rate", r, f"{r:.1%} of {n}", target, r == 0, "security")

    res.metrics += [
        rate("injection", "Injection"),
        rate("exfiltration", "Exfiltration"),
        rate("escalation", "Escalation"),
        rate("replay", "Replay"),
        Metric("unauthorised_operations", "Unauthorised operation count (all attacks)", unauth, str(unauth), "0",
               unauth == 0, "security"),
        Metric("attacks_with_harm", "Attacks with any harm (money, facility, disclosure, integrity)",
               harm["attacks_with_harm"], f"{harm['attacks_with_harm']}/{len(attacks)}", "0",
               harm["attacks_with_harm"] == 0, "security"),
        Metric("security_detection_rate", "Attacks detected (SecurityEvent or refusal code)", m.get("detection_rate"),
               f"{m.get('detection_rate', 0):.1%}", "informational", None, "security",
               f"security-event rate {m.get('security_event_rate', 0):.1%}"),
    ]
    if stale:
        res.failures.append(Failure("security", "stale_report",
                                    f"the security report and attacks.yaml disagree on {len(stale)} attack ids: "
                                    f"{stale[:8]}", REPRO))
    for a in attacks:
        if a.get("unauthorised_ops") or a.get("money_moved_fen") or a.get("facilities_added"):
            res.failures.append(Failure("security", a["id"], f"{a['id']} {a.get('title')}: harm recorded", REPRO, a))
    return res
