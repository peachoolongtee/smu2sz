"""Review gaps G2, G3, G4: a mandate that is about to lapse, a cash-below-zero fallback cure, and an act button bound to
what the owner was shown. State and structure assertions only: no absolute golden cash figures."""

from __future__ import annotations

import pytest

from app.alerts import AlertKind, Severity
from app.api.runtime import get_runtime, set_runtime
from app.config import get_settings
from app.domain.fixtures import load_scenario
from app.domain.models import FundingAction, FundingActionKind, Mode
from app.financial import project
from tests.alerts.test_act import _client, _log
from tests.alerts.test_alerts import _of, _run, _store

# ---------------------------------------------------------------- G2: the mandate lifecycle


def _with_expiry(expires_day: int):
    store = _store()
    store.put_mandate(store.get_mandate().model_copy(update={"expires_day": expires_day}))
    return store


def test_a_mandate_expiring_in_ten_days_is_a_warning_with_no_operation():
    [a] = _of(_run(_with_expiry(10)), AlertKind.MANDATE_EXPIRING)
    assert a.severity == Severity.WARNING and a.day == 10 and a.suggested == [] and a.actionable is False
    assert "expires in 10 day(s)" in a.title
    assert "offline" in a.detail and "cannot renew" in a.detail
    assert "horizon" in a.detail  # the horizon runs past the expiry and the alert says so


def test_a_mandate_expiring_on_the_last_valid_day_still_warns_and_one_far_away_does_not():
    [a] = _of(_run(_with_expiry(14)), AlertKind.MANDATE_EXPIRING)
    assert a.severity == Severity.WARNING
    assert not _of(_run(_with_expiry(15)), AlertKind.MANDATE_EXPIRING)
    assert not _of(_run(_store()), AlertKind.MANDATE_EXPIRING)  # the demo mandate is far from expiry on day 0


def test_an_expired_mandate_is_critical():
    store = _with_expiry(3)
    [a] = _of(_run(store, day=4), AlertKind.MANDATE_EXPIRING)
    assert a.severity == Severity.CRITICAL and a.title == "mandate expired: the agent can no longer act"
    assert a.suggested == [] and a.actionable is False and "offline" in a.detail
    [last_valid] = _of(_run(store, day=3), AlertKind.MANDATE_EXPIRING)  # expiry is "after the day", as the executor reads it
    assert last_valid.severity == Severity.WARNING


# ---------------------------------------------------------------- G3: cash below zero and a fallback cure


def _short_facilities_state():
    """Committed headroom too small to restore the reserve but enough to keep cash from going below zero.

    Without action cash is 400,000 − 340,000 − 120,000 = −60,000 on days 20–29 and −105,000 on days 30–31 (the existing
    loan's ¥45,000 day-30 payment), until RCV-A pays on day 32. ¥60,000 of line and ¥60,000 of invoice financing
    (landing day 3) give 120,000 ≥ 105,000 to stay at or above zero, far short of the 405,000 the reserve needs.
    (Before the loan's payments were cash, ¥50,000 each covered the −60,000 low.)"""
    state, _ = load_scenario()
    return state.model_copy(update={"facilities": [
        f.model_copy(update={"limit_fen": 6_000_000}) if f.id in ("FAC-LINE", "FAC-IF") else f for f in state.facilities]})


def test_no_plan_restores_the_reserve_but_one_keeps_cash_at_or_above_zero():
    store = _store(_short_facilities_state())
    [b] = _of(_run(store), AlertKind.RESERVE_BREACH_AHEAD)
    zero_day = int(b.inputs["zero_day"])
    assert b.title == f"cash goes below zero on day {zero_day} without action"
    assert b.committed_cure is False  # it does not restore the reserve
    assert b.inputs["cure_restores_reserve"] == "false" and b.actionable is True
    assert b.suggested and all(s.operation_kind in ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING")
                               for s in b.suggested)
    assert any(s.cost_fen is not None for s in b.suggested)  # the cure is shown with its cost (an open draw has none)
    assert ", cost " in b.detail
    assert "does not restore the reserve" in b.detail
    assert "simulation limit" in b.detail  # the overdraft is a limit of the projection, not a bank facility
    # structural check: without action the episode goes below zero, with the shown cure it never does
    state, mandate = store.get_state(), store.get_mandate()
    base = project(state, [], [], Mode.CONSERVATIVE, mandate.horizon_days)
    assert min(p.closing_fen for p in base.days if p.day >= zero_day) < 0
    cure = [FundingAction(kind=(FundingActionKind.DRAW if s.operation_kind == "DRAW_FACILITY"
                                else FundingActionKind.FINANCE_INVOICE),
                          facility_id=s.facility_id, day=0, amount_fen=s.amount_fen, receivable_id=s.receivable_id)
            for s in b.suggested]
    after = project(state, [], cure, Mode.CONSERVATIVE, mandate.horizon_days)
    assert min(p.closing_fen for p in after.days if int(b.day) <= p.day <= int(b.inputs["last_day"])) >= 0
    assert min(p.closing_fen for p in after.days if int(b.day) <= p.day <= int(b.inputs["last_day"])) < mandate.min_cash_fen


