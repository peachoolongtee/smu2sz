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
    for said in ("¥420,000 invoice issued on 18 September 2026 and due on 2 November 2026", "up to ¥260,000", "on or before 3 October 2026",
                 "0.85% discount", "Paying ¥257,790 by then settles ¥260,000 of the invoice",
                 "including the other ¥160,000, stays due on 2 November 2026", "No other terms change", "open until 3 October 2026"):
        assert said in text
    assert "day 2" not in text and "this invoice" not in text  # the engine's own record of the terms is not the message
    assert "2026年9月18日开具、2026年11月2日到期的 ¥420,000 发票" in zh["text"] and "支付 ¥257,790" in zh["text"] and "0.85%" in zh["text"]
    assert en["terms_hash"] == zh["terms_hash"] and en["message_hash"] != zh["message_hash"]
    assert en["valid_until_date"] == "3 October 2026" and en["offered"] is None


def test_a_counter_of_two_terms_says_both_and_nothing_else(api: TestClient) -> None:
    oid, v = _evaluate(api, EX01)
    b = next(c for c in v["counters"] if c["label"] == "Option B")
    text = _message(api, oid, b["id"])["text"]
    assert "1. Payment terms on future invoices move from 45 to 55 days." in text
    assert "2. Prices on future invoices rise by 0.30%." in text
    # every other ask is answered, not left to "everything else"
    assert "3. We are not able to offer the early-payment discount you asked for." in text
    assert "4. We are not able to offer the rebate you asked for." in text


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


# ================================================================ the buyer's answer on the record (phase 3 backend, 16 Oct)


def test_the_review_beside_the_message_is_the_pictures_and_the_words_follow_the_page(api: TestClient) -> None:
    oid, v = _evaluate(api, EX02)
    m = api.get(f"/offers/{oid}/counters/{v['counters'][0]['id']}/message", params={"lang": "zh", "ui_lang": "en"}).json()
    assert m["text"].startswith("Foshan Home Retail Co.：") and m["lang"] == "zh" and m["ui_lang"] == "en"
    assert m["notice_text"].startswith("FLOW does not send this message") and m["valid_until_date"] == "3 October 2026"
    assert m["provenance"]["verified"] is True and [x["code"] for x in m["languages"]] == ["en", "zh"]
    early = next(r for r in m["review"]["terms"] if r["key"] == "early_payment")
    assert early["value_text"] == "0.85% off ¥260,000.00" and early["instead_of_text"] == "instead of 1.50% off ¥420,000.00"
    assert m["review"]["cost_display"] and m["review"]["needs_owner"] is False


def test_the_record_says_what_was_sent_and_how_each_answer_is_recorded(api: TestClient) -> None:
    oid, _v, m = _sent(api)
    d = _decision(api, oid)
    out = d["outbound"]
    assert out["answer"] is None and out["tone"] == "waiting" and out["label_text"] == "Option A"
    assert out["message_same"] and out["message_text"] == m["text"]
    assert out["closes"] == {"day": 2, "when": "in 2 days", "date": "3 October 2026"} and out["progress"] == 0.0
    assert out["title_text"] == "Waiting for Foshan Home Retail Co.'s response"
    assert out["status_text"] == ("Option A · marked sent by you on 1 October 2026 · FLOW cannot confirm delivery · expires 3 October 2026 "
                                  "(in 2 days)")
    acts = out["actions"]
    assert [acts[k]["label"] for k in ("accept", "counter", "unclear", "decline")] == ["Accepted", "Proposed different terms",
                                                                                       "Unclear or a question", "Declined"]
    assert acts["accept"]["authority_text"] == "Within your mandate: in force when you record it."
    assert acts["accept"]["confirm_label"] == "Confirm and record agreement" and "exactly these terms of Option A" in acts["accept"]["binding_text"]
    assert acts["decline"]["effect_text"] == "Nothing is agreed and no money moves. The invoice stays due on its existing terms."
    assert "fund" not in acts["decline"]["effect_text"].lower()  # recording a real buyer's no runs nothing
    assert [r["code"] for r in acts["decline"]["reasons"]] == ["DISCOUNT_TOO_LOW", "WANTED_LONGER_TERMS", "NO_LONGER_NEEDED", "OTHER", "NO_REASON"]
    assert [h["kind"] for h in d["history"]] == ["received", "checked", "offered"]
    assert _decision(api, oid, "zh")["outbound"]["title_text"] == "等待Foshan Home Retail Co.答复"
    assert d["history"][-1]["source"] == "owner" and d["history"][0]["source"] == "buyer"


