"""FLOW's authority audit, item 5: which limits are approval thresholds and which are hard rules, pinned from the code and from the words.

Approval thresholds (the owner can say yes): the yearly cost above which FLOW may not borrow alone (`max_apr_bp`) and the size of a single
commitment above which it may not agree alone (`tier2_single_commitment_fen`). Above either, the operation is queued as Tier 2 and runs
only when the owner approves it.

Hard rules (nobody can say yes, the owner included): Tier 3 (guarantees, collateral, equity, changing the mandate), a mandate that is not
in force, the concession caps (the verifier answers REJECT/COUNTER, never "needs approval"), the covenants and an uncurable reserve breach.

The owner-facing words follow the same split: a threshold "waits for your approval" and is never called a ceiling or a hard cap.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import Settings
from app.domain.models import RecordCommitment, Tier
from app.mandate import demo_owner_public_key_hex, tier_for
from app.persistence import InMemoryLedgerStore
from tests.operations.builders import Clock, op

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
# words that make a threshold sound like a wall
WALL = re.compile(r"\b(ceiling|hard cap|hard limit|maximum)\b|上限", re.IGNORECASE)


@pytest.fixture
def world() -> Iterator[tuple[Runtime, TestClient]]:
    from app.main import app

    rt = Runtime(Settings(), InMemoryLedgerStore(), demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    yield rt, TestClient(app)
    set_runtime(None)


def post_op(c: TestClient, kind: str, key: str, who: str = "AGENT", headers: dict[str, str] = AGENT, **fields: Any) -> dict[str, Any]:
    r = c.post("/operations", headers=headers, json={"kind": kind, "op_id": key, "idempotency_key": key, "mandate_version": 1,
                                                     "requested_by": who, **fields})
    assert r.status_code == 200, r.text
    result: dict[str, Any] = r.json()["result"]
    return result


def dear_line(rt: Runtime) -> None:
    """The invoice-financing facility priced at 30% a year: above the mandate's 15% approval threshold."""
    s = rt.store.get_state()
    rt.store.put_state(s.model_copy(update={"facilities": [
        f.model_copy(update={"rate_bp": 3000}) if f.id == "FAC-IF" else f for f in s.facilities]}))


def facility(rt: Runtime, fid: str) -> Any:
    return next(f for f in rt.store.get_state().facilities if f.id == fid)


# ------------------------------------------------------------------------------------------------- the classification


def test_borrowing_above_the_yearly_cost_threshold_is_queued_and_only_the_owner_can_approve_it(world) -> None:
    rt, c = world
    dear_line(rt)
    cash = rt.store.get_state().cash_fen
    res = post_op(c, "SUBMIT_INVOICE_FOR_FINANCING", "dear", facility_id="FAC-IF", receivable_id="RCV-A", advance_fen=10_000_000)
    assert res["status"] == "PENDING_APPROVAL" and res["tier"] == "TIER_2" and res["approval_id"]
    assert rt.store.get_state().cash_fen == cash and facility(rt, "FAC-IF").drawn_fen == 0  # nothing ran
    c.post(f"/approvals/{res['approval_id']}", headers=AGENT, json={"decision": "APPROVE"})  # the agent cannot say yes
    assert facility(rt, "FAC-IF").drawn_fen == 0 and rt.store.get_approval(res["approval_id"]).status.value == "PENDING"
    done = c.post(f"/approvals/{res['approval_id']}", headers=OWNER, json={"decision": "APPROVE"})  # the owner can
    assert done.status_code == 200 and done.json()["approval"]["ran"] is True
    assert facility(rt, "FAC-IF").drawn_fen == 10_000_000


def test_the_same_borrowing_requested_by_the_owner_is_the_owners_own_approval(world) -> None:
    rt, c = world
    dear_line(rt)
    res = post_op(c, "SUBMIT_INVOICE_FOR_FINANCING", "dear-owner", who="OWNER", headers=OWNER, facility_id="FAC-IF",
                  receivable_id="RCV-A", advance_fen=10_000_000)
    assert res["status"] == "EXECUTED" and facility(rt, "FAC-IF").drawn_fen == 10_000_000 and rt.store.approvals() == []


def test_a_single_commitment_above_the_threshold_is_tier_2_and_at_it_is_not(world) -> None:
    rt, _ = world
    m, s = rt.store.get_mandate(), rt.store.get_state()
    t2 = m.tier2_single_commitment_fen

    def tier(value: int) -> Tier:
        o = op(RecordCommitment, Clock(rt.day), commitment_id="CMT-X", nonce="n" * 32)
        return tier_for(o, m, s, commitment_value_fen=value)

    assert tier(t2) == Tier.TIER_1 and tier(t2 + 1) == Tier.TIER_2


