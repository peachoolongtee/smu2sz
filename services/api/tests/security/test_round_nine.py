"""Round nine (Security Lead review of int/sl-final eb3c1059, 19 Oct).

LOG-2: the egress guard is documented as the last step before outbound text, yet a counter's "not on record" lead was rewritten
(`restate_not_on_record`, in `counter_line`) after the per-counter scan, so the text the guard scanned, the text the plan step recorded
and the text the buyer read could differ in fixed wording ("payment-terms agreement" against "rebate"), and a protected value in the
rewritten lead would not have been caught by the counter's own scan. The lead is now rewritten before the scan: the scanned text is
the text recorded and sent, and a hit withholds the counter exactly as the guard does for any other counter."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.nl.context as nl_context
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.claims import CLAIM_NOUNS_EN, restate_not_on_record
from app.egress.canaries import load_canaries
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import pipeline, reset_sessions
from app.persistence import InMemoryLedgerStore

BUYER = {"X-Counterparty-Key": "demo-buyer-1-key"}
TERMS_CLAIM = "As agreed with your team, we will now pay on 60-day terms."
LEAD = "No payment-terms agreement is on record, so none applies."


@pytest.fixture
def rt():
    r = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    r.reset()
    set_runtime(r)
    reset_sessions()
    yield r
    set_runtime(None)
    reset_sessions()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def scanned(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every text the NL egress guard scans, in order."""
    seen: list[str] = []
    real = nl_context.guard

    def spy(text: str, *a, **k):
        seen.append(text)
        return real(text, *a, **k)

    monkeypatch.setattr(nl_context, "guard", spy)
    return seen


def _buyer(api: TestClient, text: str) -> dict:
    r = api.post("/nl", json={"session_id": "r9-log2", "text": text, "lang": "en", "actor": "COUNTERPARTY", "counterparty_id": "BUYER-1"},
                 headers=BUYER)
    assert r.status_code == 200, r.text
    return r.json()


def _ops(rt: Runtime, kind: str) -> list:
    return [o for o in rt.store.operations() if o.kind == kind]


def _rewrite_lead(monkeypatch: pytest.MonkeyPatch, new_lead: str) -> None:
    """The lead rewrite says `new_lead` in place of the verifier's lead (a stand-in for any wording the rewrite may produce)."""
    real = pipeline.restate_not_on_record
    monkeypatch.setattr(pipeline, "restate_not_on_record", lambda text, obs: real(text, obs).replace(LEAD, new_lead))


