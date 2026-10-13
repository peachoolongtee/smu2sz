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


def test_the_routes_are_always_on_and_health_still_lists_the_constant() -> None:
    assert not hasattr(get_settings().features, "home_v2")
    from app.main import app

    assert TestClient(app).get("/health").json()["features"]["home_v2"] is True  # constant for one release


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
    assert w["alert"] == {"key": "company-cash", "eyebrow": "Company cash", "kind_text": "FLOW action ready",
                          "text": "Reserve unsafe in 12 days. A funding plan is ready.",
                          "pending_text": "¥405k funding plan available · no approval needed · waits for your go", "tone": "bad", "primary": {"label": "Run or compare", "href": "/"}}
    assert [i["key"] for i in w["needs_you"]] == [f"deal:{oid}"]
    item = w["needs_you"][0]
    assert (item["kind"], item["owner"], item["severity"], item["customer_short"]) == ("DECISION", "NEEDS_YOU", "CAUTION", "Foshan")
    assert (item["subject_text"], item["status_text"]) == ("Foshan · Payment terms", "Counter ready · Reply needed")
    assert item["consequence_text"] == "As asked: below your minimum for 15 days."
    # a safe counter is ready, so the breach is a consequence of the offer as asked and not a cash-safety item: no deadline, a caution
    assert item["deadline_day"] is None and item["is_new"] is False
    assert item["why_first_text"] == "Why first: it has the largest effect on your cash."
    assert item["href"] == "/?customer=BUYER-1&deal=deal%3A" + oid
    assert not any("reserve" in i["subject_text"].lower() for i in w["needs_you"])  # the alert is not a row
    assert w["waiting"] == []


def test_the_empty_needs_you_word_follows_the_alert_on_day_zero_and_after_the_plan(api: TestClient) -> None:
    _offer(api)
    assert _get(api)["alert"] is not None
    assert _get(api)["needs_you_empty_text"] == "Nothing else needs you."
    assert _get(api, "zh")["needs_you_empty_text"] == "没有其他事项需要您处理。"
    _run_plan(api)
    assert _get(api)["alert"] is None
    assert _get(api)["needs_you_empty_text"] == "Nothing needs a decision from you."
    zh = _get(api, "zh")["needs_you_empty_text"]
    assert zh == "没有需要您决定的事项。" and english_leaks(zh) == []


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
        # the queue's counts: a promise is an Agreements row there, so Waiting counts the rest of the `waiting` rows
        assert w["counts"] == {"needs_you": len(w["needs_you"]), "waiting": len([r for r in w["waiting"] if r["kind"] != "PROMISE"]),
                               "agreements": len([r for r in w["waiting"] if r["kind"] == "PROMISE"]), "customers": len(w["customers"])}
        assert w["counts"]["customers"] == 2
        assert all(k not in {i["key"] for i in w["needs_you"] + w["waiting"]} for k in ("company-cash",))


def test_the_first_row_alone_says_why_it_is_first(api: TestClient) -> None:
    _offer(api, "EX01_PACKAGE")
    _offer(api, "EX02_EARLY_1_5")
    rows = _get(api)["needs_you"]
    assert len(rows) == 2 and [r["kind"] for r in rows] == ["DECISION", "DECISION"]
    assert rows[0]["why_first_text"] and rows[1]["why_first_text"] is None
    assert [r["severity"] for r in rows] == ["CAUTION", "NORMAL"]  # the heavier first


def test_one_row_per_decision_and_the_customer_counts_them(api: TestClient) -> None:
    _offer(api, "EX01_PACKAGE")
    _offer(api, "EX02_EARLY_1_5")
    w = _get(api)
    assert len({r["key"] for r in w["needs_you"]}) == 2
    foshan = next(c for c in w["customers"] if c["customer_id"] == "BUYER-1")
    assert (foshan["negotiations_count"], foshan["needs_you_count"]) == (2, 2)
    assert foshan["status_text"] == "2 open negotiations · 2 need you" and foshan["tone"] == "warn"


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
    approval = api.get("/home").json()["next_action"]["pending_approval_id"]
    assert w["alert"]["primary"] == {"label": "Review the plan", "href": f"/approvals#approval-{approval}"}
    # both legs of the plan (APR-000001 and APR-000002) are the alert's: neither is a row
    assert approval == "APR-000001" and {a["id"] for a in api.get("/home").json()["approvals"]} == {"APR-000001", "APR-000002"}
    assert [i["kind"] for i in w["needs_you"]] == ["DECISION"]
    assert _get(api, "zh")["alert"]["text"] == "现金储备将在 12 天后变得不安全。融资方案正等待您批准。"
    assert w["alert"]["pending_text"] == "¥405k funding plan available · needs your approval · waits for your go"
    assert _get(api, "zh")["alert"]["pending_text"] == "¥405k 融资方案可用 · 需要您批准 · 等待您确认"


