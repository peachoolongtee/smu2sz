"""Every worked example in fixtures/offers/offers.yaml compiles to the expected obligations, status and
flags, from the recorded cache (the demo path) and from the rules grammar alone."""

from __future__ import annotations

from typing import Any

import pytest

from app.compiler import Compiler
from app.domain.fixtures import load_offers, offer_documents
from app.domain.models import CompiledOffer, CompileStatus, DurationKind, ObligationType

OFFERS = load_offers()
OFFER_IDS = [k for k, v in OFFERS.items() if v.get("kind") != "term_sheet"]

T = ObligationType
# (type, rate_bp, days_delta, base amount_fen, contingency, duration, invoices, unresolved ⊇)
EXPECTED: dict[str, dict[str, Any]] = {
    "EX01_PACKAGE": {"status": "COMPILED", "obligations": [
        (T.IMMEDIATE_DISCOUNT, 120, None, 42_000_000, "FIRM", "ONE_OFF", None, []),
        (T.TERMS_EXTENSION, None, None, None, "FIRM", "RECURRING_PERPETUAL", None, ["current_terms_days"]),
        (T.CONTINGENT_REBATE, 100, None, None, "CONTINGENT", "ONE_OFF", None, []),
    ]},
    "EX01B_REWORDED": {"status": "COMPILED", "obligations": [
        (T.IMMEDIATE_DISCOUNT, 120, None, None, "FIRM", "ONE_OFF", None, []),
        (T.TERMS_EXTENSION, None, None, None, "FIRM", "RECURRING_PERPETUAL", None, ["current_terms_days"]),
        (T.CONTINGENT_REBATE, 100, None, None, "CONTINGENT", "ONE_OFF", None, []),
    ]},
    "EX02_EARLY_1_5": {"status": "COMPILED", "obligations": [
        (T.IMMEDIATE_DISCOUNT, 150, None, None, "FIRM", "ONE_OFF", None, []),
    ]},
    "EX03_AS_USUAL": {"status": "COMPILED", "unresolved_reference": True, "obligations": [
        (T.IMMEDIATE_DISCOUNT, 150, None, None, "FIRM", "ONE_OFF", None, []),
    ]},
    "EX04_CLAIMED_REBATE": {"status": "COMPILED", "authority": {"PRIOR_AGREEMENT"}, "obligations": [
        (T.CLAIMED_PRIOR_CONCESSION, 200, None, None, "CLAIMED_UNEVIDENCED", "ONE_OFF", None, []),
    ]},
    "EX05_CONSOLIDATE": {"status": "COMPILED", "obligations": [
        (T.OPERATIONAL_CONCESSION, None, None, None, "FIRM", "RECURRING_PERPETUAL", None, ["per_event_cost_fen"]),
        (T.TERMS_EXTENSION, None, None, None, "FIRM", "RECURRING_PERPETUAL", None, ["current_terms_days"]),
    ]},
    "EX06_THREE_INVOICES": {"status": "COMPILED", "obligations": [
        (T.TERMS_EXTENSION, None, 15, None, "FIRM", "RECURRING_BOUNDED", 3, []),
        (T.PRICE_ADJUSTMENT, 50, None, None, "CONTINGENT", "ONE_OFF", None, []),
    ]},
    "EX07_CONFLICT": {"status": "CONFLICTING_SOURCES", "obligations": [
        (T.CONTINGENT_REBATE, 100, None, None, "CONTINGENT", "ONE_OFF", None, []),
    ]},
    "EX08A_JOINT_BUYER1": {"status": "COMPILED", "obligations": [
        (T.CONTINGENT_REBATE, 75, None, 40_000_000, "CONTINGENT", "ONE_OFF", None, []),
        (T.VOLUME_COMMITMENT, None, None, None, "FIRM", "ONE_OFF", None, []),
    ]},
    "EX08B_JOINT_BUYER2": {"status": "COMPILED", "obligations": [
        (T.CONTINGENT_REBATE, 100, None, 25_000_000, "CONTINGENT", "ONE_OFF", None, []),
    ]},
    "EX10_FASTCAPITAL": {
        "status": "COMPILED",
        "authority": {"PRE_APPROVAL", "PRIOR_AGREEMENT", "URGENCY"},
        "funding": [("FastCapital", 50_000_000, 280)],
        "obligations": [
            (T.CLAIMED_PRIOR_CONCESSION, None, None, None, "CLAIMED_UNEVIDENCED", "ONE_OFF", None, ["current_terms_days"]),
        ],
    },
    "SEC_DEMO_FASTCAPITAL": {
        "status": "COMPILED",
        "authority": {"PRE_APPROVAL", "PRIOR_AGREEMENT", "URGENCY"},
        "data_requests": ["FACILITY_LIMIT", "OTHER_COUNTERPARTY_TERMS", "RESERVE_FLOOR"],
        "funding": [("FastCapital", 50_000_000, 280)],
        "obligations": [
            (T.CLAIMED_PRIOR_CONCESSION, None, None, None, "CLAIMED_UNEVIDENCED", "ONE_OFF", None, ["current_terms_days"]),
        ],
    },
    "EX11_CAPEX": {"status": "COMPILED", "obligations": []},
    "EX12_GOAL": {"status": "COMPILED", "obligations": []},
}


