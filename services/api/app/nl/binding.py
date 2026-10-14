"""The owner's page, bound to the chat (wayfinder #65, F08): a validated, read-only context.

The browser names what its page shows by id (`NlPageContext`: an offer, a decision, an invoice, a last-visit day).
The server looks every id up in its own stores and keeps only what it finds; it never reads an amount, a sentence or a
verdict from the request. A valid offer seeds the session's last offer and verdict, so the explain intents answer about
the deal the page already evaluated. Nothing here evaluates, decides or executes; an unknown id is simply ignored, which
leaves the turn exactly as if no context had been sent.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.decisions.identity import offer_id_of
from app.domain.models import FinancialState, Verdict
from app.domain.ports import LedgerStore
from app.nl.models import ContextEcho, NlPageContext, NlScope, ScopeUsed
from app.nl.sessions import Session

# GET /home as a function of (lang, since_day): injected by the API layer, which owns the presentation helpers. None
# when the read cannot be made (the books cannot be projected); a read intent then says so instead of guessing.
HomeRead = Callable[[str, "int | None"], "dict[str, Any] | None"]
# business_text(text, lang): the same "day 47" -> "in 47 days" rewrite the Business pages use; identity when unwired.
Words = Callable[[str, str], str]
# The Deals queue (app/api/worklist.py `queue`) for a language: the rows that need the owner and the rows that wait on someone else. None when it cannot be read.
QueueRead = Callable[[str], "dict[str, Any] | None"]


@dataclass(frozen=True)
class OwnerReads:
    """What the API layer lends the owner's chat: the Home read, the business-words rewrite and the runtime's map of
    each offer's latest verdict. Owner channel only; a counterparty turn never receives it."""

    home: HomeRead
    words: Words = lambda text, lang: text
    latest_verdict: Mapping[str, str] | None = None
    queue: QueueRead = lambda lang: None
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


# ---------------------------------------------------------------- the scope of the question (the URL contract, ticket #130)

_SCENARIO = re.compile(r"asked|counter:[0-9]{1,3}")


@dataclass(frozen=True)
class ScopeResult:
    """The scope a request named, checked against the stores: what it is (`used`), the buyer it belongs to, the ids the turn is bound to
    (`offer_id`, `invoice_id`), or the sentence that asks which one the owner means (`clarification`) when the server cannot honour it."""

    used: ScopeUsed | None
    customer_id: str | None = None
    offer_id: str | None = None
    invoice_id: str | None = None
    clarification: str | None = None

    def context(self, sent: NlPageContext | None) -> NlPageContext:
        """The page context of the turn: the page and the last-visit day the request sent, and the scope's own offer and invoice. The ids the
        page sent are dropped: a stale prior offer never answers a scoped question."""
        return NlPageContext(page=sent.page if sent is not None else "/", offer_id=self.offer_id, invoice_id=self.invoice_id,
                             since_day=sent.since_day if sent is not None else None)


def _say(lang: str, en: str, zh: str) -> str:
    return zh if lang == "zh" else en


def _short(name: str) -> str:
    words = name.replace(",", " ").split()
    return words[0] if words else name


def resolve_scope(store: LedgerStore, scope: NlScope, *, state: FinancialState, lang: str) -> ScopeResult:
    """Check a scope against the stores. The most specific key names the scope (a decision, else an invoice, else a customer, else the whole
    company); the others must belong to it. A key that names nothing the server has, or that belongs to another customer, is not guessed
    at: the result carries the sentence that asks which one is meant."""
    names = {c.id: c.name for c in state.counterparties if c.role == "BUYER"}

    def ask(en: str, zh: str) -> ScopeResult:
        return ScopeResult(used=None, clarification=_say(lang, en, zh))

    customer = scope.customer
    if customer is not None and customer not in names:
        return ask("I cannot find the customer you selected, so I have not guessed. Which customer do you mean?",
                   "我找不到您选择的客户，所以没有猜测。您指的是哪位客户？")
    offer = None
    if scope.decision is not None:
        offer_id = offer_id_of(scope.decision)
        offer = store.get_offer(offer_id) if offer_id else None
        if offer is None or offer.counterparty_id not in names:
            return ask("I cannot find the negotiation you selected, so I have not guessed. Which negotiation do you mean?",
                       "我找不到您选择的谈判，所以没有猜测。您指的是哪一项谈判？")
        if customer is not None and offer.counterparty_id != customer:
            who = _short(names[customer])
            return ask(f"The negotiation you selected is not with {who}, so I cannot tell which one you mean. "
                       "Tell me which customer or negotiation to look at.",
                       f"您选择的谈判不是与{who}进行的，我无法确定您指的是哪一个。请告诉我要看哪位客户或哪一项谈判。")
        customer = offer.counterparty_id
    invoice = None
    if scope.invoice is not None:
        invoice = next((r for r in state.receivables if r.id == scope.invoice), None)
        if invoice is None or invoice.counterparty_id not in names:
            return ask("I cannot find the invoice you selected, so I have not guessed. Which invoice do you mean?",
                       "我找不到您选择的发票，所以没有猜测。您指的是哪张发票？")
        if customer is not None and invoice.counterparty_id != customer:
            who = _short(names[customer])
            return ask(f"The invoice you selected is not {who}'s, so I cannot tell which one you mean. Tell me which customer or invoice to look at.",
                       f"您选择的发票不属于{who}，我无法确定您指的是哪一个。请告诉我要看哪位客户或哪张发票。")
        customer = invoice.counterparty_id
    if scope.scenario is not None:
        verdict = _verdict_for(store, offer.offer_id, None) if offer is not None else None
        k = scope.scenario.split(":")[1] if ":" in scope.scenario else ""
        fits = (offer is not None and _SCENARIO.fullmatch(scope.scenario) is not None
                and (scope.scenario == "asked" or (verdict is not None and k.isdigit() and int(k) < len(verdict.counters))))
        if not fits:
            return ask("The scenario you selected does not belong to a negotiation I can find, so I have not guessed. Which scenario do you mean?",
                       "您选择的情景不属于我能找到的任何谈判，所以没有猜测。您指的是哪种情景？")
    if offer is not None:
        label = _say(lang, f"The negotiation with {names[offer.counterparty_id]}", f"与{names[offer.counterparty_id]}的谈判")
        return ScopeResult(ScopeUsed(kind="decision", label=label), offer.counterparty_id, offer_id=offer.offer_id,
                           invoice_id=invoice.id if invoice is not None else None)
    if invoice is not None:
        who = names[invoice.counterparty_id]
        return ScopeResult(ScopeUsed(kind="invoice", label=_say(lang, f"The invoice to {who}", f"开给{who}的发票")), invoice.counterparty_id,
                           invoice_id=invoice.id)
    if customer is not None:
        return ScopeResult(ScopeUsed(kind="customer", label=names[customer]), customer)
    return ScopeResult(ScopeUsed(kind="company", label=_say(lang, "Your whole company", "整个公司")))


def drop_page_binding(session: Session) -> None:
    """A scoped request supersedes the deal the page last pointed the session at: the page-bound offer and verdict are forgotten (a deal the
    owner evaluated in the conversation itself stays), so a question about a customer or an invoice is never answered about a stale offer."""
    if session.bound_verdict_id is None:
        return
    if session.last_verdict_id == session.bound_verdict_id:
        session.last_verdict_id = None
        session.last_offer_id = None
    session.bound_verdict_id = None
