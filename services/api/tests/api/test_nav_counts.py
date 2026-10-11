"""GET /nav/counts: what in each Business section needs the owner now (numbers only, cheap)."""

from __future__ import annotations

from tests.api.test_time_semantics import _walk


def _counts(client, lang="en"):
    r = client.get("/nav/counts", params={"lang": lang})
    assert r.status_code == 200, r.text
    body = r.json()
    return body["deals"], body["approvals"], body["receivables"]


def test_a_quiet_day_has_nothing_that_needs_the_owner(client):
    client.post("/demo/reset", json={})
    assert _counts(client) == (0, 0, 0)


def test_an_open_offer_makes_one_deal_need_the_owner(client):
    client.post("/demo/reset", json={})
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    assert _counts(client) == (1, 0, 0)  # received
    client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    assert _counts(client) == (1, 0, 0)  # evaluated, waiting for the owner's reply
    client.post(f"/negotiate/{offer['offer_id']}", json={"buyer_profile": "cooperative"})
    assert _counts(client) == (0, 0, 0)  # answered


def test_the_late_invoice_and_the_queued_cure_on_day_34(client):
    _walk(client, receipt="half")
    action = client.get("/home").json()["next_action"]
    deals, _approvals, receivables = _counts(client)
    assert (deals, receivables) == (1, 1)
    if action is not None:
        client.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]})
    pending = [a for a in client.get("/approvals/queue").json()["approvals"] if a.get("status") == "PENDING"]
    assert len(pending) == 1 and _counts(client) == (1, 1, 1)
    assert _counts(client, "zh") == _counts(client)


def test_the_counts_need_the_owner(client):
    r = client.get("/nav/counts", headers={"X-Owner-Token": "wrong"})
    assert r.status_code in (401, 403)
