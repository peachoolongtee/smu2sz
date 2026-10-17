"""Support for tests/security/test_route_policy.py: the route table, the callers, a world to call in, and the owner's request for every route.

Nothing here is product code. It builds a runtime the way tests/api/conftest.py does, calls the app through its public HTTP surface and
reads the books only to check that a refused request left them as they were.

A "world" is one fresh in-memory runtime on the golden books, prepared (by the owner) so that every id a route takes is real: an offer
with a verdict and a counter, a queued approval, a booked agreement, uploaded documents, a borrower file. The same request builder then
serves every caller, so a refused caller is refused on the request the owner would have made, not on a placeholder that would stop at
validation whoever asked.
"""

from __future__ import annotations

import datetime
import importlib
import re
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

Key = tuple[str, str]  # (METHOD, path template)

# ------------------------------------------------------------------------------------------------- the classes, one table
# Every route of the app belongs to exactly one of these. A route that is in none fails test_every_route_has_exactly_one_class, so a new
# route cannot slip in unclassified. The classes were checked against app/api/*.py (see the test's docstring for what was found).

PUBLIC: set[Key] = {("GET", "/health"), ("GET", "/clock"), ("GET", "/fixtures/offers")}
DOCS: set[Key] = {("GET", "/docs"), ("GET", "/redoc"), ("GET", "/openapi.json"), ("GET", "/docs/oauth2-redirect")}  # public, demo mode only
BUYER: set[Key] = {("POST", "/offers"), ("POST", "/nl")}  # open by design: a buyer's own channel, anonymous allowed (proposal only)
AGENT: set[Key] = {("POST", "/operations"), ("POST", "/approvals/{approval_id}"), ("POST", "/circuit/{counterparty_id}/reset")}
OWNER_SIDE: set[Key] = {("POST", "/clock/advance"), ("POST", "/nl/reset"), ("POST", "/nl/opener")}  # no dependency; the handler answers 403
DEMO_SETUP: set[Key] = {
    ("POST", "/demo/bank-receipt"), ("POST", "/demo/reset"), ("POST", "/demo/restore"), ("GET", "/demo/story"),
    ("GET", "/setup/documents"), ("POST", "/setup/documents"), ("POST", "/setup/open"), ("POST", "/setup/preview"), ("GET", "/setup/status"),
}
OWNER: set[Key] = {
    ("GET", "/activity"),
    ("GET", "/alerts"),
    ("POST", "/alerts/{alert_id}/act"),
    ("GET", "/approvals/queue"),
    ("GET", "/audit"),
    ("POST", "/borrower-file"),
    ("GET", "/borrower-file/{file_id}"),
    ("GET", "/borrower-file/{file_id}.docx"),
    ("GET", "/borrower-file/{file_id}.html"),
    ("GET", "/borrower-file/{file_id}.pdf"),
    ("GET", "/buyers/{buyer_id}/envelope"),
    ("GET", "/buyers/{buyer_id}/exposure"),
    ("GET", "/buyers/{buyer_id}/inputs"),
    ("POST", "/buyers/{buyer_id}/inputs"),
    ("POST", "/capex/apply"),
    ("POST", "/capex/contracts/{document_id}/commit"),
    ("POST", "/capex/contracts/{document_id}/evaluate"),
    ("POST", "/capex/evaluate"),
    ("POST", "/capex/plans"),
    ("GET", "/cash/price-curve"),
    ("POST", "/commitments/{commitment_id}/revoke"),
    ("GET", "/customers"),
    ("GET", "/customers/{customer_id}/overview"),
    ("GET", "/deals"),
    ("GET", "/deals/{counterparty_id}"),
    ("GET", "/decisions"),
    ("GET", "/decisions/{decision_id}"),
    ("GET", "/decisions/{decision_id}/compare"),
    ("GET", "/decisions/{decision_id}/exposure"),
    ("GET", "/decisions/{decision_id}/tracker"),
    ("GET", "/documents"),
    ("POST", "/documents"),
    ("GET", "/documents/{document_id}"),
    ("POST", "/documents/{document_id}/confirm"),
    ("POST", "/documents/{document_id}/reject"),
    ("GET", "/evidence"),
    ("POST", "/facilities/compile"),
    ("GET", "/finance/health"),
    ("POST", "/finance/health"),
    ("GET", "/firm/inputs"),
    ("POST", "/firm/inputs"),
    ("GET", "/fixtures/capex-contracts"),
    ("GET", "/fixtures/contracts"),
    ("GET", "/home"),
    ("GET", "/ledger"),
    ("GET", "/lending/eligibility"),
    ("POST", "/lending/eligibility"),
    ("POST", "/lending/products/{product_id}/add-to-menu"),
    ("GET", "/mandate"),
    ("GET", "/nav/counts"),
    ("POST", "/negotiate/{offer_id}"),
    ("GET", "/offers/{offer_id}"),
    ("POST", "/offers/{offer_id}/accept"),
    ("POST", "/offers/{offer_id}/buyer-reply"),
    ("GET", "/offers/{offer_id}/compare"),
    ("POST", "/offers/{offer_id}/counters/{counter_id}/buyer-accepted"),
    ("POST", "/offers/{offer_id}/counters/{counter_id}/buyer-declined"),
    ("GET", "/offers/{offer_id}/counters/{counter_id}/message"),
    ("POST", "/offers/{offer_id}/counters/{counter_id}/offered"),
    ("POST", "/offers/{offer_id}/counters/{counter_id}/offered/withdraw"),
    ("POST", "/offers/{offer_id}/decline"),
    ("POST", "/offers/{offer_id}/evaluate"),
    ("GET", "/offers/{offer_id}/exposure"),
    ("GET", "/offers/{offer_id}/picture"),
    ("GET", "/offers/{offer_id}/scenarios"),
    ("GET", "/pilot/journal"),
    ("POST", "/pilot/journal"),
    ("GET", "/purchases"),
    ("GET", "/purchases/{document_id}"),
    ("GET", "/receivables"),
    ("GET", "/receivables/worth"),
    ("GET", "/receivables/{receivable_id}/chase"),
    ("GET", "/reconciliation"),
    ("POST", "/router/plan"),
    ("GET", "/security/summary"),
    ("GET", "/state"),
    ("GET", "/trajectory"),
    ("POST", "/whatif"),
    ("GET", "/whatif/presets"),
    ("GET", "/worklist"),
}

