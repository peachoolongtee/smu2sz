"""The offer picture's authority and costs: who decides for each path, from the verifier and the funding plan; one cost basis; and
"over a limit you signed" only on a cap violation."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest

from app.api import offer_picture
from app.api.decisions import latest_verdict_for
from app.api.runtime import get_runtime
from app.domain.models import Outcome, Tier, Violation, ViolationCode
from tests.api.test_offer_picture import _accepted, _evaluated

OVER = "Over a limit you signed: only a new mandate changes that"
NEEDS = "Needs your approval"
MAY = "FLOW can send it"
OLD_OVER = "Cannot be accepted within your signed limits."


@pytest.fixture(autouse=True)
def _fresh_cache():
    """The picture is cached per state version and verdict; a test that changes what it reads must not leave its picture behind."""
    offer_picture._cache.clear()
    yield
    offer_picture._cache.clear()


def _paths(client, oid, lang="en"):
    return client.get(f"/offers/{oid}/picture", params={"lang": lang}).json()["paths"]


def _authority(p):
    return p["authority"], p["authority_text"]


# ---------------------------------------------------------------- Task 1: who decides follows the verifier and the plan


def test_each_path_says_who_decides_in_three_classes_in_both_languages(client):
    oid, _ = _evaluated(client)
    asked, opt_a, opt_b = _paths(client, oid)
    assert _authority(asked) == ("over_limit", OVER) and _authority(opt_a) == ("flow_may", MAY) and _authority(opt_b) == ("needs_owner", NEEDS)
    z_asked, z_a, z_b = _paths(client, oid, "zh")
    assert [p["authority_text"] for p in (z_asked, z_a, z_b)] == ["超出您签署的上限：只有签署新的授权才能改变", "FLOW 可以直接发送", "需要您批准"]
    assert [p["authority"] for p in (z_asked, z_a, z_b)] == ["over_limit", "flow_may", "needs_owner"]
    # the old sentences the page of `dev` reads are kept
    assert asked["decides_text"] == OLD_OVER and opt_a["decides_text"] == "FLOW can send it. Your approval is not needed."
    assert opt_b["decides_text"] == "It changes your terms, so you approve it first."


def test_an_early_payment_on_a_named_invoice_within_the_threshold_is_flow_may(client):
    oid, _ = _accepted(client)
    (asked,) = _paths(client, oid)
    assert _authority(asked) == ("flow_may", MAY) and asked["needs_owner"] is False


def test_a_reply_whose_funding_plan_needs_the_owner_reads_needs_owner(client, monkeypatch):
    oid, _ = _evaluated(client)
    real = offer_picture.plan
    monkeypatch.setattr(offer_picture, "plan", lambda *a, **k: real(*a, **k).model_copy(update={"needs_owner_approval": True}))
    offer_picture._cache.clear()
    asked, opt_a, opt_b = _paths(client, oid)
    assert _authority(opt_a) == ("needs_owner", NEEDS) and opt_a["needs_owner"] is True
    assert _authority(opt_b) == ("needs_owner", NEEDS) and _authority(asked)[0] == "over_limit"
    assert opt_a["decides_text"] == "It is above what FLOW may agree alone, so you approve it first."
    # and the parting moment says it
    parting = next(m for m in client.get(f"/offers/{oid}/picture").json()["moments"] if "paths_part" in m["kinds"])
    assert "Option A: needs your approval; Option B: needs your approval." in parting["text"]


def test_a_past_due_buyer_makes_the_verifier_ask_for_the_owner(client, monkeypatch):
    oid, _ = _evaluated(client)
    evaluate = importlib.import_module("app.verifier.evaluate")  # the package re-exports a function of the same name
    monkeypatch.setattr(evaluate, "_buyer_past_due", lambda *a, **k: [("RCV-A", 3, 25_720_000)])
    offer_picture._cache.clear()
    _, opt_a, opt_b = _paths(client, oid)
    assert _authority(opt_a) == ("needs_owner", NEEDS) and opt_a["needs_owner"] is True and _authority(opt_b)[0] == "needs_owner"


def test_the_verifiers_tier_decides_a_reply_the_route_would_have_sent(client, monkeypatch):
    """The verifier's re-check can ask for the owner where the executor's rule alone would not (autonomy, past due): that wins."""
    oid, _ = _evaluated(client)
    real = offer_picture.counter_recheck

    def recheck(*a, **k):
        check = real(*a, **k)
        return lambda c: check(c).model_copy(update={"outcome": Outcome.NEEDS_OWNER_APPROVAL, "required_tier": Tier.TIER_2})

    monkeypatch.setattr(offer_picture, "counter_recheck", recheck)
    offer_picture._cache.clear()
    assert [p["authority"] for p in _paths(client, oid)[1:]] == ["needs_owner", "needs_owner"]


# ---------------------------------------------------------------- Task 2: one cost basis across the three paths


def test_every_path_states_its_cost_on_a_basis_and_option_b_carries_its_components(client):
    oid, view = _evaluated(client)
    asked, opt_a, opt_b = _paths(client, oid)
    impact = view["workspace"]["financial_impact"]
    # the offer as asked has both parts: no total, the two kernel figures side by side, never added
    assert asked["cost_total_display"] is None and asked["cost_basis_text"] == "two parts: once, and over 12 months"
    assert asked["cost_forward_display"] == impact["forward_total_display"] == view["forward_concession"]["total_display"] == "¥28,326.92"
    assert asked["cost_once_display"] == "¥5,040.00" and asked["cost_components"] == []
    assert asked["cost_display"] == "¥28,326.92" and asked["cost_note"] == "over 12 months, plus ¥5,040.00 once"
    assert (opt_a["cost_total_display"], opt_a["cost_basis_text"]) == ("¥3,027.77", "once, nothing ongoing")
    assert opt_a["cost_once_display"] == "¥3,027.77" and opt_a["cost_forward_display"] is None and opt_a["cost_components"] == []
    # option B nets to zero: the funding cost of the longer terms and the price offset the `dev` page showed, never a bare ¥0.00
    economics = view["counters"][1]["economics"]
    assert economics["funding_cost_display"] == "¥16,217.95" and economics["offset_display"] == "¥16,380.00"
    assert opt_b["cost_display"] == "¥0.00" and opt_b["cost_basis_text"] == "net over 12 months"
    assert opt_b["cost_components"] == [{"label": "Funding cost of the longer terms", "display": economics["funding_cost_display"]},
                                        {"label": "Offset by the 0.30% price rise", "display": economics["offset_display"]},
                                        # the router's plan that funds the shortfall on these terms: beside the net, which the verifier does not add it to
                                        {"label": "Funding plan for the shortfall (not in the net)", "display": "¥3,706.46"}]
    assert "cost ¥3,706.46" in view["counters"][1]["formula"] and opt_b["cost_total_display"] == "¥0.00"
    zh = _paths(client, oid, "zh")[2]
    assert [c["display"] for c in zh["cost_components"]] == ["¥16,217.95", "¥16,380.00", "¥3,706.46"]
    assert [c["label"] for c in zh["cost_components"]] != [c["label"] for c in opt_b["cost_components"]]
    assert zh["cost_basis_text"] != opt_b["cost_basis_text"]


def test_a_reply_with_a_one_off_and_a_twelve_month_cost_states_both_without_adding_them(client):
    rt = get_runtime()
    c = SimpleNamespace(supplier_cost_fen=504_000, forward_value_fen=2_832_692, obligations=[])
    cost = offer_picture._reply_cost(c, rt.store.get_state(), rt.store.get_mandate(), 12, "en")
    assert cost["cost_basis_text"] == "two parts: once, and over 12 months"
    assert (cost["cost_once_display"], cost["cost_forward_display"], cost["cost_total_display"]) == ("¥5,040.00", "¥28,326.92", None)
    zh = offer_picture._reply_cost(c, rt.store.get_state(), rt.store.get_mandate(), 12, "zh")
    assert zh["cost_basis_text"] == "两部分：一次性，以及 12 个月内" and zh["cost_total_display"] is None
    only = {"once": SimpleNamespace(supplier_cost_fen=504_000, forward_value_fen=0, obligations=[]),
            "forward": SimpleNamespace(supplier_cost_fen=0, forward_value_fen=2_832_692, obligations=[])}
    one = offer_picture._reply_cost(only["once"], rt.store.get_state(), rt.store.get_mandate(), 12, "en")
    assert (one["cost_total_display"], one["cost_basis_text"]) == ("¥5,040.00", "once, nothing ongoing")
    two = offer_picture._reply_cost(only["forward"], rt.store.get_state(), rt.store.get_mandate(), 12, "en")
    assert (two["cost_total_display"], two["cost_basis_text"]) == ("¥28,326.92", "over 12 months")


# ---------------------------------------------------------------- Task 3: "over your limit" only on a cap violation


def _with_verdict(client, monkeypatch, oid, **update: Any):
    verdict = latest_verdict_for(get_runtime(), oid)
    assert verdict is not None
    edited = verdict.model_copy(update={"id": "VER-edited", **update})
    monkeypatch.setattr(offer_picture, "latest_verdict_for", lambda rt, offer_id: edited)
    offer_picture._cache.clear()
    return _paths(client, oid)


def _violation(code: ViolationCode) -> Violation:
    return Violation(code=code, message="m")


def test_a_cap_violation_reads_over_limit_with_the_new_mandate_sentence(client, monkeypatch):
    oid, _ = _evaluated(client)
    for code in (ViolationCode.AGG_CONCESSION_EXCEEDED, ViolationCode.PER_BUYER_CAP_EXCEEDED):
        asked = _with_verdict(client, monkeypatch, oid, violations=[_violation(code)], outcome=Outcome.REJECT, counters=[])[0]
        assert _authority(asked) == ("over_limit", OVER) and asked["decides_text"] == OLD_OVER and asked["tag_text"] == "Over your limit"
        assert asked["sendable"] is False


def test_no_verdict_asks_for_one_more_fact_and_is_not_a_mandate_breach(client, monkeypatch):
    oid, _ = _evaluated(client)
    (asked,) = _with_verdict(client, monkeypatch, oid, outcome=Outcome.NO_VERDICT, violations=[], counters=[])
    assert asked["authority"] is None and asked["authority_text"] == "FLOW needs one more fact before it can price this"
    assert asked["decides_text"] == asked["authority_text"] and asked["tag_text"] is None and asked["sendable"] is False
    assert client.get(f"/offers/{oid}/picture", params={"lang": "zh"}).json()["paths"][0]["authority_text"] == "FLOW 还需要再确认一个事实才能为此定价"


def test_no_deal_and_a_security_reject_read_their_own_sentences(client, monkeypatch):
    oid, _ = _evaluated(client)
    (no_deal,) = _with_verdict(client, monkeypatch, oid, outcome=Outcome.NO_DEAL, violations=[], counters=[])
    assert no_deal["authority"] is None and no_deal["authority_text"] == "There is no deal to send: it ended without an agreement"
    (secure,) = _with_verdict(client, monkeypatch, oid, outcome=Outcome.REJECT, counters=[],
                              violations=[_violation(ViolationCode.DATA_EXTRACTION_REFUSED)])
    assert secure["authority"] is None and secure["authority_text"] == "FLOW will not act on this: the message failed its security checks"
    for p in (no_deal, secure):
        assert OLD_OVER not in p["decides_text"] and p["tag_text"] is None and "mandate" not in p["authority_text"]


def test_a_counter_from_an_owner_goal_breach_reads_flow_counters_instead(client, monkeypatch):
    oid, _ = _evaluated(client)
    asked = _with_verdict(client, monkeypatch, oid, outcome=Outcome.COUNTER, violations=[], required_tier=Tier.TIER_1)[0]
    assert _authority(asked) == (None, "FLOW counters instead") and asked["decides_text"] == "FLOW counters instead"
    assert asked["tag_text"] is None and asked["sendable"] is False
    asked = _with_verdict(client, monkeypatch, oid, outcome=Outcome.COUNTER, violations=[], required_tier=Tier.TIER_2)[0]
    assert _authority(asked) == (None, "FLOW counters instead")  # the offer as asked is not sent: the replies carry the authority
    z = client.get(f"/offers/{oid}/picture", params={"lang": "zh"}).json()["paths"][0]
    assert z["authority_text"] == "FLOW 改为还价"


def test_a_hard_reject_with_no_counter_is_not_called_a_mandate_breach(client, monkeypatch):
    oid, _ = _evaluated(client)
    (asked,) = _with_verdict(client, monkeypatch, oid, outcome=Outcome.REJECT, counters=[], violations=[_violation(ViolationCode.RESERVE_BREACH)])
    assert asked["authority"] is None and asked["authority_text"] == "FLOW cannot accept this as asked" and OLD_OVER not in asked["decides_text"]


@pytest.mark.parametrize("outcome", [Outcome.NEEDS_OWNER_APPROVAL, Outcome.ACCEPT])
def test_an_accepted_asked_path_follows_the_tier_and_the_plan_flag(client, monkeypatch, outcome):
    oid, _ = _evaluated(client)
    tier = Tier.TIER_2 if outcome == Outcome.NEEDS_OWNER_APPROVAL else Tier.TIER_1
    (asked,) = _with_verdict(client, monkeypatch, oid, outcome=outcome, violations=[], counters=[], required_tier=tier)
    assert asked["authority"] == ("needs_owner" if outcome == Outcome.NEEDS_OWNER_APPROVAL else "flow_may")
    plan = latest_verdict_for(get_runtime(), oid).plan  # type: ignore[union-attr]
    flagged = (plan.model_copy(update={"needs_owner_approval": True}) if plan is not None else None)
    if flagged is not None:
        (asked,) = _with_verdict(client, monkeypatch, oid, outcome=Outcome.ACCEPT, violations=[], counters=[], required_tier=Tier.TIER_1,
                                 plan=flagged)
        assert asked["authority"] == "needs_owner" and asked["needs_owner"] is True


# ---------------------------------------------------------------- Task 6: follow-ups


def test_a_reply_that_still_dips_below_the_minimum_says_so_not_how_soon_the_invoice_is_paid(client, monkeypatch):
    oid, _ = _evaluated(client)
    real = offer_picture.first_breach_ahead
    calls: list[int] = []

    def breach(traj, today, floor):
        calls.append(1)
        return real(traj, today, floor) if len(calls) == 1 else (30, 0)  # the first call is the offer as asked; then each reply (day 30)

    monkeypatch.setattr(offer_picture, "first_breach_ahead", breach)
    offer_picture._cache.clear()
    _, opt_a, opt_b = _paths(client, oid)
    for p in (opt_a, opt_b):
        assert p["band_text"] == "Below your minimum for 1 day" and "sooner" not in p["band_text"] and p["first_breach_when"] == "in 30 days"


def test_an_unprojectable_reply_is_said_plainly_and_never_recommended(client, monkeypatch):
    oid, _ = _evaluated(client)

    def project(*a, **k):  # the offer as asked is projected by the decision record's own rule (it is drawable); every reply's projection fails
        raise offer_picture.EngineError("no")

    monkeypatch.setattr(offer_picture, "project", project)
    offer_picture._cache.clear()
    pic = client.get(f"/offers/{oid}/picture").json()
    _, opt_a, opt_b = pic["paths"]
    for p in (opt_a, opt_b):
        assert p["series"] is None and p["sendable"] is False and p["recommended"] is False and p["tag_text"] is None
        assert p["authority"] is None and p["authority_text"] == "FLOW cannot draw this reply on today's books"
        assert p["decides_text"] == p["authority_text"] and "limits" not in p["decides_text"] and p["band_text"] is None
        assert p["needs_owner"] is False
    assert all(len(m["values"]) == 1 for m in pic["moments"])
    zh = client.get(f"/offers/{oid}/picture", params={"lang": "zh"}).json()["paths"][1]
    assert zh["authority_text"] == "FLOW 无法按今天的账目绘制此回复"


def test_a_rate_keeps_its_sign_and_a_price_cut_is_said_once(client):
    assert offer_picture._pct(-30) == "-0.30%" and offer_picture._pct(30) == "0.30%" and offer_picture._pct(None) == "?"
    assert offer_picture._pct(-30, absolute=True) == "0.30%"
    state = get_runtime().store.get_state()
    from app.domain.models import ObligationType

    cut = SimpleNamespace(type=ObligationType.PRICE_ADJUSTMENT, rate_bp=-30)
    assert offer_picture._term_rows(state, [cut], None, "en")["rebate_or_price"] == ("0.30% price cut", "a 0.30% price cut")


def test_every_reply_carries_the_assumption_beside_its_figures(client):
    oid, _ = _evaluated(client)
    asked, opt_a, opt_b = _paths(client, oid)
    assert asked["assumption_text"] is None
    assert opt_a["assumption_text"] == opt_b["assumption_text"] == "If the buyer accepts this reply"
    z = _paths(client, oid, "zh")
    assert z[1]["assumption_text"] == "如果买方接受此回复" and z[0]["assumption_text"] is None
    # the replies' own notes are kept as they were
    assert all(r["note"] for r in client.get(f"/offers/{oid}/picture").json()["replies"])


# ---------------------------------------------------------------- a reply the re-check does not clear is not sendable, recommended or owner-approved


def _recheck_as(monkeypatch, **update: Any):
    real = offer_picture.counter_recheck

    def recheck(*a, **k):
        check = real(*a, **k)
        return lambda c: check(c).model_copy(update=update)

    monkeypatch.setattr(offer_picture, "counter_recheck", recheck)
    offer_picture._cache.clear()


@pytest.mark.parametrize("update, authority, text", [
    ({"outcome": Outcome.NO_VERDICT, "violations": []}, None, "FLOW needs one more fact before it can price this"),
    ({"outcome": Outcome.REJECT, "violations": []}, None, "FLOW cannot send this reply as it stands"),
    ({"outcome": Outcome.COUNTER, "violations": []}, None, "FLOW cannot send this reply as it stands"),
    ({"outcome": Outcome.REJECT, "violations": [_violation(ViolationCode.AGG_CONCESSION_EXCEEDED)]}, "over_limit", OVER),
    ({"outcome": Outcome.REJECT, "violations": [_violation(ViolationCode.PER_BUYER_CAP_EXCEEDED)]}, "over_limit", OVER),
])
def test_a_reply_the_recheck_does_not_clear_is_never_sendable_recommended_or_owner_approved(client, monkeypatch, update, authority, text):
    oid, _ = _evaluated(client)
    _recheck_as(monkeypatch, **update)
    _, opt_a, opt_b = _paths(client, oid)
    for p in (opt_a, opt_b):
        assert (p["authority"], p["authority_text"]) == (authority, text)
        assert p["sendable"] is False and p["recommended"] is False and p["needs_owner"] is False
        assert p["tag_text"] in (None, "Over your limit") and p["tag_text"] != "FLOW recommends" and p["tag_text"] != "Needs your approval"


def test_the_recommendation_falls_to_the_next_reply_that_can_be_sent(client, monkeypatch):
    oid, view = _evaluated(client)
    first = view["counters"][0]["id"]
    real = offer_picture.counter_recheck

    def recheck(*a, **k):
        check = real(*a, **k)
        return lambda c: check(c).model_copy(update={"outcome": Outcome.NO_VERDICT}) if c.id == first else check(c)

    monkeypatch.setattr(offer_picture, "counter_recheck", recheck)
    offer_picture._cache.clear()
    _, opt_a, opt_b = _paths(client, oid)
    assert (opt_a["sendable"], opt_a["recommended"]) == (False, False)
    assert (opt_b["sendable"], opt_b["recommended"], opt_b["tag_text"]) == (True, True, "FLOW recommends")
    assert opt_b["authority"] == "needs_owner" and opt_b["needs_owner"] is True


def test_a_recheck_that_raises_reads_as_no_verdict(client, monkeypatch):
    oid, _ = _evaluated(client)
    real = offer_picture.counter_recheck

    def recheck(*a, **k):
        real(*a, **k)

        def boom(c):
            raise RuntimeError("the re-check failed")

        return boom

    monkeypatch.setattr(offer_picture, "counter_recheck", recheck)
    offer_picture._cache.clear()
    r = client.get(f"/offers/{oid}/picture")
    assert r.status_code == 200
    _, opt_a, opt_b = r.json()["paths"]
    for p in (opt_a, opt_b):
        assert p["authority"] is None and p["sendable"] is False and p["recommended"] is False and p["needs_owner"] is False
        assert p["authority_text"] == "FLOW needs one more fact before it can price this"


# ---------------------------------------------------------------- the evidence behind `decides_text`


def test_each_path_carries_the_evidence_behind_who_decides_in_both_languages(client):
    oid, _ = _evaluated(client)
    asked, opt_a, opt_b = _paths(client, oid)
    assert asked["authority_reason_text"] is None  # the asked path is over a limit: nothing to list
    assert opt_a["authority_reason_text"] == ("Terms stay at 45 days, no rebate. "
                                              "The early-settlement offer at 0.85% is within the 1.50% limit you signed.")
    assert opt_b["authority_reason_text"] == ("Payment terms 45 → 55 days. Price on future invoices +0.30%. "
                                              "Your mandate lets FLOW send a counter on its own only when the terms stay as they are.")
    z_asked, z_a, z_b = _paths(client, oid, "zh")
    assert z_asked["authority_reason_text"] is None
    assert z_a["authority_reason_text"] == "账期保持 45 天，无返利。0.85% 的提前结算方案在您签署的 1.50% 上限之内。"
    assert z_b["authority_reason_text"] == "账期 45 → 55 天。今后发票的价格 +0.30%。您的授权只允许 FLOW 在条款保持不变时自行发送还价。"


def test_the_evidence_figures_are_the_terms_columns_own(client):
    oid, _ = _evaluated(client)
    _, opt_a, opt_b = _paths(client, oid)
    terms = {t["key"]: t for t in opt_b["terms"]}
    assert terms["payment_terms"]["value_text"] == "55 days" and terms["payment_terms"]["instead_of_text"] == "instead of 60"
    assert "45 → 55 days" in opt_b["authority_reason_text"] and terms["rebate_or_price"]["value_text"] == "0.30% price rise"
    assert "0.30%" in opt_b["authority_reason_text"] and "0.85% off" in {t["key"]: t for t in opt_a["terms"]}["early_payment"]["value_text"]
    assert "0.85%" in opt_a["authority_reason_text"] and "45 days" in {t["key"]: t for t in opt_a["terms"]}["payment_terms"]["value_text"]


def test_the_rule_it_crosses_follows_the_rule_the_mandate_applied():
    from app.domain.models import Tier

    assert offer_picture._owner_rule(True, False, Tier.TIER_2, False) == "terms"
    assert offer_picture._owner_rule(False, False, Tier.TIER_2, False) == "beyond_early_pay"
    assert offer_picture._owner_rule(False, True, Tier.TIER_2, True) == "value"
    assert offer_picture._owner_rule(False, True, Tier.TIER_1, True) == "plan"
    assert offer_picture._owner_rule(False, True, Tier.TIER_1, False) == "recheck"
    mandate = SimpleNamespace(tier2_single_commitment_fen=5_000_000)
    assert offer_picture._rule_text("en", "value", mandate) == "Your mandate lets FLOW agree on its own only to a commitment of up to ¥50,000.00."
    assert offer_picture._rule_text("zh", "plan", mandate) == "此回复所需的融资方案因其成本需要您批准。"


# ---------------------------------------------------------------- why the recommended path is recommended


def test_only_the_recommended_path_says_why_and_by_the_rule_the_engine_applies(client):
    oid, _ = _evaluated(client)
    asked, opt_a, opt_b = _paths(client, oid)
    assert opt_a["recommended"] is True
    assert opt_a["recommended_reason_text"] == "Recommended because FLOW can send it within your mandate without your approval."
    assert asked["recommended_reason_text"] is None and opt_b["recommended_reason_text"] is None
    z_asked, z_a, z_b = _paths(client, oid, "zh")
    assert z_a["recommended_reason_text"] == "推荐原因：FLOW 可以在您的授权范围内直接发送，无需您批准。"
    assert z_asked["recommended_reason_text"] is None and z_b["recommended_reason_text"] is None
    assert "cost" not in opt_a["recommended_reason_text"] and "成本" not in z_a["recommended_reason_text"]


def test_a_recommendation_that_needs_the_owner_says_so(client, monkeypatch):
    oid, _ = _evaluated(client)
    real = offer_picture.plan
    monkeypatch.setattr(offer_picture, "plan", lambda *a, **k: real(*a, **k).model_copy(update={"needs_owner_approval": True}))
    offer_picture._cache.clear()
    asked, opt_a, opt_b = _paths(client, oid)
    assert opt_a["recommended"] is True and opt_a["needs_owner"] is True
    assert opt_a["recommended_reason_text"] == "Recommended because it is the first counter within your mandate; it needs your approval."
    assert asked["recommended_reason_text"] is None and opt_b["recommended_reason_text"] is None
    assert _paths(client, oid, "zh")[1]["recommended_reason_text"] == "推荐原因：它是您授权范围内的第一个还价；需要您批准。"


def test_the_recommendation_that_falls_to_the_next_reply_carries_the_reason(client, monkeypatch):
    oid, view = _evaluated(client)
    first = view["counters"][0]["id"]
    real = offer_picture.counter_recheck

    def recheck(*a, **k):
        check = real(*a, **k)
        return lambda c: check(c).model_copy(update={"outcome": Outcome.NO_VERDICT}) if c.id == first else check(c)

    monkeypatch.setattr(offer_picture, "counter_recheck", recheck)
    offer_picture._cache.clear()
    _, opt_a, opt_b = _paths(client, oid)
    assert opt_a["recommended_reason_text"] is None
    assert opt_b["recommended_reason_text"] == "Recommended because it is the first counter within your mandate; it needs your approval."


# ---------------------------------------------------------------- the same-day comparison on every point


def _point(path, day):
    return next(p for p in path["series"] if p["day"] == day)


def test_every_point_carries_the_same_day_strip_of_the_asked_path_and_the_recommended_reply(client):
    oid, _ = _evaluated(client)
    asked, opt_a, opt_b = _paths(client, oid)
    low_day = min(asked["series"], key=lambda p: (p["closing_fen"], p["day"]))["day"]
    assert low_day == 60
    for path in (asked, opt_a, opt_b):  # the strip is the day's, whichever line the point is on
        assert _point(path, low_day)["comparison"] == {"label": "Same day", "asked_display": "¥164,960.00",
                                                       "recommended_display": "¥586,972.23", "difference_display": "+¥422,012.23"}
        # day 0: Option A's own funding plan draws the credit line today (the asked path takes no new funding)
        assert _point(path, 0)["comparison"] == {"label": "Same day", "asked_display": _point(asked, 0)["closing_display"],
                                                 "recommended_display": _point(opt_a, 0)["closing_display"],
                                                 "difference_display": "+¥149,986.20"}
    assert all(p["comparison"] is not None for p in asked["series"])
    zh = _paths(client, oid, "zh")
    assert _point(zh[0], low_day)["comparison"]["label"] == "同一天" and _point(zh[0], low_day)["comparison"]["difference_display"] == "+¥422,012.23"


def test_the_strip_is_the_two_series_own_figures_and_null_where_there_is_nothing_to_compare(client):
    oid, _ = _evaluated(client)
    asked, opt_a, _ = _paths(client, oid)
    for pt in asked["series"]:
        mine = next((q for q in opt_a["series"] if q["day"] == pt["day"]), None)
        c = pt["comparison"]
        if mine is None:
            assert c is None
            continue
        assert (c["asked_display"], c["recommended_display"]) == (pt["closing_display"], mine["closing_display"])
        diff = mine["closing_fen"] - pt["closing_fen"]
        assert c["difference_display"].lstrip("+−") == ("¥0" if diff == 0 else c["difference_display"].lstrip("+−"))
        assert (diff == 0) == (c["difference_display"] == "¥0") and (diff < 0) == c["difference_display"].startswith("−")


def test_with_no_recommended_reply_there_is_no_strip(client, monkeypatch):
    oid, _ = _evaluated(client)
    _recheck_as(monkeypatch, outcome=Outcome.REJECT, violations=[])
    offer_picture._cache.clear()
    assert all(p["comparison"] is None for path in _paths(client, oid) for p in path["series"])


# ---------------------------------------------------------------- what each line assumes


def test_a_reply_with_no_admissible_plan_says_so_and_a_reply_that_needs_none_says_that(client, monkeypatch):
    oid, _ = _evaluated(client)
    real = offer_picture.plan
    monkeypatch.setattr(offer_picture, "plan", lambda *a, **k: real(*a, **k).model_copy(update={"admissible": False}))
    offer_picture._cache.clear()
    asked, opt_a, opt_b = _paths(client, oid)
    assert asked["scenario_assumption_text"] == "Assumes the buyer accepts this offer and FLOW takes no new funding."
    for p in (opt_a, opt_b):
        assert p["scenario_assumption_text"] == "Assumes the buyer accepts this reply; no funding plan is available within your mandate."
    z = _paths(client, oid, "zh")
    assert z[1]["scenario_assumption_text"] == "假设买方接受此回复；您的授权范围内没有可用的融资方案。"
    monkeypatch.setattr(offer_picture, "plan", lambda *a, **k: real(*a, **k).model_copy(update={"admissible": True, "actions": [], "need_fen": 0}))
    offer_picture._cache.clear()
    assert _paths(client, oid)[1]["scenario_assumption_text"] == "Assumes the buyer accepts this reply; no new funding is needed."