def test_the_buyers_no_closes_the_deal_with_its_reason_and_moves_nothing(api: TestClient, rt: Runtime) -> None:
    oid, v, m = _sent(api)
    ops, commitments = len(rt.store.operations()), len(rt.store.commitments())
    r = api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-declined",
                 json={"verdict_id": v["id"], "message_hash": m["message_hash"], "reason": "DISCOUNT_TOO_LOW"})
    assert r.status_code == 200, r.text
    d = r.json()["decision"]
    assert (d["state"], d["state_text"], d["lifecycle"], d["terminal"]) == ("NO_DEAL", "Declined by the buyer", "declined", True)
    assert d["outbound"]["answer"] == "declined" and d["outbound"]["reason_text"] == "Reason, as you reported it: Discount too low"
    assert d["outbound"]["title_text"] == "No agreement was reached" and "nothing was agreed, borrowed or moved" in d["outbound"]["text"]
    assert d["history"][-1]["text"] == "You recorded that Foshan Home Retail Co. declined (discount too low)"
    assert (len(rt.store.operations()), len(rt.store.commitments())) == (ops, commitments)
    for path, body in ((f"/offers/{oid}/counters/{m['counter_id']}/buyer-declined", {"verdict_id": v["id"], "message_hash": m["message_hash"]}),
                       (f"/offers/{oid}/counters/{m['counter_id']}/buyer-accepted",
                        {"verdict_id": v["id"], "state_version": rt.store.get_state().state_version, "message_hash": m["message_hash"]}),
                       (f"/offers/{oid}/buyer-reply", {"verdict_id": v["id"], "counter_id": m["counter_id"], "text": "Could you do 50-day terms?"})):
        again = api.post(path, json=body)
        assert again.status_code == 409 and again.json()["detail"]["code"] == "ALREADY_DECLINED_BY_BUYER", path
    assert _decision(api, oid, "zh")["state_text"] == "买方已拒绝"


def test_an_offer_that_closes_unanswered_says_so(api: TestClient) -> None:
    oid, _v, _m = _sent(api)
    assert api.post("/clock/advance", json={"to_day": 3}).status_code == 200
    d = _decision(api, oid)
    assert (d["state"], d["state_text"], d["lifecycle"]) == ("NO_DEAL", "Closed without an answer", "no_answer")
    assert d["outbound"]["answer"] == "no_answer" and d["outbound"]["title_text"] == "No response by 3 October 2026"
    assert d["history"][-1]["kind"] == "no_answer"


def test_the_buyers_yes_reads_as_what_happened(api: TestClient, rt: Runtime) -> None:
    oid, v, m = _sent(api)
    assert _accepted(api, oid, v, m, rt).status_code == 200
    out = _decision(api, oid)["outbound"]
    assert out["answer"] == "accepted" and out["tone"] == "ok" and out["status_text"] == "The agreement is in force."
    assert out["title_text"] == "Buyer acceptance recorded" and out["actions"] is None
    assert out["text"] == "You confirmed that Foshan Home Retail Co. accepted Option A on 1 October 2026."
    assert out["provenance_text"] == "Source: recorded by you; no buyer message attached" and out["evidence_quote"] is None
    assert out["consequences"] == ["Foshan Home Retail Co. can settle ¥260,000.00 of the invoice by paying ¥257,790.00 by 3 October 2026.",
                                   "The other ¥160,000.00 stays due on 2 November 2026.",
                                   "No cash has been received yet; FLOW reconciles the payment when it arrives.",
                                   # recording the yes funds nothing (18 Oct): the reserve gap still ahead and where the plan is
                                   ("The agreement ran no funding: cash still falls ¥102,210.00 below your minimum in 20 days. FLOW's plan to "
                                    "cover it is ready on Cash & funding; it runs only when you run it.")]
    assert [x["href"] for x in out["links"]] == ["/cash", "/receivables#RCV-A", "/customers/BUYER-1"]


def test_their_counter_reads_as_a_new_request_to_answer(api: TestClient) -> None:
    oid2, v2, m2 = _sent(api, EX01, counter=1)
    r = api.post(f"/offers/{oid2}/buyer-reply", json={"verdict_id": v2["id"], "counter_id": m2["counter_id"], "text": "Could you do 50-day terms instead?"})
    out2 = _decision(api, oid2)["outbound"]
    assert out2["answer"] == "countered" and out2["reply_quote"] == "Could you do 50-day terms instead?"
    assert out2["links"][0]["href"] == f"/deals?decision=deal:{r.json()['reply_offer_id']}"


# ================================================================ the verifier's findings on the answer (16 Oct, second round)


