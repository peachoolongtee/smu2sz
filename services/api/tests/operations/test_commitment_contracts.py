"""propose_commitment commits exactly what was verified (the verdict's bound obligations, or a counter's
obligations) at its forward value, never an immediate cost; only a lengthening terms change is Tier 2."""

from __future__ import annotations

from typing import Any

import pytest

from app.commitments import new_commitment, terms_hash
from app.domain.models import (
    AcceptOffer,
    CommitmentStatus,
    ConcessionValue,
    Contingency,
    Outcome,
    Tier,
    ViolationCode,
)
from app.domain.models import OperationStatus as S
from app.operations import lengthens_terms, verdict_forward_value
from tests.operations.builders import Clock, counter, extension, offer, op, rebate, verdict


def accept(clock: Clock, c: Any) -> AcceptOffer:
    return op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=c.offer_version, terms_hash=c.terms_hash,
              nonce=c.nonce)


def _raw_extension() -> Any:
    """What the compiler emits for "60 days": a target, no delta yet."""
    return extension("OB-T", days_delta=15).model_copy(update={"days_delta": None, "target_terms_days": 60,
                                                               "unresolved": ["current_terms_days"]})


def test_commitment_stores_the_bound_obligations_not_the_raw_offer(ex: Any, store: Any) -> None:
    raw, bound = _raw_extension(), extension("OB-T", days_delta=15)
    store.put_offer(offer("OFF-B", [raw]))
    store.put_verdict(verdict("V-B", "OFF-B", outcome=Outcome.NEEDS_OWNER_APPROVAL, bound=[bound], value_fen=1_000))
    c = ex.propose_commitment("V-B", expires_day=5, nonce="NB")
    assert c.obligations == [bound] and c.obligations != [raw]
    assert c.terms_hash == terms_hash([bound]) != terms_hash([raw])


def test_accept_verdict_without_bound_obligations_cannot_be_committed(ex: Any, store: Any) -> None:
    store.put_offer(offer("OFF-E", [rebate()]))
    store.put_verdict(verdict("V-E", "OFF-E"))
    with pytest.raises(ValueError, match="no bound obligations"):
        ex.propose_commitment("V-E", expires_day=5, nonce="NE")
    assert store.commitments() == []


def test_a_commitment_on_the_raw_offer_terms_is_refused(ex: Any, store: Any, clock: Clock) -> None:
    raw = rebate("OB-R")
    bound = rebate("OB-R").model_copy(update={"base": raw.base.model_copy(update={"amount_fen": 40_000_000})})
    o = offer("OFF-R", [raw])
    store.put_offer(o)
    store.put_verdict(verdict("V-R", "OFF-R", bound=[bound]))
    forged = new_commitment(o, "V-R", [raw], 1, 5, 0, nonce_factory=lambda: "NR")  # raw terms, not verified
    store.put_commitment(forged)
    result = ex.execute(accept(clock, forged))
    assert result.status == S.REFUSED and [v.code for v in result.violations] == [ViolationCode.INSUFFICIENT_AUTHORITY]
    assert store.get_state().forward_concessions == []


def test_counter_commitment_books_forward_value_not_supplier_cost(ex: Any, store: Any, clock: Clock) -> None:
    k = counter(cost_fen=264_194, forward_fen=0)  # e.g. Option A: discount + line interest, nothing forward
    store.put_offer(offer("OFF-K", [rebate(rate_bp=300)]))
    store.put_verdict(verdict("V-K", "OFF-K", outcome=Outcome.REJECT, counters=[k]))
    c = ex.propose_commitment("V-K", counter_id=k.id, expires_day=5, nonce="NK")
    assert c.forward_value_fen == 0 and c.obligations == k.obligations
    result = ex.execute(accept(clock, c))
    assert result.status == S.EXECUTED and result.tier == Tier.TIER_1
    (fc,) = store.get_state().forward_concessions
    assert fc.value_fen == 0 and fc.commitment_id == c.id


def test_counter_above_threshold_by_forward_value_is_tier2(ex: Any, store: Any, clock: Clock) -> None:
    k = counter(cost_fen=0, forward_fen=10_000_001)
    store.put_offer(offer("OFF-T", [rebate(rate_bp=300)]))
    store.put_verdict(verdict("V-T", "OFF-T", outcome=Outcome.REJECT, counters=[k]))
    c = ex.propose_commitment("V-T", counter_id=k.id, expires_day=5, nonce="NT")
    assert ex.execute(accept(clock, c)).status == S.PENDING_APPROVAL


def test_verdict_forward_value_nets_only_firm_gains_and_floors_at_zero() -> None:
    cost = rebate("OB-C")
    firm_gain = extension("OB-F", days_delta=-15)
    soft_gain = extension("OB-S", days_delta=-15).model_copy(update={"contingency": Contingency.CONTINGENT})

    def v(values: dict[str, int], bound: list[Any]) -> int:
        cvs = [ConcessionValue(obligation_id=k, value_fen=x, basis="t", formula="t") for k, x in values.items()]
        return verdict_forward_value(verdict("V", "O", bound=bound).model_copy(update={"concession_values": cvs}))

    assert v({"OB-C": 500_000, "OB-F": -200_000}, [cost, firm_gain]) == 300_000
    assert v({"OB-C": 500_000, "OB-S": -200_000}, [cost, soft_gain]) == 500_000  # contingent gain counts as zero
    assert v({"OB-C": 100_000, "OB-F": -200_000}, [cost, firm_gain]) == 0  # never creates headroom


@pytest.mark.parametrize(("delta", "tier", "status"), [
    (-15, Tier.TIER_1, S.EXECUTED),  # a shortening (EX05) is a gain: Tier 1
    (15, Tier.TIER_2, S.PENDING_APPROVAL),
    (None, Tier.TIER_2, S.PENDING_APPROVAL),  # an unbound delta fails closed
])
def test_only_a_lengthening_terms_change_is_tier2(delta: int | None, tier: Tier, status: S, ex: Any, store: Any,
                                                 clock: Clock) -> None:
    ext = extension("OB-X", days_delta=15).model_copy(update={"days_delta": delta})
    store.put_offer(offer("OFF-X", [ext]))
    store.put_verdict(verdict("V-X", "OFF-X", bound=[ext], value_fen=0))
    c = ex.propose_commitment("V-X", expires_day=5, nonce="NX")
    result = ex.execute(accept(clock, c))
    assert (result.tier, result.status) == (tier, status)
    expected = CommitmentStatus.ACTIVE if status == S.EXECUTED else CommitmentStatus.PROPOSED
    assert store.get_commitment(c.id).status == expected


def test_lengthens_terms() -> None:
    assert lengthens_terms([extension(days_delta=1)])
    assert not lengthens_terms([extension(days_delta=-1), rebate()])
    assert not lengthens_terms([extension(days_delta=0)])
    assert lengthens_terms([extension().model_copy(update={"days_delta": None})])
