"""Wave 7's rule (map #65, F28) for the contract reads: `GET /deals`, `GET /deals/{buyer}`, `GET /documents` and
`GET /documents/{id}` take `lang` and give the same figures, ids, statuses and days in both languages. Every sentence is the
server's, in the page's language; no English sentence is left in the Chinese read (the helper `english_leaks`), and no Business
sentence says "day N": a day is a distance from today. The document's own words (its text, titles, quotes, the clauses'
wording) are the contract's and stay as written."""

from __future__ import annotations

import re
from typing import Any

import pytest

from app.strategy.words import buyer_short
from tests.api.conftest import _walk, english_leaks, figures
from tests.api.test_deals import (
    _confirm_edited,
    _confirm_text,
    _demo_text,
    confirm_demo_documents,
    run_demo_to_day_34,
)
from tests.api.test_documents import INJECTED

# The contract's own words: the document text, its titles, every quote and the clauses' wording. Index-free dotted paths.
RAW = (
    r".*\.document\.text", r".*\.quote", r".*\.title", r".*\.reference", r".*\.source", r".*\.note_raw", r".*\.reason_raw",
    r".*\.terms\[\]\.text", r".*\.contract_terms\[\]\.text", r".*\.owed_by_us\..*\.text", r".*\.clauses\[\]\.value_text",
    r".*\.compiler", r".*\.prompt_version", r".*\.clause",
    r".*\.href",  # an address inside the app, not a sentence
)
RAW_RE = [re.compile(p) for p in RAW]
DAY_NUMBER = re.compile(r"\bday \d+\b|第 ?\d+ ?天", re.IGNORECASE)
PATHS = ["/deals", "/deals/BUYER-1", "/documents", "/documents/DOC-000001", "/documents/DOC-000002", "/documents/DOC-000003"]


# A term of these fields is the clause's own wording (a party's name, a deliverable, the amendment rule): its display is the
# contract's words, as its `text` is.
WORDS_FIELDS = {"PARTY_SUPPLIER", "PARTY_BUYER", "CONTRACT_REFERENCE", "DELIVERABLE", "REQUIRED_DOCUMENT", "AMENDMENT"}


def _without_the_contracts_words(x: Any) -> Any:
    if isinstance(x, dict):
        quoted = x.get("field") in WORDS_FIELDS
        return {k: _without_the_contracts_words(v) for k, v in x.items() if not (quoted and k == "value_display")}
    if isinstance(x, list):
        return [_without_the_contracts_words(v) for v in x]
    return x


def _names(client) -> list[str]:  # type: ignore[no-untyped-def]
    """Names stay as the books write them on a Chinese page (owner, 16 Oct): a party's full name and the short name an owner says
    aloud ("Foshan"), and every facility's name."""
    state = client.get("/state").json()["state"]
    parties = [c["name"] for c in state["counterparties"]]
    return [*parties, *(buyer_short(n) for n in parties), *(f["name"] for f in state["facilities"])]


def _business_strings(data: Any) -> list[tuple[str, str]]:
    return [(p, s) for p, s in _walk(data) if not any(r.fullmatch(p) for r in RAW_RE)]


@pytest.fixture
def day34(client):  # type: ignore[no-untyped-def]
    confirm_demo_documents(client)
    run_demo_to_day_34(client)
    return client


def test_an_unknown_language_is_refused_and_the_default_is_english(client):
    confirm_demo_documents(client)
    for path in PATHS:
        assert client.get(path, params={"lang": "fr"}).status_code == 422, path
        assert client.get(path).json() == client.get(path, params={"lang": "en"}).json(), path


@pytest.mark.parametrize("path", PATHS)
def test_the_chinese_read_has_the_same_figures_and_no_english_sentence(day34, path):
    en, zh = (day34.get(path, params={"lang": lang}).json() for lang in ("en", "zh"))
    assert zh["lang"] == "zh" and en["lang"] == "en"
    assert figures({k: v for k, v in zh.items() if k != "lang"}) == figures({k: v for k, v in en.items() if k != "lang"})
    assert english_leaks(_without_the_contracts_words(zh), _names(day34), RAW) == [], path
    assert en != zh


