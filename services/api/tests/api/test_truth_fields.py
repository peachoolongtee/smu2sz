"""The truth fields of the simplification (wayfinder #30): what a page needs to say when money moves and what an
option covers, without computing anything. Every figure here is one the engine already produces; the fields only
copy it where the page can read it: the day a leg becomes eligible and lands, the uncovered amount of an insufficient
option, the parts behind a counter's floored cost, the cash on the first breach day, the lowest point ahead of today,
and the business action behind a verdict code."""

from __future__ import annotations

from app.domain.fixtures import load_offers, load_scenario
from app.domain.models import FundingActionKind, LedgerEventKind, Mode
from app.financial import project
from tests.alerts.test_repay_alert import OWNER, approve_cure, to_day34
from tests.nl import conftest as nl_conftest
from tests.verifier.conftest import bundle

rt = nl_conftest.rt  # the in-memory runtime and the app client of the chat tests
client = nl_conftest.client

EX01 = "EX01_PACKAGE"


def _eval(client, fx: str) -> dict:
    oid = client.post("/offers", json={"fixture_id": fx}, headers=OWNER).json()["offer"]["offer_id"]
    return client.post(f"/offers/{oid}/evaluate", json={"fixture_id": fx}, headers=OWNER).json()


def _legs(plan: dict | None) -> list[dict]:
    return list((plan or {}).get("actions") or [])


# ---------------------------------------------------------------- eligibility and landing


def test_an_advance_on_an_unissued_invoice_is_shown_available_and_landing_on_the_engines_days(client, rt):
    v = _eval(client, EX01)
    plan = v["plan"]
    assert plan["executable_now"] is False and "issued on day 32" in plan["not_executable_reason"]
    [adv] = plan["actions"]
    # the engine submits the invoice on its issue day (32) and the cash lands after the 3-day lead time (35); the
    # cost ¥2,406.67 was always priced on those days (57 days to the due day 92): only the display stamp said 3
    assert adv["receivable_id"] == "RI:BUYER-1:32" and adv["day"] == 0
    assert adv["available_from_day"] == 32 and adv["lands_day"] == 35
    assert plan["available_from_day"] == 32 and plan["total_cost_display"] == "¥2,406.67"
    assert v["cure_plan"]["actions"][0]["lands_day"] == 35


def test_no_leg_is_ever_shown_requested_or_landing_before_it_is_eligible(client, rt):
    """The brief's display invariant, on every plan the verdict and the funding desk return."""
    v = _eval(client, EX01)
    plans = [v["plan"], v["cure_plan"], v["plan_committed"], v["plan_expected"]]
    desk = client.post("/router/plan", headers=OWNER).json()
    plans += [desk["committed"], desk["expected"]]
    rows = [*v["comparison"], *desk["comparison"]]
    legs = [a for p in plans for a in _legs(p)] + [a for r in rows for a in (r.get("actions") or [])]
    checked = 0
    for a in legs:
        if a["kind"] not in ("DRAW", "FINANCE_INVOICE") or a.get("lands_day") is None:
            continue
        assert a["available_from_day"] is not None and a["available_from_day"] >= a["day"], a
        assert a["lands_day"] >= a["available_from_day"], a
        checked += 1
    assert checked >= 3


def test_the_landing_stamp_agrees_with_the_engine_on_the_deals_cure(client):
    """`lands_day` is where the engine posts the ADVANCE when the cure runs on the books with the deal."""
    b = bundle(EX01)
    state, mandate = load_scenario()
    traj = project(state, list(b.bound_obligations), list(b.cure_plan.actions), Mode.CONSERVATIVE,
                   mandate.horizon_days, mandate.min_cash_fen)
    [adv] = b.cure_plan.actions
    assert adv.kind == FundingActionKind.FINANCE_INVOICE and adv.available_from_day == 32
    landed = {e.day for d in traj.days for e in d.events
              if e.kind == LedgerEventKind.ADVANCE and e.ref == adv.facility_id and e.amount_fen == adv.amount_fen}
    assert landed == {adv.lands_day} == {35}


# ---------------------------------------------------------------- option sufficiency


