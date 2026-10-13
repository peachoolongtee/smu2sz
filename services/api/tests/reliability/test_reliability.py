"""Buyer reliability (app.reliability, GET /reliability): what the agent learns about how each buyer pays, and the open
deals ranked by it. The demo prior is the imported history (fixtures/scenarios/golden_sme.payment_history.json); every
receipt from the bank feed and every promise from an accepted deal after that reinforces or weakens it. Advisory only:
reading it never changes the books, the log or a verdict."""

from __future__ import annotations

from app.domain.models import FinancialState
from app.domain.money import bp, post
from app.reliability import Evidence, Payment, learn, profiles
from tests.alerts.test_repay_alert import _receipt, deal
from tests.nl import conftest as nl_conftest

OWNER = nl_conftest.OWNER
rt = nl_conftest.rt  # the in-memory runtime and the app client of the chat tests
client = nl_conftest.client


def _buyers(client, **params) -> dict[str, dict]:
    r = client.get("/reliability", headers=OWNER, params=params)
    assert r.status_code == 200, r.text
    return {b["counterparty_id"]: b for b in r.json()["buyers"]}


def _offer(client, fx: str, evaluate: bool = True) -> str:
    oid = client.post("/offers", json={"fixture_id": fx}, headers=OWNER).json()["offer"]["offer_id"]
    if evaluate:
        client.post(f"/offers/{oid}/evaluate", json={"fixture_id": fx}, headers=OWNER)
    return oid


def test_day_zero_learns_from_the_imported_history(client, rt):
    b = _buyers(client)
    foshan, dongguan = b["BUYER-1"], b["BUYER-2"]
    assert (foshan["rank"], foshan["score"], foshan["grade"]) == (1, 90, "RELIABLE")
    assert (dongguan["rank"], dongguan["score"], dongguan["grade"]) == (2, 39, "RISKY")
    assert (foshan["invoices_learned"], dongguan["invoices_learned"]) == (10, 8)
    assert dongguan["agreed_terms_days"] == 30 and dongguan["effective_terms_days"] == 40
    assert dongguan["trend"] == "WORSENING" and dongguan["incidents"] == 1
    reasons = [x["text"] for x in dongguan["reasons"]]
    assert "Paid 2 of 8 invoices on time (within 3 days of the due day)." in reasons
    assert "Pays on average 10 days late: agreed 30-day terms, in practice about 40 days." in reasons
    # priced at the engine's marginal cost of funds (FAC-IF, 10.84%): ¥100,000 × 10.8417% × 10 / 365
    assert ("That delay costs you about ¥297.03 per ¥100,000 invoiced, at your cheapest committed funding "
            "(10.84% a year).") in reasons
    assert "85 days ago: paid an invoice in parts, the last part late." in reasons
    assert dongguan["formula"].endswith("= 39")
    # an average delay inside the grace is not worth a sentence
    assert not any("days late:" in x["text"] for x in foshan["reasons"])
    assert [h["invoice_id"] for h in dongguan["history"]][:2] == ["HIST-B2-08", "HIST-B2-07"]
    assert dongguan["history"][0]["words"] == "18 days late" and dongguan["history"][0]["source"] == "IMPORTED"


def test_reading_it_changes_nothing(client, rt):
    before = (rt.store.get_state().state_version, len(rt.store.operations()))
    _buyers(client)
    _buyers(client, lang="zh")
    assert (rt.store.get_state().state_version, len(rt.store.operations())) == before


def test_only_the_owner_reads_it(client, rt):
    assert client.get("/reliability").status_code in (401, 403)


def test_chinese_words(client, rt):
    b = _buyers(client, lang="zh")
    assert b["BUYER-2"]["grade_words"] == "经常拖欠"
    assert "平均逾期 10 天：约定账期 30 天，实际约 40 天。" in [x["text"] for x in b["BUYER-2"]["reasons"]]


def test_deals_are_ranked_by_how_the_buyer_pays(client, rt):
    ex08b = _offer(client, "EX08B_JOINT_BUYER2")
    ex01 = _offer(client, "EX01_PACKAGE")
    unread = _offer(client, "EX01B_REWORDED", evaluate=False)
    r = client.get("/reliability", headers=OWNER, params={"offer_id": [ex08b, ex01, unread, "OFF-NOPE"]}).json()
    deals = r["deals"]
    assert [d["counterparty_id"] for d in deals] == ["BUYER-1", "BUYER-1", "BUYER-2"]  # the unknown id is ignored
    # within one buyer, the deal the check can act on comes before the one never checked
    assert deals[0]["offer_id"] == ex01 and deals[0]["business_action"] == "counter"
    assert deals[1]["offer_id"] == unread and deals[1]["business_action"] is None
    assert deals[2]["offer_id"] == ex08b and deals[2]["business_action"] == "needs_owner"
    assert deals[0]["why"] == "Ranked first: Foshan Home Retail Co. is the most reliable payer among these deals."
    assert deals[1]["why"] == "Same buyer as a deal above; ranked by what the check recommends."
    assert deals[2]["why"] == ("Ranked below Foshan Home Retail Co.: often pays late, agreed 30-day terms but pays in "
                               "about 40, getting worse, 1 payment problem (score 39).")
    assert [d["rank"] for d in deals] == [1, 2, 3]


