"""ADR-0006 section 5: a verdict is not standing authority. AcceptOffer, RecordCommitment and the owner's
approval of either re-check the receivables, exclusivity, the caps and (through the injected hook) the
terms against the state and mandate at that moment."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import (
    AcceptOffer,
    Actor,
    Commitment,
    CommitmentStatus,
    DrawFacility,
    FinancialState,
    Mandate,
    OperationStatus,
    Outcome,
    ReceivePayment,
    Tier,
    ViolationCode,
)
from app.mandate import demo_owner_public_key_hex
from app.operations import Executor
from app.operations.log import LogReader
from app.persistence import ApprovalStatus, InMemoryLedgerStore
from app.verifier import evaluate
from tests.operations.builders import Clock, early_pay, offer, op, rebate, seed_offer

Hook = Callable[[Commitment, FinancialState, Mandate, int], Outcome | None]

CAP_FEN = 500_000  # the signed demo mandate's aggregate forward-concession cap (¥5,000)


def accept(clock: Clock, c: Commitment, **kw: Any) -> Any:
    return op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=c.offer_version, terms_hash=c.terms_hash,
              nonce=c.nonce, **kw)


def codes(result: Any) -> list[ViolationCode]:
    return [v.code for v in result.violations]


def verified_rebate(store: Any, ex: Executor, offer_id: str) -> Commitment:
    """A 1.2% contingent rebate on ¥400,000 of purchases, verified by the real verifier on the golden books:
    alone it passes (NEEDS_OWNER_APPROVAL, Tier 2) at ¥4,800.00 of forward value, under the ¥5,000 cap."""
    o = offer(offer_id, [rebate(f"OB-{offer_id}", rate_bp=120, cap_fen=40_000_000)])
    store.put_offer(o)
    v = evaluate(o, store.get_state(), store.get_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex(), day=0).verdict
    assert v.outcome == Outcome.NEEDS_OWNER_APPROVAL and v.required_tier == Tier.TIER_2
    assert v.forward_concession_total_fen == 480_000 and not v.violations
    store.put_verdict(v)
    return ex.propose_commitment(v.id, expires_day=30)


def booked(store: Any) -> int:
    return sum(fc.value_fen for fc in store.get_state().forward_concessions)


def hooked(store: Any, clock: Clock, hook: Hook | None) -> Executor:
    return Executor(store, trusted_owner_key_hex=demo_owner_public_key_hex(), clock=clock, reverify=hook)


# ---------------------------------------------------------------- 1, 2: the aggregate cap


def test_second_rebate_over_the_cap_is_refused_at_approval(ex: Any, store: Any, clock: Clock) -> None:
    c1, c2 = verified_rebate(store, ex, "OFF-R1"), verified_rebate(store, ex, "OFF-R2")
    q1 = ex.execute(accept(clock, c1))
    assert q1.status == OperationStatus.PENDING_APPROVAL
    first = ex.decide(q1.approval_id, True, Actor.OWNER)
    assert first.status == OperationStatus.EXECUTED and booked(store) == 480_000

    q2 = ex.execute(accept(clock, c2))
    assert q2.status == OperationStatus.PENDING_APPROVAL
    second = ex.decide(q2.approval_id, True, Actor.OWNER)
    assert second.status == OperationStatus.REFUSED and codes(second) == [ViolationCode.STALE_VERDICT]
    assert "Aggregate forward-concession cap would be exceeded: ¥9,600.00 vs ¥5,000.00" in second.message
    assert second.violations[0].inputs == {"booked_fen": "480000", "this_fen": "480000", "cap_fen": str(CAP_FEN)}
    assert booked(store) == 480_000 <= CAP_FEN
    assert store.get_commitment(c2.id).status == CommitmentStatus.PROPOSED
    assert store.get_commitment(c1.id).status == CommitmentStatus.ACTIVE


def test_both_queued_then_approved_books_only_the_first(ex: Any, store: Any, clock: Clock) -> None:
    c1, c2 = verified_rebate(store, ex, "OFF-R1"), verified_rebate(store, ex, "OFF-R2")
    q1, q2 = ex.execute(accept(clock, c1)), ex.execute(accept(clock, c2))
    assert {q1.status, q2.status} == {OperationStatus.PENDING_APPROVAL}
    assert booked(store) == 0

    first = ex.decide(q1.approval_id, True, Actor.OWNER)
    second = ex.decide(q2.approval_id, True, Actor.OWNER)
    assert first.status == OperationStatus.EXECUTED
    assert second.status == OperationStatus.REFUSED and codes(second) == [ViolationCode.STALE_VERDICT]
    assert second.approval_id == q2.approval_id
    assert store.get_approval(q2.approval_id).status == ApprovalStatus.APPROVED  # decided, not left pending
    assert [fc.commitment_id for fc in store.get_state().forward_concessions] == [c1.id]
    assert booked(store) <= CAP_FEN and store.verify_chain()


def test_per_buyer_cap_is_enforced_too(ex: Any, store: Any, clock: Clock) -> None:
    """The demo mandate has no per-buyer entry, so re-sign a copy that has one."""
    from app.mandate import load_demo_owner_key, sign

    c = seed_offer(store, ex, "OFF-PB", value_fen=300_000)
    m = store.get_mandate().model_copy(update={"per_buyer_caps_fen": {c.counterparty_id: 200_000}})
    store.put_mandate(sign(m, load_demo_owner_key()["private_key_hex"]))
    r = ex.execute(accept(clock, c))
    assert r.status == OperationStatus.REFUSED and codes(r) == [ViolationCode.STALE_VERDICT]
    assert "¥3,000.00 vs ¥2,000.00" in r.message and c.counterparty_id in r.message
    assert booked(store) == 0


def test_zero_value_commitment_passes_the_caps_trivially(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, "OFF-Z", value_fen=0)
    assert ex.execute(accept(clock, c)).status == OperationStatus.EXECUTED


# ---------------------------------------------------------------- 3: exclusivity


def test_second_commitment_on_the_same_receivable_conflicts_until_the_first_is_revoked(
    ex: Any, store: Any, clock: Clock
) -> None:
    c1 = seed_offer(store, ex, "OFF-1")
    c2 = seed_offer(store, ex, "OFF-2")
    assert ex.execute(accept(clock, c1)).status == OperationStatus.EXECUTED

    r = ex.execute(accept(clock, c2))
    assert r.status == OperationStatus.REFUSED and codes(r) == [ViolationCode.CONFLICTING_COMMITMENT]
    assert c1.id in r.message and c2.id in r.message and "RCV-A" in r.message and "revoke" in r.message
    assert store.get_commitment(c2.id).status == CommitmentStatus.PROPOSED
    assert [fc.commitment_id for fc in store.get_state().forward_concessions] == [c1.id]

    assert ex.revoke_commitment(c1.id, Actor.OWNER).status == OperationStatus.EXECUTED
    assert booked(store) == 0
    c3 = seed_offer(store, ex, "OFF-3")
    done = ex.execute(accept(clock, c3))
    assert done.status == OperationStatus.EXECUTED and store.get_commitment(c3.id).status == CommitmentStatus.ACTIVE


def test_exclusivity_ignores_proposed_commitments(ex: Any, store: Any, clock: Clock) -> None:
    seed_offer(store, ex, "OFF-P")  # PROPOSED only: not live, so it blocks nobody
    c = seed_offer(store, ex, "OFF-A")
    assert ex.execute(accept(clock, c)).status == OperationStatus.EXECUTED


# ---------------------------------------------------------------- 4: the receivable

def test_receivable_settled_after_the_verdict_refuses_the_accept(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, "OFF-1")
    paid = ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id="RCV-A", amount_fen=42_000_000))
    assert paid.status == OperationStatus.EXECUTED
    r = ex.execute(accept(clock, c))
    assert r.status == OperationStatus.REFUSED and codes(r) == [ViolationCode.STALE_VERDICT]
    assert "Receivable RCV-A is SETTLED; re-evaluate the offer" in r.message
    assert store.get_commitment(c.id).status == CommitmentStatus.PROPOSED and booked(store) == 0


def test_generated_future_invoices_and_financed_receivables(ex: Any, store: Any, clock: Clock) -> None:
    state = store.get_state()
    fin = state.receivables[0].model_copy(update={"status": "FINANCED"})
    store.put_state(state.model_copy(update={"receivables": [fin]}))
    c = seed_offer(store, ex, "OFF-F")
    assert ex.execute(accept(clock, c)).status == OperationStatus.EXECUTED  # FINANCED is still owed

    ri = seed_offer(store, ex, "OFF-RIID", obligations=[early_pay("OB-RIID", receivable_id="RI:BUYER-1:3")],
                    value_fen=0)
    assert ex.execute(accept(clock, ri)).status == OperationStatus.EXECUTED  # "RI:" ids are not on the books yet

    missing = seed_offer(store, ex, "OFF-GONE", obligations=[early_pay("OB-GONE", receivable_id="RCV-NOPE")],
                         value_fen=0)
    r = ex.execute(accept(clock, missing))
    assert r.status == OperationStatus.REFUSED and codes(r) == [ViolationCode.STALE_VERDICT]
    assert "RCV-NOPE" in r.message


# ---------------------------------------------------------------- 5: the state version and the hook


def move_the_books(ex: Any, clock: Clock) -> None:
    drawn = ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=1_000_000))
    assert drawn.status == OperationStatus.EXECUTED


@pytest.mark.parametrize(("answer", "executed"), [
    (Outcome.ACCEPT, True),
    (Outcome.NEEDS_OWNER_APPROVAL, True),
    (Outcome.REJECT, False),
    (Outcome.COUNTER, False),
    (Outcome.NO_VERDICT, False),
    (None, False),
])
def test_hook_decides_when_the_books_moved(store: Any, clock: Clock, answer: Outcome | None, executed: bool) -> None:
    calls: list[tuple[Commitment, FinancialState, Mandate, int]] = []

    def hook(c: Commitment, s: FinancialState, m: Mandate, now: int) -> Outcome | None:
        calls.append((c, s, m, now))
        return answer

    ex = hooked(store, clock, hook)
    c = seed_offer(store, ex, "OFF-1")
    move_the_books(ex, clock)
    current = store.get_state()
    r = ex.execute(accept(clock, c))
    assert len(calls) == 1
    got_c, got_state, got_mandate, got_now = calls[0]
    assert got_c.id == c.id and got_state == current and got_mandate.version == 1 and got_now == 0
    if executed:
        assert r.status == OperationStatus.EXECUTED
    else:
        assert r.status == OperationStatus.REFUSED and codes(r) == [ViolationCode.STALE_VERDICT]
        assert "The books changed since verdict V-OFF-1 (state v1 → v2)" in r.message
        assert "no longer verify; re-evaluate" in r.message
        assert store.get_commitment(c.id).status == CommitmentStatus.PROPOSED and booked(store) == 0


def test_hook_that_raises_refuses(store: Any, clock: Clock) -> None:
    def hook(*_a: Any) -> Outcome | None:
        raise RuntimeError("verifier down")

    ex = hooked(store, clock, hook)
    c = seed_offer(store, ex, "OFF-1")
    move_the_books(ex, clock)
    r = ex.execute(accept(clock, c))
    assert r.status == OperationStatus.REFUSED and codes(r) == [ViolationCode.STALE_VERDICT]


def test_no_hook_means_only_checks_one_to_three_run(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, "OFF-1")
    move_the_books(ex, clock)
    assert ex.execute(accept(clock, c)).status == OperationStatus.EXECUTED


def test_hook_is_not_called_when_the_state_version_is_unchanged(store: Any, clock: Clock) -> None:
    calls: list[int] = []

    def hook(*_a: Any) -> Outcome | None:
        calls.append(1)
        return Outcome.REJECT

    ex = hooked(store, clock, hook)
    c = seed_offer(store, ex, "OFF-1")
    assert ex.execute(accept(clock, c)).status == OperationStatus.EXECUTED and calls == []


def test_hook_also_guards_the_owner_approval_path(store: Any, clock: Clock) -> None:
    answers = iter([Outcome.REJECT])

    def hook(*_a: Any) -> Outcome | None:
        return next(answers)

    ex = hooked(store, clock, hook)
    c = verified_rebate(store, ex, "OFF-R1")
    queued = ex.execute(accept(clock, c))
    assert queued.status == OperationStatus.PENDING_APPROVAL and queued.approval_id is not None
    move_the_books(ex, clock)
    r = ex.decide(queued.approval_id, True, Actor.OWNER)
    assert r.status == OperationStatus.REFUSED and codes(r) == [ViolationCode.STALE_VERDICT]
    assert booked(store) == 0


# ---------------------------------------------------------------- 6: the golden flow


@pytest.fixture
def runtime() -> Iterator[Runtime]:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    yield rt
    set_runtime(None)


@pytest.fixture
def client(runtime: Runtime) -> Iterator[TestClient]:
    from app.main import app

    yield TestClient(app, headers={"X-Owner-Token": "demo-owner-token"})


def test_golden_flow_is_unchanged_and_never_calls_the_hook(
    client: TestClient, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real = Runtime.reverify

    def spy(self: Runtime, c: Commitment, *a: Any) -> Outcome | None:
        calls.append(c.id)
        return real(self, c, *a)

    monkeypatch.setattr(Runtime, "reverify", spy)
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    assert client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()["outcome"] == "REJECT"
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()
    assert n["outcome"] == "DEAL"
    assert all(o["status"] == "EXECUTED" and o["tier"] == "TIER_1" for o in n["operations"]), n["operations"]
    assert calls == []  # the accept ran on the verdict's own state version


def test_every_golden_counter_reverifies_on_unchanged_books(client: TestClient, runtime: Runtime) -> None:
    """The hook treats a commitment's obligations as an offer; a counter the verifier proposed must pass."""
    for fixture in ("EX01_PACKAGE", "EX01B_REWORDED", "EX02_EARLY_1_5", "EX03_AS_USUAL", "EX04_CLAIMED_REBATE"):
        runtime.reset()
        oid = client.post("/offers", json={"fixture_id": fixture}).json()["offer"]["offer_id"]
        verdict = runtime.store.get_verdict(client.post(f"/offers/{oid}/evaluate",
                                                         json={"fixture_id": fixture}).json()["id"])
        assert verdict is not None and verdict.counters, fixture
        for counter in verdict.counters:
            c = runtime.executor.propose_commitment(verdict.id, expires_day=7, counter_id=counter.id)
            got = runtime.reverify(c, runtime.store.get_state(), runtime.store.get_mandate(), 0)
            if fixture in ("EX01_PACKAGE", "EX01B_REWORDED") and counter.label == "Option B":
                # KNOWN GAP (reported with the existing-debt change, 3 Oct): the price-adjustment counter is not
                # tested for liquidity by the verifier; with the existing loan's ¥45,000 payments as cash its 60-day
                # terms leave a reserve shortfall (¥130,000 at most, days 47-61) no committed source cures on day 0
                # (FAC-IF's limit holds the plan's ¥255,000 advance until day 32). The fix belongs in app/verifier.
                assert got == Outcome.REJECT, (fixture, counter.id, got)
                continue
            assert got in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL), (fixture, counter.id, got)