def test_an_unsafe_reserve_with_nothing_to_run_has_an_alert_that_points_at_the_options(api: TestClient) -> None:
    from app.api.runtime import get_runtime
    from tests.api.test_home import _exhaust_line

    _exhaust_line(get_runtime())
    w = _get(api)
    assert w["alert"]["text"] == "Reserve unsafe in 12 days. A funding plan is ready."  # the application for a facility is the plan
    assert w["alert"]["kind_text"] == "FLOW action ready" and w["alert"]["pending_text"] is None  # it brings no cash to name
    assert w["needs_you"] == [] and w["counts"]["needs_you"] == 0


def test_the_alert_for_an_unsafe_reserve_with_no_plan_points_at_the_options() -> None:
    home: dict[str, Any] = {"cash": {"first_breach_day": 12, "first_breach_when": "in 12 days"}, "next_action": None, "status": "CRITICAL"}
    en = worklist._alert(home, "en")
    zh = worklist._alert({**home, "cash": {"first_breach_day": 12, "first_breach_when": "12 天后"}}, "zh")
    assert en is not None and zh is not None
    assert en["kind_text"] is None and en["pending_text"] is None and zh["kind_text"] is None and zh["pending_text"] is None  # no plan, no action ready
    assert en["text"] == "Reserve unsafe in 12 days. No funding plan is ready yet." and en["primary"] == {"label": "See the options", "href": "/cash#cash-options"}
    assert zh["text"] == "现金储备将在 12 天后变得不安全。目前还没有准备好的融资方案。" and zh["primary"]["label"] == "查看选项"
    assert worklist._alert({"cash": {"first_breach_day": None}, "next_action": None}, "en") is None


def test_an_arrival_after_the_day_last_read_is_new(api: TestClient, rt: Runtime) -> None:
    oid = _offer(api)
    assert _get(api)["needs_you"][0]["is_new"] is False  # without a day last read nothing is new
    assert _get(api, since_day=0)["needs_you"][0]["is_new"] is False  # received on day 0, not after it
    stored = rt.store.get_offer(oid)
    assert stored is not None
    rt.store.put_offer(stored.model_copy(update={"received_day": 5}))
    worklist.clear_cache()  # the store's change marker does not count a re-dated offer
    assert _get(api, since_day=4)["needs_you"][0]["is_new"] is True
    assert _get(api, since_day=5)["needs_you"][0]["is_new"] is False


def test_a_missed_receipt_is_new_the_day_after_it_fell_due(api: TestClient) -> None:
    _walk(api, receipt="half")  # the invoice fell due on day 32; it is overdue from day 33
    assert _get(api, since_day=32)["needs_you"][0]["is_new"] is True
    assert _get(api, since_day=33)["needs_you"][0]["is_new"] is False


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
    _row("a-breach-day-20", breach=20, deadline=20, severity="CRITICAL"),
    _row("b-approval-expires-5", kind="APPROVAL", deadline=5),
    _row("c-collection", kind="COLLECTION", severity="CRITICAL", deadline=3),
    _row("d-material-critical", severity="CRITICAL"),
    _row("e-material-caution", severity="CAUTION"),
    _row("f-ordinary"),
]


def test_six_items_are_ordered_by_the_rule() -> None:
    """Cash safety (by breach day), then a deadline, then a missed receipt, then material consequences (CRITICAL before CAUTION), then an
    ordinary reply."""
    assert [r.key for r in worklist.order(SIX)] == [
        "a-breach-day-20", "b-approval-expires-5", "c-collection", "d-material-critical", "e-material-caution", "f-ordinary"]
    assert [worklist.tier_of(r.kind, r.severity, r.breach_day, r.deadline_day) for r in worklist.order(SIX)] == [0, 1, 2, 3, 3, 4]


