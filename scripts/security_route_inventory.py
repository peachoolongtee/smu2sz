"""Route inventory for the security handoff: every FastAPI route under services/api/app/api, its router- and route-level
dependencies, the auth calls inside the handler, and test files that mention its path. Usage:
  python -I scripts/security_route_inventory.py <repo root> <out.json> [<baseline commit>]
Reads source only; imports nothing from the repo."""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
out = Path(sys.argv[2])
baseline = sys.argv[3] if len(sys.argv) > 3 else None
api = root / "services/api/app/api"
tests = root / "services/api/tests"

AUTH_MARKERS = {
    "require_owner": "owner token (dependency)",
    "require_owner_or_agent": "owner token or agent key",
    "is_owner(": "owner token (checked in handler)",
    "is_agent(": "agent key (checked in handler)",
    "is_bank_feed(": "bank-feed key",
    "counterparty_for_key": "buyer channel key",
    "x_counterparty_key": "buyer channel key header",
    "demo_mode()": "demo mode only",
    "require_feature(": "feature flag",
    "_require_enabled(": "feature flag (module)",
    "_flag_on": "feature flag (module)",
    "log_refusal(": "logs PRIVILEGE_ESCALATION on refusal",
}


def src_of(path: Path, rev: str | None) -> str | None:
    rel = path.relative_to(root).as_posix()
    if rev is None:
        return path.read_text(encoding="utf-8")
    r = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{rel}"], capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None


def files(rev: str | None) -> list[Path]:
    if rev is None:
        return sorted(api.glob("*.py"))
    r = subprocess.run(["git", "-C", str(root), "ls-tree", "--name-only", f"{rev}", "services/api/app/api/"], capture_output=True, text=True)
    return [root / p for p in r.stdout.split() if p.endswith(".py")]


def dep_names(call: ast.Call) -> list[str]:
    names = []
    for kw in call.keywords:
        if kw.arg == "dependencies" and isinstance(kw.value, ast.List):
            for el in kw.value.elts:
                names.append(ast.unparse(el))
    return names


def routes(rev: str | None) -> list[dict]:
    found = []
    for f in files(rev):
        s = src_of(f, rev)
        if s is None:
            continue
        try:
            tree = ast.parse(s)
        except SyntaxError:
            continue
        router_deps: dict[str, list[str]] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "APIRouter":
                for t in node.targets:
                    router_deps[ast.unparse(t)] = dep_names(node.value)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in node.decorator_list:
                if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)):
                    continue
                method = d.func.attr
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                rname = ast.unparse(d.func.value)
                if rname not in router_deps:
                    continue
                path = d.args[0].value if d.args and isinstance(d.args[0], ast.Constant) else "?"
                body = ast.get_source_segment(s, node) or ""
                deps = router_deps[rname] + dep_names(d)
                text = " ".join(deps) + "\n" + body
                markers = sorted({v for k, v in AUTH_MARKERS.items() if k in text})
                params = [a.arg for a in node.args.args + node.args.kwonlyargs]
                found.append({"method": method.upper(), "path": path, "file": f.relative_to(root).as_posix(),
                              "line": node.lineno, "handler": node.name, "router_dependencies": router_deps[rname],
                              "route_dependencies": dep_names(d), "auth_markers": markers,
                              "credential_headers": [p for p in params if p.startswith("x_")]})
    return found


def tests_for(path: str) -> list[str]:
    lits = [p for p in path.split("/") if p and "{" not in p]
    if "{" not in path:
        needles = [path]
    else:
        needles = ["/" + lits[-1]] if lits else []
        if path.rstrip("/").endswith("}") and lits:
            needles = ["/" + lits[0] + "/"]
    hits = []
    for t in tests.rglob("*.py"):
        txt = t.read_text(encoding="utf-8", errors="ignore")
        if any(n in txt for n in needles):
            hits.append(t.relative_to(root).as_posix())
    return sorted(hits)


now = routes(None)
base = {(r["method"], r["path"]) for r in routes(baseline)} if baseline else set()
attacks = (root / "services/api/evals/security/attacks.yaml").read_text(encoding="utf-8", errors="ignore")
for r in now:
    r["new_since_baseline"] = bool(baseline) and (r["method"], r["path"]) not in base
    r["tests_mentioning_path"] = tests_for(r["path"])
    first = "/" + [p for p in r["path"].split("/") if p][0] if r["path"].strip("/") else "/"
    r["attack_catalogue_mentions_prefix"] = first in attacks
    r["auth_summary"] = ("OWNER" if any("owner" in m for m in r["auth_markers"]) else "") or \
                        ("NONE FOUND BY SCAN - VERIFY" if not r["auth_markers"] else ",".join(r["auth_markers"]))
out.write_text(json.dumps({"generated_from": "services/api/app/api (AST scan)", "baseline": baseline, "routes": now}, indent=1,
                          ensure_ascii=False), encoding="utf-8")
print(len(now), "routes;", sum(r["new_since_baseline"] for r in now), "new since baseline;",
      sum(not r["auth_markers"] for r in now), "with no auth marker found")
