"""The selection contract (map #121, tickets #126 and #143): the URL keys every page read accepts and the `context` it answers with.

The URL is the only selection state. Six keys travel with a page: `customer`, `decision` (the negotiation, `deal:<offer>`), `path` (the
chosen reply of that decision), `invoice`, `scenario` and `from` (the page the owner came from). `selection` reads them from the query,
`build_context` checks each against the books and the page's own record and answers:

    context = {customer, decision, path, invoice, scenario, back: {label, href} | null, irrelevant_text: str | null}

A key the page can honour is echoed. The customer is also derived when a decision or an invoice that belongs to it was selected. A key the
page cannot honour is echoed as null and `irrelevant_text` says so in one sentence per key and asks the question the owner has to answer
("Which negotiation?"): an unknown customer, decision or invoice; an invoice or a decision of another customer; a decision that is not the
one the page is about; a path that is not a reply of the decision; a scenario without a decision. Nothing is ever substituted for it.
`back` follows `from` (`customer`, `deal`, `invoice`, or a plain page: `home`, `deals`, `receivables`, `activity`, `cash`, `approvals`) when
the selections support that target, else the page's own default (`customer` for the Deals reads); a target that is the page itself is not a
way back. A part that names another customer's record is dropped from every link, never echoed.

Read-only and presentation only: nothing here changes a verdict, a cap, a plan or an execution. Every sentence is written for `lang`
through `t(lang, en, zh)` (INVARIANT 13) and carries no id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from fastapi import Query

from app.api.presentation import Lang, deal_back_label, party_name, t
from app.decisions.identity import offer_id_of
from app.domain.models import FinancialState
from app.strategy.words import buyer_short

SAFE = re.compile(r"[A-Za-z0-9_.:\-]{1,80}")
SCENARIO = re.compile(r"asked|counter:[0-9]{1,3}")
ASKED, DO_NOTHING = "asked", "do_nothing"

# the pages `from` may name without a record behind them: (label en, label zh, href)
_PLAIN = {"home": ("Back to Home", "返回首页", "/"), "deals": ("Back to Deals", "返回交易", "/deals"),
          "receivables": ("Back to the invoices", "返回发票", "/receivables"), "activity": ("Back to Activity", "返回动态", "/activity"),
          "cash": ("Back to Cash", "返回现金", "/cash"), "approvals": ("Back to Approvals", "返回批准事项", "/approvals")}
# what `from` names that is the page itself, per page: never offered as a way back
_OWN = {"deals": {"deal", "deals"}, "offer": {"deal", "deals"}, "picture": {"deal", "deals"}, "customer": {"customer"},
        "receivables": {"invoice", "receivables"}, "decision": set(), "activity": {"activity"}}
# where a page goes back to when `from` names nothing the selections support
_DEFAULT = {"deals": ("customer",), "offer": ("customer",), "picture": ("customer",), "receivables": ("customer",), "customer": (), "decision": (), "activity": ()}


@dataclass(frozen=True)
class Selection:
    """The six keys of the URL contract, as the query carried them (unchecked)."""

    customer: str | None = None
    decision: str | None = None
    path: str | None = None
    invoice: str | None = None
    scenario: str | None = None
    origin: str | None = None


def selection(customer: str | None = Query(None, max_length=120), decision: str | None = Query(None, max_length=120),
              path: str | None = Query(None, max_length=120), invoice: str | None = Query(None, max_length=120),
              scenario: str | None = Query(None, max_length=120), origin: str | None = Query(None, alias="from", max_length=40)
              ) -> Selection:
    """The FastAPI dependency every page read takes: `sel: Selection = Depends(selection)`."""
    return Selection(customer, decision, path, invoice, scenario, origin)


def query_buyer(state: FinancialState, customer: str | None, invoice: str | None) -> str | None:
    """The buyer a query names: `customer` when it is a buyer on the books, else the buyer the `invoice` belongs to."""
    buyer_ids = {c.id for c in state.counterparties if c.role == "BUYER"}
    owner_of = next((x.counterparty_id for x in state.receivables if x.id == invoice), None) if invoice else None
    return customer if customer in buyer_ids else owner_of if owner_of in buyer_ids else None


def deal_buyer(rt: Any, decision: str | None) -> str | None:
    """The buyer of the deal a `decision` key names (a plain `deal:<offer>` key of an offer on the books), else None."""
    offer_id = offer_id_of(decision) if decision and SAFE.fullmatch(decision) else None
    offer = rt.store.get_offer(offer_id) if offer_id else None
    return offer.counterparty_id if offer is not None else None


def deal_of(rt: Any, buyer: str, decision: str | None) -> bool:
    """The query's `decision` is a plain key of a deal this buyer is the counterparty of (anything else is ignored, never echoed)."""
    return deal_buyer(rt, decision) == buyer


