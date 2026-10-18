"""Ask FLOW answers a live stress test found wrong or missing (18 Oct 2026), on the golden demo books, in English and Chinese.

Every figure asserted here is read back from the engine or the books (never typed in), and every question is asked through POST /nl
so the routing (rules.py, ask.py) is under test as well as the wording.
"""

from __future__ import annotations

import re

import pytest

from app.api.presentation import whole
from app.nl.answers import question_ids
from app.nl.answers.answers import W, op_words
from app.nl.answers.metrics import Reading
from tests.nl.conftest import OWNER, Chat

CJK = re.compile(r"[一-鿿]")


def say(client, text: str, n: int = 0) -> dict:
    return Chat(client, f"rule-answers-{abs(hash(text))}-{n}").say(text)


def no_ids(reply: str) -> None:
    assert not re.search(r"RCV-|FAC-|BUYER-|BANK-|PLATFORM-|APR-|SIGN_PERSONAL|OPEN_BOOKS|ADD_CUSTOMER", reply), reply


# ---------------------------------------------------------------- the audit log (item 5)

AUDIT_EN = ["Is the audit log intact?", "Can I trust the log?"]
AUDIT_ZH = ["审计日志完整吗？", "审计链校验通过吗？"]
REFUSED_EN = ["Has anything been refused or blocked?", "Were any operations refused?"]
REFUSED_ZH = ["有没有被拒绝或拦截的操作？", "有操作被拦下来吗？"]


def log_some_operations(client) -> None:
    """One operation that ran (the clock moved) and one refused (a Tier-3 request, which also raises a security event)."""
    assert client.post("/clock/advance", json={"to_day": 1}, headers=OWNER).status_code == 200
    Chat(client, "audit-setup").say("sign a personal guarantee for the loan")


@pytest.mark.parametrize("text", AUDIT_EN + AUDIT_ZH)
def test_the_audit_question_names_each_operation_and_keeps_the_chain_check(client, rt, text: str) -> None:
    log_some_operations(client)
    zh = bool(CJK.search(text))
    reply = say(client, text)["reply"]
    assert "one other operation" not in reply and "另一项操作" not in reply
    assert (CJK.search(reply) is not None) == zh, reply
    no_ids(reply)
    assert ("哈希链校验通过" if zh else "hash chain verifies") in reply
    assert ("将日期向前推进" if zh else "moved the clock forward") in reply  # the operation that ran, by name
    assert ("签署个人担保" if zh else "signing a personal guarantee") in reply  # the one refused, by name
    assert (re.search(r"被拒绝 1 项", reply) and re.search(r"待您审批 0 项", reply) and re.search(r"安全事件 1 起", reply)) if zh else (
        "1 refused" in reply and "0 waiting for your approval" in reply and "one security event" in reply), reply


@pytest.mark.parametrize("text", REFUSED_EN + REFUSED_ZH)
def test_the_refused_question_leads_with_the_refusal_and_still_names_everything(client, rt, text: str) -> None:
    log_some_operations(client)
    zh = bool(CJK.search(text))
    reply = say(client, text)["reply"]
    assert reply.startswith("有：1 项操作被拒绝" if zh else "Yes: one operation was refused"), reply
    assert ("签署个人担保" if zh else "signing a personal guarantee") in reply
    assert ("哈希链校验通过" if zh else "hash chain verifies") in reply
    assert "one other operation" not in reply


@pytest.mark.parametrize("text", [REFUSED_EN[0], REFUSED_ZH[0]])
def test_nothing_refused_says_so_on_a_fresh_book(client, rt, text: str) -> None:
    reply = say(client, text)["reply"]
    assert reply.startswith("没有操作被拒绝或拦截" if CJK.search(text) else "Nothing has been refused or blocked"), reply


def test_an_operation_kind_without_a_verb_is_named_by_its_owner_words(rt) -> None:
    for lang, expected in (("en", "books opened"), ("zh", "账簿已开立")):
        w = W(Reading.of(type("C", (), {"store": rt.store, "day": rt.day, "owner_key_hex": rt.owner_key_hex})()), lang)
        assert op_words(w, "OPEN_BOOKS", 0, None) == expected
    w = W(Reading.of(type("C", (), {"store": rt.store, "day": rt.day, "owner_key_hex": rt.owner_key_hex})()), "en")
    assert op_words(w, "NOT_A_KIND", 0, None) == "ran one other operation"


def test_the_beyond_top30_questions_are_not_among_the_top_30() -> None:
    for qid in ("ACT-04", "ACT-05", "FUN-07", "CUS-09", "CUS-04"):
        assert qid not in question_ids()


# ---------------------------------------------------------------- the biggest customer does not pay (item 1), stops ordering (item 2)


