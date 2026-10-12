"""GET /receivables: the receivable rows with what each invoice nets, who governs it and what to do next (map #88, ticket #107).

Owner only, no flag, read-only. Every figure is derived from the books (`app.strategy.net`, `app.strategy.receivable_rows`) and every
sentence is written here for `lang`; the web computes nothing. Additive to the receivables block of Home and to
`GET /receivables/worth`: nothing there is renamed. The rows are the receivables still to collect (OPEN or FINANCED with
something outstanding), due first; the summary carries the outstanding total, the next expected receipt and the sum of the nets.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException

from app.alerts import reconcile
from app.alerts.models import PromiseStatus
from app.api.auth import require_owner
from app.api.display import displayed
from app.api.home import Partial
from app.api.presentation import last_read
from app.api.runtime import get_runtime
from app.books import current_books
from app.domain.models import CommitmentStatus, DocumentKind, DocumentStatus
from app.financial import EngineError
from app.strategy.receivable_rows import OpenOffer, receivable_rows

router = APIRouter(tags=["receivables"], dependencies=[Depends(require_owner)])


def _contract_refs(records: list[Any]) -> dict[str, str]:
    """The agreement number of each buyer's confirmed, current contract (the one no later contract replaced)."""
    out: dict[str, str] = {}
    for rec in records:
        if (rec.kind == DocumentKind.BUYER_CONTRACT and rec.status == DocumentStatus.CONFIRMED and rec.superseded_by is None
                and rec.contract is not None):
            ref = next((x.text for x in rec.contract.terms if x.field.value == "CONTRACT_REFERENCE" and x.text), None)
            if ref:
                out[rec.counterparty_id] = ref
    return out


def _financing_repaid(store: Any) -> frozenset[str]:
    """The receivables whose advance a receipt cleared, from the log: the executed receipt's own sentence says "repaid advance ..."
    (the books keep no trace on the invoice once the lot is gone). A row of the log that cannot be read is skipped."""
    out: set[str] = set()
    for rec in store.operations():
        if rec.kind != "RECEIVE_PAYMENT":
            continue
        try:
            result, payload = json.loads(rec.result_json), json.loads(rec.payload_json)
        except ValueError:
            continue
        if result.get("status") == "EXECUTED" and "repaid advance" in str(result.get("message") or "") and payload.get("receivable_id"):
            out.add(str(payload["receivable_id"]))
    return frozenset(out)


@router.get("/receivables")
def get_receivables(lang: Literal["en", "zh"] = "en") -> dict[str, Any]:
    rt = get_runtime()
    with rt.lock:
        state, store = rt.store.get_state(), rt.store
        today = max(rt.day, state.as_of_day)
        commitments = store.commitments()
        try:
            books = current_books(state, commitments)
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None
        partial = Partial()
        try:  # a supporting read: the rows stand without the promises, and say so
            report = reconcile(store, day=today)
            missed = frozenset(p.receivable_id for p in report.promised if p.status == PromiseStatus.LAPSED)
        except Exception:
            logging.getLogger("termsledger.decisions").exception("the reconciliation could not be read for the receivables")
            partial.add("reconciliation")
            missed = frozenset()
        taken = {c.offer_id for c in commitments if c.status != CommitmentStatus.REVOKED}
        latest = {}
        for v in store.verdicts():  # the last verdict stored for each offer, newest offer first
            latest[v.offer_id] = v
        open_offers = []
        for offer_id, verdict in reversed(list(latest.items())):
            offer = store.get_offer(offer_id)
            if offer is not None and offer_id not in taken:
                open_offers.append(OpenOffer(offer_id, offer.counterparty_id, verdict))
        refs = _contract_refs(store.contract_records())
        body = receivable_rows(state, today, lang, books=books, commitments=commitments, promise_missed=missed,
                               financing_repaid=_financing_repaid(store),
                               open_offers=open_offers, contract_refs=refs)
    return displayed({"day": today, "lang": lang, "state_version": state.state_version, **body, "partial": partial.view(lang),
                      **last_read(today, lang)})
