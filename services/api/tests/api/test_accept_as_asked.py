"""Accept as asked (map #121): `POST /offers/{id}/accept` and `POST /offers/{id}/decline`, the `accept` block of the offer picture and the workspace, and
what the decision record, the queue, the approvals history and Activity say afterwards.

A request that needs the owner's review (the busy books' Zhuhai 75-day terms and Dongguan rebate: NEEDS_OWNER_APPROVAL, no counter) had no way to be
answered. The accept runs the executor's AcceptOffer under the OWNER's authority and the owner's click is the approval; the decline runs RejectOffer. A
request over a limit the owner signed is 409 OVER_MANDATE, whatever the click."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview, offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.commitments import terms_hash
from app.config import get_settings
from app.domain.models import ObligationType, Outcome, Tier
from app.mandate.fixture import demo_owner_public_key_hex
from app.operations.executor import committable
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import agree_on_rcv_a, english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
ZHUHAI, DONGGUAN, FOSHAN_1, FOSHAN_3 = "EX09_TERMS_BUYER3", "EX08B_JOINT_BUYER2", "EX01_PACKAGE", "EX03_AS_USUAL"
CONSOLIDATE = "EX05_CONSOLIDATE"  # the golden books' own request for the owner's review: Foshan's consolidated terms (NEEDS_OWNER_APPROVAL, no counter)
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Zhuhai Kitchenware Wholesale Co.", "Zhuhai"]
ID = re.compile(r"\b(?:OFF|CMT|APR|VER|CTR|BUYER|RCV|FAC)-[\w-]+|\bNone\b|\bnull\b")
RECEIPT_FIELDS = ["authorizes_text", "executes_now_text", "others_must_agree_text", "in_hand_vs_future_text", "gross_display", "fees_display",
                  "net_display", "when_text", "assumptions_text", "authority_text", "remaining_text"]


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


@pytest.fixture
def busy(api: TestClient) -> TestClient:
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    return api


def _evaluate(api: TestClient, fixture: str, lang: str = "en") -> tuple[str, dict[str, Any]]:
    offer_id: str = api.post("/offers", json={"fixture_id": fixture}).json()["offer"]["offer_id"]
    r = api.post(f"/offers/{offer_id}/evaluate", params={"lang": lang}, json={"fixture_id": fixture})
    assert r.status_code == 200, r.text
    return offer_id, r.json()


def _body(v: dict[str, Any], **more: Any) -> dict[str, Any]:
    return {"verdict_id": v["id"], "state_version": v["state_version"], **more}


def _detail(r: Any) -> dict[str, Any]:
    d: dict[str, Any] = r.json()["detail"]
    return d


def _books(api: TestClient) -> dict[str, Any]:
    """Everything an answer must leave alone when it is refused: the books, the log's length, the agreements and the approvals."""
    s = api.get("/state").json()["state"]
    ledger = api.get("/ledger").json()
    return {"cash": s["cash_fen"], "version": s["state_version"], "lots": s.get("lots"), "facilities": s.get("facilities"),
            "chain": ledger["chain_length"], "commitments": len(ledger["commitments"]),
            "approvals": [(a["id"], a["status"]) for a in api.get("/approvals/queue").json()["approvals"]]}


def _strings(x: Any) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [s for v in x.values() for s in _strings(v)]
    if isinstance(x, list):
        return [s for v in x for s in _strings(v)]
    return []


def _in_any_tier(api: TestClient) -> list[str]:
    return [k for keys in _queue_keys(api).values() for k in keys]


def _queue_keys(api: TestClient, lang: str = "en") -> dict[str, list[str]]:
    q = api.get("/deals", params={"lang": lang}).json()["queue"]
    return {tier: [r["key"] for r in q[tier]] for tier in ("needs_you", "waiting", "agreements")}


# ================================================================ the accept block, on the offer picture and in the workspace


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_picture_and_the_workspace_carry_one_accept_block_for_a_request_that_needs_the_owner(busy: TestClient, lang: str) -> None:
    offer_id, v = _evaluate(busy, ZHUHAI, lang)
    block = v["workspace"]["accept"]
    assert busy.get(f"/offers/{offer_id}/picture", params={"lang": lang}).json()["accept"] == block
    assert block["available"] is True and block["reason_text"] is None and block["authority"] == "needs_owner"
    assert block["decline_available"] is True
    assert list(block["receipt"]) == [*RECEIPT_FIELDS, "cash_text"]
    assert not any(ID.search(s) for s in _strings(block)), "no id, no None in a sentence the owner reads"
    if lang == "zh":
        assert english_leaks(block, NAMES) == []


def test_the_receipt_of_accepting_zhuhai_says_what_it_does_in_the_words_of_the_brief(busy: TestClient) -> None:
    _, v = _evaluate(busy, ZHUHAI)
    block = v["workspace"]["accept"]
    assert block["commit_label"] == "Accept as asked" and block["decline_label"] == "Decline the request"
    r = block["receipt"]
    assert r["authorizes_text"] == ("Accept Zhuhai's request as asked: 75-day terms on the next invoice; "
                                    "FLOW records the agreement under your authority.")
    assert r["executes_now_text"] == "Records the agreement now; no payment and no funding moves."
    assert r["others_must_agree_text"] == "Nobody else: these are the buyer's own terms."
    assert r["authority_text"] == "Above what FLOW may agree alone; your click is the approval."
    assert r["remaining_text"] == "Nothing remains open once recorded."
    # the cost words are the asked path's own, never added or invented; the lines the read has no word for are null
    path = next(p for p in busy.get(f"/offers/{v['workspace']['buyer']['offer_id']}/picture").json()["paths"] if p["key"] == "asked")
    assert r["fees_display"] == f"{path['cost_total_display']}, {path['cost_basis_text']}"
    assert r["in_hand_vs_future_text"] == f"Future cost of the terms you accept: {r['fees_display']}."
    assert r["gross_display"] is None and r["net_display"] is None
    assert r["when_text"] == "As soon as you confirm."


