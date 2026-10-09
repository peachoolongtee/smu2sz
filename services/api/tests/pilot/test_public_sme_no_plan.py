"""The three strategy routes on the public-record books at week 2 (day 14), when the router has no committed plan
(map #58, ticket #79).

From day 14 the reserve breach starts today and no committed facility lands in time: the alerts say CRITICAL, "No
committed facility can cure it", and `plan(...).admissible` is false with a cost read as 0. The routes used to read that
0 as a price: the curve went flat ("Earlier cash saves you nothing today."), every worth row said "Saves nothing extra
now" and every envelope cost line read ¥0.00 while it kept offering 100-day terms and rebates. Each route now says the
plan is missing in its own sentence. The books are loaded as `test_public_sme.py` loads them (the pilot runtime's own
`build_runtime`) and the clock is moved the way the dry pilot moves it (`Runtime.advance_to`)."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.books import books_from_store
from app.strategy.no_plan import no_committed_plan

API_DIR = Path(__file__).resolve().parents[2]
SCENARIOS = API_DIR.parents[1] / "fixtures" / "scenarios"
SCRIPT = API_DIR / "scripts" / "pilot_runtime.py"
MANDATE = SCENARIOS / "public_sme.mandate.json"
OWNER = {"X-Owner-Token": "demo-owner-token"}

CURVE_EN = "No committed funding plan covers the shortfall, so earlier cash cannot be priced against borrowing: collect first."
WITHHELD_EN = "FLOW cannot offer longer terms or a rebate while no funding plan covers the shortfall; early payment only."
NOT_PRICED_EN = "Your current funding plan is not priced because no committed plan covers the shortfall."


@pytest.fixture(scope="module")
def runtime(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Runtime]:
    """The public-record books, the clock advanced two weeks (day 14): module-scoped, nothing here writes."""
    spec = importlib.util.spec_from_file_location("pilot_runtime_no_plan", SCRIPT)
    assert spec and spec.loader
    pilot: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules["pilot_runtime_no_plan"] = pilot
    spec.loader.exec_module(pilot)
    raw = json.loads((SCENARIOS / "public_sme.json").read_text(encoding="utf-8"))
    path = tmp_path_factory.mktemp("public_sme_no_plan") / "state.json"
    path.write_text(json.dumps(raw["state"]), encoding="utf-8")
    rt = pilot.build_runtime(path, MANDATE)
    rt.advance_to(7)
    rt.advance_to(14)
    set_runtime(rt)
    yield rt
    set_runtime(None)


@pytest.fixture(scope="module")
def api(runtime: Runtime) -> Iterator[TestClient]:
    from app.api import strategy_collections, strategy_curve, strategy_envelope
    from app.main import app

    patch = pytest.MonkeyPatch()
    for flag in ("ENVELOPE", "PRICE_CURVE", "COLLECTIONS_WORTH"):
        patch.setenv(f"FEATURE_{flag}", "1")
    for module in (strategy_collections, strategy_curve, strategy_envelope):
        module.clear_cache()
    yield TestClient(app, headers=OWNER)
    for module in (strategy_collections, strategy_curve, strategy_envelope):
        module.clear_cache()
    patch.undo()


def test_the_router_has_no_committed_plan_at_week_2_and_has_one_at_week_1(runtime: Runtime) -> None:
    books, mandate = books_from_store(runtime.store), runtime.store.get_mandate()
    assert runtime.day == 14 and no_committed_plan(books, mandate)
    from app.alerts import alerts

    breach = [a for a in alerts(books.state, mandate, runtime.store, 14) if a.kind == "RESERVE_BREACH_AHEAD"]
    assert breach and all(a.committed_cure is False and a.severity == "CRITICAL" for a in breach)


def test_the_curve_says_it_cannot_price_earlier_cash_and_shows_no_zero(api: TestClient) -> None:
    body = api.get("/cash/price-curve").json()
    assert body["sentence"] == CURVE_EN
    assert body["no_plan"] is True and body["flat"] is False
    assert body["bands"] == [], "no band means no ¥0.00 figure and no above_guard flag"
    assert "saves you nothing" not in body["sentence"]
    zh = api.get("/cash/price-curve", params={"lang": "zh"}).json()["sentence"]
    assert zh.startswith("目前没有已承诺的融资方案能补上缺口") and "请先催收" in zh


def test_the_worth_ranking_runs_by_lateness_then_amount_with_the_sentence_at_the_top(api: TestClient) -> None:
    body = api.get("/receivables/worth").json()
    assert body["no_plan"] is True
    assert body["top_action"].startswith("No committed funding plan covers the shortfall, so what collecting each invoice saves "
                                         "cannot be priced")
    assert body["top_action_second"] == "¥3,000,000.00 from Buyer B is 49 days late: ask them to pay."
    rows = body["rows"]
    assert [r["receivable_id"] for r in rows[:3]] == ["RCV-B1", "RCV-F1", "RCV-D1"], "49, 34 then 24 days late"
    late = [r for r in rows if r["days_late"] > 0]
    assert [r["days_late"] for r in late] == sorted((r["days_late"] for r in late), reverse=True)
    rest = rows[len(late):]
    assert all(r["days_late"] == 0 for r in rest) and len(rest) == 8
    assert [r["outstanding_fen"] for r in rest] == sorted((r["outstanding_fen"] for r in rest), reverse=True)
    assert "Wait" not in rows[0]["action_sentence"] and rows[0]["receivable_id"] == "RCV-B1"
    for r in late:
        assert r["worth_text"] == f"Cannot be priced: no funding plan; {r['days_late']} days late"
    assert all(r["worth_text"] == "Cannot be priced: no funding plan" for r in rest)
    for r in rows:
        assert "Saves nothing extra now" not in r["worth_text"] and r["net_saving_display"] == "cannot be priced"
        assert "would not lower your funding cost" not in r["reason_sentence"] and "saves nothing extra" not in r["action_sentence"]
        assert all(e["saving_display"] == "cannot be priced" and e["saving_fen"] == 0 for e in r["effects"])
    assert "ranked by how late each invoice is, then by amount" in body["ranking_note"]


def test_the_worth_ranking_in_chinese_says_the_same(api: TestClient) -> None:
    body = api.get("/receivables/worth", params={"lang": "zh"}).json()
    assert body["top_action"].startswith("目前没有已承诺的融资方案能补上缺口")
    assert [r["receivable_id"] for r in body["rows"][:3]] == ["RCV-B1", "RCV-F1", "RCV-D1"]
    assert body["rows"][0]["worth_text"] == "无法估值：没有融资方案；已逾期 49 天"
    assert body["rows"][-1]["worth_text"] == "无法估值：没有融资方案"


@pytest.mark.parametrize("buyer", ["BUYER-A", "BUYER-F"])
def test_the_envelope_withholds_terms_and_rebate_and_says_why_and_does_not_price_the_plan(api: TestClient, buyer: str) -> None:
    body = api.get(f"/buyers/{buyer}/envelope").json()
    assert body["reason"].endswith(WITHHELD_EN)
    assert body["money"] == NOT_PRICED_EN and "¥0.00" not in body["money"]
    assert body["primary"].startswith("You can live with: early payment at up to ")
    assert "terms" not in body["primary"] and "rebate" not in body["primary"]
    assert body["packages"] and all(p["package"]["rebate_bp"] == 0 and p["package"]["price_bp"] == 0 for p in body["packages"])
    assert all(p["plan_cost_fen"] is None for p in body["packages"])
    levers = {lv["key"]: lv for lv in body["levers"]}
    for key in ("terms_alone", "terms_budget_ignored", "terms_with_price", "rebate"):
        assert levers[key]["maximum"] is None and levers[key]["unavailable"] == "withheld while no funding plan covers the shortfall"
    assert levers["early_pay_whole"]["maximum"]
    assert body["zone"] == []


def test_the_envelope_names_the_overdue_invoice_before_the_withheld_levers(api: TestClient) -> None:
    reason = api.get("/buyers/BUYER-F/envelope").json()["reason"]
    assert reason.startswith("The ¥7,500,000.00 still owed by Other buyers (aggregate) is 34 days past due")
    assert reason.count(WITHHELD_EN) == 1


def test_a_buyer_with_only_early_payment_keeps_its_own_reason_and_still_reads_not_priced(api: TestClient) -> None:
    body = api.get("/buyers/BUYER-E/envelope").json()
    assert body["reason"] == "There is no recurring invoice to extend, so only an early payment can be priced."
    assert body["money"] == NOT_PRICED_EN
    assert body["primary"] == "You can live with: early payment at up to 0.45% on ¥2,305,982.09."
    assert {lv["key"]: lv["unavailable"] for lv in body["levers"]}["terms_alone"] == "no recurring invoice to extend"


def test_the_envelope_in_chinese(api: TestClient) -> None:
    body = api.get("/buyers/BUYER-A/envelope", params={"lang": "zh"}).json()
    assert body["reason"] == "在没有融资方案能补上缺口时，FLOW 无法提供更长账期或返利；只能提前付款。"
    assert body["money"].startswith("现行资金安排无法估值") and "¥0.00" not in body["money"]
    assert "账期" not in body["primary"] and "返利" not in body["primary"]


def test_week_1_is_priced_as_before(tmp_path: Path, pilot_at_week_1: Runtime) -> None:
    """The plan exists on day 7 (a ¥4.28m draw, ¥5,631.28): the curve is the fixture's reading seven days on, nothing is withheld."""
    from app.api import strategy_curve
    from app.main import app

    rt = pilot_at_week_1
    books, mandate = books_from_store(rt.store), rt.store.get_mandate()
    assert rt.day == 7 and not no_committed_plan(books, mandate)
    set_runtime(rt)
    try:
        strategy_curve.clear_cache()
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("FEATURE_PRICE_CURVE", "1")
            body = TestClient(app, headers=OWNER).get("/cash/price-curve").json()
    finally:
        strategy_curve.clear_cache()
    assert body["no_plan"] is False and body["flat"] is False and body["bands"]
    assert body["sentence"] == ("Cash in the next 17 days saves you ¥13.15 of funding cost per ¥10,000 (0.13%); "
                                "after that, earlier cash saves nothing.")


@pytest.fixture
def pilot_at_week_1(tmp_path: Path) -> Iterator[Runtime]:
    spec = importlib.util.spec_from_file_location("pilot_runtime_no_plan_w1", SCRIPT)
    assert spec and spec.loader
    pilot: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules["pilot_runtime_no_plan_w1"] = pilot
    spec.loader.exec_module(pilot)
    raw = json.loads((SCENARIOS / "public_sme.json").read_text(encoding="utf-8"))
    path = tmp_path / "state.json"
    path.write_text(json.dumps(raw["state"]), encoding="utf-8")
    rt = pilot.build_runtime(path, MANDATE)
    rt.advance_to(7)
    yield rt
    set_runtime(None)