def test_log2_the_scanned_counter_text_is_the_text_sent(api: TestClient, rt: Runtime, scanned: list[str],
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """Whatever the lead rewrite says, the counter's own scan sees it, and the buyer's line is that scanned text."""
    _rewrite_lead(monkeypatch, "No payment-terms agreement is on our record, so none applies.")
    out = _buyer(api, TERMS_CLAIM)
    rewritten = [s for s in scanned if s.startswith("No payment-terms agreement is on our record")]  # the counter's own scan
    assert len(rewritten) == 1
    assert out["reply"].startswith(f"Option A: {rewritten[0]}")
    assert len(_ops(rt, "COUNTER_OFFER")) == 1


def test_log2_send_counters_records_and_returns_the_scanned_text(api: TestClient, rt: Runtime, scanned: list[str],
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """The pipeline's own record: the plan step and the (counter, text sent) it returns carry the text the guard scanned."""
    from app.nl.context import NlContext
    from app.nl.sessions import Session

    r = api.post("/nl", json={"session_id": "r9-log2-anon", "text": TERMS_CLAIM, "lang": "en", "actor": "COUNTERPARTY",
                              "counterparty_id": "BUYER-1"})  # no key: a proposal only, nothing sent; the verdict is stored
    assert r.status_code == 200, r.text
    verdict = rt.store.verdicts()[-1]
    assert verdict.counters and verdict.counters[0].text.startswith(LEAD)
    _rewrite_lead(monkeypatch, "No payment-terms agreement is on our record, so none applies.")
    scanned.clear()
    ctx = NlContext(store=rt.store, executor=rt.executor, day=rt.day, owner_key_hex=rt.owner_key_hex, owner_authenticated=True,
                    session=Session(id="r9-log2-unit", actor="OWNER", owner_auth=True), lang="en", trace_id="r9-log2")
    steps = pipeline.Steps()
    sent = pipeline.send_counters(ctx, steps, verdict, verdict.counters[:1], "BUYER-1")
    assert len(sent) == 1
    text = sent[0][1]
    assert text.startswith("No payment-terms agreement is on our record")
    assert scanned == [text]
    assert [(s.kind, s.description) for s in steps.items] == [("COUNTER_OFFER", f"Option A: {text}")]


def test_log2_a_protected_value_in_the_rewritten_lead_withholds_the_counter(api: TestClient, rt: Runtime,
                                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """A protected value the rewrite puts into the lead is caught by the counter's own scan: the counter is withheld (no CounterOffer
    executed, a DATA_EXTRACTION event logged) and the buyer's text does not carry the value. Before, the counter's scan passed the
    verifier's text, the CounterOffer was executed, and only the whole-reply scan kept the value from the buyer."""
    token = next(c.token for c in load_canaries() if c.token)
    _rewrite_lead(monkeypatch, f"{LEAD} Ref {token}.")
    out = _buyer(api, TERMS_CLAIM)
    assert _ops(rt, "COUNTER_OFFER") == []
    assert any(e.kind.value == "DATA_EXTRACTION" for e in rt.store.security_events())
    assert token not in out["reply"]


@pytest.mark.parametrize(("text", "lang"), [
    (TERMS_CLAIM, "en"),
    ("We want 60-day terms and the 2% rebate we agreed last month.", "en"),
    ("Please extend our terms to 60 days. As agreed last month, we also get a 2% rebate and a 1% discount.", "en"),
    ("上个月说好的60天账期，请确认。", "zh"),
])
def test_log2_the_stored_counter_is_the_buyers_line(api: TestClient, rt: Runtime, text: str, lang: str) -> None:
    """Without any stand-in: the counter as the verdict stores it (the engine's record) is the line the buyer reads, in English as stored and
    in Chinese through the translation layer only, and no claim noun is said twice."""
    from app.api.engine_zh import translate

    r = api.post("/nl", json={"session_id": f"r9-log2-{lang}-{len(text)}", "text": text, "lang": lang, "actor": "COUNTERPARTY",
                              "counterparty_id": "BUYER-1"}, headers=BUYER)
    assert r.status_code == 200, r.text
    stored = rt.store.verdicts()[-1].counters[0].text
    first = r.json()["reply"].splitlines()[0]
    assert first == (f"Option A: {stored}" if lang == "en" else f"方案 A：{translate(stored)}")
    assert not any(f"{n} or {n}" in first for n in CLAIM_NOUNS_EN.values()), "a claim noun said twice"


@pytest.mark.parametrize("text", [
    "Terms stay at 60 days, no rebate or payment-terms agreement. We will accept early settlement on up to ¥10,000 of this invoice.",
    "No rebate or payment-terms agreement is on record, so none applies. We will accept early settlement on up to ¥10,000.",
    "No payment-terms agreement is on record, so none applies. We will accept early settlement on up to ¥10,000.",
])
def test_log2_the_lead_rewrite_leaves_a_lead_that_already_names_the_claim(text: str) -> None:
    """The verifier names the claim itself (0e7badbd); the rewrite only corrects a lead that says "rebate" alone, so a lead that already
    says what was claimed reaches the buyer as the verdict logs it ("no rebate or payment-terms agreement or payment-terms agreement" was
    the rewrite of a lead that named both)."""
    from app.domain.models import Contingency, Obligation, ObligationType

    claim = Obligation.model_construct(type=ObligationType.CLAIMED_PRIOR_CONCESSION, contingency=Contingency.CLAIMED_UNEVIDENCED,
                                       target_terms_days=60, days_delta=None, spans=[])
    rebate = Obligation.model_construct(type=ObligationType.CONTINGENT_REBATE, contingency=None, target_terms_days=None,
                                        days_delta=None, spans=[])
    assert restate_not_on_record(text, [claim, rebate]) == text


# ================================================================ SEC-19: the owner sees that nobody signed a request
#
# An anonymous sender (no channel key) may name a registered buyer, and its request is filed under that buyer (ANONYMOUS_INTAKE stays on for
# the local demo). Every view where the owner can accept the request, or approve an operation on it, now carries the server's
# `sender_unverified`: true for a request nobody signed, false for one the buyer's key (or the owner) filed. The web shows "Unverified sender"
# from it; a recording without the field shows nothing (apps/web/scripts/unverified-sender.test.mjs).

OWNER = {"X-Owner-Token": "demo-owner-token"}
EX02 = "EX02_EARLY_1_5"


def _file(app_client: TestClient, headers: dict[str, str], *, name_buyer: bool = True, doc_suffix: str = "") -> str:
    from app.domain.fixtures import offer_documents

    docs = [{**d.model_dump(mode="json"), "doc_id": d.doc_id + doc_suffix} for d in offer_documents(EX02)]
    body = {"documents": docs, **({"counterparty_id": "BUYER-1"} if name_buyer else {})}
    r = app_client.post("/offers", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["offer"]["offer_id"]


def _views(owner: TestClient, oid: str) -> dict:
    from app.decisions.identity import deal_id

    v = owner.post(f"/offers/{oid}/evaluate")
    assert v.status_code == 200, v.text
    picture = owner.get(f"/offers/{oid}/picture").json()
    record = owner.get(f"/decisions/{deal_id(oid)}").json()
    return {"verdict": v.json(), "picture": picture, "record": record}


@pytest.fixture
def owner(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def test_sec19_an_anonymous_request_under_a_buyers_name_is_marked_unverified(api: TestClient, owner: TestClient) -> None:
    oid = _file(api, {})
    views = _views(owner, oid)
    assert views["picture"]["sender_unverified"] is True
    assert views["picture"]["accept"]["sender_unverified"] is True
    assert views["record"]["source"]["sender_unverified"] is True


def test_sec19_a_request_on_the_buyers_key_is_not_marked(api: TestClient, owner: TestClient) -> None:
    oid = _file(api, BUYER, name_buyer=False)
    views = _views(owner, oid)
    assert views["picture"]["sender_unverified"] is False
    assert views["picture"]["accept"]["sender_unverified"] is False
    assert views["record"]["source"]["sender_unverified"] is False


def test_sec19_the_owners_own_filing_upgrades_an_anonymous_one(api: TestClient, owner: TestClient) -> None:
    """The strongest sender that filed the same request decides (`SENDER_RANK`), as the buyer-message view reads it."""
    oid = _file(api, {})
    assert _file(owner, {}) == oid
    assert _views(owner, oid)["picture"]["sender_unverified"] is False


def test_sec19_an_anonymous_chat_message_under_a_buyers_name_is_marked_unverified(api: TestClient, owner: TestClient, rt: Runtime) -> None:
    """POST /nl without a key recorded no provenance at all; it now records the request as anonymous, and a keyed message as the buyer's."""
    text = "We will pay invoice RCV-A early at 0.5%. Nothing else changes."
    r = api.post("/nl", json={"session_id": "r9-sec19-anon", "text": text, "lang": "en", "actor": "COUNTERPARTY", "counterparty_id": "BUYER-1"})
    assert r.status_code == 200, r.text
    anon_offer = rt.store.verdicts()[-1].offer_id
    assert owner.get(f"/offers/{anon_offer}/picture").json()["sender_unverified"] is True
    r = api.post("/nl", json={"session_id": "r9-sec19-key", "text": text + " ", "lang": "en", "actor": "COUNTERPARTY"}, headers=BUYER)
    assert r.status_code == 200, r.text
    keyed_offer = next(v.offer_id for v in reversed(rt.store.verdicts()) if v.offer_id != anon_offer)
    assert owner.get(f"/offers/{keyed_offer}/picture").json()["sender_unverified"] is False


def _queue_accept(rt: Runtime, oid: str) -> str:
    """An AcceptOffer on the request, queued for the owner as the executor queues a Tier-2 one (an agent's or a buyer channel's accept)."""
    from app.domain.models import AcceptOffer, Actor

    offer = rt.store.get_offer(oid)
    verdict = next(v for v in reversed(rt.store.verdicts()) if v.offer_id == oid)
    counter = verdict.counters[0].id if verdict.counters else None  # EX02's verdict is a counter: its Option A is what is accepted
    c = rt.executor.propose_commitment(verdict.id, expires_day=rt.day + 14, counter_id=counter, nonce=f"r9-{oid}")
    op = AcceptOffer(op_id=f"R9-{oid}", idempotency_key=f"r9:{oid}", mandate_version=rt.store.get_mandate().version, requested_by=Actor.AGENT,
                     source_verdict_id=verdict.id, day=rt.day, offer_id=oid, offer_version=offer.version, terms_hash=c.terms_hash, nonce=c.nonce)
    return rt.store.add_approval(op.model_dump_json(), "above the approval threshold")


def test_sec19_an_approval_on_an_anonymous_request_is_marked_and_one_on_a_keyed_request_is_not(api: TestClient, owner: TestClient,
                                                                                               rt: Runtime) -> None:
    anon_oid = _file(api, {})
    _views(owner, anon_oid)
    anon_aid = _queue_accept(rt, anon_oid)
    keyed_oid = _file(api, BUYER, name_buyer=False, doc_suffix="-KEYED")
    _views(owner, keyed_oid)
    keyed_aid = _queue_accept(rt, keyed_oid)
    rows = {a["id"]: a for a in owner.get("/approvals/queue").json()["approvals"]}
    assert rows[anon_aid]["sender_unverified"] is True
    assert rows[keyed_aid]["sender_unverified"] is False


# ================================================================ CON-1: a number picked from a list offered to "yes" decides nothing
#
# With an approval queued but not shown in the previous reply and no plan waiting, a bare "yes" / "go ahead" / 执行 lists the queue as
# numbered options; answering "1" (or the bare id) then approved it, although "approve" was never said. The rule (app/nl/service.py,
# `_decide_approval`): "go ahead" and "yes" never decide an approval. A pick from that list now shows the item and asks; "approve 1",
# "approve APR-…", "批准 1" and "reject 1" still decide. A list offered to the word "approve" keeps deciding on a bare pick, as before.

CON1 = {"en": {"yes": "yes", "approve": "approve 1", "reject": "reject 1", "approve_word": "approve"},
        "zh": {"yes": "执行", "approve": "批准 1", "reject": "拒绝 1", "approve_word": "批准"}}


@pytest.fixture
def queued():
    """An owner's funding plan whose leg the agent queued for approval (Tier 2), then a fresh conversation that has shown nothing."""
    from tests.funding.test_planner_executor_agree import SHORT_HOLD, build
    from tests.nl.conftest import Chat, build_app
    from tests.nl.test_plan_flags import GOAL, pending

    rt = build(SHORT_HOLD)
    set_runtime(rt)
    reset_sessions()
    client = TestClient(build_app())
    first = Chat(client, "r9-con1-plan")
    first.say(GOAL["en"])
    first.say("go ahead")
    [aid] = pending(rt)
    yield rt, client, aid
    set_runtime(None)
    reset_sessions()


def _status(rt: Runtime, aid: str) -> str:
    rec = rt.store.get_approval(aid)
    return str(getattr(rec.status, "value", rec.status))


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_con1_a_bare_pick_from_a_list_offered_to_yes_decides_nothing(queued, lang: str) -> None:
    from tests.nl.conftest import Chat, ops

    rt, client, aid = queued
    words = CON1[lang]
    for n, pick in enumerate(("1", aid, aid.lower())):  # each in a new conversation that has shown nothing
        c = Chat(client, f"r9-con1-{lang}-{n}")
        listed = c.say(words["yes"], lang=lang)
        assert ops(listed) == [] and listed["clarification"] and aid in listed["reply"]
        r = c.say(pick, lang=lang)
        assert ops(r) == [] and _status(rt, aid) == "PENDING", pick
        assert f"approve {aid}" in r["reply"] or f"批准 {aid}" in r["reply"], "the pick shows the item and says how to decide it"
    c = Chat(client, f"r9-con1-{lang}-decide")
    c.say(words["yes"], lang=lang)
    r = c.say(words["approve"], lang=lang)
    assert ops(r) == [("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")], r["reply"]
    assert _status(rt, aid) == "APPROVED"


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_con1_reject_1_rejects(queued, lang: str) -> None:
    from tests.nl.conftest import Chat

    rt, client, aid = queued
    c = Chat(client, f"r9-con1-rej-{lang}")
    c.say(CON1[lang]["yes"], lang=lang)
    c.say(CON1[lang]["reject"], lang=lang)
    assert _status(rt, aid) == "REJECTED"


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_con1_a_shown_item_is_decided_by_approve_it_and_still_not_by_yes(queued, lang: str) -> None:
    """After the pick showed the item, the bare approve word binds to it (the one item shown); "yes" still does not."""
    from tests.nl.conftest import Chat

    rt, client, aid = queued
    c = Chat(client, f"r9-con1-show-{lang}")
    c.say(CON1[lang]["yes"], lang=lang)
    c.say("1", lang=lang)
    c.say(CON1[lang]["yes"], lang=lang)
    assert _status(rt, aid) == "PENDING"
    c.say(CON1[lang]["approve_word"], lang=lang)
    assert _status(rt, aid) == "APPROVED"


def test_con1_a_list_offered_to_the_word_approve_still_decides_on_a_bare_pick(queued) -> None:
    from tests.nl.conftest import Chat

    rt, client, aid = queued
    c = Chat(client, "r9-con1-approve-word")
    c.say("thanks")
    listed = c.say("approve")
    assert listed["clarification"] and _status(rt, aid) == "PENDING"
    c.say("1")
    assert _status(rt, aid) == "APPROVED"


def test_con1_approve_with_the_id_decides_after_a_list_offered_to_yes(queued) -> None:
    from tests.nl.conftest import Chat

    rt, client, aid = queued
    c = Chat(client, "r9-con1-approve-id")
    c.say("go ahead")
    c.say(f"approve {aid}")
    assert _status(rt, aid) == "APPROVED"