def test_once_an_offer_is_sent_outside_neither_the_simulator_nor_accept_as_asked_answers_it(api: TestClient, rt: Runtime) -> None:
    """Finding 1: the buyer's answer is recorded on the deal; the simulated buyer and the owner's own accept do not answer it as well."""
    oid, v, m = _sent(api)
    sim = api.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"})
    assert sim.status_code == 409 and sim.json()["detail"]["code"] == "OFFER_SENT_OUTSIDE"
    assert api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-declined",
                    json={"verdict_id": v["id"], "message_hash": m["message_hash"]}).status_code == 200
    ops = len(rt.store.operations())
    for path, body in ((f"/negotiate/{oid}", {"buyer_profile": "cooperative"}),
                       (f"/offers/{oid}/accept", {"verdict_id": v["id"], "state_version": rt.store.get_state().state_version})):
        r = api.post(path, json=body)
        assert r.status_code == 409 and r.json()["detail"]["code"] in ("OFFER_SENT_OUTSIDE", "NOT_ACCEPTABLE"), (path, r.text)
    assert len(rt.store.operations()) == ops and _decision(api, oid)["outbound"]["answer"] == "declined"


def test_a_no_to_one_of_two_counters_names_that_counter(api: TestClient) -> None:
    """Finding 2: the title names the counter the buyer refused, not the latest one sent."""
    oid, v = _evaluate(api, EX01)
    b, a = (_message(api, oid, c["id"]) for c in (v["counters"][1], v["counters"][0]))
    assert _offered(api, oid, v, b).status_code == 200 and _offered(api, oid, v, a).status_code == 200
    r = api.post(f"/offers/{oid}/counters/{a['counter_id']}/buyer-declined", json={"verdict_id": v["id"], "message_hash": a["message_hash"]})
    assert r.status_code == 200
    assert "declined Option A on" in r.json()["decision"]["outbound"]["text"]


def test_a_yes_whose_approval_you_rejected_says_nothing_is_in_force_and_takes_no_other_answer(api: TestClient, rt: Runtime) -> None:
    """Finding 3: the record follows the approval; after the yes, no other answer is recorded."""
    oid, v, m = _sent(api, EX01, counter=1)
    yes = _accepted(api, oid, v, m, rt)
    assert yes.status_code == 200 and yes.json()["status"] == "waiting_approval"
    assert _decision(api, oid)["outbound"]["status_text"] == "The agreement waits for your approval and is not in force yet."
    assert api.post(f"/approvals/{yes.json()['approval_id']}", json={"decision": "REJECT"}).status_code == 200
    out = _decision(api, oid)["outbound"]
    assert out["answer"] == "accepted" and out["status_text"] == "You declined the agreement at approval: nothing is in force." and out["tone"] == "neutral"
    no = api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-declined", json={"verdict_id": v["id"], "message_hash": m["message_hash"]})
    assert no.status_code == 409 and no.json()["detail"]["code"] == "ALREADY_ANSWERED"


def test_a_no_after_the_offer_closed_is_refused(api: TestClient) -> None:
    """Finding 5: like a late yes, a late no is not recorded; the offer already closed unanswered."""
    oid, v, m = _sent(api)
    assert api.post("/clock/advance", json={"to_day": 3}).status_code == 200
    r = api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-declined", json={"verdict_id": v["id"], "message_hash": m["message_hash"]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "OFFER_EXPIRED"
    assert _decision(api, oid)["outbound"]["answer"] == "no_answer"


# ================================================================ round four: the audit's P0s and the workspace contract (16 Oct)


def test_the_review_says_who_decides_and_how_it_is_sent_without_saying_flow_sends(api: TestClient) -> None:
    oid, v = _evaluate(api, EX02)
    m = _message(api, oid, v["counters"][0]["id"])
    assert m["review"]["decides_text"] == m["authority_text"] == "Within your mandate: no approval needed."
    assert m["channel"] == {"kind": "manual", "label": "Manual sending · No channel connected",
                            "text": "FLOW cannot send this or confirm it arrived. Copy it and send it through your usual channel."}
    assert (m["copy_label"], m["mark_sent_label"], m["send_title_text"]) == ("Copy response", "Mark as sent", "Your response to Foshan Home Retail Co.")
    assert m["template_version"] == "buyer-message-v2" and "if_declined_text" not in m["review"]
    said = " ".join(str(x) for x in (m["review"], m["authority_text"], m["notice_text"], m["mark_sent_effect_text"]))
    assert "FLOW can send" not in said and "will fund" not in said


