"""Route authorization policy, enforced route by route (security register: external review of 16 Oct, "a status-code sweep against a baseline
does not show the baseline was right; identify each method and route").

What this adds to the sweep scripts under docs/security/evidence (authz_sweep_v3.py, sweep_policy.py):

* The routes are enumerated from the app's route table, and each (method, path) must belong to exactly one class in the table in
  route_policy_support.py. A new route that is in no class fails `test_every_route_has_exactly_one_class`, so it cannot slip in unclassified.
  The class is also checked against the code: an owner or demo/setup route must run `require_owner`, an agent-channel route
  `require_owner_or_agent`, and a public, buyer-channel or owner-side route neither (the owner-side routes check the token in the handler).
* The request is the owner's own: real ids (an offer with a verdict and a counter, a queued approval, an agreement, uploaded documents, a
  borrower file) and minimal valid bodies, not `{}` and a placeholder. A refused caller is refused on the request the owner makes, so a
  missing check shows as a 200 and not as a 404 that would have stopped whoever asked. The books are compared before and after every
  refusal: a refused request changes nothing.
* For the owner it records, per route, whether the request reached the handler or stopped before it, and asserts a floor.

Callers: anonymous, a wrong owner token, a wrong agent key, the agent key, the bank-feed key, a buyer key and the owner token under
DEMO_MODE=1; under DEMO_MODE=0 with production credentials every published demo value, plus the production values; and DEMO_MODE=0 with no
credentials configured (503 on the owner routes).

Cost choices (the whole file runs in well under two minutes): one fresh in-memory runtime per caller, so a write by one caller can never mask
or cause another's answer; the ids of a refused caller's world are found once (its offers are evaluated once), the owner's are refreshed
before every request so each verdict is on the current state version; rate limits are switched off (SEC-20 has its own tests, and a 429
would hide an authorization answer); every feature flag is on so that a flagged route reaches its handler.

Classes checked against the code (app/api/*.py), and where this suite found them to differ from the brief, are recorded in the test
`test_class_definitions_match_the_code`.
"""

from __future__ import annotations

import hashlib
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from tests.security.route_policy_support import (
    AGENT,
    BUYER,
    CLASSES,
    DEMO,
    DEMO_SETUP,
    DOCS,
    OWNER,
    OWNER_SIDE,
    PRODUCTION,
    PUBLIC,
    UNCONFIGURED,
    Caller,
    Key,
    Mode,
    _NoBody,
    build_request,
    class_of,
    classify,
    deployed,
    enumerate_routes,
    fix_today,
    new_runtime,
    prepare_world,
    run_order,
    template_regex,
)

# The floor of owner routes that reach their handler with a real id and a minimal valid body (DEMO_MODE=1). Set to what the suite achieves.
OWNER_REACH_FLOOR = 89
REFUSED = (401, 403)


# ------------------------------------------------------------------------------------------------- one pass of one mode


@dataclass
class Row:
    caller: Caller
    key: Key
    klass: str
    status: int
    outcome: str
    changed: str  # what a request changed in the books, "" when nothing
    detail: str = ""


@dataclass
class Run:
    mode: Mode
    routes: dict[Key, set[str]]
    rows: list[Row] = field(default_factory=list)
    seconds: float = 0.0
    extras: dict[str, Any] = field(default_factory=dict)

    def of(self, caller: str) -> list[Row]:
        return [r for r in self.rows if r.caller.name == caller]


def snapshot(rt: Runtime) -> tuple[Any, ...]:
    """What a refused request must leave alone: the log, the books, the agreements, the approvals and the day."""
    s = rt.store
    state = hashlib.sha256(s.get_state().model_dump_json().encode()).hexdigest()
    approvals = tuple((a.id, str(a.status)) for a in s.approvals())
    return len(s.operations()), state, tuple(c.id for c in s.commitments()), approvals, rt.day, len(s.contract_records())


def what_changed(before: tuple[Any, ...], after: tuple[Any, ...]) -> str:
    names = ("operations logged", "books", "agreements", "approvals", "day", "documents")
    return ", ".join(n for n, b, a in zip(names, before, after, strict=True) if b != a)


