"""POST /borrower-file queues a Tier-2 GenerateBorrowerFile; downloads render; the flag switches it off."""

from __future__ import annotations

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.borrower_file import router as borrower_file_router
from app.api.operations import router as operations_router
from app.api.runtime import Runtime, set_runtime
from app.config import Features, Settings, get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

BODY = {"facility_id": "FAC-GGL", "amount_fen": 36_000_000, "use_of_proceeds": "Working capital for payroll"}


def _client(settings: Settings) -> TestClient:
    rt = Runtime(settings=settings, store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    app = FastAPI()
    app.include_router(borrower_file_router)
    app.include_router(operations_router)
    return TestClient(app)


@pytest.fixture
def client():
    yield _client(get_settings())
    set_runtime(None)


def test_post_queues_owner_approval_and_returns_the_displayed_file(client):
    draw = {"kind": "DRAW_FACILITY", "op_id": "OP-D1", "idempotency_key": "d1", "mandate_version": 1,
            "requested_by": "AGENT", "facility_id": "FAC-LINE", "amount_fen": 15_000_000}
    drawn = client.post("/operations", json=draw).json()["result"]
    r = client.post("/borrower-file", json=BODY)
    assert r.status_code == 200
    v = r.json()
    assert v["status"] == "PREPARED_NOT_SENT" and v["lender_mocked"] is True
    assert v["operation"]["status"] == "PENDING_APPROVAL" and v["operation"]["tier"] == "TIER_2"
    assert v["approval_id"] and v["approval_status"] == "PENDING"
    assert v["generated_day"] == 0 and v["amount_display"] == "¥360,000.00"
    for s in v["sections"]:
        assert s["title"] and s["rows"]
        for row in s["rows"]:
            assert {"label", "value", "evidence"} <= set(row)
            assert row["evidence"] in ("OBSERVED", "PROJECTED", "OWNER_ESTIMATE")
    ledger = next(s for s in v["sections"] if s["key"] == "commitments")
    assert any(drawn["entry_hash"] in row["value"] for row in ledger["rows"])
    queue = client.get("/approvals/queue").json()["approvals"]
    assert [a["id"] for a in queue] == [v["approval_id"]]
    assert queue[0]["operation"]["kind"] == "GENERATE_BORROWER_FILE"
    # the same request on the same state is idempotent: same file, same approval
    again = client.post("/borrower-file", json=BODY).json()
    assert again["file_id"] == v["file_id"] and again["approval_id"] == v["approval_id"]
    assert again["operation"]["status"] == "DUPLICATE"


def test_downloads(client):
    from docx import Document

    v = client.post("/borrower-file", json=BODY).json()
    html = client.get(v["downloads"]["html"])
    assert html.status_code == 200 and html.headers["content-type"].startswith("text/html")
    assert "借款资料" in html.text and v["file_id"] in html.text
    docx = client.get(v["downloads"]["docx"])
    assert docx.status_code == 200 and "attachment" in docx.headers["content-disposition"]
    Document(io.BytesIO(docx.content))  # opens
    if v["downloads"]["pdf"] is None:
        assert v["pdf_note"] and client.get(f"/borrower-file/{v['file_id']}.pdf").status_code == 501
    assert client.get(f"/borrower-file/{v['file_id']}").json()["file_id"] == v["file_id"]
    assert client.get("/borrower-file/BF-NOPE.html").status_code == 404


def test_bad_request_is_422(client):
    assert client.post("/borrower-file", json={**BODY, "facility_id": "FAC-IF"}).status_code == 422
    assert client.post("/borrower-file", json={**BODY, "extra": 1}).status_code == 422


def test_flag_off_returns_feature_disabled():
    c = _client(Settings(features=Features(borrower_file=False)))
    try:
        r = c.post("/borrower-file", json=BODY)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "FEATURE_DISABLED"
        assert c.get("/borrower-file/BF-X.html").json()["detail"]["code"] == "FEATURE_DISABLED"
        assert c.get("/approvals/queue").json()["approvals"] == []  # nothing queued
    finally:
        set_runtime(None)