CLASSES: dict[str, set[Key]] = {"public": PUBLIC, "docs": DOCS, "buyer": BUYER, "agent": AGENT, "owner_side": OWNER_SIDE,
                                "demo_setup": DEMO_SETUP, "owner": OWNER}


def class_of(key: Key) -> list[str]:
    return [name for name, keys in CLASSES.items() if key in keys]


# ------------------------------------------------------------------------------------------------- enumerating the routes


def _flatten(routes: Any) -> Iterator[Any]:
    """FastAPI 0.142 keeps an included router as a lazy branch (`_IncludedRouter`) that yields its routes, with the include prefix and
    dependencies applied, from `effective_candidates()`; older versions list the flat routes. Both are handled."""
    for r in routes:
        nested = getattr(r, "effective_candidates", None)
        if callable(nested):
            yield from _flatten(nested())
        else:
            yield r


def _dependency_names(dependant: Any) -> set[str]:
    names: set[str] = set()
    for d in getattr(dependant, "dependencies", []) or []:
        call = getattr(d, "call", None)
        names.add(getattr(call, "__qualname__", repr(call)))
        names |= _dependency_names(d)
    return names


def enumerate_routes(app: FastAPI) -> dict[Key, set[str]]:
    """Every (METHOD, path template) of the app's route table (HEAD and OPTIONS are the automatic duplicates and are skipped), with the
    names of the dependency callables the route runs before its handler."""
    out: dict[Key, set[str]] = {}
    for r in _flatten(app.routes):
        path, methods = getattr(r, "path", None), getattr(r, "methods", None)
        if not path or not methods:
            continue
        names = _dependency_names(getattr(r, "dependant", None))
        for m in sorted(methods - {"HEAD", "OPTIONS"}):
            assert (m, path) not in out, f"{m} {path} is registered twice (the second would be shadowed)"
            out[(m, path)] = names
    return out


# ------------------------------------------------------------------------------------------------- modes and callers


@dataclass(frozen=True)
class Caller:
    name: str
    headers: dict[str, str]
    owner: bool = False  # holds the configured owner token
    agent: bool = False  # holds the configured agent key (and not the owner token)