def test_a_caution_with_a_safe_counter_ready_never_outranks_a_critical_missed_receipt() -> None:
    caution = _row("deal", severity="CAUTION")  # the offer as asked would breach, but the counter FLOW recommends does not: no breach day
    missed = _row("collection:BUYER-1", kind="COLLECTION", severity="CRITICAL", deadline=32)
    assert [r.key for r in worklist.order([caution, missed])] == ["collection:BUYER-1", "deal"]
    unsafe = _row("deal-unsafe", severity="CRITICAL", breach=40, deadline=40)  # even the recommended counter breaches on day 40
    assert [r.key for r in worklist.order([caution, missed, unsafe])] == ["deal-unsafe", "collection:BUYER-1", "deal"]


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


def _picture(*, asked_breach: int | None, rec_series: list[tuple[int, int]] | None, rec_breach_when: str | None, authority: str = "over_limit",
             band: str | None = "Below your minimum for 15 days") -> dict[str, Any]:
    rec = {"key": "CTR-1", "kind": "reply", "recommended": True, "sendable": True, "first_breach_when": rec_breach_when,
           "series": [{"day": d, "closing_fen": c} for d, c in rec_series or []]}
    asked = {"key": "asked", "kind": "asked", "recommended": False, "authority": authority, "band_text": band}
    return {"available": True, "day": 0, "asked": {"first_breach_day": asked_breach}, "paths": [asked, rec]}


def test_the_decisions_breach_day_is_the_recommended_paths_not_the_one_as_asked() -> None:
    floor = 30_000_000
    safe = _picture(asked_breach=47, rec_series=[(0, 40_000_000), (30, 30_000_000)], rec_breach_when=None)
    assert worklist._deal_effect(safe, floor, False, "en") == ("CAUTION", None, "As asked: below your minimum for 15 days.")
    unsafe = _picture(asked_breach=47, rec_series=[(0, 40_000_000), (9, 29_999_999), (30, 10_000_000)], rec_breach_when="in 9 days")
    assert worklist._deal_effect(unsafe, floor, False, "en")[:2] == ("CRITICAL", 9)
    quiet = _picture(asked_breach=None, rec_series=[(0, 40_000_000)], rec_breach_when=None, authority="flow_may", band=None)
    assert worklist._deal_effect(quiet, floor, False, "en") == ("NORMAL", None, "Accepting as asked does not take cash below your minimum.")
    lone = {"available": True, "day": 0, "asked": {"first_breach_day": 12}, "paths": [{"key": "asked", "recommended": False,
                                                                                      "band_text": "Below your minimum for 3 days"}]}
    assert worklist._deal_effect(lone, floor, False, "en")[:2] == ("CRITICAL", 12)  # no counter at all: the offer as asked is the only path


def test_a_picture_that_cannot_be_read_is_never_worded_as_a_fact() -> None:
    sev, day, said = worklist._deal_effect(None, 0, True, "en")
    assert (sev, day, said) == ("NORMAL", None, "The effect on your cash could not be read just now.")
    assert worklist._deal_effect(None, 0, True, "zh")[2] == "暂时无法读取它对现金的影响。"
    assert "not read the offer yet" in worklist._deal_effect(None, 0, False, "en")[2]


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
    assert (zh["alert"]["kind_text"], zh["alert"]["pending_text"]) == ("FLOW 已备好行动", "¥405k 融资方案可用 · 无需批准 · 等待您确认")
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


def test_a_promise_in_chinese_keeps_the_house_space_before_a_number() -> None:
    from types import SimpleNamespace

    state = SimpleNamespace(counterparties=[SimpleNamespace(id="BUYER-1", name="Foshan Home Retail Co.")])
    promise = SimpleNamespace(status="AWAITED", counterparty_id="BUYER-1", promised_day=5, expected_fen=25_500_000, commitment_id="CMT-1",
                              obligation_id="O1")
    ctx = SimpleNamespace(promised=[promise], state=state, today=2)
    [row] = worklist._promise_rows(ctx, "zh")  # type: ignore[arg-type]
    assert row["status_text"] == "预计 3 天后到账 · ¥255k"
    [en] = worklist._promise_rows(ctx, "en")  # type: ignore[arg-type]
    assert en["status_text"] == "Expected in 3 days · ¥255k"


