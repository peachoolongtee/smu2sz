#!/usr/bin/env python3
"""Verify a TermsLedger execution-evidence JSONL file. Standard library only.

Checks: every operation's entry_hash == sha256(prev_hash + payload_json + result_json); each
prev_hash links to the previous entry (genesis = 64 zeros); seq is contiguous; the chain line's
head_hash matches the last entry. Exit 0 if valid.

Usage: python scripts/verify_evidence.py evidence.jsonl
"""
import hashlib
import json
import sys

GENESIS = "0" * 64


def main(path: str) -> int:
    ops, chain, events = [], None, 0
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            if not raw.strip():
                continue
            rec = json.loads(raw)
            kind = rec.get("record")
            if kind == "operation":
                ops.append(rec)
            elif kind == "chain":
                chain = rec
            elif kind == "security_event":
                events += 1
    prev, problems = GENESIS, []
    for i, op in enumerate(ops, 1):
        if op["seq"] != i:
            problems.append(f"seq {op['seq']} out of order (expected {i})")
        if op["prev_hash"] != prev:
            problems.append(f"seq {op['seq']}: prev_hash does not link")
        h = hashlib.sha256((op["prev_hash"] + op["payload_json"] + op["result_json"]).encode("utf-8")).hexdigest()
        if h != op["entry_hash"]:
            problems.append(f"seq {op['seq']}: entry_hash mismatch")
        prev = op["entry_hash"]
    head = ops[-1]["entry_hash"] if ops else GENESIS
    if chain is None:
        problems.append("no chain record")
    elif chain.get("head_hash") != head:
        problems.append("chain head_hash does not match the last operation")
    status = "VALID" if not problems else "INVALID"
    print(f"{status}: {len(ops)} operations, {events} security events, head {head[:16]}…")
    for p in problems:
        print("  -", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]) if len(sys.argv) == 2 else (print(__doc__) or 2))
