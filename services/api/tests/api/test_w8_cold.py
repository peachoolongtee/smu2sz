"""Wave 8 part C (map #65, ticket #77), the server-side items of the cold screenshot review: a cure that leaves the reserve short names
its worst point apart from today's gap (F3), a decided card reads in the past tense and a refused one says what to do next (F6), an
operation row has its kind in the owner's words (F9), an agreement card names what the owner signs and why only they can (F12). The
overdue-invoice-first sentence of F4 is pinned in tests/strategy/test_collections.py. Each form in both languages, with identical figures."""

from __future__ import annotations

from tests.api.test_time_semantics import _act, _queue, _queue_agreement, _queue_counter, _walk


def _both(client, path: str) -> tuple[dict, dict]:
    return client.get(path).json(), client.get(path, params={"lang": "zh"}).json()


# ---------------------------------------------------------------- F3: the worst point is not today


def test_the_partial_cure_names_the_worst_point_apart_from_todays_gap(client):
    _walk(client)
    _act(client)
    en, zh = [client.get("/approvals/queue", params={"lang": lang}).json()["approvals"][0] for lang in ("en", "zh")]
    want = "At its lowest point, in 8 days, cash would still be ¥300,000.00 below your minimum cash reserve; today it is ¥255,013.80 below."
    assert en["presentation"]["protects"] == en["presentation"]["residual"]["text"] == en["quote"]["after"] == want
    assert zh["presentation"]["protects"] == zh["quote"]["after"] == "在最低点（8 天后），现金仍比最低现金储备低 ¥300,000.00；今天低 ¥255,013.80。"
    assert client.get("/home").json()["next_action"]["after"] == want  # the home says the same
    assert en["presentation"]["residual"]["shortfall_today_display"] == zh["presentation"]["residual"]["shortfall_today_display"] == "¥255,013.80"
    assert en["presentation"]["residual"]["shortfall_display"] == zh["presentation"]["residual"]["shortfall_display"] == "¥300,000.00"
    # once approved the same card keeps the sentence (the quote was stored with the day of its lowest point)
    client.post(f"/approvals/{en['id']}", json={"decision": "APPROVE"})
    assert client.get("/approvals/queue").json()["approvals"][0]["presentation"]["protects"] == want


# ---------------------------------------------------------------- F6: a decided card in the past tense


def test_an_approved_a_declined_and_a_refused_card_read_in_the_past_tense(client):
    _walk(client)
    _act(client)
    row = _queue(client)[0]
    client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"})
    en, zh = [client.get("/approvals/queue", params={"lang": lang}).json()["approvals"][0]["presentation"] for lang in ("en", "zh")]
    assert en["headline"] == "You approved ¥155,013.80 of invoice financing." and zh["headline"] == "您已批准 ¥155,013.80 的发票融资。"
    assert en["next_step_text"] is None and en["next_step_href"] is None

    _walk(client)
    _act(client)
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "REJECT"})
    en, zh = [client.get("/approvals/queue", params={"lang": lang}).json()["approvals"][0]["presentation"] for lang in ("en", "zh")]
    assert en["headline"] == "You declined ¥155,013.80 of invoice financing." and zh["headline"] == "您已拒绝 ¥155,013.80 的发票融资。"

    _walk(client)
    _act(client)
    client.post("/clock/advance", json={"to_day": 91})
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "APPROVE"})
    en, zh = [client.get("/approvals/queue", params={"lang": lang}).json()["approvals"][0]["presentation"] for lang in ("en", "zh")]
    assert en["headline"] == "Approved, but it did not run: ¥155,013.80 of invoice financing."
    assert zh["headline"] == "已批准，但未能执行：¥155,013.80 的发票融资。"
    assert (en["next_step_text"], en["next_step_href"]) == ("Renew your signed limits, then ask FLOW to try again.", "/limits")
    assert (zh["next_step_text"], zh["next_step_href"]) == ("请续签您的授权，然后让 FLOW 重试。", "/limits")


def test_a_waiting_card_keeps_its_question_and_has_no_next_step(client):
    _walk(client)
    _act(client)
    en = client.get("/approvals/queue").json()["approvals"][0]["presentation"]
    assert en["headline"] == "Approve ¥155,013.80 of invoice financing?" and en["next_step_text"] is None


