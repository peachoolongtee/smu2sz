"""Receipt reconciliation: match every RECEIVE_PAYMENT in the operations log to the receivable it
settles and to any accepted commitment that changed what is owed (an early-pay discount).

Receipts are replayed in log order against what was outstanding O when each arrived (ADR-0006
section 4): a receipt equal to the agreed `P − d` settles face P and uses up its commitment; any other
receipt settles its own amount. Statuses (one receipt of `received` on day D, an unused accepted
discount d on a portion P <= O):
- expected = P − d when D is on or before the discount's settlement day (its effective day, else the
  due day); otherwise expected = O.
- MATCHED           received == expected: the agreed early-pay amount for its portion, or the whole
                    outstanding amount.
- SHORT_PAYMENT     received < P − d (or < O with no discount): a partial payment; the detail states
                    the residual still due on the original day.
- DISCOUNT_IGNORED  an accepted discount exists and the receipt does not follow it: the full portion
                    arrived inside the discount window (the supplier owes the agreed credit), or the
                    discount was deducted after the window closed.
- UNEXPECTED_AMOUNT anything else between P − d and O.
- UNMATCHED         the executor refused the receipt (no such receivable, already settled, above
                    what is outstanding ...): no open receivable or commitment explains the money.
`outstanding[].face_fen` is the amount still owed (face less settled).
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


def _discount(r: Receivable, commitments: list[Commitment], outstanding: int,
              used: set[str]) -> tuple[int, int, int | None, str | None, str]:
    """(agreed discount fen, portion P it covers, settlement day, commitment id, formula) for the unused
    accepted discount on receivable r whose portion still fits inside what is outstanding."""
    for c in commitments:
        if c.status not in _AGREED or c.id in used:
            continue
        for o in c.obligations:
            if o.type != ObligationType.IMMEDIATE_DISCOUNT:
                continue
            named = o.base.receivable_id == r.id
            by_face = o.base.receivable_id is None and o.counterparty_id == r.counterparty_id \
                and o.base.amount_fen == r.face_fen
            if not (named or by_face):
                continue
            portion = o.base.amount_fen if named and o.base.amount_fen else outstanding if named else r.face_fen
            if portion > outstanding:
                continue
            if o.rate_bp is not None:
                d = post(bp(o.rate_bp) * portion)
                formula = f"{fmt_yuan(portion)} × {o.rate_bp} bp = {fmt_yuan(d)}"
            else:
                d = o.amount_fen or 0
                formula = f"fixed discount {fmt_yuan(d)}"
            return d, portion, o.effective_day, c.id, formula
    return 0, 0, None, None, "no accepted discount"


def _match(e: Entry, op: ReceivePayment, r: Receivable, commitments: list[Commitment], settled: int,
           used: set[str]) -> tuple[ReceiptMatch, int]:
    """The match, and the face this receipt settled (so the caller can replay the next receipt)."""
    face, received, day = r.face_fen, op.amount_fen, e.day
    outstanding = face - settled
    d, portion, settle_by, cid, dformula = _discount(r, commitments, outstanding, used)
    window = settle_by if settle_by is not None else r.due_day
    in_window = day is not None and day <= window
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
    agreed = cid is not None and bool(d) and received == floor  # the executor fulfils the commitment on this amount
    if agreed and cid is not None:
        used.add(cid)
    match = ReceiptMatch(
        seq=e.seq, entry_hash=e.entry_hash, op_id=op.op_id, day=day, receivable_id=r.id,
        counterparty_id=r.counterparty_id, received_fen=received, face_fen=face, agreed_discount_fen=d,
        expected_fen=expected, difference_fen=received - expected, commitment_id=cid, status=status,
        flagged=status != MatchStatus.MATCHED, detail=detail,
        formula=(f"expected = face − discount if paid by day {window} else outstanding = {fmt_yuan(expected)} "
                 f"(outstanding {fmt_yuan(outstanding)} of face {fmt_yuan(face)}; discount {dformula}); "
                 f"received {fmt_yuan(received)}"),
    )
    return match, portion if agreed else received


def reconcile(store: LedgerStore, day: int | None = None) -> ReconciliationReport:
    """Match the log's receipts; `day` (the simulated clock) marks outstanding receivables past due."""
    state = store.get_state()
    commitments = store.commitments()
    receivables = {r.id: r for r in state.receivables}
    log = entries(store)
    receipts: list[ReceiptMatch] = []
    settled: dict[str, int] = {}  # face settled so far per receivable, replayed from the log
    used: set[str] = set()  # commitments whose agreed amount a receipt has already paid
    for e in log:
        op = e.op
        if not isinstance(op, ReceivePayment) or e.result.status in (OperationStatus.DUPLICATE,
                                                                     OperationStatus.PENDING_APPROVAL):
            continue
        r = receivables.get(op.receivable_id)
        if e.result.status == OperationStatus.EXECUTED and r is not None:
            m, face_settled = _match(e, op, r, commitments, settled.get(r.id, 0), used)
            settled[r.id] = settled.get(r.id, 0) + face_settled
            receipts.append(m)
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
        OutstandingReceivable(receivable_id=r.id, counterparty_id=r.counterparty_id,
                              face_fen=r.outstanding_fen, due_day=r.due_day, status=r.status, past_due=r.due_day < today)
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
