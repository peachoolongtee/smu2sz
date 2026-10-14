"""ADR-0013, phase 4: the owner's commitment to a confirmed capex contract's payment schedule. Always Tier 2; checked when
queued and again, by the executor, when the owner approves; booked as scheduled CAPEX flows the clock pays on their days."""

from __future__ import annotations

import pytest

from app.domain.models import FlowKind, Mode

TIMELINE = {"signing_day": 20, "delivery_day": 60, "acceptance_day": 80}


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")


@pytest.fixture
def rt(client):  # the runtime the `client` fixture installed
    from app.api.runtime import get_runtime

    return get_runtime()


def _confirmed(client) -> dict:  # type: ignore[no-untyped-def]
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    return client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]}).json()["document"]


def _evaluate(client, doc_id: str, timeline: dict | None = None) -> dict:  # type: ignore[no-untyped-def]
    r = client.post(f"/capex/contracts/{doc_id}/evaluate", json={"timeline": timeline or TIMELINE})
    assert r.status_code == 200, r.text
    return r.json()


def _commit(client, doc_id: str, schedule_hash: str, timeline: dict | None = None, early: bool = False):  # type: ignore[no-untyped-def]
    return client.post(f"/capex/contracts/{doc_id}/commit",
                       json={"timeline": timeline or TIMELINE, "schedule_hash": schedule_hash, "take_early_pay": early})


def _capex_flows(rt) -> list[tuple[str, int, int]]:  # type: ignore[no-untyped-def]
    return [(f.id, f.day, f.amount_fen) for f in rt.store.get_state().flows if f.kind == FlowKind.CAPEX]