def test_real_hook_accepts_a_counter_after_unrelated_books_movement(client: TestClient, runtime: Runtime) -> None:
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    verdict = runtime.store.get_verdict(client.post(f"/offers/{oid}/evaluate",
                                                     json={"fixture_id": "EX01_PACKAGE"}).json()["id"])
    assert verdict is not None
    c = runtime.executor.propose_commitment(verdict.id, expires_day=7, counter_id=verdict.counters[0].id)
    clock = Clock(runtime.day)
    move_the_books(runtime.executor, clock)
    assert runtime.store.get_state().state_version != verdict.state_version
    r = runtime.executor.execute(accept(clock, c, source_verdict_id=verdict.id))
    assert r.status == OperationStatus.EXECUTED, r.message


def test_real_hook_refuses_terms_that_no_longer_verify_on_todays_books(client: TestClient, runtime: Runtime) -> None:
    """The books moved (cash fell away) while receivables and caps are untouched: only the verifier can tell."""
    oid = client.post("/offers", json={"fixture_id": "EX02_EARLY_1_5"}).json()["offer"]["offer_id"]
    verdict = runtime.store.get_verdict(client.post(f"/offers/{oid}/evaluate",
                                                     json={"fixture_id": "EX02_EARLY_1_5"}).json()["id"])
    assert verdict is not None
    c = runtime.executor.propose_commitment(verdict.id, expires_day=7, counter_id=verdict.counters[0].id)
    state = runtime.store.get_state()
    runtime.store.put_state(state.model_copy(update={"cash_fen": 10_000_000,
                                                     "state_version": state.state_version + 1}))
    assert runtime.reverify(c, runtime.store.get_state(), runtime.store.get_mandate(), 0) == Outcome.REJECT
    r = runtime.executor.execute(accept(Clock(runtime.day), c, source_verdict_id=verdict.id))
    assert r.status == OperationStatus.REFUSED and codes(r) == [ViolationCode.STALE_VERDICT]
    assert "no longer verify" in r.message and booked(runtime.store) == 0


