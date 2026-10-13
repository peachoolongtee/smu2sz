"""The commitment receipt (map #121, ticket #128): one `receipt` block on the reads that authorize or move money or send on the owner's behalf
(the counter to send, an approval, the plan to run, a payment request to chase, an agreement on the record). The eleven fields in order, each a
server word or null, built from the words the read already carries. On the Demo and on the busy company, in both languages."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview, offer_picture, worklist
from app.api.receipt import FIELDS, receipt
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
EX01 = {"fixture_id": "EX01_PACKAGE"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Bank credit line",
         "Invoice financing (onboarded platform)", "Buyer early-payment offer", "Government-guaranteed working-capital loan"]


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


def _whole(block: dict[str, Any] | None, lang: str) -> dict[str, str | None]:
    """The block is the eleven fields in order, every value a word or null; Chinese carries no English beyond the names the books give."""
    assert block is not None
    assert list(block) == list(FIELDS)
    assert all(v is None or (isinstance(v, str) and v.strip()) for v in block.values())
    if lang == "zh":
        assert not english_leaks({"receipt": block}, NAMES)
    return block


def test_the_builder_orders_the_fields_and_turns_an_empty_word_into_null() -> None:
    block = receipt(fees_display="¥1.00", when_text="", authorizes_text="x")
    assert list(block) == list(FIELDS) and block["authorizes_text"] == "x" and block["when_text"] is None and block["net_display"] is None
    with pytest.raises(TypeError):
        receipt(invented_text="no")


# ---------------------------------------------------------------- the counter to send


def _evaluate(api: TestClient, lang: str) -> dict[str, Any]:
    offer_id = api.post("/offers", json=EX01).json()["offer"]["offer_id"]
    ws: dict[str, Any] = api.post(f"/offers/{offer_id}/evaluate", params={"lang": lang}, json=EX01).json()["workspace"]
    return ws


def test_the_send_receipt_keeps_the_three_lines_of_the_ex01_receipt(api: TestClient) -> None:
    pr = _evaluate(api, "en")["priced_response"]
    r = _whole(pr["receipt"], "en")
    agreement, draw, cost = pr["send_scope_lines"]
    assert agreement == "Records the agreement with Foshan Home Retail Co. (needs your approval when it changes terms)"
    assert draw == "Draws ¥149,986.20 on the Bank credit line today"
    assert cost == "Funding cost ¥841.57 for the draw (already inside the ¥3,027.77 above)"
    assert r["authorizes_text"] == agreement and r["executes_now_text"] == f"{draw}; {cost}"
    assert r["fees_display"] == "¥3,027.77" == pr["supplier_cost_display"] and r["gross_display"] is None and r["net_display"] is None
    # the recheck sentence, then what the engine does whatever the buyer answers (the funding runs when the counter is sent)
    assert r["assumptions_text"].startswith(pr["recheck_text"]) and "Runs when you send, whether or not the buyer agrees" in r["assumptions_text"]
    assert r["authority_text"] == "FLOW can send it. Your approval is not needed."
    assert r["others_must_agree_text"] == "Foshan Home Retail Co. must accept the counter before it takes effect."
    assert r["in_hand_vs_future_text"] == "The draw is in hand today. Nothing from Foshan Home Retail Co. counts as cash until it arrives."
    assert r["when_text"] == "As soon as you confirm." and "has not accepted yet" in r["remaining_text"]


def test_the_send_receipt_in_chinese(api: TestClient) -> None:
    pr = _evaluate(api, "zh")["priced_response"]
    r = _whole(pr["receipt"], "zh")
    assert r["authority_text"] == "FLOW 可以发送。无需您批准。"
    assert r["in_hand_vs_future_text"].startswith("提款今天到账。") and r["fees_display"] == "¥3,027.77"
    assert r["authorizes_text"] == pr["send_scope_lines"][0] and "；" in r["executes_now_text"]


def test_a_reply_that_cannot_be_sent_has_no_receipt(api: TestClient) -> None:
    offer = api.post("/offers", json={"fixture_id": "SEC_DEMO_FASTCAPITAL"}).json()["offer"]["offer_id"]
    ws = api.post(f"/offers/{offer}/evaluate", json={"fixture_id": "SEC_DEMO_FASTCAPITAL"}).json()["workspace"]
    assert ws["priced_response"] is None


# ---------------------------------------------------------------- an approval


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_facility_application_waiting_for_approval_carries_a_receipt(api: TestClient, lang: str) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    item = next(a for a in api.get("/approvals/queue", params={"lang": lang}).json()["approvals"] if a["kind"] == "APPLY_FOR_FACILITY")
    r = _whole(item["receipt"], lang)
    assert r["gross_display"] == "¥200,000.00" and r["authorizes_text"] == item["presentation"]["what"]
    assert r["others_must_agree_text"] == {"en": "The lender still has to accept the application.", "zh": "贷款方仍需受理这份申请。"}[lang]
    assert r["authority_text"] == item["presentation"]["reason"] and r["fees_display"] is None and r["net_display"] is None


def _queued_counter(api: TestClient) -> None:
    api.post("/demo/reset", json={})
    offer_id = api.post("/offers", json=EX01).json()["offer"]["offer_id"]
    ev = api.post(f"/offers/{offer_id}/evaluate", json=EX01).json()
    verdict = ev.get("verdict", ev)
    commitment = get_runtime().executor.propose_commitment(verdict["id"], expires_day=14, counter_id=verdict["counters"][1]["id"])
    version = api.get("/mandate").json()["mandate"]["version"]
    r = api.post("/operations", headers=AGENT, json={"kind": "RECORD_COMMITMENT", "op_id": "rec-1", "idempotency_key": "rec-1",
                                                      "mandate_version": version, "requested_by": "AGENT", "commitment_id": commitment.id,
                                                      "nonce": commitment.nonce})
    assert r.json()["result"]["status"] == "PENDING_APPROVAL", r.text


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_an_agreement_waiting_for_approval_carries_its_terms_as_the_receipt(api: TestClient, lang: str) -> None:
    _queued_counter(api)
    item = api.get("/approvals/queue", params={"lang": lang}).json()["approvals"][0]
    r = _whole(item["receipt"], lang)
    p = item["presentation"]
    assert r["authorizes_text"] == p["what_you_agree_to"] and r["authority_text"] == p["why_text"]
    assert r["executes_now_text"] == {"en": "Records the agreement with Foshan Home Retail Co. as in force.",
                                      "zh": "将与Foshan Home Retail Co.的协议记为生效。"}[lang]
    assert r["gross_display"] is None and r["in_hand_vs_future_text"] == p["economic_effect_text"]
    decided = api.post(f"/approvals/{item['id']}", json={"decision": "REJECT"}, params={"lang": lang})
    assert decided.status_code == 200
    assert api.get("/approvals/queue", params={"lang": lang}).json()["approvals"][0]["receipt"] is None  # nothing left to authorize


# ---------------------------------------------------------------- the plan to run


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_plan_run_confirmation_carries_a_receipt_from_the_plans_own_words(api: TestClient, lang: str) -> None:
    a = api.get("/home", params={"lang": lang}).json()["next_action"]
    r = _whole(a["receipt"], lang)
    assert r["authorizes_text"] == a["title"] and r["gross_display"] == "¥405,000.00" == a["receive_display"]
    assert r["fees_display"] == "¥3,113.93" == a["cost_total_display"] and r["net_display"] is None
    assert r["authority_text"] == a["authority_text"] and r["assumptions_text"] == a["cost_basis"]
    assert r["executes_now_text"] == ("; " if lang == "en" else "；").join(leg["label"] for leg in a["legs"])
    assert r["when_text"] == {"en": "The last funds land in 3 days.", "zh": "最后一笔资金将于 3 天后到账。"}[lang]
    assert r["remaining_text"] is None  # this plan restores the reserve: nothing stays short
    assert "¥150k" in r["in_hand_vs_future_text"] and "¥255k" in r["in_hand_vs_future_text"]


def test_a_plan_that_needs_the_owner_says_nothing_runs_until_approval(api: TestClient) -> None:
    from app.api.receipt import plan_receipt

    a = api.get("/home").json()["next_action"]
    waits = plan_receipt("en", action={**a, "needs_owner": True}, restores_reserve=False)
    assert waits["executes_now_text"] == "Nothing runs until you approve it." and waits["remaining_text"] == a["after"]


# ---------------------------------------------------------------- a payment request to chase


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_collection_draft_says_nothing_is_sent(api: TestClient, lang: str) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    chase = api.get("/receivables/RCV-B1/chase", params={"lang": lang}).json()
    r = _whole(chase["receipt"], lang)
    assert r["gross_display"] == chase["outstanding_display"] and r["fees_display"] is None
    assert r["executes_now_text"] == {"en": "Nothing is sent from FLOW. You copy the request and send it yourself.",
                                      "zh": "FLOW 不会发送任何内容。请您复制请求并自行发送。"}[lang]
    assert chase["outstanding_display"] in r["authorizes_text"] and "Dongguan" in r["authorizes_text"]
    assert r["when_text"] and r["assumptions_text"] and r["authority_text"]
    assert "Agreed payment terms" in r["assumptions_text"] or "约定账期" in r["assumptions_text"]


# ---------------------------------------------------------------- an agreement on the record


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_agreement_on_the_record_carries_its_receipt(api: TestClient, lang: str) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    agreed = next(d for d in api.get("/decisions").json()["decisions"] if d["state"] == "AGREED")
    detail = api.get(f"/decisions/{quote(agreed['id'], safe='')}", params={"lang": lang}).json()
    r = _whole(detail["agreement"]["receipt"], lang)
    assert r["executes_now_text"] == detail["agreement"]["status_text"] and r["authorizes_text"]
    assert detail["agreement"]["terms"][0] in r["authorizes_text"]
    assert r["when_text"] and detail["agreement"]["expires_when"] in r["when_text"]
    assert r["remaining_text"]  # the promised payment is still awaited
