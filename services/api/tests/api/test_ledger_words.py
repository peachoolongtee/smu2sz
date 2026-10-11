"""The Business ledger says documents and things in words: no sentence field of any row carries an id or a code."""

from __future__ import annotations

import re

import pytest

from tests.api.test_time_semantics import _act, _walk

CODES = re.compile(r"DOC-|RCV-|RI:|APR-|COM-|FAC-|BUYER-|OFF-|CTR-|VER-")
SENTENCES = ("what_changed", "event_text", "event_detail", "message_when", "why_it_matters", "what_remains")


def _ledger_rows(client, lang: str) -> list[dict]:
    return client.get("/ledger", params={"lang": lang}).json()["operations"]


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_no_sentence_of_the_ledger_holds_an_id_or_a_code(client, lang):
    _walk(client, receipt="half")
    _act(client)
    rows = _ledger_rows(client, lang)
    assert rows
    found = [(r["seq"], k, r[k]) for r in rows for k in SENTENCES if isinstance(r.get(k), str) and CODES.search(r[k])]
    assert found == []


def _upload(client, fixture_id):
    r = client.post("/documents", json={"fixture_id": fixture_id})
    assert r.status_code == 200, r.text
    return r.json()["document"]


def test_a_document_decision_reads_as_a_business_sentence_with_the_documents_id_beside_it(client):
    client.post("/demo/reset", json={})
    rejected = _upload(client, "FHR_SUPPLY_AGREEMENT")
    client.post(f"/documents/{rejected['id']}/reject", json={"doc_hash": rejected["doc_hash"]})
    lender = _upload(client, "MB_CREDIT_LINE_AGREEMENT")
    client.post(f"/documents/{lender['id']}/confirm", json={"doc_hash": lender["doc_hash"], "link_facility_id": "FAC-LINE"})
    every = _ledger_rows(client, "en")
    rows = [r for r in every if r["kind"].endswith("_DOCUMENT")]
    assert [r["document_id"] for r in rows] == ["DOC-000001", "DOC-000002", "DOC-000003", rejected["id"], lender["id"]]
    third, rej, linked = rows[2], rows[3], rows[4]
    assert third["event_text"] == third["what_changed"] == (
        "You confirmed the invoice financing agreement, as FLOW read it. Nothing in the books changed.")
    assert third["message_when"] == third["event_text"] + " " + third["event_detail"]
    assert rej["event_text"] == "You rejected the supply agreement. Nothing was recorded from it."
    assert linked["event_text"] == "You confirmed the credit line agreement, as FLOW read it. Nothing in the books changed."
    assert linked["event_detail"] == "Linked to Bank credit line for reference; the facility itself is unchanged."
    assert third["summary"].startswith("Document DOC-000003 (")  # the audit text stays as stored
    zh = [r for r in _ledger_rows(client, "zh") if r["kind"].endswith("_DOCUMENT")]
    assert zh[2]["event_text"] == "您已确认发票融资协议，按 FLOW 读取的内容。账本未作任何更改。"
    assert zh[3]["event_text"] == "您已驳回供货协议。未从中记录任何内容。"
    assert not any(CODES.search(r[k]) for r in rows + zh for k in SENTENCES if isinstance(r.get(k), str))
    assert all("document_id" not in r for r in every if not r["kind"].endswith("_DOCUMENT"))


def test_every_entry_says_its_day_as_a_distance_from_today(client):
    _walk(client, receipt="half")
    en, zh = _ledger_rows(client, "en"), _ledger_rows(client, "zh")
    first, last = en[0], en[-1]
    assert (first["day"], first["day_when"], zh[0]["day_when"]) == (0, "34 days ago", "34 天前")
    assert (last["day"], last["day_when"], zh[-1]["day_when"]) == (34, "today", "今天")
    assert all(isinstance(r["day_when"], str) for r in en + zh)
    assert not any(c.isascii() and c.isalpha() for r in zh for c in r["day_when"])
