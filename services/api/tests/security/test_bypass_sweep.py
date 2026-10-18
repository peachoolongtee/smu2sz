"""FLOW's authority audit, item 6: no lower-level route, actor or key skips a gate.

For every route that writes on the owner's authority, and for the three routes an agent key may use (POST /operations, POST /approvals/{id},
POST /circuit/{id}/reset), a request with (i) no credential, (ii) the agent key `demo-agent-key` and (iii) a counterparty key
`demo-buyer-1-key` is refused or limited exactly as the policy intends:

* owner-only routes (documents confirm and reject, negotiate, alerts act, offers accept and decline, commitments revoke, ... every
  non-GET route of the owner, owner-side and demo/setup classes in route_policy_support.py) refuse all three and change nothing: the log,
  the books, the agreements, the approvals, the documents and the day are the same before and after;
* the agent-allowed routes never let the agent exceed Tier 1: a Tier 2 operation is queued (never run), a Tier 3 operation is refused, a
  claim to be the owner or the bank feed is read as the agent's, and the agent cannot decide an approval or reset a circuit;
* POST /nl: an owner-channel message needs the owner token or the agent key; a counterparty channel (with its key or none) can never
  approve, fund, confirm or record a payment, whatever the words; the agent key's chat cannot approve and cannot run a leg above the
  approval threshold.

route_policy_support.py (and test_route_policy.py) already classify every route and check the status code; this file checks the intent.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import Settings
from app.domain.models import FinancialState
from app.mandate import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.funding.test_planner_executor_agree import SHORT_HOLD
from tests.funding.test_planner_executor_agree import build as build_world
from tests.security.route_policy_support import (
    AGENT as AGENT_ROUTES,
)
from tests.security.route_policy_support import (
    DEMO,
    DEMO_SETUP,
    OWNER,
    OWNER_SIDE,
    Caller,
    Key,
    _NoBody,
    build_request,
    deployed,
    fix_today,
    new_runtime,
    prepare_world,
    run_order,
)

NO_KEY: dict[str, str] = {}
AGENT_KEY = {"X-Agent-Key": "demo-agent-key"}
BUYER_KEY = {"X-Counterparty-Key": "demo-buyer-1-key"}
OWNER_TOKEN = {"X-Owner-Token": "demo-owner-token"}
CALLERS = [Caller("no credential", NO_KEY), Caller("agent key", AGENT_KEY, agent=True), Caller("buyer key", BUYER_KEY)]
REFUSED = (401, 403)


# ------------------------------------------------------------------------------------------------- what "no state change" means


def executed(rt: Runtime) -> list[dict[str, Any]]:
    """The results in the log that ran (status EXECUTED)."""
    results = [json.loads(o.result_json) for o in rt.store.operations()]
    return [r for r in results if r.get("status") == "EXECUTED"]


def snapshot(rt: Runtime) -> dict[str, Any]:
    s = rt.store
    state = s.get_state()
    return {
        "operations": len(s.operations()),
        "executed": len(executed(rt)),
        "state": hashlib.sha256(state.model_dump_json().encode()).hexdigest(),
        "commitments": [(c.id, str(getattr(c.status, "value", c.status))) for c in s.commitments()],
        "approvals": [(a.id, str(getattr(a.status, "value", a.status))) for a in s.approvals()],
        "documents": [(d.id, str(getattr(d.status, "value", d.status))) for d in s.contract_records()],
        "day": rt.day,
    }


def drawn(state: FinancialState, fid: str) -> int:
    return next(f.drawn_fen for f in state.facilities if f.id == fid)


# ------------------------------------------------------------------------------------------------- every owner write, three callers

OWNER_WRITES = sorted(k for k in (OWNER | OWNER_SIDE | DEMO_SETUP) if k[0] != "GET")
NAMED = [("POST", "/documents/{document_id}/confirm"), ("POST", "/documents/{document_id}/reject"), ("POST", "/negotiate/{offer_id}"),
         ("POST", "/alerts/{alert_id}/act"), ("POST", "/offers/{offer_id}/accept"), ("POST", "/offers/{offer_id}/decline"),
         ("POST", "/commitments/{commitment_id}/revoke"), ("POST", "/demo/bank-receipt"), ("POST", "/capex/apply"),
         ("POST", "/capex/contracts/{document_id}/commit"), ("POST", "/documents/{document_id}/terms")]


def test_the_named_routes_are_in_the_sweep() -> None:
    missing = [k for k in NAMED if k not in OWNER_WRITES]
    assert not missing, f"not swept as owner writes: {missing}"
    assert len(OWNER_WRITES) >= 40


@pytest.fixture(scope="module")
def sweep() -> Iterator[tuple[Runtime, TestClient, Any]]:
    """One world (an approval waiting, an agreement, three documents, an alert, offers): a refused caller changes nothing, so one is enough
    for all three callers, and any change by one would show on its own request."""
    mp = pytest.MonkeyPatch()
    try:
        with deployed(DEMO) as app:
            fix_today(mp)
            rt = new_runtime()
            client = TestClient(app, raise_server_exceptions=False)
            yield rt, client, prepare_world(client, DEMO, rt, static=True)
    finally:
        mp.undo()
        set_runtime(None)


@pytest.mark.parametrize("key", run_order(set(OWNER_WRITES)), ids=lambda k: f"{k[0]} {k[1]}")
@pytest.mark.parametrize("caller", CALLERS, ids=lambda c: c.name)
def test_an_owner_write_refuses_the_caller_and_changes_nothing(sweep, caller: Caller, key: Key) -> None:
    rt, client, w = sweep
    req = build_request(w, caller, key)
    before = snapshot(rt)
    kw: dict[str, Any] = {"headers": caller.headers, "params": req.params}
    if not isinstance(req.json, _NoBody):
        kw["json"] = req.json
    resp = client.request(req.method, req.url, **kw)
    assert resp.status_code in REFUSED, f"{caller.name} on {key}: {resp.status_code} {resp.text[:200]}"
    assert snapshot(rt) == before, f"{caller.name} on {key} was refused but the books moved"


def test_the_owner_still_reaches_the_gated_handlers(sweep) -> None:
    """Control, run after the refusals (module order): the same requests with the owner token get past the gate, so the refusals above are the
    credential's and not a malformed request's."""
    _, client, w = sweep
    owner = Caller("owner", OWNER_TOKEN, owner=True)
    reached = {}
    for key in [("POST", "/documents/{document_id}/confirm"), ("POST", "/documents/{document_id}/reject"),
                ("POST", "/approvals/{approval_id}"), ("POST", "/alerts/{alert_id}/act")]:
        req = build_request(w, owner, key)
        r = client.request(req.method, req.url, headers=OWNER_TOKEN, params=req.params,
                           **({} if isinstance(req.json, _NoBody) else {"json": req.json}))
        reached[key] = r.status_code
    assert all(code not in (401, 403, 404, 422, 500) for code in reached.values()), reached


# ------------------------------------------------------------------------------------------------- the agent-allowed routes


@pytest.fixture
def world() -> Iterator[tuple[Runtime, TestClient]]:
    from app.main import app

    rt = Runtime(Settings(), InMemoryLedgerStore(), demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    yield rt, TestClient(app, raise_server_exceptions=False)
    set_runtime(None)


def operation(kind: str, key: str, who: str = "AGENT", **fields: Any) -> dict[str, Any]:
    return {"kind": kind, "op_id": key, "idempotency_key": key, "mandate_version": 1, "requested_by": who, **fields}


ABOVE_TIER_1: list[tuple[str, dict[str, Any], str]] = [
    ("APPLY_FOR_FACILITY", {"facility_id": "FAC-GGL", "amount_fen": 20_000_000}, "PENDING_APPROVAL"),
    ("RECEIVE_PAYMENT", {"receivable_id": "RCV-A", "amount_fen": 4_200_000}, "PENDING_APPROVAL"),  # reported, not from the bank feed
    ("SIGN_PERSONAL_GUARANTEE", {"facility_id": "FAC-GGL"}, "REFUSED"),
    ("PLEDGE_COLLATERAL", {"facility_id": "FAC-GGL"}, "REFUSED"),
    ("ISSUE_EQUITY", {"amount_fen": 10_000_000}, "REFUSED"),
    ("CHANGE_MANDATE", {"new_version": 2}, "REFUSED"),
]


@pytest.mark.parametrize(("kind", "fields", "expected"), ABOVE_TIER_1, ids=[k for k, _, _ in ABOVE_TIER_1])
@pytest.mark.parametrize("claims", ["AGENT", "OWNER", "SYSTEM"])
def test_the_agent_key_cannot_take_an_operation_past_tier_1(world, kind: str, fields: dict[str, Any], expected: str, claims: str) -> None:
    """A claim to be the owner or the bank feed, made with the agent key, is read as the agent's."""
    rt, c = world
    before = snapshot(rt)
    r = c.post("/operations", headers=AGENT_KEY, json=operation(kind, f"x-{kind}-{claims}", claims, **fields))
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result["status"] == expected, result
    after = snapshot(rt)
    assert after["state"] == before["state"] and after["commitments"] == before["commitments"] and after["executed"] == before["executed"]
    assert len(after["approvals"]) == len(before["approvals"]) + (1 if expected == "PENDING_APPROVAL" else 0)
    assert all(status == "PENDING" for _, status in after["approvals"])


