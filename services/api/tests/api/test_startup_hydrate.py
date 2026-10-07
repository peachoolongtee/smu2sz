"""Audit A04: process start hydrates from the store and never deletes. Temp SQLite files only; the engine is
disposed before the file is released (Windows keeps it locked otherwise)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.api.runtime as rtmod
from app.api.runtime import ResetRefused, StartupError, get_runtime, set_runtime
from app.mandate.fixture import demo_owner_public_key_hex

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Owner-Token": "", "X-Agent-Key": "demo-agent-key"}


def _op(kind, key, **kw):
    return {"kind": kind, "op_id": key, "idempotency_key": key, "mandate_version": 1, "requested_by": "AGENT", **kw}


DRAW = _op("DRAW_FACILITY", "A04-DRAW", facility_id="FAC-LINE", amount_fen=10_000_000)  # 100,000 yuan


def _snapshot(rt):
    st = rt.store.get_state()
    ops = rt.store.operations()
    return {
        "cash": st.cash_fen, "drawn": [f.drawn_fen for f in st.facilities], "state_version": st.state_version,
        "day": rt.day, "ops": len(ops), "pending": [a.id for a in rt.store.approvals("PENDING")],
        "chain": rt.store.verify_chain(), "head": ops[-1].entry_hash if ops else None,
    }


def _restart():
    """Simulated process restart: dispose the engine, drop the runtime."""
    if rtmod._runtime is not None:
        rtmod._runtime.store.dispose()
    set_runtime(None)


@pytest.fixture
def sqlite_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ledger.db'}")
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("OWNER_PUBLIC_KEY_HEX", raising=False)
    set_runtime(None)
    yield monkeypatch
    _restart()


def _populate():
    from app.main import app

    c = TestClient(app)
    assert c.post("/operations", json=DRAW, headers=AGENT).json()["result"]["status"] == "EXECUTED"
    pend = c.post("/operations", json=_op("APPLY_FOR_FACILITY", "A04-APPLY", facility_id="FAC-GGL", amount_fen=20_000_000),
                  headers=AGENT).json()["result"]
    assert pend["status"] == "PENDING_APPROVAL"
    assert c.post("/clock/advance", json={"to_day": 3}, headers=OWNER).status_code == 200


def test_restart_hydrates_in_demo_mode(sqlite_env):
    from app.main import app

    get_runtime()
    _populate()
    before = _snapshot(get_runtime())
    assert before["day"] == 3 and before["ops"] >= 2 and len(before["pending"]) == 1
    _restart()
    rt = get_runtime()
    assert _snapshot(rt) == before
    assert TestClient(app).post("/operations", json=DRAW, headers=AGENT).json()["result"]["status"] == "DUPLICATE"
    _same_books_one_more_log_row(rt, before)


def test_restart_hydrates_with_demo_mode_off(sqlite_env):
    from app.main import app

    get_runtime()
    _populate()
    before = _snapshot(get_runtime())
    _restart()
    sqlite_env.setenv("DEMO_MODE", "0")
    sqlite_env.setenv("OWNER_PUBLIC_KEY_HEX", demo_owner_public_key_hex())
    sqlite_env.setenv("AGENT_KEY", "prod-agent-key")
    rt = get_runtime()
    assert rt.owner_key_hex == demo_owner_public_key_hex()
    assert _snapshot(rt) == before
    r = TestClient(app).post("/operations", json=DRAW, headers={"X-Agent-Key": "prod-agent-key"}).json()["result"]
    assert r["status"] == "DUPLICATE"
    _same_books_one_more_log_row(rt, before)


def test_demo_reset_refused_when_demo_mode_off_on_sql(sqlite_env):
    from app.main import app

    get_runtime()
    _populate()
    before = _snapshot(get_runtime())
    _restart()
    sqlite_env.setenv("DEMO_MODE", "0")
    sqlite_env.setenv("OWNER_TOKEN", "prod-owner-token")
    sqlite_env.setenv("OWNER_PUBLIC_KEY_HEX", demo_owner_public_key_hex())
    r = TestClient(app).post("/demo/reset", headers={"X-Owner-Token": "prod-owner-token"})
    assert r.status_code == 403
    assert _snapshot(get_runtime()) == before
    with pytest.raises(ResetRefused):
        get_runtime().reset()
    assert _snapshot(get_runtime()) == before


def test_demo_reset_still_works_in_demo_mode_on_sql(sqlite_env):
    from app.main import app

    get_runtime()
    _populate()
    assert TestClient(app).post("/demo/reset", headers=OWNER).status_code == 200
    rt = get_runtime()
    # The demo reset opens on the three demo documents confirmed by the owner (test_demo_documents.py) and nothing else.
    assert rt.day == 0 and [o.kind for o in rt.store.operations()] == ["CONFIRM_DOCUMENT"] * 3 and rt.store.verify_chain()


def test_non_demo_requires_owner_public_key(sqlite_env):
    sqlite_env.setenv("DEMO_MODE", "0")
    with pytest.raises(StartupError, match="OWNER_PUBLIC_KEY_HEX"):
        get_runtime()
    sqlite_env.setenv("OWNER_PUBLIC_KEY_HEX", "not-hex")
    with pytest.raises(StartupError, match="64 hex"):
        get_runtime()


def test_non_demo_empty_store_fails_with_provisioning_message(sqlite_env, tmp_path):
    from app.persistence import SqlLedgerStore
    from app.persistence.errors import NotFound

    sqlite_env.setenv("DEMO_MODE", "0")
    sqlite_env.setenv("OWNER_PUBLIC_KEY_HEX", demo_owner_public_key_hex())
    with pytest.raises(StartupError, match="provision"):
        get_runtime()
    assert rtmod._runtime is None
    store = SqlLedgerStore(f"sqlite:///{tmp_path / 'ledger.db'}")  # nothing was seeded behind the error
    try:
        with pytest.raises(NotFound):
            store.get_state()
    finally:
        store.dispose()


def test_in_memory_store_is_seeded_and_resettable_without_demo_mode(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "memory")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("OWNER_PUBLIC_KEY_HEX", demo_owner_public_key_hex())
    set_runtime(None)
    try:
        rt = get_runtime()
        assert rt.store.get_state().as_of_day == 0
        rt.reset()  # in-memory: allowed
    finally:
        set_runtime(None)


def _same_books_one_more_log_row(rt, before):
    """A DUPLICATE replay changes no books; it only appends its own (chained) log entry."""
    after = _snapshot(rt)
    assert after["chain"] and after["ops"] == before["ops"] + 1
    for k in ("cash", "drawn", "state_version", "day", "pending"):
        assert after[k] == before[k], k
