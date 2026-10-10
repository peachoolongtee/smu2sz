"""Wave 3 (wayfinder #65, ticket #72, F18): the funding comparison contract. `with_roles` orders the rows the way the owner reads them and
gives each a group, a rank for the runnable ones only, and the words for arrival, gap, basis and consent. The router's figures are
untouched; only the order and the labels are the API's."""

from __future__ import annotations

from types import SimpleNamespace

from app.api.presentation import comparison_contract
from tests.alerts.test_repay_alert import OWNER, to_day34
from tests.nl import conftest as nl_conftest

rt = nl_conftest.rt  # the in-memory runtime and the app client of the chat tests
client = nl_conftest.client

SPEC_ORDER = ["full_discount", "line_partial_early_pay", "router_optimum", "line_guaranteed_loan", "line_only"]


def _plan(client, lang: str = "en") -> dict:
    return client.post("/router/plan", params={"lang": lang}, headers=OWNER).json()


def test_day0_the_router_optimum_is_rank_one_and_the_buyer_plans_are_conditional_and_unranked(client, rt):
    rows = {r["key"]: r for r in _plan(client)["comparison"]}
    opt = rows["router_optimum"]
    assert (opt["group"], opt["rank"], opt["total_fen"]) == ("RECOMMENDED", 1, 311_393)
    assert opt["total_display"].endswith("= ¥3,113.93")
    assert client.get("/home", headers=OWNER).json()["next_action"]["cost_total_display"] == "¥3,113.93"  # the card and the row agree
    for key, total in (("full_discount", 504_000), ("line_partial_early_pay", 393_881)):
        row = rows[key]
        assert (row["group"], row["rank"], row["total_fen"]) == ("CONDITIONAL_ON_BUYER", None, total)
        assert row["group_text"] == "Only if the buyer agrees to early payment"
        assert row["consent_text"] == "Needs Foshan Home Retail Co. to agree to pay early; it cannot run until they do."
        assert row["arrival_when"] is None and "buyer" in row["arrival_text"]
    assert rows["full_discount"]["total_display"] == "¥5,040.00"
    assert rows["line_partial_early_pay"]["total_display"].endswith("= ¥3,938.81")


def test_day0_the_line_only_plan_is_insufficient_and_says_what_it_leaves_uncovered(client, rt):
    rows = {r["key"]: r for r in _plan(client)["comparison"]}
    line = rows["line_only"]
    assert (line["group"], line["rank"], line["uncovered_display"], line["remaining_gap_display"]) == (
        "INSUFFICIENT", None, "¥255,000.00", "¥255,000.00")
    assert line["group_text"] == "Leaves ¥255,000.00 uncovered" and line["remaining_gap_fen"] == 25_500_000
    assert rows["router_optimum"]["remaining_gap_display"] is None and rows["router_optimum"]["remaining_gap_text"] == "No gap is left."


def test_day0_a_facility_not_yet_available_says_the_earliest_day_and_is_never_ranked(client, rt):
    loan = {r["key"]: r for r in _plan(client)["comparison"]}["line_guaranteed_loan"]
    assert (loan["group"], loan["rank"], loan["available_when"]) == ("NOT_AVAILABLE_YET", None, "in 21 days")
    assert loan["group_text"] == "Not available yet: earliest in 21 days" and loan["total_fen"] is None


def test_day0_the_order_is_the_recommended_plan_then_runnable_then_buyer_dependent_and_the_ranks_run_one_to_n(client, rt):
    plan = _plan(client)
    rows = plan["comparison"]
    assert [r["group"] for r in rows] == ["RECOMMENDED", "CONDITIONAL_ON_BUYER", "CONDITIONAL_ON_BUYER", "INSUFFICIENT", "NOT_AVAILABLE_YET"]
    # the buyer-dependent plans are cheapest first among themselves: 3,938.81 before 5,040.00
    assert [r["total_fen"] for r in rows if r["group"] == "CONDITIONAL_ON_BUYER"] == [393_881, 504_000]
    assert [r["rank"] for r in rows] == [1, None, None, None, None]
    assert plan["recommended_key"] == "router_optimum" and rows[0]["key"] == "router_optimum"
    assert "cheapest first" in plan["comparison_order_text"]