def test_runtime_hook_fails_closed(runtime: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.verifier

    def boom(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("verifier down")

    c = seed_offer(runtime.store, runtime.executor, "OFF-1")
    monkeypatch.setattr(app.verifier, "evaluate_verdict", boom)
    assert runtime.reverify(c, runtime.store.get_state(), runtime.store.get_mandate(), 0) is None


# ---------------------------------------------------------------- 7: the log


def test_refusals_are_logged_with_the_new_codes_and_replay_is_a_duplicate(
    ex: Any, store: Any, clock: Clock
) -> None:
    c1, c2, c3 = (seed_offer(store, ex, f"OFF-{n}", value_fen=300_000) for n in (1, 2, 3))
    assert ex.execute(accept(clock, c1)).status == OperationStatus.EXECUTED
    conflict_op = accept(clock, c2, key="K-CONFLICT")
    conflict = ex.execute(conflict_op)
    assert codes(conflict) == [ViolationCode.CONFLICTING_COMMITMENT]
    assert ex.revoke_commitment(c1.id, Actor.OWNER).status == OperationStatus.EXECUTED
    assert ex.execute(accept(clock, c3)).status == OperationStatus.EXECUTED
    # c3 holds RCV-A and ¥3,000 of the ¥5,000 cap; a fourth ¥3,000 is over the cap on another receivable.
    c4 = seed_offer(store, ex, "OFF-4", obligations=[early_pay("OB-4", receivable_id="RI:BUYER-1:9")], value_fen=300_000)
    stale_op = accept(clock, c4, key="K-STALE")
    stale = ex.execute(stale_op)
    assert codes(stale) == [ViolationCode.STALE_VERDICT] and "¥6,000.00 vs ¥5,000.00" in stale.message

    logged = {e.idempotency_key: e for e in LogReader().entries(store.operations())}
    assert logged["K-CONFLICT"].result.status == OperationStatus.REFUSED
    assert [v.code for v in logged["K-CONFLICT"].result.violations] == [ViolationCode.CONFLICTING_COMMITMENT]
    assert [v.code for v in logged["K-STALE"].result.violations] == [ViolationCode.STALE_VERDICT]
    assert logged["K-STALE"].result.seq is None and stale.seq == logged["K-STALE"].seq

    before = (len(store.operations()), store.get_state())
    for original, refused in ((conflict_op, conflict), (stale_op, stale)):
        dup = ex.execute(original)
        assert dup.status == OperationStatus.REFUSED and dup.violations  # run again, refused again, nothing booked
    assert store.get_state() == before[1] and len(store.operations()) == before[0] + 2
    assert store.verify_chain()