@dataclass(frozen=True)
class Mode:
    name: str
    demo: bool
    env: dict[str, str]
    callers: list[Caller]
    owner_headers: dict[str, str] | None  # None when no owner token is configured
    agent_headers: dict[str, str] | None
    buyer_headers: dict[str, str] | None  # a header that really binds BUYER-1 in this mode, else None
    configured: bool = True


ALL_FEATURES = ["TERMS_GUARD", "DEBT_DESK", "CAPEX", "BORROWER_FILE", "BUYER_NEGOTIATION", "SECURITY_SCENES", "ALERTS", "EXPECTED_PLANS",
                "ENVELOPE", "PRICE_CURVE", "COLLECTIONS_WORTH", "EXPOSURE", "CUSTOMER_ECONOMICS", "CONTRACTS", "PILOT_JOURNAL",
                "CAPEX_CONTRACTS"]
CREDENTIAL_ENV = ["OWNER_TOKEN", "AGENT_KEY", "BANK_FEED_KEY", "COUNTERPARTY_KEYS", "OWNER_PUBLIC_KEY_HEX"]

DEMO_OWNER = {"X-Owner-Token": "demo-owner-token"}
DEMO_AGENT = {"X-Agent-Key": "demo-agent-key"}
DEMO_BANK = {"X-Bank-Feed-Key": "demo-bank-feed-key"}
DEMO_BUYER = {"X-Counterparty-Key": "demo-buyer-1-key"}
WRONG_OWNER = {"X-Owner-Token": "not-the-owner-token"}
WRONG_AGENT = {"X-Agent-Key": "not-the-agent-key"}

DEMO = Mode(
    "DEMO_MODE=1", True, {"DEMO_MODE": "1"},
    [Caller("anonymous", {}), Caller("wrong owner token", WRONG_OWNER), Caller("wrong agent key", WRONG_AGENT),
     Caller("agent key", DEMO_AGENT, agent=True), Caller("bank-feed key", DEMO_BANK), Caller("buyer key (demo-buyer-1-key)", DEMO_BUYER),
     Caller("owner token", DEMO_OWNER, owner=True)],
    DEMO_OWNER, DEMO_AGENT, DEMO_BUYER)

PROD_OWNER = {"X-Owner-Token": "prod-owner-9f3a"}
PROD_AGENT = {"X-Agent-Key": "prod-agent-9f3a"}
PROD_BANK = {"X-Bank-Feed-Key": "prod-bank-9f3a"}
PROD_BUYER = {"X-Counterparty-Key": "prod-buyer1-9f3a"}

PRODUCTION = Mode(
    "DEMO_MODE=0", False,
    {"DEMO_MODE": "0", "OWNER_TOKEN": "prod-owner-9f3a", "AGENT_KEY": "prod-agent-9f3a", "BANK_FEED_KEY": "prod-bank-9f3a",
     "COUNTERPARTY_KEYS": "BUYER-1=prod-buyer1-9f3a", "OWNER_PUBLIC_KEY_HEX": demo_owner_public_key_hex()},
    [Caller("anonymous", {}), Caller("wrong owner token", WRONG_OWNER),
     Caller("published demo owner token", DEMO_OWNER), Caller("published demo agent key", DEMO_AGENT),
     Caller("published demo bank-feed key", DEMO_BANK), Caller("published demo buyer key", DEMO_BUYER),
     Caller("production bank-feed key", PROD_BANK), Caller("production buyer key", PROD_BUYER),
     Caller("production agent key", PROD_AGENT, agent=True), Caller("production owner token", PROD_OWNER, owner=True)],
    PROD_OWNER, PROD_AGENT, PROD_BUYER)

UNCONFIGURED = Mode(
    "DEMO_MODE=0, no credentials", False, {"DEMO_MODE": "0"},
    [Caller("anonymous", {}), Caller("published demo owner token", DEMO_OWNER), Caller("published demo agent key", DEMO_AGENT),
     Caller("published demo bank-feed key", DEMO_BANK), Caller("published demo buyer key", DEMO_BUYER)],
    None, None, None, configured=False)


@contextmanager
def deployed(mode: Mode) -> Iterator[FastAPI]:
    """The app as a process started in `mode` would build it: env set, `app.main` re-imported (the docs routes are decided at import),
    every feature flag on (so a flagged route reaches its handler), rate limits off (they are SEC-20's own test, and a 429 would hide an
    authorization answer). Restores the env and re-imports under the suite's own mode when it leaves."""
    from app import main

    mp = pytest.MonkeyPatch()
    try:
        for name in CREDENTIAL_ENV:
            mp.delenv(name, raising=False)
        for f in ALL_FEATURES:
            mp.setenv("FEATURE_" + f, "1")
        mp.setenv("RATE_LIMITS", "0")
        for k, v in mode.env.items():
            mp.setenv(k, v)
        yield importlib.reload(main).app
    finally:
        mp.undo()
        importlib.reload(main)


