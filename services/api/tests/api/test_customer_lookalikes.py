"""REG-3: POST /customers refuses a name that would let one party stand in for another.

The exact-name check compared only the normalised name and short name, so a Cyrillic homoglyph, an accent, a longer name that
holds an existing one, a name whose short form is an existing short form, the business's own name or an identifier-shaped name
all became new customers (and a contract filed under a lookalike passes the party check). Each is refused, nothing is written.
"""

from __future__ import annotations

import json

import pytest

from app.api.runtime import get_runtime
from app.security.names import has_letter_or_digit, keys_clash, name_key, skeleton
from tests.api.test_new_customer import _IDS, _add, _counterparties, demo  # noqa: F401

LINGNAN = "Lingnan Homeware Manufacturing Co., Ltd."


def _unchanged(client, name, code, status=409, **extra):  # type: ignore[no-untyped-def]
    before = (_counterparties(), len(get_runtime().store.operations()))
    r = _add(client, name=name, **extra)
    assert r.status_code == status, (name, r.text)
    d = r.json()["detail"]
    assert d["code"] == code, (name, d)
    assert d["message"] and not _IDS.search(d["message"]), d
    assert (_counterparties(), len(get_runtime().store.operations())) == before
    return d


@pytest.mark.parametrize("name", [
    "Fоshan Home Retail Co.",  # Cyrillic o
    "Foѕhan Home Retail Co.",  # Cyrillic dze for s
    "Fοshan Home Retail Co.",  # Greek omicron
    "Ｆｏｓｈａｎ Home Retail Co.",  # full-width
    "Foshan Home Retail Company Limited",  # legal-form suffix
    "Foshán Home Retail Co.",  # accent
    "Foshán Home Retail Co.",  # combining accent
    "Foshan Home Retai1 Co.",  # 1 for l
    "Foshan Horne Retail Co.",  # rn for m
    "Foshan Home Retail Co. Hong Kong",  # holds an existing company's name
    "Foshan Home",  # sits inside an existing company's name
    "Mаin Bank of Shenzhen",  # a lender, holds its name
])
def test_a_lookalike_of_a_customer_or_a_lender_is_refused_409(client, name):
    before = (_counterparties(), len(get_runtime().store.operations()))
    r = _add(client, name=name)
    assert r.status_code == 409, (name, r.text)
    d = r.json()["detail"]
    assert d["code"] in {"CUSTOMER_LOOKALIKE", "CUSTOMER_EXISTS"} and d["existing_id"] in {"BUYER-1", "BANK-1"}, d  # exact: the old check
    assert d["code"] == "CUSTOMER_LOOKALIKE" or "Ｆ" in name
    assert (_counterparties(), len(get_runtime().store.operations())) == before


def test_the_business_itself_is_refused_as_a_customer(client):
    rt = get_runtime()
    for name in (LINGNAN, "Lingnan Homeware Manufacturing", "Lіngnan Homeware Manufacturing Co.", "Lingnan Homeware"):
        if rt.store.get_state().scenario in (None, "blank"):
            break
        _unchanged(client, name, "CUSTOMER_IS_OWN_BUSINESS")


def test_the_company_the_owner_registered_at_open_books_is_refused_as_a_customer(client):
    rt = get_runtime()
    payload = {"kind": "OPEN_BOOKS", "op_id": "open-x", "company_name": "Xinhui Tools Co., Ltd.", "day": 0}
    rt.store.append_operation("open-x", "OPEN_BOOKS", "open-x", json.dumps(payload), json.dumps({"op_id": "open-x"}))
    d = _unchanged(client, "XINHUI TOOLS Company Limited", "CUSTOMER_IS_OWN_BUSINESS")
    assert "own business" in d["message"]
    assert _add(client, name="Xinhui Trading Partners", key="other").status_code in (200, 409)  # not the same company


def test_the_own_side_of_a_confirmed_contract_is_the_business(demo):  # noqa: F811
    demo_client = demo
    rt = get_runtime()
    names = [t.text for r in rt.store.contract_records() if r.status.value == "CONFIRMED" and r.contract
             for t in r.contract.terms if t.field.value == "PARTY_SUPPLIER" and t.text]
    assert names
    _unchanged(demo_client, names[0].upper(), "CUSTOMER_IS_OWN_BUSINESS")


@pytest.mark.parametrize("name", ["Foshan Trading Co.", "Dongguan Evil Holdings", "Main Street Trading"])
def test_a_name_whose_short_form_is_an_existing_short_form_is_refused_409(client, name):
    _unchanged(client, name, "SHORT_NAME_TAKEN")


