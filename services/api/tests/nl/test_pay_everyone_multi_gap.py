""""Can I pay everyone?" answers when the books hold more than one cash gap (PAY-2): it used to be an HTTP 500, because the "all gaps"
index (99) was built past the 1..20 limit `Slots` validates."""

from __future__ import annotations

import json

import pytest

from app.nl.sessions import SESSIONS
from tests.nl.conftest import Chat

EN, ZH = "Can I pay everyone this month?", "我能付清所有账单吗"


def _logged(rt, since: int) -> list[tuple[str, int, str]]:
    out = []
    for x in rt.store.operations()[since:]:
        p = json.loads(x.payload_json)
        out.append((x.kind, p.get("amount_fen") or p.get("advance_fen"), json.loads(x.result_json)["status"]))
    return out


def _saved_legs(sid: str) -> list[tuple[str, int]]:
    pending = SESSIONS.get(sid).pending_plan
    assert pending is not None
    return [(o.kind, getattr(o, "advance_fen", None) or o.amount_fen) for o in pending.ops]


def _yuan(fen: int) -> str:
    whole, cents = divmod(fen, 100)
    return f"¥{whole:,}" + (f".{cents:02d}" if cents else "")


@pytest.mark.parametrize(("lang", "text", "go"), [("en", EN, "go ahead"), ("zh", ZH, "执行")])
def test_more_than_one_cash_gap_gets_an_answer_not_a_500(client, rt, lang, text, go) -> None:
    s = rt.store.get_state()
    rt.store.put_state(s.model_copy(update={"cash_fen": s.cash_fen - 300_000_00}))
    chat = Chat(client, f"pm-{lang}")
    r = chat.say(text, lang=lang)  # Chat.say asserts a 200
    assert r["intent"] == "ASK_BOOKS" and r["reply"].strip()
    assert r["operations"] == []
    pending = SESSIONS.get(f"pm-{lang}").pending_plan
    if r["awaiting_confirmation"]:  # a plan was saved: it is the one shown, and go-ahead runs it
        assert pending is not None and pending.quoted_cost_fen is not None and _yuan(pending.quoted_cost_fen) in r["reply"]
        before = len(rt.store.operations())
        chat.say(go, lang=lang)
        assert [(k, a) for k, a, _s in _logged(rt, before)][:1] == _saved_legs(f"pm-{lang}")[:1]
    else:
        assert pending is None