def new_runtime() -> Runtime:
    """One fresh runtime on the golden books with the demo documents (as POST /demo/reset leaves them), installed as the process runtime."""
    from app.api import customer_overview, offer_picture, worklist

    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset_demo("golden_sme")
    set_runtime(rt)
    for clear in (worklist.clear_cache, customer_overview.clear_cache, offer_picture._cache.clear):
        clear()
    return rt


# ------------------------------------------------------------------------------------------------- requests


class _NoBody:
    pass


NO_BODY = _NoBody()


@dataclass
class Req:
    method: str
    url: str
    json: Any = NO_BODY
    params: dict[str, Any] | None = None


def template_regex(template: str) -> re.Pattern[str]:
    return re.compile("^" + re.sub(r"\\\{[^}]+\\\}", r"[^/]+", re.escape(template)) + "$")


def classify(status: int, body: Any) -> str:
    """What stopped (or did not stop) an owner request. `handler` is an answer the route's own code gave to this request: a success, or a
    refusal by the books' rules (409, 429, a coded 422, 501). `validation` is FastAPI rejecting the request before the handler (422 with a
    list of errors). `not_found` is a 404 (our id was not the one the handler wanted). `refused` is an authorization answer."""
    if status >= 500 and status != 501:
        return "error"
    if status in (401, 403, 503):
        return "refused"
    if status == 404:
        return "not_found"
    if status == 422 and isinstance(body, dict) and isinstance(body.get("detail"), list):
        return "validation"
    return "handler"


@dataclass
class World:
    client: TestClient
    mode: Mode
    rt: Runtime
    static: bool  # a refused caller's world: ids found once, not refreshed before every request
    ids: dict[str, str] = field(default_factory=dict)
    _memo: dict[Any, dict[str, str]] = field(default_factory=dict)
    blind: bool = False

    # the owner's own calls, used to prepare ids and to find the current one; never a route under test
    def call(self, method: str, url: str, expect: int = 200, **kw: Any) -> Any:
        assert self.mode.owner_headers is not None
        r = self.client.request(method, url, headers=self.mode.owner_headers, **kw)
        assert r.status_code == expect, f"world setup: {method} {url} answered {r.status_code}: {r.text[:300]}"
        return r.json()

    def offer(self, fixture: str, offered: bool = False) -> dict[str, str]:
        """The fixture's request filed and evaluated now: offer id, verdict id, the state version it was evaluated on, its decision id and,
        when it has a counter, the counter id and the message hash (`offered`: also marked as sent to the buyer)."""
        key = (fixture, offered)
        if self.blind:
            return defaultdict(lambda: "ZZ-NO-SUCH-ID")  # type: ignore[return-value]
        if self.static and key in self._memo:
            return self._memo[key]
        o = self.call("POST", "/offers", json={"fixture_id": fixture})["offer"]["offer_id"]
        r = self.client.post(f"/offers/{o}/evaluate", headers=self.mode.owner_headers, json={"fixture_id": fixture})
        if r.status_code != 200:  # e.g. OFFER_LAPSED: an earlier agreement settled the invoice; the route is then asked for a verdict that is gone
            out = {"offer_id": o, "verdict_id": "VER-NONE", "state_version": self.rt.store.get_state().state_version, "decision_id": "deal:" + o,
                   "counter_id": "CTR-NONE", "message_hash": "0" * 64}
            self._memo[key] = out
            return out
        v = r.json()
        out = {"offer_id": o, "verdict_id": v["id"], "state_version": v["state_version"], "decision_id": v["decision_id"],
               "counter_id": "CTR-NONE", "message_hash": "0" * 64}  # no counter on these books: the route then answers for a missing one
        if v["counters"]:
            c = out["counter_id"] = v["counters"][0]["id"]
            out["message_hash"] = self.call("GET", f"/offers/{o}/counters/{c}/message")["message_hash"]
            if offered:
                self.call("POST", f"/offers/{o}/counters/{c}/offered", json={
                    "verdict_id": v["id"], "state_version": v["state_version"], "message_hash": out["message_hash"], "lang": "en"})
        self._memo[key] = out
        return out

    def alert_id(self) -> str:
        return str(self.call("GET", "/alerts")["alerts"][0]["id"])