def forecast_without(rt, buyer_id: str, *, orders_only: bool = False) -> dict:
    """The conservative forecast of a copy of the books without the customer's money, projected here with the engine."""
    from app.books import current_books
    from app.domain.models import Mode
    from app.financial import project

    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    keep = [x for x in state.receivables if orders_only or x.counterparty_id != buyer_id]
    copy = state.model_copy(update={"receivables": keep, "recurring_invoices": [x for x in state.recurring_invoices
                                                                                 if x.counterparty_id != buyer_id]})
    b = current_books(copy, rt.store.commitments())
    days = [d for d in project(b.state, b.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen).days
            if d.day >= state.as_of_day]
    low = min(days, key=lambda d: (d.closing_fen, d.day))
    return {"reserve": mandate.min_cash_fen,
            "breach": next((d.day for d in days if d.closing_fen < mandate.min_cash_fen), None),
            "zero": next((d.day for d in days if d.closing_fen < 0), None), "low": low.closing_fen, "low_day": low.day}


def foshan_id(rt) -> str:
    return next(c.id for c in rt.store.get_state().counterparties if c.name.startswith("Foshan"))


LOSS_EN = ["If my biggest customer doesn't pay, how long can we last?", "could I survive losing my biggest customer?",
           "What if Foshan doesn't pay us at all, how long do we last?"]
LOSS_ZH = ["最大的客户如果不付款，我们能撑多久？", "如果佛山不付款，我们还能撑多久？"]


@pytest.mark.parametrize("text", LOSS_EN + LOSS_ZH)
def test_the_biggest_customer_not_paying_is_answered_on_a_forecast_without_its_money(client, rt, text: str) -> None:
    f = forecast_without(rt, foshan_id(rt))
    base = forecast_without(rt, "nobody")
    assert f["low"] != base["low"] and f["zero"] is not None  # the scenario is not today's forecast
    zh = bool(CJK.search(text))
    before = len(rt.store.operations())
    resp = say(client, text)
    reply = resp["reply"]
    assert not reply.startswith(("12 days to your reserve", "距离跌破储备线还有")) and "accounts for 100%" not in reply[:30]
    assert (CJK.search(reply) is not None) == zh, reply
    for figure in (whole(f["reserve"]), whole(f["low"]), whole(base["low"]), whole(rt.store.get_state().receivables[0].face_fen)):
        assert figure in reply, (figure, reply)
    day = (lambda n: f"第 {n} 天") if zh else (lambda n: f"day {n}")
    assert day(f["breach"]) in reply and day(f["zero"]) in reply and day(f["low_day"]) in reply, reply
    assert ("没有更改任何内容" if zh else "nothing was changed") in reply
    assert len(rt.store.operations()) == before
    no_ids(reply)


def test_losing_the_customer_leaves_the_stored_books_untouched(client, rt) -> None:
    state = rt.store.get_state().model_dump_json()
    say(client, LOSS_EN[0])
    assert rt.store.get_state().model_dump_json() == state


@pytest.mark.parametrize(("text", "zh"), [("What happens to cash if Dongguan stops ordering?", False), ("东莞如果不再下单，现金会怎样？", True)])
def test_a_customer_with_no_invoices_stopping_orders_changes_nothing_and_says_so(client, rt, text: str, zh: bool) -> None:
    dongguan = next(c.id for c in rt.store.get_state().counterparties if c.name.startswith("Dongguan"))
    state = rt.store.get_state()
    assert not [x for x in state.receivables if x.counterparty_id == dongguan]
    assert not [x for x in state.recurring_invoices if x.counterparty_id == dongguan]
    base = forecast_without(rt, "nobody")
    reply = say(client, text)["reply"]
    assert "Which change should I test" not in reply and "哪项更改" not in reply
    assert (CJK.search(reply) is not None) == zh, reply
    assert ("没有未结发票，也没有定期开票" if zh else "no open invoice and no recurring invoicing") in reply
    assert ("预测也不会变化" if zh else "the forecast does not change") in reply
    assert whole(base["low"]) in reply
    assert "0%" in reply


@pytest.mark.parametrize(("text", "zh"), [("What happens to cash if Foshan stops ordering?", False), ("佛山如果不再下单，现金会怎样？", True)])
def test_stopping_orders_takes_out_the_recurring_invoicing_but_not_the_open_invoice(client, rt, text: str, zh: bool) -> None:
    f = forecast_without(rt, foshan_id(rt), orders_only=True)
    reply = say(client, text)["reply"]
    assert whole(f["low"]) in reply and whole(rt.store.get_state().recurring_invoices[0].face_fen) in reply
    assert ("仍会到期" if zh else "stays due") in reply


