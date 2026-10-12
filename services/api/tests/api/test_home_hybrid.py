"""GET /home, the hybrid's server side (map #88, Home E): the position, the attention queue, the event rail and the cards.

Golden day 0: the Foshan offer (60-day terms, a 1% rebate, early payment) is evaluated, and FLOW's plan (a ¥150k credit-line draw and
¥255k of invoice financing for ¥3,113.93) is either ready or has run. Every figure is the kernel's own: the rail's cash is the trajectory's
closing cash, the costs are the router's cost lines, the deal's cost is the verdict's."""

from __future__ import annotations

import importlib
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from app.api import home_hybrid
from app.api.presentation import fmt_short
from app.api.runtime import get_runtime
from tests.api.conftest import english_leaks, figures, unchanged_words

# the routes a page links to are the same in both languages
ROUTES = [r"\.attention\.items\[\]\.(primary|secondary)\.href", r"\.(deals_card\.rows\[\]|receivables_card|changes_card)\.href"]
AUDIT = [r"\.next_action\.(formula|detail_raw)", r"\.next_action\.legs\[\]\.formula", r"\.next_action\.cost_breakdown\[\]\.formula",
         r"\.cash\.series\[\]\.events\[\]\.label(_short)?", r"\.cash\.plan_series\[\]\.events\[\]\.label(_short)?",
         r"\.cash\.counterfactual_series\[\]\.events\[\]\.label(_short)?",
         r"\.cash\.pending\.series\[\]\.events\[\]\.label(_short)?", *ROUTES]


@pytest.fixture(autouse=True)
def _no_fallback(caplog):
    """No test passes through the home's fallback for a hybrid that could not be built (the one test that means to says so)."""
    with caplog.at_level(logging.WARNING, logger="termsledger.decisions"):
        yield
    assert not [r for r in caplog.records if "could not be built" in r.getMessage()], "the hybrid fell back"


@pytest.fixture(autouse=True)
def _fresh_pictures():
    """The offer picture is cached by state version, day and offer; a test that moves the books by hand must not leave its picture to the
    next test that reaches the same key."""
    from app.api import offer_picture

    offer_picture._cache.clear()
    yield
    offer_picture._cache.clear()


def _offer(client) -> str:
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    return offer["offer_id"]


def _run_plan(client) -> None:
    a = client.get("/home").json()["next_action"]
    r = client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()
    assert r["executed"] == 2


def _before(client) -> dict[str, Any]:
    """Golden day 0 with the offer waiting and the plan ready, not run."""
    _offer(client)
    h = client.get("/home").json()
    assert h["partial"] is None
    return h


def _after(client) -> dict[str, Any]:
    """Golden day 0 after the plan ran: ¥150k drawn, ¥255k of invoice financing landing in 3 days."""
    _offer(client)
    _run_plan(client)
    h = client.get("/home").json()
    assert h["partial"] is None
    return h


def _closing(h: dict[str, Any]) -> dict[int, int]:
    return {r["day"]: r["closing_fen"] for r in h["cash"]["series"]}


# ---------------------------------------------------------------- H1: the position


def test_after_the_plan_the_position_is_covered_on_the_current_plan(client):
    h = _after(client)
    cash = h["cash"]
    assert (cash["status_word"], cash["status_tone"]) == ("Covered, but tight", "warn")
    assert h["status_text"] == cash["status_word"]  # the pill's fields stay, and say the same
    assert cash["headline_conditional"] == "Your cash is covered on the current plan."
    assert cash["headline_note"] == ("Cash stays at or above your ¥300k minimum for the next 120 days, assuming the financing arrives in "
                                     "3 days and Foshan pays in 32 days as scheduled. It touches the minimum in 30 days.")
    assert cash["assumptions"] == ["The ¥255k of invoice financing arrives in 3 days.",
                                   "Foshan pays ¥420k in 32 days, as scheduled.",
                                   "The scheduled payroll, supplier and debt payments are paid as entered."]
    # the existing headline and the pill are untouched
    assert h["headline"] == "You're covered." and h["status"] == "WATCH"


def test_the_three_facts_carry_their_notes_and_tones(client):
    cash = _after(client)["cash"]
    today, lowest, arriving = cash["facts"]
    assert (today["key"], today["label"], today["value_short"], today["value_display"]) == ("today", "Cash today", "¥550k", "¥550,000.00")
    assert (today["note"], today["tone"]) == ("¥250k above your minimum", "ok")
    assert (lowest["key"], lowest["label"], lowest["value_short"], lowest["value_display"]) == (
        "lowest", "Lowest point, in 30 days", "¥300k", "¥300,000.00")
    assert (lowest["note"], lowest["tone"]) == ("¥0 above your minimum", "warn")
    assert (arriving["key"], arriving["value_short"], arriving["note"], arriving["tone"]) == (
        "arriving", "¥255k", "Invoice financing, in 3 days", "neutral")
    # the figures are the existing cash block's own
    assert today["value_fen"] == cash["cash_fen"] and lowest["value_fen"] == cash["lowest_fen"]


def test_before_the_plan_the_position_is_the_existing_headline_and_the_lowest_is_the_plans(client):
    h = _before(client)
    cash = h["cash"]
    assert (cash["status_word"], cash["status_tone"]) == ("Action needed", "bad")
    assert cash["headline_conditional"] == h["headline"] == "Your cash reserve becomes unsafe in 12 days."
    assert cash["headline_note"] == h["note"]  # nothing is covered yet, so no assumptions are leaned on
    today, lowest, arriving = cash["facts"]
    assert (today["note"], today["tone"]) == ("¥100k above your minimum", "ok")
    # one lowest point on the page: the plan line's, which the rail names too; the do-nothing −¥105k stays in the existing fields
    assert (lowest["label"], lowest["value_short"], lowest["note"], lowest["tone"]) == (
        "Lowest point with the plan, in 30 days", "¥300k", "¥0 above your minimum", "warn")
    rail_low = next(e for e in cash["events_rail"] if e["kind"] == "lowest")
    assert (lowest["value_fen"], lowest["when"]) == (rail_low["cash_after_fen"], rail_low["when"])
    assert cash["lowest_short"] == "−¥105k" and cash["lowest_tone"] == "bad"
    assert (arriving["value_short"], arriving["note"]) == ("¥420k", "Foshan, in 32 days")
    assert cash["assumptions"][0] == "Foshan pays ¥420k in 32 days, as scheduled."


