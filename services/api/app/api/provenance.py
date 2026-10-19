"""How a buyer's request reached FLOW, for the views where the owner can accept it or approve an operation on it (SEC-19).

The deal's RECEIVED facts say who filed each version of a request: the owner, the agent, the buyer's own channel key, a reply the owner
pasted in, or nobody (`anonymous`). The strongest sender that filed a version decides how it arrived (`SENDER_RANK`: a later, stronger
filing upgrades an earlier, weaker one, never the other way). `sender_unverified` is true only when that strongest sender is nobody: the
request names a buyer, but no key vouches that the buyer sent it. A request with no RECEIVED fact at all (one the owner quoted in chat, or a
record from before provenance was kept) is not called unverified: FLOW has no evidence either way. Pure reads.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.decisions.facts import ReceivedFact, parse_fact
from app.decisions.identity import deal_id

# How much a sender vouches for a request: a stronger sender may upgrade how the same request arrived, never the other way (F4).
SENDER_RANK: dict[str, int] = {"anonymous": 0, "agent": 1, "buyer_key": 2, "buyer_reply": 2, "owner": 3}


def strongest_via(facts: Iterable[Any], offer_id: str, version: int) -> str | None:
    """The strongest sender among the parsed `facts` that filed `offer_id` at `version`, else None."""
    held = [f for f in facts if isinstance(f, ReceivedFact) and f.offer_id == offer_id and f.offer_version == version]
    return max(held, key=lambda f: SENDER_RANK[f.via], default=None).via if held else None


def sender_unverified(store: Any, offer_id: str | None, version: int | None = None) -> bool:
    """True when nobody signed this request: its strongest RECEIVED fact is `anonymous`. `version` defaults to the stored offer's own;
    False for no offer, an offer not on record, or one with no RECEIVED fact."""
    if not offer_id:
        return False
    if version is None:
        offer = store.get_offer(offer_id)
        if offer is None:
            return False
        version = offer.version
    facts = [parse_fact(r) for r in store.decision_facts(deal_id(offer_id))]
    return strongest_via(facts, offer_id, int(version)) == "anonymous"
