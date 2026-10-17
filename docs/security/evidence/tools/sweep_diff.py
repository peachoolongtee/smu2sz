#!/usr/bin/env python3
"""Diff two route-sweep results by (method, path, caller). Exit 1 on any difference.

Usage: python sweep_diff.py before.json after.json
"""
import json
import sys


def load(p: str) -> dict:
    return {(r["method"], r["path"], role): s for r in json.load(open(p, encoding="utf-8")) for role, s in r["status"].items()}


a, b = load(sys.argv[1]), load(sys.argv[2])
diff = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
print(f"{len(a)} and {len(b)} answers; {len(diff)} differ")
for k in diff:
    print(f"  - {k[0]} {k[1]} as {k[2]}: {a.get(k)} -> {b.get(k)}")
sys.exit(1 if diff else 0)
