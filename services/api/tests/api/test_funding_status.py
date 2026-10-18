"""SEC-28 (reporting): after a send, the reply says what each funding leg and the accept actually did. A leg that waits for the
owner or is refused is never reported as funded. Execution order and atomicity are unchanged (disclosed)."""

from __future__ import annotations

import pytest

from app.api import decide
from app.api.funding_report import funding_status
from app.domain.models import OperationResult, OperationStatus, Tier
from app.operations.executor import Executor
from tests.alerts.test_act import _day34

EX01 = "EX01_PACKAGE"
FUNDING_KINDS = ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING")
QUEUED = "Queued for owner approval (APR-TEST): rate 18.00% a year is above the 12.00% limit."
REFUSED = "Refused: the facility has no headroom for this amount."


def _shown(client) -> str:
    oid = client.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": EX01})
    return oid


def _force(monkeypatch, status_for: dict[str, OperationStatus], leg: int | None = None) -> None:
    """The executor's answer for the given kinds replaced by a queued or refused result (the operation is not run): what such a leg
    looks like to the reply. `leg` limits it to that funding leg (0-based, across the funding kinds)."""
    real = Executor.execute
    funding_seen = [0]

    def execute(self, op):
        want = status_for.get(op.kind)
        if op.kind in FUNDING_KINDS:
            index, funding_seen[0] = funding_seen[0], funding_seen[0] + 1
            if leg is not None and index != leg:
                want = None
        if want is None:
            return real(self, op)
        queued = want == OperationStatus.PENDING_APPROVAL
        return OperationResult(op_id=op.op_id, kind=op.kind, status=want, tier=Tier.TIER_2, message=QUEUED if queued else REFUSED,
                               approval_id="APR-TEST" if queued else None)

    monkeypatch.setattr(Executor, "execute", execute)  # the runtime builds a fresh executor on every read


def _send(client, lang: str = "en", profile: str = "cooperative") -> dict:
    r = client.post(f"/negotiate/{_shown(client)}?lang={lang}", json={"buyer_profile": profile})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("lang,funded", [("en", "the remaining gap is funded."), ("zh", "其余缺口已融资。")])
def test_all_legs_executed_says_funded(client, lang, funded):
    n = _send(client, lang)
    assert n["outcome"] == "DEAL" and n["funding_legs"], "the fixture's deal funds its gap with at least one leg"
    assert n["funding_status"] == "FUNDED" and n["accept_status"] == "EXECUTED"
    assert n["message_when"].endswith(funded)
    assert {leg["status"] for leg in n["funding_legs"]} == {"EXECUTED"}
    assert n["message"].endswith("; remaining gap funded.")


@pytest.mark.parametrize("lang,unfunded", [("en", "not funded until you approve"), ("zh", "在您批准之前")])
def test_a_leg_queued_for_approval_is_not_called_funded(client, monkeypatch, lang, unfunded):
    _force(monkeypatch, {k: OperationStatus.PENDING_APPROVAL for k in FUNDING_KINDS})
    n = _send(client, lang)
    assert n["funding_status"] == "WAITING_APPROVAL"
    assert {leg["status"] for leg in n["funding_legs"]} == {"PENDING_APPROVAL"}
    text = n["message_when"]
    assert unfunded in text and "gap is funded" not in text and "缺口已融资" not in text
    assert all(leg["text"] in text for leg in n["funding_legs"]), "every waiting leg is named"
    assert "not funded until you approve" in n["message"] and "remaining gap funded" not in n["message"]
    assert n["accept_status"] == "EXECUTED"


@pytest.mark.parametrize("lang,not_funded", [("en", "the remaining gap is not funded."), ("zh", "其余缺口未获融资。")])
def test_every_leg_refused_is_not_funded_and_says_why(client, monkeypatch, lang, not_funded):
    _force(monkeypatch, {k: OperationStatus.REFUSED for k in FUNDING_KINDS})
    n = _send(client, lang)
    assert n["funding_status"] == "NOT_FUNDED"
    assert {leg["status"] for leg in n["funding_legs"]} == {"REFUSED"}
    assert not_funded in n["message_when"]
    assert all(leg["text"] in n["message_when"] for leg in n["funding_legs"])
    assert "gap is funded" not in n["message_when"] and "缺口已融资" not in n["message_when"]


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_one_leg_refused_beside_an_executed_leg_is_partly_funded(client, monkeypatch, lang):
    real = decide._ops_for_plan

    def two_legs(rt, actions, key):  # the plan's leg run, then a second leg the executor refused
        results, payloads = real(rt, actions, key)
        refused = {**results[0], "op_id": results[0]["op_id"] + "-b", "status": "REFUSED", "message": REFUSED, "approval_id": None}
        return results + [refused], payloads + [{**payloads[0], "op_id": refused["op_id"]}]

    monkeypatch.setattr(decide, "_ops_for_plan", two_legs)
    n = _send(client, lang)
    assert n["funding_status"] == "PARTLY_FUNDED"
    assert [leg["status"] for leg in n["funding_legs"]][-2:] == ["EXECUTED", "REFUSED"]
    assert ("not fully funded" if lang == "en" else "未能全部获得融资") in n["message_when"]
    assert all(leg["text"] in n["message_when"] for leg in n["funding_legs"]), "each leg's outcome is told"
    assert "gap is funded" not in n["message_when"] and "缺口已融资" not in n["message_when"]