def test_a_short_name_that_is_anothers_short_form_is_refused_409(client):
    d = _unchanged(client, "Zhuhai Supplies Co.", "SHORT_NAME_TAKEN", short_name="Fоshan")
    assert d["existing_id"] == "BUYER-1"


@pytest.mark.parametrize("name", ["BUYER-7", "buyer 7", "BUYER_12", "ＢＵＹＥＲ－７", "ВUYER-1",
                                  "BANK-3", "OWNER-1", "ZX-99", "Buyer1"])
def test_a_name_that_reads_as_an_identifier_is_refused_422(client, name):
    _unchanged(client, name, "INVALID_CUSTOMER", status=422)


def test_a_short_name_that_reads_as_an_identifier_is_refused_422(client):
    d = _unchanged(client, "Zhuhai Supplies Co.", "INVALID_CUSTOMER", status=422, short_name="BUYER-9")
    assert d["field"] == "short_name"


@pytest.mark.parametrize("name", ["́́́", "́ ⃝", "---", "\U0001F600\U0001F600", " . , "])
def test_a_name_with_no_letter_or_digit_once_marks_are_removed_is_refused_422(client, name):
    _unchanged(client, name, "INVALID_CUSTOMER", status=422)


@pytest.mark.parametrize("name", ["Zhuhai Supplies Co.", "Café Maison Ltd", "深圳市晟达五金制品有限公司",
                                  "Acme 2000 Ltd", "3M Foshan Industrial"])
def test_a_genuinely_new_name_is_still_added(client, name):
    r = _add(client, name=name)
    assert r.status_code == 200, r.text


def test_the_refusal_words_follow_the_language(client):
    r = _add(client, name="Fоshan Home Retail Co.", lang="zh")
    assert r.status_code == 409 and "过于相近" in r.json()["detail"]["message"]


def test_the_skeleton_makes_what_a_reader_cannot_tell_apart_equal():
    assert skeleton("Fоѕhan") == skeleton("Foshan") == skeleton("Ｆoshan") == skeleton("Fo\u200bshan")
    assert name_key("Foshan Home Retail Co.") == name_key("Foshan Home Retail Company Limited")
    assert keys_clash(name_key("Foshan Home Retail"), name_key("Foshan Home Retail Hong Kong"))
    assert not keys_clash(name_key("Co"), name_key("Cocoa Trading"))  # too short to identify a company
    assert not keys_clash(name_key("Foshan Home Retail"), name_key("Dongguan Office Supplies"))
    assert not has_letter_or_digit("́⃝") and has_letter_or_digit("á")


# ---------------------------------------------------------------- REG-4: a key written by another kind of entry


def test_a_key_another_kind_of_entry_already_holds_is_refused_409_not_a_500(client):
    """The agent can write any idempotency key. `ADD_CUSTOMER:<k>` on a DRAW_FACILITY entry made the route replay that entry
    as a customer and raise KeyError (a 500); it now answers 409 IDEMPOTENCY_KEY_REUSED and writes nothing."""
    rt = get_runtime()
    body = {"kind": "DRAW_FACILITY", "op_id": "agent-op-x", "idempotency_key": "ADD_CUSTOMER:victimkey", "mandate_version": 1,
            "requested_by": "AGENT", "day": rt.day, "facility_id": "NOPE", "amount_fen": 100}
    assert client.post("/operations", json=body, headers={"X-Agent-Key": "demo-agent-key"}).status_code == 200
    held = rt.store.find_by_idempotency_key("ADD_CUSTOMER:victimkey")
    assert held is not None and held.kind == "DRAW_FACILITY"
    before = (_counterparties(), len(rt.store.operations()))
    r = _add(client, name="Victim Co", key="victimkey")
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert (_counterparties(), len(rt.store.operations())) == before
    zh = _add(client, name="Victim Co", key="victimkey", lang="zh")
    assert zh.status_code == 409 and "已用于其他操作" in zh.json()["detail"]["message"]
    assert _add(client, name="Victim Co", key="another").status_code == 200  # a new key works


def test_a_key_this_route_already_used_still_replays(client):
    first = _add(client, name="Zhuhai Supplies Co.", key="same").json()
    again = _add(client, name="Zhuhai Supplies Co.", key="same")
    assert again.status_code == 200 and again.json() == {**first, "created": False}