@pytest.mark.parametrize("plan", [False, True])
def test_the_lowest_fact_and_the_rails_lowest_event_always_agree(client, plan):
    h = _after(client) if plan else _before(client)
    facts = {f["key"]: f for f in h["cash"]["facts"]}
    rail_low = next(e for e in h["cash"]["events_rail"] if e["kind"] == "lowest")
    assert (facts["lowest"]["value_fen"], facts["lowest"]["when"]) == (rail_low["cash_after_fen"], rail_low["when"])


def test_status_tone_follows_the_pill(client):
    _offer(client)
    assert client.get("/home").json()["cash"]["status_tone"] == "bad"  # ACTION_NEEDED
    _run_plan(client)
    assert client.get("/home").json()["cash"]["status_tone"] == "warn"  # WATCH
    client.post("/clock/advance", json={"to_day": 10})
    assert client.get("/home").json()["cash"]["status_tone"] == "warn"  # still thin: covered, but tight


@pytest.mark.parametrize(("cash", "floor", "tone", "en"), [
    (550_00000, 300_00000, "ok", "¥250k above your minimum"),
    (300_00000, 300_00000, "warn", "¥0 above your minimum"),
    (240_00000, 300_00000, "bad", "¥60k below your minimum"),
    (-105_00000, 300_00000, "bad", "¥405k below your minimum"),
])
def test_tone_and_room_at_the_minimum(cash, floor, tone, en):
    assert home_hybrid._tone(cash, floor) == tone
    assert home_hybrid.room_text(cash, floor, "en") == en
    assert home_hybrid.room_text(cash, floor, "zh") != en


def test_the_position_changes_nothing(client):
    _offer(client)
    rt = get_runtime()
    before = (rt.store.get_state().state_version, len(rt.store.operations()), rt.store.operations()[-1].entry_hash if rt.store.operations() else None)
    client.get("/home")
    client.get("/home", params={"lang": "zh"})
    assert before == (rt.store.get_state().state_version, len(rt.store.operations()),
                      rt.store.operations()[-1].entry_hash if rt.store.operations() else None)


# ---------------------------------------------------------------- H2: the attention queue


def test_the_foshan_deal_is_the_primary_once_the_plan_has_run(client):
    h = _after(client)
    att = h["attention"]
    assert [i["kind"] for i in att["items"]] == ["deal", "landing"]
    deal = att["items"][0]
    assert att["primary_key"] == deal["key"] and deal["key"].startswith("deal:OFF-")
    assert deal["eyebrow"] == "1 deal needs your response"
    # what the picture of the offer recommends now that the invoice is financed: Option B, which needs the owner's approval
    assert deal["title"] == ("Foshan asked for 60-day terms, a 1% rebate and a 1.2% discount for paying early. "
                             "FLOW recommends countering with Option B.")
    assert deal["facts"] == [{"label": "Cost of Option B", "value": "¥0.00, the price rise pays for the longer terms", "tone": "neutral"},
                             {"label": "As asked", "value": "over your ¥5,000 limit", "tone": "warn"}]
    assert deal["primary"] == {"label": "Review the counter", "href": "/deals?buyer=BUYER-1"}
    assert deal["secondary"] == {"label": "Why this?", "href": "/decisions/deal%3A" + deal["key"].removeprefix("deal:")}
    landing = att["items"][1]
    assert landing["title"] == "¥255k of funding from Invoice financing arrives in 3 days."
    assert [(f["label"], f["value"]) for f in landing["facts"]] == [("Invoice financing", "¥255k in 3 days (arranged)"),
                                                                   ("From", "Invoice financing")]
    assert att["none_text"] == "No urgent action required."


def test_the_funding_recommendation_leads_while_cash_is_unsafe_and_the_deal_follows_with_its_option_a_cost(client):
    h = _before(client)
    att = h["attention"]
    assert [i["kind"] for i in att["items"]] == ["funding", "deal"] and att["primary_key"] == att["items"][0]["key"]
    funding, deal = att["items"]
    assert funding["title"] == "Your cash reserve becomes unsafe in 12 days. FLOW recommends securing ¥405k of funding."
    assert [(f["label"], f["value"], f["tone"]) for f in funding["facts"]] == [
        ("Estimated cost", "¥3,113.93", "neutral"), ("Funds arrive", "in 3 days", "neutral"),
        ("Credit line draw", "¥150k today (planned)", "neutral"), ("Invoice financing", "¥255k in 3 days (planned)", "neutral"),
        ("Authority", "within your signed limits", "ok")]
    assert funding["facts"][1]["value"] == h["next_action"]["lands_when"]  # the plain landing fact the page pins (`next-action-lands`)
    assert funding["primary"]["href"] == "/cash#cash-options"
    # the deal reads from the picture the Deals page draws: Option A, once, ¥3,027.77
    assert deal["title"].endswith("FLOW recommends countering with Option A.")
    assert deal["facts"][0] == {"label": "Cost of Option A", "value": "¥3,027.77, once; nothing ongoing", "tone": "neutral"}
    assert deal["facts"][1] == {"label": "As asked", "value": "over your ¥5,000 limit", "tone": "warn"}
    assert len(deal["facts"]) == 2  # the exposure fact is only named when the exposure layer is on


def test_the_deal_reads_the_pictures_recommended_path(client):
    offer_id = _offer(client)
    for plan in (False, True):
        if plan:
            _run_plan(client)
        picks = [p for p in client.get(f"/offers/{offer_id}/picture").json()["paths"] if p["recommended"]]
        assert len(picks) == 1
        h = client.get("/home").json()
        deal = next(i for i in h["attention"]["items"] if i["kind"] == "deal")
        assert f"countering with {picks[0]['label']}." in deal["title"]
        assert deal["facts"][0]["label"] == f"Cost of {picks[0]['label']}"
        assert deal["facts"][0]["value"].startswith(picks[0]["cost_display"])


def test_a_queued_approval_replaces_the_funding_it_waits_on(client):
    from app.domain.fixtures import load_scenario

    rt = get_runtime()
    state, _ = load_scenario()
    rt.store.put_state(state.model_copy(update={"facilities": [
        f.model_copy(update={"drawn_fen": f.limit_fen}) if f.id in ("FAC-LINE", "FAC-IF") else f for f in state.facilities]}))
    a = client.get("/home").json()["next_action"]
    client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]})
    h = client.get("/home").json()
    att = h["attention"]
    assert [i["kind"] for i in att["items"]] == ["approval"] and att["primary_key"] == "approval:APR-000001"
    item = att["items"][0]
    assert item["eyebrow"] == "1 approval needs you" and item["title"] == h["approvals"][0]["headline"]
    assert item["primary"]["href"] == "/approvals#approval-APR-000001"
    assert h["funding_line"]["state"] == "none" and h["funding_line"]["text"] == "No funding is arranged yet. The plan waits for your approval."