def invoice_of(state: FinancialState, buyer: str, invoice: str | None) -> bool:
    """The query's `invoice` is one of this buyer's receivables."""
    return bool(invoice) and any(x.id == invoice and x.counterparty_id == buyer for x in state.receivables)


def customer_link(state: FinancialState, lang: Lang, buyer: str, query: list[str]) -> dict[str, str]:
    """The Customer page's link, "Back to {who}": the one set of words, carrying `query` when it has any."""
    who = buyer_short(party_name(state, buyer))
    return {"label": t(lang, f"Back to {who}", f"返回{who}"),
            "href": f"/customers/{quote(buyer, safe='')}" + (f"?{'&'.join(query)}" if query else "")}


def selected_scenario(rt: Any, deal: str | None, scenario: str | None) -> str | None:
    """The scenario the page was opened on: `asked`, or `counter:<k>` when the deal's verdict has a k-th counter-offer; none without a deal
    (a scenario is of a deal), and never an echo of anything else."""
    from app.api.decisions import latest_verdict_for  # decisions reads this module for its own context

    if deal is None or not scenario or not SCENARIO.fullmatch(scenario):
        return None
    if scenario == ASKED:
        return scenario
    offer_id = offer_id_of(deal)
    verdict = latest_verdict_for(rt, offer_id) if offer_id else None
    return scenario if verdict is not None and int(scenario.split(":")[1]) < len(verdict.counters) else None


def _replies(rt: Any, decision: str) -> set[str]:
    """The keys of the replies a deal's picture can draw: the offer as asked, do nothing, and each counter of its latest verdict."""
    from app.api.decisions import latest_verdict_for

    offer_id = offer_id_of(decision)
    verdict = latest_verdict_for(rt, offer_id) if offer_id else None
    return {ASKED, DO_NOTHING, *(c.id for c in verdict.counters)} if verdict is not None else {ASKED, DO_NOTHING}


def _said(lang: Lang, key: str, who: str | None) -> str:
    """One sentence for a key the page could not use, with the question the owner has to answer."""
    w = who or t(lang, "this page's customer", "此页面的客户")
    en, zh = {
        "customer_unknown": ("FLOW cannot find the customer you selected, so it has not used it. Which customer?",
                             "FLOW 找不到您选择的客户，因此没有采用。您想看哪位客户？"),
        "customer_other": (f"This page is about {w}, so the customer you selected has not been used. Which customer?",
                           f"此页面讲的是{w}，因此没有采用您选择的客户。您想看哪位客户？"),
        "decision_unknown": ("FLOW cannot find the negotiation you selected, so it has not used it. Which negotiation?",
                             "FLOW 找不到您选择的谈判，因此没有采用。您想看哪一项谈判？"),
        "decision_other": ("The negotiation you selected is not the one on this page, so it has not been used. Which negotiation?",
                           "您选择的谈判不是此页面上的这一项，因此没有采用。您想看哪一项谈判？"),
        "decision_buyer": (f"The negotiation you selected is not with {w}, so it has not been used. Which negotiation?",
                           f"您选择的谈判不是与{w}进行的，因此没有采用。您想看哪一项谈判？"),
        "invoice_unknown": ("FLOW cannot find the invoice you selected, so it has not used it. Which invoice?",
                            "FLOW 找不到您选择的发票，因此没有采用。您想看哪张发票？"),
        "invoice_other": (f"The invoice you selected is not {w}'s, so it has not been used. Which invoice?",
                          f"您选择的发票不属于{w}，因此没有采用。您想看哪张发票？"),
        "path": ("The reply you selected is not one of this negotiation's replies, so it has not been used.",
                 "您选择的回复不属于这项谈判，因此没有采用。"),
        "scenario": ("The scenario you selected does not belong to this negotiation, so it has not been used.",
                     "您选择的情景不属于这项谈判，因此没有采用。"),
    }[key]
    return t(lang, en, zh)


