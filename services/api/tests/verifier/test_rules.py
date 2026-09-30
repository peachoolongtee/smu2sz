"""Verifier rules beyond the worked examples: cap boundaries, mandate validity, binding, security
events, concurrent reservation and the port."""

from __future__ import annotations

import pytest
from nacl.signing import SigningKey

from app.domain.models import (
    BaseKind,
    CompiledOffer,
    CompileStatus,
    Contingency,
    Duration,
    DurationKind,
    Obligation,
    ObligationBase,
    ObligationType,
    Outcome,
    SourceSpan,
    Tier,
    ViolationCode,
)
from app.mandate import load_demo_owner_key, revoke, sign
from app.verifier import Verifier, bind, evaluate, evaluate_many, evaluate_verdict
from tests.verifier.conftest import bundle, codes, compiled, declared_for


def _rebate_offer(offer_id: str, cp: str = "BUYER-1", *, amount_fen: int | None = None, rate_bp: int | None = None,
                  base_fen: int | None = None) -> CompiledOffer:
    span = SourceSpan(doc_id=f"{offer_id}-msg", start=0, end=6, text="rebate")
    ob = Obligation(
        id=f"{offer_id}-O1", type=ObligationType.CONTINGENT_REBATE, counterparty_id=cp, rate_bp=rate_bp,
        amount_fen=amount_fen, base=ObligationBase(kind=BaseKind.PERIOD_PURCHASES, amount_fen=base_fen),
        contingency=Contingency.CONTINGENT, duration=Duration(kind=DurationKind.ONE_OFF), spans=[span],
        confidence=1.0,
    )
    return CompiledOffer(offer_id=offer_id, counterparty_id=cp, doc_ids=[span.doc_id], received_day=0,
                         status=CompileStatus.COMPILED, obligations=[ob], compiler="test", prompt_version="test")


# ---------------------------------------------------------------- cap boundary


def test_forward_value_exactly_on_the_cap_passes(state, mandate, key):
    cap = mandate.max_aggregate_forward_concession_fen
    v = evaluate(_rebate_offer("CAP-EQ", amount_fen=cap), state, mandate, trusted_owner_key_hex=key).verdict
    assert v.outcome == Outcome.ACCEPT and v.violations == []
    assert v.forward_concession_total_fen == cap


def test_one_fen_over_the_cap_fails(state, mandate, key):
    cap = mandate.max_aggregate_forward_concession_fen
    v = evaluate(_rebate_offer("CAP-P1", amount_fen=cap + 1), state, mandate, trusted_owner_key_hex=key).verdict
    assert v.outcome == Outcome.REJECT
    assert codes(v.violations) == ["AGG_CONCESSION_EXCEEDED"]
    assert v.forward_concession_total_fen == cap + 1


def test_rate_rebate_over_the_cap_gets_a_smaller_rebate_counter(state, mandate, key):
    v = evaluate(_rebate_offer("CAP-R", rate_bp=150, base_fen=40_000_000), state, mandate,
                 trusted_owner_key_hex=key).verdict
    assert v.outcome == Outcome.REJECT and codes(v.violations) == ["AGG_CONCESSION_EXCEEDED"]
    (c,) = v.counters
    assert c.obligations[0].rate_bp == 125 and c.supplier_cost_fen == 500_000
    assert c.text == "We can offer 1.25% off next quarter's purchases of up to ¥400,000."


# ---------------------------------------------------------------- mandate validity


def _no_evaluation(b) -> None:
    assert b.verdict.outcome == Outcome.REJECT
    assert b.trajectory is None and b.plan_committed is None and b.verdict.counters == []
    assert b.verdict.concession_values == [] and b.bound_obligations == []


def test_revoked_mandate_rejects_without_evaluation(state, mandate, key):
    revoked = revoke(mandate, load_demo_owner_key()["private_key_hex"])
    b = evaluate(compiled("EX01_PACKAGE"), state, revoked, trusted_owner_key_hex=key)
    _no_evaluation(b)
    assert codes(b.verdict.violations) == ["MANDATE_REVOKED"]


