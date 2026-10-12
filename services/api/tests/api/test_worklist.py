"""GET /worklist (Home V2 wave 1, the server half): the company alert, Needs you, Waiting and Customers, the ordering rule, both languages.

Golden day 0: the Foshan offer (60-day terms, a 1% rebate, early payment) is evaluated, and FLOW's plan (a ¥150k credit-line draw and ¥255k
of invoice financing) is either ready or has run. The alert is the company's cash and is counted nowhere; Needs you holds the Foshan
decision. Every figure is another read's own (the Home status, the offer picture, the receivable rows, the reconciliation)."""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import english_leaks, figures
from tests.api.test_time_semantics import _walk

OWNER = {"X-Owner-Token": "demo-owner-token"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan"]
EX01 = {"fixture_id": "EX01_PACKAGE"}
RAW_ID = re.compile(r"\b(?:RCV|BUYER|FAC|LOT|CMT|OFF|CTR|VER|OP|APR|DOC)-[A-Za-z0-9]|RI:|\bday -?\d")
HREFS = r".*href"


@pytest.fixture
def rt(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
    monkeypatch.setenv("FEATURE_HOME_V2", "1")
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    worklist.clear_cache()
    offer_picture._cache.clear()
    yield runtime
    set_runtime(None)
    worklist.clear_cache()
    offer_picture._cache.clear()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _offer(api: TestClient, fixture: str = "EX01_PACKAGE") -> str:
    offer = api.post("/offers", json={"fixture_id": fixture}).json()["offer"]
    api.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": fixture})
    return str(offer["offer_id"])


def _run_plan(api: TestClient) -> None:
    a = api.get("/home").json()["next_action"]
    r = api.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()
    assert r["executed"] == 2


def _get(api: TestClient, lang: str = "en", **query: Any) -> dict[str, Any]:
    r = api.get("/worklist", params={"lang": lang, **query})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _strings(x: Any) -> Iterator[str]:
    if isinstance(x, dict):
        for k, v in x.items():
            if not k.endswith("href") and k not in ("key", "customer_id"):
                yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)
    elif isinstance(x, str):
        yield x


# ---------------------------------------------------------------- the gate


def test_the_flag_is_off_by_default_and_listed_on_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_HOME_V2", raising=False)
    assert get_settings().features.home_v2 is False
    from app.main import app

    assert TestClient(app).get("/health").json()["features"]["home_v2"] is False
    monkeypatch.setenv("FEATURE_HOME_V2", "1")
    assert get_settings().features.home_v2 is True
    assert TestClient(app).get("/health").json()["features"]["home_v2"] is True


def test_with_the_flag_off_the_route_is_the_standard_403(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_HOME_V2", raising=False)
    r = api.get("/worklist")
    assert r.status_code == 403
    assert r.json()["detail"] == {"code": "FEATURE_DISABLED", "feature": "home_v2", "message": "Home V2 is switched off (FEATURE_HOME_V2)."}


def test_the_owner_alone_may_read(api: TestClient) -> None:
    from app.main import app

    bare = TestClient(app)
    for headers in ({}, {"X-Owner-Token": "wrong"}):
        assert bare.get("/worklist", headers=headers).status_code == 401
    assert bare.get("/worklist", headers=OWNER).status_code == 200


# ---------------------------------------------------------------- golden: before and after the plan


def test_before_the_plan_the_alert_is_there_and_needs_you_holds_the_foshan_decision(api: TestClient) -> None:
    oid = _offer(api)
    w = _get(api)
    assert w["alert"] == {"key": "company-cash", "eyebrow": "Company cash", "text": "Reserve unsafe in 12 days. A funding plan is ready.",
                          "tone": "bad", "primary": {"label": "Run or compare", "href": "/"}}
    assert [i["key"] for i in w["needs_you"]] == [f"deal:{oid}"]
    item = w["needs_you"][0]
    assert (item["kind"], item["owner"], item["severity"], item["customer_short"]) == ("DECISION", "NEEDS_YOU", "CAUTION", "Foshan")
    assert (item["subject_text"], item["status_text"]) == ("Foshan · Payment terms", "Counter ready · Reply needed")
    assert item["consequence_text"] == "As asked: below your minimum for 15 days."
    assert item["deadline_day"] == 47 and item["is_new"] is False
    assert item["why_first_text"] == "Why first: cash falls below your minimum before any other item matters."
    assert item["href"] == "/?customer=BUYER-1&deal=deal%3A" + oid
    assert not any("reserve" in i["subject_text"].lower() for i in w["needs_you"])  # the alert is not a row
    assert w["waiting"] == []


def test_after_the_plan_the_alert_is_gone_and_the_financing_waits(api: TestClient) -> None:
    _offer(api)
    _run_plan(api)
    w = _get(api)
    assert w["alert"] is None
    assert [i["kind"] for i in w["needs_you"]] == ["DECISION"]  # the Foshan decision is still the owner's
    assert w["needs_you"][0]["consequence_text"] == "Over your limit as asked; it does not take cash below your minimum."
    assert w["needs_you"][0]["severity"] == "CAUTION" and w["needs_you"][0]["deadline_day"] is None
    assert w["needs_you"][0]["why_first_text"] == "Why first: it has the largest effect on your cash."
    [wait] = w["waiting"]
    assert (wait["kind"], wait["owner"], wait["severity"]) == ("SETTLEMENT", "WAITING", "NORMAL")
    assert (wait["subject_text"], wait["status_text"], wait["consequence_text"]) == (
        "Invoice financing · ¥255k", "Financing arranged, expected in 3 days", "Not counted as cash until it lands.")
    assert wait["expected_day"] == 3 and wait["customer_id"] == "BUYER-1"


def test_the_counts_equal_the_rows_and_the_alert_is_counted_nowhere(api: TestClient) -> None:
    _offer(api)
    for moment in ("before", "after"):
        if moment == "after":
            _run_plan(api)
        w = _get(api)
        assert w["counts"] == {"needs_you": len(w["needs_you"]), "waiting": len(w["waiting"]), "customers": len(w["customers"])}
        assert w["counts"]["customers"] == 2
        assert all(k not in {i["key"] for i in w["needs_you"] + w["waiting"]} for k in ("company-cash",))


def test_the_first_row_alone_says_why_it_is_first(api: TestClient) -> None:
    _offer(api, "EX01_PACKAGE")
    _offer(api, "EX02_EARLY_1_5")
    rows = _get(api)["needs_you"]
    assert len(rows) == 2 and [r["kind"] for r in rows] == ["DECISION", "DECISION"]
    assert rows[0]["why_first_text"] and rows[1]["why_first_text"] is None


def test_one_row_per_decision_and_the_customer_counts_them(api: TestClient) -> None:
    _offer(api, "EX01_PACKAGE")
    _offer(api, "EX02_EARLY_1_5")
    w = _get(api)
    assert len({r["key"] for r in w["needs_you"]}) == 2
    foshan = next(c for c in w["customers"] if c["customer_id"] == "BUYER-1")
    assert (foshan["negotiations_count"], foshan["needs_you_count"]) == (2, 2)
    assert foshan["status_text"] == "2 open negotiations · 2 need you" and foshan["tone"] == "warn"
    # the one with a breach in front of it leads; its sibling follows
    assert w["needs_you"][0]["deadline_day"] == 47 and w["needs_you"][1]["deadline_day"] is None


def test_the_customers_lead_with_the_one_that_needs_you(api: TestClient) -> None:
    _offer(api)
    cs = _get(api)["customers"]
    assert [c["customer_id"] for c in cs] == ["BUYER-1", "BUYER-2"]
    assert (cs[0]["outstanding_display"], cs[0]["share_text"]) == ("¥420,000", "100% of what you are owed")
    assert cs[0]["href"] == "/?customer=BUYER-1"
    assert (cs[1]["status_text"], cs[1]["tone"], cs[1]["share_text"], cs[1]["outstanding_display"]) == ("Nothing open", "neutral", None, "¥0")


# ---------------------------------------------------------------- the other kinds of row


def test_a_missed_receipt_is_a_collection_row_and_the_alert_stays_beside_it(api: TestClient) -> None:
    _walk(api, receipt="half")
    w = _get(api)
    [item] = w["needs_you"]
    assert (item["kind"], item["severity"], item["customer_id"]) == ("COLLECTION", "CRITICAL", "BUYER-1")
    assert item["subject_text"] == "Foshan · ¥291k overdue"
    assert item["status_text"] == "Payment overdue · Your follow-up needed" and item["consequence_text"] == "2 days overdue."
    assert item["deadline_day"] == 32 and item["why_first_text"] == "Why first: a payment you expected has not arrived."
    assert w["alert"] is not None and w["alert"]["text"] == "Reserve unsafe today. A funding plan is ready."
    assert w["counts"]["needs_you"] == 1  # the alert is not counted
    foshan = next(c for c in w["customers"] if c["customer_id"] == "BUYER-1")
    assert (foshan["tone"], foshan["needs_you_count"], foshan["status_text"]) == ("bad", 1, "1 needs you")


def test_a_promised_payment_waits_and_is_not_cash(api: TestClient) -> None:
    _walk(api, to=2)
    w = _get(api)
    assert w["alert"] is None and w["needs_you"] == []
    [wait] = w["waiting"]
    assert (wait["kind"], wait["severity"], wait["subject_text"]) == ("PROMISE", "CAUTION", "Foshan · Payment promised")
    assert (wait["status_text"], wait["consequence_text"]) == ("Expected today · ¥255k", "Not counted as cash until it arrives.")
    assert wait["expected_day"] == 2
    assert next(c for c in w["customers"] if c["customer_id"] == "BUYER-1")["status_text"] == "1 waiting"


def test_the_plan_waiting_on_approval_is_the_alerts_and_not_a_row_of_needs_you(api: TestClient) -> None:
    from app.api.runtime import get_runtime
    from app.mandate.fixture import load_demo_owner_key
    from app.mandate.signing import sign

    store = get_runtime().store
    _offer(api)
    store.put_mandate(sign(store.get_mandate().model_copy(update={"max_apr_bp": 500}), load_demo_owner_key()["private_key_hex"]))
    a = api.get("/home").json()["next_action"]
    api.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]})
    assert api.get("/home").json()["next_action"]["pending_approval_id"]
    w = _get(api)
    assert w["alert"]["text"] == "Reserve unsafe in 12 days. The funding plan waits for your approval."
    assert w["alert"]["primary"] == {"label": "Review the plan", "href": "/"}
    assert [i["kind"] for i in w["needs_you"]] == ["DECISION"]  # the approval of the company's own funding is the alert's
    assert _get(api, "zh")["alert"]["text"] == "现金储备将在 12 天后变得不安全。融资方案正等待您批准。"