def test_a_late_customer_is_the_collection_and_a_calm_book_has_no_queue(client):
    _offer(client)
    _run_plan(client)
    client.post("/clock/advance", json={"to_day": 10})
    calm = client.get("/home").json()["attention"]
    assert [i["kind"] for i in calm["items"]] == ["deal"]  # the offer still waits; nothing else does
    # without any offer or pending landing, nothing needs the owner
    client.post("/demo/reset", json={})
    _run_plan(client)
    client.post("/clock/advance", json={"to_day": 10})
    assert client.get("/home").json()["attention"] == {"items": [], "primary_key": None, "none_text": "No urgent action required."}
    client.post("/clock/advance", json={"to_day": 40})
    late = client.get("/home").json()["attention"]
    assert [i["kind"] for i in late["items"]] == ["collection"] and late["primary_key"] == "collection:BUYER-1"
    item = late["items"][0]
    assert item["title"] == "Foshan is 8 days late on ¥420k." and item["eyebrow"] == "1 customer is late"
    assert [(f["label"], f["value"], f["tone"]) for f in item["facts"]] == [("Overdue", "¥420k", "bad"), ("Late by", "8 days", "bad")]


def test_the_queue_is_ranked_funding_deal_approval_collection_landing(monkeypatch):
    def one(kind):
        return {"key": kind, "kind": kind}

    c = SimpleNamespace(lang="en")
    monkeypatch.setattr(home_hybrid, "_funding_item", lambda c: one("funding"))
    monkeypatch.setattr(home_hybrid, "_deal_item", lambda c, d, n: one("deal"))
    monkeypatch.setattr(home_hybrid, "_approval_items", lambda c: [one("approval")])
    monkeypatch.setattr(home_hybrid, "_collection_items", lambda c: [one("collection")])
    monkeypatch.setattr(home_hybrid, "_landing_items", lambda c: [one("landing")])
    deals = [SimpleNamespace(state=home_hybrid.DealState.RESPONSE_READY)]
    att = home_hybrid.attention(c, deals)
    assert [i["kind"] for i in att["items"]] == ["funding", "deal", "approval", "collection", "landing"]
    assert att["primary_key"] == "funding"
    # a deal waiting for the buyer, or a funding that waits on an approval, is not a deal for the owner to answer
    waiting = [SimpleNamespace(state=home_hybrid.DealState.NEEDS_CLARIFICATION)]
    assert "deal" not in [i["kind"] for i in home_hybrid.attention(c, waiting)["items"]]


def test_the_exposure_fact_is_named_only_with_the_flag_and_the_layer(client, monkeypatch):
    _before(client)
    off = next(i for i in client.get("/home").json()["attention"]["items"] if i["kind"] == "deal")
    assert [f["label"] for f in off["facts"]] == ["Cost of Option A", "As asked"]
    if importlib.util.find_spec("app.strategy.concentration") is None:
        pytest.skip("the exposure layer is not on this branch")
    monkeypatch.setattr(home_hybrid, "_exposure_on", lambda rt: True)
    on = next(i for i in client.get("/home").json()["attention"]["items"] if i["kind"] == "deal")
    assert on["facts"][2] == {"label": "Exposure", "value": "Foshan is 100% of what you are owed", "tone": "warn"}


# ---------------------------------------------------------------- H2: the funding line


def test_the_funding_line_after_the_plan_splits_the_cost_from_the_routers_lines(client):
    h = _after(client)
    line = h["funding_line"]
    assert line["state"] == "arranged"
    assert line["text"] == "Funding arranged · ¥255k of invoice financing expected in 3 days, repaid from Foshan's receipt in 32 days."
    # the router's own cost lines: the invoice-financing leg and the whole plan (the plan's total, ¥3,113.93 in DEMO_FLOW)
    assert (line["cost_leg_display"], line["cost_leg_label"]) == ("¥2,272.29", "the invoice-financing leg")
    assert (line["cost_total_display"], line["cost_total_label"]) == (
        "¥3,113.93", "the whole plan, with the ¥150k credit-line draw already made")
    assert line["authority_text"] == "Within your signed limits; nothing for you to do."


def test_the_funding_line_before_the_plan_is_the_ready_plan(client):
    h = _before(client)
    line = h["funding_line"]
    a = h["next_action"]
    assert line["state"] == "none" and line["text"] == "No funding is arranged yet. FLOW has a plan ready."
    assert line["cost_total_display"] == a["cost_total_display"] == "¥3,113.93"
    assert line["cost_leg_display"] == a["legs"][1]["cost_display"] == "¥2,272.29"
    assert line["cost_total_label"] == "the whole plan, including the ¥150k credit-line draw"
    assert line["authority_text"] == a["authority_text"]


def test_the_funding_line_follows_the_funds_in(client):
    _offer(client)
    _run_plan(client)
    client.post("/clock/advance", json={"to_day": 10})
    line = client.get("/home").json()["funding_line"]
    assert line["state"] == "landed"
    assert line["text"] == "Funding landed · ¥255k of invoice financing is in your cash, repaid from Foshan's receipt in 22 days."
    assert line["cost_total_display"] == "¥3,113.93"
    client.post("/clock/advance", json={"to_day": 40})
    late = client.get("/home").json()["funding_line"]
    assert late["text"].endswith("to be repaid from Foshan's payment, which is 8 days late.")


def test_with_nothing_run_and_no_breach_there_is_no_funding(client):
    h = client.get("/home").json()
    assert h["funding_line"]["state"] == "none"
    assert h["funding_line"]["cost_leg_display"] == h["next_action"]["legs"][1]["cost_display"]


# ---------------------------------------------------------------- H3: the event rail


