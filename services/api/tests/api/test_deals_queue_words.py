"""The server words the Deals queue dashed out (map #88, the connected pages), on the golden books before and after FLOW's plan has run:
the sentence beside the send (`priced_response.recheck_text`), the words of each path on the exposure read (`lowest_display`,
`lowest_when_text`, `limit_word`/`limit_text`, `share_after_text`, and the `do_nothing` path), `customer_context` (the Customer overview's
own contribution function, with the Demo-margin qualifier), `context.back` from the query, and the one margin function with its config
default. Every word in both languages; no English left in the Chinese read; no id in a sentence."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview as overview
from app.api import offer_picture
from app.api import strategy_exposure as route
from app.api.runtime import Runtime, set_runtime
from app.config import DEMO_GROSS_MARGIN_BP, get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.persistence.records import CustomerInputRecord
from tests.api.conftest import english_leaks
from tests.api.test_offer_picture import _accepted

OWNER = {"X-Owner-Token": "demo-owner-token"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Bank credit line",
         "Invoice financing (onboarded platform)", "Buyer early-payment offer"]
EX01 = {"fixture_id": "EX01_PACKAGE"}
WORDS = ("lowest_display", "lowest_when", "lowest_when_text", "limit_word", "limit_text", "share_after_text")
HREFS = r".*href"


@pytest.fixture
def rt(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    route.clear_cache()
    overview.clear_cache()
    offer_picture._cache.clear()
    yield runtime
    set_runtime(None)
    route.clear_cache()
    overview.clear_cache()
    offer_picture._cache.clear()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _offer(api: TestClient) -> str:
    offer_id = str(api.post("/offers", json=EX01).json()["offer"]["offer_id"])
    api.post(f"/offers/{offer_id}/evaluate", json=EX01)
    return offer_id


def _run_plan(api: TestClient) -> None:
    a = api.get("/home").json()["next_action"]
    r = api.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()
    assert r["executed"] == 2


def _read(api: TestClient, offer_id: str, lang: str = "en", **query: str) -> dict[str, Any]:
    r = api.get(f"/offers/{offer_id}/exposure", params={"lang": lang, "spare": 0, **query})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _paths(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The paths by their column: asked, Option A, Option B and do nothing."""
    keys = {"asked": "asked", "do_nothing": "do_nothing"}
    for p in body["paths"]:
        if p["kind"] == "reply":
            keys[p["label"].split()[-1]] = p["key"]
    by_key = {p["key"]: p for p in body["paths"]}
    return {name: by_key[key] for name, key in keys.items()}


# ---------------------------------------------------------------- 1. the sentence beside the send


def test_the_recheck_sentence_is_beside_the_send_in_both_languages(api: TestClient) -> None:
    offer_id = str(api.post("/offers", json=EX01).json()["offer"]["offer_id"])
    en = api.post(f"/offers/{offer_id}/evaluate", json=EX01).json()["workspace"]["priced_response"]
    zh = api.post(f"/offers/{offer_id}/evaluate", params={"lang": "zh"}, json=EX01).json()["workspace"]["priced_response"]
    assert en["recheck_text"] == "Sends exactly this option at these figures; if the books have moved, FLOW shows you the new figures first."
    assert zh["recheck_text"] == "按这些数字原样发送此方案；如果账目已有变动，FLOW 会先向您展示新的数字。"
    assert not english_leaks({"t": zh["recheck_text"]}, NAMES)


def test_no_sendable_reply_no_recheck_sentence(api: TestClient) -> None:
    offer = api.post("/offers", json={"fixture_id": "SEC_DEMO_FASTCAPITAL"}).json()["offer"]["offer_id"]
    ws = api.post(f"/offers/{offer}/evaluate", json={"fixture_id": "SEC_DEMO_FASTCAPITAL"}).json()["workspace"]
    assert ws["priced_response"] is None


# ---------------------------------------------------------------- 2. the words of each path