def test_an_unsafe_reserve_with_nothing_to_run_has_an_alert_that_points_at_the_options(api: TestClient) -> None:
    from app.api.runtime import get_runtime
    from tests.api.test_home import _exhaust_line

    _exhaust_line(get_runtime())
    w = _get(api)
    assert w["alert"]["text"] == "Reserve unsafe in 12 days. A funding plan is ready."  # the application for a facility is the plan
    assert w["needs_you"] == [] and w["counts"]["needs_you"] == 0


def test_the_alert_for_an_unsafe_reserve_with_no_plan_points_at_the_options() -> None:
    home = {"cash": {"first_breach_day": 12, "first_breach_when": "in 12 days"}, "next_action": None, "status": "CRITICAL"}
    en, zh = worklist._alert(home, "en"), worklist._alert({**home, "cash": {**home["cash"], "first_breach_when": "12 天后"}}, "zh")
    assert en is not None and zh is not None
    assert en["text"] == "Reserve unsafe in 12 days. No funding plan is ready yet." and en["primary"] == {"label": "See the options", "href": "/cash#cash-options"}
    assert zh["text"] == "现金储备将在 12 天后变得不安全。目前还没有准备好的融资方案。" and zh["primary"]["label"] == "查看选项"
    assert worklist._alert({"cash": {"first_breach_day": None}, "next_action": None}, "en") is None