def test_a_mark_made_by_mistake_is_corrected_on_the_record_and_can_be_marked_again(api: TestClient, rt: Runtime) -> None:
    oid, v, m = _sent(api)
    undo = api.post(f"/offers/{oid}/counters/{m['counter_id']}/offered/withdraw", json={"verdict_id": v["id"], "message_hash": m["message_hash"]})
    assert undo.status_code == 200, undo.text
    d = undo.json()["decision"]
    assert d["state"] == "RESPONSE_READY" and d["outbound"] is None
    assert [h["kind"] for h in d["history"]][-2:] == ["offered", "withdrawn"]
    assert d["history"][-1]["text"] == "You corrected it: Option A was not sent"
    again = _offered(api, oid, v, _message(api, oid, m["counter_id"]))
    assert again.status_code == 200 and _decision(api, oid)["state"] == "AWAITING_BUYER"
    assert [h["kind"] for h in _decision(api, oid)["history"]][-3:] == ["offered", "withdrawn", "offered"]
    twice = api.post(f"/offers/{oid}/counters/{m['counter_id']}/offered/withdraw", json={"verdict_id": v["id"], "message_hash": "0" * 64})
    assert twice.status_code == 409 and twice.json()["detail"]["code"] == "NOT_OFFERED"


def test_a_yes_with_the_buyers_message_says_where_it_came_from(api: TestClient, rt: Runtime) -> None:
    oid, v, m = _sent(api)
    r = api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-accepted",
                 json={"verdict_id": v["id"], "state_version": rt.store.get_state().state_version, "message_hash": m["message_hash"],
                       "evidence_text": "Agreed, we will pay ¥257,790.00 by 3 October."})
    assert r.status_code == 200, r.text
    out = _decision(api, oid)["outbound"]
    assert out["provenance_text"] == "Source: recorded by you, with the buyer's message"
    assert out["evidence_quote"] == "Agreed, we will pay ¥257,790.00 by 3 October."
    assert _decision(api, oid)["history"][-1]["text"] == "You recorded that Foshan Home Retail Co. accepted, with their message"


def test_their_counter_is_compared_with_our_offer_and_the_new_request_links_back(api: TestClient) -> None:
    oid, v, m = _sent(api, EX01, counter=1)
    r = api.post(f"/offers/{oid}/buyer-reply", json={"verdict_id": v["id"], "counter_id": m["counter_id"],
                                                     "text": "Could you do 50-day terms instead?"})
    assert r.status_code == 200, r.text
    out = _decision(api, oid)["outbound"]
    terms = next(row for row in out["changes"] if row["key"] == "payment_terms")
    assert (terms["ours_text"], terms["theirs_text"], terms["changed"]) == ("55 days", "50 days", True)
    assert out["reply_state_text"] == "FLOW has not evaluated their reply yet."
    back = _decision(api, r.json()["reply_offer_id"])["reply_to"]
    assert back["decision_id"] == f"deal:{oid}" and back["title_text"] == "In reply to Option B you sent on 1 October 2026"
    assert _decision(api, oid)["reply_to"] is None


def test_a_reply_naming_one_invoice_and_future_terms_is_read_without_asking_which_invoice(api: TestClient) -> None:
    """The audit's clarification case: "the 420,000 invoice" is one invoice; "future invoices" belongs to the terms ask, not the discount."""
    oid, v, m = _sent(api)
    text = "We can pay the 420,000 invoice early, but only with a 1.2% discount, and we need 60-day terms on future invoices."
    r = api.post(f"/offers/{oid}/buyer-reply", json={"verdict_id": v["id"], "counter_id": m["counter_id"], "text": text})
    assert r.status_code == 200, r.text
    new = r.json()["offer"]
    assert new["status"] == "COMPILED" and not new["abstentions"]
    assert {o["type"] for o in new["obligations"]} == {"IMMEDIATE_DISCOUNT", "TERMS_EXTENSION"}


def test_a_discount_on_several_invoices_still_asks_which_one_in_plain_words(api: TestClient) -> None:
    docs = [{"doc_id": "several-1", "channel": "email", "sender_id": "BUYER-1", "received_day": 0,
             "text": "We will pay these invoices early if you give us 1.2% off."}]
    offer = api.post("/offers", json={"counterparty_id": "BUYER-1", "documents": docs}).json()["offer"]
    [scope] = [a for a in offer["abstentions"] if a["field"].endswith("base.receivable_id")]
    assert scope["reason_when"] == "Their message does not say which single invoice the discount is for. Ask them which invoice it applies to."


# ================================================================ the verifier's round-four findings


