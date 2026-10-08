"""Wave 8 pass A (wayfinder #47, ticket #57): the owner's words on the day-34 books. A clock move, an agreement, the comparison
roles and the approval result sentence are presentation reads over what the engine already decided; no figure is priced here."""

from __future__ import annotations

from tests.alerts.test_repay_alert import OWNER, to_day34
from tests.api.test_ledger_events import ENGINE_WORDS
from tests.nl import conftest as nl_conftest

rt = nl_conftest.rt  # the in-memory runtime and the app client of the chat tests
client = nl_conftest.client


def test_no_business_event_on_the_day34_books_speaks_the_engine(client, rt):
    to_day34(client, rt)
    rows = client.get("/ledger", headers=OWNER).json()["operations"]
    clocks = [r for r in rows if r["kind"] == "ADVANCE_CLOCK"]
    assert clocks and all(r["event_text"] for r in rows)
    assert any(r["event_text"].startswith("4 days passed: the ¥45,000.00 debt payment went out and one invoice was issued") for r in clocks)
    for r in rows:
        assert not any(w in r["event_text"] for w in ENGINE_WORDS), r["event_text"]
        assert not any(w in (r["event_detail"] or "") for w in ENGINE_WORDS), r["event_detail"]
    for lang in ("en", "zh"):
        for c in client.get("/home", params={"lang": lang}, headers=OWNER).json()["changes"]:
            assert not any(w in c["event_text"] for w in ENGINE_WORDS), c["event_text"]