def test_the_routers_own_spec_order_is_kept_as_router_order(client, rt):
    rows = _plan(client)["comparison"]
    assert [r["key"] for r in sorted(rows, key=lambda r: r["router_order"])] == SPEC_ORDER
    # the router's figures are the router's: the totals are those of the spec rows
    assert {r["key"]: r["total_fen"] for r in rows} == {
        "full_discount": 504_000, "line_partial_early_pay": 393_881, "router_optimum": 311_393, "line_guaranteed_loan": None, "line_only": 84_164}


def test_every_row_carries_its_arrival_basis_and_gap_and_the_words_are_in_both_languages(client, rt):
    en = {r["key"]: r for r in _plan(client)["comparison"]}
    zh = {r["key"]: r for r in _plan(client, "zh")["comparison"]}
    opt = en["router_optimum"]
    assert (opt["arrival_when"], opt["arrival_day"]) == ("in 3 days", 3)
    assert opt["basis_text"].startswith("All charges to the assumed repayment day in 32 days.")
    assert zh["router_optimum"]["group_text"] == "推荐方案" and zh["router_optimum"]["basis_text"].startswith("所有费用均计算至假定还款日")
    assert zh["full_discount"]["group_text"] == "仅当买方同意提前付款" and zh["full_discount"]["consent_text"].startswith("需要")
    assert zh["line_only"]["group_text"] == "仍有 ¥255,000.00 缺口未覆盖"
    assert zh["line_guaranteed_loan"]["group_text"] == "暂不可用：最早21 天后"
    # a row with no figure says so: the early-payment-only plan has no repayment day to state
    assert en["full_discount"]["basis_text"] is None and en["full_discount"]["arrival_day"] is None


def test_day34_the_recommended_cure_stays_first_and_the_runnable_alternative_is_rank_two(client, rt):
    to_day34(client, rt)
    plan = _plan(client)
    rows = plan["comparison"]
    assert [(r["key"], r["group"], r["rank"]) for r in rows] == [
        ("recommended_plan", "RECOMMENDED", 1), ("router_optimum", "ALTERNATIVE", 2), ("full_discount", "CONDITIONAL_ON_BUYER", None)]
    assert [r["total_fen"] for r in rows] == [178_219, 170_610, 504_000]  # every figure is the router's or the card's own
    assert rows[0]["router_order"] is None  # the cure row is the API's, not a spec row
    assert rows[0]["basis_text"] and rows[0]["remaining_gap_text"]  # the card's own basis and after-state sentences


def _row(key: str, total: int | None, **over) -> dict:
    base = {"key": key, "role": "alternative", "role_reason": "x", "total_fen": total, "executable_now": True, "reason_kind": None,
            "actions": [], "result": "ADMISSIBLE"}
    return {**base, **over}


def test_ranked_alternatives_are_ordered_by_total_cost_ascending_whatever_order_the_router_gave():
    rows = [_row("dear", 900), _row("buyer", 100, executable_now=False, reason_kind="buyer_early_pay"), _row("cheap", 300),
            _row("rec", 500, role="recommended"), _row("middle", 600), _row("none", None)]
    out = comparison_contract(rows, None, _EMPTY_STATE, 0, "en")
    assert [(r["key"], r["rank"]) for r in out] == [("rec", 1), ("cheap", 2), ("middle", 3), ("dear", 4), ("none", 5), ("buyer", None)]
    ranked = [r["total_fen"] for r in out if r["rank"] and r["key"] != "rec" and r["total_fen"] is not None]
    assert ranked == sorted(ranked)
    assert [r["router_order"] for r in out] == [3, 2, 4, 0, 5, 1]


_EMPTY_STATE = SimpleNamespace(receivables=[], counterparties=[], facilities=[])
