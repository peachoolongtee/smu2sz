"""Wave 1 (map #65, ticket #70): the Business pages tell time as it is. A fact about a past day is history, not a current
eligibility (F03, R01, F25); a forecast reads from today, never from the projection's closed days (F01, R02); an approval
card carries its terms (F02), its after-state (F12), its landing as a forecast (R03) and what came of it (F14).

The walk is the audit's: reset, the EX01 package, a cooperative buyer, day 2, optionally the half receipt, day 34."""

from __future__ import annotations

import pytest

from app.api.presentation import (
    agreement_ref,
    agreement_terms,
    approval_words,
    deadline_text,
    find_agreement,
    obligation_sentence,
    relative_days,
    result_words,
    settlement_words,
)
from app.api.runtime import get_runtime

BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
BUYER = {"X-Counterparty-Key": "demo-buyer-1-key"}


def _walk(client, *, receipt: str | None = None, to: int = 34) -> None:
    client.post("/demo/reset", json={})
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    client.post(f"/negotiate/{offer['offer_id']}", json={"buyer_profile": "cooperative"})
    client.post("/clock/advance", json={"to_day": 2})
    if receipt == "half":
        promise = client.get("/reconciliation").json()["reconciliation"]["promised"][0]
        version = client.get("/mandate").json()["mandate"]["version"]
        r = client.post("/operations", headers=BANK, json={
            "kind": "RECEIVE_PAYMENT", "op_id": "rc-half", "idempotency_key": "rc-half", "mandate_version": version,
            "requested_by": "SYSTEM", "receivable_id": promise["receivable_id"], "amount_fen": promise["expected_fen"] // 2,
            "bank_reference": "BANK-1"})
        assert r.json()["result"]["status"] == "EXECUTED"
    if to > 30:
        client.post("/clock/advance", json={"to_day": 30})
    if to > 2:
        client.post("/clock/advance", json={"to_day": to})


def _act(client) -> dict:
    action = client.get("/home").json()["next_action"]
    r = client.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]})
    assert r.status_code == 200, r.text
    return r.json()


def _queue(client) -> list[dict]:
    return client.get("/approvals/queue").json()["approvals"]


# ---------------------------------------------------------------- the words themselves


def test_a_deadline_is_by_today_only_on_the_day_itself():
    assert [deadline_text(n) for n in (0, 1, 2, 13)] == ["by today", "by tomorrow", "within 2 days", "within 13 days"]
    assert deadline_text(-1) == "by a deadline that passed yesterday"
    assert deadline_text(-4) == "by a deadline that passed 4 days ago"
    r = lambda text, today=34: relative_days(text, today, "en")
    assert r("by day 34") == "by today" and r("by day 35") == "by tomorrow" and r("by day 30") == "by a deadline that passed 4 days ago"


def test_the_settlement_window_is_said_by_its_own_day():
    clause = "agreed early payment for ¥128,600.00 of face; up to ¥128,600.00 more may be settled early by day 2"
    live = lambda text, today: settlement_words(text, today, live=True)  # noqa: E731
    assert live(clause, 2).endswith("; up to ¥128,600.00 more may still be settled early by today")
    assert live(clause, 1).endswith("more may still be settled early by tomorrow")
    assert live(clause, 0).endswith("more may still be settled early within 2 days")
    # a window the promise no longer has open is never "may still": the neutral form says what could be done
    assert settlement_words(clause, 2).endswith("; up to ¥128,600.00 more could be settled early until today")
    assert settlement_words(clause, 0).endswith("more could be settled early until 2 days from now")
    assert settlement_words(clause, 1).endswith("more could be settled early until tomorrow")
    for live_flag in (True, False):  # a window that has ended is ended whatever the promise says
        assert settlement_words(clause, 34, live_flag).endswith("; the early-payment window for the other ¥128,600.00 ended 32 days ago")
        assert settlement_words(clause, 3, live_flag).endswith("; the early-payment window for the other ¥128,600.00 ended yesterday")
    due = "(settles ¥1.00; ¥291,400.00 still due on day 32)"
    assert settlement_words(due, 34) == "(settles ¥1.00; ¥291,400.00 was still due 2 days ago)"
    assert settlement_words(due, 30) == due  # not yet due: the ordinary day rewrite says "in 2 days"
    assert settlement_words("¥1.00 promised for day 2 under commitment CMT-ab", 34) == (
        "¥1.00 promised as an early payment due 32 days ago under commitment CMT-ab")