# ---------------------------------------------------------------- the other rows, end to end


def test_an_agreement_waiting_for_approval_is_an_approval_row_with_its_deadline(api: TestClient) -> None:
    from tests.api.test_time_semantics import _queue_counter

    queued = _queue_counter(api, 1)
    w = _get(api)
    [item] = [i for i in w["needs_you"] if i["kind"] == "APPROVAL"]
    assert item["key"] == f"approval:{queued['row']['id']}" and item["customer_id"] == "BUYER-1"
    assert (item["subject_text"], item["status_text"]) == ("Foshan · Agreement", "Approval requested · Your approval needed")
    assert item["deadline_day"] == queued["commitment"].expires_day == 14
    assert item["href"] == f"/approvals#approval-{queued['row']['id']}"
    assert not any(i["kind"] == "DECISION" for i in w["needs_you"])  # the offer is the approval's now, not a second row
    assert w["needs_you"][0]["kind"] == "APPROVAL" and w["needs_you"][0]["why_first_text"] == "Why first: it has the nearest deadline."
    foshan = next(c for c in w["customers"] if c["customer_id"] == "BUYER-1")
    assert foshan["needs_you_count"] == 1
    zh = _get(api, "zh")["needs_you"][0]
    assert (zh["subject_text"], zh["status_text"]) == ("Foshan · 协议", "已提交批准申请 · 需要您批准")
    assert not english_leaks(_get(api, "zh"), NAMES, raw_fields=[HREFS])


def test_every_leg_of_the_company_plan_is_the_alerts_and_an_unrelated_approval_stays_a_row(api: TestClient) -> None:
    from app.api.runtime import get_runtime
    from app.mandate.fixture import load_demo_owner_key
    from app.mandate.signing import sign
    from tests.api.test_time_semantics import _queue_counter

    queued = _queue_counter(api, 1)  # an unrelated approval first: an agreement with a buyer
    store = get_runtime().store
    store.put_mandate(sign(store.get_mandate().model_copy(update={"max_apr_bp": 500}), load_demo_owner_key()["private_key_hex"]))
    a = api.get("/home").json()["next_action"]
    api.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]})
    pending = {x["id"] for x in api.get("/home").json()["approvals"]}
    plan = {"APR-000002", "APR-000003"}  # the two legs of the plan (the draw and the invoice financing), queued after the agreement
    assert plan < pending and queued["row"]["id"] == "APR-000001"
    w = _get(api)
    assert w["alert"] is not None
    assert {i["key"] for i in w["needs_you"] if i["kind"] == "APPROVAL"} == {"approval:APR-000001"}
    assert w["counts"]["needs_you"] == len(w["needs_you"])


def test_a_contract_read_and_waiting_for_review_is_a_setup_row(api: TestClient) -> None:
    r = api.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"})
    assert r.status_code == 200, r.text
    w = _get(api)
    [item] = [i for i in w["needs_you"] if i["kind"] == "SETUP"]
    assert (item["subject_text"], item["status_text"], item["consequence_text"], item["severity"]) == (
        "Foshan · Contract", "Terms read · Your review needed", "No cash effect until agreed.", "NORMAL")
    assert item["customer_id"] == "BUYER-1" and item["href"] == "/deals?buyer=BUYER-1" and item["deadline_day"] is None
    assert (_get(api, "zh")["needs_you"][0]["subject_text"], _get(api, "zh")["needs_you"][0]["status_text"]) == ("Foshan · 合同", "条款已读取 · 需要您审核")
    doc = r.json()["document"]
    assert api.post(f"/documents/{doc['id']}/confirm", json={"doc_hash": doc["doc_hash"]}).status_code == 200  # the owner confirms: it is no longer waiting
    assert not [i for i in _get(api)["needs_you"] if i["kind"] == "SETUP"]


def test_an_offer_the_buyer_must_clarify_is_a_buyer_reply_that_waits(api: TestClient) -> None:
    _offer(api, "EX07_CONFLICT")
    w = _get(api)
    assert w["needs_you"] == []
    [wait] = w["waiting"]
    assert (wait["kind"], wait["owner"], wait["severity"], wait["customer_id"]) == ("BUYER_REPLY", "WAITING", "NORMAL", "BUYER-1")
    assert wait["status_text"].startswith("Waiting for the buyer's clarification") and wait["consequence_text"] == "Nothing to resend."
    zh = _get(api, "zh")["waiting"][0]
    assert zh["status_text"].startswith("等待买方澄清") and zh["consequence_text"] == "无需重新发送。"
    assert next(c for c in w["customers"] if c["customer_id"] == "BUYER-1")["status_text"] == "1 open negotiation · 1 waiting"


