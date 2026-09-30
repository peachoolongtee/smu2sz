"""terms_hash: invariant to wording/evidence/order, sensitive to every economic field."""

from __future__ import annotations

import hashlib
import re

from hypothesis import given
from hypothesis import strategies as st

from app.commitments import terms_hash
from app.domain.models import (
    BaseKind,
    Contingency,
    Duration,
    DurationKind,
    ObligationBase,
    SourceSpan,
)
from tests.persistence import factories as f

BASE = [f.discount(), f.extension(), f.rebate()]
H = terms_hash(BASE)


def test_hash_is_hex_sha256():
    assert re.fullmatch(r"[0-9a-f]{64}", H)
    assert terms_hash([]) == hashlib.sha256(b"[]").hexdigest()


def test_ids_spans_and_confidence_do_not_change_the_hash():
    other_span = SourceSpan(doc_id="EX01B-msg", start=0, end=4, text="1.2%")
    reworded = [
        o.model_copy(update={"id": f"X-{i}", "spans": [other_span], "confidence": 0.51})
        for i, o in enumerate(BASE)
    ]
    assert terms_hash(reworded) == H


def test_order_does_not_change_the_hash():
    assert terms_hash(list(reversed(BASE))) == H
    assert terms_hash(iter(BASE)) == H


def test_duplicated_obligation_changes_the_hash():
    assert terms_hash([*BASE, f.rebate(oid="OB-4")]) != H


def _changed(index: int, **update: object) -> str:
    obs = list(BASE)
    obs[index] = obs[index].model_copy(update=update)
    return terms_hash(obs)


def test_every_economic_change_changes_the_hash():
    changes = [
        _changed(0, rate_bp=121),
        _changed(0, effective_day=1),
        _changed(0, counterparty_id="BUYER-2"),
        _changed(0, base=ObligationBase(kind=BaseKind.INVOICE, amount_fen=42_000_001, receivable_id="AR-1")),
        _changed(0, base=ObligationBase(kind=BaseKind.INVOICE, amount_fen=42_000_000, receivable_id="AR-2")),
        _changed(1, days_delta=31),
        _changed(1, base=ObligationBase(kind=BaseKind.PERIOD_PURCHASES)),
        _changed(1, duration=Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=3)),
        _changed(2, contingency=Contingency.FIRM),
        _changed(2, amount_fen=15_000),
        _changed(2, unresolved=["as usual"]),
    ]
    assert H not in changes
    assert len(set(changes)) == len(changes)


@given(rate=st.integers(min_value=0, max_value=100_000), day=st.integers(min_value=0, max_value=3_650))
def test_rate_and_day_are_always_captured(rate: int, day: int):
    a = terms_hash([f.discount(rate_bp=rate, day=day)])
    assert a == terms_hash([f.discount(oid="other", rate_bp=rate, day=day)])
    assert a != terms_hash([f.discount(rate_bp=rate + 1, day=day)])
    assert a != terms_hash([f.discount(rate_bp=rate, day=day + 1)])
