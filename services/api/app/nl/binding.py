"""The owner's page, bound to the chat (wayfinder #65, F08): a validated, read-only context.

The browser names what its page shows by id (`NlPageContext`: an offer, a decision, an invoice, a last-visit day).
The server looks every id up in its own stores and keeps only what it finds; it never reads an amount, a sentence or a
verdict from the request. A valid offer seeds the session's last offer and verdict, so the explain intents answer about
the deal the page already evaluated. Nothing here evaluates, decides or executes; an unknown id is simply ignored, which
leaves the turn exactly as if no context had been sent.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.domain.models import FinancialState, Verdict
from app.domain.ports import LedgerStore
from app.nl.models import ContextEcho, NlPageContext
from app.nl.sessions import Session

# GET /home as a function of (lang, since_day): injected by the API layer, which owns the presentation helpers. None
# when the read cannot be made (the books cannot be projected); a read intent then says so instead of guessing.
HomeRead = Callable[[str, "int | None"], "dict[str, Any] | None"]
# business_text(text, lang): the same "day 47" -> "in 47 days" rewrite the Business pages use; identity when unwired.
Words = Callable[[str, str], str]


@dataclass(frozen=True)
class OwnerReads:
    """What the API layer lends the owner's chat: the Home read, the business-words rewrite and the runtime's map of
    each offer's latest verdict. Owner channel only; a counterparty turn never receives it."""

    home: HomeRead
    words: Words = lambda text, lang: text
    latest_verdict: Mapping[str, str] | None = None
    business: bool = False  # the request asked for Business words (POST /nl?mode=business): see app/nl/business.py


@dataclass(frozen=True)
class Binding:
    """The context the server accepted for one turn (every field was found in the stores)."""

    page: str
    offer_id: str | None = None
    verdict_id: str | None = None
    counterparty_name: str | None = None
    invoice_id: str | None = None
    received_day: int | None = None  # the day the offer arrived; "evaluated today" when it is the runtime's day
    since_day: int | None = None

    @property
    def echo(self) -> ContextEcho | None:
        if not (self.offer_id or self.verdict_id or self.invoice_id):
            return None
        return ContextEcho(offer_id=self.offer_id, counterparty_name=self.counterparty_name,
                           decision_id=self.verdict_id, invoice_id=self.invoice_id)


def _verdict_for(store: LedgerStore, offer_id: str, latest: Mapping[str, str] | None) -> Verdict | None:
    """The verdict the page evaluated: the runtime's latest for the offer (what /negotiate trusts), else the most
    recently stored verdict on that offer (the runtime's map is empty after a restart)."""
    vid = latest.get(offer_id) if latest else None
    found = store.get_verdict(vid) if vid else None
    if found is not None and found.offer_id == offer_id:
        return found
    return next((v for v in reversed(store.verdicts()) if v.offer_id == offer_id), None)


def resolve(store: LedgerStore, ctx: NlPageContext | None, *, day: int, state: FinancialState,
            latest_verdict: Mapping[str, str] | None = None) -> Binding | None:
    """Validate the page context against the stores. None when nothing was sent."""
    if ctx is None:
        return None
    offer = store.get_offer(ctx.offer_id) if ctx.offer_id else None
    verdict: Verdict | None = None
    if ctx.decision_id:
        named = store.get_verdict(ctx.decision_id)
        # a decision that belongs to a different offer than the one named is not one the page can be showing
        if named is not None and (offer is None or named.offer_id == offer.offer_id):
            verdict = named
            offer = offer or store.get_offer(named.offer_id)
    if verdict is None and offer is not None:
        verdict = _verdict_for(store, offer.offer_id, latest_verdict)
    if verdict is not None and offer is None:
        offer = store.get_offer(verdict.offer_id)
    if offer is None or verdict is None or verdict.offer_id != offer.offer_id:
        offer, verdict = None, None  # a deal is bound only with its verdict; half of one explains nothing
    invoice = next((r.id for r in state.receivables if r.id == ctx.invoice_id), None) if ctx.invoice_id else None
    name = None
    if offer is not None:
        name = next((c.name for c in state.counterparties if c.id == offer.counterparty_id), None)
    since = ctx.since_day if ctx.since_day is not None and ctx.since_day <= day else None
    return Binding(page=ctx.page, offer_id=offer.offer_id if offer else None, verdict_id=verdict.id if verdict else None,
                   counterparty_name=name, invoice_id=invoice, received_day=offer.received_day if offer else None,
                   since_day=since)


def apply(session: Session, binding: Binding | None) -> None:
    """Point the session at the page's deal, once per decision: the owner may then evaluate something else in the chat
    and keep talking about it, until the page shows a different decision."""
    if binding is None or binding.verdict_id is None:
        return
    if session.bound_verdict_id == binding.verdict_id and session.last_verdict_id is not None:
        return
    session.bound_verdict_id = binding.verdict_id
    session.last_offer_id = binding.offer_id
    session.last_verdict_id = binding.verdict_id
