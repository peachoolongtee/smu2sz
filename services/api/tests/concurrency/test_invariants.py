"""The concurrency and recovery invariants, each forced with two concurrent writers in two processes.

Every test ends with `assert_serial_and_accounted` (invariant 8): the chain verifies, the concurrent books are
byte-identical to a serial replay of the committed actions in log order, and every state version is explained
by exactly one EXECUTED log entry. Under the `first-write` rendezvous both writers have read the same books
before either writes, so the loser must have hit the compare-and-swap and run again (`units` counts it)."""

from __future__ import annotations

from typing import Any

from app.domain.models import (
    AcceptOffer,
    Actor,
    DrawFacility,
    ReceivePayment,
    SubmitInvoiceForFinancing,
)
from tests.concurrency.harness import (
    CTX,
    DAY,
    TIMEOUT,
    Engine,
    Journal,
    WorkerPair,
    assert_serial_and_accounted,
    perform,
    plain_executor,
    process_queue_then_hang,
    replay,
    run,
    seed_books,
)
from tests.operations.builders import extension, seed_offer

LINE, IF, RCV = "FAC-LINE", "FAC-IF", "RCV-A"


def mk(cls: type, n: str, actor: Actor = Actor.AGENT, key: str | None = None, **fields: Any) -> Any:
    return cls(op_id=f"OP-{n}", idempotency_key=key or f"KEY-{n}", mandate_version=1, requested_by=actor, day=DAY,
               **fields)


def accept_of(c: Any, n: str = "ACC") -> AcceptOffer:
    return mk(AcceptOffer, n, offer_id=c.offer_id, offer_version=c.offer_version, terms_hash=c.terms_hash,
              nonce=c.nonce)


def fac(state: Any, fid: str) -> Any:
    return next(f for f in state.facilities if f.id == fid)


def rcv(state: Any, rid: str) -> Any:
    return next(r for r in state.receivables if r.id == rid)


def lots_match_drawn(state: Any) -> bool:
    return all(sum(lot.remaining_fen for lot in state.lots if lot.facility_id == f.id) == f.drawn_fen
               for f in state.facilities)


def the(outcomes: list[dict[str, Any]], status: str) -> dict[str, Any]:
    [o] = [o for o in outcomes if o.get("status") == status]
    return o


def raced(engine: Engine, ra: dict[str, Any], rb: dict[str, Any]) -> None:
    """Under `first-write` both read the same books, so one compare-and-swap lost and that unit ran again."""
    assert ra["pid"] != rb["pid"]  # two processes
    if engine.rendezvous == "first-write":
        assert ra["units"] + rb["units"] > len(ra["outcomes"]) + len(rb["outcomes"]), "the interleaving was not forced"


def finish(books: Any, seed: Any, journal: Journal, seed_states: int, wiring: str = "plain") -> None:
    assert_serial_and_accounted(books, replay(seed, journal, wiring=wiring), seed_states=seed_states)


# ================================================================ 1. the last room on a facility


def test_1_two_draws_against_the_last_room_execute_once(engine: Engine, books: Any, workers: WorkerPair) -> None:
    seed_books(books)
    n0 = len(books.state_history())
    limit = fac(books.get_state(), LINE).limit_fen  # ¥150,000, nothing drawn: room for one ¥100,000 draw
    a, b = mk(DrawFacility, "D1", facility_id=LINE, amount_fen=10_000_000), \
        mk(DrawFacility, "D2", facility_id=LINE, amount_fen=10_000_000)
    ra, rb = workers.both(run(engine, [("execute", a)]), run(engine, [("execute", b)]))
    outs = ra["outcomes"] + rb["outcomes"]
    assert sorted(o["status"] for o in outs) == ["EXECUTED", "REFUSED"]
    refused = the(outs, "REFUSED")
    assert refused["codes"] == ["PRECONDITION_FAILED"] and "exceeds FAC-LINE's available" in refused["message"]
    raced(engine, ra, rb)

    state = books.get_state()
    assert fac(state, LINE).drawn_fen == 10_000_000 <= limit
    assert all(fac(s, LINE).drawn_fen <= limit for s in books.state_history())  # never over the limit, ever
    assert lots_match_drawn(state)
    journal = Journal()
    journal.add(*outs)
    finish(books, seed_books, journal, n0)


