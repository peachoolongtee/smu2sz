"""GET /nav/counts: how many things in each Business section need the owner now, for the sidebar's badges. Cheap by design: the stores are
read once, the decision record is derived without the alerts (so no projection and no router run), and nothing is priced."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_owner
from app.api.deal_offers import needs_you, open_offers
from app.api.runtime import get_runtime
from app.domain.models import DocumentKind, DocumentStatus
from app.persistence import ApprovalStatus

router = APIRouter(dependencies=[Depends(require_owner)])


@router.get("/nav/counts")
def nav_counts(lang: str = "en") -> dict:
    """`deals` (buyers with something waiting for the owner, as `GET /deals` says by `needs_you`), `approvals` (approvals pending) and
    `receivables` (invoices past their due day with money still owed). `lang` is accepted for symmetry with the other reads; the
    answer holds numbers only."""
    from app.api.decisions import load_context

    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    with rt.lock:
        ctx = load_context(rt, found=[])
        waiting_docs = {r.counterparty_id for r in rt.store.contract_guard_rows()
                        if r.kind == DocumentKind.BUYER_CONTRACT.value and r.status == DocumentStatus.PROPOSED.value}
        offers = open_offers(ctx, lang)
        buyers = [c.id for c in ctx.state.counterparties if c.role == "BUYER"]
        deals = sum(1 for cp in buyers if needs_you(ctx, offers.get(cp, (None, None))[1], cp, cp in waiting_docs, lang)[0])
        approvals = sum(1 for a in ctx.approvals if a.status == ApprovalStatus.PENDING)
        late = sum(1 for r in ctx.state.receivables if r.status != "SETTLED" and r.outstanding_fen > 0 and r.due_day < ctx.today)
    return {"lang": lang, "day": ctx.today, "deals": deals, "approvals": approvals, "receivables": late}