def test_a_receipt_from_the_bank_feed_reinforces_the_profile(client, rt):
    before = _buyers(client)["BUYER-1"]
    client.post("/clock/advance", json={"to_day": 32}, headers=OWNER)  # RCV-A is due on day 32
    _receipt(client, rt, "t-rel-on-time", "RCV-A", 42000000)
    after = _buyers(client)["BUYER-1"]
    assert after["invoices_learned"] == before["invoices_learned"] + 1
    assert after["score"] >= before["score"]
    first = after["history"][0]
    assert (first["invoice_id"], first["words"], first["source"]) == ("RCV-A", "on time", "BANK_FEED")
    assert "BANK_FEED" in after["sources"]


def test_an_overdue_invoice_then_a_late_payment_weakens_it(client, rt):
    before = _buyers(client)["BUYER-1"]["score"]
    client.post("/clock/advance", json={"to_day": 47}, headers=OWNER)  # 15 days past RCV-A's due day (32); the next invoice is due today
    overdue = _buyers(client)["BUYER-1"]
    assert overdue["overdue_now"] == 1 and overdue["score"] < before
    assert "An invoice of ¥420,000.00 is overdue now, 15 days past due." in [x["text"] for x in overdue["reasons"]]
    _receipt(client, rt, "t-rel-late", "RCV-A", 42000000)
    paid = _buyers(client)["BUYER-1"]
    assert paid["overdue_now"] == 0 and paid["score"] < before
    rcv = next(h for h in paid["history"] if h["invoice_id"] == "RCV-A")
    assert rcv["words"] == "15 days late" and rcv["source"] == "BANK_FEED"


def test_a_missed_promise_from_a_deal_counts_against(client, rt):
    ob = deal(client, rt)  # the accepted early payment on RCV-A
    before = _buyers(client)["BUYER-1"]["score"]
    client.post("/clock/advance", json={"to_day": ob.effective_day + 1}, headers=OWNER)
    b = _buyers(client)["BUYER-1"]
    assert b["incidents"] == 1 and b["score"] < before
    assert any("missed an early payment it promised in a deal" in x["text"] for x in b["reasons"])


def test_a_kept_promise_counts_for(client, rt):
    ob = deal(client, rt)
    client.post("/clock/advance", json={"to_day": ob.effective_day}, headers=OWNER)
    _receipt(client, rt, "t-rel-kept", ob.base.receivable_id,
             ob.base.amount_fen - post(bp(ob.rate_bp) * ob.base.amount_fen))
    b = _buyers(client)["BUYER-1"]
    assert b["promises_kept"] == 1 and b["incidents"] == 0
    assert "Kept its early-payment promise in an accepted deal once." in [x["text"] for x in b["reasons"]]


def test_provisioned_books_start_unrated(client, rt):
    state = rt.store.get_state()
    rt.store.put_state(state.model_copy(update={"scenario": None}))
    b = _buyers(client)
    assert all(x["grade"] == "UNRATED" and x["score"] is None and x["rank_score"] == 50 for x in b.values())


def test_the_rule_on_hand_made_evidence():
    def pay(i: int, late: int) -> Payment:
        return Payment(f"I{i}", "B", 100, 30, -100 + i * 10, -100 + i * 10 + late, "IMPORTED")

    steady = learn("B", Evidence(payments=[pay(i, 0) for i in range(5)]), today=0)
    late = learn("B", Evidence(payments=[pay(i, 20) for i in range(5)]), today=0)
    assert steady.grade == "RELIABLE" and late.grade == "RISKY" and steady.score > late.score  # type: ignore[operator]
    assert learn("B", Evidence(), today=0).grade == "UNRATED"
    worse = learn("B", Evidence(payments=[pay(i, 0) for i in range(4)] + [pay(i, 15) for i in range(4, 7)]), today=0)
    assert worse.trend == "WORSENING"


def test_without_a_permanent_source_the_delay_is_not_priced(client, rt):
    state: FinancialState = rt.store.get_state()
    rows = profiles(state.model_copy(update={"facilities": []}), rt.store.get_mandate(), rt.store, 0)
    assert [r["counterparty_id"] for r in rows] == ["BUYER-1", "BUYER-2"]
    assert not any("per ¥100,000" in x["text"] for r in rows for x in r["reasons"])