def test_a_commitment_id_never_reaches_the_owner():
    ref = lambda text, **m: agreement_ref(text, m)  # noqa: E731
    known = {"CMT-ab12": "Foshan Home Retail Co."}
    assert agreement_ref("promised under commitment CMT-ab12 did not arrive", known) == (
        "promised under the agreement with Foshan Home Retail Co. did not arrive")
    assert agreement_ref("the early payment of commitment CMT-ab12 lapsed", known) == "the early payment of the agreement with Foshan Home Retail Co. lapsed"
    assert agreement_ref("Commitment CMT-ab12 is ACTIVE; forward concession ¥0.00 booked", known) == (
        "The agreement with Foshan Home Retail Co. is ACTIVE; forward concession ¥0.00 booked")
    assert agreement_ref("Only the owner may revoke commitment CMT-ab12; the owner may revoke CMT-ab12 first", known) == (
        "Only the owner may revoke the agreement with Foshan Home Retail Co.; the owner may revoke the agreement with Foshan Home Retail Co. first")
    assert agreement_ref("of accepted commitment CMT-ff00 and the earlier REVOKED commitment CMT-ee11") == (
        "of the accepted agreement and the earlier revoked agreement")
    assert agreement_ref("paid (commitment CMT-ab12) now", known) == "paid now"
    assert ref("FC-CMT-ab12 stays") == "FC-CMT-ab12 stays"  # a longer record id is not a commitment id


def test_a_pending_approval_lands_from_today_a_decided_one_from_its_lot(client):
    from app.domain.fixtures import load_scenario

    state, _ = load_scenario()
    facility = next(f for f in state.facilities if f.lead_time_days > 0)
    op = {"kind": "DRAW_FACILITY", "op_id": "x", "day": 0, "facility_id": facility.id, "amount_fen": 100}
    pending = approval_words(state, op, "DRAW_FACILITY", 34, None, "en")
    assert pending["lands_day"] == 34 + facility.lead_time_days
    assert pending["lands_text"] == f"If you approve today, the cash lands in {facility.lead_time_days} days."
    assert pending["if_decline"] is not None
    decided = approval_words(state, op, "DRAW_FACILITY", 34, None, "en", status="APPROVED")
    assert decided["lands_day"] is None and decided["lands_text"] is None and decided["if_decline"] is None


def test_only_a_rejected_approval_is_a_decline(client):
    from app.domain.fixtures import load_scenario

    state, _ = load_scenario()
    draw = {"kind": "DRAW_FACILITY", "facility_id": state.facilities[0].id, "amount_fen": 15_000_000}
    kw = {"kind": "DRAW_FACILITY", "status": "REFUSED", "payload": draw, "day": 91, "today": 91}
    assert result_words(state, **kw, approval_status="APPROVED", message="Refused: Mandate v1 expired on day 90") == (
        "You approved it, but it could not run: Mandate v1 expired yesterday. No money moved.")
    assert result_words(state, **kw, approval_status="REJECTED", message="Declined by the owner").startswith("You declined")
    assert result_words(state, **kw).startswith("You declined")  # the callers that do not say which keep the old reading


# ---------------------------------------------------------------- F01, R02: the forecast reads from today


