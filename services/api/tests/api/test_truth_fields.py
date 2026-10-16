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
        if a["kind"] not in ("DRAW", "FINANCE_INVOICE"):
            continue
        # every comparison row carries the stamps now, so no leg is skipped for lacking them
        assert a["lands_day"] is not None and a["available_from_day"] is not None, a
        assert a["available_from_day"] >= a["day"], a
        assert a["lands_day"] >= a["available_from_day"], a
        checked += 1
    assert checked >= 6


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
    # the recorded verdict (mocks/verdict_ex01.json) has the router's pick as the one recommended row
    assert statuses["router_optimum"] == "recommended"
    assert statuses == {"full_discount": "alternative", "line_partial_early_pay": "alternative",
                        "router_optimum": "recommended", "line_guaranteed_loan": "unavailable", "line_only": "insufficient"}



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
    assert a["economics"]["is_net"] is False and a["supplier_cost_display"] == "¥3,035.99"


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


def test_the_headline_does_not_repeat_the_worst_point_when_the_first_breach_is_the_lowest(client, rt):
    assert client.get("/home", headers=OWNER).json()["worst"] is not None  # day 0: breach day 12, lowest day 30
    to_day34(client, rt)
    h = client.get("/home", headers=OWNER).json()
    assert h["cash"]["first_breach_day"] == h["cash"]["lowest_day"] and h["worst"] is None
    assert "in 8 days" in h["headline"]


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


def test_a_comparison_row_says_why_it_cannot_run_and_carries_its_landing_days(client, rt):
    rows = {r["key"]: r for r in client.post("/router/plan", headers=OWNER).json()["comparison"]}
    for key in ("full_discount", "line_partial_early_pay"):
        assert rows[key]["executable_now"] is False and rows[key]["not_executable_reason"], key
    for key in ("router_optimum", "line_only", "line_guaranteed_loan"):
        assert rows[key]["executable_now"] is True and rows[key]["not_executable_reason"] == "", key
    [draw, adv] = rows["router_optimum"]["actions"]
    assert draw["lands_day"] == 0 and adv["available_from_day"] == 0 and adv["lands_day"] == 3
    [_, loan] = rows["line_guaranteed_loan"]["actions"]
    assert loan["lands_day"] == 21 and loan["available_from_day"] == 0


# ---------------------------------------------------------------- the status of every outcome


def test_comparison_status_names_every_outcome():
    from app.api.presentation import comparison_status as status
    assert status("SELECTED", [], None) == "recommended"
    assert status("ADMISSIBLE", [], None) == "alternative"
    assert status("NOT_ADMISSIBLE", ["RESERVE_BREACH"], 12) == "insufficient"
    assert status("NOT_ADMISSIBLE", [], 12) == "insufficient"  # a breach day alone is enough
    assert status("NOT_ADMISSIBLE", ["UNCOMMITTED_FACILITY", "LEAD_TIME_TOO_LONG"], None) == "unavailable"
    assert status("NOT_ADMISSIBLE", ["LEAD_TIME_TOO_LONG"], None) == "unavailable"
    # anything else (a covenant, the borrowing switch, the rate ceiling) breaks one of the owner's limits
    assert status("NOT_ADMISSIBLE", ["DSCR_BREACH"], None) == "blocked"
    assert status("NOT_ADMISSIBLE", [], None) == "blocked"


def test_comparison_reason_says_the_buyer_or_the_invoice():
    from app.api.presentation import comparison_reason as reason
    assert reason([{"kind": "EARLY_PAY"}], False) == "buyer_early_pay"
    assert reason([{"kind": "DRAW"}, {"kind": "EARLY_PAY"}], False) == "buyer_early_pay"
    assert reason([{"kind": "FINANCE_INVOICE", "day": 0, "available_from_day": 32}], False) == "invoice_not_issued"
    assert reason([{"kind": "FINANCE_INVOICE", "day": 0, "available_from_day": 0}], False) is None
    assert reason([{"kind": "EARLY_PAY"}], True) is None  # a row that can run today has no reason


def test_business_action_for_every_outcome():
    from app.api.presentation import business_action as action
    assert action("ACCEPT", 0) == "accept"
    assert action("COUNTER", 1) == "counter" and action("REJECT", 2) == "counter"
    assert action("REJECT", 0) == "decline"
    assert action("NEEDS_OWNER_APPROVAL", 0) == "needs_owner"
    assert action("NO_VERDICT", 0) == "cannot" and action("NO_DEAL", 0) == "cannot"


def test_counter_economics_has_no_figure_when_no_committed_source_prices_concessions():
    from app.api.presentation import counter_economics
    from app.domain.models import FacilityStatus
    from app.mandate import load_signed_mandate
    b = bundle(EX01)
    state, _ = load_scenario()
    mandate = load_signed_mandate()
    counter = b.verdict.counters[0]
    assert counter_economics(list(counter.obligations), state, mandate) is not None
    uncommitted = state.model_copy(update={"facilities": [f.model_copy(update={"status": FacilityStatus.NOT_APPLIED})
                                                           for f in state.facilities]})
    assert counter_economics(list(counter.obligations), uncommitted, mandate) is None