def test_the_chinese_receipt_is_the_same_receipt_in_chinese(busy: TestClient) -> None:
    _, en = _evaluate(busy, ZHUHAI)
    _, zh = _evaluate(busy, ZHUHAI, "zh")
    a, b = en["workspace"]["accept"], zh["workspace"]["accept"]
    assert {k: v for k, v in a.items() if k not in ("reason_text", "receipt", "commit_label", "decline_label")} == {
        k: v for k, v in b.items() if k not in ("reason_text", "receipt", "commit_label", "decline_label")}
    assert b["commit_label"] == "按对方要求接受" and b["decline_label"] == "拒绝该请求"
    assert [k for k, v in a["receipt"].items() if v is None] == [k for k, v in b["receipt"].items() if v is None]
    assert "您" in b["receipt"]["authority_text"] and b["receipt"]["authorizes_text"].startswith("按对方要求接受Zhuhai的请求：")


def test_a_request_over_a_signed_limit_is_not_available_and_says_why(busy: TestClient) -> None:
    offer_id, v = _evaluate(busy, FOSHAN_1)
    block = v["workspace"]["accept"]
    assert block["available"] is False and block["authority"] == "over_limit" and block["receipt"] is None
    assert block["reason_text"] == "Over a limit you signed: only a new mandate changes that."
    assert block["decline_available"] is True  # the owner can still close it
    # the picture's own words for the same class
    asked = next(p for p in busy.get(f"/offers/{offer_id}/picture").json()["paths"] if p["key"] == "asked")
    assert asked["authority"] == "over_limit" and asked["authority_text"].removesuffix(".") == block["reason_text"].removesuffix(".")


def test_a_counter_outcome_cannot_be_accepted_as_asked(busy: TestClient) -> None:
    _, v = _evaluate(busy, FOSHAN_3)
    assert v["outcome"] == Outcome.COUNTER.value
    block = v["workspace"]["accept"]
    assert block["available"] is False and block["reason_text"] == "FLOW cannot accept this as asked." and block["receipt"] is None


def test_a_lapsed_offers_block_says_the_offer_lapsed(busy: TestClient) -> None:
    offer_id, _ = _evaluate(busy, FOSHAN_1)
    agree_on_rcv_a(busy)
    pic = busy.get(f"/offers/{offer_id}/picture").json()
    assert pic["available"] is False
    block = pic["accept"]
    assert block["available"] is False and block["reason_text"] == pic["unavailable_text"] and block["receipt"] is None
    assert block["decline_available"] is False


# ================================================================ Zhuhai accepted as asked


def test_accepting_zhuhai_agrees_the_terms_under_the_owners_authority_and_nothing_funds(busy: TestClient) -> None:
    offer_id, v = _evaluate(busy, ZHUHAI)
    assert v["outcome"] == "NEEDS_OWNER_APPROVAL" and v["counters"] == []
    before = _books(busy)
    r = busy.post(f"/offers/{offer_id}/accept", json=_body(v))
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"decision", "receipt", "execution"}

    d = body["decision"]
    assert busy.get(f"/decisions/{d['id']}").json()["state"] == d["state"] == "AGREED"
    assert (d["lifecycle"], d["status_text"], d["terminal"]) == ("agreed", "Agreed", False)
    assert d["agreement"]["status"] == "ACTIVE" and d["response"]["sent"] is None
    assert d["response"]["accepted_as_asked"]["text"] == "You accepted the request as asked. Nothing was sent to the buyer."
    assert d["authorization"]["status"] == "APPROVED" and d["authorization"]["decided_by"] == "OWNER" and d["authorization"]["required_tier"] == "TIER_2"

    # the receipt is the agreement receipt, and it says that nothing funds
    assert body["receipt"] == d["agreement"]["receipt"] and list(body["receipt"]) == RECEIPT_FIELDS
    assert body["receipt"]["executes_now_text"] == "Agreement with Zhuhai Kitchenware Wholesale Co. recorded. No payment and no funding moved."
    assert body["receipt"]["authority_text"] == "You accepted it as asked; your click was the approval."
    assert body["execution"] == {"summary_text": body["receipt"]["executes_now_text"]}
    assert d["execution"]["requested_fen"] == 0 and d["settlement"] == []

    after = _books(busy)
    assert after["cash"] == before["cash"] and after["lots"] == before["lots"] and after["facilities"] == before["facilities"]  # no payment, no funding
    assert after["commitments"] == before["commitments"] + 1


