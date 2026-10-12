"""GET /buyers/{id}/exposure (map #88, the connected pages): the buyer's exposure with no deal needed, behind FEATURE_EXPOSURE (404 with a
sentence when it is off), built from `buyer_exposure` and cached like the Customer overview; and the fields the Receivables page reads
from GET /receivables (the short amounts, the recourse sentence, the financing link, the terms label, the next payment's buyer and the
financing total). Both languages, the golden books before and after FLOW's plan has run."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app.api import strategy_exposure as route
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.persistence.records import CustomerInputRecord
from app.strategy import exposure as assembly
from tests.api.conftest import english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Bank credit line",
         "Invoice financing (onboarded platform)", "Buyer early-payment offer"]
EX01 = {"fixture_id": "EX01_PACKAGE"}


@pytest.fixture
def rt(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    route.clear_cache()
    yield runtime
    set_runtime(None)
    route.clear_cache()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _buyer(api: TestClient, lang: str = "en", **query: Any) -> dict[str, Any]:
    r = api.get("/buyers/BUYER-1/exposure", params={"lang": lang, "spare": 0, **query})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _run_plan(api: TestClient) -> None:
    api.post("/offers", json=EX01)
    a = api.get("/home").json()["next_action"]
    r = api.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()
    assert r["executed"] == 2


# ---------------------------------------------------------------- the route


def test_the_owner_alone_may_read(api: TestClient) -> None:
    from app.main import app

    assert TestClient(app).get("/buyers/BUYER-1/exposure").status_code == 401


def test_flag_off_is_a_404_with_a_sentence(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_EXPOSURE", raising=False)
    r = api.get("/buyers/BUYER-1/exposure")
    assert r.status_code == 404
    assert r.json()["detail"] == {"code": "FEATURE_DISABLED", "feature": "exposure", "message": "Buyer exposure is switched off (FEATURE_EXPOSURE)."}
    zh = api.get("/buyers/BUYER-1/exposure", params={"lang": "zh"})
    assert zh.status_code == 404 and zh.json()["detail"]["message"] == "买家风险敞口功能尚未开启（FEATURE_EXPOSURE）。"


def test_an_unknown_buyer_or_a_name_that_is_not_a_buyer_is_a_404(api: TestClient) -> None:
    for name in ("BUYER-9", "FAC-IF", "nonsense"):
        r = api.get(f"/buyers/{name}/exposure")
        assert r.status_code == 404 and r.json()["detail"]["code"] == "BUYER_NOT_FOUND", name
        assert name not in r.json()["detail"]["message"]  # the id in the path is never echoed
    assert api.get("/buyers/BUYER-9/exposure", params={"lang": "zh"}).json()["detail"]["message"] == "您的账目中没有这位客户。"
    assert api.get("/buyers/BUYER-1/exposure", params={"lang": "fr"}).status_code == 422


def test_the_block_for_foshan_on_the_golden_books(api: TestClient) -> None:
    body = _buyer(api)
    assert (body["buyer_id"], body["buyer_name"], body["day"], body["spare_read"], body["economics"]) == ("BUYER-1", "Foshan Home Retail Co.", 0, False, None)
    assert body["concentration"]["ar_share_bp"] == 10_000 and body["band"]["concentration"] == body["concentration"]["sentence"]
    assert body["payments"]["insufficient"] is True and body["payments_note"] is None
    now = body["stress"]["now"]
    assert body["stress"]["delay_days"] == 30 and now["available"] is True and now["breach_days"] > 0
    assert now["net_later_text"] == "about ¥420k, a month later" and now["net_later_fen"] == 42_000_000  # nothing financed: the whole invoice
    assert set(body["capacity"]) == {"available", "unavailable_text", "before", "spare"}
    assert body["capacity"]["spare"] is None and {w["dimension"] for w in body["capacity"]["before"]["windows"]} >= {"cash_buffer", "credit_line"}
    assert body["customer_context"]["owes_display"] == "¥420,000" and "paths" not in body and "context" not in body


def test_the_spare_room_when_asked(api: TestClient) -> None:
    body = _buyer(api, spare=1)
    assert body["spare_read"] is True and body["capacity"]["spare"]["x_star_fen"] == 8_100_000
    assert body["band"]["capacity"] == "Accepting as asked leaves ¥81,000 of room for another payment; today ¥81,000."


def test_it_is_the_deals_own_figures(api: TestClient) -> None:
    offer_id = api.post("/offers", json=EX01).json()["offer"]["offer_id"]
    deal = api.get(f"/offers/{offer_id}/exposure", params={"spare": 0}).json()
    body = _buyer(api)  # the offer has no verdict yet: its asked path is the books as they stand
    assert body["concentration"] == deal["concentration"] and body["payments"] == deal["payments"]
    assert body["stress"]["now"]["lowest_fen"] == deal["stress"]["now"]["lowest_fen"]
    assert body["stress"]["now"]["series"] == deal["stress"]["now"]["series"]


def test_the_net_a_month_later_after_the_plan(api: TestClient) -> None:
    _run_plan(api)
    en, zh = _buyer(api), _buyer(api, "zh")
    row = api.get("/receivables").json()["rows"][0]
    later = en["stress"]["now"]["net_later_fen"]
    assert later < row["net"]["net_fen"] == 16_272_771  # a month more of the financing's charges
    assert en["stress"]["now"]["net_later_text"] == "about ¥160k, a month later"
    assert zh["stress"]["now"]["net_later_text"] == "约 ¥160k，一个月后" and zh["stress"]["now"]["net_later_fen"] == later
    assert not english_leaks({"s": zh["stress"]["now"]["net_later_text"], "b": zh["band"], "c": zh["customer_context"]}, NAMES)


def test_the_chinese_read_has_the_same_figures(api: TestClient) -> None:
    en, zh = _buyer(api), _buyer(api, "zh")
    assert zh["lang"] == "zh" and zh["concentration"]["ar_share_bp"] == en["concentration"]["ar_share_bp"]
    assert zh["stress"]["now"]["lowest_fen"] == en["stress"]["now"]["lowest_fen"]
    assert zh["customer_context"]["contribution_note"].startswith("每年，估算")
    words = {"band": zh["band"], "ctx": zh["customer_context"], "later": zh["stress"]["now"]["net_later_text"],
             "payments": zh["payments"]["insufficient_text"], "conc": zh["concentration"]["sentence"]}
    assert not english_leaks(words, NAMES), english_leaks(words, NAMES)


def test_an_aggregate_buyer_has_no_payment_statistics_and_no_share(api: TestClient, rt: Runtime) -> None:
    state = rt.store.get_state()
    rt.store.add_customer_input(CustomerInputRecord(
        org_id=state.org_id, counterparty_id="BUYER-1", field="aggregate", value_json="true", provenance="OWNER_ENTERED",
        source_ref="test", entered_by="OWNER", entered_day=0, state_version=state.state_version))
    body = _buyer(api)
    assert body["payments"] is None and "stands for many small customers" in body["payments_note"]
    assert body["customer_context"]["owes_display"] is None and body["customer_context"]["share_text"] is None
    assert body["concentration"]["is_aggregate"] is True


def test_it_is_cached_like_the_overview_and_a_change_reads_again(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = assembly.buyer_exposure
    monkeypatch.setattr(assembly, "buyer_exposure", lambda *a, **k: (calls.append("read"), real(*a, **k))[1])
    first = _buyer(api)
    second = _buyer(api)
    assert calls == ["read"] and {k: v for k, v in first.items() if k != "computed_in_seconds"} == {k: v for k, v in second.items() if k != "computed_in_seconds"}
    _buyer(api, "zh")  # another language is another answer
    _buyer(api, spare=1)  # and so is the spare search
    assert calls == ["read", "read", "read"]
    _run_plan(api)  # the books and the log moved
    assert _buyer(api)["stress"]["now"]["net_later_text"] != first["stress"]["now"]["net_later_text"] and len(calls) == 4


# ---------------------------------------------------------------- GET /receivables: the words the page dashed out


def _receivables(api: TestClient, lang: str = "en") -> dict[str, Any]:
    body: dict[str, Any] = api.get("/receivables", params={"lang": lang}).json()
    return body


def test_the_row_carries_its_short_amounts_and_the_standing_sentence(api: TestClient) -> None:
    body = _receivables(api)
    row = body["rows"][0]
    assert row["amount_short"] == "¥420k" and row["net_short"] == row["net"]["net_short"] == "about ¥420k"
    assert row["recourse_text"] == "If the receipt falls short, what is left is owed by you."
    zh = _receivables(api, "zh")["rows"][0]
    assert zh["recourse_text"] == "如果回款不足，差额由您承担。" and zh["amount_short"] == "¥420k" and zh["net_short"] == "约 ¥420k"


def test_the_terms_are_labelled_and_the_text_does_not_open_with_the_label(api: TestClient) -> None:
    for lang, label in (("en", "Payment terms"), ("zh", "付款条款")):
        g = _receivables(api, lang)["rows"][0]["governed_by"]
        assert g["terms_label"] == label and not g["terms_text"].startswith(("Governed by", "依据协议"))
    assert _receivables(api)["rows"][0]["governed_by"]["terms_text"] == "No confirmed agreement on file; payment is due 45 days from the invoice date"
    assert _receivables(api, "zh")["rows"][0]["governed_by"]["terms_text"] == "尚无已确认的协议；账期为自开票日起 45 天"


def test_the_summary_names_the_buyer_and_totals_the_financing(api: TestClient) -> None:
    before = _receivables(api)["summary"]
    assert before["next_expected"]["buyer_name"] == "Foshan Home Retail Co." and before["financing_total_display"] == "¥0.00"
    _run_plan(api)
    after = _receivables(api)
    assert after["summary"]["financing_total_display"] == "¥255,000.00" and after["summary"]["financing_total_fen"] == 25_500_000
    assert _receivables(api, "zh")["summary"]["next_expected"]["buyer_name"] == "Foshan Home Retail Co."  # a buyer's own name stays original


def test_the_financing_link_is_the_record_that_exists(api: TestClient) -> None:
    assert _receivables(api)["rows"][0]["financing_href"] is None
    _run_plan(api)
    href = _receivables(api)["rows"][0]["financing_href"]
    assert href and href.startswith("/decisions/")
    assert api.get(unquote(href)).status_code == 200  # the page it names is there
    assert _receivables(api, "zh")["rows"][0]["financing_href"] == href


def test_the_receivables_words_have_no_english_in_chinese_and_no_id(api: TestClient) -> None:
    _run_plan(api)
    body = _receivables(api, "zh")
    row = body["rows"][0]
    words = {"recourse": row["recourse_text"], "label": row["governed_by"]["terms_label"], "terms": row["governed_by"]["terms_text"],
             "short": [row["amount_short"], row["net_short"]], "buyer": body["summary"]["next_expected"]["buyer_name"],
             "total": body["summary"]["financing_total_display"]}
    assert not english_leaks(words, NAMES), english_leaks(words, NAMES)
    assert "RCV-" not in str(words) and "BUYER-" not in str(words)


def test_a_buyer_with_no_open_invoice_has_null_net_later(api: TestClient) -> None:
    body = api.get("/buyers/BUYER-2/exposure", params={"spare": 0}).json()  # Dongguan owes nothing and is billed nothing
    assert body["stress"]["now"]["available"] is False
    assert "net_later_text" in body["stress"]["now"] and body["stress"]["now"]["net_later_text"] is None
    assert body["stress"]["now"]["net_later_fen"] is None and "net_later_display" not in body["stress"]["now"]
