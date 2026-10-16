"""Execution evidence for judges (template: timestamp, action, result, screenshot/link).

JSONL records, in order:
  run            - topic, scenario, fixture + mandate hashes, LLM mode, git sha, wall-clock start
  operation      - every executed / refused / pending / duplicate operation (hash-chained)
  security_event - every refusal-worthy event (unknown lender, data extraction, ...)
  chain          - chain_valid, head_hash
Wall-clock `recorded_at` lives only in the run header, outside every hash, so a replay of the
same scenario reproduces the same head hash (docs/adr/0004-evidence-export.md).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime

from app.api.runtime import Runtime
from app.domain.fixtures import FIXTURES
from app.persistence import canonical_json
from app.persistence.chain import chain_line, evidence_line


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=2, check=True).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def build(rt: Runtime, screenshots: dict[str, str] | None = None) -> str:
    ops = rt.store.operations()
    mandate = rt.store.get_mandate()
    header = {
        "record": "run",
        "competition": "FinTechathon 2026, International track, Topic E (SME Finance Copilot)",
        "project": "TermsLedger v2",
        "scenario": rt.scenario,
        # Books the owner opened at setup have no fixture file; their hash is in the chain's OPEN_BOOKS entry.
        "scenario_sha256": _sha(p) if (p := FIXTURES / "scenarios" / f"{rt.scenario}.json").is_file() else None,
        "offers_sha256": _sha(FIXTURES / "offers" / "offers.yaml"),
        "mandate_version": mandate.version,
        "mandate_signature": mandate.signature_hex,
        "llm_mode": rt.settings.llm_mode,
        "git_sha": _git_sha(),
        "simulated_day": rt.day,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "verify": "python scripts/verify_evidence.py <file.jsonl>",
    }
    lines = [canonical_json(header)]
    for e in ops:
        line = evidence_line(e)
        if screenshots and e.op_id in screenshots:
            line["screenshot"] = screenshots[e.op_id]
        lines.append(canonical_json(line))
    for ev in rt.store.security_events():
        d = json.loads(ev.model_dump_json())
        lines.append(canonical_json({"record": "security_event", **d}))
    lines.append(canonical_json(chain_line(ops)))
    return "\n".join(lines) + "\n"
