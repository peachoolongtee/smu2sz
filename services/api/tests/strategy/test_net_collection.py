"""Net cash at collection (map #88, ticket #107): what an invoice leaves the owner on a day, after the lender, on the golden
books. The three financing states never mixed (ARRANGED today, RECEIVED after the cash lands, REPAID after the receipt), the
shortfall owed by the owner, what one more fee period adds, and the words in both languages."""

from __future__ import annotations

import pytest

from app.api.financing_words import financing_state_words
from app.domain.models import FundingLot
from app.domain.money import fmt_yuan, fmt_yuan_about
from app.financial import lots as funding_lots
from app.strategy.net import advance_lot, net_at_collection
from app.strategy.words import net_words

from .exposure_books import financed_golden, golden

FOSHAN = "Foshan Home Retail Co."


def _rcv(books, rid: str = "RCV-A"):
    return next(r for r in books.state.receivables if r.id == rid)


def _facility(books):
    return next(f for f in books.state.facilities if f.id == "FAC-IF")


def test_an_unfinanced_invoice_nets_its_whole_outstanding():
    books, _ = golden()
    net = net_at_collection(books.state, _rcv(books))
    assert (net.financing_state, net.advance_fen, net.charges_fen, net.claim_fen) == ("NONE", 0, 0, 0)
    assert (net.net_fen, net.owed_by_owner_fen, net.per_period_more_fen, net.on_day) == (42_000_000, 0, 0, 32)  # the due day
    assert net.face_fen == net.outstanding_fen == 42_000_000


def test_arranged_today_received_after_landing_repaid_after_the_receipt():
    arranged = financed_golden(False)
    net = net_at_collection(arranged.state, _rcv(arranged))
    assert (net.financing_state, net.arrival_day, net.advance_fen) == ("ARRANGED", 3, 25_500_000)
    received = financed_golden(True)
    net_r = net_at_collection(received.state, _rcv(received))
    assert (net_r.financing_state, net_r.arrival_day, net_r.advance_fen) == ("RECEIVED", -2, 25_500_000)
    # the charges are the facility's (advance_charges, whole fee periods from the day the cash landed), to the due day
    lot, f = received.state.lots[0], _facility(received)
    interest, fee, _ = funding_lots.advance_charges(f, lot, 32)
    assert net_r.charges_fen == interest + fee and net_r.claim_fen == 25_500_000 + interest + fee
    assert net_r.net_fen == 42_000_000 - net_r.claim_fen and net_r.owed_by_owner_fen == 0
    # the lot has not landed: the charges still run from its arrival day (day 3), so they are smaller than after landing on day -2
    assert net.charges_fen == sum(funding_lots.advance_charges(f, arranged.state.lots[0], 32)[:2]) < net_r.charges_fen
    # after the receipt the lot is gone and the books keep no trace on the invoice: the caller who read the log says so
    settled = received.state.model_copy(update={
        "receivables": [_rcv(received).model_copy(update={"status": "SETTLED", "settled_fen": 42_000_000, "advance_fen": 0,
                                                           "advance_facility_id": None})],
        "lots": [], "facilities": [x.model_copy(update={"drawn_fen": 0}) if x.id == "FAC-IF" else x for x in received.state.facilities]})
    done = net_at_collection(settled, settled.receivables[0], 32, financed_before=True)
    assert (done.financing_state, done.claim_fen, done.net_fen) == ("REPAID", 0, 0)
    assert net_at_collection(settled, settled.receivables[0], 32).financing_state == "NONE"  # nothing says it was financed


def test_a_receipt_that_does_not_cover_the_claim_is_owed_by_the_owner_and_the_net_is_never_negative():
    books = financed_golden(True, outstanding_fen=25_600_000)
    net = net_at_collection(books.state, _rcv(books), 62)  # 30 days after the due day
    assert net.claim_fen > 25_600_000
    assert (net.net_fen, net.owed_by_owner_fen) == (0, net.claim_fen - 25_600_000)
    # a fixed remainder (principal 0, nothing accrues) is the same amount whatever the day
    lot = FundingLot(id="LOT-IF", facility_id="FAC-IF", principal_fen=0, remaining_fen=300_000, request_day=-5, arrival_day=-2,
                     receivable_id="RCV-A", settled=True)
    fixed = books.state.model_copy(update={"lots": [lot]})
    for day in (32, 92):
        n = net_at_collection(fixed, _rcv(books), day)
        assert (n.charges_fen, n.claim_fen, n.per_period_more_fen) == (0, 300_000, 0)
        assert (n.net_fen, n.owed_by_owner_fen) == (25_300_000, 0)