# ---------------------------------------------------------------- days sales outstanding (item 4)


@pytest.mark.parametrize(("text", "zh"), [("What is our DSO?", False), ("我们的应收账款周转天数是多少？", True),
                                           ("How long do customers take to pay us?", False), ("客户平均多久付款？", True)])
def test_dso_is_computed_from_receivables_and_recurring_invoicing(client, rt, text: str, zh: bool) -> None:
    state = rt.store.get_state()
    owed = sum(x.outstanding_fen for x in state.receivables if x.status != "SETTLED")
    ri = state.recurring_invoices[0]
    dso = round(owed / (ri.face_fen / ri.every_days))
    reply = say(client, text)["reply"]
    assert "cannot answer" not in reply and "暂时还不能" not in reply
    assert (CJK.search(reply) is not None) == zh, reply
    assert reply.startswith(f"{dso} 天" if zh else f"{dso} days"), reply
    assert whole(owed) in reply and whole(ri.face_fen) in reply and whole(ri.face_fen // ri.every_days) in reply
    assert ("计算方法：应收账款除以每日定期开票额" if zh else "Method: receivables divided by daily recurring invoicing") in reply
    assert ("没有收款历史" if zh else "no receipt history") in reply  # the honest limit of the figure
    assert (f"账期是 {ri.terms_days} 天" if zh else f"{ri.terms_days}-day terms") in reply
    no_ids(reply)


def test_without_regular_invoicing_the_dso_answer_names_what_is_missing(client, rt) -> None:
    rt.store.put_state(rt.store.get_state().model_copy(update={"recurring_invoices": []}))
    for text, zh in (("What is our DSO?", False), ("我们的应收账款周转天数是多少？", True)):
        reply = say(client, text, 1)["reply"]
        assert ("无法给出应收账款周转天数" if zh else "I cannot give a DSO") in reply, reply
        assert ("没有定期开票或销售历史" if zh else "no recurring invoicing or sales history") in reply


# ---------------------------------------------------------------- borrowing against the Foshan invoice (item 3)


def engine_facts(rt) -> dict:
    """The invoice, the invoice-financing line and its menu row, as the engine holds them (never typed in here)."""
    from app.funding import menu_view

    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    foshan = next(c for c in state.counterparties if c.name.startswith("Foshan"))
    inv = next(x for x in state.receivables if x.counterparty_id == foshan.id and x.status == "OPEN")
    fac = next(f for f in state.facilities if f.kind.value == "INVOICE_FINANCING")
    row = next(m for m in menu_view(state, mandate) if m.facility_id == fac.id)
    advance = min(fac.limit_fen - fac.drawn_fen, inv.outstanding_fen * fac.advance_rate_bp // 10_000)
    return {"invoice": inv, "fac": fac, "row": row, "advance": advance}


@pytest.mark.parametrize(("text", "zh"), [("Can we borrow against the Foshan invoice?", False), ("佛山那张发票能拿去融资吗？", True),
                                           ("Can we get an advance on the Foshan invoice?", False)])
def test_borrowing_against_the_foshan_invoice_is_answered_from_the_funding_menu(client, rt, text: str, zh: bool) -> None:
    f = engine_facts(rt)
    before = len(rt.store.operations())
    resp = say(client, text)
    reply = resp["reply"]
    assert "I can't do that" not in reply and "做不了" not in reply
    assert (CJK.search(reply) is not None) == zh, reply
    assert whole(f["advance"]) in reply and whole(f["invoice"].outstanding_fen) in reply
    assert f"{f['fac'].advance_rate_bp // 100}%" in reply and whole(f["fac"].limit_fen) in reply
    assert f["row"].all_in_display in reply and f"{f['row'].time_to_cash_days}" in reply
    assert ("没有提交，也没有提款" if zh else "nothing was submitted or drawn") in reply
    assert len(rt.store.operations()) == before and not resp["operations"]  # a read: nothing drawn, nothing submitted
    no_ids(reply)


@pytest.mark.parametrize(("text", "zh"), [("Can we borrow against the Dongguan invoice?", False), ("东莞那张发票能拿去融资吗？", True)])
def test_a_customer_without_an_open_invoice_has_nothing_to_borrow_against(client, rt, text: str, zh: bool) -> None:
    reply = say(client, text)["reply"]
    assert reply.startswith("不能" if zh else "No:"), reply
    assert ("没有可用于融资的未结发票" if zh else "no open invoice to borrow against") in reply


def test_pledging_an_invoice_is_still_refused(client, rt) -> None:
    resp = say(client, "Can we pledge the Foshan invoice as collateral?")
    assert any(o["status"] == "REFUSED" for o in resp["operations"]), resp["reply"]