def test_the_chinese_deal_card_says_the_same_things_in_chinese(day34):
    deal = day34.get("/deals/BUYER-1", params={"lang": "zh"}).json()["deal"]
    assert deal["label"] == "由代理读取，经您确认"
    assert [p["label"] for p in deal["pills"]] == ["款项逾期", "1 项待您批准"]
    assert [(s["label"], s["note"]) for s in deal["stages"]] == [
        ("合同已读取", "34 天前"), ("条款已谈判", "34 天前"), ("提前付款到账", "32 天前"), ("催收中", "已逾期 2 天"),
        ("已履行完毕", "300 天后")]
    assert deal["changes"][3]["text"].startswith("提前结算 Foshan Home Retail Co. 的 ¥420,000.00 发票中的 ¥257,200.00，折扣 0.85%")
    assert "应于32 天前付款" in deal["changes"][3]["text"] and deal["changes"][3]["text"].endswith("由代理在您设定的限额内入账")
    assert deal["next_action"]["text"] == (
        "催收 Foshan Home Retail Co. 的 ¥420,000.00 发票（2 天前到期）中未收的 ¥162,800.00。审批：针对32 天前开具的发票，"
        "垫款 ¥200,000.00，以保证8 天后的现金不低于您的底线。")
    assert deal["invoices"][0]["label"] == "Foshan Home Retail Co. 的 ¥420,000.00 发票（2 天前到期）"
    assert deal["invoices"][1]["label"] == "32 天前开具的发票"
    assert deal["contract"]["signed_display"] == "2026年9月1日" and deal["contract"]["term_display"] == "12 个月"
    rows = {r["key"]: r for r in deal["in_force"]}
    assert rows["payment_terms"]["value_display"] == "45 天" and rows["payment_terms"]["vs_contract_text"] == "与合同一致"
    assert rows["payment_terms"]["contract_display"] == "自发票日起 45 天"
    assert [a["label"] for a in deal["next_action"]["actions"]] == ["审批垫款", "核对到账"]


def test_no_business_sentence_says_day_n_in_either_language(day34):
    for path in PATHS:
        for lang in ("en", "zh"):
            data = day34.get(path, params={"lang": lang}).json()
            said = [(p, s) for p, s in _business_strings(data) if DAY_NUMBER.search(s)]
            assert said == [], (path, lang, said)
    # the numbers stay beside the words, in their own fields
    deal = day34.get("/deals/BUYER-1").json()["deal"]
    assert (deal["invoices"][0]["due_day"], deal["invoices"][0]["due_when"]) == (32, "2 days ago")
    assert (deal["changes"][4]["day"], deal["changes"][4]["when"]) == (2, "32 days ago")


def test_no_business_sentence_carries_a_document_id_a_ledger_word_or_a_raw_enum(day34):
    banned = re.compile(r"DOC-\d|ledger entry|#\d|hash-chained|\bCOMPILED\b|\bABSTAINED\b|INSTRUCTION_OVERRIDE|DATA_REQUEST", re.IGNORECASE)
    for path in PATHS:
        data = day34.get(path).json()
        text_fields = [(p, s) for p, s in _business_strings(data)
                       if p.endswith(("_text", ".text", ".summary", ".label", ".note", ".reason", ".value_display"))]
        assert [x for x in text_fields if banned.search(x[1])] == [], path


def test_a_document_says_where_it_stands_in_the_owners_words(day34):
    docs = day34.get("/documents").json()["documents"]
    assert {d["status_text"] for d in docs} == {"Confirmed by you 34 days ago"} and {d["status_tone"] for d in docs} == {"ok"}
    assert [d["decided_when"] for d in docs] == ["34 days ago"] * 3 and docs[0]["decided_day"] == 0  # the number stays
    zh = day34.get("/documents", params={"lang": "zh"}).json()["documents"]
    assert {d["status_text"] for d in zh} == {"34 天前经您确认"}
    assert [d["kind_text"] for d in zh] == ["买方合同", "贷款方协议", "贷款方协议"]
    assert zh[2]["summary"].startswith("¥") and "利率" in zh[2]["summary"] and "垫款" in zh[2]["summary"]
    assert docs[0]["summary"] == "18 terms read, 3 left blank" and zh[0]["summary"] == "已读取 18 项条款，3 项留空"


