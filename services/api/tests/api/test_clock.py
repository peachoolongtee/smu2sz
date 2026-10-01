"""POST /clock/advance (ADR-0006 §2)."""

from fastapi.testclient import TestClient

from app.api.runtime import get_runtime


def test_advance_posts_scheduled_outflows_and_moves_the_executor_clock(client):
    rt = get_runtime()
    s0 = rt.store.get_state()
    outflows = sum(f.amount_fen for f in s0.flows if f.day < 40 and f.amount_fen < 0)
    assert outflows < 0
    r = client.post("/clock/advance", json={"to_day": 40})
    assert r.status_code == 200 and r.json()["day"] == 40
    s1 = rt.store.get_state()
    assert rt.day == 40 and s1.as_of_day == 40
    assert s1.cash_fen == s0.cash_fen + r.json()["posted_net_fen"] <= s0.cash_fen + outflows + sum(
        f.amount_fen for f in s0.flows if f.day < 40 and f.amount_fen > 0)
    assert [x.status for x in s1.receivables if x.id == "RCV-A"] == ["OPEN"]  # never recorded as received
    assert client.get("/clock").json() == {"day": 40}
    line = next(f for f in s1.facilities if f.kind.value == "CREDIT_LINE")
    op = {"kind": "DRAW_FACILITY", "op_id": "d1", "idempotency_key": "d1", "mandate_version": rt.store.get_mandate().version,
          "requested_by": "AGENT", "facility_id": line.id, "amount_fen": 1_000_000}
    res = client.post("/operations", json=op).json()["result"]
    assert res["status"] == "EXECUTED" and res["effective_day"] == 40


def test_clock_needs_a_credential_and_never_goes_back(client):
    from app.main import app

    assert TestClient(app).post("/clock/advance", json={"days": 1}).status_code == 403
    assert client.post("/clock/advance", json={"days": 3}).json()["day"] == 3
    assert client.post("/clock/advance", json={"to_day": 1}).status_code == 409
    assert client.post("/clock/advance", json={"to_day": 3}).json()["result"] is None  # no-op, nothing logged
    assert client.post("/clock/advance", json={}).status_code == 422


def test_reset_returns_to_day_zero(client):
    client.post("/clock/advance", json={"days": 10})
    client.post("/demo/reset")
    rt = get_runtime()
    assert rt.day == 0 and rt.store.get_state().as_of_day == 0