def prepare_world(client: TestClient, mode: Mode, rt: Runtime, static: bool) -> World:
    """Make every id a route needs real. Done by the owner (or, where none is configured, not at all: nothing is then reachable)."""
    w = World(client, mode, rt, static)
    if mode.owner_headers is None:  # nothing is configured, so no owner can prepare anything: every id is a placeholder (all is refused)
        w.ids = defaultdict(lambda: "ZZ-NO-SUCH-ID")  # type: ignore[assignment]
        w.blind = True
        return w
    agent = mode.agent_headers or {}
    # an approval waiting for the owner, queued by the agent as it would be
    q = client.post("/operations", headers={**mode.owner_headers, **agent}, json={
        "kind": "APPLY_FOR_FACILITY", "op_id": "route-policy-apply", "idempotency_key": "route-policy-apply", "mandate_version": 1,
        "requested_by": "AGENT", "facility_id": "FAC-GGL", "amount_fen": 20_000_000})
    assert q.status_code == 200 and q.json()["result"]["approval_id"], q.text
    w.ids["approval"] = q.json()["result"]["approval_id"]
    # an agreement on the books (Foshan's consolidated terms need the owner's review, and the accept is the owner's click)
    first = w.offer("EX05_CONSOLIDATE")
    done = w.call("POST", f"/offers/{first['offer_id']}/accept", json={"verdict_id": first["verdict_id"], "state_version": first["state_version"]})
    w.ids["commitment"] = done["decision"]["agreement"]["commitment_id"]
    w._memo.clear()
    # documents: a capex contract the owner confirmed (and priced), one waiting to be confirmed, one waiting to be rejected
    docs = [w.call("POST", "/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"})["document"] for _ in range(3)]
    w.ids.update(doc_capex=docs[0]["id"], doc_confirm=docs[1]["id"], doc_reject=docs[2]["id"],
                 hash_confirm=docs[1]["doc_hash"], hash_reject=docs[2]["doc_hash"])
    w.call("POST", f"/documents/{docs[0]['id']}/confirm", json={"doc_hash": docs[0]["doc_hash"]})
    ev = w.call("POST", f"/capex/contracts/{docs[0]['id']}/evaluate", json={"timeline": TIMELINE})
    w.ids["schedule_hash"] = ev["schedule"]["schedule"]["schedule_hash"]
    w.ids["file"] = w.call("POST", "/borrower-file", json=BORROWER)["file_id"]
    w.ids["alert"] = w.alert_id()
    w.ids["offer"] = w.offer("EX01_PACKAGE")["offer_id"]
    w.ids["decision"] = w.offer("EX01_PACKAGE")["decision_id"]
    return w


# ------------------------------------------------------------------------------------------------- the owner's request for every route

TIMELINE = {"signing_day": 20, "delivery_day": 60, "acceptance_day": 80}
BORROWER = {"facility_id": "FAC-GGL", "amount_fen": 36_000_000, "use_of_proceeds": "equipment"}
DELAY = {"field": "typical_delay_days", "value": 15, "provenance": "ESTIMATED", "source_ref": "route-policy"}
VAT = {"field": "vat_rate_bp", "value": 600, "provenance": "OWNER_ENTERED", "source_ref": "route-policy"}
CONTRACT_TEXT = ("SUPPLY AGREEMENT between Acme Parts Co. (Supplier) and Delta Retail Co. (Buyer). "
                 "The Buyer shall pay each invoice within thirty (30) days of the invoice date.")
