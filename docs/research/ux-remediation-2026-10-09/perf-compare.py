"""perf-compare.py BEFORE_DIR AFTER_DIR [--ignore key,key] [--drop-change-ids]: whether two perf-harness.py runs wrote the same JSON, once random
hex ids (commitment ids, nonces, hashes) are renamed by first appearance. --drop-change-ids leaves out the new id fields of the home change rows."""
import json, re, sys
from pathlib import Path
a, b = Path(sys.argv[1]), Path(sys.argv[2])
ignore = set((sys.argv[sys.argv.index("--ignore") + 1] if "--ignore" in sys.argv else "").split(","))
HEX = re.compile(r"[0-9a-f]{12,}")
def norm(text):
    seen = {}
    return HEX.sub(lambda m: seen.setdefault(m.group(0), f"<h{len(seen)}>"), text)
NEWKEYS = ("id", "receivable_id", "commitment_id", "decision_id", "superseded_by")
def drop(x, name=""):
    if name.endswith("-home.json") and "--drop-change-ids" in sys.argv and isinstance(x, dict):
        x = dict(x); x["changes"] = [{k: v for k, v in r.items() if k not in NEWKEYS or (k == "decision_id" and False)} for r in x["changes"]]
    return drop_(x)
def drop_(x):
    if isinstance(x, dict):
        return {k: drop_(v) for k, v in x.items() if k not in ignore}
    if isinstance(x, list):
        return [drop_(v) for v in x]
    return x
bad = 0
for f in sorted(a.glob("*.json")):
    if f.name in ("numbers.json", "_state.json"):
        continue
    g = b / f.name
    if not g.exists():
        print("MISSING", f.name); bad += 1; continue
    ja, jb = norm(json.dumps(drop(json.loads(f.read_text()), f.name), indent=1, sort_keys=True)), norm(json.dumps(drop(json.loads(g.read_text()), g.name), indent=1, sort_keys=True))
    if ja != jb:
        bad += 1
        import difflib
        print("DIFF", f.name); print("\n".join(list(difflib.unified_diff(ja.splitlines(), jb.splitlines(), lineterm="", n=1))[:40]))
    else:
        print("same", f.name)
print("files differing:", bad)
sys.exit(1 if bad else 0)
