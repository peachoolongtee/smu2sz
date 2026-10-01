"""One contract suite, run against InMemoryLedgerStore and SqlLedgerStore (SQLite in tmp_path)."""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import itertools
import json

import pytest

from app.domain import ports
from app.domain.fixtures import load_scenario
from app.domain.models import (
    Actor,
    ApplyForFacility,
    CommitmentStatus,
    OperationResult,
    OperationStatus,
    Tier,
)
from app.persistence import (
    GENESIS_HASH,
    ApprovalAlreadyDecided,
    ApprovalStatus,
    InvalidPayload,
    NonceAlreadyUsed,
    NotFound,
    OfferVersionConflict,
    canonical_json,
)
from tests.persistence import factories as f

# ---------------------------------------------------------------- helpers


def _op(n: int, key: str | None = None) -> tuple[str, str, str, str, str]:
    op = ApplyForFacility(
        op_id=f"OP-{n}",
        idempotency_key=key or f"idem-{n}",
        mandate_version=1,
        requested_by=Actor.AGENT,
        day=0,
        facility_id="FAC-GGL",
        amount_fen=50_000_000 + n,
    )
    result = OperationResult(
        op_id=op.op_id, kind=op.kind, status=OperationStatus.PENDING_APPROVAL, tier=Tier.TIER_2
    )
    return op.op_id, op.kind, op.idempotency_key, canonical_json(op), canonical_json(result)


def _append(store, n: int, key: str | None = None):
    return store.append_operation(*_op(n, key))


# ---------------------------------------------------------------- port conformance


def test_implements_every_ledger_store_method_with_the_port_signature(store):
    port_methods = {
        name: fn for name, fn in vars(ports.LedgerStore).items() if callable(fn) and not name.startswith("_")
    }
    assert len(port_methods) >= 20
    for name, port_fn in port_methods.items():
        impl = getattr(store, name, None)
        assert callable(impl), name
        port_params = [p for p in inspect.signature(port_fn).parameters if p != "self"]
        impl_params = list(inspect.signature(impl).parameters)
        assert impl_params[: len(port_params)] == port_params, name


def test_operations_have_no_update_or_delete_api(store):
    for name in dir(store):
        lowered = name.lower()
        if "operation" in lowered or "entry" in lowered or "nonce" in lowered:
            assert not any(verb in lowered for verb in ("update", "delete", "remove", "edit", "set_")), name


# ---------------------------------------------------------------- canonical JSON


def test_canonical_json_is_sorted_compact_and_keeps_unicode():
    assert canonical_json({"b": 1, "a": {"d": "¥", "c": [2, 1]}}) == '{"a":{"c":[2,1],"d":"¥"},"b":1}'
    ob = f.discount()
    text = canonical_json(ob)
    assert json.loads(text) == ob.model_dump(mode="json")
    assert ", " not in text and ": " not in text
    assert canonical_json(ob) == canonical_json(f.discount())


def test_canonical_json_rejects_nan():
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


# ---------------------------------------------------------------- hash chain


def test_empty_chain_is_valid(store):
    assert store.operations() == []
    assert store.verify_chain() is True


def test_append_builds_a_contiguous_sha256_chain_from_genesis(store):
    entries = [_append(store, n) for n in range(1, 6)]
    assert [e.seq for e in entries] == [1, 2, 3, 4, 5]
    assert entries[0].prev_hash == GENESIS_HASH == "0" * 64
    for prev, cur in itertools.pairwise(entries):
        assert cur.prev_hash == prev.entry_hash
    for e in entries:
        expected = hashlib.sha256((e.prev_hash + e.payload_json + e.result_json).encode()).hexdigest()
        assert e.entry_hash == expected
    assert store.operations() == entries
    assert store.verify_chain() is True


def test_append_rejects_non_json_payloads_and_writes_nothing(store):
    op_id, kind, key, payload, result = _op(1)
    with pytest.raises(InvalidPayload):
        store.append_operation(op_id, kind, key, "not json", result)
    with pytest.raises(InvalidPayload):
        store.append_operation(op_id, kind, key, payload, "{broken")
    assert store.operations() == []