def test_an_arrival_after_the_day_last_read_is_new(api: TestClient) -> None:
    _offer(api)
    assert _get(api)["needs_you"][0]["is_new"] is False  # without a day last read nothing is new
    assert _get(api, since_day=0)["needs_you"][0]["is_new"] is False  # received on day 0, not after it
    api.post("/clock/advance", json={"to_day": 1})
    assert [i["is_new"] for i in _get(api, since_day=0)["needs_you"]] == [False]


def test_the_read_is_cached_and_a_change_of_the_books_moves_it(api: TestClient) -> None:
    _offer(api)
    first = _get(api)
    assert _get(api) == first
    assert len(worklist._CACHE) >= 1
    _run_plan(api)
    assert _get(api)["alert"] is None and first["alert"] is not None


# ---------------------------------------------------------------- the ordering rule


def _row(key: str, kind: str = "DECISION", severity: str = "NORMAL", breach: int | None = None, deadline: int | None = None) -> worklist.Row:
    return worklist.Row(key=key, kind=kind, customer_id=None, customer_short=None, subject="", status="", consequence="", severity=severity,
                        deadline_day=deadline, breach_day=breach, href="")


SIX = [
    _row("a-breach-day-20", breach=20, deadline=20, severity="CAUTION"),
    _row("b-breach-day-47", breach=47, deadline=47, severity="CAUTION"),
    _row("c-approval-expires-5", kind="APPROVAL", deadline=5),
    _row("d-collection", kind="COLLECTION", severity="CAUTION", deadline=3),
    _row("e-material", severity="CAUTION"),
    _row("f-ordinary"),
]