def test_each_path_carries_its_words_on_the_golden_books_before_the_plan(api: TestClient) -> None:
    offer_id = _offer(api)
    paths = _paths(_read(api, offer_id))
    assert [paths[k]["kind"] for k in ("asked", "A", "B", "do_nothing")] == ["asked", "reply", "reply", "do_nothing"]
    asked, a, b, nothing = (paths[k] for k in ("asked", "A", "B", "do_nothing"))
    assert (asked["lowest_display"], asked["lowest_when_text"], asked["lowest_when"]) == ("¥165k", "below it for 15 days", "in 60 days")
    assert (a["lowest_display"], a["lowest_when_text"]) == ("¥300k", "at your minimum")
    assert (b["lowest_display"], b["lowest_when_text"]) == ("¥300k", "at your minimum")
    assert (nothing["label"], nothing["lowest_display"], nothing["lowest_when_text"]) == ("Do nothing", "−¥105k", "below it for 20 days")
    assert all(p["lowest_display"] for p in paths.values())


def test_the_lowest_is_the_pictures_own_figure(api: TestClient) -> None:
    offer_id = _offer(api)
    body = _read(api, offer_id)
    picture = {p["key"]: p for p in api.get(f"/offers/{offer_id}/picture").json()["paths"]}
    for p in body["paths"]:
        if p["key"] in picture:
            assert p["lowest_display"] == picture[p["key"]]["lowest_short"] and p["lowest_when"] == picture[p["key"]]["lowest_when"]


def test_the_words_after_the_plan_has_run(api: TestClient) -> None:
    offer_id = _offer(api)
    _run_plan(api)
    paths = _paths(_read(api, offer_id))
    assert (paths["asked"]["lowest_display"], paths["asked"]["lowest_when_text"]) == ("¥313k", "above your minimum")
    assert (paths["B"]["lowest_display"], paths["B"]["lowest_when_text"]) == ("¥300k", "at your minimum")
    assert (paths["do_nothing"]["lowest_display"], paths["do_nothing"]["lowest_when_text"]) == ("¥300k", "at your minimum")
    assert paths["do_nothing"]["limit_word"] is None


def test_a_reply_the_picture_cannot_price_has_a_null_limit_word(api: TestClient) -> None:
    offer_id = _offer(api)
    _run_plan(api)  # Option A can no longer be drawn on the books once the invoice is financed
    pictured = {p["key"]: p for p in api.get(f"/offers/{offer_id}/picture").json()["paths"]}
    a = _paths(_read(api, offer_id))["A"]
    assert pictured[a["key"]]["authority"] is None
    assert (a["limit_word"], a["limit_text"]) == (None, None) and a["lowest_display"] == "¥310k"  # the words that can be said still are
    zh = _paths(_read(api, offer_id, "zh"))["A"]
    assert (zh["limit_word"], zh["limit_text"]) == (None, None)


def test_the_limit_word_follows_the_authority_class(api: TestClient) -> None:
    offer_id = _offer(api)
    paths = _paths(_read(api, offer_id))
    assert (paths["asked"]["limit_word"], paths["asked"]["limit_text"]) == ("EXCEEDED", "exceeded")  # a cap violation: over a limit you signed
    assert (paths["A"]["limit_word"], paths["A"]["limit_text"]) == ("WITHIN", "within")  # FLOW may send it
    assert (paths["B"]["limit_word"], paths["B"]["limit_text"]) == ("WITHIN", "within")  # needs your approval, still inside the signed limits
    assert (paths["do_nothing"]["limit_word"], paths["do_nothing"]["limit_text"]) == (None, None)  # it agrees to nothing
    pictured = {p["key"]: p["authority"] for p in api.get(f"/offers/{offer_id}/picture").json()["paths"]}
    assert [pictured[paths[k]["key"]] for k in ("asked", "A", "B")] == ["over_limit", "flow_may", "needs_owner"]


def test_an_offer_flow_may_accept_is_within(api: TestClient) -> None:
    oid, _ = _accepted(api)
    asked = _paths(_read(api, oid))["asked"]
    assert (asked["limit_word"], asked["limit_text"]) == ("WITHIN", "within")


def test_the_share_after_the_path_says_how_the_payment_moves(api: TestClient) -> None:
    offer_id = _offer(api)
    paths = _paths(_read(api, offer_id))
    # the share while the invoice stays open: today's (the concentration's own), with each path's timing as the qualifier
    assert _read(api, offer_id)["concentration"]["ar_share_bp"] == 10_000
    assert paths["do_nothing"]["share_after_text"] == "100%, until the due day"
    assert paths["asked"]["share_after_text"] == "100%, for 15 days longer"  # the terms to 60 days: its next invoice owed 15 days longer
    assert paths["A"]["share_after_text"] == "100%, paid 2 days after the offer"
    assert paths["B"]["share_after_text"] == "100%, for 10 days longer"
    assert len({p["share_after_text"] for p in paths.values()}) == 4  # the qualifiers differ per path