def detail_of(body: Any) -> str:
    d = body.get("detail") if isinstance(body, dict) else None
    return str(d.get("code", "")) if isinstance(d, dict) else ""


def run_mode(mode: Mode, app: FastAPI) -> Run:
    started = time.monotonic()
    routes = enumerate_routes(app)
    run = Run(mode, routes)
    for caller in mode.callers:
        rt = new_runtime()
        client = TestClient(app, raise_server_exceptions=False)
        w = prepare_world(client, mode, rt, static=not caller.owner)
        for key in run_order(set(routes) - DOCS):
            req = build_request(w, caller, key)
            assert template_regex(key[1]).match(req.url), f"the request for {key} went to {req.url}"
            before = snapshot(rt)
            kw: dict[str, Any] = {"headers": caller.headers, "params": req.params}
            if not isinstance(req.json, _NoBody):
                kw["json"] = req.json
            resp = client.request(req.method, req.url, **kw)
            try:
                body = resp.json()
            except ValueError:
                body = None
            run.rows.append(Row(caller, key, class_of(key)[0], resp.status_code, classify(resp.status_code, body),
                                what_changed(before, snapshot(rt)), detail_of(body)))
        for key in sorted(DOCS):  # the docs routes are not in the owner's plan: nobody needs an id to read them
            resp = client.get(key[1], headers=caller.headers)
            run.rows.append(Row(caller, key, "docs", resp.status_code, "docs", ""))
        run.extras.setdefault("runtimes", []).append((caller.name, rt, client))
    run.seconds = time.monotonic() - started
    return run


@pytest.fixture(scope="module")
def demo_run() -> Run:
    mp = pytest.MonkeyPatch()
    try:
        with deployed(DEMO) as app:
            fix_today(mp)
            run = run_mode(DEMO, app)
    finally:
        mp.undo()
        set_runtime(None)
    return run


@pytest.fixture(scope="module")
def prod_run() -> Run:
    mp = pytest.MonkeyPatch()
    try:
        with deployed(PRODUCTION) as app:
            fix_today(mp)
            run = run_mode(PRODUCTION, app)
    finally:
        mp.undo()
        set_runtime(None)
    return run


@pytest.fixture(scope="module")
def unconfigured_run() -> Run:
    try:
        with deployed(UNCONFIGURED) as app:
            run = run_mode(UNCONFIGURED, app)
    finally:
        set_runtime(None)
    return run


# ------------------------------------------------------------------------------------------------- the expectation per class


def must_be_refused(klass: str, caller: Caller) -> bool:
    """Whether the policy refuses this caller on a route of this class."""
    if klass in ("public", "docs", "buyer"):
        return False
    if klass == "agent":
        return not (caller.owner or caller.agent)
    return not caller.owner  # owner, owner_side, demo_setup


def refusal_codes(klass: str, mode: Mode) -> tuple[int, ...]:
    if klass == "owner_side":
        return (403,)  # the handler checks the token itself: 403 whoever is missing, configured or not
    return REFUSED if mode.configured else (503,)


def fail_lines(rows: list[Row], what: str) -> str:
    return f"{what}:\n" + "\n".join(f"  {r.key[0]} {r.key[1]} as {r.caller.name}: {r.status} {r.detail} {r.changed}".rstrip() for r in rows)


# ------------------------------------------------------------------------------------------------- the table against the code


