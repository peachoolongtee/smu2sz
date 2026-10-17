"""SEC-08 (security register): the audit trail outside the operations log is guarded by the database itself.

Before: approvals and security events had no database guard, and on PostgreSQL any session could lift the log's guard with
`SET LOCAL termsledger.allow_reset = 'on'`. A rejected Tier-2 approval reset to PENDING in the database was then approved and EXECUTED,
with the hash chain still valid (reproduced on SQLite and on PostgreSQL 17). The PostgreSQL cases run only with
TERMSLEDGER_TEST_DATABASE_URL (an empty, throwaway database), like the concurrency suite."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import SqlLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
PG_ENV = "TERMSLEDGER_TEST_DATABASE_URL"


def _client(store: SqlLedgerStore) -> tuple[Runtime, TestClient]:
    rt = Runtime(settings=get_settings(), store=store, owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    c = TestClient(app)
    assert c.post("/demo/reset", params={"scenario": "busy"}, headers=OWNER).status_code == 200
    return rt, c


@pytest.fixture
def sqlite_env(tmp_path: Path):
    store = SqlLedgerStore(f"sqlite:///{tmp_path / 'audit.db'}")
    rt, c = _client(store)
    yield rt, c, tmp_path / "audit.db"
    set_runtime(None)
    store.dispose()


def _reject_one(rt: Runtime, c: TestClient) -> str:
    a = next(x for x in rt.store.approvals() if x.status.value == "PENDING")
    r = c.post(f"/approvals/{a.id}", json={"decision": "REJECT"}, headers=OWNER).json()["result"]
    assert r["status"] == "REFUSED"
    return a.id


def test_sqlite_a_rejected_approval_cannot_be_put_back_to_pending(sqlite_env):
    rt, c, db = sqlite_env
    aid = _reject_one(rt, c)
    with pytest.raises(sqlite3.IntegrityError, match="decision is recorded once"), sqlite3.connect(db) as conn:
        conn.execute("UPDATE approvals SET status='PENDING', decided_by=NULL, decided_day=NULL WHERE id=?", (aid,))
    r = c.post(f"/approvals/{aid}", json={"decision": "APPROVE"}, headers=OWNER)
    assert r.status_code == 409  # still decided: nothing executes
    assert not [o for o in rt.store.operations() if json.loads(o.result_json).get("approval_id") == aid
                and json.loads(o.result_json)["status"] == "EXECUTED"]


def test_sqlite_approvals_cannot_be_deleted_or_rewritten_and_security_events_are_append_only(sqlite_env):
    rt, c, db = sqlite_env
    c.get("/ledger")  # a refused credential: one security event
    assert rt.store.security_events()
    for stmt in ("DELETE FROM approvals", "UPDATE approvals SET op_json = '{}'", "UPDATE approvals SET reason = 'x'",
                 "DELETE FROM security_events", "UPDATE security_events SET payload_json = '{}'"):
        with pytest.raises(sqlite3.IntegrityError), sqlite3.connect(db) as conn:
            conn.execute(stmt)


def test_sqlite_deciding_a_pending_approval_and_the_demo_reset_still_work(sqlite_env):
    rt, c, _db = sqlite_env
    a = next(x for x in rt.store.approvals() if x.status.value == "PENDING")
    r = c.post(f"/approvals/{a.id}", json={"decision": "APPROVE"}, headers=OWNER).json()["result"]
    assert r["status"] in ("EXECUTED", "REFUSED")  # decided once, by the executor's gates
    assert c.post("/demo/reset", params={"scenario": "golden_sme"}, headers=OWNER).status_code == 200
    assert rt.store.verify_chain()


@pytest.mark.skipif(not os.environ.get(PG_ENV), reason=f"{PG_ENV} is not set: the PostgreSQL variant is UNVERIFIED")
def test_postgres_no_session_setting_lifts_the_guard_and_approvals_decide_once():
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import DBAPIError

    from tests.concurrency.harness import claim_postgres

    url = os.environ[PG_ENV]
    claim_postgres(url)
    store = SqlLedgerStore(url)
    rt, c = _client(store)
    try:
        aid = _reject_one(rt, c)
        c.get("/ledger")  # a refused credential: one security event, so the row trigger has a row to refuse
        assert rt.store.security_events()
        eng = create_engine(url)
        for stmts in (["SET LOCAL termsledger.allow_reset = 'on'", "DELETE FROM operations"],
                      ["UPDATE approvals SET status = 'PENDING' WHERE id = :aid"],
                      ["DELETE FROM approvals"], ["DELETE FROM security_events"], ["TRUNCATE approvals"]):
            with pytest.raises(DBAPIError), eng.begin() as conn:
                for s in stmts:
                    conn.execute(text(s), {"aid": aid})
        eng.dispose()
        assert c.post(f"/approvals/{aid}", json={"decision": "APPROVE"}, headers=OWNER).status_code == 409
        assert c.post("/demo/reset", params={"scenario": "golden_sme"}, headers=OWNER).status_code == 200  # the owner's reset works
        assert rt.store.verify_chain()
    finally:
        set_runtime(None)
        store.dispose()
