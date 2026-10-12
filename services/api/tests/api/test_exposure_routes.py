"""The buyer-exposure routes (map #88 Phase 1): owner only, behind FEATURE_EXPOSURE, the whole block for EX01 on the golden books
(the concentration, the payment behaviour, the 30-day stress with its line, the capacity before and after each path and the spare
room, the Demo's pins), the two ids resolving to the same buyer, one answer per key in the cache with `spare=0` skipping the search,
the Chinese read with the same figures as the English one (the helper of map #65 Wave 7), and P8: the verdict is byte-identical
with the flag on and off."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import strategy_exposure as route
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.strategy import exposure as assembly
from tests.api.conftest import english_leaks, figures, unchanged_words

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Bank credit line",
         "Invoice financing (onboarded platform)", "Buyer early-payment offer"]  # the buyers and the facilities the books name
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


@pytest.fixture
def offer_id(api: TestClient) -> str:
    return str(api.post("/offers", json=EX01).json()["offer"]["offer_id"])


# ---------------------------------------------------------------- the gate


def test_both_routes_are_403_with_the_flag_off(api: TestClient, offer_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_EXPOSURE", raising=False)
    for url in (f"/offers/{offer_id}/exposure", f"/decisions/deal:{offer_id}/exposure", "/offers/NOPE/exposure"):
        r = api.get(url)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "FEATURE_DISABLED"
        assert r.json()["detail"]["feature"] == "exposure"


def test_the_flag_is_off_by_default_and_listed_on_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_EXPOSURE", raising=False)
    assert get_settings().features.exposure is False
    from app.main import app

    assert TestClient(app).get("/health").json()["features"]["exposure"] is False
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    assert get_settings().features.exposure is True


def test_the_owner_alone_may_read(api: TestClient, offer_id: str) -> None:
    from app.main import app

    bare = TestClient(app)  # no default credentials
    for headers in ({}, AGENT, {"X-Owner-Token": "wrong"}):
        assert bare.get(f"/offers/{offer_id}/exposure", headers=headers).status_code == 401
        assert bare.get(f"/decisions/deal:{offer_id}/exposure", headers=headers).status_code == 401
    assert bare.get(f"/offers/{offer_id}/exposure", headers=OWNER).status_code == 200


def test_an_unknown_offer_or_decision_is_a_404(api: TestClient, offer_id: str) -> None:
    r = api.get("/offers/OFF-nope/exposure")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "OFFER_NOT_FOUND"
    for decision in ("deal:OFF-nope", "alert:ALERT-RESERVE-12:v1", "nonsense"):  # no such deal, and a funding decision has no buyer
        r = api.get(f"/decisions/{decision}/exposure")
        assert r.status_code == 404 and r.json()["detail"]["code"] == "DECISION_NOT_FOUND", decision


def test_the_response_is_asked_or_a_counter_that_exists(api: TestClient, offer_id: str) -> None:
    assert api.get(f"/offers/{offer_id}/exposure?response=asked").status_code == 200
    for bad in ("counter", "counter:", "counter:-1", "counter:x", "ASKED", "other"):
        assert api.get(f"/offers/{offer_id}/exposure", params={"response": bad}).status_code == 422, bad
    assert api.get(f"/offers/{offer_id}/exposure?response=counter:0").status_code == 404  # not evaluated yet: no counters
    verdict = api.post(f"/offers/{offer_id}/evaluate", json=EX01).json()
    assert verdict["counters"], "EX01 has counter-offers on the golden books"
    ok = api.get(f"/offers/{offer_id}/exposure?response=counter:0")
    assert ok.status_code == 200 and ok.json()["response"] == "counter:0"
    missing = api.get(f"/offers/{offer_id}/exposure?response=counter:{len(verdict['counters'])}")
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "COUNTER_NOT_FOUND"
    assert api.get(f"/offers/{offer_id}/exposure?lang=fr").status_code == 422


# ---------------------------------------------------------------- the block


def test_a_read_before_the_offer_is_evaluated_has_one_path_and_no_package(api: TestClient, offer_id: str) -> None:
    body = api.get(f"/offers/{offer_id}/exposure").json()
    assert body["offer_id"] == offer_id and body["buyer_id"] == "BUYER-1" and body["buyer_name"] == "Foshan Home Retail Co."
    assert body["buyer"] == {"id": "BUYER-1", "name": "Foshan Home Retail Co."}
    assert body["response"] == "asked" and body["day"] == 0 and body["partial"] is False and body["state_version"] == 1
    assert [p["key"] for p in body["paths"]] == ["asked"] and body["lead"] == "asked"
    assert body["capacity"]["asked"]["after"] is None  # nothing to bind yet: the asked path is the books as they stand
    assert body["capacity"]["asked"]["spare"]["x_star_fen"] == 8_100_000
    c, p = body["concentration"], body["payments"]
    assert c["sentence"] == ("Foshan is 100% of what you are owed today (¥420,000). "
                             "No customer receipts are due in the next 30 days.")
    assert c["ar_share_bp"] == 10_000 and c["ar_buyer_display"] == "¥420,000.00" and c["receipts_share_bp"] is None
    assert p["insufficient"] is True and p["completed"] == 0 and p["median_days_late"] is None
    assert p["insufficient_text"].startswith("FLOW has no completed payments from Foshan in the last 12 months")


def _by_label(body: dict[str, Any]) -> dict[str, str]:
    """The path key of each column: the Deals page's own ("asked" and the counters' ids)."""
    return {p["label"]: p["key"] for p in body["paths"]}


def test_the_whole_block_for_ex01_on_the_golden_books(api: TestClient, offer_id: str) -> None:
    verdict = api.post(f"/offers/{offer_id}/evaluate", json=EX01).json()
    body = api.get(f"/offers/{offer_id}/exposure?response=counter:0").json()
    keys = _by_label(body)
    assert list(keys) == ["As they asked", "Option A", "Option B"]
    assert keys["As they asked"] == "asked" and [keys["Option A"], keys["Option B"]] == [c["id"] for c in verdict["counters"]]
    a, b = keys["Option A"], keys["Option B"]
    assert body["partial"] is False and body["economics"] is None and body["loss"] is None and body["spare_read"] is True
    assert body["lead"] == a and set(body["capacity"]) == set(body["stress"]["paths"]) == set(keys.values())

    # concentration: Foshan is all of what is owed
    assert body["concentration"]["ar_share_bp"] == 10_000 and body["band"]["concentration"] == body["concentration"]["sentence"]
    assert body["flag"]["material"] is True and body["flag"]["text"] == "Foshan is 100% of what you are owed"

    # the stress on the books as they stand: -¥250,000 on day 60, 65 days below the minimum, ¥550,000, no admissible plan
    now = body["stress"]["now"]
    assert body["stress"]["delay_days"] == 30
    assert (now["lowest_fen"], now["lowest_day"], now["breach_days"], now["need_fen"]) == (-25_000_000, 60, 65, 55_000_000)
    assert now["plan_admissible"] is False and now["plan_cost_fen"] is None
    assert (now["lowest_display"], now["lowest_short"], now["lowest_when"]) == ("−¥250,000.00", "−¥250k", "in 60 days")
    assert now["text"] == ("Paid 30 days late: cash falls to −¥250,000 in 60 days, 65 days below your minimum; "
                           "no committed facility covers the ¥550,000.")
    assert now["assumption"].startswith("If Foshan Home Retail Co. paid every invoice 30 days late (a test, not a forecast).")
    assert now["history_text"].startswith("FLOW has no completed payments from Foshan")  # below the minimums: no "typical"
    # every stressed line is the server's series, from today, and its lowest point is the moment the row names
    for row in (now, *body["stress"]["paths"].values()):
        series = row["series"]
        assert series[0]["day"] == 0 and set(series[0]) == {"day", "closing_fen", "closing_display"}
        assert min(series, key=lambda r: (r["closing_fen"], r["day"]))["day"] == row["lowest_day"]
        assert min(r["closing_fen"] for r in series) == row["lowest_fen"]
        assert all(r["closing_display"] == f"{'−' if r['closing_fen'] < 0 else ''}¥{abs(r['closing_fen']) / 100:,.2f}" for r in series)
    option_a = body["stress"]["paths"][a]
    assert (option_a["lowest_fen"], option_a["breach_days"]) == (-25_000_000, 65)
    assert body["stress"]["paths"]["asked"]["breach_days"] > option_a["breach_days"]  # the package changes the stressed line, not just a label

    # the spare room: ¥81,000 today, ¥14,000 as asked, ¥0 under Option A, ¥62,000 under Option B
    spare = {k: body["capacity"][k]["spare"] for k in keys.values()}
    assert {k: v["today_fen"] for k, v in spare.items()} == dict.fromkeys(keys.values(), 8_100_000)
    assert [spare[k]["x_star_fen"] for k in ("asked", a, b)] == [1_400_000, 0, 6_200_000]
    assert [spare[k]["figure_short"] for k in ("asked", a, b)] == ["¥14k", "¥0", "¥62k"]
    assert spare[a]["today_short"] == "¥81k" and spare[a]["refused_text"] is None
    assert spare[a]["shape_text"].startswith("Counted as a one-off payment of X today") and spare[a]["binding_text"]
    assert body["band"]["capacity"] == ("Option A leaves ¥0 of room for another payment for the next 31 days; today ¥81,000.")
    assert body["band"]["by_path"]["asked"]["capacity"] == "Accepting as asked leaves ¥14,000 of room for another payment; today ¥81,000."
    assert body["band"]["by_path"][b]["capacity"] == "Option B leaves ¥62,000 of room for another payment; today ¥81,000."
    assert body["band"]["stress"] == body["band"]["by_path"][a]["stress"] == option_a["text"]

    # capacity before and after: the line has ¥13.80 left through day 31 under Option A
    cap = body["capacity"][a]
    line = next(w for w in cap["after"]["windows"] if w["dimension"] == "credit_line")
    assert (line["today_fen"], line["today_short"], line["through_when"], line["recovers_when"]) == (1_380, "¥13.80", "in 31 days", "in 32 days")
    assert line["after_short"] == "¥150k" and line["facility_name"] == "Bank credit line" and line["over_by"] is False
    before = next(w for w in cap["before"]["windows"] if w["dimension"] == "credit_line")
    assert before["today_fen"] == 0 and before["label"] == "Credit line room"
    buffer = next(w for w in cap["after"]["windows"] if w["dimension"] == "cash_buffer")
    assert buffer["over_by"] is True and buffer["today_text"] == "¥100,000.00"
    assert {w["dimension"] for w in cap["before"]["windows"]} >= {"cash_buffer", "credit_line", "invoice_finance", "concession", "dscr_room"}
    iff = next(w for w in cap["after"]["windows"] if w["dimension"] == "invoice_finance" and w["reading"] == "TODAY")
    assert iff["reason_text"].startswith("no invoice can be financed")  # a reason in words, never a code
    assert body["capacity"]["asked"]["after"]["windows"][0]["dimension"] == "cash_buffer"


def test_the_response_leads_the_band_and_nothing_else_changes(api: TestClient, offer_id: str) -> None:
    api.post(f"/offers/{offer_id}/evaluate", json=EX01)
    first = api.get(f"/offers/{offer_id}/exposure?response=asked").json()
    second = api.get(f"/offers/{offer_id}/exposure?response=counter:1").json()
    assert first["lead"] == "asked" and second["lead"] == second["paths"][2]["key"]
    assert first["band"]["capacity"].startswith("Accepting as asked") and second["band"]["capacity"].startswith("Option B")
    drop = {"response", "lead", "band", "computed_in_seconds"}
    assert {k: v for k, v in first.items() if k not in drop} == {k: v for k, v in second.items() if k not in drop}
    assert first["band"]["by_path"] == second["band"]["by_path"]


def test_a_buyer_with_nothing_to_pay_late_has_no_stress_and_still_has_capacity(api: TestClient, rt: Runtime, offer_id: str) -> None:
    stored = rt.store.get_offer(offer_id)
    assert stored is not None
    rt.store.put_offer(stored.model_copy(update={"offer_id": "OFF-dongguan", "counterparty_id": "BUYER-2"}))
    body = api.get("/offers/OFF-dongguan/exposure?spare=0").json()
    assert body["stress"]["now"]["available"] is False and body["stress"]["now"]["unavailable_text"].startswith("No late-payment test for Dongguan")
    assert body["band"]["stress"] is None and body["flag"] == {"material": False, "text": None, "min_share_bp": 5000,
                                                                 "min_share_display": "50.00%"}
    assert body["capacity"]["asked"]["before"]["windows"]


def test_the_read_writes_nothing(api: TestClient, rt: Runtime, offer_id: str) -> None:
    state, chain = rt.store.get_state().model_dump_json(), [e.entry_hash for e in rt.store.operations()]
    facts, inputs = len(rt.store.decision_facts()), len(rt.store.all_customer_inputs())  # type: ignore[attr-defined]
    for url in (f"/offers/{offer_id}/exposure", f"/decisions/deal:{offer_id}/exposure?lang=zh"):
        assert api.get(url).status_code == 200
    assert rt.store.get_state().model_dump_json() == state and [e.entry_hash for e in rt.store.operations()] == chain
    assert (len(rt.store.decision_facts()), len(rt.store.all_customer_inputs())) == (facts, inputs)  # type: ignore[attr-defined]


def test_the_offer_and_its_deal_decision_resolve_to_the_same_buyer_and_the_same_block(api: TestClient, offer_id: str) -> None:
    by_offer = api.get(f"/offers/{offer_id}/exposure").json()
    by_decision = api.get(f"/decisions/deal:{offer_id}/exposure").json()
    assert by_decision["decision_id"] == f"deal:{offer_id}" and by_decision["offer_id"] == offer_id
    drop = {"decision_id", "computed_in_seconds"}
    assert {k: v for k, v in by_decision.items() if k not in drop} == {k: v for k, v in by_offer.items() if k not in drop}
    assert by_decision["buyer_id"] == by_offer["buyer_id"] == "BUYER-1"


def test_an_offer_from_the_other_buyer_shows_that_buyer(api: TestClient, rt: Runtime, offer_id: str) -> None:
    stored = rt.store.get_offer(offer_id)
    assert stored is not None
    rt.store.put_offer(stored.model_copy(update={"offer_id": "OFF-dongguan", "counterparty_id": "BUYER-2"}))
    body = api.get("/offers/OFF-dongguan/exposure").json()
    assert body["buyer_id"] == "BUYER-2" and body["concentration"]["ar_text"] == "Dongguan owes you nothing today."


def test_the_owners_inputs_reach_the_block(api: TestClient, offer_id: str) -> None:
    before = api.get(f"/offers/{offer_id}/exposure").json()
    assert before["payments"]["delay_basis"] == "NONE" and before["concentration"]["is_aggregate"] is False
    for body in ({"field": "typical_delay_days", "value": 15, "provenance": "OWNER_ENTERED", "source_ref": ""},
                 {"field": "aggregate", "value": True, "provenance": "OWNER_ENTERED", "source_ref": ""}):
        assert api.post("/buyers/BUYER-1/inputs", json=body).status_code == 200
    after = api.get(f"/offers/{offer_id}/exposure").json()  # the new rows are part of the key: not the cached block
    assert after["payments"]["typical_delay_days"] == 15 and after["payments"]["delay_basis"] == "OWNER_ENTERED"
    assert after["concentration"]["is_aggregate"] is True and after["concentration"]["ar_share_bp"] is None


# ---------------------------------------------------------------- the cache


def _count(monkeypatch: pytest.MonkeyPatch, name: str) -> list[str]:
    calls: list[str] = []
    real = getattr(assembly, name)

    def counted(*a: Any, **k: Any) -> Any:
        calls.append(name)
        return real(*a, **k)

    monkeypatch.setattr(assembly, name, counted)
    return calls


def test_one_computation_serves_every_repeat_every_response_and_both_ids(api: TestClient, offer_id: str,
                                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _count(monkeypatch, "concentration")
    for url in (f"/offers/{offer_id}/exposure", f"/offers/{offer_id}/exposure", f"/decisions/deal:{offer_id}/exposure"):
        assert api.get(url).status_code == 200
    assert calls == ["concentration"]
    api.get(f"/offers/{offer_id}/exposure?lang=zh")  # the language is part of the key ...
    assert len(calls) == 2
    api.post(f"/offers/{offer_id}/evaluate", json=EX01)  # ... and so is the verdict (the paths depend on it) ...
    api.get(f"/offers/{offer_id}/exposure?response=counter:0")
    assert len(calls) == 3
    for response in ("counter:0", "counter:1", "asked"):  # ... but the picked column is not: switching it needs no new computation
        api.get(f"/offers/{offer_id}/exposure?response={response}")
    assert len(calls) == 3


def test_spare_zero_skips_the_search_and_a_later_read_pays_only_for_it(api: TestClient, offer_id: str,
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    api.post(f"/offers/{offer_id}/evaluate", json=EX01)
    searches = _count(monkeypatch, "spare_capacity")
    light = api.get(f"/offers/{offer_id}/exposure?spare=0").json()
    assert searches == [] and light["spare_read"] is False and light["band"]["capacity"] is None
    assert all(v["spare"] is None for v in light["capacity"].values()) and light["stress"]["now"]["lowest_fen"] == -25_000_000
    assert all(v["after"] is not None for v in light["capacity"].values())  # the windows do not need the search
    full = api.get(f"/offers/{offer_id}/exposure").json()  # spare defaults to 1
    assert len(searches) == 4 and full["spare_read"] is True  # the books as they stand, then each of the three paths
    api.get(f"/offers/{offer_id}/exposure")
    api.get(f"/decisions/deal:{offer_id}/exposure")  # the decision read asks for it too, and finds it searched
    assert len(searches) == 12  # asked for each time, answered by the capacity cache (the next test counts the real runs)
    assert api.get(f"/offers/{offer_id}/exposure?spare=2").status_code == 422


def test_the_search_itself_runs_once_per_package(api: TestClient, offer_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.strategy import capacity

    api.post(f"/offers/{offer_id}/evaluate", json=EX01)
    runs: list[int] = []
    real = capacity._search

    def counted(*a: Any, **k: Any) -> Any:
        runs.append(1)
        return real(*a, **k)

    monkeypatch.setattr(capacity, "_search", counted)
    for _ in range(3):
        assert api.get(f"/offers/{offer_id}/exposure").status_code == 200
    assert len(runs) == 4


def test_the_key_follows_the_books_the_day_and_the_commitments(api: TestClient, rt: Runtime, offer_id: str,
                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _count(monkeypatch, "concentration")
    api.get(f"/offers/{offer_id}/exposure?spare=0")
    assert api.post("/clock/advance", json={"to_day": 3}).status_code == 200
    body = api.get(f"/offers/{offer_id}/exposure?spare=0").json()
    assert body["day"] == 3 and len(calls) == 2


def test_a_failed_computation_is_not_cached(api: TestClient, offer_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.financial import EngineError

    real = assembly.concentration

    def boom(*a: Any, **k: Any) -> Any:
        raise EngineError("cannot")

    monkeypatch.setattr(assembly, "concentration", boom)
    r = api.get(f"/offers/{offer_id}/exposure?spare=0")
    assert r.status_code == 422 and "cannot project" in r.json()["detail"]
    monkeypatch.setattr(assembly, "concentration", real)
    assert api.get(f"/offers/{offer_id}/exposure?spare=0").status_code == 200


# ---------------------------------------------------------------- language


def test_the_chinese_read_has_the_same_figures_and_no_english_sentence_left(api: TestClient, offer_id: str) -> None:
    en = api.get(f"/offers/{offer_id}/exposure?lang=en").json()
    zh = api.get(f"/offers/{offer_id}/exposure?lang=zh").json()
    assert zh["lang"] == "zh"
    assert figures({k: v for k, v in en.items() if k not in ("computed_in_seconds", "lang")}) == figures(
        {k: v for k, v in zh.items() if k not in ("computed_in_seconds", "lang")})
    assert english_leaks(zh, NAMES) == []
    assert unchanged_words(en, zh, NAMES) == []
    assert zh["concentration"]["sentence"] == "Foshan占您目前全部应收款的 100%（¥420,000）。未来 30 天内没有客户回款到期。"
    assert zh["payments"]["insufficient_text"].startswith("FLOW 在过去 12 个月内没有Foshan的已完成付款")


def test_the_chinese_read_of_the_whole_block_has_the_same_figures_and_no_english_sentence_left(api: TestClient, offer_id: str) -> None:
    api.post(f"/offers/{offer_id}/evaluate", json=EX01)
    en = api.get(f"/offers/{offer_id}/exposure?lang=en&response=counter:0").json()
    zh = api.get(f"/offers/{offer_id}/exposure?lang=zh&response=counter:0").json()
    drop = ("computed_in_seconds", "lang")
    assert figures({k: v for k, v in en.items() if k not in drop}) == figures({k: v for k, v in zh.items() if k not in drop})
    assert english_leaks(zh, NAMES) == []
    assert unchanged_words(en, zh, NAMES) == []
    assert zh["band"]["capacity"] == "采用方案 A 后，再支付一笔款项的余量为 ¥0（未来 31 天内）；目前为 ¥81,000。"
    assert zh["band"]["stress"] == "晚付 30 天：60 天后现金将跌至 −¥250,000，有 65 天低于您的最低现金；您已承诺的融资额度无法弥补 ¥550,000 的缺口。"
    assert zh["band"]["by_path"]["asked"]["capacity"] == "按对方要求接受后，再支付一笔款项的余量为 ¥14,000；目前为 ¥81,000。"
    assert zh["flag"]["text"] == "Foshan占您应收款的 100%"
    line = next(w for w in zh["capacity"][zh["lead"]]["after"]["windows"] if w["dimension"] == "credit_line")
    assert (line["label"], line["through_when"], line["facility_name"]) == ("授信额度余量", "31 天后", "Bank credit line")


# ---------------------------------------------------------------- P8: customer context never touches a verdict


def _evaluated(monkeypatch: pytest.MonkeyPatch, flag: bool, inputs: list[dict[str, Any]], read: bool) -> str:
    """EX01 evaluated on a fresh golden runtime with the flag on or off (and, on, the owner's inputs written and the exposure read
    before and after): the verdict as the owner sees it, serialised."""
    if flag:
        monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    else:
        monkeypatch.delenv("FEATURE_EXPOSURE", raising=False)
    from app.main import app

    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    route.clear_cache()
    client = TestClient(app, headers=OWNER)
    oid = str(client.post("/offers", json=EX01).json()["offer"]["offer_id"])
    if flag:
        for body in inputs:
            assert client.post("/buyers/BUYER-1/inputs", json=body).status_code == 200
        if read:
            assert client.get(f"/offers/{oid}/exposure").status_code == 200
    view = client.post(f"/offers/{oid}/evaluate", json=EX01).json()
    if flag and read:
        assert client.get(f"/offers/{oid}/exposure").status_code == 200
        assert client.get(f"/decisions/deal:{oid}/exposure?lang=zh").status_code == 200
        view = client.post(f"/offers/{oid}/evaluate", json=EX01).json()
    keep = ("outcome", "required_tier", "violations", "bound_obligations", "concession_values", "forward_concession_total_fen",
            "counters", "plan", "summary", "business_action")
    return json.dumps({k: view.get(k) for k in keep}, sort_keys=True, ensure_ascii=False)


INPUTS = [
    [],
    [{"field": "typical_delay_days", "value": 45, "provenance": "OWNER_ENTERED", "source_ref": ""}],
    [{"field": "aggregate", "value": True, "provenance": "OWNER_ENTERED", "source_ref": ""}],
]


@pytest.mark.parametrize("inputs", INPUTS, ids=["none", "typical-delay", "aggregate"])
def test_p8_the_verdict_tier_counters_and_plan_are_byte_identical_with_the_flag_on_and_off(
        monkeypatch: pytest.MonkeyPatch, inputs: list[dict[str, Any]]) -> None:
    try:
        off = _evaluated(monkeypatch, False, [], False)
        on = _evaluated(monkeypatch, True, inputs, True)
        on_unread = _evaluated(monkeypatch, True, inputs, False)
    finally:
        set_runtime(None)
        route.clear_cache()
    assert json.loads(off)["counters"], "EX01 has counters on the golden books"
    assert on == off == on_unread


def test_the_chinese_read_of_a_buyer_with_owner_input_and_an_aggregate_is_in_chinese(api: TestClient, offer_id: str) -> None:
    api.post("/buyers/BUYER-1/inputs", json={"field": "typical_delay_days", "value": 15, "provenance": "ESTIMATED",
                                              "source_ref": "Demo assumption"})
    zh = api.get(f"/decisions/deal:{offer_id}/exposure?lang=zh").json()
    assert english_leaks(zh, NAMES) == []
    assert zh["payments"]["owner_delay_text"] == "通常的延迟：15 天，估计值，不是记录（FLOW 的收款记录太少，无法衡量）。"