@pytest.mark.parametrize("kind", ["PLEDGE_COLLATERAL", "SIGN_PERSONAL_GUARANTEE"])
@pytest.mark.parametrize(("who", "headers"), [("AGENT", AGENT), ("OWNER", OWNER)])
def test_tier_3_is_refused_for_the_owner_too_and_no_approval_is_queued(world, kind: str, who: str, headers: dict[str, str]) -> None:
    rt, c = world
    res = post_op(c, kind, f"t3-{who}", who=who, headers=headers, facility_id="FAC-IF")
    assert res["status"] == "REFUSED" and res["tier"] == "TIER_3" and not res.get("approval_id")
    assert rt.store.approvals() == []


def test_a_covenant_breach_is_refused_for_the_owner_and_never_queued(world) -> None:
    rt, c = world
    s = rt.store.get_state()
    rt.store.put_state(s.model_copy(update={"monthly_ebitda_fen": 100_000}))
    res = post_op(c, "DRAW_FACILITY", "cov-owner", who="OWNER", headers=OWNER, facility_id="FAC-LINE", amount_fen=10_000_000)
    assert res["status"] == "REFUSED" and not res.get("approval_id")
    assert {v["code"] for v in res["violations"]} & {"DSCR_BREACH", "LEVERAGE_BREACH"}
    assert rt.store.approvals() == [] and facility(rt, "FAC-LINE").drawn_fen == 0 and rt.store.get_state().cash_fen == s.cash_fen


def test_a_mandate_that_is_not_in_force_refuses_the_owner_too(world) -> None:
    rt, c = world
    rt.store.put_mandate(rt.store.get_mandate().model_copy(update={"revoked": True}))
    res = post_op(c, "DRAW_FACILITY", "revoked", who="OWNER", headers=OWNER, facility_id="FAC-LINE", amount_fen=1_000_000)
    assert res["status"] == "REFUSED" and not res.get("approval_id") and rt.store.approvals() == []


def test_a_concession_cap_is_a_hard_rule_the_owners_accept_cannot_pass(world) -> None:
    rt, c = world
    oid = c.post("/offers", headers=OWNER, json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    v = c.post(f"/offers/{oid}/evaluate", headers=OWNER, json={"fixture_id": "EX01_PACKAGE"}).json()
    assert v["outcome"] == "REJECT" and {x["code"] for x in v["violations"]} & {"AGG_CONCESSION_EXCEEDED", "PER_BUYER_CAP_EXCEEDED"}
    r = c.post(f"/offers/{oid}/accept", headers=OWNER, json={"verdict_id": v["id"], "state_version": v["state_version"]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "OVER_MANDATE"
    assert rt.store.approvals() == [] and rt.store.commitments() == []


# ------------------------------------------------------------------------------------------------- the words


def queued_card(c: TestClient, rt: Runtime, lang: str) -> dict[str, Any]:
    dear_line(rt)
    post_op(c, "SUBMIT_INVOICE_FOR_FINANCING", "dear-card", facility_id="FAC-IF", receivable_id="RCV-A", advance_fen=10_000_000)
    rows: list[dict[str, Any]] = c.get("/approvals/queue", headers=OWNER, params={"lang": lang}).json()["approvals"]
    return rows[0]


def test_the_approvals_card_says_it_waits_because_it_is_above_the_approval_threshold(world) -> None:
    rt, c = world
    reason = queued_card(c, rt, "en")["presentation"]["reason"]
    assert reason.startswith("The yearly cost of ")
    assert "is above the 15.00% limit you signed for funding without your approval, so it waits for your approval." in reason
    assert not WALL.search(reason)


def test_the_approvals_card_says_the_same_in_chinese(world) -> None:
    rt, c = world
    reason = queued_card(c, rt, "zh")["presentation"]["reason"]
    assert "高于您签署的无需批准融资的批准线 15.00%" in reason and "因此需等您批准" in reason
    assert not WALL.search(reason)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_no_card_word_calls_the_threshold_a_ceiling_or_cap(world, lang: str) -> None:
    rt, c = world
    card = queued_card(c, rt, lang)
    words = json.dumps({k: card["presentation"].get(k) for k in ("reason", "headline", "result_message")}, ensure_ascii=False)
    assert not WALL.search(words), words
