"""The offline evidence verifier (scripts/verify_evidence.py), after the external review of the self-assessment (17 Oct): it recomputed
the chain but believed the readable fields beside it, ignored the chain line's count, crashed on a missing key, and had no way to tell a
consistently cut-short, rolled-back or rewritten file from the real one. It now checks those fields and the count, reports instead of
crashing, and verifies a file against a checkpoint kept outside the system."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "verify_evidence.py"
OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Owner-Token": "", "X-Agent-Key": "demo-agent-key"}


def op(kind: str, key: str, **kw) -> dict:
    return {"kind": kind, "op_id": key, "idempotency_key": key, "mandate_version": 1, "requested_by": "AGENT", **kw}


@pytest.fixture
def lines(tmp_path) -> list[dict]:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    c = TestClient(app)
    for i in range(3):
        c.post("/operations", json=op("DRAW_FACILITY", f"ev-{i}", facility_id="FAC-LINE", amount_fen=1_000_000), headers=AGENT)
    c.post("/operations", json=op("SIGN_PERSONAL_GUARANTEE", "ev-t3", facility_id="FAC-LINE"), headers=AGENT)
    text = c.get("/evidence", headers=OWNER).text
    set_runtime(None)
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def run(tmp_path: Path, lines: list[dict], *args: str) -> subprocess.CompletedProcess:
    f = tmp_path / "ev.jsonl"
    f.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), str(f), *args], capture_output=True, text=True, check=False)


def ops(lines: list[dict]) -> list[dict]:
    return [x for x in lines if x.get("record") == "operation"]


def chain(lines: list[dict]) -> dict:
    return next(x for x in lines if x.get("record") == "chain")


def rehash(lines: list[dict]) -> None:
    """What a database owner would do: recompute every link after a change, and the chain line with it."""
    prev = "0" * 64
    for i, o in enumerate(ops(lines), 1):
        o["seq"], o["prev_hash"] = i, prev
        o["entry_hash"] = prev = hashlib.sha256((prev + o["payload_json"] + o["result_json"]).encode("utf-8")).hexdigest()
    chain(lines).update(head_hash=prev, operations=len(ops(lines)))


def test_the_real_export_verifies_and_gives_a_checkpoint(tmp_path, lines):
    out = run(tmp_path, lines, "--checkpoint-out")
    assert out.returncode == 0 and "VALID: 4 operations" in out.stdout, out.stdout
    assert f"checkpoint 4:{ops(lines)[-1]['entry_hash']}" in out.stdout


def test_a_readable_field_that_contradicts_the_hashed_text_is_invalid(tmp_path, lines):
    refused = next(o for o in ops(lines) if o["status"] == "REFUSED")
    refused["status"] = "EXECUTED"  # a reader skimming the readable fields would be misled; the hash still matches
    out = run(tmp_path, lines)
    assert out.returncode == 1 and "status beside the hashed text say something else" in out.stdout, out.stdout


def test_a_chain_line_whose_count_disagrees_is_invalid(tmp_path, lines):
    del lines[[i for i, x in enumerate(lines) if x.get("record") == "operation"][-1]]
    chain(lines)["head_hash"] = ops(lines)[-1]["entry_hash"]  # cut short, head patched, count left
    out = run(tmp_path, lines)
    assert out.returncode == 1 and "counts 4 operations; the file holds 3" in out.stdout, out.stdout


def test_a_missing_field_is_reported_not_raised(tmp_path, lines):
    del ops(lines)[1]["prev_hash"]
    out = run(tmp_path, lines)
    assert out.returncode == 1 and "entry 2: missing prev_hash" in out.stdout and "Traceback" not in out.stderr, out.stderr


def test_a_consistent_cut_or_rewrite_is_caught_only_against_a_kept_checkpoint(tmp_path, lines):
    keep = f"4:{ops(lines)[-1]['entry_hash']}"
    cut = [x for x in lines if x is not ops(lines)[-1]]
    rehash(cut)
    assert run(tmp_path, cut).returncode == 0  # on its own a consistent cut verifies: the documented limit
    out = run(tmp_path, cut, "--checkpoint", keep)
    assert out.returncode == 1 and "fewer than the 4 checkpointed" in out.stdout, out.stdout

    payload = json.loads(ops(lines)[0]["payload_json"])
    payload["amount_fen"] = 9_000_000
    ops(lines)[0]["payload_json"] = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    rehash(lines)
    assert run(tmp_path, lines).returncode == 0
    out = run(tmp_path, lines, "--checkpoint", keep)
    assert out.returncode == 1 and "history rewritten" in out.stdout, out.stdout