def build_context(rt: Any, lang: Lang, sel: Selection, *, page: str, buyer: str | None = None, deal: str | None = None,
                  default_back: dict[str, str] | None = None) -> dict[str, Any]:
    """The `context` of a page read (call under `rt.lock`). `page` is `deals`, `offer`, `picture`, `customer`, `receivables` or `decision`.
    `buyer` and `deal` are the page's own record when it has one (the customer of a Customer page; the buyer and the `deal:<offer>` key of
    an offer, its picture, or a decision record): a selection of another record is irrelevant to it. `default_back` is the page's own back
    link when `from` names nothing the selections support."""
    state = rt.store.get_state()
    buyers = {c.id for c in state.counterparties if c.role == "BUYER"}
    bad: list[str] = []
    subject = buyer
    # the customer
    customer = sel.customer
    if customer is not None and customer not in buyers:
        bad.append("customer_unknown")
        customer = None
    elif customer is not None and subject is not None and customer != subject:
        bad.append("customer_other")
        customer = None
    known = subject or customer
    # the decision: the page's own record when it has one, else a deal of the customer already known
    decision = sel.decision
    if decision is not None:
        owner = deal_buyer(rt, decision)
        if deal is not None and decision != deal:
            bad.append("decision_other")
            decision = None
        elif deal is None and owner is None:
            bad.append("decision_unknown")
            decision = None
        elif deal is None and known is not None and owner != known:
            bad.append("decision_buyer")
            decision = None
        else:
            known = known or owner
    elif deal is not None:
        decision = deal
    # the invoice: one of the customer's receivables
    invoice = sel.invoice
    if invoice is not None:
        owner_of = next((x.counterparty_id for x in state.receivables if x.id == invoice), None)
        if owner_of is None or owner_of not in buyers:
            bad.append("invoice_unknown")
            invoice = None
        elif known is not None and owner_of != known:
            bad.append("invoice_other")
            invoice = None
        else:
            known = known or owner_of
    # the path and the scenario belong to the decision
    path = sel.path
    if path is not None and not (decision is not None and SAFE.fullmatch(path) and path in _replies(rt, decision)):
        bad.append("path")
        path = None
    scenario = selected_scenario(rt, decision, sel.scenario)
    if sel.scenario is not None and scenario is None:
        bad.append("scenario")
    who = buyer_short(party_name(state, known)) if known else None
    text = " ".join(_said(lang, key, who) for key in bad) or None
    return {"customer": known, "decision": decision, "path": path, "invoice": invoice, "scenario": scenario,
            "back": _back(lang, state, sel.origin, page, known, decision, path, invoice) or default_back,
            "irrelevant_text": text}


def _back(lang: Lang, state: FinancialState, origin: str | None, page: str, buyer: str | None, decision: str | None, path: str | None,
          invoice: str | None) -> dict[str, str] | None:
    """The way back `from` names when the honoured selections support it, else the page's default targets in order. None when neither does."""
    own = _OWN.get(page, set())
    targets: dict[str, dict[str, str]] = {}
    quoted = quote(buyer, safe="") if buyer else ""
    if buyer is not None:
        query: list[str] = []
        if decision is not None:
            query.append(f"decision={quote(decision, safe='')}")
            if path is not None:
                query.append(f"path={quote(path, safe='')}")
        if invoice is not None:
            query.append(f"invoice={quote(invoice, safe='')}")
        targets["customer"] = customer_link(state, lang, buyer, query)
        if decision is not None:
            tail = f"&path={quote(path, safe='')}" if path is not None else ""
            targets["deal"] = {"label": deal_back_label(lang, buyer_short(party_name(state, buyer))),
                               "href": f"/deals?decision={quote(decision, safe='')}{tail}&customer={quoted}"}
        if invoice is not None:
            targets["invoice"] = {"label": t(lang, "Back to the invoice", "返回发票"), "href": f"/receivables?invoice={quote(invoice, safe='')}&customer={quoted}"}
    for key, (en, zh, href) in _PLAIN.items():
        targets[key] = {"label": t(lang, en, zh), "href": href}
    if origin is not None and origin not in own and origin in targets:
        return targets[origin]
    return next((targets[k] for k in _DEFAULT.get(page, ()) if k in targets), None)