def test_the_accepted_terms_are_the_agreement_exactly_as_the_verdict_bound_them(busy: TestClient, rt: Runtime) -> None:
    offer_id, v = _evaluate(busy, ZHUHAI)
    assert busy.post(f"/offers/{offer_id}/accept", json=_body(v)).status_code == 200
    verdict = rt.store.get_verdict(v["id"])
    assert verdict is not None
    [c] = [c for c in rt.store.commitments() if c.offer_id == offer_id]
    # EX09: 75-day terms on the buyer's next invoice, as bound; the commitment carries the verdict's terms and no more
    [ext] = c.obligations
    assert ext.type == ObligationType.TERMS_EXTENSION and ext.target_terms_days == 75 and ext.duration.invoices == 1
    assert c.terms_hash == terms_hash(committable(list(verdict.bound_obligations)))
    assert c.status.value == "ACTIVE" and c.verdict_id == v["id"] and c.counterparty_id == verdict.bound_obligations[0].counterparty_id
    assert c.forward_value_fen == v["forward_concession"]["total_fen"] > 0
    # the agreement is booked against the budget as a cooperative send would book it
    state = rt.store.get_state()
    assert [fc.value_fen for fc in state.forward_concessions if fc.commitment_id == c.id] == [c.forward_value_fen]
    # and it is the same shape a send of the asked path records: a PROPOSED -> ACTIVE commitment with the offer's version and the same expiry window
    assert (c.offer_id, c.offer_version, c.expires_day) == (offer_id, 1, rt.day + 7)


def test_the_owners_call_is_the_approval_and_is_recorded_as_theirs(busy: TestClient, rt: Runtime) -> None:
    offer_id, v = _evaluate(busy, ZHUHAI)
    busy.post(f"/offers/{offer_id}/accept", json=_body(v))
    mine = [a for a in rt.store.approvals() if a.kind == "ACCEPT_OFFER"]
    assert len(mine) == 1 and mine[0].status.value == "APPROVED" and mine[0].decided_by == "OWNER" and mine[0].decided_day == rt.day
    assert json.loads(mine[0].op_json)["requested_by"] == "OWNER"
    # the approvals history lists it as decided; the facility application the busy seed queued is still waiting
    rows = {a["id"]: a for a in busy.get("/approvals/queue").json()["approvals"]}
    assert rows[mine[0].id]["status"] == "APPROVED" and rows[mine[0].id]["decision_id"] == f"deal:{offer_id}"
    assert [a["status"] for a in rows.values() if a["kind"] == "APPLY_FOR_FACILITY"] == ["PENDING"]
    # nothing is waiting on the owner for this deal
    q = _queue_keys(busy)
    assert f"deal:{offer_id}" not in q["needs_you"] and f"agreement:deal:{offer_id}" in q["agreements"]


@pytest.mark.parametrize(("lang", "title", "detail"), [
    ("en", "You accepted Zhuhai's request as asked.", "Agreement with Zhuhai Kitchenware Wholesale Co. recorded; concessions booked against your budget:"),
    ("zh", "您已按对方要求接受Zhuhai的请求。", "已记录与Zhuhai Kitchenware Wholesale Co.的协议；已计入您预算的让步："),
])
def test_activity_says_you_accepted_it(busy: TestClient, lang: str, title: str, detail: str) -> None:
    offer_id, v = _evaluate(busy, ZHUHAI)
    busy.post(f"/offers/{offer_id}/accept", json=_body(v))
    rows = [r for r in busy.get("/activity", params={"lang": lang}).json()["rows"] if r["decision_id"] == f"deal:{offer_id}"]
    done = next(r for r in rows if r["status_word"] == ("Done" if lang == "en" else "已完成"))
    assert done["title_text"] == title and done["detail_text"].startswith(detail)
    assert (done["actor"], done["category"], done["customer_name"]) == ("you", "deals", "Zhuhai Kitchenware Wholesale Co.")
    # the queued entry the same click decided reads as the owner's own choice, never as FLOW's request waiting for them
    queued = next(r for r in rows if r["status_word"] != done["status_word"])
    assert queued["actor"] == "you" and "Waiting" not in queued["title_text"] and "等待" not in queued["title_text"]
    assert not any(ID.search(s) for r in rows for s in (r["title_text"], r["detail_text"] or "", queued["title_text"]))
    ledger = busy.get("/ledger", params={"lang": lang}).json()["operations"]
    assert not any(ID.search(e["message_when"]) for e in ledger if e.get("decision_id") == f"deal:{offer_id}" and e["kind"] == "ACCEPT_OFFER")


def test_the_chinese_accept_answers_in_chinese_without_leaks(busy: TestClient) -> None:
    offer_id, v = _evaluate(busy, ZHUHAI, "zh")
    r = busy.post(f"/offers/{offer_id}/accept", params={"lang": "zh"}, json=_body(v))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"]["status_text"] == "已达成" and body["execution"]["summary_text"].endswith("没有付款，也没有融资。")
    assert english_leaks({"receipt": body["receipt"], "execution": body["execution"]}, [*NAMES, "Zhuhai Kitchenware Wholesale Co."]) == []
    assert not any(ID.search(s) for s in _strings([body["receipt"], body["execution"]]))