def test_before_the_offer_is_evaluated_only_the_books_as_they_stand_have_words(api: TestClient) -> None:
    offer_id = str(api.post("/offers", json=EX01).json()["offer"]["offer_id"])
    paths = _paths(_read(api, offer_id))
    assert set(paths) == {"asked", "do_nothing"}
    assert paths["asked"]["lowest_display"] == paths["do_nothing"]["lowest_display"] and paths["asked"]["limit_word"] is None


def test_the_chinese_words_are_the_same_figures_in_chinese(api: TestClient) -> None:
    offer_id = _offer(api)
    en, zh = _paths(_read(api, offer_id)), _paths(_read(api, offer_id, "zh"))
    assert {k: (v["lowest_display"], v["limit_word"]) for k, v in en.items()} == {k: (v["lowest_display"], v["limit_word"]) for k, v in zh.items()}
    assert zh["asked"]["lowest_when_text"] == "低于最低现金 15 天" and zh["A"]["lowest_when_text"] == "恰为您的最低现金"
    assert (zh["asked"]["limit_text"], zh["A"]["limit_text"]) == ("超出授权", "在授权内")
    assert zh["asked"]["share_after_text"] == "100%，多持续 15 天" and zh["A"]["share_after_text"] == "100%，报价后 2 天付款"
    assert zh["do_nothing"]["share_after_text"] == "100%，直到到期日"
    assert zh["do_nothing"]["label"] == "不采取行动"


def test_no_english_leaks_into_the_chinese_read_and_no_id_into_a_sentence(api: TestClient) -> None:
    offer_id = _offer(api)
    _run_plan(api)
    body = _read(api, offer_id, "zh", customer="BUYER-1", invoice="RCV-A")
    words = {"paths": [{k: p[k] for k in ("label", *WORDS)} for p in body["paths"]], "customer_context": body["customer_context"],
             "context": body["context"]}
    assert not english_leaks(words, NAMES, raw_fields=[HREFS]), english_leaks(words, NAMES, raw_fields=[HREFS])
    for lang in ("en", "zh"):
        text = json.dumps([{k: p[k] for k in ("label", *WORDS)} for p in _read(api, offer_id, lang)["paths"]], ensure_ascii=False)
        assert "CTR-" not in text and "BUYER-" not in text and "RCV-" not in text


# ---------------------------------------------------------------- 3. the customer context


def test_the_customer_context_is_the_overviews_contribution(api: TestClient) -> None:
    offer_id = _offer(api)
    body = _read(api, offer_id)
    assert body["economics"] is None
    assert body["customer_context"] == {
        "contribution_display": "about ¥1.09m", "contribution_note": "a year, estimated; margin assumed for the Demo, not confirmed by you",
        "owes_display": "¥420,000", "share_text": "100%", "profile_href": "/customers/BUYER-1"}
    figure = api.get("/customers/BUYER-1/overview").json()["figures"][0]
    assert figure["value_display"] == body["customer_context"]["contribution_display"]  # one function
    zh = _read(api, offer_id, "zh")["customer_context"]
    assert (zh["contribution_display"], zh["contribution_note"]) == ("约 ¥109万", "每年，估算；毛利率为演示而假设，尚未经您确认")


def test_an_owner_margin_drops_the_demo_qualifier(api: TestClient, rt: Runtime) -> None:
    offer_id = _offer(api)
    state = rt.store.get_state()
    rt.store.add_customer_input(CustomerInputRecord(
        org_id=state.org_id, counterparty_id="BUYER-1", field="margin_bp", value_json="3000", provenance="OWNER_ENTERED",
        source_ref="test", entered_by="OWNER", entered_day=0, state_version=state.state_version))
    ctx = _read(api, offer_id)["customer_context"]
    assert ctx["contribution_note"] == "a year, estimated" and ctx["contribution_display"] == "about ¥1.64m"


