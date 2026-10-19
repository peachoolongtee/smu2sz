"""Terms hash: a fingerprint of what was economically agreed, independent of how it was worded."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from app.domain.models import Obligation
from app.persistence.canonical import canonical_json

# Fields that identify or evidence an obligation but do not change its economics. Reader provenance is evidence;
# a settlement promise reaches the terms as the bound effective day, so its source span and parse stay out of the hash.
NON_ECONOMIC_FIELDS = frozenset({"id", "spans", "confidence", "field_provenance", "payment_timing"})


def economic_terms(obligation: Obligation) -> dict[str, object]:
    """The obligation as plain JSON data with the non-economic fields removed."""
    data = obligation.model_dump(mode="json")
    return {k: v for k, v in data.items() if k not in NON_ECONOMIC_FIELDS}


def terms_hash(obligations: Iterable[Obligation]) -> str:
    """sha256 of the canonical JSON of the obligations with ids, spans and confidence stripped.

    The obligations are sorted by their canonical form, so the same terms listed in another order
    hash the same. Any change to a rate, amount, day, base, duration, contingency, type or
    counterparty changes the hash.
    """
    items = sorted(canonical_json(economic_terms(o)) for o in obligations)
    body = "[" + ",".join(items) + "]"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