def test_the_review_screen_says_the_reading_status_and_the_flags_in_words(client):
    d = client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"}).json()["document"]
    assert (d["reading_status"], d["reading_text"], d["status_text"], d["status_tone"]) == (
        "COMPILED", "The agent read this document.", "Waiting for your review", "warn")
    zh = client.get(f"/documents/{d['id']}", params={"lang": "zh"}).json()["document"]
    assert (zh["reading_status"], zh["reading_text"], zh["status_text"], zh["label"]) == (
        "COMPILED", "代理已读取此文件。", "等待您审核", "由 AI 生成，仅供参考")
    assert [b["label"] for b in zh["blanks"]] == ["阶段付款", "质保金", "逾期利息"]
    assert {b["reason"] for b in zh["blanks"]} == {"代理没有找到相关条款，已留空。"}
    assert [b["reason_raw"] for b in d["blanks"]] == ["The agent found no clause for this and left it blank."] * 3
    price = next(t for t in zh["terms"] if t["field"] == "PRICE")
    assert (price["value_display"], price["label"]) == ("¥420,000.00 每批交货", "价格")
    start = next(t for t in zh["terms"] if t["field"] == "START_DATE")
    en_start = next(t for t in d["terms"] if t["field"] == "START_DATE")
    assert (start["value_display"], start["date_display"]) == ("2026年9月1日（30 天前）", "2026年9月1日")
    assert (en_start["value_display"], en_start["day"]) == ("1 Sep 2026 (30 days ago)", -30)


def test_a_blocking_flag_is_said_in_words_in_both_languages(client):
    from app.domain.fixtures import contract_fixture_bytes

    text = contract_fixture_bytes("FHR_SUPPLY_AGREEMENT")[1].decode().replace("8. CONFIDENTIALITY",
                                                                             INJECTED + "8. CONFIDENTIALITY")
    r = client.post("/documents", json={"kind": "BUYER_CONTRACT", "counterparty_id": "BUYER-1", "text": text})
    d = r.json()["document"]
    flag = next(f for f in d["flags"] if f["blocking"])
    assert flag["kind"] == "INSTRUCTION_OVERRIDE" and flag["kind_text"] == "an instruction addressed to the agent"
    assert d["status_text"] == "Cannot be confirmed: it carries text addressed to the agent" and d["status_tone"] == "bad"
    zh = client.get(f"/documents/{d['id']}", params={"lang": "zh"}).json()["document"]
    zf = next(f for f in zh["flags"] if f["blocking"])
    assert zf["kind"] == "INSTRUCTION_OVERRIDE" and zf["kind_text"] == "写给代理的指令" and zf["note"].startswith("这是写给代理")
    assert zf["note_raw"] == flag["note"] and english_leaks(zh["flags"], [], [r".*\.quote", r".*\.note_raw"]) == []


def test_a_decision_answers_in_the_page_language(client):
    d = client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"}).json()["document"]
    r = client.post(f"/documents/{d['id']}/confirm", params={"lang": "zh"}, json={"doc_hash": d["doc_hash"]}).json()
    assert r["document"]["status_text"] == "今天经您确认" and r["document"]["label"] == "由代理读取，经您确认"
    assert r["result"]["status"] == "EXECUTED"  # the executor's own sentence is the audit level and stays as written


def test_the_payment_basis_and_price_notes_have_their_chinese_twins(client):
    _confirm_edited(client, "PAYMENT_TERMS", basis=None)
    zh = client.get("/deals/BUYER-1", params={"lang": "zh"}).json()["deal"]
    sentence = "合同没有写明这 45 天从何时起算；账面按发票日起算。"
    assert zh["checks"][0] == {"status": "info", "text": sentence}
    row = next(r for r in zh["in_force"] if r["key"] == "payment_terms")
    assert (row["vs_contract"], row["vs_contract_text"], row["vs_contract_note"]) == (
        "NOT_COMPARABLE", "无法与合同比较", sentence)
    assert english_leaks(zh["checks"], [], [r".*\.quote"]) == []