def test_the_rail_after_the_plan_is_the_key_events_with_the_trajectorys_own_cash(client):
    h = _after(client)
    cash = h["cash"]
    rail = cash["events_rail"]
    assert [(e["day"], e["kind"]) for e in rail] == [(3, "landing"), (12, "payroll"), (20, "supplier"), (30, "lowest"), (32, "receipt")]
    assert len(rail) <= 6 and [e["day"] for e in rail] == sorted(e["day"] for e in rail)
    closing = _closing(h)
    for e in rail:
        assert e["cash_after_fen"] == closing[e["day"]]  # the trajectory's own closing cash on that day
        assert e["cash_after_short"] == fmt_short(closing[e["day"]])
        assert e["room_after_fen"] == closing[e["day"]] - cash["floor_fen"]
    by = {e["day"]: e for e in rail}
    assert (by[3]["label"], by[3]["amount_short"], by[3]["cash_after_short"]) == ("invoice financing arrives", "+¥255k", "¥805k")
    assert (by[12]["label"], by[12]["amount_short"], by[12]["cash_after_short"], by[12]["room_after_short"], by[12]["tone"]) == (
        "payroll is paid", "−¥340k", "¥465k", "¥165k above your minimum", "ok")
    assert by[12]["cash_after_display"] == "¥465,000.00"
    assert by[30]["tone"] == "warn" and by[30]["room_after_short"] == "¥0 above your minimum"
    assert [e["tone"] for e in rail] == ["ok", "ok", "ok", "warn", "ok"]


def test_the_rail_explains_with_the_plan_and_without_it(client):
    _offer(client)
    before = client.get("/home").json()
    _run_plan(client)
    h = client.get("/home").json()
    by = {e["day"]: e for e in h["cash"]["events_rail"]}
    low_before = min(r["closing_fen"] for r in before["cash"]["series"])
    # payroll: the line falls ¥805k to ¥465k; without the plan it would have gone to what the books said before the plan ran
    assert by[12]["explain"] == (
        f"Cash falls from ¥805k to ¥465k. Your minimum is ¥300k, so ¥165k of room remains. Without the financing plan, payroll would have "
        f"taken cash to {fmt_short(_closing(before)[12])}, below your minimum.")
    assert fmt_short(_closing(before)[12]) == "¥60k"
    assert fmt_short(_closing(before)[20]) in by[20]["explain"]
    # the lowest point names both lines
    assert by[30]["explain"] == (
        "This is the lowest point on your cash line: ¥300k, ¥0 above your minimum. Debt service of ¥45k takes cash from ¥345k to ¥300k. "
        f"Without the financing plan, the lowest point would have been {fmt_short(low_before)} in 30 days.")
    assert fmt_short(low_before) == "−¥105k"


def test_a_receipt_that_repays_the_financing_is_one_event_with_its_figures(client):
    h = _after(client)
    day32 = [e for e in h["cash"]["events_rail"] if e["day"] == 32]
    assert len(day32) == 1
    e = day32[0]
    assert (e["kind"], e["label"], e["amount_short"]) == ("receipt", "Foshan pays", "+¥420k")
    # the day's net is the series' own net (the receipt less everything the day repays)
    row = next(r for r in h["cash"]["series"] if r["day"] == 32)
    assert e["net_short"] == "+" + row["net_short"] == "+¥12k" and row["net_fen"] > 0
    assert e["explain"] == ("Foshan pays ¥420k, and ¥257k of it repays the invoice financing, leaving ¥163k. "
                            "¥151k of that repays the Bank credit line. Cash rises from ¥300k to ¥312k, ¥12k above your minimum.")
    events = {x["kind"]: x["amount_fen"] for x in row["events"]}
    assert events["RECEIPT"] == 42_000_000


def test_before_the_plan_the_rail_is_the_plans_line_and_the_grey_line_is_doing_nothing(client):
    h = _before(client)
    cash = h["cash"]
    assert cash["counterfactual_label"] == "if you did nothing"
    plan = {r["day"]: r["closing_fen"] for r in cash["plan_series"]}
    rail = cash["events_rail"]
    assert all(e["cash_after_fen"] == plan[e["day"]] for e in rail)
    by = {e["day"]: e for e in rail}
    assert by[12]["explain"].endswith("If you did nothing, payroll would take cash to ¥60k, below your minimum.")
    assert "If you did nothing, the lowest point would be −¥105k in 30 days." in by[30]["explain"]


def test_the_counterfactual_line_is_the_books_before_the_plan_ran(client):
    _offer(client)
    before = client.get("/home").json()["cash"]
    _run_plan(client)
    after = client.get("/home").json()["cash"]
    assert after["counterfactual_label"] == "without FLOW's financing plan (a comparison, not a choice you still have)"
    # the kernel's projection of the books without the funding the plan created is the baseline the plan was priced against
    grey = after["counterfactual_series"]
    assert [(r["day"], r["closing_fen"]) for r in grey] == [(r["day"], r["closing_fen"]) for r in before["series"]]
    assert set(grey[0]) == set(after["series"][0]) and grey[0]["day"] == after["series"][0]["day"] == 0
    assert after["plan_series"] is None  # the plan has run: the web has no second line without this one


def test_before_the_plan_the_grey_line_is_doing_nothing_and_without_a_plan_there_is_none(client):
    _offer(client)
    cash = client.get("/home").json()["cash"]
    assert cash["counterfactual_label"] == "if you did nothing"
    assert [r["closing_fen"] for r in cash["counterfactual_series"]] == [r["closing_fen"] for r in cash["series"]]
    # a book with plenty of cash and no plan: nothing to compare, so neither the series nor the label
    rt = get_runtime()
    rt.store.put_state(rt.store.get_state().model_copy(update={"cash_fen": 5_000_000_00}))
    rich = client.get("/home").json()
    assert rich["next_action"] is None
    assert "counterfactual_series" not in rich["cash"] and "counterfactual_label" not in rich["cash"]


def test_a_further_plan_after_one_ran_is_compared_as_proposed_not_as_the_plan_that_ran(client, monkeypatch):
    _offer(client)
    monkeypatch.setattr(home_hybrid, "_plan_has_run", lambda state: True)  # a plan has run and another is ready
    cash = client.get("/home").json()["cash"]
    assert cash["counterfactual_label"] == "without the plan FLOW proposes (a comparison)"
    assert [r["closing_fen"] for r in cash["counterfactual_series"]] == [r["closing_fen"] for r in cash["series"]]
    by = {e["day"]: e for e in cash["events_rail"]}
    assert "Without the plan FLOW proposes, payroll would take cash to ¥60k" in by[12]["explain"]
    assert "financing plan" not in by[12]["explain"]


