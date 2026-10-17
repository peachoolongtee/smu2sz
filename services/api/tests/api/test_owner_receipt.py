"""The owner records a payment themself (feature inventory, gap 1): the existing RECEIVE_PAYMENT operation through POST /operations,
answered with the owner's words for what it did (`receipt`, `app.api.receipt_words`). The executor decides; the words only say it."""

from __future__ import annotations

from app.api.runtime import get_runtime


def _receipt(client, amount_fen: int, key: str, *, rid: str = "RCV-A", lang: str = "en", ref: str | None = None, owner: bool = True) -> dict:
    body = {"kind": "RECEIVE_PAYMENT", "op_id": key, "idempotency_key": key, "mandate_version": 1, "requested_by": "OWNER",
            "receivable_id": rid, "amount_fen": amount_fen, **({"bank_reference": ref} if ref else {})}
    headers = None if owner else {"X-Owner-Token": "", "X-Agent-Key": "demo-agent-key"}
    r = client.post(f"/operations?lang={lang}", json=body, **({"headers": headers} if headers else {}))
    assert r.status_code == 200, r.text
    return r.json()


def _row(rid: str = "RCV-A"):
    return next(r for r in get_runtime().store.get_state().receivables if r.id == rid)


def test_a_full_payment_settles_the_invoice_and_says_so(client) -> None:
    out = _receipt(client, 42_000_000, "own-full", ref="BANK-STMT-7")
    assert out["result"]["status"] == "EXECUTED" and out["result"]["tier"] == "TIER_1"  # the owner's receipt is a fact, never queued
    w = out["receipt"]
    assert w["status"] == "EXECUTED" and w["tone"] == "ok"
    assert w["headline_text"] == "Recorded: ¥420,000.00 received from Foshan Home Retail Co."
    assert w["lines"] == ["The ¥420,000.00 invoice to Foshan Home Retail Co. is paid in full.", "Your cash is now ¥820,000.00."]
    assert w["reconciliation_text"] == "Amount equals what the accepted terms say is owed."
    assert _row().status == "SETTLED"
    # the reconciliation lists it with the bank's reference
    rows = client.get("/reconciliation").json()["reconciliation"]["receipts"]
    assert [(x["op_id"], x["bank_reference"], x["status"]) for x in rows] == [("own-full", "BANK-STMT-7", "MATCHED")]


def test_a_partial_payment_leaves_the_rest_open(client) -> None:
    w = _receipt(client, 10_000_000, "own-part")["receipt"]
    assert w["lines"][0] == "¥320,000.00 is still open on the ¥420,000.00 invoice to Foshan Home Retail Co., due in 32 days."
    assert w["reconciliation_text"].startswith("Partial payment: short by ¥320,000.00")
    assert _row().status == "OPEN" and _row().outstanding_fen == 32_000_000
    zh = _receipt(client, 2_000_000, "own-part-zh", lang="zh")["receipt"]
    assert zh["headline_text"] == "已记录：收到Foshan Home Retail Co.的 ¥20,000.00。"
    assert zh["lines"][0] == "Foshan Home Retail Co. 的 ¥420,000.00 发票仍有 ¥300,000.00 未付，32 天后到期。"
    assert zh["reconciliation_text"].startswith("部分付款")


def test_a_payment_on_a_financed_invoice_repays_the_lender_first(client) -> None:
    fin = {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-1", "idempotency_key": "fin-1", "mandate_version": 1,
           "requested_by": "OWNER", "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": 20_000_000}
    assert client.post("/operations", json=fin).json()["result"]["status"] == "EXECUTED"
    # before the advance lands the payment is the owner's, and the advance still lands
    early = _receipt(client, 5_000_000, "own-early")["receipt"]
    assert early["lines"][0] == ("The advance of ¥200,000.00 you asked Invoice financing (onboarded platform) for on this invoice has not "
                                 "landed yet; it still lands in 3 days. This payment is yours.")
    assert client.post("/clock/advance", json={"to_day": 10}).status_code == 200
    part = _receipt(client, 10_000_000, "own-fin-1")["receipt"]
    assert part["lines"][:2] == [
        "All ¥100,000.00 went to Invoice financing (onboarded platform) first, against the advance on this invoice; none of it reached your cash.",
        "¥100,000.00 of the advance is still owed to Invoice financing (onboarded platform); the invoice stays financed.",
    ]
    rest = _receipt(client, 20_000_000, "own-fin-2")["receipt"]
    assert rest["lines"][0].startswith("¥101,782.19 went to Invoice financing (onboarded platform) first, to repay the advance on this invoice; "
                                       "¥98,217.81 reached your cash.")
    assert rest["lines"][1] == "The advance from Invoice financing (onboarded platform) on this invoice is repaid in full."
    assert _row().status == "OPEN" and _row().outstanding_fen == 7_000_000


def test_a_refused_payment_books_nothing_and_says_why(client) -> None:
    before = get_runtime().store.get_state()
    w = _receipt(client, 50_000_000, "own-too-much")["receipt"]
    assert w["status"] == "REFUSED" and w["tone"] == "bad" and w["headline_text"] == "Nothing was recorded."
    assert w["lines"] == ["¥500,000.00 is more than the ¥420,000.00 still open on the ¥420,000.00 invoice to Foshan Home Retail Co.; "
                          "enter at most ¥420,000.00."]
    assert get_runtime().store.get_state().cash_fen == before.cash_fen
    _receipt(client, 42_000_000, "own-all")
    paid = _receipt(client, 100, "own-again", lang="zh")["receipt"]
    assert paid["lines"] == ["Foshan Home Retail Co. 的 ¥420,000.00 发票已全部付清。"]


def test_the_same_submit_twice_is_one_payment(client) -> None:
    assert _receipt(client, 10_000_000, "own-once")["receipt"]["status"] == "EXECUTED"
    again = _receipt(client, 10_000_000, "own-once")["receipt"]
    assert again["status"] == "DUPLICATE" and again["headline_text"] == "This payment was already recorded; nothing changed."
    assert _row().outstanding_fen == 32_000_000


def test_without_the_owner_sign_in_it_is_the_agent_report_and_waits(client) -> None:
    """An unauthenticated owner claim is the agent's report (Tier 2); it gets no owner words and books nothing until approved."""
    out = _receipt(client, 10_000_000, "own-claim", owner=False)
    assert out["result"]["status"] == "PENDING_APPROVAL" and "receipt" not in out
    assert _row().outstanding_fen == 42_000_000