def test_commit_queues_for_the_owner_and_books_nothing_until_approved(client, on, rt):
    d = _confirmed(client)
    ev = _evaluate(client, d["id"])
    before = rt.store.get_state()
    r = _commit(client, d["id"], ev["schedule"]["schedule"]["schedule_hash"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "PENDING_APPROVAL" and body["result"]["tier"] == "TIER_2"
    assert body["result"]["kind"] == "COMMIT_PURCHASE" and body["approval_id"]
    assert rt.store.get_state() == before and _capex_flows(rt) == []
    queued = [a for a in client.get("/approvals/queue").json()["approvals"] if a["id"] == body["approval_id"]]
    assert queued and queued[0]["operation"]["document_id"] == d["id"]
    assert queued[0]["operation"]["requested_by"] == "AGENT"


def test_the_owners_approval_books_the_payments_and_registers_the_vendor(client, on, rt):
    d = _confirmed(client)
    ev = _evaluate(client, d["id"])
    aid = _commit(client, d["id"], ev["schedule"]["schedule"]["schedule_hash"]).json()["approval_id"]
    ok = client.post(f"/approvals/{aid}", json={"decision": "APPROVE"}).json()["result"]
    assert ok["status"] == "EXECUTED", ok
    doc = d["id"]
    assert _capex_flows(rt) == [(f"CAPEX:{doc}:1", 20, -18_000_000), (f"CAPEX:{doc}:2", 105, -36_000_000),
                                (f"CAPEX:{doc}:3", 440, -6_000_000)]
    vendor = next(c for c in rt.store.get_state().counterparties if c.id == "VENDOR-GZPM")
    assert (vendor.role, vendor.name, vendor.known) == ("SUPPLIER", "Guangzhou Precision Machinery Co., Ltd.", True)
    ledger = client.get("/ledger").json()
    assert ledger["chain_valid"] and ledger["operations"][-1]["kind"] == "COMMIT_PURCHASE"


def test_the_early_payment_schedule_can_be_committed(client, on, rt):
    d = _confirmed(client)
    ev = _evaluate(client, d["id"])
    assert ev["early_pay"]["take"] is True
    aid = _commit(client, d["id"], ev["early_pay_schedule"]["schedule_hash"], early=True).json()["approval_id"]
    assert client.post(f"/approvals/{aid}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    assert [(day, amount) for _, day, amount in _capex_flows(rt)] == [(20, -18_000_000), (65, -35_280_000),
                                                                      (440, -6_000_000)]


def test_a_schedule_not_the_one_shown_is_refused_at_once(client, on, rt):
    d = _confirmed(client)
    ev = _evaluate(client, d["id"])
    other = {**TIMELINE, "delivery_day": 61}  # the owner changed the timeline but sends the old hash
    r = _commit(client, d["id"], ev["schedule"]["schedule"]["schedule_hash"], timeline=other)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "SCHEDULE_CHANGED"
    r = _commit(client, d["id"], ev["schedule"]["schedule"]["schedule_hash"], early=True)  # the plain hash, early flag
    assert r.status_code == 409
    assert client.get("/approvals/queue").json()["approvals"] == []


def test_an_unconfirmed_reading_cannot_be_committed(client, on):
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    ev = _evaluate(client, d["id"])
    r = _commit(client, d["id"], ev["schedule"]["schedule"]["schedule_hash"])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "NOT_CONFIRMED"


def test_a_missing_day_cannot_be_committed(client, on):
    d = _confirmed(client)
    r = _commit(client, d["id"], "0" * 64, timeline={"signing_day": 20})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "NO_SCHEDULE"
    assert r.json()["detail"]["needs"] == ["delivery_day", "acceptance_day"]


def test_a_purchase_is_committed_once(client, on, rt):
    d = _confirmed(client)
    ev = _evaluate(client, d["id"])
    h = ev["schedule"]["schedule"]["schedule_hash"]
    aid = _commit(client, d["id"], h).json()["approval_id"]
    client.post(f"/approvals/{aid}", json={"decision": "APPROVE"})
    again = _commit(client, d["id"], h).json()  # the same request: the executor answers with the original
    assert again["status"] == "DUPLICATE"
    other = {**TIMELINE, "delivery_day": 61}
    h2 = _evaluate(client, d["id"], other)["schedule"]["schedule"]["schedule_hash"]
    aid2 = _commit(client, d["id"], h2, timeline=other).json()["approval_id"]
    refused = client.post(f"/approvals/{aid2}", json={"decision": "APPROVE"}).json()["result"]
    assert refused["status"] == "REFUSED" and "already committed" in refused["message"]
    assert len(_capex_flows(rt)) == 3


def test_approval_after_a_payment_day_has_passed_books_nothing(client, on, rt):
    d = _confirmed(client)
    ev = _evaluate(client, d["id"])
    aid = _commit(client, d["id"], ev["schedule"]["schedule"]["schedule_hash"]).json()["approval_id"]
    assert client.post("/clock/advance", json={"to_day": 25}).status_code == 200  # the signing payment (day 20) is past
    refused = client.post(f"/approvals/{aid}", json={"decision": "APPROVE"}).json()["result"]
    assert refused["status"] == "REFUSED" and "before today" in refused["message"]
    assert _capex_flows(rt) == []


def test_committed_payments_are_projected_and_paid_by_the_clock(client, on, rt):
    from app.books import books_from_store
    from app.financial import project

    d = _confirmed(client)
    ev = _evaluate(client, d["id"])
    aid = _commit(client, d["id"], ev["schedule"]["schedule"]["schedule_hash"]).json()["approval_id"]
    client.post(f"/approvals/{aid}", json={"decision": "APPROVE"})
    books = books_from_store(rt.store)
    mandate = rt.store.get_mandate()
    traj = project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, mandate.horizon_days,
                   mandate.min_cash_fen)
    day20 = next(p for p in traj.days if p.day == 20)
    assert any(e.ref == f"CAPEX:{d['id']}:1" and e.amount_fen == -18_000_000 for e in day20.events)
    adv = client.post("/clock/advance", json={"to_day": 21}).json()
    assert f"CAPEX:{d['id']}:1" not in [f.id for f in rt.store.get_state().flows]
    assert f"CAPEX:{d['id']}:1" in str(adv)
    assert [i for i, _, _ in _capex_flows(rt)] == [f"CAPEX:{d['id']}:2", f"CAPEX:{d['id']}:3"]


def test_the_approval_card_says_what_is_authorized(client, on):
    d = _confirmed(client)
    ev = _evaluate(client, d["id"])
    aid = _commit(client, d["id"], ev["schedule"]["schedule"]["schedule_hash"]).json()["approval_id"]
    card = next(a for a in client.get("/approvals/queue").json()["approvals"] if a["id"] == aid)
    assert card["presentation"]["headline"] == "Commit to the ¥600,000 equipment purchase"
    assert card["presentation"]["what"] == "Book the ¥600,000.00 equipment purchase on the contract's payment days"
    assert card["tier"] == "TIER_2" and card["decision_state"] == "AUTHORIZATION_REQUIRED"