def test_the_lowest_point_stays_on_the_rail_when_the_window_does_not_reach_it(client, monkeypatch):
    from app.api import home

    monkeypatch.setattr(home, "_picture_days", lambda *a, **k: 10)
    h = _after(client)
    cash = h["cash"]
    kinds = {e["day"]: e["kind"] for e in cash["events_rail"]}
    assert cash["picture_days"] == 10 and kinds[30] == "lowest"
    assert [d for d in kinds if d <= 10] == [3] and cash["events_rail_days"] >= 30  # the rail says how far it runs
    assert all(d <= 10 or d == 30 for d in kinds)


def test_the_financing_is_the_lenders_postings_by_ref_never_a_substring_of_a_label(client):
    _offer(client)
    state = get_runtime().store.get_state()
    ev = lambda kind, fen, ref, label: SimpleNamespace(kind=kind, amount_fen=fen, ref=ref, label=label)
    from app.domain.models import LedgerEventKind as K

    receipt = ev(K.RECEIPT, 42_000_000, "RCV-A", "Receipt RCV-A from BUYER-1")
    day = SimpleNamespace(events=[receipt, ev(K.REPAYMENT, -25_500_000, "FAC-IF", "Repay advance on RCV-A"),
                                  ev(K.REPAYMENT, -10_000_000, "FAC-LINE", "Repay line, with RCV-AB in the label")])
    text = home_hybrid.receipt_words(SimpleNamespace(state=state, lang="en"), day, receipt, "en")
    assert text == ("Foshan pays ¥420k, and ¥255k of it repays the invoice financing, leaving ¥165k. "
                    "¥100k of that repays the Bank credit line.")


def test_the_rail_holds_at_most_six_and_keeps_the_lowest_point(client, monkeypatch):
    h = _after(client)
    monkeypatch.setattr(home_hybrid, "MAX_RAIL", 3)
    rail = client.get("/home").json()["cash"]["events_rail"]
    assert len(rail) == 3 and "lowest" in [e["kind"] for e in rail]
    assert [e["day"] for e in rail] == sorted(e["day"] for e in rail)
    # the largest moves stay: the receipt (¥420k) and the payroll (¥340k), with the lowest point
    assert [e["day"] for e in rail] == [12, 30, 32] and len(h["cash"]["events_rail"]) == 5


def test_the_rail_stays_inside_the_picture_window(client):
    h = _after(client)
    end = h["day"] + h["cash"]["picture_days"]
    assert all(h["day"] <= e["day"] <= end for e in h["cash"]["events_rail"])


# ---------------------------------------------------------------- H3: the late-payment stress

try:
    from app.strategy.impact import stress as _stress_fn  # the exposure layer's stress; not on every branch
except ImportError:
    _stress_fn = None


def test_the_stress_is_omitted_when_the_exposure_flag_is_off(client):
    cash = _after(client)["cash"]
    assert cash["stress_available"] is False and "stress" not in cash


def test_the_stress_is_absent_not_broken_when_the_layer_lacks_it(client, monkeypatch, caplog):
    if _stress_fn is not None:
        pytest.skip("the exposure layer is present on this branch")
    monkeypatch.setattr(home_hybrid, "_exposure_on", lambda rt: True)
    cash = _after(client)["cash"]
    assert cash["stress_available"] is False and "stress" not in cash
    assert any("no late-payment stress" in r.getMessage() for r in caplog.records)  # the absence is said, not hidden


@pytest.mark.skipif(_stress_fn is None, reason="the exposure layer's stress is not on this branch")
def test_the_stress_reads_the_buyer_paying_thirty_days_late(client, monkeypatch):
    monkeypatch.setattr(home_hybrid, "_exposure_on", lambda rt: True)
    _offer(client)
    before = client.get("/home").json()["cash"]["stress"]
    # before the plan, Foshan paying 30 days late leaves cash below the minimum for weeks, and no committed plan covers it
    assert (before["delay_days"], before["buyer"]) == (30, "Foshan")
    assert before["breach_days"] > 0 and before["need_short"] != "¥0" and "No committed plan covers" in before["plan_text"]
    assert before["net_later_text"] == "about ¥420k, a month later"  # not financed yet: the whole invoice, a month later
    assert before["text"].startswith("Paid 30 days late: cash falls to −¥250,000") and before["funding_text"] == before["plan_text"]
    _run_plan(client)
    h = client.get("/home").json()
    s = h["cash"]["stress"]
    assert h["cash"]["stress_available"] is True
    assert s["series"] and {"day", "closing_fen", "closing_display"} <= set(s["series"][0])
    assert s["lowest_short"] == fmt_short(min(r["closing_fen"] for r in s["series"]))
    # once the invoice is financed its late receipt is modelled too (#107): the financing runs longer and its repayment
    # moves with the receipt, so the stress still breaches, and the assumption says so without naming an id
    assert s["breach_days"] > 0 and not s["plan_text"].startswith("Cash stays above your minimum")
    assert "runs 30 days longer" in s["assumption_text"] and "RCV-" not in s["assumption_text"]
    # the page widens its window to show the moved receipt: Foshan's day-32 receipt is paid on day 62
    assert s["window_days_needed"] >= 62 + 4 - h["day"]
    # the row's own sentences, so the Home and the Cash page say the same thing (ticket #116, item 5); `plan_text` stays as it was
    assert s["funding_text"] == s["plan_text"]
    assert s["text"] == ("Paid 30 days late: cash falls to ¥155,000 in 60 days, 15 days below your minimum; "
                         "no committed facility covers the ¥145,000.")
    assert s["net_later_text"] == "about ¥160k, a month later"
    zh = client.get("/home", params={"lang": "zh"}).json()["cash"]["stress"]
    assert zh["text"] == "晚付 30 天：60 天后现金将跌至 ¥155,000，有 15 天低于您的最低现金；您已承诺的融资额度无法弥补 ¥145,000 的缺口。"
    assert zh["funding_text"] == zh["plan_text"] and zh["funding_text"] != s["funding_text"]
    assert zh["net_later_text"] == "约 ¥160k，晚一个月收到"
    assert english_leaks({"stress": {k: zh[k] for k in ("text", "funding_text", "net_later_text")}}, ["Foshan Home Retail Co.", "FLOW"]) == []
    # one search per state: a second read of the same books takes the cached answer
    from app.strategy import impact

    calls = []
    real = impact.stress
    monkeypatch.setattr(impact, "stress", lambda *a, **k: calls.append(1) or real(*a, **k))
    client.get("/home")
    client.get("/home")
    assert calls == []