def test_expired_mandate_rejects_without_evaluation(state, mandate, key):
    b = evaluate(compiled("EX05_CONSOLIDATE"), state, mandate, trusted_owner_key_hex=key,
                 day=mandate.expires_day + 1, owner_declared=declared_for("EX05_CONSOLIDATE"))
    _no_evaluation(b)
    assert codes(b.verdict.violations) == ["MANDATE_EXPIRED"]


def test_foreign_signed_mandate_rejects_without_evaluation(state, mandate, key):
    foreign = sign(mandate, SigningKey.generate().encode().hex())
    b = evaluate(compiled("EX05_CONSOLIDATE"), state, foreign, trusted_owner_key_hex=key,
                 owner_declared=declared_for("EX05_CONSOLIDATE"))
    _no_evaluation(b)
    assert codes(b.verdict.violations) == ["BAD_SIGNATURE"]
    assert b.verdict.violations[0].observed == "signed by an untrusted key"


def test_edited_mandate_rejects(state, mandate, key):
    loosened = mandate.model_copy(update={"max_aggregate_forward_concession_fen": 10_000_000})
    b = evaluate(compiled("EX01_PACKAGE"), state, loosened, trusted_owner_key_hex=key)
    _no_evaluation(b)
    assert codes(b.verdict.violations) == ["BAD_SIGNATURE"]


# ---------------------------------------------------------------- binding


def test_bind_resolves_receivable_terms_and_declared_costs(state):
    bound, notes = bind(compiled("EX05_CONSOLIDATE"), state, declared_for("EX05_CONSOLIDATE"))
    op, ext = bound
    assert (op.amount_fen, op.base.events_per_year, op.unresolved) == (15_000, 52, [])
    assert (ext.days_delta, ext.unresolved) == (-15, [])
    assert all(n.resolved for n in notes)
    bound, _ = bind(compiled("EX01B_REWORDED"), state, declared_for("EX01B_REWORDED"))
    disc = bound[0]
    assert (disc.base.receivable_id, disc.base.amount_fen, disc.effective_day) == ("RCV-A", 42_000_000, 2)


def test_missing_declared_cost_is_unresolved_scope(state, mandate, key):
    b = evaluate(compiled("EX05_CONSOLIDATE"), state, mandate, trusted_owner_key_hex=key)
    v = b.verdict
    assert v.outcome == Outcome.NO_VERDICT and codes(v.violations) == ["UNRESOLVED_SCOPE"]
    assert b.trajectory is None and v.forward_concession_total_fen == 0


def test_undeclared_rebate_base_uses_a_conservative_ledger_estimate(state, mandate, key):
    b = evaluate(compiled("EX01_PACKAGE"), state, mandate, trusted_owner_key_hex=key)
    rebate = next(o for o in b.bound_obligations if o.type == ObligationType.CONTINGENT_REBATE)
    assert rebate.base.amount_fen == 3 * 42_000_000  # a quarter of the ledger's invoicing to BUYER-1
    note = next(n for n in b.notes if n.obligation_id == rebate.id)
    assert note.resolved and "conservative estimate" in note.message
    assert b.verdict.outcome == Outcome.REJECT


def test_claimed_concessions_are_never_bound(state):
    bound, notes = bind(compiled("SEC_DEMO_FASTCAPITAL"), state)
    assert bound == [] and notes[0].field == "contingency"


# ---------------------------------------------------------------- security


def test_sec_demo_logs_three_events_each_with_spans():
    b = bundle("SEC_DEMO_FASTCAPITAL")
    kinds = [e.kind.value for e in b.security_events]
    assert kinds == ["UNKNOWN_COUNTERPARTY", "UNEVIDENCED_CLAIM", "DATA_EXTRACTION"]
    assert all(e.spans for e in b.security_events)
    assert len(b.security_events[2].spans) == 3
    assert all(e.counterparty_id == "FASTCAPITAL" for e in b.security_events)
    assert len({e.id for e in b.security_events}) == 3


def test_sec_demo_discloses_nothing():
    b = bundle("SEC_DEMO_FASTCAPITAL")
    data = b.verdict.model_dump_json() + "".join(e.model_dump_json() for e in b.security_events)
    for secret in ("300,000", "150,000", "350,000", "5,000.00", "10.84", "15.00%", "250,000"):
        assert secret not in data
    reply = b.verdict.violations[2].inputs["reply_template"]
    assert reply == "We are not able to share internal financial, facility or counterparty information."


