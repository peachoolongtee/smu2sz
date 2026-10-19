"""Round eight (Security Lead review of dev 03215a20, 19 Oct): what the owner is told about a send's funding (SEC-28, reporting only).

FUND-1: a send whose gap plan has no legs (the router found no admissible plan) said the gap was funded: `funding_status([])` was FUNDED
and the reply read "the remaining gap is funded" / "the near-term gap is funded another way". A plan with no gap said the same.
FUND-3: the owner chat's "go ahead" on a no-deal send with no admissible plan said "NO DEAL, and there is no gap to cover." while the
verdict line on the same reply shows the reserve breach.
(FUND-2 is the web's send result: apps/web/components/deals/flow/send-result.test.tsx.)"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.funding_report import funding_status
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore
from tests.nl.conftest import build_app

EX01 = "EX01_PACKAGE"
OWNER = {"X-Owner-Token": "demo-owner-token"}
FUNDED_WORDS = ("gap is funded", "funded another way", "缺口已融资", "其他方式融资", "Debt Desk funds", "remaining gap funded")


@pytest.fixture
def client():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    reset_sessions()
    yield TestClient(build_app(), headers=OWNER)
    set_runtime(None)
    reset_sessions()


def _cap_lines() -> None:
    """Books whose committed lines are small (FAC-LINE and FAC-IF ¥50,000, no early pay): the router finds no admissible plan."""
    caps = {"FAC-LINE": 5_000_000, "FAC-IF": 5_000_000, "FAC-EARLYPAY": 0}
    store = get_runtime().store
    s = store.get_state()
    store.put_state(s.model_copy(update={"facilities": [f.model_copy(update={"limit_fen": caps.get(f.id, f.limit_fen)})
                                                        for f in s.facilities]}))


def _drain_lines() -> None:
    """Every facility's headroom gone after the evaluation (another user drew the lines): no admissible plan after the accept."""
    store = get_runtime().store
    s = store.get_state()
    store.put_state(s.model_copy(update={"facilities": [f.model_copy(update={"limit_fen": f.drawn_fen}) for f in s.facilities]}))


def _flush_cash() -> None:
    """Cash far above the reserve after the evaluation: the books need no funding either way."""
    store = get_runtime().store
    s = store.get_state()
    store.put_state(s.model_copy(update={"cash_fen": s.cash_fen + 10_000_000_000}))


def _send(client, profile: str, lang: str, after_eval=None) -> dict:
    oid = client.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": EX01})
    if after_eval is not None:
        after_eval()
    r = client.post(f"/negotiate/{oid}?lang={lang}", json={"buyer_profile": profile})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- FUND-1


def test_fund1_no_leg_ran_is_never_funded():
    assert funding_status([]) != "FUNDED"
    assert funding_status([], need_fen=1) == "NOT_FUNDED"
    assert funding_status([], need_fen=0) == "NOT_NEEDED"
    assert funding_status(["EXECUTED"], need_fen=1) == "FUNDED"


@pytest.mark.parametrize("lang,lead", [("en", "the near-term gap of ¥405,000 is not funded: no admissible plan on the funding menu"),
                                       ("zh", "近期缺口 ¥405,000 未获融资：融资菜单上没有可行的方案")])
def test_fund1_no_deal_with_no_admissible_plan_is_not_funded(client, lang, lead):
    _cap_lines()
    n = _send(client, "hard_line", lang)
    assert n["outcome"] == "NO_DEAL" and n["plan"]["admissible"] is False and not n["plan"]["actions"], n["plan"]
    assert n["funding_status"] == "NOT_FUNDED" and n["funding_legs"] == []
    assert lead in n["message_when"], n["message_when"]
    assert not any(w in n["message_when"] for w in FUNDED_WORDS), n["message_when"]
    assert "near-term gap is not funded: no admissible plan" in n["message"] and "Debt Desk funds" not in n["message"]


@pytest.mark.parametrize("lang,lead", [("en", "the remaining gap of ¥147,210 is not funded: no admissible plan on the funding menu"),
                                       ("zh", "其余缺口 ¥147,210 未获融资：融资菜单上没有可行的方案")])