# ================================================================ 2. a receipt and a financing on one invoice


def _seed_if(store: Any) -> None:
    seed_books(store, if_lead_days=0)  # the advance lands at once, so a later receipt repays the lender


def test_2_receipt_and_financing_on_one_invoice_conserve_in_either_order(
        engine: Engine, books: Any, workers: WorkerPair) -> None:
    _seed_if(books)
    n0 = len(books.state_history())
    s0 = books.get_state()
    face = 42_000_000
    pay = mk(ReceivePayment, "PAY", Actor.SYSTEM, receivable_id=RCV, amount_fen=face, bank_reference="BK-2")
    fin = mk(SubmitInvoiceForFinancing, "FIN", Actor.OWNER, facility_id=IF, receivable_id=RCV, advance_fen=33_600_000)
    ra, rb = workers.both(run(engine, [("execute", pay)]), run(engine, [("execute", fin)]))
    [p], [f] = ra["outcomes"], rb["outcomes"]
    raced(engine, ra, rb)

    assert p["status"] == "EXECUTED"
    state = books.get_state()
    invoice = rcv(state, RCV)
    assert (invoice.status, invoice.settled_fen) == ("SETTLED", face)  # paid exactly once, in full
    assert fac(state, IF).drawn_fen == 0 and lots_match_drawn(state)  # the lender is owed nothing afterwards
    cash = state.cash_fen - s0.cash_fen
    if f["status"] == "EXECUTED":  # financed, then paid: the receipt repaid the lender
        assert f["seq"] < p["seq"]
        assert IF in p["message"] and "repaid advance" in p["message"]
        assert 0 < face - cash < 33_600_000 // 50  # the receipt, less only the lender's interest and fees
    else:  # paid, then financed: the financing is refused, nothing booked for it
        assert f["status"] == "REFUSED" and "SETTLED" in f["message"] and p["seq"] < f["seq"]
        assert cash == face
    journal = Journal()
    journal.add(p, f)
    finish(books, _seed_if, journal, n0)


# ================================================================ 3. accept versus revoke


def _seed_offer(store: Any) -> None:
    seed_books(store)
    seed_offer(store, plain_executor(store))  # the Tier-1 early-pay acceptance, PROPOSED, nonce NONCE-OFF-1


def test_3_accept_versus_revoke_books_the_concession_at_most_once(
        engine: Engine, books: Any, workers: WorkerPair) -> None:
    _seed_offer(books)
    n0 = len(books.state_history())
    [c] = books.commitments()
    ra, rb = workers.both(run(engine, [("execute", accept_of(c))]), run(engine, [("revoke", c.id)]))
    [acc], [rev] = ra["outcomes"], rb["outcomes"]
    raced(engine, ra, rb)

    final = books.get_commitment(c.id)
    assert rev["status"] == "EXECUTED" and final.status == "REVOKED"  # the owner's revocation always lands
    if acc["status"] == "EXECUTED":  # accepted first: the revocation took the concession back out
        assert acc["seq"] < rev["seq"] and books.nonce_used(c.nonce)
    else:  # revoked first: the acceptance is refused and books nothing
        assert acc["status"] == "REFUSED" and rev["seq"] < acc["seq"] and not books.nonce_used(c.nonce)
    for s in books.state_history():  # booked exactly once or not at all, at every version of the books
        assert len([fc for fc in s.forward_concessions if fc.commitment_id == c.id]) <= 1
    state = books.get_state()
    assert not [fc for fc in state.forward_concessions if fc.commitment_id == c.id]
    assert not [a for a in state.invoice_adjustments if a.id.startswith(f"{c.id}:")]  # match REVOKED
    journal = Journal()
    journal.add(acc, rev)
    finish(books, _seed_offer, journal, n0)


