"""E10: a pattern scan for credentials in the tracked files of one commit and in the history of every branch.

Usage (from the repository): python secret_scan.py <commit> <out.txt>
It prints the file (or commit and file) and a masked match only, never a value in full. Matches in the published DEMO ONLY
fixtures and in placeholders are listed separately, so the reader can check them; they are not findings.
"""

from __future__ import annotations

import re
import subprocess
import sys

PATTERNS = {
    "anthropic key": r"sk-ant-[A-Za-z0-9_\-]{20,}",
    "openai-style key": r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}",
    "deepseek-style key": r"\bsk-[a-f0-9]{32}\b",
    "aws access key": r"\bAKIA[0-9A-Z]{16}\b",
    "github token": r"\bgh[pousr]_[A-Za-z0-9]{36,}",
    "slack token": r"\bxox[abpr]-[A-Za-z0-9\-]{10,}",
    "private key block": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----",
    "supabase key": r"\bsbp_[A-Za-z0-9]{30,}|\bsb_secret_[A-Za-z0-9_\-]{20,}",
    "jwt": r"\beyJ[A-Za-z0-9_\-]{15,}\.eyJ[A-Za-z0-9_\-]{15,}\.[A-Za-z0-9_\-]{10,}",
    "database url with password": r"postgres(?:ql)?(?:\+\w+)?://[^:/\s\"'@]+:[^@\s\"'/]{4,}@[^\s\"']+",
}
BENIGN = re.compile(r"DEMO ONLY|demo|example|placeholder|changeme|change-me|password@|postgres:postgres@|user:pass|"
                    r"xxx|<|\$\{|\*\*\*|test|fixture|localhost", re.I)


def mask(s: str) -> str:
    return s[:8] + "…" + f"({len(s)} chars)"


def scan(text: str, where: str, out: list[str], benign: list[str]) -> None:
    for name, pat in PATTERNS.items():
        for m in re.finditer(pat, text):
            line = text[max(0, text.rfind("\n", 0, m.start()) + 1): text.find("\n", m.end()) if text.find("\n", m.end()) > 0 else len(text)]
            (benign if BENIGN.search(line) else out).append(f"{where}: {name}: {mask(m.group(0))}")


def main() -> None:
    commit, dest = sys.argv[1], sys.argv[2]
    found: list[str] = []
    benign: list[str] = []
    files = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit], capture_output=True, text=True, check=True).stdout.split()
    for f in files:
        if f.endswith((".png", ".jpg", ".pdf", ".docx", ".woff", ".woff2", ".ico", ".gif", ".zip")):
            continue
        blob = subprocess.run(["git", "show", f"{commit}:{f}"], capture_output=True)
        scan(blob.stdout.decode("utf-8", "replace"), f"{commit[:8]}:{f}", found, benign)
    tracked_env = [f for f in files if re.search(r"(^|/)\.env($|\.)", f)]
    hist = subprocess.run(["git", "log", "--all", "-p", "--no-color", "--format=COMMIT %h", "--",
                           ".", ":!*.png", ":!*.pdf", ":!*.docx", ":!*.jpg"], capture_output=True)
    cur = "?"
    hist_found: list[str] = []
    hist_benign: list[str] = []
    for raw in hist.stdout.decode("utf-8", "replace").splitlines():
        if raw.startswith("COMMIT "):
            cur = raw[7:]
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            scan(raw[1:], f"history {cur}", hist_found, hist_benign)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(f"commit {commit}; {len(files)} tracked files; tracked env files: {tracked_env}\n")
        fh.write(f"tree findings: {len(found)}\n" + "".join(f"  {x}\n" for x in found))
        fh.write(f"history findings (added lines, every branch): {len(set(hist_found))}\n" + "".join(f"  {x}\n" for x in sorted(set(hist_found))))
        fh.write(f"benign matches (fixtures, placeholders, tests): tree {len(benign)}, history {len(set(hist_benign))}\n")
        fh.write("".join(f"  {x}\n" for x in sorted(set(benign))[:200]))
    print(f"tree findings {len(found)}; history findings {len(set(hist_found))}; benign tree {len(benign)} history {len(set(hist_benign))}")


if __name__ == "__main__":
    main()