def test_fund1_deal_with_no_admissible_plan_is_not_funded(client, lang, lead):
    n = _send(client, "cooperative", lang, after_eval=_drain_lines)
    assert n["outcome"] == "DEAL" and n["plan"]["admissible"] is False and not n["plan"]["actions"], n["plan"]
    assert n["funding_status"] == "NOT_FUNDED"
    assert lead in n["message_when"], n["message_when"]
    assert not any(w in n["message_when"] for w in FUNDED_WORDS), n["message_when"]
    assert "remaining gap is not funded: no admissible plan" in n["message"] and "remaining gap funded" not in n["message"]


@pytest.mark.parametrize("profile", ["hard_line", "cooperative"])
@pytest.mark.parametrize("lang,words", [("en", "; no funding is needed."), ("zh", "；无需融资。")])
def test_fund1_no_gap_says_no_funding_is_needed(client, profile, lang, words):
    n = _send(client, profile, lang, after_eval=_flush_cash)
    assert n["plan"]["need_fen"] == 0 and n["plan"]["admissible"] is True and not n["plan"]["actions"]
    assert n["funding_status"] == "NOT_NEEDED"
    assert n["message_when"].endswith(words), n["message_when"]
    assert not any(w in n["message_when"] for w in FUNDED_WORDS), n["message_when"]
    assert n["message"].endswith("; no funding needed.")


# ---------------------------------------------------------------- FUND-3


@pytest.mark.parametrize("mode", ["business", None])
@pytest.mark.parametrize("lang,yes,said", [("en", "go ahead", "The near-term gap of ¥405,000 is not funded: no admissible plan on the funding menu"),
                                           ("zh", "好，执行", "近期缺口 ¥405,000 未获融资：融资菜单上没有可行的方案")])
def test_fund3_go_ahead_with_no_admissible_plan_says_the_gap_is_not_funded(client, mode, lang, yes, said):
    _cap_lines()
    params = {"mode": mode} if mode else {}

    def say(text: str) -> dict:
        body = {"session_id": f"r8-{mode}-{lang}", "actor": "OWNER", "text": text, "lang": lang, "buyer_profile": "BUYER-1-HARDLINE"}
        r = client.post("/nl", params=params, json=body)
        assert r.status_code == 200, r.text
        return r.json()

    say("Evaluate EX01")
    reply = say(yes)["reply"]
    assert "no gap to cover" not in reply and "无资金缺口" not in reply, reply
    assert said in reply, reply
    assert ("NO DEAL" if lang == "en" else "未成交") in reply


# ---------------------------------------------------------------- FUND-5


@pytest.mark.parametrize("lang,yes,said,proposed", [
    ("en", "go ahead", "BUYER-1 refused. The near-term gap of ¥405,000 is not funded: no admissible plan on the funding menu",
     "the near-term gap of ¥405,000 stays unfunded"),
    ("zh", "好，执行", "近期缺口 ¥405,000 未获融资：融资菜单上没有可行的方案", "近期缺口 ¥405,000 仍未获融资")])
def test_fund5_early_settlement_with_no_admissible_fallback_says_the_gap_is_not_funded(client, lang, yes, said, proposed):
    """The early-settlement proposal said "If BUYER-1 refuses: no fallback needed" and the go-ahead "BUYER-1 refused, and there is
    no gap to fund." when the gap was open and no admissible plan covered it."""
    _cap_lines()

    def say(text: str) -> dict:
        body = {"session_id": f"r8-accel-{lang}", "actor": "OWNER", "text": text, "lang": lang, "buyer_profile": "BUYER-1-HARDLINE"}
        r = client.post("/nl", json=body)
        assert r.status_code == 200, r.text
        return r.json()

    plan = say("get Foshan to pay early" if lang == "en" else "让佛山提前付款")
    assert plan["intent"] == "ACCELERATE_RECEIPT", plan
    assert "no fallback needed" not in plan["reply"] and "无需后备" not in plan["reply"], plan["reply"]
    assert proposed in plan["reply"], plan["reply"]
    reply = say(yes)["reply"]
    assert "no gap to fund" not in reply and "无资金缺口" not in reply, reply
    assert said in reply, reply
