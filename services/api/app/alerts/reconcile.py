"""Receipt reconciliation: match every RECEIVE_PAYMENT in the operations log to the receivable it
settles and to any accepted commitment that changed what is owed (an early-pay discount).

Receipts are replayed in log order against what was outstanding O when each arrived (ADR-0006
section 4, red team e F4): an accepted early payment covers "up to F of face at rate d, paid on or before
day N". A receipt R on or before day N (the day it was reported when the owner approved an agent's report
later, F6) pays the whole-fen portion P <= what the agreement still covers (F less the portions already
paid early, at most O) with R = P − post(d × P), and settles face P; a second portion may follow until F
is used. Any other receipt settles its own amount. Statuses (one receipt of `received` on day D, an
accepted discount d on what the agreement still covers, P <= O):
- MATCHED           the agreed early payment for a portion (solved from R and verified exactly), or a
                    receipt of the whole outstanding amount.
- expected = O for every other receipt (outside the window, or no portion fits).
- SHORT_PAYMENT     received < P − d (or < O with no discount): a partial payment; the detail states
                    the residual still due on the original day.
- DISCOUNT_IGNORED  an accepted discount exists and the receipt does not follow it: the full portion
                    arrived inside the discount window (the supplier owes the agreed credit), or the
                    discount was deducted after the window closed.
- UNEXPECTED_AMOUNT anything else between P − d and O.
- UNMATCHED         the executor refused the receipt (no such receivable, already settled, above
                    what is outstanding ...): no open receivable or commitment explains the money.
`outstanding[].face_fen` is the amount still owed (face less settled).

`promised` is the other direction: every early payment a live commitment promised (an IMMEDIATE_DISCOUNT
naming a receivable, on an ACCEPTED, ACTIVE or FULFILLED commitment), as AWAITED, RECEIVED, LAPSED (its day
passed unpaid; the receivable is back on its due day) or SETTLED_OTHERWISE. Read-only: nothing is written.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.alerts.ledger import Entry, entries, head
from app.alerts.models import (
    MatchStatus,
    OutstandingReceivable,
    PromisedReceipt,
    PromiseStatus,
    ReceiptMatch,
    ReconciliationReport,
)
from app.books import current_books
from app.domain.models import (
    Commitment,
    CommitmentStatus,
    FinancialState,
    Obligation,
    ObligationType,
    OperationStatus,
    Receivable,
    ReceivePayment,
)
from app.domain.money import fmt_yuan
from app.domain.ports import LedgerStore
from app.financial.trajectory import early_pay_discount, early_pay_face

_AGREED = (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE, CommitmentStatus.FULFILLED)


def _agreed(c: Commitment) -> bool:
    """An agreement whose early payments are reconciled: a live or fulfilled one, or one the clock ended because its
    early payments lapsed (EXPIRED with `lapsed_obligations`, red team d F3, or with an obligation paid by a receipt
    reported in time and approved after the lapse, red team e F6); never an offer that expired unaccepted."""
    return c.status in _AGREED or (c.status == CommitmentStatus.EXPIRED
                                   and bool(c.lapsed_obligations or c.settled_obligations))


Used = dict[tuple[str, str], int]  # (commitment id, obligation id) -> face already settled early under it


@dataclass(frozen=True)
class _Leg:
    """An agreed early payment on a receivable and what it still covers when a receipt arrives."""

    commitment_id: str
    obligation: Obligation  # with its face filled in (`base.amount_fen`) for the arithmetic
    open_fen: int  # face it still covers: its face less portions already paid early, at most what is outstanding

    @property
    def key(self) -> tuple[str, str]:
        return self.commitment_id, self.obligation.id


def _leg(r: Receivable, commitments: list[Commitment], outstanding: int, used: Used) -> _Leg | None:
    """The agreed early-pay obligation on receivable r that still covers some face (red team e, F4: an agreement
    covers "up to" its face, portion by portion, until the face is used)."""
    for c in commitments:
        if not _agreed(c):
            continue
        for o in c.obligations:
            if o.type != ObligationType.IMMEDIATE_DISCOUNT or (o.rate_bp is None and o.amount_fen is None):
                continue
            named = o.base.receivable_id == r.id
            by_face = o.base.receivable_id is None and o.counterparty_id == r.counterparty_id \
                and o.base.amount_fen == r.face_fen
            if not (named or by_face):
                continue
            face = o.base.amount_fen if named and o.base.amount_fen else outstanding if named else r.face_fen
            calc = o if o.base.amount_fen else o.model_copy(
                update={"base": o.base.model_copy(update={"amount_fen": face})})
            open_fen = min(face - used.get((c.id, o.id), 0), outstanding)
            if open_fen <= 0:
                continue
            return _Leg(c.id, calc, open_fen)
    return None


def _terms(o: Obligation, portion: int, d: int) -> str:
    if o.rate_bp is not None:
        return f"{fmt_yuan(portion)} × {o.rate_bp} bp = {fmt_yuan(d)}"
    return f"fixed discount {fmt_yuan(o.amount_fen or 0)} on {fmt_yuan(o.base.amount_fen or 0)}: {fmt_yuan(d)} on " \
           f"{fmt_yuan(portion)}"


def _match(e: Entry, op: ReceivePayment, r: Receivable, commitments: list[Commitment], settled: int,
           used: Used) -> tuple[ReceiptMatch, int, tuple[str, str] | None]:
    """The match, the face this receipt settled (so the caller can replay the next receipt), and the early-pay
    obligation it paid (if any). The executor's rule (`_early_pay_match`): a receipt R on or before the promised day
    pays the portion P <= what the agreement still covers with R = P − post(d × P); the deadline is tested on the
    day the receipt was reported (`reported_day`, a queued report approved later), else the day it was booked."""
    face, received = r.face_fen, op.amount_fen
    day = op.reported_day if op.reported_day is not None else e.day
    outstanding = face - settled
    leg = _leg(r, commitments, outstanding, used)
    cid = leg.commitment_id if leg is not None else None
    settle_by = leg.obligation.effective_day if leg is not None else None
    window = settle_by if settle_by is not None else r.due_day
    in_window = day is not None and day <= window
    when = (f"reported day {day}, booked day {e.day}" if op.reported_day is not None and op.reported_day != e.day
            else f"day {day}")
    if leg is not None and in_window:
        p = early_pay_face(leg.obligation, received, leg.open_fen)
        if p is not None:  # the agreed early payment for a portion P of face
            d = p - received
            used[leg.key] = used.get(leg.key, 0) + p
            left = leg.open_fen - p
            more = f"; up to {fmt_yuan(left)} more may be settled early by day {window}" if left > 0 else ""
            match = ReceiptMatch(
                seq=e.seq, entry_hash=e.entry_hash, op_id=op.op_id, day=e.day, receivable_id=r.id,
                counterparty_id=r.counterparty_id, received_fen=received, face_fen=face, agreed_discount_fen=d,
                expected_fen=received, difference_fen=0, commitment_id=cid, bank_reference=op.bank_reference,
                status=MatchStatus.MATCHED, flagged=False,
                detail=f"agreed early payment for {fmt_yuan(p)} of face (commitment {cid}){more}",
                formula=(f"P − post(d × P) = received, paid by day {window} ({when}): {_terms(leg.obligation, p, d)}; "
                         f"{fmt_yuan(p)} − {fmt_yuan(d)} = {fmt_yuan(received)}"))
            return match, p, leg.key
    portion = leg.open_fen if leg is not None else 0
    d = early_pay_discount(leg.obligation, portion) if leg is not None else 0
    dformula = _terms(leg.obligation, portion, d) if leg is not None else "no accepted discount"
    floor = portion - d if d else outstanding
    expected = floor if d and in_window else outstanding
    if received == expected:
        status, detail = MatchStatus.MATCHED, "amount equals what the accepted terms say is owed"
    elif received < floor:
        status = MatchStatus.SHORT_PAYMENT
        detail = (f"partial payment: short by {fmt_yuan(floor - received)} against "
                  f"{'face less the agreed discount' if d else 'what is outstanding'}; "
                  f"{fmt_yuan(outstanding - received)} of {r.id} still due")
    elif d and received == portion and in_window:
        status = MatchStatus.DISCOUNT_IGNORED
        detail = (f"full face paid inside the discount window of accepted commitment {cid}; "
                  f"the agreed {fmt_yuan(d)} credit is still owed to the buyer")
    elif d and received == floor and not in_window:
        status = MatchStatus.DISCOUNT_IGNORED
        detail = (f"discount of {fmt_yuan(d)} deducted on day {day}, after the window closed on day {window} "
                  f"(commitment {cid})")
    else:
        status, detail = MatchStatus.UNEXPECTED_AMOUNT, "amount matches neither the face nor the discounted face"
    # Not an agreed early payment (outside the window, or no portion fits): a plain receipt that settles its own
    # amount; a late receipt of the discounted amount leaves the difference due (FINANCIAL_SEMANTICS §2).
    match = ReceiptMatch(
        seq=e.seq, entry_hash=e.entry_hash, op_id=op.op_id, day=e.day, receivable_id=r.id,
        counterparty_id=r.counterparty_id, received_fen=received, face_fen=face, agreed_discount_fen=d,
        expected_fen=expected, difference_fen=received - expected, commitment_id=cid, bank_reference=op.bank_reference,
        status=status,
        flagged=status != MatchStatus.MATCHED, detail=detail,
        formula=(f"expected = face − discount if paid by day {window} else outstanding = {fmt_yuan(expected)} "
                 f"(outstanding {fmt_yuan(outstanding)} of face {fmt_yuan(face)}; discount {dformula}); "
                 f"received {fmt_yuan(received)} ({when})"),
    )
    return match, received, None


def _promises(state: FinancialState, commitments: list[Commitment],
              paid: dict[tuple[str, str], list[ReceiptMatch]]) -> list[PromisedReceipt]:
    """What each live early-pay commitment promised and what became of it (ADR-0006 sections 3 and 4).
    `paid` maps (commitment id, obligation id) to the receipts the replay matched to it, portion by portion; a row
    with receipts shows the face they paid early (red team e, F4)."""
    books = current_books(state, commitments)
    receivables = {r.id: r for r in state.receivables}
    lapsed = {(lp.commitment_id, lp.obligation.id): lp.reason for lp in books.lapsed}
    rows: list[PromisedReceipt] = []
    for c in commitments:
        if not _agreed(c):
            continue
        for o in c.obligations:
            rid = o.base.receivable_id
            r = receivables.get(rid) if rid else None
            if o.type != ObligationType.IMMEDIATE_DISCOUNT or rid is None or r is None:
                continue
            if o.rate_bp is None and o.amount_fen is None:
                continue
            hits = [h for h in paid.get((c.id, o.id), []) if h.receivable_id == rid]
            fulfilled = c.status == CommitmentStatus.FULFILLED
            day = o.effective_day
            when = f"day {day}" if day is not None else "its due day"
            if hits:
                d = sum(h.agreed_discount_fen for h in hits)
                portion = sum(h.received_fen for h in hits) + d
                parts = " + ".join(fmt_yuan(h.received_fen + h.agreed_discount_fen) for h in hits)
                formula = (f"face paid early {parts} = {fmt_yuan(portion)} at the agreed terms, discount "
                           f"{fmt_yuan(d)}; " if len(hits) > 1 else f"{_terms(o, portion, d)}; ")
            else:
                settled = fulfilled or lapsed.get((c.id, o.id)) == "RECEIVABLE_SETTLED"
                portion = o.base.amount_fen or (r.face_fen if settled else r.outstanding_fen)
                d = early_pay_discount(o, portion)
                formula = (f"{fmt_yuan(portion)} × {o.rate_bp} bp = {fmt_yuan(d)}; "
                           if o.rate_bp is not None else f"fixed discount {fmt_yuan(d)} on {fmt_yuan(portion)}; ")
            expected = portion - d
            formula += f"{fmt_yuan(portion)} − {fmt_yuan(d)} = {fmt_yuan(expected)}"
            seq: int | None = None
            if hits or fulfilled:
                status = PromiseStatus.RECEIVED
                seq = hits[-1].seq if hits else None
                detail = f"the agreed {fmt_yuan(expected)} for {rid} arrived (commitment {c.id})"
                agreed_face = o.base.amount_fen or 0
                if hits and agreed_face and portion < agreed_face:
                    detail = (f"the agreed {fmt_yuan(expected)} for {fmt_yuan(portion)} of the {fmt_yuan(agreed_face)} "
                              f"agreed for early settlement of {rid} arrived (commitment {c.id}); the other "
                              f"{fmt_yuan(agreed_face - portion)} " + (
                                  f"may still be settled early by {when}" if o in books.obligations else
                                  "is due on the invoice's own day"))
            elif (c.id, o.id) in lapsed or o in books.obligations:
                reason = lapsed.get((c.id, o.id))
                if reason is None:
                    status = PromiseStatus.AWAITED
                    detail = (f"{fmt_yuan(expected)} promised for {rid} by {when} under commitment {c.id}; "
                              f"the day has not passed")
                elif reason == "RECEIVABLE_SETTLED":
                    status = PromiseStatus.SETTLED_OTHERWISE
                    detail = (f"{rid} was settled without the agreed {fmt_yuan(expected)} early payment "
                              f"(commitment {c.id})")
                else:
                    status = PromiseStatus.LAPSED
                    detail = (f"{fmt_yuan(expected)} promised for {when} under commitment {c.id} did not arrive; "
                              f"{fmt_yuan(r.outstanding_fen)} of {rid} is still outstanding and falls back to its "
                              f"original due day, day {r.due_day}")
                    if reason != "EARLY_PAYMENT_MISSED":
                        detail += f" (lapsed: {reason})"
            else:
                continue
            rows.append(PromisedReceipt(
                commitment_id=c.id, obligation_id=o.id, receivable_id=rid, counterparty_id=o.counterparty_id,
                promised_day=day, face_fen=portion, discount_fen=d, expected_fen=expected, status=status,
                receipt_seq=seq, detail=detail, formula=formula))
    rows.sort(key=lambda p: (p.promised_day is None, p.promised_day or 0, p.commitment_id, p.obligation_id))
    return rows


def reconcile(store: LedgerStore, day: int | None = None) -> ReconciliationReport:
    """Match the log's receipts; `day` (the simulated clock) marks outstanding receivables past due."""
    state = store.get_state()
    commitments = store.commitments()
    receivables = {r.id: r for r in state.receivables}
    log = entries(store)
    receipts: list[ReceiptMatch] = []
    settled: dict[str, int] = {}  # face settled so far per receivable, replayed from the log
    used: Used = {}  # face already paid early under each agreed early-pay obligation, replayed from the log
    paid: dict[tuple[str, str], list[ReceiptMatch]] = {}  # the receipts that paid each of them, portion by portion
    for e in log:
        op = e.op
        if not isinstance(op, ReceivePayment) or e.result.status in (OperationStatus.DUPLICATE,
                                                                     OperationStatus.PENDING_APPROVAL):
            continue
        r = receivables.get(op.receivable_id)
        if e.result.status == OperationStatus.EXECUTED and r is not None:
            m, face_settled, leg = _match(e, op, r, commitments, settled.get(r.id, 0), used)
            if leg is not None:
                paid.setdefault(leg, []).append(m)
            settled[r.id] = settled.get(r.id, 0) + face_settled
            receipts.append(m)
            continue
        why = "; ".join(v.message for v in e.result.violations) or e.result.message
        receipts.append(ReceiptMatch(
            seq=e.seq, entry_hash=e.entry_hash, op_id=op.op_id, day=e.day, receivable_id=op.receivable_id,
            counterparty_id=r.counterparty_id if r else None, received_fen=op.amount_fen,
            face_fen=r.face_fen if r else None, expected_fen=None, difference_fen=None,
            bank_reference=op.bank_reference, status=MatchStatus.UNMATCHED, flagged=True,
            detail=f"no open receivable or commitment explains this receipt ({why})",
            formula="receipt not booked by the executor; nothing to match it against",
        ))
    days = [e.day for e in log if e.day is not None]
    today = day if day is not None else (max(days) if days else 0)
    outstanding = [
        OutstandingReceivable(receivable_id=r.id, counterparty_id=r.counterparty_id,
                              face_fen=r.outstanding_fen, due_day=r.due_day, status=r.status, past_due=r.due_day < today)
        for r in state.receivables if r.status in ("OPEN", "FINANCED")
    ]
    promised = _promises(state, commitments, paid)
    return ReconciliationReport(
        as_of_day=today,
        receipts=receipts,
        outstanding=outstanding,
        matched=sum(1 for m in receipts if not m.flagged),
        flagged=sum(1 for m in receipts if m.flagged),
        received_total_fen=sum(m.received_fen for m in receipts if m.status != MatchStatus.UNMATCHED),
        expected_total_fen=sum(m.expected_fen or 0 for m in receipts),
        chain_head_hash=head(store),
        chain_valid=store.verify_chain(),
        promised=promised,
        lapsed_promises=sum(1 for p in promised if p.status == PromiseStatus.LAPSED),
    )