# ================================================================ 4. one bank event, submitted twice at once


def test_4a_the_same_idempotency_key_twice_counts_cash_once(engine: Engine, books: Any, workers: WorkerPair) -> None:
    seed_books(books)
    n0 = len(books.state_history())
    s0 = books.get_state()
    pay = mk(ReceivePayment, "BANK-1", Actor.SYSTEM, key="bank-feed-1", receivable_id=RCV, amount_fen=10_000_000)
    ra, rb = workers.both(run(engine, [("execute", pay)]), run(engine, [("execute", pay)]))
    outs = ra["outcomes"] + rb["outcomes"]
    assert sorted(o["status"] for o in outs) == ["DUPLICATE", "EXECUTED"]
    raced(engine, ra, rb)
    state = books.get_state()
    assert state.cash_fen - s0.cash_fen == 10_000_000 and rcv(state, RCV).settled_fen == 10_000_000
    journal = Journal()
    journal.add(*outs)
    finish(books, seed_books, journal, n0)


def test_4b_the_same_bank_reference_under_two_keys_counts_cash_once(
        engine: Engine, books: Any, workers: WorkerPair) -> None:
    seed_books(books)
    n0 = len(books.state_history())
    s0 = books.get_state()
    a = mk(ReceivePayment, "BR-1", Actor.SYSTEM, receivable_id=RCV, amount_fen=10_000_000, bank_reference="BK-77")
    b = mk(ReceivePayment, "BR-2", Actor.SYSTEM, receivable_id=RCV, amount_fen=10_000_000, bank_reference="BK-77")
    ra, rb = workers.both(run(engine, [("execute", a)]), run(engine, [("execute", b)]))
    outs = ra["outcomes"] + rb["outcomes"]
    assert sorted(o["status"] for o in outs) == ["EXECUTED", "REFUSED"]
    assert "Duplicate bank event" in the(outs, "REFUSED")["message"]
    raced(engine, ra, rb)
    state = books.get_state()
    assert state.cash_fen - s0.cash_fen == 10_000_000 and rcv(state, RCV).settled_fen == 10_000_000
    journal = Journal()
    journal.add(*outs)
    finish(books, seed_books, journal, n0)


# ================================================================ 5. a failed log append


def _seed_tier2(store: Any) -> None:
    seed_books(store)
    seed_offer(store, plain_executor(store), "OFF-T", obligations=[extension()])  # lengthening: Tier 2