def test_day_34_without_a_receipt_the_first_breach_is_today_and_the_payroll_driver_is_back(client):
    _walk(client)
    home = client.get("/home").json()
    cash = home["cash"]
    assert cash["cash_fen"] < cash["floor_fen"]
    assert cash["first_breach_day"] == 34 and cash["first_breach_when"] == "today" and cash["below_reserve_today"] is True
    assert cash["first_breach_cash_fen"] == cash["cash_fen"] and cash["first_breach_cash_short"] == cash["cash_short"]
    assert "34 days ago" not in str(cash["first_breach_when"]) and "becomes unsafe" not in home["headline"]
    assert any(d.startswith("Payroll of") and d.endswith("falls due in 8 days.") for d in cash["drivers"])
    assert cash["series"][0]["day"] == 34 and all(row["day"] >= 34 for row in cash["series"])
    # already under the reserve (F01): the headline says so; the zero day is the note's fact
    assert home["headline"] == "Below reserve today."
    assert home["note"].startswith("Cash is ¥255k below your ¥300k minimum cash reserve and goes below zero in 8 days if nothing is done.")
    assert home["worst"] == "Worst point: −¥155k in 8 days if you do nothing."


def test_the_trajectory_view_keeps_the_engines_day_and_adds_the_first_breach_ahead(client):
    _walk(client)
    view = client.get("/trajectory").json()
    assert view["first_breach_day"] == 0 and view["today"] == 34  # the engine's own scan, closed days included
    assert view["first_breach_ahead_day"] == 34 and view["first_breach_ahead_cash"]["fen"] == client.get("/home").json()["cash"]["cash_fen"]


def test_a_breach_ahead_is_reported_by_its_own_day_and_is_not_today(client):
    client.post("/demo/reset", json={})
    home = client.get("/home").json()
    cash = home["cash"]
    assert cash["below_reserve_today"] is False
    assert cash["first_breach_day"] == 12 and cash["first_breach_when"] == "in 12 days"
    assert cash["first_breach_cash_short"] == "¥60k"
    view = client.get("/trajectory").json()
    assert view["first_breach_ahead_day"] == 12 and view["first_breach_ahead_cash"]["fen"] == 6_000_000
    assert home["headline"] == "Your cash reserve becomes unsafe in 12 days."


