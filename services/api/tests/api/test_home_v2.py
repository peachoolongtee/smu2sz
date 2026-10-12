"""GET /home, Home V2's fields (wave 1, the server half): `home_v2` behind FEATURE_HOME_V2 (the three KPIs, the one company-side action,
the chart's scope and inspector, the links), before and after the plan runs, in both languages.

Golden day 0: cash ¥400,000 against a ¥300,000 minimum; payroll in 12 days takes the books to ¥60,000 and then −¥105,000 in 30 days; FLOW's
plan (a ¥150k credit-line draw and ¥255k of invoice financing for ¥3,113.93) is ready, or has run. The lowest-ahead KPI is the CURRENT BOOKS'
lowest and the plan's effect is a hint; nothing hypothetical (a pending deal, a late payment) ever moves a KPI."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import home_v2, offer_picture, worklist
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import english_leaks, figures
from tests.api.test_home import _exhaust_line

OWNER = {"X-Owner-Token": "demo-owner-token"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan"]
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


def _offer(api: TestClient) -> None:
    offer = api.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    api.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})


def _run_plan(api: TestClient) -> None:
    a = api.get("/home").json()["next_action"]
    r = api.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()
    assert r["executed"] == 2


def _home(api: TestClient, lang: str = "en") -> dict[str, Any]:
    h: dict[str, Any] = api.get("/home", params={"lang": lang}).json()
    assert h["partial"] is None
    return h


def _v2(api: TestClient, lang: str = "en") -> dict[str, Any]:
    v2: dict[str, Any] = _home(api, lang)["home_v2"]
    return v2


# ---------------------------------------------------------------- the gate


def test_with_the_flag_off_the_home_read_carries_no_v2_field_and_is_otherwise_the_same(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _offer(api)
    on = _home(api)
    monkeypatch.delenv("FEATURE_HOME_V2", raising=False)
    off = _home(api)
    assert "home_v2" in on and "home_v2" not in off
    assert {k: v for k, v in on.items() if k != "home_v2"} == off


def test_the_flag_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_HOME_V2", raising=False)
    assert get_settings().features.home_v2 is False


# ---------------------------------------------------------------- golden: before the plan runs


def test_before_the_plan_the_three_kpis(api: TestClient) -> None:
    _offer(api)
    k = _v2(api)["kpis"]
    assert k["cash_available"] == {"eyebrow": "CASH AVAILABLE", "value_display": "¥400,000", "note": "¥100k above your ¥300k minimum",
                                   "tone": "ok", "buffer": {"min_fen": 30_000_000, "cash_fen": 40_000_000, "min_display": "¥300k",
                                                            "cash_display": "¥400,000.00", "headroom_text": "+¥100k"}}
    assert k["lowest_ahead"] == {"eyebrow": "LOWEST CASH AHEAD", "value_display": "−¥105,000", "tone": "bad",
                                 "note": "¥405k below your minimum in 30 days · current books, no new funding",
                                 "with_plan_hint": "If FLOW's plan executes: ¥300,000, assuming the funds arrive as planned.",
                                 "with_plan": {"label": "with plan", "value_text": "¥300,000"}}
    assert k["funding"] == {"state": "PROPOSED", "eyebrow": "PLANNED FUNDING", "value_display": "¥405,000",
                            "note": "¥150k credit line today + ¥255k invoice financing in 3 days",
                            "hint": "Conditional on you running the plan; not counted as cash."}


def test_before_the_plan_the_action_the_chart_and_the_links(api: TestClient) -> None:
    _offer(api)
    v2 = _v2(api)
    assert v2["action"] == {
        "variant": "ACTION", "key": "funding:ALERT-RESERVE-12", "tone": "bad", "eyebrow": "NEXT ACTION · WITHIN 12 DAYS",
        "title": "Secure ¥405,000 before payroll in 12 days.",
        "text": "FLOW's plan within your signed limits: ¥150k credit-line draw today, ¥255k invoice financing in 3 days, both planned · "
                "cost ¥3,113.93 · no approval needed.",
        "facts": [{"label": "Estimated cost", "value": "¥3,113.93"},
                  {"label": "Funding", "value": "¥150k credit-line draw today, ¥255k invoice financing in 3 days, both planned"},
                  {"label": "Approval", "value": "No approval needed"}],
        "primary": {"label": "Run the funding plan", "href": "/cash#cash-options"},
        "secondary": {"label": "Compare", "href": "/cash#cash-options"}, "control": "RUN_PLAN"}
    chart = v2["chart"]
    assert chart["scope_title"] == "COMPANY CASH FORECAST"
    assert chart["legend"] == [{"label": "Current books · no new funding", "kind": "current"},
                               {"label": "If FLOW's plan runs (planned)", "kind": "planned"}]
    assert chart["lowest_inspector"] == {
        "day_text": "The lowest point · in 30 days", "projected_display": "−¥105,000", "minimum_display": "¥300,000",
        "third_label": "Shortfall", "third_display": "¥405,000",
        "note": "With FLOW's plan (planned): ¥300,000, assuming it runs and the funds arrive as planned."}
    assert chart["note"] == "Current books, nothing new assumed. The same figures as Cash & Funding."
    assert [link["label"] for link in v2["links"]] == ["Where the cash goes", "Facility headroom", "What you are owed, by when", "All deals"]
    assert [link["href"] for link in v2["links"]][2:] == ["/receivables", "/deals"]


# ---------------------------------------------------------------- golden: after the plan ran


def test_after_the_plan_the_three_kpis(api: TestClient) -> None:
    _offer(api)
    _run_plan(api)
    k = _v2(api)["kpis"]
    assert (k["cash_available"]["value_display"], k["cash_available"]["note"]) == ("¥550,000", "¥250k above your ¥300k minimum")
    assert k["lowest_ahead"] == {"eyebrow": "LOWEST CASH AHEAD", "value_display": "¥300,000", "tone": "warn",
                                 "note": "reaches your minimum in 30 days · current books, the plan ran",
                                 "with_plan_hint": "No hypothetical applied.", "with_plan": None}
    assert k["funding"] == {"state": "ARRANGED", "eyebrow": "FUNDING ARRANGED", "value_display": "¥255,000 pending",
                            "note": "¥150k credit-line draw received today · ¥255k invoice financing expected in 3 days",
                            "hint": "Counted as cash only when it lands."}


def test_after_the_plan_the_action_is_quiet_and_the_chart_has_the_one_line(api: TestClient) -> None:
    _offer(api)
    _run_plan(api)
    v2 = _v2(api)
    assert v2["action"] == {
        "variant": "QUIET", "key": None, "tone": "ok", "eyebrow": "NOTHING NEEDS YOU FROM THE COMPANY SIDE",
        "title": "Your cash is covered on the plan that ran.",
        "text": "Next: ¥255k arrives in 3 days; Foshan pays ¥420k in 32 days (owed). Your worklist still holds 1 item for you.",
        "facts": [], "primary": None, "secondary": None, "control": None}
    assert v2["chart"]["legend"] == [{"label": "Current books · the plan ran", "kind": "current"}]
    assert v2["chart"]["lowest_inspector"] == {
        "day_text": "The lowest point · in 30 days", "projected_display": "¥300,000", "minimum_display": "¥300,000",
        "third_label": "Above your minimum", "third_display": "¥0", "note": "At your minimum; nothing below it in the window."}


def test_a_healthy_company_has_no_filled_primary_and_no_pointer_when_the_worklist_is_empty(api: TestClient) -> None:
    _run_plan(api)  # no offer: nothing commercial waits
    action = _v2(api)["action"]
    assert action["variant"] == "QUIET" and action["primary"] is None and action["secondary"] is None and action["control"] is None
    assert action["text"] == "Next: ¥255k arrives in 3 days; Foshan pays ¥420k in 32 days (owed)."


# ---------------------------------------------------------------- the KPIs are the books', never a hypothetical


def test_the_kpis_are_the_books_own_figures(api: TestClient) -> None:
    _offer(api)
    for moment in ("before", "after"):
        if moment == "after":
            _run_plan(api)
        h = _home(api)
        k = h["home_v2"]["kpis"]
        assert k["cash_available"]["buffer"]["cash_fen"] == h["cash"]["cash_fen"] and k["cash_available"]["buffer"]["min_fen"] == h["cash"]["floor_fen"]
        # the lowest KPI is the books' lowest (the existing field), never the plan line's that the facts carry before the run
        assert h["home_v2"]["chart"]["lowest_inspector"]["projected_display"] == k["lowest_ahead"]["value_display"]
        assert h["cash"]["lowest_fen"] == (-10_500_000 if moment == "before" else 30_000_000)
        assert k["lowest_ahead"]["tone"] == ("bad" if moment == "before" else "warn")


def test_a_pending_deal_never_moves_a_kpi(api: TestClient) -> None:
    bare = _v2(api)["kpis"]
    _offer(api)  # the Foshan offer, and the counter FLOW would send: both hypothetical until the buyer accepts
    assert _v2(api)["kpis"] == bare


def test_the_planned_word_is_the_financing_vocabularys_own(api: TestClient) -> None:
    from app.api.financing_words import state_of, state_word

    for lang in ("en", "zh"):
        word = state_word(lang, state_of(None, planned=True))
        v2 = _v2(api, lang)
        assert word in v2["kpis"]["funding"]["eyebrow"].lower() and word in v2["chart"]["legend"][1]["label"] and word in v2["action"]["text"]
        assert word in v2["chart"]["lowest_inspector"]["note"] and "propos" not in str(v2).lower().replace("'proposed'", "")
    assert (state_word("en", "PLANNED"), state_word("zh", "PLANNED")) == ("planned", "计划中")


def test_the_plans_effect_is_only_ever_a_hint(api: TestClient) -> None:
    k = _v2(api)["kpis"]
    assert "300,000" not in k["lowest_ahead"]["value_display"] and "300,000" in k["lowest_ahead"]["with_plan_hint"]
    assert "plan" not in k["lowest_ahead"]["note"].replace("the plan ran", "")
    assert k["funding"]["state"] == "PROPOSED" and "not counted as cash" in k["funding"]["hint"]


# ---------------------------------------------------------------- the other states of the action


def test_a_plan_waiting_on_approval_says_so_and_points_at_the_approval(api: TestClient) -> None:
    from app.mandate.fixture import load_demo_owner_key
    from app.mandate.signing import sign

    rt = get_runtime()
    _offer(api)
    rt.store.put_mandate(sign(rt.store.get_mandate().model_copy(update={"max_apr_bp": 500}), load_demo_owner_key()["private_key_hex"]))
    a = api.get("/home").json()["next_action"]
    api.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]})
    h = _home(api)
    v2, approval = h["home_v2"], h["next_action"]["pending_approval_id"]
    assert approval and v2["action"]["control"] == "APPROVE_PLAN"
    assert v2["action"]["key"] == f"approval:{approval}" and v2["action"]["primary"] == {"label": "Review the plan", "href": f"/approvals#approval-{approval}"}
    assert "needs your approval because of its cost" in v2["action"]["text"] and "your approval is needed" in v2["action"]["text"]
    assert v2["kpis"]["funding"]["state"] == "PROPOSED" and v2["kpis"]["funding"]["hint"] == "Conditional on you approving the plan; not counted as cash."
    zh = _home(api, "zh")["home_v2"]
    assert zh["kpis"]["funding"]["hint"] == "取决于您是否批准方案；不计入现金。"
    assert zh["action"]["primary"]["label"] == "查看方案"


def test_a_step_with_no_cash_landing_yet_says_what_it_is_and_who_must_act(api: TestClient) -> None:
    _exhaust_line(get_runtime())  # the line and the platform are full: the only cure is an application for a facility
    v2 = _home(api)["home_v2"]
    assert v2["action"]["variant"] == "ACTION" and v2["action"]["control"] == "RUN_PLAN" and v2["action"]["tone"] == "bad"
    assert v2["action"]["title"] == "Apply for ¥405,000.00 on Equipment lease"
    assert v2["action"]["text"] == "Your cash reserve becomes unsafe in 12 days. Needs your approval."
    assert v2["kpis"]["funding"]["state"] == "NONE" and v2["kpis"]["lowest_ahead"]["tone"] == "bad"
    assert v2["chart"]["lowest_inspector"]["note"] == "FLOW has no funding plan that closes this yet."
    assert v2["chart"]["legend"] == [{"label": "Current books · no new funding", "kind": "current"}]


def test_an_unsafe_reserve_with_no_action_at_all_is_never_the_quiet_variant() -> None:
    c = SimpleNamespace(action=None, breach_day=12, today=0, lang="en", headline="Your cash reserve becomes unsafe in 12 days.",
                        note="Cash falls to ¥60k.", state=None)
    action = home_v2._action(c, {"items": []})  # type: ignore[arg-type]
    assert action["variant"] == "ACTION" and action["control"] is None and action["tone"] == "bad"
    assert (action["title"], action["text"]) == ("Your cash reserve becomes unsafe in 12 days.", "Cash falls to ¥60k.")
    assert action["primary"] == {"label": "See the options", "href": "/cash#cash-options"} and action["eyebrow"] == "NEXT ACTION · WITHIN 12 DAYS"


def test_a_repayable_credit_line_is_the_action_and_never_the_quiet_variant() -> None:
    repay = {"kind": "FACILITY_REPAYABLE", "pending_approval_id": None, "outcome_title": "Repay ¥150k of the credit line",
             "after": "The balance is repaid and the interest stops.", "authority_text": "Within your signed limits. No additional approval required."}
    c = SimpleNamespace(action=repay, breach_day=None, today=0, lang="en", headline="You're covered.", note="", state=None)
    action = home_v2._action(c, {"items": []})  # type: ignore[arg-type]
    assert action["variant"] == "ACTION" and action["control"] == "RUN_PLAN" and action["tone"] == "warn" and action["key"] is None
    assert action["title"] == "Repay ¥150k of the credit line"
    assert action["text"] == "The balance is repaid and the interest stops. Within your signed limits. No additional approval required."
    assert action["primary"] == {"label": "Run the repayment", "href": "/cash#cash-options"}
    waiting = home_v2._action(SimpleNamespace(**{**c.__dict__, "action": {**repay, "pending_approval_id": "APR-000007"}}), {"items": []})  # type: ignore[arg-type]
    assert waiting["control"] == "APPROVE_PLAN" and waiting["key"] == "approval:APR-000007"
    assert waiting["primary"] == {"label": "Review the repayment", "href": "/approvals#approval-APR-000007"}
    zh = home_v2._action(SimpleNamespace(**{**c.__dict__, "lang": "zh", "action": {**repay, "outcome_title": "偿还信用额度 ¥150k"}}), {"items": []})  # type: ignore[arg-type]
    assert zh["primary"]["label"] == "执行还款" and zh["eyebrow"] == "下一步"


def test_the_pointer_to_the_worklist_is_the_worklists_own_count(api: TestClient) -> None:
    _offer(api)
    offer = api.post("/offers", json={"fixture_id": "EX02_EARLY_1_5"}).json()["offer"]
    api.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX02_EARLY_1_5"})
    _run_plan(api)
    held = api.get("/worklist").json()["counts"]["needs_you"]
    assert held == 2
    assert _v2(api)["action"]["text"].endswith(f"Your worklist still holds {held} items for you.")
    assert _v2(api, "zh")["action"]["text"].endswith(f"您的待办列表里还有 {held} 项等您处理。")


def test_a_worklist_that_cannot_be_counted_is_named_and_the_pointer_is_left_out(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import worklist

    _offer(api)
    _run_plan(api)

    def boom(*_: Any, **__: Any) -> dict[str, int]:
        raise RuntimeError("no")

    monkeypatch.setattr(worklist, "counts", boom)
    h = api.get("/home").json()
    assert h["partial"]["missing"] == ["home_v2"]
    assert h["home_v2"]["action"]["text"] == "Next: ¥255k arrives in 3 days; Foshan pays ¥420k in 32 days (owed)."


def test_the_home_reads_for_the_worklist_without_building_the_v2_fields(api: TestClient) -> None:
    from app.api.home import read_home

    assert "home_v2" in read_home("en") and "home_v2" not in read_home("en", v2=False)


def test_the_company_alert_and_the_action_agree(api: TestClient) -> None:
    _offer(api)
    assert _home(api)["home_v2"]["action"]["variant"] == "ACTION" and api.get("/worklist").json()["alert"] is not None
    _run_plan(api)
    assert _home(api)["home_v2"]["action"]["variant"] == "QUIET" and api.get("/worklist").json()["alert"] is None


def test_a_failure_in_the_v2_fields_is_named_and_never_takes_the_home_down(api: TestClient, monkeypatch: pytest.MonkeyPatch,
                                                                         caplog: pytest.LogCaptureFixture) -> None:
    _offer(api)

    def boom(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("no")

    monkeypatch.setattr(home_v2, "build", boom)
    h = api.get("/home").json()
    assert h["home_v2"] is None and h["partial"]["missing"] == ["home_v2"]
    assert h["headline"] and h["attention"]["items"] and h["cash"]["facts"]  # the rest of the Home stands
    assert "could not be built" in caplog.text


# ---------------------------------------------------------------- Chinese


def test_the_chinese_fields_before_the_plan(api: TestClient) -> None:
    _offer(api)
    en, zh = _v2(api), _v2(api, "zh")
    assert figures(en) == figures(zh)
    assert not english_leaks(zh, NAMES, raw_fields=[HREFS])
    k = zh["kpis"]
    assert (k["cash_available"]["eyebrow"], k["cash_available"]["note"]) == ("可用现金", "比您 ¥300k 的最低现金高 ¥100k")
    assert k["lowest_ahead"]["note"] == "比您的最低现金低 ¥405k（30 天后） · 当前账目，未新增融资"
    assert k["lowest_ahead"]["with_plan_hint"] == "如果 FLOW 的方案执行：¥300,000，前提是资金按计划到账。"
    assert (k["funding"]["eyebrow"], k["funding"]["hint"]) == ("计划中的融资", "取决于您是否执行方案；不计入现金。")
    assert zh["action"]["eyebrow"] == "下一步 · 12 天内" and zh["action"]["title"] == "请在工资（12 天后）之前筹措 ¥405,000。"
    assert zh["action"]["text"] == ("FLOW 的方案在您签署的授权内：信用额度提款 ¥150k（今天）、发票融资 ¥255k（3 天后），均为计划中 · 成本 ¥3,113.93 · 无需批准。")
    assert zh["chart"]["scope_title"] == "公司现金预测"
    assert [x["label"] for x in zh["chart"]["legend"]] == ["当前账目 · 未新增融资", "如果 FLOW 的方案执行（计划中）"]
    assert (zh["chart"]["lowest_inspector"]["third_label"], zh["chart"]["lowest_inspector"]["day_text"]) == ("缺口", "最低点 · 30 天后")


def test_the_chinese_fields_after_the_plan(api: TestClient) -> None:
    _offer(api)
    _run_plan(api)
    zh = _v2(api, "zh")
    assert not english_leaks(zh, NAMES, raw_fields=[HREFS])
    k = zh["kpis"]
    assert k["lowest_ahead"]["note"] == "30 天后达到您的最低现金 · 当前账目，方案已执行"
    assert (k["funding"]["eyebrow"], k["funding"]["value_display"]) == ("已安排的融资", "待到账 ¥255,000")
    assert k["funding"]["note"] == "¥150k 信用额度提款已到账（今天） · ¥255k 发票融资预计 3 天后到账"
    assert zh["action"]["variant"] == "QUIET" and zh["action"]["title"] == "按已执行的方案，您的现金是安全的。"
    assert zh["action"]["text"] == "接下来：¥255k 将于 3 天后到账；Foshan将于 32 天后支付 ¥420k（应收）。您的待办列表里还有 1 项等您处理。"
    assert zh["chart"]["legend"] == [{"label": "当前账目 · 方案已执行", "kind": "current"}]


# ---------------------------------------------------------------- what makes the lowest point the lowest


def _cause(api: TestClient, lang: str = "en") -> tuple[str | None, str]:
    """(`home_v2.chart.lowest.cause`, the label of the rail's lowest row)."""
    h = _home(api, lang)
    row = next(r for r in h["cash"]["events_rail"] if r["kind"] == "lowest")
    assert h["home_v2"]["chart"]["lowest"].keys() == {"cause"}
    cause: str | None = h["home_v2"]["chart"]["lowest"]["cause"]
    return cause, row["label"]


def test_the_lowest_cause_is_the_rails_lowest_row_named_by_its_cause_on_day_zero_and_after_the_plan(api: TestClient) -> None:
    # the hybrid names the debt service (a loan repayment) as what takes the Demo company to its lowest point, with or without the plan
    assert _cause(api) == ("a loan repayment goes out",) * 2 and _cause(api, "zh") == ("一笔贷款还款支出",) * 2
    _offer(api)
    assert _cause(api) == ("a loan repayment goes out",) * 2
    _run_plan(api)
    assert _cause(api) == ("a loan repayment goes out",) * 2 and _cause(api, "zh") == ("一笔贷款还款支出",) * 2


def test_the_lowest_cause_is_null_when_the_hybrid_names_none() -> None:
    assert home_v2._lowest_cause(None) is None and home_v2._lowest_cause([]) is None
    assert home_v2._lowest_cause([{"kind": "payroll", "label": "payroll is paid", "amount_fen": -1}]) is None
    row = {"kind": "lowest", "label": "cash is at its lowest", "amount_fen": 0}  # the rail's fallback row: no event behind it
    assert home_v2._lowest_cause([row]) is None
    assert home_v2._lowest_cause([{**row, "label": "payroll is paid", "amount_fen": -1}]) == "payroll is paid"


def test_the_headroom_and_the_structured_with_plan_on_day_zero_after_the_plan_and_in_chinese(api: TestClient) -> None:
    k = _v2(api)["kpis"]  # day 0: cash above the minimum; the plan figure is the hint's, structured
    assert k["cash_available"]["buffer"]["headroom_text"] == "+¥100k"
    assert k["lowest_ahead"]["with_plan"] == {"label": "with plan", "value_text": "¥300,000"} and "¥300,000" in k["lowest_ahead"]["with_plan_hint"]
    _offer(api)
    zh = _v2(api, "zh")["kpis"]
    assert zh["cash_available"]["buffer"]["headroom_text"] == "+¥100k"
    assert zh["lowest_ahead"]["with_plan"] == {"label": "采用方案后", "value_text": "¥300,000"}
    _run_plan(api)
    k = _v2(api)["kpis"]
    assert k["cash_available"]["buffer"]["headroom_text"] == "+¥250k" and k["lowest_ahead"]["with_plan"] is None
    assert _v2(api, "zh")["kpis"]["lowest_ahead"]["with_plan"] is None


def test_the_headroom_is_negative_below_the_minimum_and_zero_on_it() -> None:
    def kpi(cash: int) -> dict[str, Any]:
        c = SimpleNamespace(lang="en", state=SimpleNamespace(cash_fen=cash), floor=30_000_000)
        return home_v2._cash_available(c)["buffer"]  # type: ignore[arg-type,no-any-return]

    assert kpi(26_000_000)["headroom_text"] == "−¥40k" and kpi(30_000_000)["headroom_text"] == "¥0" and kpi(40_000_000)["headroom_text"] == "+¥100k"


# ---------------------------------------------------------------- the series points carry their words


def test_every_point_of_the_longest_window_has_when_and_display_and_the_lowest_is_the_kpi(api: TestClient) -> None:
    _offer(api)
    for moment in ("before", "after"):
        if moment == "after":
            _run_plan(api)
        for lang in ("en", "zh"):
            h = _home(api, lang)
            cash = h["cash"]
            lines = [cash["series"], cash["plan_series"], cash.get("counterfactual_series")]
            assert [p["day"] for p in cash["series"]] == list(range(121))  # the longest window: 120 days from today
            for series in (s for s in lines if s):
                assert all(p["when"] and p["display"] for p in series)  # no point past day 32 (or any day) is left without its words
            by_day = {p["day"]: p for p in cash["series"]}
            assert by_day[0]["when"] == ("today" if lang == "en" else "今天") and by_day[120]["when"] == ("in 120 days" if lang == "en" else "120 天后")
            assert by_day[100]["when"] == ("in 100 days" if lang == "en" else "100 天后")
            lowest = min(cash["series"], key=lambda p: p["closing_fen"])
            assert lowest["display"] == h["home_v2"]["kpis"]["lowest_ahead"]["value_display"]
            assert by_day[0]["display"] == h["home_v2"]["kpis"]["cash_available"]["value_display"]  # the KPI's form, no cents on a round sum


# ---------------------------------------------------------------- the action's facts are the sentence's own parts


def _parts(text: str) -> list[str]:
    """The sentence's parts, split at its separators: [what the plan is made of, cost?, approval]."""
    return [part.strip() for part in text.split(" · ")]


def test_the_plans_three_facts_are_the_action_sentences_own_words_on_day_zero(api: TestClient) -> None:
    _offer(api)
    action = _v2(api)["action"]
    assert action["control"] == "RUN_PLAN"
    assert [f["label"] for f in action["facts"]] == ["Estimated cost", "Funding", "Approval"]
    cost, funding, approval = (f["value"] for f in action["facts"])
    head, cost_part, approval_part = _parts(action["text"])
    assert head.endswith(funding) and cost_part == f"cost {cost}" and approval_part == f"{approval.lower()}."
    assert (cost, funding, approval) == ("¥3,113.93", "¥150k credit-line draw today, ¥255k invoice financing in 3 days, both planned",
                                         "No approval needed")


def test_the_plans_facts_in_chinese(api: TestClient) -> None:
    _offer(api)
    action = _v2(api, "zh")["action"]
    assert [f["label"] for f in action["facts"]] == ["预计成本", "融资", "批准"]
    cost, funding, approval = (f["value"] for f in action["facts"])
    head, cost_part, approval_part = _parts(action["text"])
    assert head.endswith(funding) and cost_part == f"成本 {cost}" and approval_part == f"{approval}。"
    assert (cost, approval) == ("¥3,113.93", "无需批准") and "计划中" in funding and english_leaks(action["facts"]) == []


def test_the_facts_are_empty_when_the_action_has_no_plan(api: TestClient) -> None:
    _offer(api)
    _run_plan(api)
    for lang in ("en", "zh"):
        action = _v2(api, lang)["action"]
        assert action["control"] is None and action["facts"] == []


def test_the_approval_fact_says_when_the_owner_must_approve() -> None:
    for lang, needed, not_needed in (("en", "Your approval is needed", "No approval needed"), ("zh", "需要您批准", "无需批准")):
        for needs_owner, expected in ((True, needed), (False, not_needed)):
            c = SimpleNamespace(lang=lang)
            leg = {"operation_kind": "DRAW_FACILITY", "lands_when": "today" if lang == "en" else "今天", "amount_fen": 15_000_000}
            a = {"needs_owner": needs_owner, "legs": [leg], "cost_total_display": None}
            parts = home_v2._plan_parts(c, a)  # type: ignore[arg-type]
            facts = home_v2._plan_facts(lang, parts)
            assert facts[2]["value"] == expected and facts[0]["value"] == ("Not priced" if lang == "en" else "未计价")
            assert " · 成本" not in home_v2._plan_sentence(lang, parts) and " · cost" not in home_v2._plan_sentence(lang, parts)


# ---------------------------------------------------------------- the chart's scenario title (words batch 3)


def _deal(api: TestClient) -> str:
    offer = api.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    api.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    return f"deal:{offer['offer_id']}"


def _title(api: TestClient, lang: str = "en", **query: str) -> str | None:
    h = api.get("/home", params={"lang": lang, **query}).json()
    assert h["partial"] is None
    title: str | None = h["home_v2"]["chart"]["scenario_title_text"]
    return title


def test_the_chart_title_names_the_customer_the_subject_the_paths_and_the_scenario(api: TestClient) -> None:
    decision = _deal(api)
    assert _title(api, decision=decision) == "Foshan · Payment terms · As they asked vs Option A · Expected payments"
    assert _title(api, decision=decision, scenario="expected") == "Foshan · Payment terms · As they asked vs Option A · Expected payments"
    assert _title(api, decision=decision, scenario="late") == "Foshan · Payment terms · As they asked vs Option A · Foshan 30 days late"


def test_the_chart_title_in_chinese_has_no_english(api: TestClient) -> None:
    decision = _deal(api)
    zh = _title(api, "zh", decision=decision)
    assert zh == "Foshan · 付款账期 · 按对方要求 对比 方案 A · 预期收款"
    assert _title(api, "zh", decision=decision, scenario="late") == "Foshan · 付款账期 · 按对方要求 对比 方案 A · Foshan晚付 30 天"
    assert not english_leaks(zh, NAMES)


def test_the_chart_title_is_null_without_a_decision_or_for_one_that_is_not_a_deal_here(api: TestClient) -> None:
    decision = _deal(api)
    assert _title(api) is None
    assert _title(api, scenario="late") is None  # a scenario alone names no deal
    assert _title(api, decision="deal:OFF-nothing") is None
    assert _title(api, decision="funding:ALERT-RESERVE-12") is None
    assert _title(api, decision=decision) is not None


def test_the_chart_title_moves_no_figure(api: TestClient) -> None:
    decision = _deal(api)
    plain = _home(api)["home_v2"]
    titled = api.get("/home", params={"decision": decision, "scenario": "late"}).json()["home_v2"]
    plain["chart"].pop("scenario_title_text")
    titled["chart"].pop("scenario_title_text")
    assert plain == titled