def test_a_full_committed_cure_keeps_its_old_title_and_is_not_a_fallback():
    [b] = _of(_run(_store()), AlertKind.RESERVE_BREACH_AHEAD)
    assert b.committed_cure is True and b.title == f"Reserve breach ahead on day {b.day}"
    assert "cure_restores_reserve" not in b.inputs and "zero_day" not in b.inputs


def test_with_no_committed_headroom_at_all_the_apply_suggestion_is_unchanged():
    state, _ = load_scenario()
    state = state.model_copy(update={"facilities": [
        f.model_copy(update={"drawn_fen": f.limit_fen}) if f.id in ("FAC-LINE", "FAC-IF") else f for f in state.facilities]})
    [b] = _of(_run(_store(state)), AlertKind.RESERVE_BREACH_AHEAD)
    assert b.committed_cure is False and "cure_restores_reserve" not in b.inputs
    assert all(s.operation_kind == "APPLY_FOR_FACILITY" for s in b.suggested)


# ---------------------------------------------------------------- G4: the act button is bound to what was shown


@pytest.fixture
def act_client():
    yield _client(get_settings())
    set_runtime(None)


def _breach(c):
    body = c.get("/alerts").json()
    [b] = [a for a in body["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
    return b, body["state_version"]


def _sig(b):
    return [{k: s.get(k) for k in ("operation_kind", "facility_id", "receivable_id", "amount_fen")} for s in b["suggested"]]


def test_get_alerts_carries_the_state_version(act_client):
    _b, v = _breach(act_client)
    assert v == get_runtime().store.get_state().state_version


def test_a_stale_state_version_is_409_alert_changed_and_nothing_runs(act_client):
    rt = get_runtime()
    b, v = _breach(act_client)
    rt.store.put_state(rt.store.get_state().model_copy(update={"state_version": v + 1}))
    logged = len(_log(rt))
    r = act_client.post(f"/alerts/{b['id']}/act", json={"state_version": v})
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["code"] == "ALERT_CHANGED" and d["state_version"] == v + 1
    assert d["alert"]["id"] == b["id"] and d["alert"]["kind"] == "RESERVE_BREACH_AHEAD"
    assert len(_log(rt)) == logged and not rt.store.approvals()


def test_a_stale_version_for_an_alert_that_is_gone_answers_with_a_null_alert(act_client):
    rt = get_runtime()
    _b, v = _breach(act_client)
    rt.store.put_state(rt.store.get_state().model_copy(update={"state_version": v + 1}))
    r = act_client.post("/alerts/ALERT-NO-SUCH/act", json={"state_version": v})
    assert r.status_code == 409 and r.json()["detail"]["alert"] is None


def test_a_signature_that_no_longer_matches_is_409_and_nothing_runs(act_client):
    rt = get_runtime()
    b, v = _breach(act_client)
    shown = _sig(b)
    shown[0]["amount_fen"] = (shown[0]["amount_fen"] or 0) + 1  # the web was shown a different amount
    logged = len(_log(rt))
    r = act_client.post(f"/alerts/{b['id']}/act", json={"state_version": v, "suggestions": shown})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ALERT_CHANGED"
    r2 = act_client.post(f"/alerts/{b['id']}/act", json={"suggestions": list(reversed(_sig(b)))})  # order matters
    assert r2.status_code == 409
    assert len(_log(rt)) == logged


def test_the_current_state_version_runs_the_cure(act_client):
    rt = get_runtime()
    b, v = _breach(act_client)
    before = len(_log(rt))
    r = act_client.post(f"/alerts/{b['id']}/act", json={"state_version": v, "suggestions": _sig(b)})
    assert r.status_code == 200 and r.json()["results"]
    assert len(_log(rt)) > before
    assert not [e for e in rt.store.security_events() if "unbound act" in e.detail]


def test_a_request_without_a_body_still_acts_and_logs_an_unbound_act(act_client):
    rt = get_runtime()
    b, _v = _breach(act_client)
    before = len(_log(rt))
    r = act_client.post(f"/alerts/{b['id']}/act")
    assert r.status_code == 200 and r.json()["results"]
    assert len(_log(rt)) > before
    [ev] = [e for e in rt.store.security_events() if "unbound act" in e.detail]
    assert b["id"] in ev.detail