def test_the_signed_limits_are_named_in_words_not_as_a_mandate_version(client):
    from app.api.presentation import business_text
    from app.api.runtime import get_runtime

    state = get_runtime().store.get_state()

    def said(text: str, lang: str = "en") -> str | None:
        return business_text(state, text, 91, lang)

    assert said("Mandate v1 expired on day 90") == "Your signed limits (version 1) expired yesterday"
    assert said("Mandate v1 expires in 5 day(s)") == "Your signed limits (version 1) expire in 5 days"
    assert said("Mandate v2 has been revoked by the owner") == "Your signed limits (version 2) have been revoked by the owner"
    assert said("Mandate v1 expired on day 90", "zh") == "您签署的授权（第 1 版）已于昨天到期"


# ---------------------------------------------------------------- F9: the kind in the owner's words


def test_operation_rows_carry_their_kind_in_the_owners_words_and_keep_the_raw_kind(client):
    _walk(client, receipt="half")
    _act(client)
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "APPROVE"})
    en, zh = _both(client, "/ledger")
    kinds = {o["kind"]: (o["kind_text"]) for o in en["operations"]}
    # The demo opens on the owner's confirmation of the three demo documents (contract ingestion, brief 03).
    assert kinds == {"ACCEPT_OFFER": "Agreement recorded", "DRAW_FACILITY": "Credit line drawn", "ADVANCE_CLOCK": "Time passed",
                     "RECEIVE_PAYMENT": "Payment received", "SUBMIT_INVOICE_FOR_FINANCING": "Invoice financing requested",
                     "CONFIRM_DOCUMENT": "Document confirmed"}
    assert {o["kind"]: o["kind_text"] for o in zh["operations"]} == {
        "ACCEPT_OFFER": "协议已记录", "DRAW_FACILITY": "信用额度已提款", "ADVANCE_CLOCK": "时间已推进", "RECEIVE_PAYMENT": "已收到付款",
        "SUBMIT_INVOICE_FOR_FINANCING": "已申请发票融资", "CONFIRM_DOCUMENT": "文件已确认"}
    assert [o["kind"] for o in en["operations"]] == [o["kind"] for o in zh["operations"]]
    funding = next(r for r in client.get("/decisions").json()["decisions"] if r["family"] == "FUNDING")
    record = client.get(f"/decisions/{funding['id']}", params={"lang": "zh"}).json()
    assert [(o["kind"], o["kind_text"]) for o in record["operations"]] == [("SUBMIT_INVOICE_FOR_FINANCING", "已申请发票融资")]


def test_the_repayment_and_the_unknown_kind():
    from app.api.presentation import kind_text

    assert kind_text("REPAY_FACILITY", "en") == "Repayment" and kind_text("REPAY_FACILITY", "zh") == "还款"
    assert kind_text("SOMETHING_NEW", "en") == "Something new"


# ---------------------------------------------------------------- F12: the agreement card


def test_an_agreement_card_names_what_it_signs_and_why_it_is_the_owners(client):
    row = _queue_agreement(client)
    en = client.get("/approvals/queue").json()["approvals"][0]["presentation"]
    zh = client.get("/approvals/queue", params={"lang": "zh"}).json()["approvals"][0]["presentation"]
    assert row["presentation"]["approve_label"] == en["approve_label"] == "Approve the agreement (0.50% early-payment discount, about ¥2,100.00)"
    assert zh["approve_label"] == "批准该协议（0.50% 提前付款折扣，约 ¥2,100.00）"
    assert en["why_text"] == "This changes the terms with a buyer, which you keep for yourself."
    assert zh["why_text"] == "这会改变与买方的条款，这类决定由您自己保留。"
    assert "verdict" not in en["why_text"].lower()


def test_a_terms_only_agreement_says_its_terms(client):
    queued = _queue_counter(client, 1)  # Option B: 55-day terms with a price adjustment
    en = queued["row"]["presentation"]
    assert en["approve_label"] == "Approve the agreement (55-day terms)"
    zh = client.get("/approvals/queue", params={"lang": "zh"}).json()["approvals"][0]["presentation"]
    assert zh["approve_label"] == "批准该协议（55 天账期）"


def test_a_decided_agreement_is_in_the_past_tense_and_has_no_button_label(client):
    _queue_agreement(client)
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "APPROVE"})
    en = client.get("/approvals/queue").json()["approvals"][0]["presentation"]
    assert en["headline"] == "You approved the agreement with Foshan Home Retail Co." and en["approve_label"] is None
