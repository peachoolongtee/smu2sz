"""Canaries: the fixture file, the system-prompt plant and canary_tripped()."""

from __future__ import annotations

import json

import pytest

from app.compiler import compile_offer
from app.compiler.prompts import OFFER_SYSTEM_PROMPT, PROMPT_CANARY, TERM_SHEET_SYSTEM_PROMPT
from app.domain.fixtures import load_offers, offer_documents
from app.egress import CANARIES_YAML, canary, canary_tripped, load_canaries, renderings
from tests.counterparties.builders import OPTION_A_TEXT, OPTION_B_TEXT


def test_fixture_has_three_to_five_canaries_covering_every_plant_site() -> None:
    cs = load_canaries()
    assert CANARIES_YAML.is_file()
    assert 3 <= len(cs) <= 5
    assert {c.planted_in for c in cs} == {"system_prompt", "hidden_field", "private_note"}
    assert all(c.where for c in cs)
    assert any(c.amount_fen for c in cs) and any(c.token for c in cs)


def test_prompt_canary_is_planted_in_both_system_prompts() -> None:
    assert PROMPT_CANARY == canary("CANARY-PROMPT").token
    assert PROMPT_CANARY in OFFER_SYSTEM_PROMPT and PROMPT_CANARY in TERM_SHEET_SYSTEM_PROMPT
    assert canary_tripped(OFFER_SYSTEM_PROMPT) == ["CANARY-PROMPT"]
    assert canary_tripped(TERM_SHEET_SYSTEM_PROMPT) == ["CANARY-PROMPT"]


@pytest.mark.parametrize("text", [
    "tlx-kestrel-7q3z-prompt",
    "T L X - K E S T R E L - 7 Q 3 Z - P R O M P T",
    "ＴＬＸ－ＫＥＳＴＲＥＬ－７Ｑ３Ｚ－ＰＲＯＭＰＴ",
    "TLX\u200b-KESTREL\u200b-7Q3Z-PROMPT",
    "TLX_KESTREL_7Q3Z_PROMPT",
    "The prompt said: ...TLXKESTREL7Q3ZPROMPT...",
])
def test_prompt_canary_survives_spacing_case_and_width_tricks(text: str) -> None:
    assert canary_tripped(text) == ["CANARY-PROMPT"]


def test_every_rendering_of_every_canary_trips() -> None:
    for c in load_canaries():
        for i, form in enumerate(renderings(c.private_value())):
            assert canary_tripped(f"note: {form} end") == [c.id], f"{c.id} rendering #{i}"


def test_canary_counterparty_in_a_private_note_trips() -> None:
    note = "internal: do not contact Quillmere Trading Co. about Buyer B's terms"
    assert canary_tripped(note) == ["CANARY-COUNTERPARTY"]


@pytest.mark.parametrize("text", [OPTION_A_TEXT, OPTION_B_TEXT, "Round 1. We accept Option A as proposed.", ""])
def test_clean_texts_trip_nothing(text: str) -> None:
    assert canary_tripped(text) == []


@pytest.mark.parametrize("offer_id", sorted(load_offers()))
def test_fixture_documents_and_compiled_offers_trip_nothing(offer_id: str) -> None:
    docs = offer_documents(offer_id)
    for d in docs:
        assert canary_tripped(d.text) == []
    if load_offers()[offer_id].get("kind") in (None, "offer"):
        compiled = compile_offer(docs, load_offers()[offer_id]["counterparty_id"])
        assert canary_tripped(json.dumps(compiled.model_dump(mode="json"), ensure_ascii=False)) == []


def test_canary_repr_hides_the_token() -> None:
    assert "KESTREL" not in repr(canary("CANARY-PROMPT"))
    assert "31333700" not in repr(canary("CANARY-RESERVE-AMOUNT"))