def test_the_decision_exposure_carries_the_same_words(api: TestClient) -> None:
    offer_id = _offer(api)
    body = api.get(f"/decisions/deal:{offer_id}/exposure").json()
    assert body["customer_context"]["profile_href"] == "/customers/BUYER-1" and "context" not in body
    assert [p["key"] for p in body["paths"]][-1] == "do_nothing" and all(k in body["paths"][0] for k in WORDS)


# ---------------------------------------------------------------- 4. context.back from the query


def test_the_back_link_is_built_from_the_query(api: TestClient) -> None:
    offer_id = _offer(api)
    assert "context" not in _read(api, offer_id)  # nothing in the query, no back link
    got = _read(api, offer_id, customer="BUYER-1")["context"]["back"]
    assert got == {"label": "Back to Foshan", "href": f"/customers/BUYER-1?decision=deal%3A{offer_id}"}
    got = _read(api, offer_id, customer="BUYER-1", invoice="RCV-A", path="asked")["context"]["back"]
    assert got["href"] == f"/customers/BUYER-1?decision=deal%3A{offer_id}&path=asked&invoice=RCV-A"
    assert _read(api, offer_id, "zh", customer="BUYER-1")["context"]["back"]["label"] == "返回Foshan"
    assert _read(api, offer_id, invoice="RCV-A")["context"]["back"]["href"].startswith("/customers/BUYER-1?")  # the invoice names its buyer


def test_a_query_that_names_nothing_of_the_buyer_is_ignored(api: TestClient) -> None:
    offer_id = _offer(api)
    assert "context" not in _read(api, offer_id, customer="NOBODY")
    back = _read(api, offer_id, customer="BUYER-1", invoice="RCV-NOPE", path="x y")["context"]["back"]
    assert back["href"] == f"/customers/BUYER-1?decision=deal%3A{offer_id}"
    other = api.get(f"/decisions/deal:{offer_id}/exposure", params={"customer": "BUYER-2", "path": "<script>"}).json()
    assert other["context"]["back"]["href"] == "/customers/BUYER-2"  # a decision that is not this buyer's is not carried


def test_the_deals_read_carries_the_back_link_on_the_open_offer(api: TestClient) -> None:
    offer_id = _offer(api)
    plain = api.get("/deals").json()["deals"]
    assert all("context" not in (d["open_offer"] or {}) for d in plain)
    deals = {d["counterparty_id"]: d for d in api.get("/deals", params={"customer": "BUYER-1", "invoice": "RCV-A"}).json()["deals"]}
    assert deals["BUYER-1"]["open_offer"]["context"]["back"] == {
        "label": "Back to Foshan", "href": f"/customers/BUYER-1?decision=deal%3A{offer_id}&invoice=RCV-A"}
    assert all("context" not in (d["open_offer"] or {}) for k, d in deals.items() if k != "BUYER-1")
    one = api.get("/deals/BUYER-1", params={"customer": "BUYER-1", "lang": "zh"}).json()["deal"]["open_offer"]
    assert one["context"]["back"]["label"] == "返回Foshan"


# ---------------------------------------------------------------- 7. the margin default, whatever the books are called


def _held(state: Any, inputs: Any = None) -> Any:
    from app.strategy.inputs import CustomerInputs

    return overview.Held(state, 0, "BUYER-1", inputs or CustomerInputs())