DRAFT: dict[str, Any] = {
    "business": {"company_name": "Lingnan Homeware", "start_date": "2026-10-14", "cash": "¥400,000", "monthly_sales": "500,000",
                 "monthly_costs": "410,000"},
    "borrowing": [{"name": "Bank credit line", "kind": "CREDIT_LINE", "limit": "300,000", "drawn": "50,000", "rate_pct": "4.35",
                   "lead_time_days": 0, "agreed": True, "clean_down_days": 30}],
    "loans": [{"label": "Equipment loan", "owed": "540,000", "repayment": "45,000", "every": "MONTHLY", "next_payment_date": "2026-11-01"}],
    "customers": [{"name": "Foshan Home Retail", "contract": {"amount": "420,000", "every_days": 30, "terms_days": 45,
                                                              "next_invoice_date": "2026-10-29"},
                   "invoices": [{"sent_on": "2026-09-29", "amount": "420,000"}]}],
    "bills": [{"label": "Payroll", "kind": "PAYROLL", "amount": "340,000", "next_date": "2026-10-26", "repeats": "MONTHLY"}],
    "limits": {"min_cash": "300,000", "max_apr_pct": "15", "concession_cap": "5,000", "approval_above": "100,000", "valid_days": 90},
}


def operation(**kw: Any) -> dict[str, Any]:
    return {"kind": "DRAW_FACILITY", "op_id": "route-policy-draw", "idempotency_key": "route-policy-draw", "mandate_version": 1,
            "requested_by": "AGENT", "facility_id": "FAC-LINE", "amount_fen": 1_000_000, **kw}


Builder = Callable[[World, Caller], Req]
PLAN: dict[Key, Builder] = {}


def _plan(method: str, path: str) -> Callable[[Builder], Builder]:
    def deco(fn: Builder) -> Builder:
        PLAN[(method, path)] = fn
        return fn

    return deco


def _post(path: str, body: Any = NO_BODY, **params: Any) -> Builder:
    return lambda w, c: Req("POST", path, body, params or None)


def _post_ids(path: str, body: Callable[[World], Any] = lambda w: NO_BODY, **ids: str) -> Builder:
    """POST with the template's ids taken from the world (`ids`: parameter name -> key in `w.ids`)."""
    return lambda w, c: Req("POST", path.format(**{k: w.ids[v] for k, v in ids.items()}), body(w))


def _offer_post(template: str, fixture: str, body: Callable[[dict[str, str]], Any], offered: bool = False) -> Builder:
    def build(w: World, c: Caller) -> Req:
        o = w.offer(fixture, offered)
        return Req("POST", template.format(offer_id=o["offer_id"], counter_id=o["counter_id"]), body(o))

    return build


def _verdict(o: dict[str, str]) -> dict[str, Any]:
    return {"verdict_id": o["verdict_id"], "state_version": o["state_version"]}


# the channels
PLAN[("POST", "/offers")] = lambda w, c: Req("POST", "/offers", {"fixture_id": "EX01_PACKAGE"})
PLAN[("POST", "/nl")] = lambda w, c: Req("POST", "/nl", (
    {"actor": "OWNER", "text": "What is my cash position?", "lang": "en"} if (c.owner or c.agent) else
    {"actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": "Could you pay me earlier this month?", "lang": "en"}))
PLAN[("POST", "/operations")] = lambda w, c: Req("POST", "/operations", operation())
PLAN[("POST", "/approvals/{approval_id}")] = _post_ids("/approvals/{approval_id}", lambda w: {"decision": "APPROVE"}, approval_id="approval")
PLAN[("POST", "/circuit/{counterparty_id}/reset")] = _post("/circuit/BUYER-1/reset")
PLAN[("POST", "/clock/advance")] = _post("/clock/advance", {"days": 1})
PLAN[("POST", "/nl/reset")] = _post("/nl/reset")
PLAN[("POST", "/nl/opener")] = _post("/nl/opener", {"lang": "en"})

# the owner's reads and writes that need a real id of one kind
PLAN[("POST", "/alerts/{alert_id}/act")] = lambda w, c: Req("POST", f"/alerts/{w.alert_id() if not w.static else w.ids['alert']}/act", {})
PLAN[("POST", "/borrower-file")] = _post("/borrower-file", BORROWER)
PLAN[("POST", "/buyers/{buyer_id}/inputs")] = _post("/buyers/BUYER-1/inputs", DELAY)
PLAN[("POST", "/firm/inputs")] = _post("/firm/inputs", VAT)
PLAN[("POST", "/capex/apply")] = lambda w, c: Req("POST", "/capex/apply", {
    "facility_id": "FAC-ETL", "amount_fen": 10_000_000, "state_version": w.rt.store.get_state().state_version})
PLAN[("POST", "/capex/contracts/{document_id}/commit")] = _post_ids(
    "/capex/contracts/{document_id}/commit", lambda w: {"timeline": TIMELINE, "schedule_hash": w.ids["schedule_hash"], "take_early_pay": False},
    document_id="doc_capex")