def test_records_are_immutable_and_reads_are_copies(store):
    e = _append(store, 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.result_json = "{}"  # type: ignore[misc]
    listing = store.operations()
    listing.clear()
    assert len(store.operations()) == 1
    assert store.verify_chain() is True


def test_refusals_and_duplicates_are_appended_like_any_result(store):
    op_id, kind, key, payload, _ = _op(1)
    refused = OperationResult(op_id=op_id, kind=kind, status=OperationStatus.REFUSED, tier=Tier.TIER_3)
    store.append_operation(op_id, kind, key, payload, canonical_json(refused))
    dup = OperationResult(op_id=op_id, kind=kind, status=OperationStatus.DUPLICATE, tier=Tier.TIER_3)
    store.append_operation(op_id, kind, key, payload, canonical_json(dup))
    assert [e.seq for e in store.operations()] == [1, 2]
    assert store.verify_chain() is True


# ---------------------------------------------------------------- idempotency and nonces


def test_find_by_idempotency_key_returns_the_first_record(store):
    first = _append(store, 1, key="same")
    _append(store, 2, key="other")
    _append(store, 3, key="same")
    found = store.find_by_idempotency_key("same")
    assert found == first
    assert store.find_by_idempotency_key("other").seq == 2
    assert store.find_by_idempotency_key("missing") is None


def test_nonce_tracking_and_reuse(store):
    assert store.nonce_used("n-1") is False
    store.mark_nonce_used("n-1")
    assert store.nonce_used("n-1") is True
    assert store.nonce_used("n-2") is False
    with pytest.raises(NonceAlreadyUsed):
        store.mark_nonce_used("n-1")


# ---------------------------------------------------------------- commitments


def test_commitments_round_trip_and_upsert_keeps_order(store):
    a, b = f.commitment("CMT-A"), f.commitment("CMT-B")
    store.put_commitment(a)
    store.put_commitment(b)
    assert store.get_commitment("CMT-A") == a
    assert store.get_commitment("missing") is None
    accepted = a.model_copy(update={"status": CommitmentStatus.ACCEPTED})
    store.put_commitment(accepted)
    assert store.get_commitment("CMT-A").status == CommitmentStatus.ACCEPTED
    assert [c.id for c in store.commitments()] == ["CMT-A", "CMT-B"]
    assert store.commitments()[0] == accepted


# ---------------------------------------------------------------- state and mandate (versioned)


def test_state_and_mandate_missing_raise_not_found(store):
    with pytest.raises(NotFound):
        store.get_state()
    with pytest.raises(NotFound):
        store.get_mandate()


def test_state_and_mandate_are_versioned_and_latest_wins(store):
    state, mandate = load_scenario()
    store.put_state(state)
    store.put_mandate(mandate)
    assert store.get_state() == state
    assert store.get_mandate() == mandate

    state2 = state.model_copy(update={"state_version": 2, "cash_fen": 12_345_678_901_234})
    mandate2 = mandate.model_copy(update={"version": 2, "revoked": True})
    store.put_state(state2)
    store.put_mandate(mandate2)
    assert store.get_state() == state2
    assert store.get_state().cash_fen == 12_345_678_901_234
    assert store.get_mandate() == mandate2
    assert store.state_history() == [state, state2]
    assert store.mandate_history() == [mandate, mandate2]


# ---------------------------------------------------------------- offers, verdicts, security events


def test_offers_round_trip_by_latest_or_explicit_version(store):
    v1 = f.offer("OFF-1", 1)
    v2 = f.offer("OFF-1", 2, obligations=[f.discount(rate_bp=85)])
    store.put_offer(v1)
    store.put_offer(v2)
    assert store.get_offer("OFF-1") == v2
    assert store.get_offer("OFF-1", 1) == v1
    assert store.get_offer("OFF-1", 3) is None
    assert store.get_offer("nope") is None



def test_a_stored_offer_version_cannot_be_swapped_for_other_terms(store):
    """F-07: an (offer_id, version) is immutable in its economics; new terms need a new version."""
    v1 = f.offer("OFF-1", 1)
    store.put_offer(v1)
    store.put_offer(v1)  # the same offer again is fine (idempotent intake)
    reworded = v1.model_copy(update={"obligations": [o.model_copy(update={"confidence": 0.5, "id": o.id + "x"})
                                                     for o in v1.obligations]})
    store.put_offer(reworded)  # ids, spans and confidence are not economics
    for swapped in (
        f.offer("OFF-1", 1, obligations=[f.rebate()]),  # different terms
        f.offer("OFF-1", 1, obligations=[f.discount(rate_bp=300), f.extension(), f.rebate()]),  # a richer rate
        v1.model_copy(update={"counterparty_id": "BUYER-2"}),
    ):
        with pytest.raises(OfferVersionConflict):
            store.put_offer(swapped)
    assert store.get_offer("OFF-1", 1) == reworded
    store.put_offer(f.offer("OFF-1", 2, obligations=[f.rebate()]))  # a new version is the way to change terms
    assert store.get_offer("OFF-1").version == 2


def test_verdicts_round_trip(store):
    v = f.verdict()
    store.put_verdict(v)
    assert store.get_verdict("V-1") == v
    assert store.get_verdict("V-2") is None


def test_verdicts_lists_every_stored_verdict_in_first_stored_order(store):
    assert store.verdicts() == []
    first, second = f.verdict("V-1"), f.verdict("V-2", offer_id="OFF-2")
    store.put_verdict(first)
    store.put_verdict(second)
    assert store.verdicts() == [first, second]
    replaced = first.model_copy(update={"forward_concession_total_fen": 1})
    store.put_verdict(replaced)  # same id: replaced in place, not duplicated or moved
    assert store.verdicts() == [replaced, second]
    store.reset()
    assert store.verdicts() == []


def test_security_events_are_kept_in_order(store):
    events = [f.security_event(f"SEC-{i}") for i in range(3)]
    for e in events:
        store.add_security_event(e)
    assert store.security_events() == events


# ---------------------------------------------------------------- approvals (Tier-2 queue)


def test_approvals_queue_add_list_and_decide(store):
    _, _, _, op_json, _ = _op(1)
    a1 = store.add_approval(op_json, "Tier 2: apply for a facility")
    a2 = store.add_approval(_op(2)[3], "Tier 2: apply for a facility")
    assert a1 != a2
    pending = store.approvals(ApprovalStatus.PENDING)
    assert [a.id for a in pending] == [a1, a2]
    assert pending[0].op_id == "OP-1" and pending[0].kind == "APPLY_FOR_FACILITY"
    assert pending[0].op_json == op_json

    decided = store.decide_approval(a1, True, Actor.OWNER)
    assert decided.status == ApprovalStatus.APPROVED and decided.decided_by == "OWNER"
    rejected = store.decide_approval(a2, False, "OWNER")
    assert rejected.status == ApprovalStatus.REJECTED

    assert store.approvals("PENDING") == []
    assert [a.id for a in store.approvals("APPROVED")] == [a1]
    assert [a.id for a in store.approvals()] == [a1, a2]
    assert store.get_approval(a1) == decided


def test_an_approval_can_be_decided_only_once(store):
    aid = store.add_approval(_op(1)[3], "Tier 2")
    store.decide_approval(aid, False, "OWNER")
    with pytest.raises(ApprovalAlreadyDecided):
        store.decide_approval(aid, True, "OWNER")
    assert store.get_approval(aid).status == ApprovalStatus.REJECTED
    with pytest.raises(NotFound):
        store.decide_approval("APR-999999", True, "OWNER")


def test_approval_payload_must_be_json(store):
    with pytest.raises(InvalidPayload):
        store.add_approval("apply for a loan please", "Tier 2")
    assert store.approvals() == []


# ---------------------------------------------------------------- telemetry


def test_llm_calls_and_evaluation_runs_are_recorded(store):
    cid = store.record_llm_call(
        backend="cache",
        model="fixture-cache",
        prompt_version="p1",
        input_sha256="a" * 64,
        status="OK",
        output_json='{"status":"COMPILED"}',
        cache_hit=True,
    )
    calls = store.llm_calls()
    assert [c.id for c in calls] == [cid]
    assert calls[0].cache_hit is True and calls[0].model == "fixture-cache"

    rid = store.add_evaluation_run(suite="security", passed=11, failed=0, metrics_json='{"asr":0}')
    runs = store.evaluation_runs()
    assert [r.id for r in runs] == [rid]
    assert runs[0].passed == 11 and json.loads(runs[0].metrics_json) == {"asr": 0}
    with pytest.raises(InvalidPayload):
        store.add_evaluation_run(suite="x", passed=0, failed=0, metrics_json="nope")


# ---------------------------------------------------------------- evidence


def test_evidence_export_is_jsonl_and_ends_with_the_head_hash(store):
    entries = [_append(store, n) for n in range(1, 4)]
    text = store.export_evidence()
    lines = [json.loads(line) for line in text.splitlines()]
    assert len(lines) == len(entries) + 1
    for line, e in zip(lines, entries, strict=False):
        assert line["record"] == "operation"
        assert (line["seq"], line["kind"], line["entry_hash"], line["prev_hash"]) == (
            e.seq,
            e.kind,
            e.entry_hash,
            e.prev_hash,
        )
        assert line["status"] == "PENDING_APPROVAL"
    final = lines[-1]
    assert final["record"] == "chain"
    assert final["chain_valid"] is True
    assert final["head_hash"] == entries[-1].entry_hash
    assert final["operations"] == 3
    exports = store.evidence_exports()
    assert len(exports) == 1 and exports[0].head_hash == entries[-1].entry_hash
    assert exports[0].content_sha256 == hashlib.sha256(text.encode()).hexdigest()


def test_evidence_export_of_an_empty_ledger(store):
    lines = [json.loads(line) for line in store.export_evidence().splitlines()]
    assert lines == [
        {
            "record": "chain",
            "operations": 0,
            "chain_valid": True,
            "head_hash": GENESIS_HASH,
            "genesis_hash": GENESIS_HASH,
        }
    ]


# ---------------------------------------------------------------- reset


def test_reset_clears_the_ledger_and_keeps_telemetry(store):
    state, mandate = load_scenario()
    store.put_state(state)
    store.put_mandate(mandate)
    store.put_offer(f.offer())
    store.put_verdict(f.verdict())
    store.put_commitment(f.commitment())
    store.add_security_event(f.security_event())
    store.mark_nonce_used("n-1")
    store.add_approval(_op(1)[3], "Tier 2")
    _append(store, 1)
    store.export_evidence()
    store.record_llm_call(backend="cache", model="m", prompt_version="p", input_sha256="b" * 64, status="OK")
    store.add_evaluation_run(suite="s", passed=1, failed=0)

    store.reset()

    assert store.operations() == [] and store.verify_chain() is True
    assert store.commitments() == [] and store.security_events() == [] and store.approvals() == []
    assert store.get_offer("OFF-1") is None and store.get_verdict("V-1") is None and store.verdicts() == []
    assert store.nonce_used("n-1") is False
    assert store.evidence_exports() == []
    with pytest.raises(NotFound):
        store.get_state()
    with pytest.raises(NotFound):
        store.get_mandate()
    assert len(store.llm_calls()) == 1 and len(store.evaluation_runs()) == 1

    # The chain restarts from genesis and ids restart.
    e = _append(store, 7)
    assert (e.seq, e.prev_hash) == (1, GENESIS_HASH)
    assert store.add_approval(_op(2)[3], "Tier 2") == "APR-000001"

    store.reset(include_telemetry=True)
    assert store.llm_calls() == [] and store.evaluation_runs() == []


# ---------------------------------------------------------------- unit of work (F-01)


def test_a_failed_transaction_keeps_nothing(store):
    state, mandate = load_scenario()
    store.put_state(state)
    store.put_mandate(mandate)
    _append(store, 1)
    with pytest.raises(RuntimeError), store.transaction():
        store.put_state(state.model_copy(update={"cash_fen": 1, "state_version": 2}))
        store.put_commitment(f.commitment())
        store.mark_nonce_used("n-tx")
        store.add_security_event(f.security_event())
        store.add_approval(_op(2)[3], "Tier 2")
        _append(store, 3)
        assert len(store.operations()) == 2  # visible inside the unit of work
        raise RuntimeError("the database went away")
    assert store.get_state() == state and store.state_history() == [state]
    assert store.commitments() == [] and store.nonce_used("n-tx") is False
    assert store.security_events() == [] and store.approvals() == []
    assert [e.seq for e in store.operations()] == [1] and store.verify_chain() is True
    assert _append(store, 4).seq == 2  # the chain continues from what was committed


def test_a_transaction_commits_everything_together_and_nested_blocks_join_it(store):
    state, _ = load_scenario()
    with store.transaction():
        store.put_state(state)
        with store.transaction():
            store.mark_nonce_used("n-1")
            _append(store, 1)
        store.put_commitment(f.commitment())
    assert store.get_state() == state and store.nonce_used("n-1") is True
    assert len(store.operations()) == 1 and len(store.commitments()) == 1
    with pytest.raises(RuntimeError), store.transaction():
        with store.transaction():
            _append(store, 2)
        raise RuntimeError("outer fails after the inner block")
    assert len(store.operations()) == 1  # the inner block did not commit on its own


def test_a_nonce_replay_inside_a_transaction_raises_before_any_write_fails(store):
    store.mark_nonce_used("n-1")
    with store.transaction():
        with pytest.raises(NonceAlreadyUsed):
            store.mark_nonce_used("n-1")
        _append(store, 1)  # the unit of work is still usable, e.g. to log the refusal
    assert len(store.operations()) == 1 and store.verify_chain() is True