def test_the_status_of_a_run_is_decided_by_its_legs():
    assert funding_status(["EXECUTED", "EXECUTED"]) == "FUNDED"
    assert funding_status(["EXECUTED", "PENDING_APPROVAL"]) == "WAITING_APPROVAL"
    assert funding_status(["REFUSED"]) == "NOT_FUNDED"
    assert funding_status(["EXECUTED", "REFUSED"]) == "PARTLY_FUNDED"
    assert funding_status(["PENDING_APPROVAL", "REFUSED"]) == "PARTLY_FUNDED"


@pytest.mark.parametrize("lang,waits,recorded", [("en", "waits for your approval", "agreement is recorded"),
                                                 ("zh", "正在等待您批准", "协议已记录")])
def test_an_accept_queued_for_approval_does_not_say_recorded(client, monkeypatch, lang, waits, recorded):
    _force(monkeypatch, {"ACCEPT_OFFER": OperationStatus.PENDING_APPROVAL})
    n = _send(client, lang)
    assert n["accept_status"] == "PENDING_APPROVAL"
    assert waits in n["message_when"] and recorded not in n["message_when"]
    assert "waits for owner approval" in n["message"] and "commitment recorded" not in n["message"]


@pytest.mark.parametrize("lang,head,recorded", [("en", "the agreement was not recorded", "agreement is recorded"),
                                                ("zh", "协议未被记录", "协议已记录")])
def test_a_refused_accept_says_it_was_not_recorded_and_why(client, monkeypatch, lang, head, recorded):
    _force(monkeypatch, {"ACCEPT_OFFER": OperationStatus.REFUSED})
    n = _send(client, lang)
    assert n["accept_status"] == "REFUSED"
    assert head in n["message_when"] and recorded not in n["message_when"]
    assert "was not recorded" in n["message"] and "commitment recorded" not in n["message"]
    assert "headroom" in n["message"], "the executor's reason is carried"


@pytest.mark.parametrize("lang,waits,funded", [("en", "not funded until you approve", "funded another way"),
                                               ("zh", "在您批准之前", "其他方式融资")])
def test_no_deal_with_a_queued_leg_is_not_called_funded(client, monkeypatch, lang, waits, funded):
    _force(monkeypatch, {k: OperationStatus.PENDING_APPROVAL for k in FUNDING_KINDS})
    n = _send(client, lang, profile="hard_line")
    assert n["outcome"] == "NO_DEAL", "the hard-line buyer refuses the fixture's counter"
    assert n["funding_legs"], "the refusal plan funds the near-term gap with at least one leg"
    assert n["funding_status"] == "WAITING_APPROVAL"
    assert waits in n["message_when"] and funded not in n["message_when"]
    assert "Debt Desk funds" not in n["message"]


@pytest.mark.parametrize("lang,lead,waits", [("en", "Not everything has run", "Waiting for your approval"),
                                             ("zh", "尚未全部执行", "等待您批准")])
def test_an_act_with_a_queued_step_states_each_steps_outcome(client, lang, lead, waits):
    breach, _face, _rid = _day34(client)  # day 34: the invoice financing exceeds the APR approval threshold, so it is queued
    body = client.post(f"/alerts/{breach['id']}/act?lang={lang}").json()
    assert body["pending_approval"] == 1 and body["run_status"] == "WAITING_APPROVAL"
    assert lead in body["message_when"] and waits in body["message_when"]
    assert "Every step ran" not in body["message_when"] and "所有步骤均已执行" not in body["message_when"]
    again = client.post(f"/alerts/{breach['id']}/act?lang={lang}").json()
    assert again["results"][0]["status"] == "DUPLICATE" and again["run_status"] == "WAITING_APPROVAL"


def test_an_act_with_a_refused_step_says_what_stopped(client, monkeypatch):
    breach, _face, _rid = _day34(client)
    _force(monkeypatch, {"SUBMIT_INVOICE_FOR_FINANCING": OperationStatus.REFUSED})
    body = client.post(f"/alerts/{breach['id']}/act").json()
    assert body["refused"] == 1 and body["run_status"] == "NOT_FUNDED"
    assert "the step was refused" in body["message_when"] and "Every step ran" not in body["message_when"]
    zh = client.post(f"/alerts/{breach['id']}/act?lang=zh").json()
    assert "该步骤被拒绝" in zh["message_when"]