def test_every_route_has_exactly_one_class(demo_run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    seen = demo_run.routes
    unclassified = [k for k in seen if not class_of(k)]
    assert not unclassified, f"routes in no class (add each to a class in route_policy_support.py): {sorted(unclassified)}"
    several = {k: class_of(k) for k in seen if len(class_of(k)) > 1}
    assert not several, f"routes in more than one class: {several}"
    missing = sorted(k for keys in CLASSES.values() for k in keys if k not in seen)
    assert not missing, f"the table names routes that do not exist: {missing}"
    counts = Counter(class_of(k)[0] for k in seen)
    with capsys.disabled():
        print(f"\n[route-policy] {len(seen)} routes (HEAD/OPTIONS skipped) in DEMO_MODE=1: " + ", ".join(f"{n} {counts[n]}" for n in CLASSES))


def test_the_docs_routes_exist_in_demo_mode_and_do_not_exist_otherwise(demo_run: Run, prod_run: Run) -> None:
    assert DOCS <= set(demo_run.routes)
    assert not DOCS & set(prod_run.routes), "the docs and schema routes are registered with DEMO_MODE=0 (SEC-13)"
    assert set(demo_run.routes) - DOCS == set(prod_run.routes), "the route table differs between DEMO_MODE=1 and DEMO_MODE=0"


def test_class_definitions_match_the_code(demo_run: Run) -> None:
    """Each class against the dependencies the code runs, not against the brief."""
    wrong: list[str] = []
    for key, deps in demo_run.routes.items():
        klass = class_of(key)[0]
        gated = "require_owner" in deps
        agent_gated = "require_owner_or_agent" in deps
        if klass in ("owner", "demo_setup") and not gated:
            wrong.append(f"{key} is class {klass} but runs no require_owner")
        elif klass == "agent" and not agent_gated:
            wrong.append(f"{key} is class agent but runs no require_owner_or_agent")
        elif klass in ("public", "docs", "buyer", "owner_side") and (gated or agent_gated):
            wrong.append(f"{key} is class {klass} but runs an owner dependency")
    assert not wrong, "\n".join(wrong)
    # the owner-side routes are gated in the handler, and the buyer channel's POST /nl by its actor; both are tested behaviourally below.
    assert OWNER_SIDE.isdisjoint(AGENT | BUYER | PUBLIC | OWNER | DEMO_SETUP)


# ------------------------------------------------------------------------------------------------- DEMO_MODE=1


def test_demo_non_owner_callers_are_refused_on_every_owner_route_and_change_nothing(demo_run: Run) -> None:
    bad = [r for r in demo_run.rows if r.klass != "docs" and must_be_refused(r.klass, r.caller)
           and r.status not in refusal_codes(r.klass, demo_run.mode)]
    assert not bad, fail_lines(bad, "not refused")
    touched = [r for r in demo_run.rows if r.klass != "docs" and must_be_refused(r.klass, r.caller) and r.changed]
    assert not touched, fail_lines(touched, "refused, but the books changed")


def test_demo_public_routes_answer_everyone_and_the_docs_are_served(demo_run: Run) -> None:
    pub = [r for r in demo_run.rows if r.klass == "public"]
    assert len(pub) == len(PUBLIC) * len(DEMO.callers)
    bad = [r for r in pub if r.status != 200]
    assert not bad, fail_lines(bad, "public route did not answer 200")
    docs = [r for r in demo_run.rows if r.klass == "docs"]
    assert len(docs) == len(DOCS) * len(DEMO.callers)
    bad = [r for r in docs if r.status != 200]
    assert not bad, fail_lines(bad, "docs route in demo mode did not answer 200")


def test_demo_buyer_channel_accepts_everyone_and_agent_channel_accepts_the_agent(demo_run: Run) -> None:
    buyer = [r for r in demo_run.rows if r.klass == "buyer"]
    bad = [r for r in buyer if r.status != 200]
    assert not bad, fail_lines(bad, "buyer channel did not answer 200")
    agent = [r for r in demo_run.rows if r.klass == "agent" and (r.caller.agent or r.caller.owner)]
    assert len(agent) == len(AGENT) * 2
    bad = [r for r in agent if r.status in (401, 403, 503) or r.status >= 500]
    assert not bad, fail_lines(bad, "agent channel refused the agent key (or the owner)")
    # the agent's decision on an approval is the executor's to refuse (INSUFFICIENT_AUTHORITY), and the approval stays for the owner
    decided = next(r for r in demo_run.rows if r.caller.agent and r.key == ("POST", "/approvals/{approval_id}"))
    assert decided.status == 200 and "approvals" not in decided.changed, "the agent key must not be able to decide an approval"


def test_demo_owner_only_actions_with_the_agent_key_or_bank_key_are_refused_even_on_approval_ids(demo_run: Run) -> None:
    """The bank-feed key alone has no standing on the agent channel (it is accepted only beside the agent key, to speak as SYSTEM)."""
    rows = [r for r in demo_run.of("bank-feed key") if r.klass == "agent"]
    assert [r.status for r in rows] == [401, 401, 401], fail_lines(rows, "bank-feed key on the agent channel")


def test_demo_the_owner_side_routes_answer_403_to_everyone_but_the_owner(demo_run: Run) -> None:
    rows = [r for r in demo_run.rows if r.klass == "owner_side" and not r.caller.owner]
    assert len(rows) == len(OWNER_SIDE) * (len(DEMO.callers) - 1)
    bad = [r for r in rows if r.status != 403 or r.changed]
    assert not bad, fail_lines(bad, "owner-side route did not answer 403 without a change")
    mine = [r for r in demo_run.rows if r.klass == "owner_side" and r.caller.owner]
    bad = [r for r in mine if r.status != 200]
    assert not bad, fail_lines(bad, "owner-side route did not answer the owner")


def test_demo_the_owner_chat_channel_needs_the_owner_token_or_the_agent_key(demo_run: Run) -> None:
    """POST /nl is open to a buyer (proposal only), but its OWNER actor needs the owner token or the agent key."""
    for name, rt, client in demo_run.extras["runtimes"]:
        caller = next(c for c in DEMO.callers if c.name == name)
        set_runtime(rt)
        r = client.post("/nl", json={"actor": "OWNER", "text": "What is my cash position?"}, headers=caller.headers)
        expected = 200 if (caller.owner or caller.agent) else 401
        assert r.status_code == expected, f"POST /nl as the OWNER actor with {name}: {r.status_code} (expected {expected})"
    set_runtime(None)


def test_demo_owner_reaches_the_handler(demo_run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    summarise("DEMO_MODE=1", demo_run, "owner token", OWNER_REACH_FLOOR, capsys)


# ------------------------------------------------------------------------------------------------- DEMO_MODE=0 with production credentials


def test_production_every_published_demo_value_is_refused_on_every_route_that_needs_a_credential(prod_run: Run) -> None:
    bad, touched = [], []
    for r in prod_run.rows:
        if r.klass == "docs":
            continue
        if must_be_refused(r.klass, r.caller):
            if r.status not in refusal_codes(r.klass, prod_run.mode):
                bad.append(r)
            if r.changed:
                touched.append(r)
    assert not bad, fail_lines(bad, "not refused")
    assert not touched, fail_lines(touched, "refused, but the books changed")
    demo_callers = [c for c in PRODUCTION.callers if c.name.startswith("published demo")]
    assert len(demo_callers) == 4
    for c in demo_callers:  # every one of them was run on every non-public route
        ran = {r.key for r in prod_run.of(c.name)}
        assert ran >= set(prod_run.routes) - PUBLIC, c.name


def test_production_public_buyer_and_agent_channels(prod_run: Run) -> None:
    bad = [r for r in prod_run.rows if r.klass in ("public", "buyer") and r.status != 200]
    assert not bad, fail_lines(bad, "public or buyer-channel route did not answer 200")
    agent = [r for r in prod_run.rows if r.klass == "agent" and (r.caller.agent or r.caller.owner)]
    bad = [r for r in agent if r.status in (401, 403, 503) or r.status >= 500]
    assert not bad, fail_lines(bad, "agent channel refused the production agent key")
    for name in ("published demo agent key", "published demo owner token", "published demo bank-feed key"):
        rows = [r for r in prod_run.of(name) if r.klass == "agent"]
        assert [r.status for r in rows] == [401, 401, 401], fail_lines(rows, name + " on the agent channel")


def test_production_the_docs_and_schema_routes_answer_404_to_everyone(prod_run: Run) -> None:
    rows = [r for r in prod_run.rows if r.klass == "docs"]
    assert len(rows) == len(DOCS) * len(PRODUCTION.callers)
    bad = [r for r in rows if r.status != 404]
    assert not bad, fail_lines(bad, "docs route answered with DEMO_MODE=0")


def test_production_a_published_buyer_key_binds_no_buyer() -> None:
    """The channel keys are demo values too: with COUNTERPARTY_KEYS set, `demo-buyer-1-key` is an unknown key. A request under it is an
    unauthenticated proposal (the sender is not BUYER-1, and the unknown key is itself recorded); under the production key it is BUYER-1's."""
    from app.decisions.facts import ReceivedFact, parse_fact

    with deployed(PRODUCTION) as app:
        for name, headers, bound in (("published demo buyer key", {"X-Counterparty-Key": "demo-buyer-1-key"}, False),
                                     ("production buyer key", {"X-Counterparty-Key": "prod-buyer1-9f3a"}, True)):
            rt = new_runtime()
            c = TestClient(app, raise_server_exceptions=False)
            said = c.post("/nl", headers=headers, json={"actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": "Can you pay earlier?"})
            assert said.status_code == 200, said.text
            wrong_key = [e for e in rt.store.security_events() if e.id.startswith("SEC-CPKEY-")]
            assert bool(wrong_key) is (not bound), f"{name}: {len(wrong_key)} wrong-key events"
            r = c.post("/offers", headers=headers, json={"fixture_id": "EX02_EARLY_1_5"})
            assert r.status_code == 200, r.text
            facts = [parse_fact(f) for f in rt.store.decision_facts()]
            via = [f.via for f in facts if isinstance(f, ReceivedFact) and f.offer_id == r.json()["offer"]["offer_id"]]
            assert via == ["buyer_key" if bound else "anonymous"], f"{name}: the offer arrived as {via}"
    set_runtime(None)


def test_production_owner_reaches_the_handler(prod_run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    summarise("DEMO_MODE=0", prod_run, "production owner token", OWNER_REACH_FLOOR - 5, capsys)


# ------------------------------------------------------------------------------------------------- DEMO_MODE=0, nothing configured


def test_unconfigured_deployment_fails_closed_on_every_credentialed_route(unconfigured_run: Run) -> None:
    """DEMO_MODE=0 with no OWNER_TOKEN, AGENT_KEY, BANK_FEED_KEY or COUNTERPARTY_KEYS: the owner routes answer 503 (not configured), the
    owner-side routes 403, the agent channel 503, and the published demo values open nothing."""
    bad = [r for r in unconfigured_run.rows if r.klass != "docs" and must_be_refused(r.klass, r.caller)
           and r.status not in refusal_codes(r.klass, unconfigured_run.mode)]
    assert not bad, fail_lines(bad, "not refused as unconfigured")
    touched = [r for r in unconfigured_run.rows if r.changed]
    assert not touched, fail_lines(touched, "the books changed on an unconfigured deployment")
    open_ = [r for r in unconfigured_run.rows if r.klass in ("public", "buyer") and r.status != 200]
    assert not open_, fail_lines(open_, "public or buyer-channel route did not answer 200")
    docs = [r for r in unconfigured_run.rows if r.klass == "docs"]
    assert docs and all(r.status == 404 for r in docs)


# ------------------------------------------------------------------------------------------------- the owner's reach


def summarise(label: str, run: Run, owner_name: str, floor: int, capsys: pytest.CaptureFixture[str]) -> None:
    rows = [r for r in run.of(owner_name) if r.klass != "docs"]
    owner_routes = [r for r in rows if r.klass in ("owner", "demo_setup")]
    reached = [r for r in owner_routes if r.outcome == "handler"]
    stopped = [r for r in owner_routes if r.outcome != "handler"]
    errors = [r for r in rows if r.outcome == "error"]
    with capsys.disabled():
        print(f"\n[route-policy] {label}: {run.seconds:.1f}s for {len(run.rows)} requests; the owner reached the handler on "
              f"{len(reached)} of {len(owner_routes)} owner and demo/setup routes "
              f"({Counter(r.outcome for r in owner_routes)}); {sum(r.outcome == 'handler' for r in rows)} of {len(rows)} counting every class")
        for r in stopped:
            print(f"  stopped before the handler: {r.key[0]} {r.key[1]} -> {r.status} {r.outcome} {r.detail}")
        by_status = Counter(r.status for r in owner_routes)
        print(f"  owner answers: {dict(sorted(by_status.items()))}")
    assert not errors, fail_lines(errors, "a server error on a valid owner request")
    refused = [r for r in owner_routes if r.outcome == "refused"]
    assert all(r.klass == "demo_setup" and not run.mode.demo for r in refused), fail_lines(
        [r for r in refused if not (r.klass == "demo_setup" and not run.mode.demo)], "the owner was refused")
    assert len(reached) >= floor, fail_lines(stopped, f"only {len(reached)} owner routes reached the handler (floor {floor})")