def test_a_second_accept_changes_nothing_and_says_the_agreement_exists(busy: TestClient) -> None:
    offer_id, v = _evaluate(busy, ZHUHAI)
    assert busy.post(f"/offers/{offer_id}/accept", json=_body(v)).status_code == 200
    before = _books(busy)
    again = busy.post(f"/offers/{offer_id}/accept", json=_body(v))
    d = _detail(again)
    assert again.status_code == 409 and d["code"] == "ALREADY_ACCEPTED" and d["decision_id"] == f"deal:{offer_id}"
    assert d["commitment_status"] == "ACTIVE" and d["approval_id"]
    assert not ID.search(d["message_when"])
    assert _books(busy) == before
    # a decline cannot undo it either: the agreement is revoked, not declined
    assert _detail(busy.post(f"/offers/{offer_id}/decline", json=_body(v)))["code"] == "ALREADY_ACCEPTED"
    block = busy.get(f"/offers/{offer_id}/picture").json()["accept"]
    assert block["available"] is False and block["receipt"] is None and block["decline_available"] is False
    assert block["reason_text"] == "An agreement for this request is already in place."


# ================================================================ Dongguan declined


def test_declining_dongguan_closes_the_request_and_moves_nothing(busy: TestClient) -> None:
    offer_id, v = _evaluate(busy, DONGGUAN)
    assert f"deal:{offer_id}" in _queue_keys(busy)["needs_you"]
    before = _books(busy)
    r = busy.post(f"/offers/{offer_id}/decline", json=_body(v, reason="not this quarter"))
    assert r.status_code == 200, r.text
    body = r.json()
    d = body["decision"]
    assert (d["state"], d["state_text"], d["lifecycle"], d["status_text"], d["terminal"]) == ("DECLINED", "You declined it", "declined", "Declined", True)
    assert d["waiting_for"]["code"] == "NOTHING" and d["agreement"] is None
    assert body["execution"]["summary_text"] == "You declined this request. Nothing was agreed, sent or funded."
    assert list(body["receipt"]) == RECEIPT_FIELDS
    assert body["receipt"]["authorizes_text"] == "Decline Dongguan's request: 1% rebate next quarter."
    assert body["receipt"]["executes_now_text"] == "Records your refusal now; nothing is agreed, sent, paid or funded."
    assert body["receipt"]["gross_display"] is None and body["receipt"]["fees_display"] is None and body["receipt"]["net_display"] is None
    # nothing moved: the books, the agreements and the approvals are as they were; the log gained the one refusal
    after = _books(busy)
    assert {k: v for k, v in after.items() if k != "chain"} == {k: v for k, v in before.items() if k != "chain"}
    assert after["chain"] == before["chain"] + 1
    # declined is terminal: out of every tier, and out of the open decisions
    assert f"deal:{offer_id}" not in _in_any_tier(busy)
    assert all(r["id"] != f"deal:{offer_id}" for r in busy.get("/decisions", params={"open": True}).json()["decisions"])
    assert busy.get("/decisions", params={"family": "DEAL"}).json()["decisions"][0]["id"] == f"deal:{offer_id}"
    # the other decisions are untouched
    assert len([r for r in busy.get("/deals").json()["queue"]["needs_you"] if r["kind"] == "DECISION"]) == 4


@pytest.mark.parametrize(("lang", "title"), [("en", "You declined Dongguan's request."), ("zh", "您已拒绝Dongguan的请求。")])
def test_activity_says_you_declined_it(busy: TestClient, lang: str, title: str) -> None:
    offer_id, v = _evaluate(busy, DONGGUAN, lang)
    r = busy.post(f"/offers/{offer_id}/decline", params={"lang": lang}, json=_body(v))
    assert r.status_code == 200
    row = next(x for x in busy.get("/activity", params={"lang": lang}).json()["rows"] if x["decision_id"] == f"deal:{offer_id}")
    assert row["title_text"] == title and (row["actor"], row["category"]) == ("you", "deals")
    assert row["customer_name"] == "Dongguan Office Supplies Ltd." and row["href"].endswith(f"deal%3A{offer_id}") or "decision" in row["href"]
    if lang == "zh":
        assert english_leaks({"receipt": r.json()["receipt"], "execution": r.json()["execution"]}, NAMES) == []
    ledger = busy.get("/ledger", params={"lang": lang}).json()["operations"]
    refusal = next(e for e in ledger if e["kind"] == "REJECT_OFFER")
    assert refusal["requested_by"] == "OWNER" and not ID.search(refusal["message_when"])


def test_a_declined_request_cannot_be_accepted_or_declined_again(busy: TestClient) -> None:
    offer_id, v = _evaluate(busy, DONGGUAN)
    busy.post(f"/offers/{offer_id}/decline", json=_body(v))
    before = _books(busy)
    for route in ("accept", "decline"):
        r = busy.post(f"/offers/{offer_id}/{route}", json=_body(v))
        assert r.status_code == 409 and _detail(r)["code"] == "ALREADY_DECLINED"
    assert _books(busy) == before
    block = busy.get(f"/offers/{offer_id}/picture").json()["accept"]
    assert block["available"] is False and block["reason_text"] == "You declined this request." and block["decline_available"] is False


def test_an_agents_rejection_does_not_close_the_request(busy: TestClient) -> None:
    offer_id, _ = _evaluate(busy, DONGGUAN)
    r = busy.post("/operations", json={"kind": "REJECT_OFFER", "op_id": "agent-reject", "idempotency_key": "agent-reject", "mandate_version": 1,
                                       "requested_by": "AGENT", "offer_id": offer_id, "reason_codes": []})
    assert r.status_code == 200 and r.json()["result"]["status"] == "EXECUTED"
    state = busy.get(f"/decisions/deal:{offer_id}").json()["state"]
    assert state == "RESPONSE_READY"  # only the owner declines


