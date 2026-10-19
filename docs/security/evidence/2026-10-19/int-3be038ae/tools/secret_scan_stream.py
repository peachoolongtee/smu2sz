"""The gate's secret scan (dev-03215a20/tools/secret_scan.py), streaming the history instead of holding it in memory.

The original reads `git log --all -p` whole into memory; on the review machine (7 GB) it was killed (exit 137). This wrapper
imports the original's PATTERNS, BENIGN, mask and scan unchanged and only streams the history line by line. Same output file.

usage (from the repository): python secret_scan_stream.py <path to secret_scan.py> <commit> <out.txt>
"""
import importlib.util
import re
import subprocess
import sys

spec = importlib.util.spec_from_file_location("ss", sys.argv[1])
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)
commit, dest = sys.argv[2], sys.argv[3]
found: list[str] = []
benign: list[str] = []
files = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit], capture_output=True, text=True, check=True).stdout.split()
for f in files:
    if f.endswith((".png", ".jpg", ".pdf", ".docx", ".woff", ".woff2", ".ico", ".gif", ".zip")):
        continue
    blob = subprocess.run(["git", "show", f"{commit}:{f}"], capture_output=True)
    ss.scan(blob.stdout.decode("utf-8", "replace"), f"{commit[:8]}:{f}", found, benign)
tracked_env = [f for f in files if re.search(r"(^|/)\.env($|\.)", f)]
p = subprocess.Popen(["git", "log", "--all", "-p", "--no-color", "--format=COMMIT %h", "--",
                      ".", ":!*.png", ":!*.pdf", ":!*.docx", ":!*.jpg"], stdout=subprocess.PIPE)
cur = "?"
hist_found: list[str] = []
hist_benign: list[str] = []
commits = 0
for rawb in p.stdout:
    raw = rawb.decode("utf-8", "replace").rstrip("\n")
    if raw.startswith("COMMIT "):
        cur = raw[7:]
        commits += 1
        continue
    if raw.startswith("+") and not raw.startswith("+++"):
        ss.scan(raw[1:], f"history {cur}", hist_found, hist_benign)
p.wait()
with open(dest, "w", encoding="utf-8") as fh:
    fh.write(f"commit {commit}; {len(files)} tracked files; tracked env files: {tracked_env}\n")
    fh.write(f"history scanned: {commits} commits on every branch (git log --all, full clone), streamed\n")
    fh.write(f"tree findings: {len(found)}\n" + "".join(f"  {x}\n" for x in found))
    fh.write(f"history findings (added lines, every branch): {len(set(hist_found))}\n" + "".join(f"  {x}\n" for x in sorted(set(hist_found))))
    fh.write(f"benign matches (fixtures, placeholders, tests): tree {len(benign)}, history {len(set(hist_benign))}\n")
    fh.write("".join(f"  {x}\n" for x in sorted(set(benign))[:200]))
print(f"tree findings {len(found)}; history findings {len(set(hist_found))}; benign tree {len(benign)} history {len(set(hist_benign))}; "
      f"{commits} commits")
