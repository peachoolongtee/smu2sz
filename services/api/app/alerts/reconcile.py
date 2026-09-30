"""Receipt reconciliation: match every RECEIVE_PAYMENT in the operations log to the receivable it
settles and to any accepted commitment that changed what is owed (an early-pay discount).

Statuses (one receipt of `received` on day D for a receivable of face F, agreed discount d):
- expected = F − d when an accepted discount applies and D is on or before its settlement day
  (its effective day, else the due day); otherwise expected = F.
- MATCHED           received == expected.
- SHORT_PAYMENT     received < F − d: the buyer paid less than even the discounted amount.
- DISCOUNT_IGNORED  an accepted discount exists and the receipt does not follow it: the full face
                    arrived inside the discount window (the supplier owes the agreed credit), or the
                    discount was deducted after the window closed.
- UNEXPECTED_AMOUNT anything else between F − d and F.
- UNMATCHED         the executor refused the receipt (no such receivable, already settled, above
                    face ...): no open receivable or commitment explains the money.
"""

from __future__ import annotations

from app.alerts.ledger import Entry, entries, head
from app.alerts.models import MatchStatus, OutstandingReceivable, ReceiptMatch, ReconciliationReport
from app.domain.models import (
    Commitment,
    CommitmentStatus,
    ObligationType,
    OperationStatus,
    Receivable,
    ReceivePayment,
)
from app.domain.money import bp, fmt_yuan, post
from app.domain.ports import LedgerStore

_AGREED = (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE, CommitmentStatus.FULFILLED)


def _discount(r: Receivable, commitments: list[Commitment]) -> tuple[int, int | None, str | None, str]:
    """(agreed discount fen, settlement day, commitment id, formula) for receivable r."""
    for c in commitments:
        if c.status not in _AGREED:
            continue
        for o in c.obligations:
            if o.type != ObligationType.IMMEDIATE_DISCOUNT:
                continue
            named = o.base.receivable_id == r.id
            by_face = o.base.receivable_id is None and o.counterparty_id == r.counterparty_id \
                and o.base.amount_fen == r.face_fen
            if not (named or by_face):
                continue
            portion = o.base.amount_fen if named and o.base.amount_fen is not None else r.face_fen
            if o.rate_bp is not None:
                d = post(bp(o.rate_bp) * portion)
                formula = f"{fmt_yuan(portion)} × {o.rate_bp} bp = {fmt_yuan(d)}"
            else:
                d = o.amount_fen or 0
                formula = f"fixed discount {fmt_yuan(d)}"
            return d, o.effective_day, c.id, formula
    return 0, None, None, "no accepted discount"


def _match(e: Entry, op: ReceivePayment, r: Receivable, commitments: list[Commitment]) -> ReceiptMatch:
    face, received, day = r.face_fen, op.amount_fen, e.day
    d, settle_by, cid, dformula = _discount(r, commitments)
    window = settle_by if settle_by is not None else r.due_day
    in_window = day is not None and day <= window
    expected = face - d if d and in_window else face
    floor = face - d
    if received == expected:
        status, detail = MatchStatus.MATCHED, "amount equals what the accepted terms say is owed"
    elif received < floor:
        status = MatchStatus.SHORT_PAYMENT
        detail = f"short by {fmt_yuan(floor - received)} against face less the agreed discount"
    elif d and received == face and in_window:
        status = MatchStatus.DISCOUNT_IGNORED
        detail = (f"full face paid inside the discount window of accepted commitment {cid}; "
                  f"the agreed {fmt_yuan(d)} credit is still owed to the buyer")
    elif d and received == floor and not in_window:
        status = MatchStatus.DISCOUNT_IGNORED
        detail = (f"discount of {fmt_yuan(d)} deducted on day {day}, after the window closed on day {window} "
                  f"(commitment {cid})")
    else:
        status, detail = MatchStatus.UNEXPECTED_AMOUNT, "amount matches neither the face nor the discounted face"
    return ReceiptMatch(
        seq=e.seq, entry_hash=e.entry_hash, op_id=op.op_id, day=day, receivable_id=r.id,
        counterparty_id=r.counterparty_id, received_fen=received, face_fen=face, agreed_discount_fen=d,
        expected_fen=expected, difference_fen=received - expected, commitment_id=cid, status=status,
        flagged=status != MatchStatus.MATCHED, detail=detail,
        formula=(f"expected = face − discount if paid by day {window} else face = {fmt_yuan(expected)} "
                 f"(face {fmt_yuan(face)}; discount {dformula}); received {fmt_yuan(received)}"),
    )


def reconcile(store: LedgerStore, day: int | None = None) -> ReconciliationReport:
    """Match the log's receipts; `day` (the simulated clock) marks outstanding receivables past due."""
    state = store.get_state()
    commitments = store.commitments()
    receivables = {r.id: r for r in state.receivables}
    log = entries(store)
    receipts: list[ReceiptMatch] = []
    for e in log:
        op = e.op
        if not isinstance(op, ReceivePayment) or e.result.status in (OperationStatus.DUPLICATE,
                                                                     OperationStatus.PENDING_APPROVAL):
            continue
        r = receivables.get(op.receivable_id)
        if e.result.status == OperationStatus.EXECUTED and r is not None:
            receipts.append(_match(e, op, r, commitments))
            continue
        why = "; ".join(v.message for v in e.result.violations) or e.result.message
        receipts.append(ReceiptMatch(
            seq=e.seq, entry_hash=e.entry_hash, op_id=op.op_id, day=e.day, receivable_id=op.receivable_id,
            counterparty_id=r.counterparty_id if r else None, received_fen=op.amount_fen,
            face_fen=r.face_fen if r else None, expected_fen=None, difference_fen=None,
            status=MatchStatus.UNMATCHED, flagged=True,
            detail=f"no open receivable or commitment explains this receipt ({why})",
            formula="receipt not booked by the executor; nothing to match it against",
        ))
    days = [e.day for e in log if e.day is not None]
    today = day if day is not None else (max(days) if days else 0)
    outstanding = [
        OutstandingReceivable(receivable_id=r.id, counterparty_id=r.counterparty_id, face_fen=r.face_fen,
                              due_day=r.due_day, status=r.status, past_due=r.due_day < today)
        for r in state.receivables if r.status in ("OPEN", "FINANCED")
    ]
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
    )