# ---------------------------------------------------------------- no hidden degradation


def test_an_offer_picture_that_fails_is_named_in_partial_and_the_row_says_so_and_the_read_is_not_cached(
        api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _offer(api)

    def boom(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("no picture")

    real = worklist.cached_picture
    monkeypatch.setattr(worklist, "cached_picture", boom)
    w = _get(api)
    assert w["partial"]["missing"] == ["offer_picture"]
    assert w["partial"]["text"] == "Some supporting facts could not be read: the cash picture of an open offer."
    [item] = w["needs_you"]
    assert item["consequence_text"] == "The effect on your cash could not be read just now." and item["severity"] == "NORMAL"
    assert len(worklist._CACHE) == 0  # never cached while partial
    monkeypatch.setattr(worklist, "cached_picture", real)
    whole = _get(api)
    assert whole["partial"] is None and whole["needs_you"][0]["consequence_text"] == "As asked: below your minimum for 15 days."
    assert len(worklist._CACHE) == 1
    assert _get(api, "zh", ).get("partial") is None


def test_a_customers_share_that_cannot_be_read_is_named_and_never_a_dash(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.financial import EngineError

    def boom(*_: Any, **__: Any) -> Any:
        raise EngineError("no")

    monkeypatch.setattr(worklist, "concentration", boom)
    w = _get(api)
    assert w["partial"]["missing"] == ["customer_shares"]
    assert all(c["outstanding_display"] is None and c["share_text"] is None for c in w["customers"])
    assert all(c["detail_text"] == "Outstanding not available" for c in w["customers"])
    assert len(worklist._CACHE) == 0


def test_the_homes_partial_is_merged_not_replaced(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import home

    real = home.read_home

    def fallen(*args: Any, **kwargs: Any) -> dict[str, Any]:
        out = real(*args, **kwargs)
        return {**out, "partial": {"missing": ["reconciliation"], "missing_text": [], "text": ""}}

    monkeypatch.setattr(worklist, "read_home", fallen)
    _offer(api)
    monkeypatch.setattr(worklist, "cached_picture", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    w = _get(api)
    assert w["partial"]["missing"] == ["reconciliation", "offer_picture"]
    assert len(worklist._CACHE) == 0


def test_a_home_v2_fault_does_not_make_the_worklist_partial(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import home_v2

    def boom(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("no")

    _offer(api)
    monkeypatch.setattr(home_v2, "build", boom)
    assert api.get("/home").json()["partial"]["missing"] == ["home_v2"]
    w = _get(api)
    assert w["partial"] is None and w["alert"] is not None


# ---------------------------------------------------------------- the cache


def test_the_read_is_built_once_per_state_and_the_key_moves_on_a_new_offer_and_a_new_approval(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.api.test_time_semantics import _queue_counter

    built: list[int] = []
    real = worklist._build

    def counting(*args: Any, **kwargs: Any) -> Any:
        built.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(worklist, "_build", counting)
    _offer(api)
    first = _get(api)
    assert _get(api) == first and _get(api, "zh")["lang"] == "zh" and len(built) == 2  # the second English read was a hit; the zh read was not
    _offer(api, "EX02_EARLY_1_5")  # a new offer: the key moves
    assert len(_get(api)["needs_you"]) == 2 and len(built) == 3
    _get(api)
    assert len(built) == 3
    queued = _queue_counter(api, 1)  # a new approval (and a reset): the key moves
    after = _get(api)
    assert any(i["key"] == f"approval:{queued['row']['id']}" for i in after["needs_you"]) and len(built) == 4
    api.post(f"/approvals/{queued['row']['id']}", json={"decision": "APPROVE"})  # a decided approval: it moves again
    assert not any(i["kind"] == "APPROVAL" for i in _get(api)["needs_you"]) and len(built) == 5


def _queue_draw(api: TestClient) -> str:
    """A standalone credit-line draw that needs the owner (the mandate's cost ceiling is tightened first): an approval of no alert."""
    from app.api.runtime import get_runtime
    from app.mandate.fixture import load_demo_owner_key
    from app.mandate.signing import sign

    store = get_runtime().store
    store.put_mandate(sign(store.get_mandate().model_copy(update={"max_apr_bp": 500}), load_demo_owner_key()["private_key_hex"]))
    r = api.post("/operations", headers={"X-Owner-Token": "", "X-Agent-Key": "demo-agent-key"}, json={
        "kind": "DRAW_FACILITY", "op_id": "draw-1", "idempotency_key": "draw-1", "mandate_version": store.get_mandate().version,
        "requested_by": "AGENT", "facility_id": "FAC-LINE", "amount_fen": 15_000_000})
    assert r.status_code == 200 and r.json()["result"]["status"] == "PENDING_APPROVAL", r.text
    return str(r.json()["result"]["approval_id"])


def test_a_facility_approval_row_is_a_chinese_sentence_around_the_facilitys_name(api: TestClient) -> None:
    _queue_draw(api)
    [item] = [i for i in _get(api)["needs_you"] if i["kind"] == "APPROVAL"]
    assert item["subject_text"] == "Draw ¥150,000.00 on Bank credit line" and item["customer_id"] is None
    zh = _get(api, "zh")
    [item] = [i for i in zh["needs_you"] if i["kind"] == "APPROVAL"]
    # the books name the facility in English only: the sentence around it is Chinese, the name stays and is set off as a name
    assert item["subject_text"] == "从“Bank credit line”提款 ¥150,000.00"
    assert item["status_text"] == "已提交批准申请 · 需要您批准"
    assert not english_leaks(zh, [*NAMES, "Bank credit line"], raw_fields=[HREFS])


# ---------------------------------------------------------------- the differentiator (words batch 3)


def _ask_row(key: str, cid: str | None, subject: str, ask: str | None) -> worklist.Row:
    return worklist.Row(key=key, kind="DECISION", customer_id=cid, customer_short="Foshan", subject=subject, status="", consequence="",
                        severity=worklist.NORMAL, deadline_day=None, breach_day=None, href="/", ask=ask)


def test_two_rows_of_one_customer_and_subject_say_what_separates_them(api: TestClient) -> None:
    _offer(api, "EX01_PACKAGE")
    _offer(api, "EX02_EARLY_1_5")
    _offer(api, "EX03_AS_USUAL")
    rows = _get(api)["needs_you"]
    said = {r["subject_text"]: [] for r in rows}
    for r in rows:
        said[r["subject_text"]].append(r["differentiator_text"])
    assert said["Foshan · Payment terms"] == [None]  # alone in its subject: nothing to separate
    assert sorted(said["Foshan · Early-payment discount"]) == ["“Early pay at 1.5%”", "“pay this one early at 1.5%”"]


def test_the_differentiator_is_the_buyers_own_words_in_both_languages(api: TestClient) -> None:
    _offer(api, "EX02_EARLY_1_5")
    _offer(api, "EX03_AS_USUAL")
    en, zh = _get(api), _get(api, "zh")
    assert figures(en) == figures(zh)
    assert [r["differentiator_text"] for r in en["needs_you"]] == [r["differentiator_text"] for r in zh["needs_you"]]
    assert all(r["differentiator_text"] for r in zh["needs_you"])
    # the quoted phrase is the buyer's message, not FLOW's word: it is the one string of the zh read left in the buyer's language
    assert not english_leaks(zh, NAMES, raw_fields=[HREFS, r".*differentiator_text"])


def test_a_lone_row_or_one_with_no_phrase_or_a_phrase_said_twice_has_no_differentiator() -> None:
    lone = worklist._differentiate([_ask_row("a", "B1", "Foshan · Offer", "x"), _ask_row("b", "B2", "Foshan · Offer", "y")])
    assert [r.differentiator for r in lone] == [None, None]  # two customers: no clash
    rows = worklist._differentiate([_ask_row("a", "B1", "S", "same"), _ask_row("b", "B1", "S", "same"), _ask_row("c", "B1", "S", None),
                                    _ask_row("d", "B1", "S", "own")])
    assert [r.differentiator for r in rows] == [None, None, None, "“own”"]
    assert [r.differentiator for r in worklist._differentiate([_ask_row("a", None, "S", "p"), _ask_row("b", None, "S", "q")])] == [None, None]