def test_per_period_more_is_what_one_more_fee_period_adds():
    books = financed_golden(True)
    lot = books.state.lots[0]
    assert net_at_collection(books.state, _rcv(books)).period_days == 30
    for day in (32, 62, 92):  # a period turns over every 30 days: the charges rise by exactly it
        n = net_at_collection(books.state, _rcv(books), day)
        later = net_at_collection(books.state, _rcv(books), day + 30)
        assert later.charges_fen - n.charges_fen == n.per_period_more_fen > 0
    assert advance_lot(books.state, _rcv(books)) == lot


def test_the_default_day_is_the_due_day_and_the_function_is_deterministic_and_pure():
    books = financed_golden(True)
    before = books.state.model_dump_json()
    a = net_at_collection(books.state, _rcv(books))
    assert a == net_at_collection(books.state, _rcv(books), 32) and a.on_day == 32
    assert books.state.model_dump_json() == before


def test_the_words_in_english():
    received = financed_golden(True)
    net = net_at_collection(received.state, _rcv(received))
    w = net_words("en", net, buyer_name=FOSHAN, today=0, due_day=32)
    assert w["net_display"] == fmt_yuan(net.net_fen) and w["net_short"] == f"about {fmt_yuan_about(net.net_fen)}"
    assert w["condition_text"] == "if Foshan pays on the due day"
    assert w["repays_text"] == f"{fmt_yuan(net.claim_fen)} repays the financing received 34 days earlier, with its charges"
    assert w["financing_state_text"] == "Received"
    assert w["per_period_text"] == f"about {fmt_yuan_about(net.per_period_more_fen)} more for every 30 days late"
    assert w["owed_text"] is None
    arranged = financed_golden(False)
    wa = net_words("en", net_at_collection(arranged.state, _rcv(arranged)), buyer_name=FOSHAN, today=0, due_day=32)
    assert wa["repays_text"].endswith("repays the financing arranged, expected in 3 days, with its charges")
    assert wa["financing_state_text"] == "Arranged"
    plain = golden()[0]
    wn = net_words("en", net_at_collection(plain.state, _rcv(plain)), buyer_name=FOSHAN, today=0, due_day=32)
    assert (wn["repays_text"], wn["financing_state_text"], wn["per_period_text"]) == (None, None, None)
    short = financed_golden(True, outstanding_fen=25_600_000)
    ws = net_words("en", net_at_collection(short.state, _rcv(short), 62), buyer_name=FOSHAN, today=0, due_day=32)
    assert ws["owed_text"].startswith("The receipt falls about ¥") and "owed by you" in ws["owed_text"]
    assert net_words("en", net, buyer_name=FOSHAN, today=32, due_day=32)["condition_text"] == "if Foshan pays on the due day"
    later = net_at_collection(received.state, _rcv(received), 40)
    assert net_words("en", later, buyer_name=FOSHAN, today=0, due_day=32)["condition_text"] == "if Foshan pays in 40 days"


def test_the_words_in_chinese_carry_the_same_figures():
    received = financed_golden(True)
    net = net_at_collection(received.state, _rcv(received))
    en, zh = (net_words(lang, net, buyer_name=FOSHAN, today=0, due_day=32) for lang in ("en", "zh"))
    assert zh["net_display"] == en["net_display"]
    assert zh["condition_text"] == "如果 Foshan 在到期日付款" and zh["financing_state_text"] == "已到账"
    assert fmt_yuan(net.claim_fen) in zh["repays_text"] and "34 天前到账的融资及其费用" in zh["repays_text"]
    assert zh["net_short"] == f"约 {fmt_yuan_about(net.net_fen)}" and zh["per_period_text"].startswith("每晚 30 天")


@pytest.mark.parametrize(("lang", "words"), [("en", ("arranged", "received", "repaid")), ("zh", ("已安排", "已到账", "已还清"))])
def test_the_financing_state_words_by_the_lots_state_never_mixed(lang, words):
    arranged, received = financed_golden(False).state.lots[0], financed_golden(True).state.lots[0]
    cleared = received.model_copy(update={"remaining_fen": 0})
    got = [financing_state_words(lang, lot, 0) for lot in (arranged, received, cleared)]
    assert [g["state"] for g in got] == ["ARRANGED", "RECEIVED", "REPAID"]
    assert [g["word"] for g in got] == list(words)
    assert financing_state_words(lang, None, 0)["state"] == "REPAID"
    for g in got:  # a sentence names its own state's word only
        assert [w for w in words if w in g["text"]] == [g["word"]]
    assert "advanced" not in got[0]["text"]  # never the word advanced for an unlanded lot
    en = financing_state_words("en", arranged, 0)["text"]
    assert en == "financing arranged, expected in 3 days"
    assert financing_state_words("en", received, 0)["text"] == "financing received 2 days ago"
