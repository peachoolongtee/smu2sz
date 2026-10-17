#!/usr/bin/env python3
"""Write the release manifest and checksums for one certification's evidence folder.

Usage (from the repo root of the checkout that was certified):
  python scripts/security_manifest.py docs/security/evidence/<date>/<label> --assessor "Security Lead (AI agent)"

It records what a reviewer needs to tie the evidence to one build: the full commit SHA and whether the working tree was
clean, the runtime and key dependency versions, the configuration the runs used, the time and assessor, and a SHA-256
for every file in the folder (SHA256SUMS). It reads lockfiles and tool versions only; it never reads .env files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The configuration every certification run uses (docs/security/CERTIFICATIONS.md); listed, not read from the machine.
RUN_CONFIG = {
    "DATABASE_URL": "memory (suites, catalogue, sweep); local PostgreSQL 17 for tests/concurrency and the guards",
    "LLM_MODE": "cache (no model provider is called)",
    "DEMO_MODE": "1 for the suites and the catalogue; the sweep runs demo, prod (0) and unset",
    "TERMSLEDGER_NO_DOTENV": "1 (.env is never loaded)",
    "API processes": "1",
}
PY_PACKAGES = ("fastapi", "pydantic", "starlette", "sqlalchemy", "psycopg", "anthropic", "openai", "cryptography")
WEB_PACKAGES = ("next", "react", "react-dom", "source-map-js")


def _run(*cmd: str, cwd: Path = ROOT) -> str:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        return "not installed"


def _uv_lock_versions(lock: Path) -> dict[str, str]:
    text = lock.read_text(encoding="utf-8") if lock.exists() else ""
    out = {}
    for name in PY_PACKAGES:
        m = re.search(rf'\[\[package\]\]\nname = "{re.escape(name)}"\nversion = "([^"]+)"', text)
        out[name] = m.group(1) if m else "not locked"
    return out


def _pnpm_lock_versions(lock: Path) -> dict[str, str]:
    text = lock.read_text(encoding="utf-8") if lock.exists() else ""
    out = {}
    for name in WEB_PACKAGES:
        found = sorted(set(re.findall(rf"^  {re.escape(name)}@([0-9][^:(\s]*)", text, re.MULTILINE)))
        out[name] = ", ".join(found) or "not locked"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="the evidence folder of this certification")
    ap.add_argument("--assessor", required=True)
    ap.add_argument("--scope", default="local simulation: loopback, one API process, cache mode, synthetic data")
    ap.add_argument("--exception", action="append", default=[], help="an approved exception, repeatable")
    ap.add_argument("--exclusion", action="append", default=[], help="an explicit exclusion, repeatable")
    args = ap.parse_args()
    folder = (ROOT / args.folder).resolve() if not Path(args.folder).is_absolute() else Path(args.folder)
    folder.mkdir(parents=True, exist_ok=True)

    sha = _run("git", "rev-parse", "HEAD")
    dirty = _run("git", "status", "--porcelain", "--untracked-files=no")
    manifest = {
        "commit": sha,
        "working_tree_clean": not dirty,
        "build": f"source checkout at {sha[:12]}; no container image (local simulation)",
        "assessed_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "assessor": args.assessor,
        "scope": args.scope,
        "runtime": {
            "os": platform.platform(),
            "python": _run("uv", "run", "--no-sync", "--project", "services/api", "python", "--version"),
            "uv": _run("uv", "--version"),
            "node": _run("node", "--version"),
            "pnpm": _run("pnpm", "--version", cwd=ROOT / "apps" / "web"),
            "postgresql": "17 (local, for tests/concurrency only)",
        },
        "python_packages": _uv_lock_versions(ROOT / "services" / "api" / "uv.lock"),
        "web_packages": _pnpm_lock_versions(ROOT / "apps" / "web" / "pnpm-lock.yaml"),
        "configuration": RUN_CONFIG,
        "exclusions": args.exclusion,
        "approved_exceptions": args.exception,
    }
    (folder / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    sums = []
    for f in sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        sums.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(folder).as_posix()}")
    (folder / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    archive = hashlib.sha256((folder / "SHA256SUMS").read_bytes()).hexdigest()
    print(f"{folder.relative_to(ROOT).as_posix()}: {len(sums)} files; evidence id sha256:{archive[:16]} (of SHA256SUMS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
