"""Ticket #103: a document decision is one unit of work with its log row, and two confirms at once are one decision."""

from __future__ import annotations

import threading

import pytest

from app.api.runtime import get_runtime
from app.domain.models import Actor, DocumentStatus


def _proposed(client):  # type: ignore[no-untyped-def]
    return client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"}).json()["document"]


def _decisions(rt, kind: str = "CONFIRM_DOCUMENT") -> list:  # type: ignore[no-untyped-def]
    return [e for e in rt.store.operations() if e.kind == kind]


def test_when_the_record_cannot_be_decided_neither_the_log_row_nor_the_status_survives(client, monkeypatch):
    d = _proposed(client)
    rt = get_runtime()
    log_before = len(rt.store.operations())

    def failing(_record):  # type: ignore[no-untyped-def]
        raise RuntimeError("the store failed after the log row was appended")

    monkeypatch.setattr(rt.store, "decide_contract_record", failing)
    with pytest.raises(RuntimeError, match="after the log row"):
        rt.executor.decide_document(d["id"], Actor.OWNER, confirm=True, doc_hash=d["doc_hash"])
    monkeypatch.undo()
    assert len(rt.store.operations()) == log_before and _decisions(rt) == []
    rec = rt.store.get_contract_record(d["id"])
    assert rec is not None and rec.status == DocumentStatus.PROPOSED and rec.decided_seq is None
    # nothing was half done: the same confirmation now goes through once
    again = rt.executor.decide_document(d["id"], Actor.OWNER, confirm=True, doc_hash=d["doc_hash"])
    assert again.status.value == "EXECUTED" and len(_decisions(rt)) == 1


def test_two_confirms_at_once_are_one_decision_and_one_log_row(client):
    d = _proposed(client)
    rt = get_runtime()
    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []

    def confirm() -> None:
        barrier.wait()
        try:
            results.append(rt.executor.decide_document(d["id"], Actor.OWNER, confirm=True, doc_hash=d["doc_hash"]))
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=confirm) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert errors == [] and len(results) == 2
    assert [r.status.value for r in results] == ["EXECUTED", "EXECUTED"]
    assert results[0].op_id == results[1].op_id and results[0].seq == results[1].seq
    assert results[0].entry_hash == results[1].entry_hash
    assert len(_decisions(rt)) == 1 and _decisions(rt)[0].seq == results[0].seq
    rec = rt.store.get_contract_record(d["id"])
    assert rec is not None and rec.status == DocumentStatus.CONFIRMED and rec.decided_seq == results[0].seq