def test_a_missed_early_payment_does_not_read_as_in_force(api: TestClient, rt: Runtime) -> None:
    """Finding 2: past the early-payment day unpaid, the record says so and offers no settlement by a passed date."""
    oid, v, m = _sent(api)
    assert _accepted(api, oid, v, m, rt).status_code == 200
    assert api.post("/clock/advance", json={"to_day": 5}).status_code == 200
    d = _decision(api, oid)
    out = d["outbound"]
    assert d["state"] == "MISSED" and out["tone"] == "neutral"
    assert out["status_text"] == "The early payment did not arrive by its day; the invoice stays due on its existing terms."
    assert out["consequences"][0] == "No early payment arrived by 3 October 2026; the invoice stays due on 2 November 2026."
    assert not any("by paying" in line or "No cash has been received yet" in line for line in out["consequences"])


def test_a_closed_offer_cannot_be_corrected_into_never_sent(api: TestClient) -> None:
    """Finding 3: "no answer" stays "no answer"."""
    oid, v, m = _sent(api)
    assert api.post("/clock/advance", json={"to_day": 3}).status_code == 200
    r = api.post(f"/offers/{oid}/counters/{m['counter_id']}/offered/withdraw", json={"verdict_id": v["id"], "message_hash": m["message_hash"]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "OFFER_EXPIRED"
    assert _decision(api, oid)["outbound"]["answer"] == "no_answer"


def test_after_a_correction_the_owners_other_answers_are_open_again(api: TestClient, rt: Runtime) -> None:
    """Finding 4: a corrected mark no longer keeps the simulator away."""
    oid, v, m = _sent(api)
    assert api.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()["detail"]["code"] == "OFFER_SENT_OUTSIDE"
    assert api.post(f"/offers/{oid}/counters/{m['counter_id']}/offered/withdraw",
                    json={"verdict_id": v["id"], "message_hash": m["message_hash"]}).status_code == 200
    assert api.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).status_code == 200


def test_the_words_sent_stay_readable_after_the_books_move(api: TestClient, rt: Runtime) -> None:
    """Finding 5: the record shows the exact words the owner marked sent, checked by their hash, even once the invoice changes."""
    oid, _v, m = _sent(api)
    rcv = next(r for r in rt.store.get_state().receivables if r.id == "RCV-A")
    rt.store.put_state(rt.store.get_state().model_copy(update={"receivables": [
        r.model_copy(update={"settled_fen": 1_000_000}) if r.id == rcv.id else r for r in rt.store.get_state().receivables]}))
    out = _decision(api, oid)["outbound"]
    assert out["message_same"] and out["message_text"] == m["text"]


def test_a_pasted_acceptance_is_never_dropped_for_a_claimed_id(api: TestClient, rt: Runtime) -> None:
    """Finding 6: the evidence's id is random; nobody can plant a document under it first."""
    oid, v, m = _sent(api)
    r = api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-accepted",
                 json={"verdict_id": v["id"], "state_version": rt.store.get_state().state_version, "message_hash": m["message_hash"],
                       "evidence_text": "Yes, agreed."})
    assert r.status_code == 200 and _decision(api, oid)["outbound"]["evidence_quote"] == "Yes, agreed."


def test_a_reply_names_the_counter_it_answered(api: TestClient) -> None:
    """Finding 7: with two counters marked, the reply links to the one it answered."""
    oid, v = _evaluate(api, EX01)
    b, a = (_message(api, oid, c["id"]) for c in (v["counters"][1], v["counters"][0]))
    assert _offered(api, oid, v, b).status_code == 200 and _offered(api, oid, v, a).status_code == 200
    r = api.post(f"/offers/{oid}/buyer-reply", json={"verdict_id": v["id"], "counter_id": b["counter_id"], "text": "Could you do 50-day terms instead?"})
    assert _decision(api, r.json()["reply_offer_id"])["reply_to"]["title_text"] == "In reply to Option B you sent on 1 October 2026"


def test_an_offer_that_ended_unagreed_lists_what_was_offered_never_as_in_force(api: TestClient) -> None:
    """Owner review of the screens: after the offer closed, its terms read as offered, not "effective yesterday"."""
    oid, _v, _m = _sent(api)
    assert _decision(api, oid)["outbound"]["terms_title_text"] == "What you offered"
    assert api.post("/clock/advance", json={"to_day": 3}).status_code == 200
    out = _decision(api, oid)["outbound"]
    assert out["terms_title_text"] == "What you offered (not agreed)"
    assert out["terms"] == ["Payment terms: 45 days", "Early payment: 0.85% off ¥260,000.00", "Rebate or price: Not offered"]
    assert not any("effective" in line for line in out["terms"])
