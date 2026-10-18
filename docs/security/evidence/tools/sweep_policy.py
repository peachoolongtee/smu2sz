#!/usr/bin/env python3
"""Check a route-sweep result (authz_sweep_v3.py output) against the route policy of the self-assessment, section 1.5.

Every non-owner caller must be refused (401, 403 or 503) on every route that is not public, a buyer channel or the agent channel; the
agent key is accepted on the agent channel only. Also prints, for the owner, how many requests reached a handler (200) and how many
stopped at validation (404 or 422 on the sweep's placeholder ids and empty bodies). Exit 1 on any violation.

Usage: python sweep_policy.py sweep_demo.json [sweep_prod.json ...]
"""
import json
import sys
from collections import Counter

PUBLIC = {("GET", "/health"), ("GET", "/clock"), ("GET", "/fixtures/offers"), ("GET", "/docs"), ("GET", "/redoc"),
          ("GET", "/openapi.json"), ("GET", "/docs/oauth2-redirect")}
BUYER = {("POST", "/offers"), ("POST", "/nl"), ("POST", "/nl/session/reset")}  # the reset ends only a session the caller may end
AGENT = {("POST", "/operations"), ("POST", "/approvals/{approval_id}"), ("POST", "/circuit/{counterparty_id}/reset")}
REFUSED = {401, 403, 503}


def check(path: str) -> int:
    rows = json.load(open(path, encoding="utf-8"))
    bad, owner = [], Counter()
    for r in rows:
        key = (r["method"], r["path"])
        for role, s in r["status"].items():
            code = int(str(s).split(":")[0])
            if role == "owner":
                owner[code] += 1
            elif key in PUBLIC or key in BUYER or (key in AGENT and role == "agent"):
                continue
            elif code not in REFUSED:
                bad.append(f"{key[0]} {key[1]} as {role}: {s}")
    print(f"{path}: {len(rows)} routes; {len(bad)} policy violations; owner answers {dict(sorted(owner.items()))}")
    for b in bad:
        print("  -", b)
    return len(bad)


if __name__ == "__main__":
    sys.exit(1 if sum(check(p) for p in sys.argv[1:]) else 0)
