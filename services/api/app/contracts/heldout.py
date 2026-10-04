"""Scoring the agent's contract readings against labels written before the first run (brief 03 §6.8).

Pure: `score(reading, expected)` compares one compiled contract with one label set; `report(results)` renders the
markdown. `scripts/evaluate_contracts.py` runs it over `fixtures/contracts_heldout/`. Only the keys a label gives are
compared; a field the label leaves null must be blank in the reading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.models import MULTI_VALUED_CONTRACT_FIELDS, CompiledContract, ContractField, ContractTerm

AGREE, ABSTAINED, WRONG = "AGREE", "ABSTAINED", "WRONG"


@dataclass
class FieldResult:
    field: str
    outcome: str
    expected: Any
    read: Any
    note: str = ""


@dataclass
class ContractResult:
    id: str
    compiler: str
    status: str
    fields: list[FieldResult] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)

    def count(self, outcome: str) -> int:
        return sum(1 for f in self.fields if f.outcome == outcome)


def _value(t: ContractTerm, keys: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in keys:
        v = getattr(t, k)
        out[k] = v.value if hasattr(v, "value") else v
    return out


def score(reading: CompiledContract, expected: dict[str, Any]) -> list[FieldResult]:
    by: dict[ContractField, list[ContractTerm]] = {}
    for t in reading.terms:
        by.setdefault(t.field, []).append(t)
    results: list[FieldResult] = []
    for name, want in expected.items():
        f = ContractField(name)
        got = by.get(f, [])
        if f in MULTI_VALUED_CONTRACT_FIELDS:
            if isinstance(want, int):  # a count ("REQUIRED_DOCUMENT: 3")
                n = len(got)
                outcome = AGREE if n == want else ABSTAINED if n < want else WRONG
                results.append(FieldResult(name, outcome, want, n, "count"))
                continue
            want_list = list(want or [])
            read = [_value(t, sorted({k for w in want_list for k in w})) for t in got] if want_list else [{} for _ in got]
            if not want_list:
                results.append(FieldResult(name, AGREE if not got else WRONG, [], len(got)))
                continue
            missing = [w for w in want_list if w not in read]
            extra = [r for r in read if r not in want_list]
            outcome = WRONG if extra else ABSTAINED if missing else AGREE
            results.append(FieldResult(name, outcome, want_list, read))
            continue
        if want is None:
            results.append(FieldResult(name, AGREE if not got else WRONG, None,
                                       _value(got[0], ["value_text"]) if got else None))
            continue
        if not got:
            results.append(FieldResult(name, ABSTAINED, want, None))
            continue
        read_v = _value(got[0], list(want))
        results.append(FieldResult(name, AGREE if read_v == want else WRONG, want, read_v))
    return results


def report(results: list[ContractResult], *, pending: bool) -> str:
    lines = ["# Held-out contract readings (brief 03 §6.8)", ""]
    if pending:
        lines += [
            "**Status: pending.** No independent contract has been supplied yet (`fixtures/contracts_heldout/` holds "
            "the protocol and an empty label file). There are no held-out figures to report.",
            "",
            "The demo documents in `fixtures/contracts/` are not a held-out set: the contract grammar was written "
            "against them, so no accuracy figure is quoted from them.",
            "",
        ]
        return "\n".join(lines)
    total = [f for r in results for f in r.fields]
    agree, abst, wrong = (sum(1 for f in total if f.outcome == o) for o in (AGREE, ABSTAINED, WRONG))
    lines += [
        f"{len(results)} contract(s), {len(total)} labelled fields: **{agree} agree, {abst} left blank, {wrong} wrong**.",
        "",
        "Labels were written before the first run by someone who had not seen the reading code (see "
        "`fixtures/contracts_heldout/README.md`). A blank field is safe (the owner sees \"not found\"); a wrong field "
        "is the number that matters.",
        "",
        "| Contract | Reading | Compiler | Agree | Blank | Wrong |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append(f"| {r.id} | {r.status} | {r.compiler} | {r.count(AGREE)} | {r.count(ABSTAINED)} | {r.count(WRONG)} |")
    for r in results:
        bad = [f for f in r.fields if f.outcome != AGREE]
        if bad or r.unsupported:
            lines += ["", f"## {r.id}", ""]
            for f in bad:
                lines.append(f"- {f.field}: {f.outcome}; label {f.expected!r}, read {f.read!r}")
            for u in r.unsupported:
                lines.append(f"- not in the schema (by design, shown nowhere): {u}")
    lines.append("")
    return "\n".join(lines)


__all__ = ["ABSTAINED", "AGREE", "WRONG", "ContractResult", "FieldResult", "report", "score"]