# ================================================================ over the mandate


@pytest.mark.parametrize("scenario", ["busy", "golden"])
@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_reject_verdict_cannot_be_accepted_over_the_mandate_cap(api: TestClient, scenario: str, lang: str) -> None:
    if scenario == "busy":
        api.post("/demo/reset", params={"scenario": "busy"})
    offer_id, v = _evaluate(api, FOSHAN_1, lang)
    assert v["outcome"] == "REJECT" and {x["code"] for x in v["violations"]} & {"AGG_CONCESSION_EXCEEDED", "PER_BUYER_CAP_EXCEEDED"}
    before = _books(api)
    r = api.post(f"/offers/{offer_id}/accept", params={"lang": lang}, json=_body(v))
    d = _detail(r)
    assert r.status_code == 409 and d["code"] == "OVER_MANDATE" and d["offer_id"] == offer_id
    assert "new mandate" in d["message"] and "Nothing was accepted" in d["message"]
    if lang == "zh":
        assert d["message_when"] == "该请求超出了您签署的上限，只有签署新的授权才能改变。未接受任何内容。"
        assert english_leaks(d["message_when"], NAMES) == []
    else:
        assert d["message_when"] == d["message"]
    assert _books(api) == before, "nothing was proposed, accepted, logged or approved"


def test_the_over_limit_request_can_still_be_declined(busy: TestClient) -> None:
    offer_id, v = _evaluate(busy, FOSHAN_1)
    r = busy.post(f"/offers/{offer_id}/decline", json=_body(v))
    assert r.status_code == 200 and r.json()["decision"]["state"] == "DECLINED"


def test_a_counter_outcome_is_not_acceptable_as_asked(busy: TestClient) -> None:
    offer_id, v = _evaluate(busy, FOSHAN_3)
    before = _books(busy)
    r = busy.post(f"/offers/{offer_id}/accept", json=_body(v))
    assert r.status_code == 409 and _detail(r)["code"] == "NOT_ACCEPTABLE"
    assert _books(busy) == before


def test_a_mandate_that_is_not_in_force_is_over_the_mandate_too(api: TestClient, rt: Runtime) -> None:
    offer_id, v = _evaluate(api, CONSOLIDATE)
    rt.store.put_mandate(rt.store.get_mandate().model_copy(update={"revoked": True}))
    before = _books(api)
    r = api.post(f"/offers/{offer_id}/accept", json=_body(v))
    assert r.status_code == 409 and _detail(r)["code"] == "OVER_MANDATE" and "not in force" in _detail(r)["message"]
    assert _books(api) == before


# ================================================================ stale and lapsed


def test_a_stale_state_version_is_refused_and_nothing_changes(api: TestClient) -> None:
    offer_id, v = _evaluate(api, CONSOLIDATE)
    api.post("/clock/advance", json={"to_day": 1})  # the books move
    before = _books(api)
    for route in ("accept", "decline"):
        r = api.post(f"/offers/{offer_id}/{route}", json=_body(v))
        d = _detail(r)
        assert r.status_code == 409 and d["code"] == "COUNTER_CHANGED" and d["reason"] == "BOOKS_CHANGED" and d["reevaluate"] is True
        assert d["message"].startswith("The request changed since you read it; nothing was ")
    assert _books(api) == before


def test_an_old_verdict_is_refused_and_the_current_one_goes_through(api: TestClient) -> None:
    offer_id, v1 = _evaluate(api, CONSOLIDATE)
    api.post("/clock/advance", json={"to_day": 1})
    v2 = api.post(f"/offers/{offer_id}/evaluate", json={"fixture_id": CONSOLIDATE}).json()
    assert v2["id"] != v1["id"]
    before = _books(api)
    r = api.post(f"/offers/{offer_id}/accept", json=_body(v1))
    d = _detail(r)
    assert r.status_code == 409 and d["code"] == "COUNTER_CHANGED" and d["reason"] == "VERDICT_CHANGED" and d["verdict_id"] == v2["id"]
    assert _books(api) == before
    assert api.post(f"/offers/{offer_id}/accept", json=_body(v2)).status_code == 200


def test_one_wrong_field_is_enough_to_refuse(api: TestClient) -> None:
    offer_id, v = _evaluate(api, CONSOLIDATE)
    before = _books(api)
    assert api.post(f"/offers/{offer_id}/accept", json=_body(v, state_version=v["state_version"] + 3)).status_code == 409
    assert api.post(f"/offers/{offer_id}/accept", json=_body(v, verdict_id="VER-old")).status_code == 409
    assert _books(api) == before


def test_a_lapsed_offer_answers_offer_lapsed_to_both_routes(busy: TestClient) -> None:
    offer_id, v = _evaluate(busy, FOSHAN_1)
    agree_on_rcv_a(busy)  # a send on invoice RCV-A settles it: every other reply about it lapses
    v = busy.get(f"/decisions/deal:{offer_id}").json()
    assert v["state"] == "LAPSED"
    latest = busy.get(f"/offers/{offer_id}/picture").json()["verdict_id"]
    version = busy.get("/state").json()["state"]["state_version"]
    before = _books(busy)
    for route in ("accept", "decline"):
        r = busy.post(f"/offers/{offer_id}/{route}", json={"verdict_id": latest, "state_version": version})
        d = _detail(r)
        assert r.status_code == 409 and d["code"] == "OFFER_LAPSED" and d["message"] and d["message_when"]
    assert _books(busy) == before


