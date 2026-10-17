"""RT-2 (security register, from the external red-team report of 16 Oct): a malformed document is the caller's error.

Before, `POST /offers` built each document without catching its validation error: anyone, with no key, could send a document on the
`email` or `chat` channel missing `doc_id`, `sender_id` or `received_day`, get "Internal Server Error" and leave a full traceback in the log
for each request. It now answers 422 DOCUMENT_INVALID naming the fields, never the values sent; `POST /facilities/compile` too."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
CANARY = "CANARY-7f3a"
FULL = {"doc_id": "d-1", "channel": "email", "sender_id": "BUYER-1", "received_day": 0, "text": "We pay in 60 days."}


@pytest.fixture
def c():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app, raise_server_exceptions=False)
    set_runtime(None)


@pytest.mark.parametrize("channel", ["email", "chat"])
@pytest.mark.parametrize("missing", ["doc_id", "sender_id", "received_day"])
def test_a_document_missing_a_field_is_422_not_500(c: TestClient, channel: str, missing: str) -> None:
    doc = {k: v for k, v in {**FULL, "channel": channel}.items() if k != missing}
    r = c.post("/offers", json={"documents": [doc]})  # no key: anyone
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "DOCUMENT_INVALID" and any(missing in f for f in detail["fields"])


def test_the_answer_names_the_field_never_the_value(c: TestClient) -> None:
    r = c.post("/offers", json={"documents": [{**FULL, "received_day": CANARY}]})
    assert r.status_code == 422 and CANARY not in r.text


def test_the_owners_term_sheet_route_is_422_too(c: TestClient) -> None:
    r = c.post("/facilities/compile", json={"documents": [{"channel": "email", "text": "A facility."}]}, headers=OWNER)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "DOCUMENT_INVALID"