def test_the_agent_key_may_still_do_tier_1_work(world) -> None:
    """Control: the refusals above are about the tier, not about the route."""
    _, c = world
    r = c.post("/operations", headers=AGENT_KEY, json=operation("DRAW_FACILITY", "draw-ok", facility_id="FAC-LINE", amount_fen=1_000_000))
    assert r.status_code == 200 and r.json()["result"]["status"] == "EXECUTED" and r.json()["result"]["tier"] == "TIER_1"


def test_the_agent_key_cannot_add_a_facility_by_claiming_to_be_the_owner(world) -> None:
    rt, c = world
    fac = next(f for f in rt.store.get_state().facilities if f.id == "FAC-GGL")
    before = snapshot(rt)
    body = operation("ADD_FACILITY", "add-fac", "OWNER", facility={**fac.model_dump(mode="json"), "id": "FAC-BYPASS"})
    r = c.post("/operations", headers=AGENT_KEY, json=body)
    assert r.status_code == 200 and r.json()["result"]["status"] != "EXECUTED", r.text
    after = snapshot(rt)
    assert after["state"] == before["state"] and after["approvals"] == before["approvals"]
    assert all(f.id != "FAC-BYPASS" for f in rt.store.get_state().facilities)


RAW_FIELDS: dict[str, dict[str, Any]] = {
    "DRAW_FACILITY": {"facility_id": "FAC-LINE", "amount_fen": 1_000_000},
    "APPLY_FOR_FACILITY": {"facility_id": "FAC-GGL", "amount_fen": 1_000_000},
    "CHANGE_MANDATE": {"new_version": 2},
}