def test_the_body_is_required_and_bounded(api: TestClient) -> None:
    offer_id, v = _evaluate(api, CONSOLIDATE)
    assert api.post(f"/offers/{offer_id}/accept", json={}).status_code == 422
    assert api.post(f"/offers/{offer_id}/accept", json={"verdict_id": v["id"]}).status_code == 422
    assert api.post(f"/offers/{offer_id}/decline", json=_body(v, reason="x" * 501)).status_code == 422
    assert api.post("/offers/OFF-nothing/accept", json=_body(v)).status_code == 404
    unevaluated = api.post("/offers", json={"fixture_id": "EX10_FASTCAPITAL"}).json()["offer"]["offer_id"]
    r = api.post(f"/offers/{unevaluated}/accept", json=_body(v))
    assert r.status_code == 409 and _detail(r)["code"] == "NOT_EVALUATED"


def test_only_the_owner_answers_a_request(api: TestClient) -> None:
    offer_id, v = _evaluate(api, CONSOLIDATE)
    before = _books(api)
    for headers in ({}, {"X-Agent-Key": "demo-agent-key"}, {"X-Owner-Token": "wrong"}):
        for route in ("accept", "decline"):
            r = api.post(f"/offers/{offer_id}/{route}", json=_body(v), headers={"X-Owner-Token": "", **headers})
            assert r.status_code == 401, (route, headers)
    assert _books(api) == before


# ================================================================ siblings, and what FLOW may agree alone


def test_siblings_on_the_same_invoice_lapse_as_after_a_send(busy: TestClient, rt: Runtime) -> None:
    """Foshan's three replies are all about invoice RCV-A. A 0.5% early-settlement request on the same invoice, accepted as asked, settles it."""
    base = rt.store.get_offer(busy.post("/offers", json={"fixture_id": "EX02_EARLY_1_5"}).json()["offer"]["offer_id"])
    assert base is not None
    asked = base.model_copy(update={"offer_id": "OFF-ASKED-RCV-A", "obligations": [o.model_copy(update={"rate_bp": 50}) for o in base.obligations]})
    rt.store.put_offer(asked)
    v = busy.post("/offers/OFF-ASKED-RCV-A/evaluate", json={}).json()
    assert v["outcome"] == "NEEDS_OWNER_APPROVAL" and v["workspace"]["accept"]["available"] is True
    foshan = [d for d in busy.get("/decisions").json()["decisions"] if d["counterparty_name"] == "Foshan Home Retail Co." and d["state"] == "RESPONSE_READY"]
    assert len(foshan) == 4  # Foshan's three replies and the new request, all about the one invoice
    r = busy.post("/offers/OFF-ASKED-RCV-A/accept", json=_body(v))
    assert r.status_code == 200, r.text
    assert r.json()["decision"]["state"] == "AGREED"
    left = [d for d in busy.get("/decisions").json()["decisions"] if d["counterparty_name"] == "Foshan Home Retail Co."]
    assert {d["id"]: d["state"] for d in left}["deal:OFF-ASKED-RCV-A"] == "AGREED"
    lapsed = [d["id"] for d in left if d["state"] == "LAPSED"]
    assert len(lapsed) == 3 and {d["id"] for d in foshan} - set(lapsed) == {"deal:OFF-ASKED-RCV-A"}
    queue = _queue_keys(busy)
    assert not set(lapsed) & {k for keys in queue.values() for k in keys}  # a lapsed reply is in no tier


def test_when_flow_may_accept_alone_the_owners_accept_just_records(busy: TestClient, rt: Runtime) -> None:
    # an early payment on a named invoice, inside what FLOW may agree alone: the verifier says ACCEPT and Tier 1
    base = rt.store.get_offer(busy.post("/offers", json={"fixture_id": "EX02_EARLY_1_5"}).json()["offer"]["offer_id"])
    assert base is not None
    rt.store.put_offer(base.model_copy(update={"offer_id": "OFF-ALONE", "obligations": [o.model_copy(update={"rate_bp": 50}) for o in base.obligations]}))
    shown = busy.post("/offers/OFF-ALONE/evaluate", json={}).json()
    stored = rt.store.get_verdict(shown["id"])
    assert stored is not None
    alone = stored.model_copy(update={"id": "VER-ALONE", "outcome": Outcome.ACCEPT, "required_tier": Tier.TIER_1, "violations": [], "plan": None})
    rt.store.put_verdict(alone)
    rt.latest_verdict["OFF-ALONE"] = alone.id
    from app.api.accept import accept_block
    from app.api.runtime import get_runtime

    offer = get_runtime().store.get_offer("OFF-ALONE")
    block = accept_block("en", state=rt.store.get_state(), offer=offer, verdict=alone, months=12)
    assert block["available"] is True and block["authority"] == "flow_may" and block["receipt"]["authority_text"] == "Within what FLOW may agree."
    approvals_before = len(rt.store.approvals())
    r = busy.post("/offers/OFF-ALONE/accept", json={"verdict_id": alone.id, "state_version": rt.store.get_state().state_version})
    assert r.status_code == 200, r.text
    assert r.json()["decision"]["state"] == "AGREED"
    assert len(rt.store.approvals()) == approvals_before, "FLOW may agree this alone: there is no approval to record"
    assert r.json()["receipt"]["authority_text"] == "You accepted it as asked."


