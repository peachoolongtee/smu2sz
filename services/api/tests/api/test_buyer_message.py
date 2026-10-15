"""The owner sends a verified counter to the buyer themself (negotiation communication, phases 0 to 2).

FLOW prepares the message, the owner copies it and marks it sent, and the deal waits for the buyer. Marking it sent agrees nothing and moves
nothing; the buyer's yes is the owner's to record and becomes the offered counter's agreement through the executor; a reply with terms of its
own is a new request. A request filed without a known sender gets no message (SEC-19).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.decide import simulated_profile
from app.api.runtime import Runtime, get_runtime
from app.domain.fixtures import offer_documents

EX01, EX02 = "EX01_PACKAGE", "EX02_EARLY_1_5"


@pytest.fixture
def api(client: TestClient) -> TestClient:
    return client


@pytest.fixture
def rt(client: TestClient) -> Runtime:
    return get_runtime()


def _evaluate(api: TestClient, fixture: str) -> tuple[str, dict[str, Any]]:
    oid = api.post("/offers", json={"fixture_id": fixture}).json()["offer"]["offer_id"]
    return oid, api.post(f"/offers/{oid}/evaluate", json={"fixture_id": fixture}).json()


def _message(api: TestClient, oid: str, cid: str, lang: str = "en") -> dict[str, Any]:
    r = api.get(f"/offers/{oid}/counters/{cid}/message", params={"lang": lang})
    assert r.status_code == 200, r.text
    return r.json()


def _offered(api: TestClient, oid: str, v: dict[str, Any], m: dict[str, Any], lang: str = "en"):
    return api.post(f"/offers/{oid}/counters/{m['counter_id']}/offered",
                    json={"verdict_id": v["id"], "state_version": v["state_version"], "message_hash": m["message_hash"], "lang": lang})


def _sent(api: TestClient, fixture: str = EX02, counter: int = 0) -> tuple[str, dict[str, Any], dict[str, Any]]:
    oid, v = _evaluate(api, fixture)
    m = _message(api, oid, v["counters"][counter]["id"])
    assert _offered(api, oid, v, m).status_code == 200
    return oid, v, m


def _accepted(api: TestClient, oid: str, v: dict[str, Any], m: dict[str, Any], rt: Runtime):
    return api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-accepted",
                    json={"verdict_id": v["id"], "state_version": rt.store.get_state().state_version, "message_hash": m["message_hash"]})


def _decision(api: TestClient, oid: str, lang: str = "en") -> dict[str, Any]:
    return api.get(f"/decisions/deal:{oid}", params={"lang": lang}).json()


# ================================================================ phase 0: the simulated buyer is the offer's own


def test_a_simulated_send_negotiates_with_the_offers_own_buyer_or_not_at_all() -> None:
    assert simulated_profile("BUYER-1", "cooperative") == "BUYER-1"
    assert simulated_profile("BUYER-1", "hard_line") == "BUYER-1-HARDLINE"
    assert simulated_profile("BUYER-2", "cooperative") == "BUYER-2"
    assert simulated_profile("BUYER-2", "hard_line") is None  # never BUYER-1's reservation for another buyer
    assert simulated_profile("BUYER-3", "cooperative") is None


# ================================================================ the message


def test_the_message_names_the_invoice_and_real_dates_in_either_language(api: TestClient) -> None:
    oid, v = _evaluate(api, EX02)
    cid = v["counters"][0]["id"]
    en, zh = _message(api, oid, cid), _message(api, oid, cid, "zh")
    assert en["copyable"] and en["blocked"] is None and en["provenance"]["via"] == "owner"
    text = en["text"]
    assert text.startswith("Dear Foshan Home Retail Co.,")
    for said in ("¥420,000 invoice issued on 18 September 2026", "up to ¥257,200", "on or before 3 October 2026", "0.85% discount",
                 "Everything else stays as it is", "open until 3 October 2026"):
        assert said in text
    assert "day 2" not in text and "this invoice" not in text  # the engine's own record of the terms is not the message
    assert "2026年9月18日开具的 ¥420,000 发票" in zh["text"] and "2026年10月3日" in zh["text"] and "0.85%" in zh["text"]
    assert en["terms_hash"] == zh["terms_hash"] and en["message_hash"] != zh["message_hash"]
    assert en["valid_until_date"] == "3 October 2026" and en["offered"] is None


def test_a_counter_of_two_terms_says_both_and_nothing_else(api: TestClient) -> None:
    oid, v = _evaluate(api, EX01)
    b = next(c for c in v["counters"] if c["label"] == "Option B")
    text = _message(api, oid, b["id"])["text"]
    assert "1. Payment terms on future invoices move from 45 to 55 days." in text
    assert "2. Prices on future invoices rise by 0.30%." in text
    assert "rebate" not in text.lower()


def test_an_anonymous_request_under_a_buyers_name_gets_no_message(api: TestClient) -> None:
    docs = [d.model_dump(mode="json") for d in offer_documents(EX02)]
    anon = TestClient(api.app)  # no owner token, no key
    oid = anon.post("/offers", json={"counterparty_id": "BUYER-1", "documents": docs}).json()["offer"]["offer_id"]
    v = api.post(f"/offers/{oid}/evaluate").json()
    m = _message(api, oid, v["counters"][0]["id"])
    assert m["text"] is None and m["message_hash"] is None and not m["copyable"]
    assert m["blocked"]["code"] == "UNVERIFIED_SENDER" and m["provenance"]["via"] == "anonymous"
    r = api.post(f"/offers/{oid}/counters/{m['counter_id']}/offered",
                 json={"verdict_id": v["id"], "state_version": v["state_version"], "message_hash": "x" * 64})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "UNVERIFIED_SENDER"


# ================================================================ "I've sent it"


def test_marking_it_sent_agrees_nothing_and_moves_nothing(api: TestClient, rt: Runtime) -> None:
    oid, v = _evaluate(api, EX02)
    m = _message(api, oid, v["counters"][0]["id"])
    ops, commitments, version = len(rt.store.operations()), len(rt.store.commitments()), rt.store.get_state().state_version
    r = _offered(api, oid, v, m)
    assert r.status_code == 200, r.text
    assert r.json()["offered"]["same_message"] and not r.json()["already_recorded"]
    assert "closes in 2 days" in r.json()["message_when"]
    assert (len(rt.store.operations()), len(rt.store.commitments()), rt.store.get_state().state_version) == (ops, commitments, version)
    d = _decision(api, oid)
    assert d["state"] == "AWAITING_BUYER" and d["state_text"] == "Offer sent; waiting for the buyer's answer"
    assert d["waiting_for"]["code"] == "BUYER_ANSWER" and "closes in 2 days" in d["waiting_for"]["text"]
    assert _decision(api, oid, "zh")["state_text"] == "报价已发出，等待买方答复"
    again = _offered(api, oid, v, m)  # a second mark changes nothing
    assert again.status_code == 200 and len(rt.store.operations()) == ops


def test_the_deals_queue_shows_the_offer_as_waiting_for_the_buyer(api: TestClient) -> None:
    oid, _v, _m = _sent(api)
    rows = [r for r in api.get("/worklist").json()["waiting"] if r.get("kind") == "BUYER_REPLY"]
    assert any(oid in r["key"] and r["lifecycle"] == "awaiting_buyer" and r["status_text"] == "Awaiting buyer"
               and r["consequence_text"] == "You sent an offer; it closes in 2 days." for r in rows), rows


def test_a_mark_that_is_not_what_the_owner_was_shown_is_refused(api: TestClient, rt: Runtime) -> None:
    oid, v = _evaluate(api, EX02)
    m = _message(api, oid, v["counters"][0]["id"])
    stale = api.post(f"/offers/{oid}/counters/{m['counter_id']}/offered",
                     json={"verdict_id": v["id"], "state_version": v["state_version"], "message_hash": "0" * 64})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "MESSAGE_CHANGED"
    old_books = api.post(f"/offers/{oid}/counters/{m['counter_id']}/offered",
                         json={"verdict_id": v["id"], "state_version": v["state_version"] - 1, "message_hash": m["message_hash"]})
    assert old_books.status_code == 409 and old_books.json()["detail"]["reason"] == "BOOKS_CHANGED"
    assert _decision(api, oid)["state"] == "RESPONSE_READY"


# ================================================================ the buyer's answer


def test_the_buyers_yes_makes_the_offered_counters_agreement_under_the_owner(api: TestClient, rt: Runtime) -> None:
    oid, v, m = _sent(api)
    r = _accepted(api, oid, v, m, rt)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "agreed"
    [c] = [c for c in rt.store.commitments() if c.offer_id == oid]
    assert c.terms_hash == m["terms_hash"] and c.verdict_id == v["id"]
    accept = next(e for e in rt.store.operations() if '"ACCEPT_OFFER"' in e.payload_json and c.nonce in e.payload_json)
    assert '"requested_by":"OWNER"' in accept.payload_json.replace(" ", "")
    assert _decision(api, oid)["state"] == "AGREED"
    again = _accepted(api, oid, v, m, rt)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "ALREADY_ACCEPTED"


def test_the_buyers_yes_needs_the_sent_message_and_its_day(api: TestClient, rt: Runtime) -> None:
    oid, v = _evaluate(api, EX02)
    m = _message(api, oid, v["counters"][0]["id"])
    unsent = _accepted(api, oid, v, m, rt)
    assert unsent.status_code == 409 and unsent.json()["detail"]["code"] == "NOT_OFFERED"
    assert _offered(api, oid, v, m).status_code == 200
    wrong = api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-accepted",
                     json={"verdict_id": v["id"], "state_version": rt.store.get_state().state_version, "message_hash": "0" * 64})
    assert wrong.status_code == 409 and wrong.json()["detail"]["code"] == "NOT_OFFERED"
    assert api.post("/clock/advance", json={"to_day": m["valid_until_day"] + 1}).status_code == 200
    late = _accepted(api, oid, v, m, rt)
    assert late.status_code == 409 and late.json()["detail"]["code"] == "OFFER_EXPIRED"
    assert not [c for c in rt.store.commitments() if c.offer_id == oid]
    assert _decision(api, oid)["state"] == "NO_DEAL"  # unanswered after its day, the offer is over


def test_a_reply_with_terms_of_its_own_is_a_new_request_and_closes_this_one(api: TestClient, rt: Runtime) -> None:
    oid, v, m = _sent(api)
    r = api.post(f"/offers/{oid}/buyer-reply", json={"verdict_id": v["id"], "counter_id": m["counter_id"],
                                                     "text": "Could you do 50-day terms instead?"})
    assert r.status_code == 200, r.text
    new = r.json()["reply_offer_id"]
    stored = rt.store.get_offer(new)
    assert stored is not None and stored.counterparty_id == "BUYER-1" and stored.obligations
    assert _decision(api, oid)["state"] == "REPLIED"
    assert _decision(api, new)["state"] == "RECEIVED"
    doc = rt.documents[stored.doc_ids[0]]
    assert doc.channel == "email" and doc.parent_doc_id is not None  # buyer text, never the owner's channel
    twice = api.post(f"/offers/{oid}/buyer-reply", json={"verdict_id": v["id"], "counter_id": m["counter_id"], "text": "Or 52 days?"})
    assert twice.status_code == 409 and twice.json()["detail"]["code"] == "ALREADY_ANSWERED"
    yes = _accepted(api, oid, v, m, rt)
    assert yes.status_code == 409 and yes.json()["detail"]["code"] == "ALREADY_ANSWERED"
    # the pasted reply is a known sender: its own counter can be offered in turn
    v2 = api.post(f"/offers/{new}/evaluate").json()
    for c in v2["counters"]:
        assert _message(api, new, c["id"])["provenance"]["via"] == "buyer_reply"


def test_a_reply_with_no_terms_is_refused_and_nothing_is_stored(api: TestClient, rt: Runtime) -> None:
    oid, v, m = _sent(api)
    offers = len(rt.store.offers()) if hasattr(rt.store, "offers") else None
    r = api.post(f"/offers/{oid}/buyer-reply", json={"verdict_id": v["id"], "counter_id": m["counter_id"], "text": "Thanks, noted."})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NO_TERMS_IN_REPLY"
    if offers is not None:
        assert len(rt.store.offers()) == offers
    assert _decision(api, oid)["state"] == "AWAITING_BUYER"


def test_a_reply_needs_an_offer_sent(api: TestClient) -> None:
    oid, v = _evaluate(api, EX02)
    r = api.post(f"/offers/{oid}/buyer-reply", json={"verdict_id": v["id"], "counter_id": v["counters"][0]["id"],
                                                     "text": "Could you do 50-day terms instead?"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NOT_OFFERED"


def test_every_route_is_the_owners(api: TestClient) -> None:
    oid, v = _evaluate(api, EX02)
    cid = v["counters"][0]["id"]
    stranger = TestClient(api.app)
    assert stranger.get(f"/offers/{oid}/counters/{cid}/message").status_code in (401, 403)
    assert stranger.post(f"/offers/{oid}/counters/{cid}/offered", json={}).status_code in (401, 403)
    assert stranger.post(f"/offers/{oid}/counters/{cid}/buyer-accepted", json={}).status_code in (401, 403)
    assert stranger.post(f"/offers/{oid}/buyer-reply", json={}).status_code in (401, 403)
    agent = TestClient(api.app, headers={"X-Agent-Key": "demo-agent-key"})
    assert agent.post(f"/offers/{oid}/counters/{cid}/buyer-accepted", json={}).status_code in (401, 403)


# ================================================================ the verifier's findings (16 Oct)


def test_an_offer_sent_stands_until_its_day_when_the_request_itself_lapses(api: TestClient, rt: Runtime) -> None:
    """Finding 1: EX01's ask (early payment by day 2) lapses on day 3, but Option B (terms and price) was offered open until day 7."""
    oid, v, m = _sent(api, EX01, counter=1)
    assert m["valid_until_day"] == 7
    assert api.post("/clock/advance", json={"to_day": 3}).status_code == 200
    assert _decision(api, oid)["state"] == "AWAITING_BUYER"
    r = _accepted(api, oid, v, m, rt)
    assert r.status_code == 200, r.text
    assert r.json()["status"] in ("agreed", "waiting_approval")


