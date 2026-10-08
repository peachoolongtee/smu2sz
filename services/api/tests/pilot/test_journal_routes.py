"""POST /pilot/journal and GET /pilot/journal: the flag, the owner, the round trip, validation, and that a write touches nothing
of the engine (docs/pilot/JOURNAL_SPEC.md sections 4 and 6)."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.api.display import displayed
from app.api.runtime import Runtime
from app.config import get_settings
from app.persistence import InMemoryLedgerStore

from .conftest import entry

pytestmark = pytest.mark.usefixtures("flag_on")


def test_the_flag_defaults_off(flag_off: None) -> None:
    assert get_settings().features.pilot_journal is False


def test_both_routes_are_403_with_the_flag_off(flag_off: None, client: TestClient) -> None:
    for resp in (client.post("/pilot/journal", json=entry()), client.get("/pilot/journal")):
        assert resp.status_code == 403
        assert resp.json()["detail"] == {
            "code": "FEATURE_DISABLED", "feature": "pilot_journal",
            "message": "The pilot journal is switched off (FEATURE_PILOT_JOURNAL).",
        }


def test_a_body_that_does_not_validate_is_still_403_with_the_flag_off(flag_off: None, client: TestClient) -> None:
    assert client.post("/pilot/journal", json={"week": "x"}).status_code == 403


def test_nothing_is_written_with_the_flag_off(flag_off: None, client: TestClient, runtime: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    client.post("/pilot/journal", json=entry())
    monkeypatch.setenv("FEATURE_PILOT_JOURNAL", "1")
    assert client.get("/pilot/journal").json() == {"entries": [], "count": 0}


def test_the_owner_token_is_required(runtime: Runtime) -> None:
    from app.main import app

    anonymous = TestClient(app)
    assert anonymous.post("/pilot/journal", json=entry()).status_code == 401
    assert anonymous.get("/pilot/journal").status_code == 401
    agent = TestClient(app, headers={"X-Agent-Key": "demo-agent-key"})
    assert agent.post("/pilot/journal", json=entry()).status_code == 401


def test_an_entry_round_trips_with_the_server_fields_stamped(client: TestClient, runtime: Runtime) -> None:
    sent = entry()
    posted = client.post("/pilot/journal", json=sent)
    assert posted.status_code == 201
    stored = posted.json()["entry"]
    state = runtime.store.get_state()
    assert {k: stored[k] for k in sent} == sent
    assert stored["id"] == "PJ-000001" and stored["seq"] == 1
    assert stored["state_version"] == state.state_version and stored["day"] == runtime.day
    assert stored["recorded_at"].endswith("+00:00")
    assert client.get("/pilot/journal").json() == {"entries": [stored], "count": 1}


def test_entries_come_newest_first_and_filter_by_week_and_sme(client: TestClient) -> None:
    for week, sme in ((1, "sme-a"), (2, "sme-a"), (2, "sme-b")):
        assert client.post("/pilot/journal", json=entry(week=week, sme=sme)).status_code == 201
    assert [e["seq"] for e in client.get("/pilot/journal").json()["entries"]] == [3, 2, 1]
    assert [e["seq"] for e in client.get("/pilot/journal", params={"week": 2}).json()["entries"]] == [3, 2]
    assert [e["seq"] for e in client.get("/pilot/journal", params={"sme": "sme-a"}).json()["entries"]] == [2, 1]
    assert client.get("/pilot/journal", params={"week": 9}).json()["count"] == 0


def test_an_entry_is_never_edited_or_deleted_through_the_api(client: TestClient) -> None:
    client.post("/pilot/journal", json=entry())
    for method in ("put", "patch", "delete"):
        assert getattr(client, method)("/pilot/journal").status_code == 405
        assert getattr(client, method)("/pilot/journal/PJ-000001").status_code in (404, 405)
    assert client.get("/pilot/journal").json()["count"] == 1


@pytest.mark.parametrize("changes", [
    {"week": 0}, {"week": 61}, {"week": "3"}, {"week": True},
    {"sme": ""}, {"sme": "x" * 65}, {"sme": "-leading"}, {"sme": "Foshan/Home"},
    {"answer": "portfolio"}, {"choice": "obeyed"},
    {"flow_said": ""}, {"flow_said": "x" * 2001}, {"owner_did": ""}, {"owner_did": "x" * 2001},
    {"snapshot_hash": "A" * 64}, {"snapshot_hash": "a" * 63}, {"snapshot_hash": "g" * 64},
    {"recorded_on": "19 October 2026"}, {"recorded_on": "2026-13-01"}, {"recorded_on": "2026-1-5"}, {"recorded_on": "20261019"},
])
def test_a_field_out_of_its_limits_is_a_422_and_writes_nothing(client: TestClient, changes: dict[str, Any]) -> None:
    assert client.post("/pilot/journal", json=entry(**changes)).status_code == 422
    assert client.get("/pilot/journal").json()["count"] == 0


def test_missing_and_unknown_fields_are_refused(client: TestClient) -> None:
    body = entry()
    del body["owner_did"]
    assert client.post("/pilot/journal", json=body).status_code == 422
    assert client.post("/pilot/journal", json=entry(state_version=99)).status_code == 422
    assert client.post("/pilot/journal", json=entry(seq=5)).status_code == 422


@pytest.mark.parametrize("text", [
    "paid into 6222020012345678 on Monday", "account 6222 0200 1234 5678", "acct 6222-0200-1234-5678", "x" + "9" * 12,
])
def test_text_that_looks_like_an_account_number_is_refused(client: TestClient, text: str) -> None:
    for field in ("flow_said", "owner_did"):
        resp = client.post("/pilot/journal", json=entry(**{field: text}))
        assert resp.status_code == 422
        assert "account" in json.dumps(resp.json()).lower()
    assert client.get("/pilot/journal").json()["count"] == 0


def test_amounts_dates_and_ordinary_numbers_are_not_mistaken_for_an_account(client: TestClient) -> None:
    text = "Saves ¥1,374.61 of ¥162,800.00 due 2026-10-19 (day 34); 0.89% on ¥10,000, 1234567890 yuan"
    assert client.post("/pilot/journal", json=entry(flow_said=text, owner_did=text)).status_code == 201


def test_a_write_changes_nothing_of_the_engine(client: TestClient, runtime: Runtime) -> None:
    store = cast(InMemoryLedgerStore, runtime.store)
    before = (
        store.get_state(), store.get_mandate(), len(store.state_history()), len(store.mandate_history()),
        [e.entry_hash for e in store.operations()], len(store.operations()), store.verify_chain(),
        store.commitments(), store.approvals(), store.security_events(), store.verdicts(), runtime.day,
    )
    for week in (1, 2, 3):
        assert client.post("/pilot/journal", json=entry(week=week)).status_code == 201
        assert client.get("/pilot/journal").status_code == 200
    after = (
        store.get_state(), store.get_mandate(), len(store.state_history()), len(store.mandate_history()),
        [e.entry_hash for e in store.operations()], len(store.operations()), store.verify_chain(),
        store.commitments(), store.approvals(), store.security_events(), store.verdicts(), runtime.day,
    )
    assert after == before
    assert client.get("/state").json()["state"]["state_version"] == before[0].state_version
    assert client.get("/ledger").json()["chain_length"] == before[5] == 0


def test_the_engines_state_version_is_the_one_stamped_after_the_books_move(client: TestClient, runtime: Runtime) -> None:
    first = client.post("/pilot/journal", json=entry()).json()["entry"]
    client.post("/clock/advance", json={"to_day": 5})
    second = client.post("/pilot/journal", json=entry(week=4)).json()["entry"]
    assert first["day"] == 0 and second["day"] == 5 == runtime.day
    assert second["state_version"] == runtime.store.get_state().state_version


def test_the_listing_has_no_money_field_and_displayed_adds_nothing(client: TestClient) -> None:
    client.post("/pilot/journal", json=entry(flow_said="Saves ¥1,374.61 on ¥162,800.00"))
    body = client.get("/pilot/journal").json()
    keys: set[str] = set()

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            keys.update(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(body)
    assert not [k for k in keys if k.endswith(("_fen", "_bp", "_display"))]
    assert displayed(body) == body


def test_the_journal_survives_the_demo_reset_of_the_ledger(client: TestClient) -> None:
    client.post("/pilot/journal", json=entry())
    assert client.post("/demo/reset").status_code == 200
    assert client.get("/pilot/journal").json()["count"] == 1


def test_health_lists_the_flag(client: TestClient) -> None:
    assert client.get("/health").json()["features"]["pilot_journal"] is True
