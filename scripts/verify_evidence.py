#!/usr/bin/env python3
"""Verify a TermsLedger execution-evidence JSONL file. Standard library only.

Checks:
  - every operation's entry_hash == sha256(prev_hash + payload_json + result_json), the three strings joined as they are
    (payload_json and result_json are each one canonical JSON object, so the boundary between them is unambiguous);
  - each prev_hash links to the previous entry (genesis = 64 zeros) and seq is contiguous from 1;
  - payload_json and result_json are JSON objects, and the readable fields beside them (op_id, kind, requested_by, status,
    tier, day, violations, message) say what those hashed strings say, so a reader is not misled (idempotency_key and seq are
    the log's own columns and are not inside the hash; seq order is held by the prev_hash links);
  - the chain line exists, its head_hash is the last entry's, its operation count is the number of entries, its
    genesis_hash is the genesis value and its chain_valid is true.

What it cannot tell on its own: a file whose whole chain was rewritten consistently, cut short together with its chain line,
or replaced by an older valid export verifies as VALID. Against those, keep a checkpoint somewhere the database owner cannot
write (print one with --checkpoint-out) and verify later files with --checkpoint COUNT:HEAD: the file must then hold at least
COUNT entries, and entry COUNT must have exactly that hash.

Usage:
  python scripts/verify_evidence.py evidence.jsonl
  python scripts/verify_evidence.py evidence.jsonl --checkpoint-out          # print COUNT:HEAD to keep elsewhere
  python scripts/verify_evidence.py evidence.jsonl --checkpoint 12:3f2a...   # this file extends that checkpoint
Exit 0 if valid, 1 if not, 2 on usage errors.
"""
import argparse
import hashlib
import json
import sys

GENESIS = "0" * 64
REQUIRED = ("seq", "payload_json", "result_json", "prev_hash", "entry_hash")


def _obj(text: object) -> dict | None:
    if not isinstance(text, str):
        return None
    try:
        v = json.loads(text)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def _readable_fields(op: dict, payload: dict, result: dict) -> list[str]:
    """The fields shown beside the hashed strings that disagree with them (app/persistence/chain.py:evidence_line)."""
    want = {
        "requested_by": payload.get("requested_by"),
        "status": result.get("status"),
        "tier": result.get("tier"),
        "day": result.get("effective_day", payload.get("day")),
        "message": result.get("message", ""),
        "violations": [v.get("code") for v in result.get("violations", []) if isinstance(v, dict)],
    }
    for key in ("op_id", "kind"):  # idempotency_key is the log's own column (an approval's decision adds a suffix), not hashed
        if key in payload:
            want[key] = payload[key]
    return [k for k, v in want.items() if k in op and op[k] != v]


def verify(path: str, checkpoint: tuple[int, str] | None = None) -> tuple[list[str], list[dict], int]:
    ops, chains, events, problems = [], [], 0, []
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw)
            except ValueError:
                problems.append(f"line {n}: not JSON")
                continue
            kind = rec.get("record") if isinstance(rec, dict) else None
            if kind == "operation":
                ops.append(rec)
            elif kind == "chain":
                chains.append(rec)
            elif kind == "security_event":
                events += 1
    prev = GENESIS
    for i, op in enumerate(ops, 1):
        missing = [k for k in REQUIRED if k not in op]
        if missing:
            problems.append(f"entry {i}: missing {', '.join(missing)}")
            prev = op.get("entry_hash", prev)
            continue
        if op["seq"] != i:
            problems.append(f"seq {op['seq']} out of order (expected {i})")
        if op["prev_hash"] != prev:
            problems.append(f"seq {op['seq']}: prev_hash does not link")
        payload, result = _obj(op["payload_json"]), _obj(op["result_json"])
        if payload is None or result is None:
            problems.append(f"seq {op['seq']}: payload_json or result_json is not a JSON object")
        else:
            wrong = _readable_fields(op, payload, result)
            if wrong:
                problems.append(f"seq {op['seq']}: {', '.join(wrong)} beside the hashed text say something else")
        h = hashlib.sha256((str(op["prev_hash"]) + str(op["payload_json"]) + str(op["result_json"])).encode("utf-8")).hexdigest()
        if h != op["entry_hash"]:
            problems.append(f"seq {op['seq']}: entry_hash mismatch")
        prev = op["entry_hash"]
    head = ops[-1].get("entry_hash", "") if ops else GENESIS
    if len(chains) != 1:
        problems.append("no chain record" if not chains else f"{len(chains)} chain records")
    else:
        chain = chains[0]
        if chain.get("head_hash") != head:
            problems.append("chain head_hash does not match the last operation")
        if chain.get("operations") != len(ops):
            problems.append(f"chain line counts {chain.get('operations')} operations; the file holds {len(ops)}")
        if chain.get("genesis_hash", GENESIS) != GENESIS:
            problems.append("chain line names another genesis")
        if chain.get("chain_valid") is not True:
            problems.append("chain line does not say chain_valid")
    if checkpoint is not None:
        count, want = checkpoint
        if len(ops) < count:
            problems.append(f"checkpoint: the file holds {len(ops)} entries, fewer than the {count} checkpointed (cut short or rolled back)")
        elif ops[count - 1].get("entry_hash") != want:
            problems.append(f"checkpoint: entry {count} is not the checkpointed entry (history rewritten)")
    return problems, ops, events


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("evidence")
    ap.add_argument("--checkpoint", help="COUNT:HEAD kept from an earlier export; the file must extend it")
    ap.add_argument("--checkpoint-out", action="store_true", help="print COUNT:HEAD of this file to keep elsewhere")
    args = ap.parse_args(argv)
    cp = None
    if args.checkpoint:
        count, sep, h = args.checkpoint.partition(":")
        if not sep or not count.isdigit() or int(count) < 1 or len(h) != 64:
            print("--checkpoint must be COUNT:HEAD with a 64-character hash", file=sys.stderr)
            return 2
        cp = (int(count), h)
    problems, ops, events = verify(args.evidence, cp)
    head = ops[-1].get("entry_hash", "") if ops else GENESIS
    status = "VALID" if not problems else "INVALID"
    print(f"{status}: {len(ops)} operations, {events} security events, head {head[:16]}…")
    for p in problems:
        print("  -", p)
    if args.checkpoint_out and not problems:
        print(f"checkpoint {len(ops)}:{head}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
