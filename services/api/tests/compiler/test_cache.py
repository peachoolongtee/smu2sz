"""Fixture cache: round trip, key stability, and coverage of every document set in offers.yaml."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.compiler import Compiler, compile_offer, compile_term_sheet
from app.compiler.base import CacheMiss
from app.compiler.cache import CACHE_MODEL_ID, CacheBackend, cache_key, entry_path, write_entry
from app.compiler.prompts import PROMPT_VERSION, TERM_SHEET_PROMPT_VERSION
from app.compiler.rules import RulesBackend, rules_offer, rules_term_sheet
from app.domain.fixtures import load_offers, offer_documents
from app.domain.models import SourceDocument

OFFERS = load_offers()


def test_round_trip(tmp_path: Path, rules_compiler: Compiler) -> None:
    docs = offer_documents("EX01_PACKAGE")
    write_entry(tmp_path, PROMPT_VERSION, docs, rules_offer(docs), "rules-v1", "EX01_PACKAGE")
    cached = Compiler([CacheBackend(tmp_path)]).compile_offer(docs, "BUYER-1")
    live = rules_compiler.compile_offer(docs, "BUYER-1")
    assert cached.compiler == CACHE_MODEL_ID
    assert cached.model_copy(update={"compiler": "x"}) == live.model_copy(update={"compiler": "x"})


def test_term_sheet_round_trip(tmp_path: Path) -> None:
    doc = offer_documents("EX09_TERM_SHEET_PG")[0]
    write_entry(tmp_path, TERM_SHEET_PROMPT_VERSION, [doc], rules_term_sheet(doc), "rules-v1")
    ts = Compiler([CacheBackend(tmp_path)]).compile_term_sheet(doc)
    assert ts.compiler == CACHE_MODEL_ID and ts.all_in_rate_bp == 590


def test_miss_falls_through_to_rules(tmp_path: Path) -> None:
    docs = [SourceDocument(doc_id="new", channel="chat", sender_id="BUYER-1", received_day=0, text="Early pay at 1%.")]
    with pytest.raises(CacheMiss):
        CacheBackend(tmp_path).extract_offer(docs)
    offer = Compiler([CacheBackend(tmp_path), RulesBackend()]).compile_offer(docs, "BUYER-1")
    assert offer.compiler == "rules-v1" and offer.obligations[0].rate_bp == 100


def test_key_depends_on_prompt_version_and_every_document_field() -> None:
    docs = offer_documents("EX07_CONFLICT")
    k = cache_key(PROMPT_VERSION, docs)
    assert len(k) == 64 and k == cache_key(PROMPT_VERSION, offer_documents("EX07_CONFLICT"))
    assert k != cache_key("offer-v0", docs)
    edited = [docs[0], docs[1].model_copy(update={"text": docs[1].text.replace("400,000", "40,000")})]
    assert k != cache_key(PROMPT_VERSION, edited)


def test_stale_prompt_version_is_a_miss(tmp_path: Path) -> None:
    docs = offer_documents("EX02_EARLY_1_5")
    p = write_entry(tmp_path, PROMPT_VERSION, docs, rules_offer(docs), "rules-v1")
    entry = json.loads(p.read_text())
    entry["prompt_version"] = "offer-v0"
    p.write_text(json.dumps(entry))
    with pytest.raises(CacheMiss):
        CacheBackend(tmp_path).extract_offer(docs)


@pytest.mark.parametrize("oid", list(OFFERS))
def test_every_fixture_document_set_is_recorded_and_current(cache_path: Path, oid: str) -> None:
    """The recorded demo cache exists for every offers.yaml entry and matches today's rules grammar
    (re-record with `uv run python -m app.compiler.record_cache` after changing the grammar)."""
    docs = offer_documents(oid)
    is_ts = OFFERS[oid].get("kind") == "term_sheet"
    path = entry_path(cache_path, TERM_SHEET_PROMPT_VERSION if is_ts else PROMPT_VERSION, docs)
    assert path.is_file(), f"missing cache entry for {oid}"
    entry = json.loads(path.read_text(encoding="utf-8"))
    expected = rules_term_sheet(docs[0]) if is_ts else rules_offer(docs)
    assert entry["extraction"] == expected.model_dump(mode="json")
    assert entry["doc_ids"] == [d.doc_id for d in docs]


def test_no_orphan_cache_files(cache_path: Path) -> None:
    keys = set()
    for oid, o in OFFERS.items():
        docs = offer_documents(oid)
        pv = TERM_SHEET_PROMPT_VERSION if o.get("kind") == "term_sheet" else PROMPT_VERSION
        keys.add(cache_key(pv, docs))
    assert {p.stem for p in cache_path.glob("*.json")} == keys


def test_module_level_entry_points_use_the_cache() -> None:
    offer = compile_offer(offer_documents("SEC_DEMO_FASTCAPITAL"), "FASTCAPITAL")
    assert offer.compiler == CACHE_MODEL_ID and len(offer.data_requests) == 3
    ts = compile_term_sheet(offer_documents("EX09_TERM_SHEET_PG")[0])
    assert ts.compiler == CACHE_MODEL_ID