def test_with_the_cure_approved_the_headline_says_below_reserve_and_the_worst_point_counts_the_funding(client):
    _walk(client)
    _act(client)
    approval = _queue(client)[0]
    assert client.post(f"/approvals/{approval['id']}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    home = client.get("/home").json()
    assert home["headline"] == "Below reserve today."
    assert home["note"].startswith("Cash is ¥255k below your ¥300k minimum cash reserve")
    assert home["worst"] == "Lowest point: ¥0.00 in 8 days if nothing more is done."  # R04: not "if you do nothing"
    assert home["cash"]["below_reserve_today"] is True and home["cash"]["first_breach_when"] == "today"
    assert any(d.startswith("Payroll of") for d in home["cash"]["drivers"])
    lang = client.get("/home?lang=zh").json()
    assert lang["headline"] == "今天现金低于储备。"


# ---------------------------------------------------------------- F03, R01, R05, F25: history stays history


def test_day_2_the_early_payment_window_is_still_open_by_today(client):
    _walk(client, receipt="half", to=2)
    receipt = client.get("/reconciliation").json()["reconciliation"]["receipts"][0]
    assert "up to ¥128,600.00 more may still be settled early by today" in receipt["detail_when"]
    assert "ended" not in receipt["detail_when"] and "by day 2" in receipt["detail"]


def test_day_34_a_receipt_from_day_2_does_not_say_by_today(client):
    _walk(client, receipt="half")
    rec = client.get("/reconciliation").json()["reconciliation"]
    receipt, promise = rec["receipts"][0], rec["promised"][0]
    assert receipt["detail_when"] == ("agreed early payment for ¥128,600.00 of the invoice; the early-payment window for the "
                                      "other ¥128,600.00 ended 32 days ago")
    assert "by today" not in receipt["detail_when"]
    assert "by day 2" in receipt["detail"]  # the raw sentence is untouched
    assert promise["detail_when"].endswith("the other ¥128,600.00 is due on the invoice's own day.")
    assert "CMT-" not in promise["detail_when"]
    event = next(o for o in client.get("/ledger").json()["operations"] if o["kind"] == "RECEIVE_PAYMENT")
    for text in (event["event_detail"], event["message_when"]):
        assert "by today" not in text and "more may be settled early" not in text
        assert "ended 32 days ago" in text and "¥291,400.00 was still due 2 days ago" in text
    assert event["event_text"] == "Received ¥127,506.90 from Foshan Home Retail Co."


def test_a_lapsed_promise_names_the_buyer_not_the_commitment(client):
    _walk(client)
    rec = client.get("/reconciliation").json()["reconciliation"]["promised"][0]
    assert rec["status"] == "LAPSED"
    assert "CMT-" not in rec["detail_when"] and "commitment" not in rec["detail_when"]
    assert "under the agreement with Foshan Home Retail Co. did not arrive" in rec["detail_when"]
    home = client.get("/home").json()
    for text in [c["text"] for c in home["changes"]] + [w["title"] for w in home["warnings"]] + [w["detail"] for w in home["warnings"]]:
        assert "CMT-" not in text and "commitment" not in text
    late = next(c for c in home["changes"] if "early payment" in c["text"])
    assert late["text"] == ("The early payment promised under the agreement with Foshan Home Retail Co. 32 days ago did not arrive.")
    assert "window_state" not in late  # nothing arrived: no four facts


def test_after_a_partial_receipt_the_change_says_what_arrived(client):
    _walk(client, receipt="half")
    changes = client.get("/home").json()["changes"]
    row = next(c for c in changes if c.get("window_state"))
    assert row["text"] == row["event_text"] == (
        "Received ¥127,506.90 from Foshan Home Retail Co. 32 days ago: it cleared ¥128,600.00 of the invoice, including a "
        "¥1,093.10 early-payment discount; ¥291,400.00 remains and is overdue; the early-payment window has ended.")
    assert (row["received_display"], row["face_cleared_display"], row["discount_display"], row["remaining_display"]) == (
        "¥127,506.90", "¥128,600.00", "¥1,093.10", "¥291,400.00")
    assert row["window_state"] == "ended" and row["kind"] == "LATE"
    assert not any("did not arrive" in c["text"] for c in changes)
    assert not any("CMT-" in c["text"] for c in changes)
    overdue = next(c for c in changes if c["kind"] == "LATE" and not c.get("window_state"))
    assert overdue["text"] == "¥291,400.00 outstanding from Foshan Home Retail Co. was due 2 days ago and is still OPEN."
    warnings = client.get("/home").json()["warnings"]
    assert next(w["detail"] for w in warnings) == (
        "¥291,400.00 outstanding from Foshan Home Retail Co. was due 2 days ago and is still OPEN. "
        "The cash forecast no longer counts on a dated receipt.")
    assert not any("CMT-" in w["title"] + w["detail"] for w in warnings)


def test_the_first_breach_after_the_half_receipt_is_today_too(client):
    _walk(client, receipt="half")
    cash = client.get("/home").json()["cash"]
    assert cash["first_breach_day"] == 34 and cash["first_breach_when"] == "today" and cash["below_reserve_today"] is True
    assert cash["first_breach_cash_short"] == "¥172k"


# ---------------------------------------------------------------- F02: the card carries the terms


def _queue_agreement(client) -> dict:
    client.post("/demo/reset", json={})
    r = client.post("/nl", headers=BUYER, json={"session_id": "w1", "actor": "COUNTERPARTY", "counterparty_id": "BUYER-1",
                                                  "text": "We can pay the invoice early at 0.5%.", "request_id": "w1-1"})
    assert r.status_code == 200, r.text
    rows = [a for a in _queue(client) if a["kind"] in ("ACCEPT_OFFER", "RECORD_COMMITMENT")]
    assert rows, "the buyer's early-payment message should queue an agreement for the owner"
    return rows[0]


def test_a_queued_agreement_carries_its_terms_and_the_buyer(client):
    row = _queue_agreement(client)
    p = row["presentation"]
    assert p["terms_available"] is True and p["terms_unavailable_reason"] is None
    assert p["terms"] == ["The buyer may pay early and take 0.50% off the ¥420,000.00 invoice to Foshan Home Retail Co. "
                          "(effective in 2 days; one time)"]
    assert p["counterparty_name"] == "Foshan Home Retail Co."
    # a zero forward value is not "free": no figure, and the economic effect said in words
    assert p["forward_value_display"] is None
    assert p["economic_effect_text"] == "No cost over the valuation window beyond the early-payment discount."
    assert p["what_you_agree_to"] == p["terms"][0] + "."
    assert p["headline"] == "Approve this agreement with Foshan Home Retail Co.?"
    assert p["amount_display"] == "¥420,000.00" and row["amount_display"] == "¥420,000.00"
    assert "¥0.00" not in p["what"] and "Accept offer" not in p["what"]
    assert p["lands_text"] is None and p["residual"] is None
    # the same row on the home
    home_row = client.get("/home").json()["approvals"][0]
    assert home_row["terms"] == p["terms"] and home_row["terms_available"] is True and home_row["headline"] == p["headline"]
    assert home_row["execution_status"] == "PENDING" and home_row["economic_effect_text"] == p["economic_effect_text"]


def test_a_funding_row_has_no_agreement_fields(client):
    _walk(client)
    _act(client)
    p = _queue(client)[0]["presentation"]
    assert "terms" not in p and "terms_available" not in p
    assert p["lands_text"] == "If you approve today, the cash lands in 3 days."


def test_an_agreement_that_cannot_be_found_says_why_and_offers_no_terms(client, monkeypatch):
    _queue_agreement(client)
    monkeypatch.setattr(get_runtime().store, "commitments", list)
    p = _queue(client)[0]["presentation"]
    assert p["terms_available"] is False and p["terms"] == [] and p["what_you_agree_to"] is None
    assert p["terms_unavailable_reason"] == "The agreement this approval refers to could not be found."
    assert p["amount_display"] is None  # no agreement, no scope: never ¥0.00


@pytest.mark.parametrize(("status", "reason"), [
    ("EXPIRED", "The agreement this approval refers to has expired."),
    ("REVOKED", "The agreement this approval refers to was revoked."),
    ("ACTIVE", "The agreement this approval refers to is already in force or settled."),
])
def test_an_agreement_that_is_no_longer_waiting_has_no_terms(client, status, reason):
    row = _queue_agreement(client)
    rt = get_runtime()
    commitment = find_agreement(row["operation"], rt.store.commitments())
    assert commitment is not None and commitment.status.value == "PROPOSED"
    out = agreement_terms(rt.store.get_state(), commitment.model_copy(update={"status": status}), rt.day)
    assert out["terms_available"] is False and out["terms_unavailable_reason"] == reason and out["terms"] == []


def test_an_agreement_is_found_by_offer_version_and_the_exact_nonce(client):
    row = _queue_agreement(client)
    rt = get_runtime()
    op = row["operation"]
    commitments = rt.store.commitments()
    assert find_agreement(op, commitments) is not None
    assert find_agreement({**op, "nonce": op["nonce"] + "x"}, commitments) is None
    assert find_agreement({**op, "offer_version": op["offer_version"] + 1}, commitments) is None
    record = {"kind": "RECORD_COMMITMENT", "commitment_id": commitments[0].id}
    assert find_agreement(record, commitments) is commitments[0]
    assert find_agreement({"kind": "RECORD_COMMITMENT", "commitment_id": "CMT-none"}, commitments) is None


def test_a_commitment_without_obligations_has_no_readable_terms(client):
    row = _queue_agreement(client)
    rt = get_runtime()
    commitment = find_agreement(row["operation"], rt.store.commitments())
    out = agreement_terms(rt.store.get_state(), commitment.model_copy(update={"obligations": []}), rt.day)
    assert out["terms_available"] is False and out["terms_unavailable_reason"].endswith("could not be read.")


# ---------------------------------------------------------------- F12, R03, F14


def test_a_cure_that_only_keeps_cash_above_zero_still_states_its_after_state(client):
    _walk(client)
    _act(client)
    row = _queue(client)[0]
    p = row["presentation"]
    assert p["protects"] == ("Prevents negative cash; cash stays ¥300k below your ¥300k minimum cash reserve from today "
                             "(lowest ¥0.00 in 8 days).")
    assert p["residual"] == {"shortfall_display": "¥300,000.00", "from_when": "today", "restores_reserve": False}
    assert p["execution_status"] == "PENDING" and p["if_decline"] == "Cash goes below zero in 8 days."
    # the home's card for the same cure says the same
    assert client.get("/home").json()["approvals"][0]["protects"] == p["protects"]


def test_a_decided_row_has_no_decline_outcome_and_a_status(client):
    _walk(client)
    _act(client)
    approval = _queue(client)[0]
    client.post(f"/approvals/{approval['id']}", json={"decision": "APPROVE"})
    p = _queue(client)[0]["presentation"]
    assert p["if_decline"] is None and p["execution_status"] == "EXECUTED" and p["lands_text"] is None
    assert p["lands_day"] == 37 and p["lands_when"] == "in 3 days"  # the lot's own landing day


def test_a_declined_row_says_declined_and_has_no_landing(client):
    _walk(client)
    _act(client)
    approval = _queue(client)[0]
    client.post(f"/approvals/{approval['id']}", json={"decision": "REJECT"})
    p = _queue(client)[0]["presentation"]
    assert p["execution_status"] == "DECLINED" and p["result_message"].startswith("You declined")
    assert p["lands_day"] is None and p["if_decline"] is None


def test_an_approval_the_run_refused_is_not_a_decline(client):
    _walk(client)
    _act(client)
    approval = _queue(client)[0]
    client.post("/clock/advance", json={"to_day": 91})  # the mandate expired on day 90
    result = client.post(f"/approvals/{approval['id']}", json={"decision": "APPROVE"})
    assert result.status_code == 200 and result.json()["result"]["status"] == "REFUSED"
    row = _queue(client)[0]
    p = row["presentation"]
    assert row["status"] == "APPROVED" and p["execution_status"] == "REFUSED"
    assert p["result_message"] == "You approved it, but it could not run: Mandate v1 expired yesterday. No money moved."
    assert "declined" not in p["result_message"].lower()
    assert p["if_decline"] is None and p["lands_day"] is None


# ---------------------------------------------------------------- review fixes: the EX01 package through the HTTP queue


AGENT = {"X-Agent-Key": "demo-agent-key"}


def _queue_counter(client, which: int) -> dict:
    """Option A (0) or Option B (1) of the EX01 package, proposed as a commitment and recorded as the agent would: a RECORD_COMMITMENT
    that needs the owner waits in the approvals queue."""
    client.post("/demo/reset", json={})
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    ev = client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()
    verdict = ev.get("verdict", ev)
    rt = get_runtime()
    commitment = rt.executor.propose_commitment(verdict["id"], expires_day=14, counter_id=verdict["counters"][which]["id"])
    version = client.get("/mandate").json()["mandate"]["version"]
    r = client.post("/operations", headers=AGENT, json={
        "kind": "RECORD_COMMITMENT", "op_id": "rec-1", "idempotency_key": "rec-1", "mandate_version": version,
        "requested_by": "AGENT", "commitment_id": commitment.id, "nonce": commitment.nonce})
    assert r.status_code == 200, r.text
    rows = [a for a in _queue(client) if a["kind"] == "RECORD_COMMITMENT"]
    return {"row": rows[0] if rows else None, "result": r.json()["result"], "commitment": commitment}


def test_option_b_of_the_package_reads_as_terms_not_as_an_invoice_amount(client):
    queued = _queue_counter(client, 1)
    assert queued["result"]["status"] == "PENDING_APPROVAL"
    p = queued["row"]["presentation"]
    assert p["terms_available"] is True and p["headline"] == "Approve this agreement with Foshan Home Retail Co.?"
    assert p["terms"] == ["The buyer gets 55-day payment terms on future invoices (ongoing, no end date)",
                          "The price changes by 0.30% on future invoices (ongoing, no end date)"]
    assert p["amount_display"] is None and queued["row"]["amount_display"] is None  # the bases are not invoices
    assert "RCV-" not in " ".join(p["terms"]) and "¥0.00" not in p["what"]
    cost = queued["commitment"].forward_value_fen
    if cost:
        assert p["forward_value_display"] and p["economic_effect_text"].startswith("Future cost of the terms you promise: ")
        assert p["economic_effect_text"].endswith(" over the next 365 days.")
    else:
        assert p["forward_value_display"] is None and "terms you promise: ¥0.00" in p["economic_effect_text"]


def test_a_cap_below_the_invoice_is_a_cap_not_a_smaller_invoice(client):
    _queue_agreement(client)
    rt = get_runtime()
    commitment = rt.store.commitments()[0]
    capped = commitment.model_copy(update={"obligations": [
        ob.model_copy(update={"base": ob.base.model_copy(update={"amount_fen": 25_720_000})}) for ob in commitment.obligations]})
    rt.store.put_commitment(capped)
    row = _queue(client)[0]
    assert row["presentation"]["terms"] == [
        "The buyer may pay early and take 0.50% off up to ¥257,200.00 of the ¥420,000.00 invoice to Foshan Home Retail Co. "
        "(effective in 2 days; one time)"]
    assert row["presentation"]["amount_display"] == "¥257,200.00"
    assert "RCV-" not in str(row["presentation"]["terms"])


def test_an_expired_or_revoked_agreement_in_the_queue_says_so(client):
    _queue_agreement(client)
    rt = get_runtime()
    commitment = rt.store.commitments()[0]
    for status, reason in (("EXPIRED", "has expired."), ("REVOKED", "was revoked.")):
        rt.store.put_commitment(commitment.model_copy(update={"status": status}))
        p = _queue(client)[0]["presentation"]
        assert p["terms_available"] is False and p["terms"] == []
        assert p["terms_unavailable_reason"] == f"The agreement this approval refers to {reason}"


def test_a_decided_agreement_row_still_shows_what_was_approved(client):
    row = _queue_agreement(client)
    assert client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    decided = next(a for a in _queue(client) if a["id"] == row["id"])
    assert get_runtime().store.commitments()[0].status.value in ("ACTIVE", "FULFILLED", "ACCEPTED")
    p = decided["presentation"]
    assert p["terms_available"] is True and p["terms_unavailable_reason"] is None
    assert p["terms"] and p["execution_status"] == "EXECUTED" and p["if_decline"] is None


def test_a_payment_term_that_gets_shorter_says_sooner(client):
    queued = _queue_counter(client, 1)
    rt = get_runtime()
    ob = next(o for o in queued["commitment"].obligations if o.type.value == "TERMS_EXTENSION")
    sooner = ob.model_copy(update={"days_delta": -15, "target_terms_days": None})
    assert obligation_sentence(rt.store.get_state(), sooner, 0).startswith("The buyer pays 15 days sooner on future invoices")
    assert "-15" not in obligation_sentence(rt.store.get_state(), sooner, 0)


# ---------------------------------------------------------------- review fixes: receipts, windows, warnings


def _receive(client, name: str, amount: int) -> None:
    promise = client.get("/reconciliation").json()["reconciliation"]["promised"][0]
    version = client.get("/mandate").json()["mandate"]["version"]
    r = client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": name, "idempotency_key": name, "mandate_version": version, "requested_by": "SYSTEM",
        "receivable_id": promise["receivable_id"], "amount_fen": amount, "bank_reference": name.upper()})
    assert r.json()["result"]["status"] == "EXECUTED", r.text


