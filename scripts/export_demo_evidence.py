#!/usr/bin/env python3
"""Run the full demo walk (scripts/demo_run.py: 17 steps, in process) and export its operations log as ADR-0004 evidence.

    DEMO_MODE=1 PYTHONUTF8=1 uv run --project services/api python scripts/export_demo_evidence.py OUT.jsonl
    python3 scripts/verify_evidence.py OUT.jsonl

OUT.jsonl is the answer of GET /evidence (owner token) on the books the walk leaves behind: a run header, one line per operation
(day, kind, requested_by, status, tier, message, payload_json, result_json, prev_hash, entry_hash), the security events, and a chain
line with the head hash. The walk's own printout is discarded (run demo_run.py to read it). Nothing leaves memory.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "memory")
os.environ.setdefault("LLM_MODE", "cache")
ROOT = Path(__file__).resolve().parents[1]


def main(out: str) -> int:
    spec = importlib.util.spec_from_file_location("demo_run", ROOT / "scripts" / "demo_run.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)  # exits with a clear message unless DEMO_MODE=1
    with contextlib.redirect_stdout(io.StringIO()):
        rc = demo.main()
    c = demo.TestClient(demo.app)
    anonymous = c.get("/evidence").status_code
    r = c.get("/evidence", headers=demo.OWNER)
    Path(out).write_bytes(r.content)
    print(f"demo walk exit {rc}; GET /evidence: {r.status_code} with the owner token, {anonymous} without; {len(r.content)} bytes -> {out}")
    return rc if r.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]) if len(sys.argv) == 2 else (print(__doc__) or 2))