PLAN[("POST", "/capex/contracts/{document_id}/evaluate")] = _post_ids(
    "/capex/contracts/{document_id}/evaluate", lambda w: {"timeline": TIMELINE}, document_id="doc_capex")
PLAN[("POST", "/capex/evaluate")] = _post("/capex/evaluate", {})
PLAN[("POST", "/capex/plans")] = _post("/capex/plans", {"projects": [{
    "id": "robot", "label": "Packing robot", "price_fen": 40_000_000, "monthly_uplift_fen": 1_500_000, "uplift_start_month": 4,
    "start_offsets": [0, 3]}]})
PLAN[("POST", "/commitments/{commitment_id}/revoke")] = _post_ids("/commitments/{commitment_id}/revoke", commitment_id="commitment")
PLAN[("POST", "/demo/bank-receipt")] = _post("/demo/bank-receipt")
PLAN[("POST", "/demo/reset")] = _post("/demo/reset", scenario="blank")
PLAN[("POST", "/demo/restore")] = _post("/demo/restore")
PLAN[("POST", "/documents")] = _post("/documents", {"fixture_id": "FHR_SUPPLY_AGREEMENT"})
PLAN[("POST", "/documents/{document_id}/confirm")] = _post_ids(
    "/documents/{document_id}/confirm", lambda w: {"doc_hash": w.ids["hash_confirm"]}, document_id="doc_confirm")
PLAN[("POST", "/documents/{document_id}/reject")] = _post_ids(
    "/documents/{document_id}/reject", lambda w: {"doc_hash": w.ids["hash_reject"]}, document_id="doc_reject")
PLAN[("POST", "/facilities/compile")] = _post("/facilities/compile", {"fixture_id": "EX09_TERM_SHEET_PG"})
PLAN[("POST", "/finance/health")] = _post("/finance/health", {"inputs": {"inventory_fen": 30_000_000, "trade_payables_fen": 25_000_000}})
PLAN[("POST", "/lending/eligibility")] = _post("/lending/eligibility", {"inputs": {"months_trading": 48}})
PLAN[("POST", "/lending/products/{product_id}/add-to-menu")] = _post("/lending/products/PRD-BANK1-TERM-60/add-to-menu", {"amount_fen": 60_000_000})
PLAN[("POST", "/negotiate/{offer_id}")] = _offer_post("/negotiate/{offer_id}", "EX06_THREE_INVOICES", lambda o: {"buyer_profile": "cooperative"})
PLAN[("POST", "/pilot/journal")] = _post("/pilot/journal", {
    "week": 1, "sme": "golden", "answer": "envelope", "flow_said": "x", "snapshot_hash": "a" * 64, "owner_did": "y", "choice": "followed",
    "recorded_on": "2026-10-17"})
PLAN[("POST", "/router/plan")] = _post("/router/plan")
PLAN[("POST", "/whatif")] = _post("/whatif", {"terms_days": 60, "discount_bp": 100, "rebate_bp": 0})
PLAN[("POST", "/setup/documents")] = _post("/setup/documents", {"kind": "BUYER_CONTRACT", "text": CONTRACT_TEXT, "title": "Delta supply agreement",
                                                                 "start_date": "2026-10-14"})
PLAN[("POST", "/setup/preview")] = _post("/setup/preview", {"draft": DRAFT})
PLAN[("POST", "/setup/open")] = lambda w, c: Req("POST", "/setup/open", {
    "draft": DRAFT, "password": (w.mode.owner_headers or {}).get("X-Owner-Token", "")})

# the offer chain: one fixture per route, each filed and evaluated just before the request (so its state version is current)
PLAN[("POST", "/offers/{offer_id}/evaluate")] = _offer_post("/offers/{offer_id}/evaluate", "EX01_PACKAGE", lambda o: {"fixture_id": "EX01_PACKAGE"})
PLAN[("POST", "/offers/{offer_id}/accept")] = _offer_post("/offers/{offer_id}/accept", "EX08A_JOINT_BUYER1", _verdict)
PLAN[("POST", "/offers/{offer_id}/decline")] = _offer_post("/offers/{offer_id}/decline", "EX08B_JOINT_BUYER2", _verdict)
PLAN[("POST", "/offers/{offer_id}/counters/{counter_id}/offered")] = _offer_post(
    "/offers/{offer_id}/counters/{counter_id}/offered", "EX01_PACKAGE",
    lambda o: {**_verdict(o), "message_hash": o["message_hash"], "lang": "en"})