def test_5_a_failed_log_append_keeps_nothing_and_the_retry_executes_once(
        engine: Engine, books: Any, workers: WorkerPair) -> None:
    _seed_tier2(books)
    n0 = len(books.state_history())
    [c] = books.commitments()
    journal = Journal()
    queued = perform(plain_executor(books), ("execute", accept_of(c)))
    assert queued["status"] == "PENDING_APPROVAL"
    journal.add(queued)
    aid = queued["approval_id"]
    s0 = books.get_state()

    # The owner's approval fails at the log append (after its state, commitment, nonce and approval writes)
    # while another process books a draw.
    draw = mk(DrawFacility, "D5", facility_id=LINE, amount_fen=1_000_000)
    ra, rb = workers.both(run(engine, [("decide", aid, True)], fail_append=True), run(engine, [("execute", draw)]))
    [failed], [drew] = ra["outcomes"], rb["outcomes"]
    assert failed["error"] == "ConnectionError" and drew["status"] == "EXECUTED"
    journal.add(drew)
    assert books.get_approval(aid).status == "PENDING"  # the approval: rolled back
    assert books.get_commitment(c.id).status == "PROPOSED" and not books.nonce_used(c.nonce)  # commitment, nonce
    state = books.get_state()
    assert not state.forward_concessions and state.state_version == s0.state_version + 1  # only the draw
    assert fac(state, LINE).drawn_fen == 1_000_000
    assert [o.op_id for o in books.operations()] == [accept_of(c).op_id, draw.op_id]

    # The retry executes exactly once; deciding again is refused.
    retry = workers.one(run(engine, [("decide", aid, True)], rendezvous=False))["outcomes"][0]
    assert retry["status"] == "EXECUTED"
    journal.add(retry)
    again = workers.one(run(engine, [("decide", aid, True)], rendezvous=False), worker=1)["outcomes"][0]
    assert again["error"] == "ApprovalAlreadyDecided"
    assert len(books.get_state().forward_concessions) == 1 and books.nonce_used(c.nonce)

    # The same for an operation retried under its idempotency key.
    draw2 = mk(DrawFacility, "D6", facility_id=LINE, amount_fen=2_000_000)
    pay = mk(ReceivePayment, "P5", Actor.SYSTEM, receivable_id=RCV, amount_fen=5_000_000)
    ra, rb = workers.both(run(engine, [("execute", draw2)], fail_append=True), run(engine, [("execute", pay)]))
    assert ra["outcomes"][0]["error"] == "ConnectionError" and rb["outcomes"][0]["status"] == "EXECUTED"
    journal.add(*rb["outcomes"])
    assert fac(books.get_state(), LINE).drawn_fen == 1_000_000
    first, second = (workers.one(run(engine, [("execute", draw2)], rendezvous=False), worker=w)["outcomes"][0]
                     for w in (0, 1))
    assert (first["status"], second["status"]) == ("EXECUTED", "DUPLICATE")
    journal.add(first, second)
    assert fac(books.get_state(), LINE).drawn_fen == 3_000_000
    executed = [o for o in books.operations() if o.idempotency_key == draw2.idempotency_key
                and '"status":"EXECUTED"' in o.result_json]
    assert len(executed) == 1
    finish(books, _seed_tier2, journal, n0)


# ================================================================ 6. a restart in the middle of an approval


def test_6_a_process_killed_mid_approval_and_a_hydrated_runtime_decides_once(
        engine: Engine, books: Any, workers: WorkerPair) -> None:
    _seed_tier2(books)
    n0 = len(books.state_history())
    [c] = books.commitments()
    s0 = books.get_state()
    inside, release, out = CTX.Event(), CTX.Event(), CTX.Queue()
    doomed = CTX.Process(target=process_queue_then_hang, args=(engine, accept_of(c), inside, release, out))
    doomed.start()
    try:
        queued = out.get(timeout=4 * TIMEOUT)
        assert queued["status"] == "PENDING_APPROVAL", queued
        assert inside.wait(4 * TIMEOUT), "the dying process never reached its log append"
    finally:
        doomed.kill()  # mid-unit: the approval, nonce, commitment and state writes are uncommitted
        doomed.join(TIMEOUT)
    aid = queued["approval_id"]
    journal = Journal()
    journal.add(queued)
    assert books.get_approval(aid).status == "PENDING"
    assert books.get_commitment(c.id).status == "PROPOSED" and not books.nonce_used(c.nonce)
    assert books.get_state() == s0 and len(books.operations()) == 1 and books.verify_chain()

    task = ("task_hydrate_and_decide", {"engine": engine, "approval_id": aid})
    ra, rb = workers.both(task, task)
    for r in (ra, rb):
        assert r["hydrated"] == {"day": DAY, "pending": [aid]}  # each process rebuilt the runtime from the database
    outs = ra["outcomes"] + rb["outcomes"]
    decided = [o for o in outs if "status" in o]
    assert len(decided) == 1, outs
    assert [o["error"] for o in outs if "error" in o] == ["ApprovalAlreadyDecided"]
    assert books.get_approval(aid).status == "APPROVED"
    executed = [o for o in books.operations() if o.op_id == accept_of(c).op_id and '"status":"EXECUTED"' in o.result_json]
    assert len(executed) == (1 if decided[0]["status"] == "EXECUTED" else 0)
    assert len(books.get_state().forward_concessions) == len(executed)
    journal.add(*decided)
    finish(books, _seed_tier2, journal, n0, wiring="runtime")


