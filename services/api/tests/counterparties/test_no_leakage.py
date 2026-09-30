"""INVARIANTS 7: no reply text, obligation, transcript or public view reveals a buyer's reservation."""

from __future__ import annotations

import json

import pytest
from fastapi.encoders import jsonable_encoder
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import BaseModel, ConfigDict, TypeAdapter
from pydantic_core import PydanticSerializationError

from app.counterparties import BuyerKernel, HiddenStateError, negotiate, public_view
from app.counterparties.profiles import BuyerProfile, get_profile, load_buyer_profiles
from app.counterparties.verbaliser import PublicMessageFields
from app.domain.money import bp, fmt_pct, fmt_yuan, pct_of, post
from tests.counterparties.builders import (
    INVOICE_FACE_FEN,
    OPTION_A_FACE_FEN,
    discount,
    option_a,
    option_b,
    rebate,
    terms,
)

PROFILES = sorted(load_buyer_profiles())


def reservation_strings(p: BuyerProfile) -> set[str]:
    """Every rendered form of the profile's hidden bp and fen reservation values."""
    rates = {p.funding_cost_bp}
    if p.min_early_pay_discount_bp:
        rates.add(p.min_early_pay_discount_bp)
    if p.min_rebate_bp:
        rates.add(p.min_rebate_bp)
    fens = {p.min_surplus_fen, *(b.value_fen for b in p.declared_benefits)}
    if p.payment_day_value_fen:
        fens.add(p.payment_day_value_fen)
    for face in (OPTION_A_FACE_FEN, INVOICE_FACE_FEN):
        if p.min_early_pay_discount_bp:
            fens.add(post(pct_of(face, bp(p.min_early_pay_discount_bp))))
    if p.min_rebate_bp:
        fens.add(post(pct_of(p.next_quarter_purchases_fen, bp(p.min_rebate_bp))))
    out: set[str] = set()
    for r in rates:
        out |= {fmt_pct(bp(r)), f"{r} bp", f"{r}bp"}
    for f in fens:
        y = fmt_yuan(f)
        out |= {y, y.removeprefix("¥")}
    return out


def assert_no_leak(profile_id: str, *texts: str) -> None:
    secrets = reservation_strings(get_profile(profile_id))
    for text in texts:
        for s in secrets:
            assert s not in text, f"{profile_id} leaked {s!r} in {text!r}"


def test_reservation_strings_are_non_trivial() -> None:
    assert "0.80%" in reservation_strings(get_profile("BUYER-1"))
    assert "1.00%" in reservation_strings(get_profile("BUYER-1-HARDLINE"))
    assert "¥1,694.40" in reservation_strings(get_profile("BUYER-1"))


@pytest.mark.parametrize("profile_id", PROFILES)
def test_negotiation_transcripts_never_show_the_reservation(profile_id: str) -> None:
    for nxt in (lambda _r: option_a(), lambda _r: option_b(), lambda _r: None):
        t = negotiate([option_a(), option_b()], profile_id, nxt)
        for r in t.rounds:
            assert_no_leak(profile_id, r.response.model_dump_json(), r.response.reply_en, r.response.reply_zh)
        for m in t.messages:
            if m.sender == "BUYER":
                assert_no_leak(profile_id, m.text_en, m.text_zh or "")


@pytest.mark.parametrize("profile_id", PROFILES)
def test_counters_never_state_a_reservation_value(profile_id: str) -> None:
    p = get_profile(profile_id)
    for round_no in (1, 2):
        r = BuyerKernel().respond(profile_id, [discount(0), rebate(0)], round_no)
        for o in r.obligations:
            assert o.rate_bp not in {p.min_early_pay_discount_bp, p.min_rebate_bp} - {0}


@settings(max_examples=150, deadline=None)
@given(
    profile_id=st.sampled_from(PROFILES),
    rate=st.integers(0, 300),
    delta=st.integers(-15, 30),
    reb=st.integers(0, 300),
    round_no=st.integers(1, 4),
)
def test_no_reply_ever_contains_a_reservation_value(
    profile_id: str, rate: int, delta: int, reb: int, round_no: int
) -> None:
    r = BuyerKernel().respond(profile_id, [discount(rate), terms(delta), rebate(reb)], round_no)
    assert_no_leak(profile_id, r.reply_en, r.reply_zh, r.model_dump_json())


@pytest.mark.parametrize("profile_id", PROFILES)
def test_public_view_is_name_and_role_only(profile_id: str) -> None:
    view = public_view(profile_id)
    data = view.model_dump()
    assert set(data) == {"name", "role"}
    assert data["role"] == "BUYER"
    dumped = view.model_dump_json()
    assert_no_leak(profile_id, dumped)
    assert "HARDLINE" not in dumped


def test_public_view_does_not_distinguish_profile_variants() -> None:
    assert public_view("BUYER-1") == public_view("BUYER-1-HARDLINE")


@pytest.mark.parametrize("profile_id", PROFILES)
def test_profile_refuses_every_serialisation(profile_id: str) -> None:
    p = get_profile(profile_id)
    with pytest.raises(HiddenStateError):
        p.model_dump()
    with pytest.raises(HiddenStateError):
        p.model_dump_json()
    with pytest.raises(HiddenStateError):
        jsonable_encoder(p)

    class Wrapper(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)
        profile: BuyerProfile

    with pytest.raises((HiddenStateError, PydanticSerializationError)):
        Wrapper(profile=p).model_dump_json()
    with pytest.raises((HiddenStateError, PydanticSerializationError)):
        TypeAdapter(BuyerProfile).dump_json(p)
    assert_no_leak(profile_id, repr(p), str(p))


def test_verbaliser_hook_receives_only_public_fields() -> None:
    received: list[PublicMessageFields] = []

    def hook(fields: PublicMessageFields, lang: str) -> str:
        received.append(fields)
        return ""

    kernel = BuyerKernel(verbaliser_hook=hook)
    for profile_id in PROFILES:
        received.clear()
        kernel.respond(profile_id, option_a(), 1)
        assert received and all(isinstance(f, PublicMessageFields) for f in received)
        for f in received:
            assert_no_leak(profile_id, json.dumps(f.model_dump(mode="json"), ensure_ascii=False))