def test_net_words_say_about_zero_when_the_offset_covers_the_cost(client, rt):
    from app.api.presentation import counter_economics
    from app.domain.models import ObligationType
    from app.mandate import load_signed_mandate
    a, b = _eval(client, EX01)["counters"]
    assert b["economics"]["net_fen"] < 0 and b["economics"]["net_words"] == "≈ ¥0"
    assert a["economics"]["net_fen"] == 0 and a["economics"]["net_words"] == "≈ ¥0"
    # a net that is a cost is said as the figure (the extension without its offset)
    state, _ = load_scenario()
    ext = [o for o in bundle(EX01).bound_obligations if o.type == ObligationType.TERMS_EXTENSION]
    e = counter_economics(ext, state, load_signed_mandate())
    assert e is not None and e["net_fen"] > 0 and e["net_words"] == e["net_display"] == "¥24,326.92"



# ---------------------------------------------------------------- the home's words


def test_the_status_text_for_every_band():
    from types import SimpleNamespace

    from app.alerts import AlertKind
    from app.api.home import _status_text as text
    tight = [SimpleNamespace(kind=AlertKind.RESERVE_HEADROOM_LOW)]
    other = [SimpleNamespace(kind=AlertKind.RECEIVABLE_PAST_DUE)]
    assert text("SAFE", [], "en") == "Covered" and text("SAFE", [], "zh") == "安全"
    assert text("WATCH", tight, "en") == "Covered, but tight" and text("WATCH", tight, "zh") == "安全，但余量不多"
    assert text("WATCH", other, "en") == "Covered, with warnings" and text("WATCH", [], "zh") == "安全，但有提醒"
    assert text("ACTION_NEEDED", [], "en") == "Action needed"
    assert text("CRITICAL", [], "en") == "Critical"


def test_chart_annotations_use_the_last_from_and_short_words_per_kind():
    from app.api.home import _label_short as short
    assert short("ADVANCE", "Advance ¥255,000.00 on X from Invoice financing", "en") == "Invoice financing lands"
    assert short("ADVANCE", "x", "zh") == "发票融资到账"
    assert short("DRAW", "Draw from Bank credit line", "en") == "Credit line draw"
    assert short("RECEIPT", "Receipt the ¥420,000.00 invoice from Foshan Home Retail Co.", "en") == "Receipt from Foshan Home Retail Co."
    # a party name that itself contains " from " keeps its whole name: the last " from " is the one that introduces it
    assert short("RECEIPT", "Receipt the ¥1.00 invoice from Sourced from Asia Ltd", "en") == "Receipt from Asia Ltd"
    assert short("RECEIPT", "Receipt", "en") == "Receipt" and short("EARLY_RECEIPT", "x", "zh") == "收款"
    assert short("FLOW", "Payroll (monthly), day 12", "en") == "Payroll"
    assert short("FLOW", "Supplier payment from stock", "en") == "Supplier payment from stock"  # no kind rule: the label itself


def test_the_lowest_point_ahead_falls_back_to_every_day_when_today_is_past_the_last():
    from types import SimpleNamespace

    from app.api.home import _lowest_ahead
    days = [SimpleNamespace(day=d, closing_fen=c) for d, c in [(0, 300), (1, 100), (2, 50), (3, 200)]]
    traj = SimpleNamespace(days=days)
    assert _lowest_ahead(traj, 2) == (50, 2)
    assert _lowest_ahead(traj, 3) == (200, 3)  # only today and later count
    assert _lowest_ahead(traj, 9) == (50, 2)  # today beyond the last day: the whole series


# ---------------------------------------------------------------- no runnable fix: the home says so


def test_a_critical_breach_with_no_runnable_fix_has_no_next_action_but_still_a_first_breach(client, rt):
    state, _ = load_scenario()
    rt.store.put_state(state.model_copy(update={"facilities": [
        f.model_copy(update={"drawn_fen": f.limit_fen}) if f.id in ("FAC-LINE", "FAC-IF") else
        f.model_copy(update={"owner_approved": False}) if f.status.value != "COMMITTED" else f
        for f in state.facilities]}))
    h = client.get("/home", headers=OWNER).json()
    # the Cash page must not say "no additional funding is needed" here: a breach is ahead and nothing can be run
    assert h["status"] == "CRITICAL" and h["next_action"] is None
    assert h["cash"]["first_breach_day"] == 12 and h["headline"] == "Your cash reserve becomes unsafe in 12 days."
    assert [f["drawn_fen"] for f in h["facilities"] if f["id"] in ("FAC-LINE", "FAC-IF")] == [15_000_000, 35_000_000]


def test_the_homes_facilities_and_lots_say_what_is_drawn_and_what_is_an_opening_balance(client, rt):
    h = client.get("/home", headers=OWNER).json()
    assert all(f["drawn_fen"] == 0 for f in h["facilities"])
    to_day34(client, rt)
    [breach] = [a for a in client.get("/alerts", headers=OWNER).json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
    approve_cure(client, rt, breach["id"])
    h = client.get("/home", headers=OWNER).json()
    assert sum(f["drawn_fen"] for f in h["facilities"]) > 0
    assert all(lot["opening"] is False for lot in h["cash"]["funding_lots"])
    # a balance older than the books is an opening balance, not funding received today
    state = rt.store.get_state()
    lots = [lot.model_copy(update={"assumed_date": True}) for lot in state.lots]
    rt.store.put_state(state.model_copy(update={"lots": lots}))
    h = client.get("/home", headers=OWNER).json()
    assert h["cash"]["funding_lots"] and all(lot["opening"] is True for lot in h["cash"]["funding_lots"])
