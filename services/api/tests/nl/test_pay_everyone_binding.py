""""Can I pay everyone?" saves the plan it shows (PAY-1).

The plan-binding rule: the owner's "go ahead" runs exactly the operations the reply showed. The reply's plan clause is worded from the
plan that is saved (the very pending plan "fund the cash gap" would store), never from Home's own recommendation, which can be a
different plan on the same books (the demo's day 34)."""

from __future__ import annotations

import json
import re

import pytest

from app.nl.sessions import SESSIONS
from tests.nl.conftest import Chat
from tests.nl.test_alerts_opener import _day34

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
def test_day_34_shows_the_saved_plan_and_go_ahead_runs_exactly_it(client, rt, lang, text, go) -> None:
    _day34(client, rt)
    chat = Chat(client, f"pb-{lang}")
    r = chat.say(text, lang=lang)
    reply, pending = r["reply"], SESSIONS.get(f"pb-{lang}").pending_plan
    assert r["awaiting_confirmation"] is True and pending is not None and pending.quoted_cost_fen is not None
    legs = _saved_legs(f"pb-{lang}")
    assert [k for k, _ in legs] == ["DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING", "SUBMIT_INVOICE_FOR_FINANCING"]
    assert _yuan(pending.quoted_cost_fen) in reply, reply  # the cost shown is the saved plan's cost
    clause = reply[reply.find(_yuan(pending.quoted_cost_fen)):]  # from the plan's cost on: the legs
    for _kind, amount in legs:  # every saved leg is shown, with its amount
        assert _yuan(amount) in clause, (_yuan(amount), reply)
    assert "¥1,782.19" not in reply and "¥200,000 of" not in reply and "200,000 of" not in reply  # Home's other plan is not shown
    assert r["operations"] == []
    before = len(rt.store.operations())
    done = chat.say(go, lang=lang)
    ran = _logged(rt, before)
    assert [(k, a) for k, a, _s in ran][: len(ran)] == legs[: len(ran)]  # what ran is a prefix of what was shown, in order
    assert ran and ran[0][0] == "DRAW_FACILITY" and ran[0][1] == 279_000
    assert done["intent"] == "FUND_GAP"
    assert not any(s == "EXECUTED" and a == 20_000_000 for _k, a, s in ran)


def test_day_34_clause_names_the_approval_the_saved_plan_needs(client, rt) -> None:
    _day34(client, rt)
    reply = Chat(client, "pb-ap").say(EN)["reply"]
    assert "costs ¥1,702.20 and needs your approval" in reply
    assert re.search(r"draw ¥2,790 on the credit line", reply) and "¥80,000" in reply and "¥117,210" in reply


def test_golden_books_keep_their_plan_clause(client, rt) -> None:
    reply = Chat(client, "pb-g").say(EN)["reply"]
    assert "FLOW's plan covers it for ¥3,113.93: draw ¥150,000 on the credit line today (¥841.64) and finance ¥255,000" in reply
    assert _saved_legs("pb-g") == [("DRAW_FACILITY", 15_000_000), ("SUBMIT_INVOICE_FOR_FINANCING", 25_500_000)]


def test_a_plan_that_cannot_be_worded_from_the_saved_one_is_not_offered(client, rt, monkeypatch) -> None:
    """The guard: when the reply's plan differs from the saved one and the saved one cannot be shown, nothing is saved and no
    go-ahead is promised."""
    from app.nl import ask

    _day34(client, rt)
    monkeypatch.setattr(ask, "_saved_clause", lambda *a, **k: None)
    r = Chat(client, "pb-guard").say(EN)
    assert r["awaiting_confirmation"] is False and SESSIONS.get("pb-guard").pending_plan is None
    assert "go ahead" not in r["reply"] and "reply 'go ahead'" not in r["reply"]
    assert r["operations"] == []