def test_comparison_rows_carry_a_status_and_what_an_insufficient_one_leaves_uncovered(client, rt):
    rows = {r["key"]: r for r in client.post("/router/plan", headers=OWNER).json()["comparison"]}
    assert rows["router_optimum"]["status"] == "recommended" and rows["router_optimum"]["shortfall_display"] is None
    for key in ("full_discount", "line_partial_early_pay"):
        assert rows[key]["status"] == "alternative" and rows[key]["reason_kind"] == "buyer_early_pay"
    line = rows["line_only"]
    assert line["status"] == "insufficient" and line["breach_day"] == 12
    assert line["shortfall_display"] == "¥255,000.00" and line["worst_day"] == 30
    ggl = rows["line_guaranteed_loan"]
    assert ggl["status"] == "unavailable" and ggl["shortfall_display"] is None and ggl["reason_kind"] is None
    assert "in 21 days" in ggl["note_when"] and "in 12 days" in ggl["note_when"] and "day 2" not in ggl["note_when"]
    assert "day 21" in ggl["note"]  # the engine's own note is unchanged
    # a plan that does not fully protect cash is never one of the ranked solutions
    assert all(r["status"] in ("recommended", "alternative") for r in rows.values() if r["result"] in ("SELECTED", "ADMISSIBLE"))
    assert all(r["status"] in ("insufficient", "unavailable") for r in rows.values() if r["result"] == "NOT_ADMISSIBLE")


def test_the_verdicts_comparison_rows_carry_the_same_status(client, rt):
    v = _eval(client, EX01)
    statuses = {r["key"]: r["status"] for r in v["comparison"]}
    assert statuses["router_optimum"] in ("recommended", "insufficient", "unavailable")
    assert set(statuses.values()) <= {"recommended", "alternative", "insufficient", "unavailable"}


# ---------------------------------------------------------------- gross versus net


def test_option_b_shows_the_parts_its_floored_cost_hides(client, rt):
    v = _eval(client, EX01)
    a, b = v["counters"]
    assert b["label"] == "Option B" and b["supplier_cost_display"] == "¥0.00"
    e = b["economics"]
    by_type = {c["type"]: c["value_fen"] for c in e["components"]}
    assert by_type["TERMS_EXTENSION"] == 1_621_795 and by_type["PRICE_ADJUSTMENT"] == -1_638_000
    assert e["funding_cost_display"] == "¥16,217.95" and e["offset_display"] == "¥16,380.00"
    assert e["net_fen"] == -16_205 and e["net_display"] == "−¥162.05" and e["is_net"] is True
    # Option A has no offsetting part: its figure is a plain cost, not a net
    assert a["economics"]["is_net"] is False and a["supplier_cost_display"] == "¥3,027.77"


# ---------------------------------------------------------------- first breach versus worst point


def test_the_trajectory_names_the_cash_on_the_first_breach_day(client, rt):
    v = _eval(client, EX01)
    tr = v["trajectory"]
    assert tr["first_breach_day"] == 47 and tr["first_breach_cash"]["text"] == "¥209,960.00"
    assert tr["min_cash_day"] == 60 and tr["min_cash"]["text"] == "¥164,960.00"


# ---------------------------------------------------------------- business action


def test_a_reject_with_counters_is_the_action_counter_and_without_is_decline(client, rt):
    v = _eval(client, EX01)
    assert v["outcome"] == "REJECT" and len(v["counters"]) == 2 and v["business_action"] == "counter"
    sec = next(k for k in load_offers() if "SEC" in k.upper() or "FASTCAPITAL" in k.upper())
    s = _eval(client, sec)
    assert s["outcome"] == "REJECT" and s["counters"] == [] and s["business_action"] == "decline"


# ---------------------------------------------------------------- the home: lowest point ahead, headroom, words


def test_the_home_reads_headroom_and_its_status_in_words(client, rt):
    h = client.get("/home", headers=OWNER).json()
    c = h["cash"]
    assert c["cash_short"] == "¥400k" and c["floor_short"] == "¥300k"
    assert c["headroom_short"] == "¥100k" and c["lowest_headroom_short"] == "−¥405k"
    assert h["status"] == "ACTION_NEEDED" and h["status_text"] == "Action needed"
    assert c["funding_lots"] == []


def test_after_the_day34_cure_the_lowest_point_ahead_is_today_not_34_days_ago(client, rt):
    to_day34(client, rt)
    [breach] = [a for a in client.get("/alerts", headers=OWNER).json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
    approve_cure(client, rt, breach["id"])
    h = client.get("/home", headers=OWNER).json()
    assert h["status"] == "WATCH" and h["headline"] == "You're covered."
    assert h["status_text"] == "Covered, but tight"
    assert h["worst"] == "Lowest cash ahead: ¥300k today." and h["cash"]["lowest_when"] == "today"
    assert h["cash"]["lowest_day"] == 34 and h["cash"]["lowest_headroom_short"] == "¥0.00"
    [lot] = [lot for lot in h["cash"]["funding_lots"] if not lot["landed"]]
    assert lot["amount_display"] == "¥200,000.00" and lot["arrival_when"] == "in 3 days"
    assert h["cash"]["in_transit"]["total_display"] == "¥200,000.00"
    zh = client.get("/home", params={"lang": "zh"}, headers=OWNER).json()
    assert zh["status_text"] == "安全，但余量不多" and "今天" in zh["worst"]