# ================================================================ the queue's words


@pytest.mark.parametrize(("lang", "act"), [("en", "Accept, decline, or try other terms."), ("zh", "接受、拒绝，或尝试其他条款。")])
def test_a_request_for_review_names_the_act_in_the_queue(busy: TestClient, lang: str, act: str) -> None:
    rows = busy.get("/deals", params={"lang": lang}).json()["queue"]["needs_you"]
    review = [r for r in rows if r.get("lifecycle") == "owner_review"]
    assert len(review) == 2 and all(r["consequence_text"].endswith(act) for r in review)
    # the cash effect is still the first thing said
    assert all(r["consequence_text"].startswith(("As asked", "按对方要求")) for r in review)
    others = [r for r in rows if r["kind"] == "DECISION" and r.get("lifecycle") != "owner_review"]
    assert others and not any(act in r["consequence_text"] for r in others)
    wl = busy.get("/worklist", params={"lang": lang}).json()["needs_you"]
    assert all(r["consequence_text"].endswith(act) for r in wl if r.get("lifecycle") == "owner_review")


def test_an_over_limit_request_for_review_names_only_what_can_be_done(busy: TestClient, rt: Runtime) -> None:
    offer_id, v = _evaluate(busy, DONGGUAN)
    stored = rt.store.get_verdict(v["id"])
    assert stored is not None
    capped = stored.model_copy(update={"id": "VER-CAPPED", "outcome": Outcome.REJECT, "violations": [stored.violations[0].model_copy(update={"code": "AGG_CONCESSION_EXCEEDED"})] if stored.violations else []})
    if not stored.violations:
        from app.domain.models import Violation, ViolationCode
        capped = capped.model_copy(update={"violations": [Violation(code=ViolationCode.AGG_CONCESSION_EXCEEDED, message="over the cap")]})
    rt.store.put_verdict(capped)
    rt.latest_verdict[offer_id] = capped.id
    offer_picture._cache.clear()
    worklist.clear_cache()
    rows = busy.get("/deals").json()["queue"]["needs_you"]
    row = next(r for r in rows if r["key"] == f"deal:{offer_id}")
    assert row["lifecycle"] == "owner_review" and row["consequence_text"].endswith("Decline, or try other terms.")


def test_an_agreement_already_waiting_for_approval_is_not_recorded_twice(api: TestClient, rt: Runtime) -> None:
    """Something else (the agent) queued the same terms for the owner: the owner's accept does not make a second agreement beside it."""
    from app.domain.models import AcceptOffer, Actor

    offer_id, v = _evaluate(api, CONSOLIDATE)
    c = rt.executor.propose_commitment(v["id"], expires_day=rt.day + 7)
    queued = rt.executor.execute(AcceptOffer(op_id="agent-accept", idempotency_key="agent-accept", mandate_version=1, requested_by=Actor.AGENT,
                                             source_verdict_id=v["id"], day=rt.day, offer_id=offer_id, offer_version=1,
                                             terms_hash=c.terms_hash, nonce=c.nonce))
    assert queued.status.value == "PENDING_APPROVAL"
    before = _books(api)
    r = api.post(f"/offers/{offer_id}/accept", json=_body(v))
    d = _detail(r)
    assert r.status_code == 409 and d["code"] == "ALREADY_SENT" and d["approval_id"] == queued.approval_id
    assert api.get(f"/offers/{offer_id}/picture").json()["accept"]["reason_text"] == "An agreement for this request is already waiting for your approval."
    assert _books(api) == before


@pytest.mark.parametrize("route", ["accept", "decline"])
def test_a_refusal_by_the_executor_is_a_409_with_its_reason_in_business_words(api: TestClient, rt: Runtime, monkeypatch: pytest.MonkeyPatch, route: str) -> None:
    from app.domain.models import OperationResult, OperationStatus, Violation, ViolationCode

    offer_id, v = _evaluate(api, CONSOLIDATE)

    def refuse(_self: Any, op: Any) -> OperationResult:
        return OperationResult(op_id=op.op_id, kind=op.kind, status=OperationStatus.REFUSED, tier=Tier.TIER_2, effective_day=rt.day,
                               violations=[Violation(code=ViolationCode.CIRCUIT_OPEN, message="Circuit open for BUYER-1: 3 refusals within 7 days; the owner must reset it")],
                               message="Refused: Circuit open for BUYER-1")

    from app.operations.executor import Executor

    monkeypatch.setattr(Executor, "execute", refuse)
    r = api.post(f"/offers/{offer_id}/{route}", params={"lang": "zh"}, json=_body(v))
    d = _detail(r)
    assert r.status_code == 409 and d["code"] == "NOT_RECORDED"
    assert d["message"].startswith("FLOW could not record") and d["message_when"].startswith("FLOW 未能")
    assert not ID.search(d["message_when"]), d["message_when"]


# ================================================================ every surface names the buyer


def _home_changes(api: TestClient, lang: str) -> list[dict[str, Any]]:
    body = api.get("/home", params={"lang": lang}).json()
    found = body.get("changes") or (body.get("what_changed") or {}).get("items") or []
    return list(found)