def test_a_zh_read_of_a_slip_and_of_an_amendment_has_no_english(client):
    _confirm_text(client, _demo_text().replace("forty-five (45) days after the Invoice Date",
                                               "forty-five (45) days after acceptance of the Batch"))
    zh = client.get("/deals/BUYER-1", params={"lang": "zh"}).json()["deal"]
    assert zh["checks"][0]["status"] == "warn" and "合同从验收起算这 45 天（第 4.2 条），但账面从发票日起算" in zh["checks"][0]["text"]
    assert english_leaks(_without_the_contracts_words(zh), _names(client), RAW) == []


@pytest.mark.parametrize("reason", [
    "term dropped: its value_text is not inside its quoted evidence",
    "term dropped: the invoice amount is stated twice with different values (words against figures)",
    "term dropped: the number of days is not parseable as an exact value",
    "term dropped: its quote is not found verbatim in the document",
    "term dropped: no invoice date is stated in its quote",
    "term dropped: it sits in text addressed to the agent, which is never read as a term",
    "note: the payment terms do not say what the days count from",
    "stated more than once with the same value: read once",
    "conflicting sources: 4.2, an unnumbered clause state different values; neither is read, clarification needed",
    "clause dropped: quote not found verbatim in the term sheet",
    "a sentence the reader wrote that no template knows",
])
def test_every_reason_the_contract_reader_gives_has_a_chinese_sentence(reason):
    from app.contracts.views import reason_words

    zh = reason_words(reason, "zh")
    assert zh != reason and not re.search(r"[A-Za-z]{3,}", zh), zh
    assert reason_words(reason, "en") == reason


def test_a_lender_agreement_names_the_facility_it_appears_to_describe(client):
    d = client.post("/documents", json={"fixture_id": "GBR_INVOICE_FINANCING_AGREEMENT"}).json()["document"]
    assert (d["suggested_facility_id"], d["suggested_facility_name"]) == ("FAC-IF", "Invoice financing (onboarded platform)")
    buyer = client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"}).json()["document"]
    assert "suggested_facility_name" not in buyer
    rejected = client.post(f"/documents/{buyer['id']}/reject", json={"doc_hash": buyer["doc_hash"]}).json()["document"]
    assert (rejected["status_text"], rejected["status_tone"]) == ("Rejected by you today", "mute")


# An id belongs in a field of its own: the keys below hold ids, hrefs and the list of document ids; every other string of the
# read is a sentence (except the contract's own words, `RAW`), and a sentence never carries an invoice, approval, commitment, document or recurring-invoice id.
ID_KEYS = ("id", "href", "pending_documents")
ID_IN_A_SENTENCE = re.compile(r"RCV-|APR-|RI:|COM-|DOC-")


def _is_an_id_field(path: str) -> bool:
    key = path.rsplit(".", 1)[-1].removesuffix("[]")
    return key in ID_KEYS or key.endswith(("_id", "_ids"))


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_no_sentence_of_the_deals_read_carries_an_invoice_approval_or_document_id(day34, lang):
    for path in ("/deals", "/deals/BUYER-1"):
        data = day34.get(path, params={"lang": lang}).json()
        said = [(p, s) for p, s in _walk(data) if not _is_an_id_field(p) and not any(r.fullmatch(p) for r in RAW_RE) and ID_IN_A_SENTENCE.search(s)]
        assert said == [], (path, lang, said)
    deal = day34.get("/deals/BUYER-1", params={"lang": lang}).json()["deal"]
    assert deal["invoices"][0]["id"] == "RCV-A" and deal["next_action"]["items"][0]["receivable_id"] == "RCV-A"
    assert deal["next_action"]["items"][1]["approval_id"].startswith("APR-")  # the ids stay in their own fields


def test_the_reading_status_is_a_whole_sentence_in_both_languages_for_every_status():
    from app.contracts.views import reading_status_text

    said = {(st, lang): reading_status_text(st, lang) for st in ("COMPILED", "ABSTAINED", "CONFLICTING_SOURCES")
            for lang in ("en", "zh")}
    assert said[("ABSTAINED", "en")] == "The agent could not read this document."
    assert said[("CONFLICTING_SOURCES", "zh")] == "代理发现条款相互矛盾。"
    assert len(set(said.values())) == 6 and all(v.endswith((".", "。")) for v in said.values())
    assert not [v for (_, lang), v in said.items() if lang == "zh" and re.search(r"[A-Za-z]{2,}", v)]