def _to_package_deal(client) -> int:
    client.post("/demo/reset", json={})
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    client.post(f"/negotiate/{offer['offer_id']}", json={"buyer_profile": "cooperative"})
    return client.get("/reconciliation").json()["reconciliation"]["promised"][0]["expected_fen"]


def test_a_receipt_stops_saying_may_still_once_the_remainder_is_settled(client):
    expected = _to_package_deal(client)
    client.post("/clock/advance", json={"to_day": 1})
    _receive(client, "half-1", expected // 2)
    first = client.get("/reconciliation").json()["reconciliation"]["receipts"][0]
    assert "may still be settled early by tomorrow" in first["detail_when"]  # the other half is still open
    ledger = next(o for o in client.get("/ledger").json()["operations"] if o["kind"] == "RECEIVE_PAYMENT")
    assert "may still be settled early by tomorrow" in ledger["event_detail"]
    client.post("/clock/advance", json={"to_day": 2})
    _receive(client, "half-2", expected - expected // 2)
    rec = client.get("/reconciliation").json()["reconciliation"]
    assert [p["status"] for p in rec["promised"]] == ["RECEIVED"]
    for row in rec["receipts"]:
        assert "may still" not in row["detail_when"]
    assert "more could be settled early until today" in rec["receipts"][0]["detail_when"]
    for op in client.get("/ledger").json()["operations"]:
        if op["kind"] == "RECEIVE_PAYMENT":
            assert "may still" not in (op["event_detail"] or "") + op["message_when"]


def test_two_part_payments_read_as_one_change_and_no_warning_says_nothing_arrived(client):
    expected = _to_package_deal(client)
    client.post("/clock/advance", json={"to_day": 1})
    _receive(client, "q-1", expected // 4)
    client.post("/clock/advance", json={"to_day": 2})
    _receive(client, "q-2", expected // 4)
    client.post("/clock/advance", json={"to_day": 30})
    client.post("/clock/advance", json={"to_day": 34})
    home = client.get("/home").json()
    row = next(c for c in home["changes"] if c.get("window_state"))
    assert row["text"].startswith("Received 2 payments totalling ¥127,506.90 from Foshan Home Retail Co. (the last 32 days ago): "
                                  "together they cleared ¥128,600.00 of the invoice")
    assert row["window_state"] == "ended" and row["kind"] == "LATE"
    assert not any("did not arrive" in w["title"] + w["detail"] for w in home["warnings"])
    early = next(w for w in home["warnings"] if w["kind"] == "RECEIVABLE_PAST_DUE" and "partly paid" in w["title"])
    assert early["title"].startswith("Early payment on the ¥420,000.00 invoice to Foshan Home Retail Co.")
    assert early["detail"].startswith("Received 2 payments totalling")


def test_the_half_receipt_leaves_no_warning_that_says_nothing_arrived(client):
    _walk(client, receipt="half")
    home = client.get("/home").json()
    assert not any("did not arrive" in w["title"] + w["detail"] for w in home["warnings"])
    early = next(w for w in home["warnings"] if "partly paid" in w["title"])
    assert early["detail"].startswith("Received ¥127,506.90 from Foshan Home Retail Co. 32 days ago: it cleared ¥128,600.00")
    assert "CMT-" not in early["title"] + early["detail"]


def test_the_decided_receipt_row_never_names_a_passed_deadline_as_by_today(client):
    _walk(client, receipt="half")
    # the result_message fallback goes through the same words as the ledger (names, the past as past, no commitment id)
    from app.api.presentation import business_text

    state = get_runtime().store.get_state()
    text = business_text(state, "Received ¥1.00 on RCV-A (settles ¥1.00; up to ¥2.00 more may be settled early by day 2; "
                                "¥3.00 still due on day 32) under commitment CMT-ab12", 34, "en", {"CMT-ab12": "Foshan Home Retail Co."})
    assert "by a deadline that passed" not in text and "by today" not in text
    assert "ended 32 days ago" in text and "was still due 2 days ago" in text and "CMT-" not in text


def test_the_home_next_action_and_the_card_say_the_same_after_state(client):
    _walk(client)
    _act(client)
    home = client.get("/home").json()
    card = _queue(client)[0]["presentation"]["protects"]
    assert home["next_action"]["after"] == card and card.startswith("Prevents negative cash; cash stays ")