@pytest.mark.parametrize("caller", [CALLERS[0], CALLERS[2]], ids=lambda c: c.name)
@pytest.mark.parametrize("kind", ["DRAW_FACILITY", "APPLY_FOR_FACILITY", "CHANGE_MANDATE"])
def test_no_credential_and_a_buyer_key_cannot_post_an_operation(world, caller: Caller, kind: str) -> None:
    rt, c = world
    fields = RAW_FIELDS[kind]
    before = snapshot(rt)
    r = c.post("/operations", headers=caller.headers, json=operation(kind, f"nope-{kind}", "OWNER", **fields))
    assert r.status_code in REFUSED
    assert snapshot(rt) == before


@pytest.fixture
def queued(world) -> tuple[Runtime, TestClient, str]:
    rt, c = world
    r = c.post("/operations", headers=AGENT_KEY, json=operation("APPLY_FOR_FACILITY", "queue-me", facility_id="FAC-GGL", amount_fen=20_000_000))
    return rt, c, r.json()["result"]["approval_id"]


@pytest.mark.parametrize("decision", ["APPROVE", "REJECT"])
def test_only_the_owner_decides_an_approval(queued, decision: str) -> None:
    rt, c, aid = queued
    for headers in (NO_KEY, BUYER_KEY):
        before = snapshot(rt)
        r = c.post(f"/approvals/{aid}", headers=headers, json={"decision": decision})
        assert r.status_code in REFUSED and snapshot(rt) == before
    before = snapshot(rt)
    r = c.post(f"/approvals/{aid}", headers=AGENT_KEY, json={"decision": decision})
    assert r.status_code in (*REFUSED, 200)
    if r.status_code == 200:
        assert r.json()["result"]["status"] == "REFUSED" and r.json()["approval"]["decision"] is None and r.json()["approval"]["ran"] is False  # APR-1: undisclosed to a non-owner
    after = snapshot(rt)
    assert after["approvals"] == before["approvals"] and after["state"] == before["state"] and after["executed"] == before["executed"]


def test_only_the_owner_resets_a_circuit(world) -> None:
    rt, c = world
    for headers in (NO_KEY, BUYER_KEY):
        before = snapshot(rt)
        assert c.post("/circuit/BUYER-1/reset", headers=headers).status_code in REFUSED
        assert snapshot(rt) == before
    r = c.post("/circuit/BUYER-1/reset", headers=AGENT_KEY)
    assert r.status_code in (*REFUSED, 200)
    if r.status_code == 200:
        assert r.json()["result"]["status"] == "REFUSED"