def test_six_items_are_ordered_by_the_rule() -> None:
    """Cash safety (by breach day), then a deadline, then a missed receipt, then a material consequence, then an ordinary reply."""
    assert [r.key for r in worklist.order(SIX)] == [
        "a-breach-day-20", "b-breach-day-47", "c-approval-expires-5", "d-collection", "e-material", "f-ordinary"]
    assert [worklist.tier_of(r.kind, r.severity, r.breach_day, r.deadline_day) for r in worklist.order(SIX)] == [0, 0, 1, 2, 3, 4]


def test_the_order_does_not_depend_on_the_order_the_rows_arrive_in() -> None:
    want = [r.key for r in worklist.order(SIX)]
    for perm in itertools.permutations(SIX):
        assert [r.key for r in worklist.order(list(perm))] == want


def test_the_deadline_breaks_a_tie_and_a_missing_one_goes_last() -> None:
    rows = [_row("z-no-deadline", breach=30), _row("m-deadline-9", breach=30, deadline=9), _row("a-deadline-8", breach=30, deadline=8),
            _row("old-collection", kind="COLLECTION", deadline=1), _row("older-collection", kind="COLLECTION", deadline=0),
            _row("b-expires-2", kind="APPROVAL", deadline=2), _row("a-expires-2", kind="APPROVAL", deadline=2)]
    assert [r.key for r in worklist.order(rows)] == [
        "a-deadline-8", "m-deadline-9", "z-no-deadline", "a-expires-2", "b-expires-2", "older-collection", "old-collection"]


def test_a_collection_outranks_a_deadline_only_when_it_breaches_nothing_first() -> None:
    assert worklist.tier_of("COLLECTION", "CRITICAL", None, 3) == worklist.MISSED_RECEIPT
    assert worklist.tier_of("COLLECTION", "CRITICAL", 10, 3) == worklist.CASH_SAFETY
    assert worklist.tier_of("APPROVAL", "NORMAL", None, 7) == worklist.DEADLINE
    assert worklist.tier_of("DECISION", "CRITICAL", None, None) == worklist.MATERIAL
    assert worklist.tier_of("SETUP", "NORMAL", None, None) == worklist.ORDINARY


# ---------------------------------------------------------------- Chinese


def test_the_chinese_read_has_the_same_figures_and_no_english_or_ids(api: TestClient) -> None:
    _offer(api)
    en, zh = _get(api), _get(api, "zh")
    assert figures(en) == figures(zh)
    assert not english_leaks(zh, NAMES, raw_fields=[HREFS])
    assert not [s for s in _strings(zh) if RAW_ID.search(s)] and not [s for s in _strings(en) if RAW_ID.search(s)]
    assert zh["alert"]["text"] == "现金储备将在 12 天后变得不安全。融资方案已准备好。"
    item = zh["needs_you"][0]
    assert (item["subject_text"], item["status_text"]) == ("Foshan · 付款账期", "还价已就绪 · 需要您答复")
    assert item["consequence_text"] == "按对方要求：低于您的最低现金储备 15 天。"
    assert item["why_first_text"].startswith("优先处理的原因")
    assert "您" in item["status_text"]


def test_the_chinese_read_after_the_plan_and_for_a_missed_receipt(api: TestClient) -> None:
    _offer(api)
    _run_plan(api)
    zh = _get(api, "zh")
    assert zh["alert"] is None
    assert not english_leaks(zh, NAMES, raw_fields=[HREFS])
    assert zh["waiting"][0]["status_text"].startswith("融资已安排") and zh["waiting"][0]["consequence_text"] == "到账前不计入现金。"
    assert zh["waiting"][0]["subject_text"] == "发票融资 · ¥255k"


def test_the_chinese_collection_and_promise_rows(api: TestClient) -> None:
    _walk(api, receipt="half")
    zh = _get(api, "zh")
    assert not english_leaks(zh, NAMES, raw_fields=[HREFS])
    item = zh["needs_you"][0]
    assert (item["subject_text"], item["status_text"], item["consequence_text"]) == (
        "Foshan · 逾期 ¥291k", "款项已逾期 · 需要您跟进", "已逾期 2 天。")
    _walk(api, to=2)
    zh = _get(api, "zh")
    assert not english_leaks(zh, NAMES, raw_fields=[HREFS])
    assert zh["waiting"][0]["status_text"] == "预计今天到账 · ¥255k"