def test_the_net_later_has_no_text_without_an_open_invoice(client):
    rt = get_runtime()
    state = rt.store.get_state()
    c = SimpleNamespace(state=state.model_copy(update={"receivables": []}), today=0, lang="en")
    assert home_hybrid._net_later(c, "BUYER-1", 30) is None
    assert home_hybrid._net_later(SimpleNamespace(state=state, today=0, lang="zh"), "BUYER-1", 30) == "约 ¥420k，晚一个月收到"
    assert home_hybrid._net_later(SimpleNamespace(state=state, today=0, lang="en"), "BUYER-9", 30) is None


# ---------------------------------------------------------------- H4: the cards


def test_the_deals_card_is_one_row_per_deal_without_stages(client):
    row_before = _before(client)["deals_card"]["rows"]
    assert row_before == [{"buyer": "Foshan Home Retail Co.", "buyer_id": "BUYER-1", "status_text": "Your response needed",
                           "request_text": "60-day terms + 1% rebate + 1.2% off for early payment",
                           "recommendation_text": "Counter with Option A, estimated cost ¥3,027.77", "href": "/deals?buyer=BUYER-1"}]
    client.post("/demo/reset", json={})
    card = _after(client)["deals_card"]
    [row] = card["rows"]
    assert row["recommendation_text"] == "Counter with Option B, no estimated cost" and row["status_text"] == "Your response needed"
    assert "stages" not in row and card["href"] == "/deals"


def test_the_deals_card_is_empty_without_an_offer(client):
    card = client.get("/home").json()["deals_card"]
    assert card["rows"] == [] and card["empty_text"] == "No deals are open."


def test_the_receivables_card_says_what_the_receipt_will_do(client):
    before = _before(client)["receivables_card"]
    assert before == {"outstanding_short": "¥420k", "overdue_short": "¥0", "next_text": "Foshan, ¥420k in 32 days",
                      "financing_note": None, "href": "/receivables"}
    client.post("/demo/reset", json={})
    after = _after(client)["receivables_card"]
    assert after["outstanding_short"] == "¥420k" and after["next_text"] == "Foshan, ¥420k in 32 days"
    # the trajectory's events on the due day: ¥257k to the financing, ¥163k left of the receipt, ¥151k of that to the credit line
    # one claim, the same words as the rail's event for that day: ¥257k is the financing's principal and charges
    assert after["financing_note"] == ("Foshan pays ¥420k, and ¥257k of it repays the invoice financing, leaving ¥163k. "
                                       "¥151k of that repays the Bank credit line.")
    day32 = next(e for e in client.get("/home").json()["cash"]["events_rail"] if e["day"] == 32)
    assert day32["explain"].startswith(after["financing_note"])


def test_the_receivables_card_counts_what_is_late(client):
    _offer(client)
    _run_plan(client)
    client.post("/clock/advance", json={"to_day": 40})
    card = client.get("/home").json()["receivables_card"]
    assert (card["overdue_short"], card["outstanding_short"]) == ("¥420k", "¥1,260k")
    assert card["financing_note"] is None  # the next receipt has no advance on it


def test_the_changes_card_is_the_latest_sentences_the_home_already_words(client):
    h = _after(client)
    card = h["changes_card"]
    assert [r["text"] for r in card["rows"]] == [c["event_text"] for c in h["changes"] if not c["superseded_by"]][:3]
    assert 2 <= len(card["rows"]) <= 3 and card["href"] == "/activity"
    assert card["rows"][0]["text"].startswith("¥255,000.00 of invoice financing drawn against the Foshan Home Retail Co. invoice")


def test_the_changes_card_is_empty_when_nothing_changed(client):
    card = client.get("/home").json()["changes_card"]
    assert card["rows"] == [] and card["empty_text"] == "Nothing has changed lately."


# ---------------------------------------------------------------- both languages, and the home never falls for the hybrid

NEW = ["status_word", "status_tone", "headline_conditional", "headline_note", "assumptions", "facts", "events_rail", "counterfactual_series", "counterfactual_label"]


def _names() -> list[str]:
    state = get_runtime().store.get_state()
    flows = [part for x in state.flows for part in (x.label, x.label.split(",")[0], x.label.split(" (")[0])]
    shorts = [c.name.replace(",", " ").split()[0] for c in state.counterparties]  # the name an owner says aloud
    return [*(c.name for c in state.counterparties), *shorts, *(f.name for f in state.facilities), *flows]


@pytest.mark.parametrize("plan", [False, True])
def test_the_hybrid_reads_the_same_in_both_languages(client, plan):
    _offer(client)
    if plan:
        _run_plan(client)
    en, zh = client.get("/home").json(), client.get("/home", params={"lang": "zh"}).json()
    pick = {"cash": {k: en["cash"][k] for k in NEW}, **{k: en[k] for k in ("attention", "funding_line", "deals_card", "receivables_card", "changes_card")}}
    pick_zh = {"cash": {k: zh["cash"][k] for k in NEW}, **{k: zh[k] for k in pick if k != "cash"}}
    assert figures(en) == figures(zh)  # the same figures, ids, statuses and days
    assert unchanged_words(pick, pick_zh, _names(), AUDIT) == []
    assert english_leaks(pick_zh, _names(), AUDIT) == []
    assert english_leaks(zh, _names(), AUDIT) == []
    assert zh["cash"]["headline_conditional"] != en["cash"]["headline_conditional"] or not plan


def test_the_zh_hybrid_has_the_owners_voice(client):
    zh = _after(client) and client.get("/home", params={"lang": "zh"}).json()
    assert zh["cash"]["headline_conditional"] == "按当前方案，您的现金是安全的。"
    assert zh["attention"]["none_text"] == "没有需要紧急处理的事项。"
    assert zh["cash"]["facts"][0]["note"] == "比您的最低现金高 ¥250k"
    assert zh["attention"]["items"][0]["primary"]["label"] == "查看还价"


def test_a_deals_read_that_fails_is_a_partial_home_never_an_empty_one(client, monkeypatch, caplog):
    from app.api import deal_offers

    def boom(ctx, lang):
        raise RuntimeError("no")

    _offer(client)
    monkeypatch.setattr(deal_offers, "open_offers", boom)
    h = client.get("/home").json()
    assert h["attention"] is None and h["deals_card"] is None  # not "No deals are open", not "No urgent action required"
    assert h["partial"]["missing"] == ["summary"] and h["headline"]
    caplog.clear()