def test_ex10_two_events():
    b = bundle("EX10_FASTCAPITAL")
    assert [e.kind.value for e in b.security_events] == ["UNKNOWN_COUNTERPARTY", "UNEVIDENCED_CLAIM"]
    unknown = b.verdict.violations[0]
    assert unknown.spans[0].text.startswith("pre-approved for ¥500,000")


# ---------------------------------------------------------------- concurrency


def test_evaluate_many_reserves_in_order(state, mandate, key):
    a, b = compiled("EX08A_JOINT_BUYER1"), compiled("EX08B_JOINT_BUYER2")
    first, second = evaluate_many([a, b], state, mandate, trusted_owner_key_hex=key)
    assert first.verdict.outcome == Outcome.ACCEPT and first.verdict.forward_concession_total_fen == 300_000
    assert second.verdict.outcome == Outcome.COUNTER
    (c,) = second.verdict.counters
    assert c.obligations[0].rate_bp == 80 and c.supplier_cost_fen == 200_000  # ¥5,000 − ¥3,000 left
    assert c.text == "We can offer 0.80% off next quarter's purchases of up to ¥250,000."
    # the reverse order accepts BUYER-2 and counters BUYER-1
    r1, r2 = evaluate_many([b, a], state, mandate, trusted_owner_key_hex=key)
    assert r1.verdict.outcome == Outcome.ACCEPT and r2.verdict.outcome == Outcome.COUNTER
    # alone, each fits
    assert evaluate(b, state, mandate, trusted_owner_key_hex=key).verdict.outcome == Outcome.ACCEPT


# ---------------------------------------------------------------- tiers and the port


def test_lengthening_terms_need_owner_approval(state, mandate, key):
    span = SourceSpan(doc_id="T-msg", start=0, end=7, text="50 days")
    ob = Obligation(id="T-O1", type=ObligationType.TERMS_EXTENSION, counterparty_id="BUYER-1", days_delta=5,
                    base=ObligationBase(kind=BaseKind.FUTURE_INVOICES), contingency=Contingency.FIRM,
                    duration=Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=1), spans=[span], confidence=1.0)
    offer = CompiledOffer(offer_id="T", counterparty_id="BUYER-1", doc_ids=["T-msg"], received_day=0,
                          status=CompileStatus.COMPILED, obligations=[ob], compiler="test", prompt_version="test")
    v = evaluate(offer, state, mandate, trusted_owner_key_hex=key).verdict
    assert v.outcome == Outcome.NEEDS_OWNER_APPROVAL and v.required_tier == Tier.TIER_2


def test_verifier_class_satisfies_the_port(state, mandate, key):
    from app.domain.ports import Verifier as VerifierPort

    verifier: VerifierPort = Verifier(trusted_owner_key_hex=key, owner_declared=declared_for("EX01_PACKAGE"))
    offer = compiled("EX01_PACKAGE")
    v = verifier.evaluate(offer, state, mandate)
    assert v == evaluate_verdict(offer, state, mandate, trusted_owner_key_hex=key,
                                 owner_declared=declared_for("EX01_PACKAGE"))
    assert [c.model_dump() for c in verifier.counters(offer, v, state, mandate)] == [
        c.model_dump() for c in v.counters]
    with pytest.raises(ValueError):
        Verifier(trusted_owner_key_hex="")


def test_verdict_is_deterministic(state, mandate, key):
    offer = compiled("EX06_THREE_INVOICES")
    one = evaluate(offer, state, mandate, trusted_owner_key_hex=key)
    two = evaluate(offer, state, mandate, trusted_owner_key_hex=key)
    assert one == two


def test_every_violation_has_formula_and_inputs():
    for offer_id in ("EX01_PACKAGE", "EX02_EARLY_1_5", "EX04_CLAIMED_REBATE", "EX06_THREE_INVOICES",
                     "EX07_CONFLICT", "SEC_DEMO_FASTCAPITAL"):
        for v in bundle(offer_id).verdict.violations:
            assert v.formula and v.inputs, (offer_id, v.code)
    assert ViolationCode.RESERVE_BREACH  # keep the import meaningful for readers
