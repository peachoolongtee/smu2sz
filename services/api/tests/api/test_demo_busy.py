"""The busy company (POST /demo/reset?scenario=busy): the golden books plus six more customers and two overdue invoices, opened mid-conversation.

The scenario's seed file (`fixtures/scenarios/busy.seed.json`) is replayed after the books are seeded, through the functions the routes
call: eleven offers submitted and evaluated (six from the first three customers, one from each of the five newer ones), one facility
application queued for the owner. No deal is negotiated: Foshan's three replies (EX01,
EX02, EX03) are all about invoice RCV-A and any one sent makes the others lapse, so the day-0 books keep all three live and sendable (the
cooperative buyer cannot agree Dongguan's rebate, EX08B, which has no counter to send). What is pinned is the shape of the day-0 worklist (tiers, kinds, customers and counts), not the words or the money in it."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import agree_on_rcv_a

OWNER = {"X-Owner-Token": "demo-owner-token"}
SEEDED = ["EX01_PACKAGE", "EX02_EARLY_1_5", "EX03_AS_USUAL", "EX07_CONFLICT", "EX08B_JOINT_BUYER2", "EX09_TERMS_BUYER3",
          "EX13_EARLY_BUYER4", "EX14_TERMS_BUYER5", "EX15_REBATE_BUYER6", "EX16_PACKAGE_BUYER7", "EX17_CLAIMED_REBATE_BUYER8"]
NEWER = ["BUYER-4", "BUYER-5", "BUYER-6", "BUYER-7", "BUYER-8"]  # each on a supply agreement in fixtures/contracts/


@pytest.fixture
def rt(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
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


def _busy(api: TestClient) -> None:
    r = api.post("/demo/reset", params={"scenario": "busy"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "scenario": "busy", "day": 0}


def _worklist(api: TestClient) -> dict[str, Any]:
    r = api.get("/worklist")
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _shape(rows: list[dict[str, Any]]) -> Counter[tuple[str, str | None]]:
    return Counter((r["kind"], r["customer_id"]) for r in rows)


def test_the_day_zero_worklist(api: TestClient) -> None:
    _busy(api)
    w = _worklist(api)
    assert w["day"] == 0
    # Needs you: the ten open decisions (three Foshan, Dongguan, Zhuhai, one for each of the five newer customers), the facility approval, and Dongguan's overdue invoices
    assert _shape(w["needs_you"]) == Counter({
        ("DECISION", "BUYER-1"): 3, ("DECISION", "BUYER-2"): 1, ("DECISION", "BUYER-3"): 1,
        **{("DECISION", b): 1 for b in NEWER}, ("APPROVAL", None): 1, ("COLLECTION", "BUYER-2"): 1})
    # Waiting: the buyer's reply to the conflicting message; no agreement is in force, so no promised payment
    assert _shape(w["waiting"]) == Counter({("BUYER_REPLY", "BUYER-1"): 1})
    assert w["counts"] == {"needs_you": 12, "waiting": 1, "agreements": 0, "customers": 8}
    assert w["alert"] is not None and w["alert"]["key"] == "company-cash"
    assert all(r["owner"] == "NEEDS_YOU" for r in w["needs_you"]) and all(r["owner"] == "WAITING" for r in w["waiting"])
    assert len({r["key"] for r in w["needs_you"] + w["waiting"]}) == 13


def test_the_approval_is_the_facility_application_and_no_deal_is_agreed(api: TestClient, rt: Runtime) -> None:
    _busy(api)
    [pending] = rt.store.approvals("PENDING")
    assert '"FAC-GGL"' in pending.op_json and '"APPLY_FOR_FACILITY"' in pending.op_json
    [row] = [r for r in _worklist(api)["needs_you"] if r["kind"] == "APPROVAL"]
    assert row["key"] == f"approval:{pending.id}"
    assert rt.store.commitments() == []


def test_a_send_on_rcv_a_agrees_one_deal_and_the_waiting_count_leaves_the_promise_to_agreements(api: TestClient, rt: Runtime) -> None:
    """Sending one of Foshan's replies agrees the deal and promises its payment; the promise's row stays in `waiting[]` but is counted under
    Agreements, as the Deals queue counts it, so the Home and Deals agree."""
    _busy(api)
    agree_on_rcv_a(api)
    [agreement] = rt.store.commitments()
    assert agreement.status.value in ("ACCEPTED", "ACTIVE")
    w = _worklist(api)
    [promise] = [r for r in w["waiting"] if r["kind"] == "PROMISE"]
    assert promise["key"].startswith(f"promise:{agreement.id}:")
    q = api.get("/deals").json()["queue"]
    # Funding Foshan's deal finances one of the newer customers' invoices, so its arranged lot waits too (a SETTLEMENT row).
    assert w["counts"] == q["counts"] == {"needs_you": 9, "waiting": 2, "agreements": 1, "customers": 8}
    assert sorted(r["kind"] for r in w["waiting"]) == ["BUYER_REPLY", "PROMISE", "SETTLEMENT"]
    assert len(w["waiting"]) == 3 and w["counts"]["waiting"] == len(w["waiting"]) - 1


def test_every_offer_was_submitted_and_evaluated_in_the_seeds_order(api: TestClient, rt: Runtime) -> None:
    _busy(api)
    verdicts = rt.store.verdicts()
    assert len(verdicts) == len({v.offer_id for v in verdicts}) == len(SEEDED)
    outcomes = Counter(v.outcome.value for v in verdicts)
    assert outcomes == Counter({"REJECT": 3, "COUNTER": 2, "NO_VERDICT": 1, "NEEDS_OWNER_APPROVAL": 5})
    [zhuhai] = [v for v in verdicts if (rt.store.get_offer(v.offer_id) or pytest.fail("offer missing")).counterparty_id == "BUYER-3"]
    assert zhuhai.outcome.value == "NEEDS_OWNER_APPROVAL"


def test_eight_customers_and_two_overdue_invoices(api: TestClient) -> None:
    _busy(api)
    customers = api.get("/customers").json()["customers"]
    assert {c["customer_id"] for c in customers} == {"BUYER-1", "BUYER-2", "BUYER-3", *NEWER}
    assert len(customers) == 8
    rows = api.get("/receivables").json()["rows"]
    late = [r for r in rows if r["collection_state"] == "OVERDUE"]
    assert sorted((r["receivable_id"], r["buyer_id"], r["days_late"]) for r in late) == [("RCV-B1", "BUYER-2", 30), ("RCV-B2", "BUYER-2", 15)]
    assert {r["buyer_id"] for r in rows} == {"BUYER-1", "BUYER-2", "BUYER-3", *NEWER}


def test_the_busy_books_confirm_the_golden_documents_and_the_newer_customers_contracts(api: TestClient, rt: Runtime) -> None:
    """The three golden documents and the five supply agreements written for the busy books, each read and confirmed; every
    supply agreement matches its customer's books (the deal summary's checks warn of nothing)."""
    _busy(api)
    fixtures = [f["id"] for f in api.get("/fixtures/contracts").json()["contracts"]]
    assert fixtures[:3] == ["FHR_SUPPLY_AGREEMENT", "MB_CREDIT_LINE_AGREEMENT", "GBR_INVOICE_FINANCING_AGREEMENT"] and len(fixtures) == 8
    rows = rt.store.contract_guard_rows()
    assert len(rows) == 8 and all(r.status == "CONFIRMED" for r in rows)
    assert {r.counterparty_id for r in rows if r.kind == "BUYER_CONTRACT"} == {"BUYER-1", *NEWER}
    from app.deals import deal_summary

    for b in NEWER:
        checks = deal_summary(rt.store, b, rt.day)["checks"]
        assert checks and all(c["status"] != "warn" for c in checks), (b, checks)


def test_the_golden_books_list_only_their_own_documents(api: TestClient) -> None:
    api.post("/demo/reset")
    assert [f["id"] for f in api.get("/fixtures/contracts").json()["contracts"]] == [
        "FHR_SUPPLY_AGREEMENT", "MB_CREDIT_LINE_AGREEMENT", "GBR_INVOICE_FINANCING_AGREEMENT"]
    r = api.post("/documents", json={"fixture_id": "TL_CNC_SUPPLY_AGREEMENT"})
    assert r.status_code == 404 and r.json()["detail"]["code"] == "UNKNOWN_FIXTURE"


def test_the_golden_buyers_figures_are_unchanged(api: TestClient, rt: Runtime) -> None:
    """EX01 evaluates on the bare busy books to the verdict the golden books give it (after the seed, the agreed deal has changed the invoice)."""
    from app.domain.fixtures import load_scenario

    golden, _ = load_scenario("golden_sme")
    busy, _ = load_scenario("busy")
    for field in ("receivables", "recurring_invoices", "expected_orders"):
        mine = [x for x in getattr(busy, field) if x.counterparty_id == "BUYER-1"]
        assert mine == [x for x in getattr(golden, field) if x.counterparty_id == "BUYER-1"]
    rt.reset("busy")
    fixture = "EX01_PACKAGE"
    offer = api.post("/offers", json={"fixture_id": fixture}).json()["offer"]
    v = api.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": fixture}).json()
    assert v["outcome"] == "REJECT"
    assert {x["code"] for x in v["violations"]} == {"AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH", "DISCOUNT_ABOVE_BREAK_EVEN",
                                                     "EARLY_PAY_DEARER_THAN_PLAN"}
    assert v["forward_concession"]["total_fen"] == 2832692


def test_a_second_reset_starts_over_from_the_same_day_zero(api: TestClient, rt: Runtime) -> None:
    _busy(api)
    first = _worklist(api)
    _busy(api)
    again = _worklist(api)
    assert again["counts"] == first["counts"] and _shape(again["needs_you"]) == _shape(first["needs_you"])
    assert len(rt.store.verdicts()) == len(SEEDED) and len(rt.store.commitments()) == 0 and len(rt.store.approvals("PENDING")) == 1


def test_a_scenario_without_a_seed_file_is_not_replayed(api: TestClient, rt: Runtime) -> None:
    assert api.post("/demo/reset", params={"scenario": "short_facilities"}).status_code == 200
    assert rt.store.verdicts() == [] and rt.store.commitments() == [] and rt.store.approvals() == []
    assert api.post("/demo/reset").status_code == 200
    assert rt.store.verdicts() == [] and rt.store.commitments() == []


def test_a_failing_step_is_a_500_that_names_it_and_leaves_the_plain_books(api: TestClient, rt: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    broken = {"offers": ["EX02_EARLY_1_5", "EX99_NOT_A_FIXTURE"]}
    monkeypatch.setattr("app.api.demo_seed.scenario_seed", lambda name: broken)
    r = api.post("/demo/reset", params={"scenario": "busy"})
    assert r.status_code == 500
    detail = r.json()["detail"]
    assert detail["code"] == "DEMO_SEED_FAILED" and detail["step"] == "offers[1] EX99_NOT_A_FIXTURE: submit"
    assert "EX99_NOT_A_FIXTURE" in detail["message"]
    # nothing of the first step stands: the books are the scenario's own, as a plain reset leaves them
    assert rt.store.verdicts() == [] and rt.store.commitments() == [] and rt.latest_verdict == {}
    assert rt.scenario == "busy"


def test_a_negotiation_of_an_offer_the_seed_did_not_submit_is_refused_by_name(api: TestClient, rt: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = {"offers": ["EX02_EARLY_1_5"], "negotiate": [{"offer": "EX03_AS_USUAL"}]}
    monkeypatch.setattr("app.api.demo_seed.scenario_seed", lambda name: bad)
    r = api.post("/demo/reset", params={"scenario": "busy"})
    assert r.status_code == 500 and r.json()["detail"]["step"] == "negotiate[0] EX03_AS_USUAL"
    assert rt.store.verdicts() == []


def test_an_invalid_seed_file_is_a_500_not_a_silent_skip(api: TestClient, rt: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.demo_seed.scenario_seed", lambda name: {"offerz": []})
    r = api.post("/demo/reset", params={"scenario": "busy"})
    assert r.status_code == 500 and r.json()["detail"]["step"] == "seed file"


# ---------------------------------------------------------------- the scenario allowlist


def test_the_four_demo_scenarios_are_accepted(api: TestClient) -> None:
    for name in ("golden_sme", "short_facilities", "public_sme"):
        r = api.post("/demo/reset", params={"scenario": name})
        assert r.status_code == 200 and r.json()["scenario"] == name, (name, r.text)


@pytest.mark.parametrize("name", ["nope", "", "../golden_sme", "golden_sme.events", "busy.seed"])
def test_any_other_name_is_a_422_that_wipes_nothing(api: TestClient, rt: Runtime, name: str) -> None:
    _busy(api)
    before = (len(rt.store.verdicts()), len(rt.store.commitments()), len(rt.store.approvals("PENDING")))
    r = api.post("/demo/reset", params={"scenario": name})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "UNKNOWN_SCENARIO" and detail["scenarios"] == ["golden_sme", "short_facilities", "public_sme", "busy"]
    assert "Nothing was reset" in detail["message"] and "没有名为" in api.post("/demo/reset", params={"scenario": name, "lang": "zh"}).json()["detail"]["message_when"]
    assert (len(rt.store.verdicts()), len(rt.store.commitments()), len(rt.store.approvals("PENDING"))) == before
    assert rt.scenario == "busy"