# ================================================================ 7. compare-and-swap on the state version


def test_7_two_writers_of_the_same_state_version_one_wins_the_other_is_refused(
        engine: Engine, books: Any, workers: WorkerPair) -> None:
    seed_books(books)
    s0 = books.get_state()
    ra, rb = workers.both(("task_put_state_cas", {"engine": engine, "cash_delta": 1}),
                          ("task_put_state_cas", {"engine": engine, "cash_delta": 2}))
    assert ra["read"] == rb["read"] == s0.state_version  # both read the same version
    assert sorted([ra["written"], rb["written"]]) == [False, True]
    loser = ra if not ra["written"] else rb
    assert loser["error"] == "StateVersionConflict"
    winner_delta = 1 if ra["written"] else 2
    history = books.state_history()
    assert [s.state_version for s in history] == [s0.state_version, s0.state_version + 1]  # nothing overwritten
    assert books.get_state().cash_fen == s0.cash_fen + winner_delta


def test_7b_two_executors_on_one_state_version_lose_no_update(engine: Engine, books: Any, workers: WorkerPair) -> None:
    seed_books(books)
    n0 = len(books.state_history())
    s0 = books.get_state()
    a, b = mk(DrawFacility, "L1", facility_id=LINE, amount_fen=1_000_000), \
        mk(DrawFacility, "L2", facility_id=LINE, amount_fen=2_000_000)
    ra, rb = workers.both(run(engine, [("execute", a)]), run(engine, [("execute", b)]))
    outs = ra["outcomes"] + rb["outcomes"]
    assert [o["status"] for o in outs] == ["EXECUTED", "EXECUTED"]
    raced(engine, ra, rb)
    state = books.get_state()
    assert fac(state, LINE).drawn_fen == 3_000_000 and state.cash_fen == s0.cash_fen + 3_000_000  # both, not one
    assert state.state_version == s0.state_version + 2
    journal = Journal()
    journal.add(*outs)
    finish(books, seed_books, journal, n0)


# ================================================================ 8. chain integrity under a burst


def test_8_a_burst_from_two_processes_keeps_one_contiguous_explained_chain(
        engine: Engine, books: Any, workers: WorkerPair) -> None:
    _seed_offer(books)
    n0 = len(books.state_history())
    [c] = books.commitments()
    left = [("execute", mk(DrawFacility, f"BL{i}", facility_id=LINE, amount_fen=3_000_000)) for i in range(4)]
    left += [("execute", mk(ReceivePayment, "BL-PAY", Actor.SYSTEM, receivable_id=RCV, amount_fen=1_000_000,
                            bank_reference="BK-BURST")), ("execute", accept_of(c))]
    right = [("execute", mk(DrawFacility, f"BR{i}", facility_id=LINE, amount_fen=3_000_000)) for i in range(4)]
    right += [("execute", mk(ReceivePayment, "BR-PAY", Actor.SYSTEM, receivable_id=RCV, amount_fen=1_000_000,
                             bank_reference="BK-BURST")), ("revoke", c.id)]
    ra, rb = workers.both(run(engine, left), run(engine, right))
    outs = ra["outcomes"] + rb["outcomes"]
    assert all("status" in o for o in outs), outs
    raced(engine, ra, rb)
    state = books.get_state()
    draws = [o for o in outs if o["action"][1:] and getattr(o["action"][1], "kind", "") == "DRAW_FACILITY"]
    assert len([o for o in draws if o["status"] == "EXECUTED"]) == 5  # ¥150,000 of room: five ¥30,000 draws
    assert fac(state, LINE).drawn_fen == 15_000_000 and lots_match_drawn(state)
    assert rcv(state, RCV).settled_fen == 1_000_000  # one bank event, booked once
    journal = Journal()
    journal.add(*outs)
    finish(books, _seed_offer, journal, n0)