def test_the_buyers_yes_is_never_said_as_accepted_as_asked(api: TestClient, rt: Runtime) -> None:
    """Finding 2: the owner's AcceptOffer of an offered counter is the buyer's yes, not the owner accepting the request as asked."""
    import json

    oid, v, m = _sent(api)
    assert _accepted(api, oid, v, m, rt).status_code == 200
    for lang in ("en", "zh"):
        d = _decision(api, oid, lang)
        said = json.dumps(d, ensure_ascii=False)
        assert "as asked" not in said and "按对方要求接受" not in said
    said = json.dumps(_decision(api, oid), ensure_ascii=False)
    assert "You sent this counter to the buyer yourself, and recorded that they accepted it." in said
    assert "The buyer accepted the counter you sent; you recorded it." in said
    assert "The counter sent was not recorded." not in said


def test_a_reply_after_the_buyers_yes_is_refused_and_stores_nothing(api: TestClient, rt: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding 3: the buyer's yes recorded while the reply compiles closes the deal; the reply is then refused, nothing is stored."""
    from app.api import outbound

    oid, v, m = _sent(api)
    real = outbound.compile_offer

    def compile_while_the_yes_lands(docs, cp):  # type: ignore[no-untyped-def]
        assert _accepted(api, oid, v, m, rt).status_code == 200
        return real(docs, cp)

    monkeypatch.setattr(outbound, "compile_offer", compile_while_the_yes_lands)
    r = api.post(f"/offers/{oid}/buyer-reply", json={"verdict_id": v["id"], "counter_id": m["counter_id"],
                                                     "text": "Could you do 50-day terms instead?"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ALREADY_ACCEPTED"
    assert _decision(api, oid)["state"] == "AGREED"
    assert not [d for d in rt.documents.values() if d.doc_id.startswith("reply-")]


def test_a_buyers_key_vouches_only_for_its_own_buyer(api: TestClient) -> None:
    """Finding 4: BUYER-2's key filing a fixture of BUYER-1 is not BUYER-1's request."""
    keyed = TestClient(api.app, headers={"X-Counterparty-Key": "demo-buyer-2-key"})
    oid = keyed.post("/offers", json={"fixture_id": EX02}).json()["offer"]["offer_id"]
    v = api.post(f"/offers/{oid}/evaluate", json={"fixture_id": EX02}).json()
    m = _message(api, oid, v["counters"][0]["id"])
    assert m["provenance"]["via"] == "anonymous" and m["blocked"]["code"] == "UNVERIFIED_SENDER"


def test_with_two_counters_out_the_deal_closes_on_the_later_day(api: TestClient) -> None:
    """Finding 5: the state, the wait and the worklist read the same offer: the one open latest."""
    oid, v = _evaluate(api, EX01)
    b, a = (_message(api, oid, c["id"]) for c in (v["counters"][1], v["counters"][0]))
    assert _offered(api, oid, v, b).status_code == 200 and _offered(api, oid, v, a).status_code == 200
    assert (a["valid_until_day"], b["valid_until_day"]) == (2, 7)
    assert api.post("/clock/advance", json={"to_day": 5}).status_code == 200
    d = _decision(api, oid)
    assert d["state"] == "AWAITING_BUYER" and "closes in 2 days" in d["waiting_for"]["text"]
