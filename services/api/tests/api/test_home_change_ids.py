"""Map #65 debt (tickets #85 and #87): the home's change rows carry the ids of what they are about, and a LATE row that repeats a
part-paid invoice names the row that tells it better (`superseded_by`), so the web drops it with no logic of its own. One request
reconciles once and runs the alerts once."""

from __future__ import annotations

import pytest

from app.api.runtime import get_runtime
from tests.api.test_time_semantics import _act, _walk

IDS = ("id", "receivable_id", "commitment_id", "decision_id", "superseded_by")


def _changes(client, lang: str = "en") -> list[dict]:
    return client.get("/home", params={"lang": lang}).json()["changes"]


def _late(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["kind"] == "LATE"]


def test_every_change_row_has_an_id_and_the_id_fields(client):
    _walk(client, receipt="half")
    rows = _changes(client)
    assert rows and all(set(IDS) <= set(r) for r in rows)
    assert len({r["id"] for r in rows}) == len(rows)  # an id names one row
    assert all(isinstance(r["id"], str) and r["id"] for r in rows)


def test_the_part_paid_invoices_plain_late_row_names_the_row_that_tells_it_better(client):
    _walk(client, receipt="half")
    rows = _late(_changes(client))
    four = next(r for r in rows if r.get("window_state"))
    plain = next(r for r in rows if not r.get("window_state"))
    rid = get_runtime().store.get_state().receivables[0].id
    assert four["receivable_id"] == plain["receivable_id"] == rid
    assert four["commitment_id"] and four["commitment_id"].startswith("CMT-")
    assert four["decision_id"] == "deal:" + get_runtime().store.commitments()[0].offer_id
    assert four["superseded_by"] is None  # the row that tells it is never itself dropped
    assert plain["superseded_by"] == four["id"]
    assert [r["id"] for r in rows if r["superseded_by"] is not None] == [plain["id"]]


def test_the_chinese_home_marks_the_same_row_as_the_english_one(client):
    _walk(client, receipt="half")
    en, zh = _changes(client, "en"), _changes(client, "zh")
    keys = [(r["id"], r["receivable_id"], r["commitment_id"], r["decision_id"], r["superseded_by"]) for r in en]
    assert keys == [(r["id"], r["receivable_id"], r["commitment_id"], r["decision_id"], r["superseded_by"]) for r in zh]
    assert any(r["superseded_by"] for r in zh) and any(r.get("window_state") == "ended" for r in zh)  # the part-paid row is told in Chinese too
    assert not any("没有到账" in r["text"] for r in zh if r["kind"] == "LATE" and r.get("window_state"))


def test_without_a_receipt_no_late_row_is_superseded(client):
    _walk(client)  # nothing arrived: "did not arrive" stands beside the invoice's own past-due row
    rows = _late(_changes(client))
    assert len(rows) == 2 and all(r["superseded_by"] is None for r in rows)
    assert {r["receivable_id"] for r in rows} == {get_runtime().store.get_state().receivables[0].id}
    assert any("did not arrive" in r["text"] for r in rows)


def test_a_superseded_row_always_points_at_a_row_that_is_on_the_list(client):
    _walk(client, receipt="half")
    _act(client)
    rows = _changes(client)
    ids = {r["id"] for r in rows}
    assert all(r["superseded_by"] in ids for r in rows if r["superseded_by"] is not None)


def test_operation_rows_carry_their_decision_and_invoice(client):
    _walk(client, receipt="half")
    rows = client.get("/home", params={"since_day": 0}).json()["changes"]
    receipt = next(r for r in rows if r["kind"] == "RECEIPT")
    assert receipt["receivable_id"] == get_runtime().store.get_state().receivables[0].id
    assert receipt["id"] == f"op:{receipt['seq']}" and receipt["superseded_by"] is None
    agreement = next(r for r in rows if r["kind"] == "AGREEMENT")
    assert agreement["commitment_id"] == get_runtime().store.commitments()[0].id
    assert agreement["decision_id"] == "deal:" + get_runtime().store.commitments()[0].offer_id


# ---------------------------------------------------------------- one reconcile and one alerts per request (ticket #87)


@pytest.fixture
def counted(monkeypatch):
    """Count every call to `reconcile` and `alerts` made by the API layer, wherever it was imported."""
    from app.api import decisions, home, operations, read

    counts = {"reconcile": 0, "alerts": 0}

    def wrap(module, name):
        real = getattr(module, name)

        def inner(*a, **k):
            counts[name] += 1
            return real(*a, **k)

        monkeypatch.setattr(module, name, inner)

    for module in (decisions, home, read):
        wrap(module, "reconcile")
    for module in (decisions, home, operations):
        wrap(module, "alerts")
    return counts


@pytest.mark.parametrize("receipt", [None, "half"])
@pytest.mark.parametrize("path", ["/home", "/decisions", "/approvals/queue", "/ledger"])
def test_a_read_reconciles_at_most_once_and_runs_the_alerts_at_most_once(client, counted, path, receipt):
    _walk(client, receipt=receipt)
    _act(client)  # a queued cure: the queue prices it from the alerts and the ledger has a receipt to read
    for key in counted:
        counted[key] = 0
    assert client.get(path).status_code == 200
    assert counted["reconcile"] <= 1 and counted["alerts"] <= 1, (path, counted)


def test_the_ledger_with_a_receipt_reconciles_once(client, counted):
    _walk(client, receipt="half")
    counted["reconcile"] = 0
    assert any(o["kind"] == "RECEIVE_PAYMENT" for o in client.get("/ledger").json()["operations"])
    assert counted["reconcile"] == 1