def test_an_unreadable_record_is_not_a_calm_queue(client, monkeypatch):
    from app.api import home as home_module

    _offer(client)

    def broken(*_a, **_k):
        raise RuntimeError("the decision record is unreadable")

    monkeypatch.setattr(home_module, "load_context", broken)
    h = client.get("/home").json()
    assert h["partial"]["missing"] == ["decision_record"]  # the home names it
    assert h["deals_card"] is None and h["attention"]["none_text"] is None and h["attention"]["incomplete"] is True
    assert [i["kind"] for i in h["attention"]["items"]] == ["funding"]  # what the books alone say still stands


def test_a_failing_hybrid_never_takes_the_home_down(client, monkeypatch, caplog):
    def boom(_c):
        raise RuntimeError("no")

    monkeypatch.setattr(home_hybrid, "build", boom)
    r = client.get("/home")
    assert r.status_code == 200
    h = r.json()
    assert h["attention"] is None and h["funding_line"] is None and h["partial"]["missing"] == ["summary"]
    assert "events_rail" not in h["cash"] and h["headline"]  # the conclusion stands
    caplog.clear()


def test_the_existing_fields_are_all_still_there(client):
    h = _after(client)
    for key in ("day", "state_version", "status", "status_text", "headline", "note", "worst", "plan_note", "cash", "next_action", "approvals",
                "open_decisions", "changes", "receivables", "warnings", "facilities", "counts", "partial"):
        assert key in h
    for key in ("series", "plan_series", "axis", "axes", "picture_days", "in_transit", "funding_lots", "lowest_short", "headroom_short"):
        assert key in h["cash"]
    assert h["receivables"]["open_total_display"] == "¥420,000.00" and h["receivables"]["open_total_fen"] == 42_000_000


# ---------------------------------------------------------------- ticket #111: the truth of the plan on the Home