@pytest.mark.parametrize(("lang", "declined"), [("en", "You declined Dongguan's request."), ("zh", "您已拒绝Dongguan的请求。")])
def test_home_and_the_customer_overview_name_the_buyer_of_an_answered_request(busy: TestClient, lang: str, declined: str) -> None:
    # a decline on one buyer's request and an accept on another's: both surfaces say whose request it was
    dongguan, dv = _evaluate(busy, DONGGUAN, lang)
    zhuhai, zv = _evaluate(busy, ZHUHAI, lang)
    assert busy.post(f"/offers/{dongguan}/decline", params={"lang": lang}, json=_body(dv)).status_code == 200
    assert busy.post(f"/offers/{zhuhai}/accept", params={"lang": lang}, json=_body(zv)).status_code == 200

    home = " ".join(str(x.get("event_text")) for x in _home_changes(busy, lang))
    assert declined in home and "买方的请求" not in home and "the buyer's request" not in home

    buyer_history = lambda cid: " ".join(h["text"] for h in busy.get(f"/customers/{cid}/overview", params={"lang": lang}).json()["history"])
    assert declined in buyer_history("BUYER-2")
    zhuhai_text = buyer_history("BUYER-3")
    assert ("Zhuhai Kitchenware Wholesale Co." in zhuhai_text) and "the buyer's request" not in zhuhai_text and "买方的请求" not in zhuhai_text


# ================================================================ an agreement in force has no expiry; the review says what it does to cash


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_an_owner_accepted_agreement_is_in_force_and_says_no_expiry_anywhere(busy: TestClient, lang: str) -> None:
    offer_id, v = _evaluate(busy, ZHUHAI, lang)
    body = busy.post(f"/offers/{offer_id}/accept", params={"lang": lang}, json=_body(v)).json()
    decision = busy.get(f"/decisions/deal:{offer_id}", params={"lang": lang}).json()
    assert body["decision"]["agreement"]["status"] == "ACTIVE"
    assert body["receipt"]["when_text"] == ("In force." if lang == "en" else "已生效。")
    for name, data in (("accept", body), ("decision", decision),
                       ("queue", busy.get("/deals", params={"lang": lang}).json()["queue"]["agreements"]),
                       ("worklist", busy.get("/worklist", params={"lang": lang}).json())):
        assert not [s for s in _strings(data) if re.search(r"expir|到期", s, re.IGNORECASE)], name
    assert (decision["agreement"]["expires_day"], decision["agreement"]["expires_when"]) == (None, None)
    assert any(r["key"] == f"agreement:deal:{offer_id}" for r in busy.get("/deals", params={"lang": lang}).json()["queue"]["agreements"])


def test_a_proposal_still_waiting_keeps_its_acceptance_window(busy: TestClient, rt: Runtime) -> None:
    from app.domain.models import AcceptOffer, Actor

    offer_id, v = _evaluate(busy, ZHUHAI)
    c = rt.executor.propose_commitment(v["id"], expires_day=rt.day + 7)
    rt.executor.execute(AcceptOffer(op_id="agent-accept", idempotency_key="agent-accept", mandate_version=1, requested_by=Actor.AGENT,
                                    source_verdict_id=v["id"], day=rt.day, offer_id=offer_id, offer_version=1, terms_hash=c.terms_hash, nonce=c.nonce))
    agreement = busy.get(f"/decisions/deal:{offer_id}").json()["agreement"]
    assert agreement["status"] == "PROPOSED" and agreement["expires_day"] == rt.day + 7
    assert agreement["receipt"]["when_text"] == "Expires in 7 days."


@pytest.mark.parametrize(("lang", "cash"), [
    ("en", "As asked: below your minimum for 35 days, starting in 12 days. Accepting runs no funding, so that gap stays open."),
    ("zh", "按对方要求：低于您的最低现金储备 35 天（最早 12 天后）。接受不会办理融资，缺口仍然存在。"),
])
def test_the_accept_review_says_what_the_asked_terms_do_to_cash(busy: TestClient, lang: str, cash: str) -> None:
    offer_id, v = _evaluate(busy, ZHUHAI, lang)
    receipt = v["workspace"]["accept"]["receipt"]
    assert receipt["cash_text"] == cash
    # the queue row warns with the same words
    row = next(r for r in busy.get("/deals", params={"lang": lang}).json()["queue"]["needs_you"] if r["key"] == f"deal:{offer_id}")
    assert row["consequence_text"].startswith("As asked: below your minimum for 35 days" if lang == "en" else "按对方要求：低于您的最低现金储备 35 天")
    assert busy.get(f"/offers/{offer_id}/picture", params={"lang": lang}).json()["accept"]["receipt"]["cash_text"] == cash


def test_a_request_that_keeps_the_reserve_has_no_cash_line(api: TestClient, rt: Runtime) -> None:
    state = rt.store.get_state()
    rt.store.put_state(state.model_copy(update={"cash_fen": state.cash_fen + 10_000_000_000}), expected_version=state.state_version)
    _, v = _evaluate(api, CONSOLIDATE)
    block = v["workspace"]["accept"]
    assert block["available"] is True and block["receipt"]["cash_text"] is None
    assert block["receipt"]["authorizes_text"]  # the rest of the receipt is whole