def test_the_route_table_still_lists_exactly_these_agent_routes() -> None:
    assert AGENT_ROUTES == {("POST", "/operations"), ("POST", "/approvals/{approval_id}"), ("POST", "/circuit/{counterparty_id}/reset")}


# ------------------------------------------------------------------------------------------------- POST /nl

OWNER_ONLY_WORDS = ["approve APR-000001", "批准 APR-000001", "yes, approve it", "go ahead", "fund the gap", "补足资金缺口",
                    "confirm document DOC-000001", "reject document DOC-000001", "we have paid RCV-A in full, mark it settled",
                    "draw ¥100,000 on FAC-LINE", "accept the offer and sign it"]


def nl(c: TestClient, headers: dict[str, str], text: str, actor: str, **kw: Any) -> Any:
    return c.post("/nl", headers=headers, json={"session_id": "bypass-1", "actor": actor, "text": text, **kw})


def no_effect(rt: Runtime, before: dict[str, Any]) -> None:
    after = snapshot(rt)
    assert after["state"] == before["state"] and after["commitments"] == before["commitments"]
    assert after["executed"] == before["executed"] and after["approvals"] == before["approvals"] and after["documents"] == before["documents"]


@pytest.mark.parametrize("headers", [NO_KEY, BUYER_KEY], ids=["no credential", "buyer key"])
@pytest.mark.parametrize("text", OWNER_ONLY_WORDS)
def test_the_owner_channel_needs_the_owner_token_or_the_agent_key(queued, headers: dict[str, str], text: str) -> None:
    rt, c, _ = queued
    before = snapshot(rt)
    r = nl(c, headers, text, "OWNER")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "CREDENTIAL_REQUIRED"
    assert snapshot(rt) == before


@pytest.mark.parametrize("headers", [NO_KEY, BUYER_KEY], ids=["no key", "buyer-1 key"])
@pytest.mark.parametrize("text", OWNER_ONLY_WORDS)
def test_a_counterparty_message_can_never_approve_fund_confirm_or_book_a_payment(queued, headers: dict[str, str], text: str) -> None:
    rt, c, aid = queued
    before = snapshot(rt)
    r = nl(c, headers, text.replace("APR-000001", aid), "COUNTERPARTY", counterparty_id="BUYER-1")
    assert r.status_code in (200, 403, 429), r.text
    if r.status_code == 200:
        assert all(o["status"] not in ("EXECUTED", "PENDING_APPROVAL") for o in r.json().get("operations", []))
    no_effect(rt, before)


@pytest.mark.parametrize("text", ["approve APR-000001", "批准 APR-000001", "yes, approve it", "confirm document DOC-000001"])
def test_the_agent_keys_chat_cannot_decide_or_confirm(queued, text: str) -> None:
    rt, c, aid = queued
    before = snapshot(rt)
    r = nl(c, AGENT_KEY, text.replace("APR-000001", aid), "OWNER")
    assert r.status_code == 200, r.text
    assert all(o["status"] != "EXECUTED" for o in r.json().get("operations", []))
    no_effect(rt, before)


def test_the_agent_keys_chat_cannot_run_a_leg_above_the_approval_threshold() -> None:
    """The short-hold world: the cure is an advance at 32.5% a year, above the 15% the owner signed. The agent's go-ahead queues it."""
    from tests.nl.conftest import build_app

    rt = build_world(SHORT_HOLD)
    set_runtime(rt)
    try:
        c = TestClient(build_app())
        drawn_before = drawn(rt.store.get_state(), "FAC-IF")
        for text in ("Find me the cheapest way to fund the cash gap", "go ahead", "fund the gap", "go ahead"):
            r = nl(c, AGENT_KEY, text, "OWNER", session_id="agent-leg")
            assert r.status_code == 200, r.text
        state = rt.store.get_state()
        assert drawn(state, "FAC-IF") == drawn_before  # the dear leg did not run (a cheaper Tier 1 leg may have)
        approvals = [(a.kind, str(getattr(a.status, "value", a.status))) for a in rt.store.approvals()]
        assert approvals and all(status == "PENDING" for _, status in approvals), approvals  # queued for the owner, none decided
        assert all(r.get("tier") == "TIER_1" for r in executed(rt))
    finally:
        set_runtime(None)
