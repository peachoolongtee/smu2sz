"""What a buyer's claimed prior agreement is about (the words only; no engine decision rests on it).

A CLAIMED_PRIOR_CONCESSION ("the 2% rebate we agreed last month", "the 60-day terms you agreed with us", "as agreed, we pay on
60-day terms") is never booked without ledger evidence, whatever it claims. The replies that say so used to call every claim a
rebate. `claim_kind` reads what was claimed from the obligation (a stated terms figure) and from the buyer's own quoted words, so
a reply can name it in neutral words: "No rebate is on record", "No payment-terms agreement is on record".

Server words only (INVARIANT 13): the English nouns here are the engine's text; `CLAIM_NOUNS_ZH` is their Chinese.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from app.domain.models import Contingency, Obligation, ObligationType

ClaimKind = Literal["rebate", "terms", "discount", "price", "other"]

CLAIM_KINDS: tuple[ClaimKind, ...] = ("rebate", "terms", "discount", "price", "other")

# "No <noun> is on record, so none applies" / "no <noun>"; the noun for a claim that names nothing we can classify is "such agreement"
CLAIM_NOUNS_EN: dict[ClaimKind, str] = {
    "rebate": "rebate",
    "terms": "payment-terms agreement",
    "discount": "discount",
    "price": "price agreement",
    "other": "such agreement",
}
CLAIM_NOUNS_ZH: dict[ClaimKind, str] = {
    "rebate": "返利",
    "terms": "账期协议",
    "discount": "折扣",
    "price": "价格协议",
    "other": "此类协议",
}

_REBATE = re.compile(r"rebate|cash\s*back|%\s*back\b|\bback\s+\d|返利|返点|返现|返还|回扣|让利|返(?!回)", re.IGNORECASE)
_TERMS = re.compile(r"terms?\b|\bnet\s*\d+|payment\s+period|credit\s+period|extension|账期|付款期|信用期|延期|延长", re.IGNORECASE)
_DISCOUNT = re.compile(r"discount|\boff\b|early\s+(?:pay|settle)|prompt\s+pay|折扣|优惠|贴息|提前(?:付款|结算)", re.IGNORECASE)
_PRICE = re.compile(r"\bprice|pricing|unit\s+cost|价格|单价|货价|降价|涨价", re.IGNORECASE)


def is_claim(ob: Obligation) -> bool:
    return ob.type == ObligationType.CLAIMED_PRIOR_CONCESSION or ob.contingency == Contingency.CLAIMED_UNEVIDENCED


def claim_kind(ob: Obligation) -> ClaimKind:
    """What one claimed obligation claims. A stated terms figure (60-day terms) is a terms claim whatever the quote says; otherwise the
    buyer's quoted words decide, rebate before terms before discount before price; a claim that names none of them is `other`."""
    if ob.target_terms_days is not None or ob.days_delta is not None:
        return "terms"
    quote = " ".join(sp.text for sp in ob.spans)
    for kind, pattern in (("rebate", _REBATE), ("terms", _TERMS), ("discount", _DISCOUNT), ("price", _PRICE)):
        if pattern.search(quote):
            return kind  # type: ignore[return-value]
    return "other"


def claim_kinds(obligations: Iterable[Obligation]) -> list[ClaimKind]:
    """The distinct kinds the claimed obligations among `obligations` claim, in the order of `CLAIM_KINDS`."""
    found = {claim_kind(o) for o in obligations if is_claim(o)}
    return [k for k in CLAIM_KINDS if k in found]


# The two clauses where the verifier's early-pay counter names what is not on record (app/verifier/counters.py, `early_pay_counter`).
# It says "rebate" for every claim; `restate_not_on_record` says what was claimed, in the layer that shows the counter to the reader.
# Only a lead that says "rebate" alone is rewritten: one that already names the claim ("no rebate or payment-terms agreement") is left as
# the verifier wrote it, so a second pass changes nothing (LOG-2: it read "... or payment-terms agreement or payment-terms agreement").
_LEAD_NONE = re.compile(r"^No rebate is on record, so none applies")
_LEAD_STAYS = re.compile(r"^(Terms stay at \d+ days), no rebate(?=\s*[.;]|\s*$)")


def restate_not_on_record(text: str, offer_obligations: Iterable[Obligation]) -> str:
    """The early-pay counter's `text` with its "not on record" lead naming what the buyer claimed. A claimed rebate (or a rebate asked
    for) keeps "rebate"; a claimed payment-terms agreement says "payment-terms agreement", and so on; several kinds are all named
    ("No rebate or payment-terms agreement is on record, so none applies"). Only the leading clause changes: the figures, the other
    counters and the engine's own record (the log, the verdict) are as the verifier wrote them."""
    obligations = list(offer_obligations)
    kinds: set[ClaimKind] = set(claim_kinds(obligations))
    if any(o.type == ObligationType.CONTINGENT_REBATE for o in obligations):
        kinds.add("rebate")
    if not kinds or kinds == {"rebate"}:
        return text
    nouns = " or ".join(CLAIM_NOUNS_EN[k] for k in CLAIM_KINDS if k in kinds)
    if _LEAD_NONE.match(text):
        return _LEAD_NONE.sub(f"No {nouns} is on record, so none applies", text, count=1)
    return _LEAD_STAYS.sub(rf"\1, no {nouns}", text, count=1)
