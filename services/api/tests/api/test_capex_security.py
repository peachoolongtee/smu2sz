"""The buy side's merge-blocking security findings (docs/capex_handover.md; the Security Lead's register).

CAPEX-1  a schedule can book money coming IN (a rate above 100%, a negative share): refused at derivation, in owner words
         (en and zh), and again by the executor.
CAPEX-3  the same contract (same doc_hash) commits twice: the second is refused.
CAPEX-2  the agent authors a commit / the owner approves without seeing the schedule.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.capex.schedule import PaymentSchedule, ScheduleResult, Timeline, derive_schedule, schedule_hash
from app.compiler import Compiler
from app.compiler.contract import contract_document
from app.compiler.rules import RulesBackend
from app.domain.fixtures import capex_contract_fixture_bytes
from app.domain.models import CompiledContract, ContractField, DocumentKind, FlowKind
from app.operations.log import read_entries

ANCHOR = "2026-10-01"
HEAD = ("Contract No. T-1. This Contract is made on 8 October 2026 between Alpha Machines Co., Ltd. (the \"Seller\") and "
        "Beta Works Co., Ltd. (the \"Buyer\").\n\n")
TIMELINE = {"signing_day": 20, "delivery_day": 60, "acceptance_day": 80}
AGENT = {"X-Agent-Key": "demo-agent-key"}

# the Security Lead's probes: payment terms alone, the retention is the whole of the contract's reading
RETAIN_150 = (HEAD + "The Contract Price is RMB 600,000.\n\nThe Contract Price is payable ninety (90) days after delivery."
              "\n\nThe Buyer shall retain 150% of the Contract Price as retention for twelve (12) months after acceptance.\n")
DISCOUNT_150 = (HEAD + "The Contract Price is RMB 600,000.\n\n100% of the Contract Price is payable upon delivery of the "
                "Equipment.\n\nIf the Buyer pays early, within five (5) days of delivery, the Seller grants a discount of "
                "150% of that payment.\n")


def read(text: str) -> CompiledContract:
    doc = contract_document(text, DocumentKind.CAPEX_CONTRACT, "VENDOR-T")
    return Compiler([RulesBackend()]).compile_contract(doc, DocumentKind.CAPEX_CONTRACT)


def fixture() -> CompiledContract:
    return read(capex_contract_fixture_bytes("GZPM_EQUIPMENT_PURCHASE")[1].decode("utf-8"))


def derive(c: CompiledContract, today: int = 0, **timeline: int) -> ScheduleResult:
    return derive_schedule(c, Timeline(**timeline), anchor_iso=ANCHOR, today=today)


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")


@pytest.fixture
def rt(client):
    from app.api.runtime import get_runtime

    return get_runtime()


@pytest.fixture
def agent(client):  # type: ignore[no-untyped-def]
    from app.main import app

    return TestClient(app, headers=AGENT)


def _upload(client, text: str | None = None) -> dict:  # type: ignore[no-untyped-def]
    body = ({"fixture_id": "GZPM_EQUIPMENT_PURCHASE"} if text is None else
            {"kind": "CAPEX_CONTRACT", "counterparty_id": "VENDOR-T", "text": text, "title": "Test contract"})
    r = client.post("/documents", json=body)
    assert r.status_code == 200, r.text
    d = r.json()["document"]
    c = client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]})
    assert c.status_code == 200, c.text
    return c.json()["document"]


def _owner_op(doc: dict, schedule_hash_: str, over: dict | None = None, key: str = "t") -> dict:
    body = {"kind": "COMMIT_PURCHASE", "op_id": f"sec-{key}", "idempotency_key": f"sec:{key}", "mandate_version": 1,
            "requested_by": "OWNER", "document_id": doc["id"], "doc_hash": doc["doc_hash"],
            "schedule_hash": schedule_hash_, "amount_fen": 60_000_000, **TIMELINE}
    body.update(over or {})
    return body


def _capex_flows(rt) -> list[tuple[str, int, int]]:  # type: ignore[no-untyped-def]
    return [(f.id, f.day, f.amount_fen) for f in rt.store.get_state().flows if f.kind == FlowKind.CAPEX]


def _last_entry(rt):  # type: ignore[no-untyped-def]
    return read_entries(rt.store.operations())[0][-1]


# ---------------------------------------------------------------- CAPEX-1: derivation


def test_a_retention_above_100_percent_is_not_derivable_and_says_so_in_both_languages():
    r = derive(read(RETAIN_150), delivery_day=30, acceptance_day=40)
    assert not r.derivable and r.schedule is None
    assert len(r.reasons) == 1 and "150.00%" in r.reasons[0] and "more than 100%" in r.reasons[0]
    assert len(r.reasons_zh) == 1 and "150.00%" in r.reasons_zh[0] and "超过" in r.reasons_zh[0]


def test_an_early_payment_discount_of_150_percent_is_not_derivable():
    c = read(DISCOUNT_150)
    assert any(t.field == ContractField.EARLY_PAYMENT and t.rate_bp == 15_000 for t in c.terms)  # the probe reads as 150%
    r = derive(c, delivery_day=30)
    assert not r.derivable and r.schedule is None
    assert "early-payment discount" in r.reasons[0] and "150.00%" in r.reasons[0] and r.reasons_zh and "提前付款折扣" in r.reasons_zh[0]


def test_a_discount_of_all_of_the_payment_is_not_derivable_either():
    r = derive(read(DISCOUNT_150.replace("150%", "100%")), delivery_day=30)
    assert not r.derivable and "early-payment discount" in r.reasons[0]


def _with_rate(c: CompiledContract, field: ContractField, n: int, bp: int) -> CompiledContract:
    seen = -1
    terms = []
    for t in c.terms:
        if t.field == field:
            seen += 1
            if seen == n:
                t = t.model_copy(update={"rate_bp": bp})
        terms.append(t)
    return c.model_copy(update={"terms": terms})


def test_a_negative_share_is_not_derivable_even_when_the_shares_add_up():
    c = fixture()  # 30% + 60% + 10% retention
    c = _with_rate(c, ContractField.MILESTONE, 0, -1_000)
    c = _with_rate(c, ContractField.MILESTONE, 1, 6_000)
    c = _with_rate(c, ContractField.RETENTION, 0, 5_000)  # -10% + 60% + 50%: adds up to 100%, one leg is money coming in
    r = derive(c, delivery_day=60, acceptance_day=80)
    assert not r.derivable and r.schedule is None
    assert "-10.00%" in r.reasons[0] and "not between 0% and 100%" in r.reasons[0] and r.reasons_zh


def test_a_milestone_share_above_100_percent_is_not_derivable():
    c = _with_rate(_with_rate(fixture(), ContractField.MILESTONE, 0, 13_000), ContractField.MILESTONE, 1, -3_000)
    assert not derive(c, delivery_day=60, acceptance_day=80).derivable


def test_the_demo_contract_still_derives():
    r = derive(fixture(), delivery_day=60, acceptance_day=80)
    assert r.derivable and [p.amount_fen for p in r.schedule.payments] == [18_000_000, 36_000_000, 6_000_000]  # type: ignore[union-attr]


# ---------------------------------------------------------------- CAPEX-1: the routes and the executor


@pytest.mark.parametrize("text", [RETAIN_150, DISCOUNT_150], ids=["retention-150", "discount-150"])
def test_the_routes_refuse_a_schedule_that_books_money_in(client, on, rt, text):
    doc = _upload(client, text)
    ev = client.post(f"/capex/contracts/{doc['id']}/evaluate", json={"timeline": TIMELINE}).json()
    assert ev["schedule"]["derivable"] is False and ev["schedule"]["schedule"] is None
    r = client.post(f"/capex/contracts/{doc['id']}/commit",
                    json={"timeline": TIMELINE, "schedule_hash": "a" * 64})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "NO_SCHEDULE"
    assert "150.00%" in r.json()["detail"]["message"] and "150.00%" in r.json()["detail"]["message_zh"]
    assert _capex_flows(rt) == []


@pytest.mark.parametrize("text", [RETAIN_150, DISCOUNT_150], ids=["retention-150", "discount-150"])
def test_a_forged_commit_of_such_a_contract_is_refused_by_the_executor_and_the_books_stay(client, on, rt, text):
    doc = _upload(client, text)
    before = rt.store.get_state()
    queued = client.post("/operations", json=_owner_op(doc, "b" * 64, {"amount_fen": 60_000_000})).json()["result"]
    assert queued["status"] == "PENDING_APPROVAL"
    out = client.post(f"/approvals/{queued['approval_id']}", json={"decision": "APPROVE"}).json()["result"]
    assert out["status"] == "REFUSED" and "No payment schedule follows" in out["message"], out
    assert rt.store.get_state().flows == before.flows and _capex_flows(rt) == []
    entry = _last_entry(rt)
    assert entry.kind == "COMMIT_PURCHASE" and entry.result.status.value == "REFUSED"  # the log records the refusal


def test_the_executor_refuses_a_payment_that_is_not_money_out_even_if_a_schedule_were_derived(client, on, rt, monkeypatch):
    """Defence in depth: whatever the derivation returns, a leg of zero or less is never booked."""
    import app.capex.schedule as schedule_module

    doc = _upload(client)
    real = schedule_module.derive_schedule(
        rt.store.get_contract_record(doc["id"]).contract,  # type: ignore[union-attr]
        Timeline(**TIMELINE), anchor_iso=rt.store.get_state().as_of, today=rt.store.get_state().as_of_day).schedule
    assert real is not None
    legs = [real.payments[0].model_copy(update={"amount_fen": -18_000_000}),
            real.payments[1].model_copy(update={"amount_fen": 72_000_000}), real.payments[2]]
    forged = PaymentSchedule(price_fen=real.price_fen, payments=legs, schedule_hash=schedule_hash(real.price_fen, legs))
    monkeypatch.setattr(schedule_module, "derive_schedule",
                        lambda *a, **k: ScheduleResult(derivable=True, schedule=forged))
    before = rt.store.get_state()
    queued = client.post("/operations", json=_owner_op(doc, forged.schedule_hash)).json()["result"]
    assert queued["status"] == "PENDING_APPROVAL"
    out = client.post(f"/approvals/{queued['approval_id']}", json={"decision": "APPROVE"}).json()["result"]
    assert out["status"] == "REFUSED", out
    assert out["violations"][0]["code"] == "PRECONDITION_FAILED" and out["violations"][0]["inputs"]["refusal"] == "PAYMENT_NOT_POSITIVE"
    assert rt.store.get_state().flows == before.flows and _capex_flows(rt) == []
    entry = _last_entry(rt)
    assert entry.kind == "COMMIT_PURCHASE" and entry.result.status.value == "REFUSED"


# ---------------------------------------------------------------- CAPEX-3: one contract, one purchase


def _commit_and_approve(client, doc: dict) -> dict:  # type: ignore[no-untyped-def]
    ev = client.post(f"/capex/contracts/{doc['id']}/evaluate", json={"timeline": TIMELINE}).json()
    queued = client.post(f"/capex/contracts/{doc['id']}/commit",
                         json={"timeline": TIMELINE, "schedule_hash": ev["schedule"]["schedule"]["schedule_hash"]})
    assert queued.status_code == 200, queued.text
    return client.post(f"/approvals/{queued.json()['approval_id']}", json={"decision": "APPROVE"}).json()["result"]


def test_the_same_contract_uploaded_twice_commits_once(client, on, rt):
    first, second = _upload(client), _upload(client)
    assert first["id"] != second["id"] and first["doc_hash"] == second["doc_hash"]
    queued = []
    for d in (first, second):  # both are queued before either is approved: the queue cannot tell them apart
        ev = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE}).json()
        r = client.post(f"/capex/contracts/{d['id']}/commit",
                        json={"timeline": TIMELINE, "schedule_hash": ev["schedule"]["schedule"]["schedule_hash"]})
        assert r.status_code == 200, r.text
        queued.append(r.json()["approval_id"])
    a = client.post(f"/approvals/{queued[0]}", json={"decision": "APPROVE"}).json()["result"]
    b = client.post(f"/approvals/{queued[1]}", json={"decision": "APPROVE"}).json()["result"]
    assert a["status"] == "EXECUTED"
    assert b["status"] == "REFUSED" and b["violations"][0]["inputs"]["refusal"] == "CONTRACT_ALREADY_COMMITTED", b
    assert "already committed" in b["message"]
    flows = _capex_flows(rt)
    assert len(flows) == 3 and {f[0].split(":")[1] for f in flows} == {first["id"]}  # one schedule on the books
    assert sum(f[2] for f in flows) == -60_000_000
    entry = _last_entry(rt)
    assert entry.kind == "COMMIT_PURCHASE" and entry.result.status.value == "REFUSED"


def test_the_same_contract_reference_with_the_same_vendor_is_one_purchase_even_if_the_text_differs(client, on, rt):
    text = capex_contract_fixture_bytes("GZPM_EQUIPMENT_PURCHASE")[1].decode("utf-8")
    first = _upload(client)
    # same vendor and number, but not the same bytes
    reworded = client.post("/documents", json={"kind": "CAPEX_CONTRACT", "counterparty_id": "VENDOR-GZPM",
                                               "text": text + "\n\n9.1 This copy was re-typed for the file.\n"}).json()["document"]
    reworded = client.post(f"/documents/{reworded['id']}/confirm", json={"doc_hash": reworded["doc_hash"]}).json()["document"]
    assert reworded["doc_hash"] != first["doc_hash"]
    assert _commit_and_approve(client, first)["status"] == "EXECUTED"
    out = _commit_and_approve(client, reworded)
    assert out["status"] == "REFUSED" and out["violations"][0]["inputs"]["refusal"] == "CONTRACT_ALREADY_COMMITTED"
    assert len(_capex_flows(rt)) == 3


def test_a_different_contract_with_the_same_vendor_still_commits(client, on, rt):
    text = capex_contract_fixture_bytes("GZPM_EQUIPMENT_PURCHASE")[1].decode("utf-8")
    first = _upload(client)
    other = client.post("/documents", json={"kind": "CAPEX_CONTRACT", "counterparty_id": "VENDOR-GZPM",
                                            "text": text.replace("GZPM-2026-114", "GZPM-2026-201")}).json()["document"]
    other = client.post(f"/documents/{other['id']}/confirm", json={"doc_hash": other["doc_hash"]}).json()["document"]
    assert _commit_and_approve(client, first)["status"] == "EXECUTED"
    assert _commit_and_approve(client, other)["status"] == "EXECUTED"
    assert len(_capex_flows(rt)) == 6


# ---------------------------------------------------------------- CAPEX-2 (b): only the owner authors a commit


def test_the_agent_key_cannot_queue_a_commit_through_the_operations_route(client, agent, on, rt):
    doc = _upload(client)
    ev = client.post(f"/capex/contracts/{doc['id']}/evaluate", json={"timeline": TIMELINE}).json()
    sh = ev["schedule"]["schedule"]["schedule_hash"]
    for who in ("AGENT", "OWNER"):  # an owner claim without the owner's token is the agent's
        r = agent.post("/operations", json=_owner_op(doc, sh, {"requested_by": who}, key=who)).json()["result"]
        assert r["status"] == "REFUSED" and r["approval_id"] is None
        v = r["violations"][0]
        assert v["code"] == "INSUFFICIENT_AUTHORITY" and v["inputs"]["refusal"] == "PURCHASE_OWNER_ONLY"
    assert rt.store.approvals() == [] and _capex_flows(rt) == []
    assert _last_entry(rt).result.status.value == "REFUSED"  # the log records it
    assert any(e.kind.value == "PRIVILEGE_ESCALATION" for e in rt.store.security_events())  # and so does the security record


def test_the_agent_key_cannot_use_the_owner_only_commit_route(client, agent, on, rt):
    doc = _upload(client)
    ev = client.post(f"/capex/contracts/{doc['id']}/evaluate", json={"timeline": TIMELINE}).json()
    r = agent.post(f"/capex/contracts/{doc['id']}/commit",
                   json={"timeline": TIMELINE, "schedule_hash": ev["schedule"]["schedule"]["schedule_hash"]})
    assert r.status_code in (401, 403) and rt.store.approvals() == []


def test_the_owners_route_queues_the_commit_as_the_owner(client, on, rt):
    doc = _upload(client)
    ev = client.post(f"/capex/contracts/{doc['id']}/evaluate", json={"timeline": TIMELINE}).json()
    r = client.post(f"/capex/contracts/{doc['id']}/commit",
                    json={"timeline": TIMELINE, "schedule_hash": ev["schedule"]["schedule"]["schedule_hash"]}).json()
    assert r["status"] == "PENDING_APPROVAL"
    assert client.get("/approvals/queue").json()["approvals"][0]["operation"]["requested_by"] == "OWNER"


def test_the_executor_refuses_an_agent_authored_commit_that_was_already_in_the_queue(client, on, rt):
    """Defence in depth: even an agent-authored operation that reached the queue some other way (an older queue, a direct
    store write) books nothing when the owner approves it."""
    import json

    doc = _upload(client)
    ev = client.post(f"/capex/contracts/{doc['id']}/evaluate", json={"timeline": TIMELINE}).json()
    op = _owner_op(doc, ev["schedule"]["schedule"]["schedule_hash"], {"requested_by": "AGENT", "day": rt.day})
    aid = rt.store.add_approval(json.dumps(op, sort_keys=True), "forged into the queue")
    out = client.post(f"/approvals/{aid}", json={"decision": "APPROVE"}).json()["result"]
    assert out["status"] == "REFUSED" and out["violations"][0]["inputs"]["refusal"] == "PURCHASE_OWNER_ONLY", out
    assert _capex_flows(rt) == []


# ---------------------------------------------------------------- CAPEX-2 (a): the card carries the schedule


def _queued_row(client, lang: str = "en", early: bool = False) -> dict:  # type: ignore[no-untyped-def]
    doc = _upload(client)
    ev = client.post(f"/capex/contracts/{doc['id']}/evaluate", json={"timeline": TIMELINE}).json()
    sh = ev["early_pay_schedule"]["schedule_hash"] if early else ev["schedule"]["schedule"]["schedule_hash"]
    r = client.post(f"/capex/contracts/{doc['id']}/commit", json={"timeline": TIMELINE, "schedule_hash": sh, "take_early_pay": early})
    assert r.status_code == 200, r.text
    return next(a for a in client.get(f"/approvals/queue?lang={lang}").json()["approvals"] if a["id"] == r.json()["approval_id"])


def test_the_approval_row_shows_the_vendor_document_payments_early_pay_choice_and_total(client, on):
    row = _queued_row(client)
    assert row["schedule_title"] == "What you are committing to" and row["schedule_note"] is None
    rows = {r["label"]: r["value_text"] for r in row["schedule_rows"]}
    assert rows["Vendor"] == "Guangzhou Precision Machinery Co., Ltd."
    assert rows["Contract"] == "Equipment purchase contract GZPM-2026-114"
    assert rows["Payment 1"].startswith("¥180,000.00, ") and rows["Payment 2"].startswith("¥360,000.00, ")
    assert rows["Payment 3"].startswith("¥60,000.00, ") and "(retention)" in rows["Payment 3"]
    assert rows["Early payment"].startswith("Not taken")
    assert rows["Total you will pay"] == "¥600,000.00"
    assert [r["label"] for r in row["schedule_rows"]][-1] == "Total you will pay"


def test_the_early_payment_choice_and_the_zh_words_are_the_servers(client, on):
    row = _queued_row(client, lang="zh", early=True)
    rows = {r["label"]: r["value_text"] for r in row["schedule_rows"]}
    assert row["schedule_title"] == "您将承诺的内容" and rows["供应商"] == "Guangzhou Precision Machinery Co., Ltd."
    assert rows["提前付款"].startswith("选择提前付款") and "¥7,200.00" in rows["提前付款"]
    assert rows["您将支付的总额"] == "¥592,800.00" and "第 1 笔付款" in rows


# ---------------------------------------------------------------- CAPEX-4: the vendor is not the business itself


def test_a_vendor_named_as_the_business_itself_is_not_registered_or_committed(client, on, rt):
    text = capex_contract_fixture_bytes("GZPM_EQUIPMENT_PURCHASE")[1].decode("utf-8")
    text = text.replace("Guangzhou Precision Machinery Co., Ltd., a company", "Lingnan Homeware Manufacturing Co., Ltd., a company")
    d = client.post("/documents", json={"kind": "CAPEX_CONTRACT", "counterparty_id": "VENDOR-SELF", "text": text}).json()["document"]
    d = client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]}).json()["document"]
    out = _commit_and_approve(client, d)
    assert out["status"] == "REFUSED" and out["violations"][0]["inputs"]["refusal"] == "VENDOR_IS_OWN_BUSINESS", out
    assert _capex_flows(rt) == [] and not any(c.id == "VENDOR-SELF" for c in rt.store.get_state().counterparties)