PLAN[("POST", "/offers/{offer_id}/counters/{counter_id}/offered/withdraw")] = _offer_post(
    "/offers/{offer_id}/counters/{counter_id}/offered/withdraw", "EX01B_REWORDED",
    lambda o: {"verdict_id": o["verdict_id"], "message_hash": o["message_hash"]}, offered=True)
PLAN[("POST", "/offers/{offer_id}/counters/{counter_id}/buyer-declined")] = _offer_post(
    "/offers/{offer_id}/counters/{counter_id}/buyer-declined", "EX02_EARLY_1_5",
    lambda o: {"verdict_id": o["verdict_id"], "message_hash": o["message_hash"], "reason": "NO_REASON"}, offered=True)
PLAN[("POST", "/offers/{offer_id}/counters/{counter_id}/buyer-accepted")] = _offer_post(
    "/offers/{offer_id}/counters/{counter_id}/buyer-accepted", "EX03_AS_USUAL",
    lambda o: {**_verdict(o), "message_hash": o["message_hash"]}, offered=True)
PLAN[("POST", "/offers/{offer_id}/buyer-reply")] = _offer_post(
    "/offers/{offer_id}/buyer-reply", "EX04_CLAIMED_REBATE",
    lambda o: {"verdict_id": o["verdict_id"], "counter_id": o["counter_id"], "text": "That works for us, thank you."}, offered=True)

# the GETs: the template filled from the world (a few take a query)
GET_IDS: dict[str, Callable[[World], str]] = {
    "alert_id": lambda w: w.ids["alert"], "approval_id": lambda w: w.ids["approval"], "buyer_id": lambda w: "BUYER-1",
    "commitment_id": lambda w: w.ids["commitment"], "counterparty_id": lambda w: "BUYER-1",
    "customer_id": lambda w: "BUYER-1", "decision_id": lambda w: w.ids["decision"], "document_id": lambda w: "DOC-000001",
    "file_id": lambda w: w.ids["file"], "offer_id": lambda w: w.ids["offer"], "product_id": lambda w: "PRD-BANK1-TERM-60",
    "receivable_id": lambda w: "RCV-A"}
GET_OVERRIDES: dict[Key, Callable[[World], dict[str, str]]] = {
    ("GET", "/purchases/{document_id}"): lambda w: {"document_id": w.ids["doc_capex"]},
    ("GET", "/offers/{offer_id}/counters/{counter_id}/message"): lambda w: {
        k: w.offer("EX01_PACKAGE")[k] for k in ("offer_id", "counter_id")},
}


def build_request(w: World, caller: Caller, key: Key) -> Req:
    """The request the owner would make to `key`; the same one every other caller is refused on."""
    if key in PLAN:
        return PLAN[key](w, caller)
    method, template = key
    assert method == "GET", f"no request is written for {method} {template}"
    names = re.findall(r"\{([^}]+)\}", template)
    fill = dict(GET_OVERRIDES[key](w)) if key in GET_OVERRIDES else {}
    fill.update({n: GET_IDS[n](w) for n in names if n not in fill})
    return Req("GET", template.format(**fill))


# some owner requests change the books for the ones after them; these run last, in this order (the reset to the blank books last of the
# books-changing ones, because setup opens only blank books)
LATE: list[Key] = [
    ("POST", "/alerts/{alert_id}/act"), ("POST", "/capex/apply"), ("POST", "/clock/advance"), ("POST", "/nl/reset"),
    ("POST", "/demo/bank-receipt"), ("POST", "/demo/restore"), ("POST", "/demo/reset"),
    ("GET", "/setup/status"), ("GET", "/setup/documents"), ("POST", "/setup/documents"), ("POST", "/setup/preview"), ("POST", "/setup/open"),
]


def run_order(keys: set[Key]) -> list[Key]:
    early = sorted(k for k in keys if k not in LATE)
    return early + [k for k in LATE if k in keys]


def fix_today(mp: pytest.MonkeyPatch) -> None:
    """Setup bounds the start date against the server's today; the draft above is written for mid-October 2026 (as tests/api does)."""
    import app.setup as setup_mod

    mp.setattr(setup_mod, "today", lambda: datetime.date(2026, 10, 15))
