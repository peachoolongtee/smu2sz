"""The queue for Deals (map #121, ticket #127): `GET /deals` returns `queue`, the worklist's own rows in three tiers by who owes the next step
(Needs you, Waiting, Agreements), one row per task, each with its own identity and link; and the state vocabulary is one across reads
(AUTHORIZATION_REQUIRED is "Waiting for your approval" everywhere, a buyer's clarification is not the owner's decision, RECEIVED is a decision,
the approvals read's tier is the record's). On the Demo and on the busy company, in both languages."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview, offer_picture, worklist
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import agree_on_rcv_a, english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
EX01 = {"fixture_id": "EX01_PACKAGE"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Zhuhai Kitchenware Wholesale Co.", "Zhuhai",
         "Bank credit line", "Invoice financing (onboarded platform)", "Buyer early-payment offer",
         "Government-guaranteed working-capital loan"]
ROW = {"key", "kind", "tier", "customer_id", "customer_short", "subject_text", "subject_demo_text", "lifecycle", "status_text", "consequence_text",
       "severity", "deadline_day", "expected_day", "differentiator_text", "decision_id", "invoice_id", "approval_id", "href"}


@pytest.fixture
def rt() -> Iterator[Runtime]:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    for clear in (worklist.clear_cache, customer_overview.clear_cache, offer_picture._cache.clear):
        clear()
    yield runtime
    set_runtime(None)
    for clear in (worklist.clear_cache, customer_overview.clear_cache, offer_picture._cache.clear):
        clear()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _queue(api: TestClient, lang: str = "en") -> dict[str, Any]:
    r = api.get("/deals", params={"lang": lang})
    assert r.status_code == 200, r.text
    q: dict[str, Any] = r.json()["queue"]
    return q


def _rows(q: dict[str, Any]) -> list[dict[str, Any]]:
    return [*q["needs_you"], *q["waiting"], *q["agreements"]]


def _busy(api: TestClient) -> None:
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200


def _shape(rows: list[dict[str, Any]]) -> dict[tuple[str, str | None], int]:
    out: dict[tuple[str, str | None], int] = {}
    for r in rows:
        out[(r["kind"], r["customer_id"])] = out.get((r["kind"], r["customer_id"]), 0) + 1
    return out


# ---------------------------------------------------------------- the queue


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_demo_queue_is_empty_until_an_offer_arrives_and_then_one_row_per_offer(api: TestClient, lang: str) -> None:
    q = _queue(api, lang)
    assert q["counts"] == {"needs_you": 0, "waiting": 0, "agreements": 0, "customers": 2}
    assert not q["needs_you"] and not q["waiting"] and not q["agreements"]
    for fixture in ("EX01_PACKAGE", "EX02_EARLY_1_5"):  # two negotiations of one customer
        offer_id = api.post("/offers", json={"fixture_id": fixture}).json()["offer"]["offer_id"]
        api.post(f"/offers/{offer_id}/evaluate", json={"fixture_id": fixture})
    q = _queue(api, lang)
    rows = q["needs_you"]
    assert [r["kind"] for r in rows] == ["DECISION", "DECISION"] and len({r["decision_id"] for r in rows}) == 2
    assert {r["customer_id"] for r in rows} == {"BUYER-1"} and q["counts"]["needs_you"] == 2
    for r in rows:
        assert set(r) == ROW and r["tier"] == "NEEDS_YOU" and r["href"] == f"/deals?customer=BUYER-1&decision={quote(r['decision_id'], safe='')}"
    if lang == "zh":
        # (a subject may quote the buyer's own words, which stay in the language the buyer wrote them in)
        assert not english_leaks([{k: re.sub("“[^”]*”", "", r[k]) for k in ("subject_text", "status_text", "consequence_text")} for r in rows], NAMES)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_busy_queue_has_every_task_in_its_tier(api: TestClient, lang: str) -> None:
    _busy(api)
    q = _queue(api, lang)
    # the busy seed holds no agreement: three Foshan replies (EX01, EX02, EX03) are all live on invoice RCV-A, and the owner can send any of them
    assert q["counts"] == {"needs_you": 7, "waiting": 1, "agreements": 0, "customers": 3}
    assert _shape(q["needs_you"]) == {("DECISION", "BUYER-1"): 3, ("DECISION", "BUYER-2"): 1, ("DECISION", "BUYER-3"): 1,
                                      ("APPROVAL", None): 1, ("COLLECTION", "BUYER-2"): 1}
    assert _shape(q["waiting"]) == {("BUYER_REPLY", "BUYER-1"): 1}
    assert q["agreements"] == []
    assert {r["tier"] for r in q["needs_you"]} == {"NEEDS_YOU"} and {r["tier"] for r in q["waiting"]} == {"WAITING"}
    rows = _rows(q)
    assert all(set(r) == ROW for r in rows) and len({r["key"] for r in rows}) == 8
    assert q["alert"] is not None and q["alert"]["key"] == "company-cash"  # shown above the tabs, counted nowhere
    assert q["needs_you_empty_text"] and q["waiting_empty_text"] and q["agreements_empty_text"]
    if lang == "zh":
        assert not english_leaks([{k: re.sub("“[^”]*”", "", r[k]) for k in ("subject_text", "status_text", "consequence_text")} for r in rows], NAMES)


def test_the_open_negotiations_of_one_customer_are_rows_of_their_own_with_their_own_links(api: TestClient) -> None:
    _busy(api)
    q = _queue(api)
    foshan = [r for r in q["needs_you"] if r["kind"] == "DECISION" and r["customer_id"] == "BUYER-1"]
    assert len(foshan) == 3 and len({r["decision_id"] for r in foshan}) == 3
    assert [r["href"] for r in foshan] == [f"/deals?customer=BUYER-1&decision={quote(r['decision_id'], safe='')}" for r in foshan]
    assert foshan[0]["subject_text"] and foshan[0]["href"] != foshan[1]["href"]
    assert all(r["decision_id"].startswith("deal:") and "OFF-" not in r["subject_text"] for r in foshan)


def test_every_row_links_to_its_own_task_and_never_to_another_rows_context(api: TestClient) -> None:
    _busy(api)
    agree_on_rcv_a(api)  # an agreement and its promise, for the Agreements tier
    by_kind: dict[str, dict[str, Any]] = {r["kind"]: r for r in _rows(_queue(api)) if r["kind"] not in ("DECISION",)}
    approval = by_kind["APPROVAL"]
    assert approval["approval_id"] and approval["href"] == f"/approvals#approval-{approval['approval_id']}"
    collection = by_kind["COLLECTION"]
    assert collection["invoice_id"] in ("RCV-B1", "RCV-B2")
    assert collection["href"] == f"/receivables?customer=BUYER-2&invoice={collection['invoice_id']}&from=deals"
    reply = by_kind["BUYER_REPLY"]
    assert reply["href"] == f"/deals?customer=BUYER-1&decision={quote(reply['decision_id'], safe='')}"
    agreement, promise = by_kind["AGREEMENT"], by_kind["PROMISE"]
    assert agreement["decision_id"] == promise["decision_id"] and agreement["decision_id"].startswith("deal:")
    assert promise["invoice_id"] == "RCV-A" and promise["href"].endswith("&invoice=RCV-A") and promise["expected_day"] is not None
    assert agreement["status_text"] == "Agreed" and agreement["consequence_text"]


def test_the_worklist_the_home_reads_is_unchanged(api: TestClient) -> None:
    _busy(api)
    w = api.get("/worklist").json()
    assert set(w) == {"lang", "day", "state_version", "alert", "counts", "needs_you", "needs_you_empty_text", "waiting", "customers", "partial"}
    assert w["counts"] == {"needs_you": 7, "waiting": 1, "agreements": 0, "customers": 3}
    assert {r["kind"] for r in w["waiting"]} == {"BUYER_REPLY"}
    assert all("tier" not in r and "decision_id" not in r for r in w["needs_you"] + w["waiting"])


# ---------------------------------------------------------------- one vocabulary


def _queued_counter(api: TestClient) -> str:
    """Option B of EX01 proposed as a commitment and recorded as the agent would: it needs the owner, so it waits in the approvals queue."""
    api.post("/demo/reset", json={})
    offer_id = api.post("/offers", json=EX01).json()["offer"]["offer_id"]
    ev = api.post(f"/offers/{offer_id}/evaluate", json=EX01).json()
    verdict = ev.get("verdict", ev)
    commitment = get_runtime().executor.propose_commitment(verdict["id"], expires_day=14, counter_id=verdict["counters"][1]["id"])
    version = api.get("/mandate").json()["mandate"]["version"]
    r = api.post("/operations", headers=AGENT, json={"kind": "RECORD_COMMITMENT", "op_id": "rec-1", "idempotency_key": "rec-1",
                                                      "mandate_version": version, "requested_by": "AGENT", "commitment_id": commitment.id,
                                                      "nonce": commitment.nonce})
    assert r.status_code == 200 and r.json()["result"]["status"] == "PENDING_APPROVAL", r.text
    return str(offer_id)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_an_offer_waiting_for_approval_is_waiting_for_your_approval_everywhere(api: TestClient, lang: str) -> None:
    offer_id = _queued_counter(api)
    said = {"en": "Waiting for your approval", "zh": "等待您批准"}[lang]
    deal = next(d for d in api.get("/deals", params={"lang": lang}).json()["deals"] if d["counterparty_id"] == "BUYER-1")
    offer = deal["open_offer"]
    assert offer["offer_id"] == offer_id and offer["action_text"] == said + {"en": ".", "zh": "。"}[lang]
    now = [s["key"] for s in offer["stages"] if s["state"] == "now"]
    assert now == ["reply_ready"] and offer["tone"] == "warn"  # the owner owes the step: not "Sent"
    assert deal["needs_you"] is True and deal["needs_you_text"] == {"en": "An approval is waiting for you", "zh": "有一项批准等待您处理"}[lang]
    record = next(d for d in api.get("/decisions", params={"lang": lang}).json()["decisions"] if d["id"] == f"deal:{offer_id}")
    assert record["state"] == "AUTHORIZATION_REQUIRED" and record["state_text"] == said
    q = _queue(api, lang)
    approval = next(r for r in q["needs_you"] if r["kind"] == "APPROVAL")
    assert approval["status_text"] == said and approval["decision_id"] == f"deal:{offer_id}" and approval["customer_id"] == "BUYER-1"
    assert not any(r["decision_id"] == f"deal:{offer_id}" for r in q["waiting"]) and q["counts"]["needs_you"] == 1
    home = api.get("/home", params={"lang": lang}).json()["deals_card"]
    assert [r["status_text"] for r in home["rows"] if r["buyer_id"] == "BUYER-1"] == [said]
    queue_row = api.get("/approvals/queue", params={"lang": lang}).json()["approvals"][0]
    assert queue_row["presentation"]["result_state_text"] == said
    overview = api.get("/customers/BUYER-1/overview", params={"lang": lang}).json()["decision"]
    assert overview["kind"] == "approval" and overview["eyebrow"] == said
    assert overview["primary"]["href"] == f"/approvals#approval-{queue_row['id']}"


def test_the_clarification_wording_when_it_is_the_only_open_offer(api: TestClient) -> None:
    offer_id = api.post("/offers", json={"fixture_id": "EX07_CONFLICT"}).json()["offer"]["offer_id"]
    api.post(f"/offers/{offer_id}/evaluate", json={"fixture_id": "EX07_CONFLICT"})
    for lang, eyebrow in (("en", "Waiting for the buyer"), ("zh", "等待买方")):
        d = api.get("/customers/BUYER-1/overview", params={"lang": lang}).json()["decision"]
        assert d["kind"] == "awaiting_buyer" and d["eyebrow"] == eyebrow
        assert d["primary"]["href"] == f"/deals?decision=deal%3A{offer_id}"
        assert "waits for you" not in d["eyebrow"] and "等待您" not in d["eyebrow"]
    row = next(d for d in api.get("/deals").json()["deals"] if d["counterparty_id"] == "BUYER-1")
    assert row["needs_you"] is False and row["open_offer"]["action_text"] == "The buyer needs to clarify first."
    q = _queue(api)
    assert [r["kind"] for r in q["waiting"]] == ["BUYER_REPLY"] and not q["needs_you"]


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_received_is_a_decision_on_the_record(api: TestClient, lang: str) -> None:
    offer_id = api.post("/offers", json=EX01).json()["offer"]["offer_id"]  # received, not evaluated
    rows = api.get("/decisions", params={"lang": lang}).json()["decisions"]
    row = next(d for d in rows if d["id"] == f"deal:{offer_id}")
    assert row["state"] == "RECEIVED" and row["state_text"] == {"en": "Received; not evaluated yet", "zh": "已收到，尚未评估"}[lang]
    assert row["terminal"] is False and any(d["id"] == row["id"] for d in api.get("/decisions", params={"open": "true"}).json()["decisions"])
    assert api.get("/decisions/" + quote(row["id"], safe=""), params={"lang": lang}).json()["state"] == "RECEIVED"
    api.post(f"/offers/{offer_id}/evaluate", json=EX01)
    assert sum(1 for d in api.get("/decisions").json()["decisions"] if d["id"] == f"deal:{offer_id}") == 1  # once evaluated it is no longer listed twice


def test_the_approvals_tier_is_the_records_not_a_constant(api: TestClient) -> None:
    _queued_counter(api)
    row = api.get("/approvals/queue").json()["approvals"][0]
    detail = api.get(f"/decisions/{quote(row['decision_id'], safe='')}").json()
    assert detail["authorization"]["required_tier"] is not None and row["tier"] == detail["authorization"]["required_tier"]