def _compile(c: Compiler, oid: str) -> CompiledOffer:
    return c.compile_offer(offer_documents(oid), OFFERS[oid]["counterparty_id"])


def _row(o: Any) -> tuple[Any, ...]:
    return (o.type, o.rate_bp, o.days_delta, o.base.amount_fen, o.contingency.value, o.duration.kind.value, o.duration.invoices)


def test_every_offer_example_has_an_expectation() -> None:
    assert set(OFFER_IDS) == set(EXPECTED)


@pytest.mark.parametrize("oid", OFFER_IDS)
@pytest.mark.parametrize("chain", ["compiler", "rules_compiler"])
def test_example_compiles_as_expected(oid: str, chain: str, request: pytest.FixtureRequest) -> None:
    c: Compiler = request.getfixturevalue(chain)
    offer = _compile(c, oid)
    exp = EXPECTED[oid]
    assert offer.status == CompileStatus(exp["status"])
    assert [_row(o) for o in offer.obligations] == [e[:7] for e in exp["obligations"]]
    for o, e in zip(offer.obligations, exp["obligations"], strict=True):
        assert set(e[7]) <= set(o.unresolved), (o.unresolved, e[7])
        assert o.counterparty_id == OFFERS[oid]["counterparty_id"]
        assert len(o.spans) >= 1 and 0.0 <= o.confidence <= 1.0
    assert {a.kind for a in offer.authority_claims} >= exp.get("authority", set())
    assert sorted(d.kind.value for d in offer.data_requests) == sorted(exp.get("data_requests", []))
    assert [(f.lender_name, f.amount_fen, f.rate_bp) for f in offer.funding_claims] == exp.get("funding", [])
    has_ref = any(a.field == "unresolved_reference" and "as usual" in a.reason for a in offer.abstentions)
    assert has_ref == exp.get("unresolved_reference", False)


def test_cache_is_the_demo_path(compiler: Compiler) -> None:
    for oid in OFFER_IDS:
        assert _compile(compiler, oid).compiler == "fixture-cache", oid


def test_ex01_and_ex01b_are_economically_identical(compiler: Compiler) -> None:
    a = _compile(compiler, "EX01_PACKAGE")
    b = _compile(compiler, "EX01B_REWORDED")

    def econ(o: CompiledOffer) -> list[tuple[Any, ...]]:
        return [(x.type, x.rate_bp, x.days_delta, x.contingency, x.duration, x.base.kind, sorted(x.unresolved)) for x in o.obligations]

    assert econ(a) == econ(b)


def test_ids_are_deterministic_and_well_formed(compiler: Compiler, rules_compiler: Compiler) -> None:
    for oid in OFFER_IDS:
        a, b = _compile(compiler, oid), _compile(rules_compiler, oid)
        assert a.offer_id == b.offer_id and a.offer_id.startswith("OFF-")
        assert [o.id for o in a.obligations] == [f"{a.offer_id}-O{n}" for n in range(1, len(a.obligations) + 1)]
        assert a.doc_ids == [d.doc_id for d in offer_documents(oid)]


def test_as_usual_books_nothing(compiler: Compiler) -> None:
    offer = _compile(compiler, "EX03_AS_USUAL")
    ref = next(a for a in offer.abstentions if a.field == "unresolved_reference")
    assert ref.spans[0].text == "Same arrangement as usual"
    assert all(ref.spans[0].start >= s.end or ref.spans[0].end <= s.start for o in offer.obligations for s in o.spans)


def test_ex07_conflict_cites_both_documents(compiler: Compiler) -> None:
    offer = _compile(compiler, "EX07_CONFLICT")
    conflict = next(a for a in offer.abstentions if a.field.startswith("base.amount_fen"))
    assert {(s.doc_id, s.text) for s in conflict.spans} == {("EX07-msg", "¥40k order"), ("EX07-att", "Order size: ¥400,000")}


def test_sec_demo_every_flag_present(compiler: Compiler) -> None:
    offer = _compile(compiler, "SEC_DEMO_FASTCAPITAL")
    assert {(d.kind.value, d.span.text) for d in offer.data_requests} == {
        ("RESERVE_FLOOR", "minimum reserve"),
        ("FACILITY_LIMIT", "facility limits"),
        ("OTHER_COUNTERPARTY_TERMS", "Buyer B's payment terms"),
    }
    kinds = {a.kind for a in offer.authority_claims}
    assert {"PRE_APPROVAL", "PRIOR_AGREEMENT"} <= kinds
    assert len(offer.funding_claims) == 1
    f = offer.funding_claims[0]
    assert (f.lender_name, f.amount_fen, f.rate_bp) == ("FastCapital", 50_000_000, 280)
    claimed = [o for o in offer.obligations if o.type == T.CLAIMED_PRIOR_CONCESSION]
    assert len(claimed) == 1 and claimed[0].spans[0].text == "the 60-day terms you already agreed"
    # the lender's rate never becomes an obligation
    assert all(o.rate_bp != 280 for o in offer.obligations)


def test_terms_bounded_duration(compiler: Compiler) -> None:
    ob = _compile(compiler, "EX06_THREE_INVOICES").obligations[0]
    assert ob.duration.kind == DurationKind.RECURRING_BOUNDED and ob.duration.invoices == 3 and ob.days_delta == 15