def test_the_default_margin_is_the_configs_whatever_the_fixture_is_called(rt: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    assert DEMO_GROSS_MARGIN_BP == 2000
    state = rt.store.get_state()
    for name in ("golden_sme", "public_sme", "anything else", None):
        m = overview._margin(_held(state.model_copy(update={"scenario": name})))
        assert (m.bp, m.record, m.provenance, m.assumed) == (2000, None, "DEMO", True), name
    monkeypatch.setattr(overview, "DEMO_GROSS_MARGIN_BP", 1500)  # one constant: the overview, its economics and the context all follow it
    assert overview._margin(_held(state)).bp == 1500
    assert overview.customer_context(state, _held(state).inputs, "BUYER-1", 0, None, "en")["contribution_display"] == "about ¥819k"


def test_an_owner_margin_overrides_the_default(rt: Runtime) -> None:
    from app.strategy.inputs import inputs_from_rows

    state = rt.store.get_state()
    row = CustomerInputRecord(org_id=state.org_id, counterparty_id="BUYER-1", field="margin_bp", value_json="1850", provenance="OWNER_ENTERED",
                              source_ref="test", entered_by="OWNER", entered_day=0, state_version=1)
    m = overview._margin(_held(state, inputs_from_rows([row])))
    assert (m.bp, m.assumed, m.provenance) == (1850, False, "OWNER_ENTERED") and m.record is row


def test_the_context_says_nothing_it_cannot_support(rt: Runtime) -> None:
    state = rt.store.get_state()
    aggregate = {"is_aggregate": True, "ar_buyer_fen": 0, "ar_total_fen": 1}
    ctx = overview.customer_context(state, _held(state).inputs, "BUYER-1", 0, aggregate, "en")
    assert ctx["owes_display"] is None and ctx["share_text"] is None and ctx["profile_href"] == "/customers/BUYER-1"
    bare = overview.customer_context(state.model_copy(update={"recurring_invoices": [], "receivables": []}), _held(state).inputs, "BUYER-1", 0, None, "zh")
    assert bare["contribution_display"] is None and bare["contribution_note"] is None and bare["owes_display"] is None


# ---------------------------------------------------------------- 8. the overview's authority is a sentence that stands alone


def _path(authority: str | None, text: str = "fragment") -> Any:
    return {"authority": authority, "authority_text": text}


def test_the_overview_authority_is_a_full_sentence_by_the_pictures_class() -> None:
    say = overview._authority_sentence
    assert say(_path("flow_may"), "counter", "en") == "This counter is within your mandate: no approval needed."
    assert say(_path("needs_owner"), "counter", "en") == "This counter needs your approval before it is sent."
    assert say(_path("over_limit"), "counter", "en") == "This counter is over a limit you signed: only a new mandate changes that."
    assert say(_path("over_limit"), "request", "en") == "This request is over a limit you signed: only a new mandate changes that."
    assert say(_path("needs_owner"), "counter", "zh") == "这份还价需要您批准后才能发送。"
    assert say(_path("over_limit"), "request", "zh") == "这项请求超出您签署的上限：只有签署新的授权才能改变。"
    assert say(_path(None, "FLOW counters instead"), "request", "en") == "FLOW counters instead"  # no class: the picture's own words


def test_the_overview_decision_reads_the_sentence(api: TestClient) -> None:
    _offer(api)
    d = api.get("/customers/BUYER-1/overview").json()["decision"]
    assert d["authority_text"] == "This counter is within your mandate: no approval needed."
    zh = api.get("/customers/BUYER-1/overview", params={"lang": "zh"}).json()["decision"]
    assert zh["authority_text"] == "这份还价在您的授权范围内：无需批准。"


# ---------------------------------------------------------------- the do_nothing path carries words only


def test_do_nothing_has_explicit_null_entries_in_the_keyed_maps(api: TestClient) -> None:
    offer_id = _offer(api)
    for body in (_read(api, offer_id), api.get(f"/decisions/deal:{offer_id}/exposure").json()):
        assert body["band"]["by_path"]["do_nothing"] is None and "do_nothing" in body["band"]["by_path"]
        assert "do_nothing" in body["capacity"] and body["capacity"]["do_nothing"] is None
        assert "do_nothing" in body["stress"]["paths"] and body["stress"]["paths"]["do_nothing"] is None
        assert all(extra["paths"]["do_nothing"] is None for extra in body["stress"]["also"])
        assert all(body["band"]["by_path"][p["key"]] is not None for p in body["paths"] if p["kind"] != "do_nothing")


def test_the_words_are_worked_out_once_with_the_cached_block(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import exposure_words as words

    offer_id = _offer(api)
    calls: list[str] = []
    real = words.deal_extras
    monkeypatch.setattr(words, "deal_extras", lambda *a, **k: (calls.append("words"), real(*a, **k))[1])
    first = _read(api, offer_id)
    second = _read(api, offer_id)
    assert calls == ["words"] and first["paths"] == second["paths"] and first["customer_context"] == second["customer_context"]
    _read(api, offer_id, "zh")
    assert calls == ["words", "words"]  # another language is another block


# ---------------------------------------------------------------- one predicate for "assumed for the Demo"


def test_a_margin_the_demo_entered_is_assumed_like_no_margin_at_all(rt: Runtime) -> None:
    from app.strategy.inputs import inputs_from_rows

    state = rt.store.get_state()
    row = CustomerInputRecord(org_id=state.org_id, counterparty_id="BUYER-1", field="margin_bp", value_json="1500", provenance="ESTIMATED",
                              source_ref="Demo assumption", entered_by="DEMO", entered_day=0, state_version=1)
    m = overview._margin(_held(state, inputs_from_rows([row])))
    assert (m.bp, m.assumed, m.provenance) == (1500, True, "DEMO") and m.record is row
    ctx = overview.customer_context(state, inputs_from_rows([row]), "BUYER-1", 0, None, "en")
    assert ctx["contribution_note"].endswith("margin assumed for the Demo, not confirmed by you")


def test_the_overviews_value_figure_and_the_context_say_the_same_thing_of_the_same_number(api: TestClient, rt: Runtime) -> None:
    offer_id = _offer(api)
    figure = api.get("/customers/BUYER-1/overview").json()["figures"][0]
    ctx = _read(api, offer_id)["customer_context"]
    assert figure["value_display"] == ctx["contribution_display"]
    assert figure["note"] == "a year, estimated contribution; margin assumed for the Demo, not confirmed by you"
    assert figure["note"].endswith(ctx["contribution_note"].split("; ")[1])
    state = rt.store.get_state()
    rt.store.add_customer_input(CustomerInputRecord(
        org_id=state.org_id, counterparty_id="BUYER-1", field="margin_bp", value_json="3000", provenance="OWNER_ENTERED",
        source_ref="test", entered_by="OWNER", entered_day=0, state_version=state.state_version))
    assert api.get("/customers/BUYER-1/overview").json()["figures"][0]["note"] == "a year, estimated contribution"


# ---------------------------------------------------------------- the scenario assumption on every path (words batch 3)


def test_each_path_states_what_its_line_assumes(api: TestClient) -> None:
    offer_id = _offer(api)
    paths = _paths(_read(api, offer_id))
    assert paths["asked"]["scenario_assumption_text"] == "Assumes the buyer accepts this offer and FLOW takes no new funding."
    assert paths["do_nothing"]["scenario_assumption_text"] == "The books as they stand, no new funding."
    assert paths["A"]["scenario_assumption_text"] == (
        "Assumes the buyer accepts this reply and FLOW's funding plan runs (¥147k credit-line draw today); without the plan, cash falls lower.")
    assert paths["B"]["scenario_assumption_text"] == (
        "Assumes the buyer accepts this reply and FLOW's funding plan runs (¥90k credit-line draw today, ¥315k invoice financing in 3 days); "
        "without the plan, cash falls lower.")
    # the exposure read says what the picture says of the same path
    pictured = {p["key"]: p["scenario_assumption_text"] for p in api.get(f"/offers/{offer_id}/picture").json()["paths"]}
    assert all(paths[k]["scenario_assumption_text"] == pictured[paths[k]["key"]] for k in ("asked", "A", "B"))
    zh = _paths(_read(api, offer_id, "zh"))
    assert zh["asked"]["scenario_assumption_text"] == "假设买方接受此报价，且 FLOW 不新增融资。"
    assert zh["do_nothing"]["scenario_assumption_text"] == "当前账目，未新增融资。"
    assert zh["A"]["scenario_assumption_text"] == "假设买方接受此回复，且 FLOW 的融资方案得以执行（信用额度提款 ¥147k（今天））；没有该方案，现金会更低。"
    assert zh["B"]["scenario_assumption_text"] == (
        "假设买方接受此回复，且 FLOW 的融资方案得以执行（信用额度提款 ¥90k（今天）、发票融资 ¥315k（3 天后））；没有该方案，现金会更低。")


def test_before_the_offer_is_evaluated_the_asked_path_still_says_what_it_assumes(api: TestClient) -> None:
    offer_id = str(api.post("/offers", json=EX01).json()["offer"]["offer_id"])
    paths = _paths(_read(api, offer_id))
    assert paths["asked"]["scenario_assumption_text"] == "Assumes the buyer accepts this offer and FLOW takes no new funding."
    assert paths["do_nothing"]["scenario_assumption_text"] == "The books as they stand, no new funding."
