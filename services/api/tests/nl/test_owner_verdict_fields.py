"""The owner's /nl verdict carries the passed checks, the autonomy proof and the annualised cost of each early-pay
discount; the counterparty response stays the allow-list and carries none of it (INVARIANT 7)."""

from __future__ import annotations

import json

from app.api.nl import COUNTERPARTY_KEYS
from app.domain.fixtures import load_offers
from tests.nl.conftest import Chat

EX01 = load_offers()["EX01_PACKAGE"]["documents"][0]["text"]
CLEAN = "Deduct 0.6% and we'll settle the open ¥420,000 invoice today."
ALLOW = {*COUNTERPARTY_KEYS, "plan", "verdict", "operations", "clarification", "negotiation", "security_events",
         "parse_source", "awaiting_confirmation", "amended", "replayed"}


def test_owner_verdict_has_checks_autonomy_and_annualised(client):
    r = Chat(client, "own-ex01").say("Evaluate EX01")
    v = r["verdict"]
    assert v is not None and isinstance(v["passed_checks"], list) and v["passed_checks"]
    assert set(v["autonomy"]) == {"eligible", "accepted_alone", "whole_invoice", "covered", "gaps", "notes"}
    assert v["autonomy"]["accepted_alone"] is False and v["autonomy"]["whole_invoice"] is True
    by_id = {a["obligation_id"]: a for a in v["annualised"]}
    counter_a = next(c for c in v["counters"] if c["label"] == "Option A")
    assert by_id[counter_a["obligations"][0]["id"]]["annual_rate_display"] == "10.43%"
    assert by_id[v["bound_obligations"][0]["id"]]["compare_to"]
    # part 1 on the /nl verdict: obligations carry their display strings
    assert v["bound_obligations"][0]["rate_display"] == "1.20%"
    assert v["bound_obligations"][0]["base"]["amount_display"] == "¥420,000.00"
    assert counter_a["obligations"][0]["rate_display"] == "0.85%"


def test_owner_clean_early_pay_turn_reports_the_autonomy_proof(client):
    v = Chat(client, "own-clean").say(f"Foshan sent this: \"{CLEAN}\" What do you think?")["verdict"]
    au = v["autonomy"]
    assert (au["eligible"], au["accepted_alone"], au["whole_invoice"], au["gaps"]) == (True, True, True, [])
    assert au["covered"][0].startswith("early payment of ¥420,000.00 of RCV-A at 0.60%")


def test_counterparty_response_is_the_allow_list_and_has_no_supplier_side_figures(client):
    r = Chat(client, "cp-ex01", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(EX01)
    assert set(r) == ALLOW
    assert r["verdict"] is None
    dumped = json.dumps(r, ensure_ascii=False)
    for leak in ("annual", "passed_checks", "autonomy", "10.43", "10.84", "6.40"):
        assert leak not in dumped, leak