def _rail_by_day(h: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {e["day"]: e for e in h["cash"]["events_rail"]}


def test_before_the_plan_runs_its_landings_are_planned_and_say_so(client):
    by = _rail_by_day(_before(client))
    assert (by[0]["kind"], by[0]["planned"], by[0]["label"]) == ("landing", True, "the Bank credit line draw would arrive, if you run the plan")
    assert (by[3]["kind"], by[3]["planned"], by[3]["label"]) == ("landing", True, "invoice financing would arrive, if you run the plan")
    assert not any(e["planned"] for d, e in by.items() if d not in (0, 3))


def test_after_the_plan_runs_the_executed_words_stand(client):
    by = _rail_by_day(_after(client))
    assert by[3]["label"] == "invoice financing arrives" and not any(e["planned"] for e in by.values())


def test_the_plan_lines_legend_is_a_question_until_the_operations_run(client):
    assert _before(client)["cash"]["plan_line_label"] == "If you run FLOW's plan"
    client.post("/demo/reset", json={})
    assert _after(client)["cash"]["plan_line_label"] == "With FLOW's plan"
    rt = get_runtime()
    client.post("/demo/reset", json={})
    rt.store.put_state(rt.store.get_state().model_copy(update={"cash_fen": 5_000_000_00}))
    assert "plan_line_label" not in client.get("/home").json()["cash"]  # no plan, nothing to name


@pytest.mark.parametrize("plan", [False, True])
def test_the_lowest_row_names_the_repayment_and_notes_the_low(client, plan):
    h = _after(client) if plan else _before(client)
    low = _rail_by_day(h)[30]
    assert (low["kind"], low["label"], low["amount_short"]) == ("lowest", "a loan repayment goes out", "−¥45k")
    assert low["note"] == "cash at its lowest, ¥300k, at your minimum"
    assert low["cash_after_short"] == "¥300k"  # the low is the note's figure; the amount is the repayment's
    assert all(e["note"] is None for e in h["cash"]["events_rail"] if e["kind"] != "lowest")


@pytest.mark.parametrize("plan", [False, True])
def test_every_rail_event_has_its_effect_table(client, plan):
    h = _after(client) if plan else _before(client)
    rows = _rail_by_day(h)[12]["effect_rows"]
    assert rows == [{"label": "Cash before", "display": "¥805k"}, {"label": "Cash after", "display": "¥465k"},
                    {"label": "Minimum reserve", "display": "¥300k"}, {"label": "Cash above reserve", "display": "¥165k"}]
    for e in h["cash"]["events_rail"]:  # the table is the paragraph's own figures
        assert e["effect_rows"][1]["display"] == e["cash_after_short"] and e["explain"]
    assert _rail_by_day(h)[30]["effect_rows"][3] == {"label": "Cash above reserve", "display": "¥0"}


def test_the_words_of_the_plan_in_chinese(client):
    _offer(client)
    zh = client.get("/home", params={"lang": "zh"}).json()
    by = _rail_by_day(zh)
    assert by[3]["label"] == "发票融资将到账，前提是您执行方案" and by[3]["planned"] is True
    assert by[30]["label"] == "一笔贷款还款支出" and by[30]["note"] == "现金降到最低，¥300k，正好是您的最低现金"
    assert zh["cash"]["plan_line_label"] == "如果您执行 FLOW 的方案"
    funding = zh["attention"]["items"][0]
    assert [f["value"] for f in funding["facts"][2:4]] == ["¥150k，今天（计划中）", "¥255k，3 天后（计划中）"]
    assert [r["label"] for r in by[12]["effect_rows"]] == ["此前现金", "此后现金", "最低现金储备", "高于储备的现金"]
    _run_plan(client)
    zh = client.get("/home", params={"lang": "zh"}).json()
    assert zh["cash"]["plan_line_label"] == "采用 FLOW 的方案"
    landing = next(i for i in zh["attention"]["items"] if i["kind"] == "landing")
    assert landing["facts"][0]["value"] == "¥255k，3 天后（已安排）"


# ---------------------------------------------------------------- ticket #111, review: legs, the cause of the low, counted landings, approval, partial runs


def _action(*legs):
    return {"kind": "RESERVE_BREACH_AHEAD", "alert_id": "A1", "receive_short": "¥405k", "cost_total_display": "¥10.00", "lands_when": "in 3 days",
            "needs_owner": False, "legs": list(legs)}


def _leg(kind, amount, when, facility="Bank credit line"):
    return {"operation_kind": kind, "facility_name": facility, "amount_fen": amount, "lands_when": when}


def test_only_the_legs_that_land_get_a_fact_and_authority_stays_last():
    c = SimpleNamespace(lang="en", headline="H.", action=_action(
        _leg("DRAW_FACILITY", 15_000_000, "today"), _leg("SUBMIT_INVOICE_FOR_FINANCING", 25_500_000, "in 3 days", "Invoice financing (x)"),
        _leg("APPLY_FOR_FACILITY", None, None, "Equipment lease"), _leg("REPAY_FACILITY", 5_000_000, None)))
    facts = home_hybrid._funding_item(c)["facts"]
    assert [(f["label"], f["value"]) for f in facts] == [
        ("Estimated cost", "¥10.00"), ("Funds arrive", "in 3 days"), ("Credit line draw", "¥150k today (planned)"),
        ("Invoice financing", "¥255k in 3 days (planned)"), ("Authority", "within your signed limits")]
    assert not any("None" in f["value"] or "¥0 " in f["value"] for f in facts)


def test_an_apply_and_a_repay_leg_alone_leave_the_plain_facts_only():
    c = SimpleNamespace(lang="en", headline="H.", action={**_action(_leg("APPLY_FOR_FACILITY", None, None), _leg("REPAY_FACILITY", 1, None)),
                                                          "lands_when": None})
    assert [f["label"] for f in home_hybrid._funding_item(c)["facts"]] == ["Estimated cost", "Authority"]


def test_the_lowest_row_names_the_largest_outflow_not_a_receipt_that_day():
    from app.domain.models import LedgerEventKind as K

    ev = lambda kind, fen, ref, label: SimpleNamespace(kind=kind, amount_fen=fen, ref=ref, label=label)
    day = [ev(K.RECEIPT, 42_000_000, "RCV-A", "Receipt"), ev(K.FLOW, -34_000_000, None, "Payroll"), ev(K.FLOW, -4_500_000, None, "Debt service"),
           ev(K.INTEREST, -90_000_000, "FAC-IF", "Interest")]
    assert home_hybrid._main_event(day).label == "Receipt"  # the other rows are named by their largest move
    assert home_hybrid._cause_event(day).label == "Payroll"  # the low is caused by an outflow; charges never name a day
    assert home_hybrid._cause_event([ev(K.DRAW, 5, "FAC-LINE", "D"), ev(K.ADVANCE, 9, "FAC-IF", "A")]).label == "A"  # no outflow: the largest


def _fake_read(line_events, base_events, lang="en"):
    state = get_runtime().store.get_state()
    day = lambda n, ev, op, cl: SimpleNamespace(day=n, opening_fen=op, closing_fen=cl, events=ev)
    line = SimpleNamespace(days=[day(0, [], 500, 500), day(3, line_events, 500, 700), day(5, [], 700, 650)])
    base = SimpleNamespace(days=[day(0, [], 500, 500), day(3, base_events, 500, 600), day(5, [], 600, 550)])
    return SimpleNamespace(state=state, lang=lang, today=0, picture_days=30, floor=300, plan_traj=line, traj=base, waiting=False), line


def test_two_identical_landings_are_counted_as_two():
    from app.domain.models import LedgerEventKind as K

    one = SimpleNamespace(kind=K.ADVANCE, amount_fen=100, ref="FAC-IF", label="Advance")
    c, line = _fake_read([one, one], [one])  # the books hold one such landing already; the plan adds the second
    row = next(e for e in home_hybrid._rail(c, line, None, "none") if e["day"] == 3)
    assert row["planned"] is True
    c, line = _fake_read([one, one], [one, one])  # the books hold both: nothing here is the plan's
    assert next(e for e in home_hybrid._rail(c, line, None, "none") if e["day"] == 3)["planned"] is False


def test_a_plan_waiting_on_approval_says_approve_not_run(client):
    from app.mandate.fixture import load_demo_owner_key
    from app.mandate.signing import sign

    rt = get_runtime()
    _offer(client)
    rt.store.put_mandate(sign(rt.store.get_mandate().model_copy(update={"max_apr_bp": 500}), load_demo_owner_key()["private_key_hex"]))
    a = client.get("/home").json()["next_action"]
    client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]})
    h = client.get("/home").json()
    assert h["next_action"]["pending_approval_id"] and h["cash"]["plan_line_label"] == "If you approve FLOW's plan"
    by = _rail_by_day(h)
    assert by[3]["label"] == "invoice financing would arrive, if you approve the plan" and by[3]["planned"] is True
    zh = client.get("/home", params={"lang": "zh"}).json()
    assert zh["cash"]["plan_line_label"] == "如果您批准 FLOW 的方案"
    assert _rail_by_day(zh)[3]["label"] == "发票融资将到账，前提是您批准方案"


def test_a_plan_run_in_part_plans_only_the_leg_that_has_not_run(client):
    _offer(client)
    rt = get_runtime()
    op = {"kind": "DRAW_FACILITY", "op_id": "d1", "idempotency_key": "d1", "mandate_version": rt.store.get_mandate().version,
          "requested_by": "AGENT", "facility_id": "FAC-LINE", "amount_fen": 15_000_000}
    assert client.post("/operations", json=op).json()["result"]["status"] == "EXECUTED"
    h = client.get("/home").json()
    by = _rail_by_day(h)
    assert 0 not in by  # the draw is in the cash already: no row says it would arrive
    assert (by[3]["planned"], by[3]["label"]) == (True, "invoice financing would arrive, if you run the plan")
    assert all(not e["planned"] for d, e in by.items() if d != 3)
    assert h["cash"]["plan_line_label"] == "If you run FLOW's plan"
    funding = h["attention"]["items"][0]
    assert [f["label"] for f in funding["facts"]] == ["Estimated cost", "Funds arrive", "Invoice financing", "Authority"]


def test_the_planned_state_is_only_a_legs_never_a_lots():
    from app.api.financing_words import state_of
    from app.domain.models import FundingLot

    lot = FundingLot(id="L", facility_id="F", principal_fen=10, remaining_fen=10, request_day=0, arrival_day=3)
    assert state_of(None, planned=True) == "PLANNED" and state_of(None) == "NONE"
    assert state_of(lot, planned=True) == "ARRANGED"  # a lot is arranged, received or repaid, whatever the caller says
    assert state_of(lot.model_copy(update={"settled": True}), planned=True) == "RECEIVED"
