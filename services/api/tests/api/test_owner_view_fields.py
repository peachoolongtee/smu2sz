"""The owner's screens need server-formatted strings (INVARIANT 13): obligation display fields everywhere an
obligation is serialised, the autonomy proof and the annualised cost of every early-pay discount."""

from __future__ import annotations

from app.domain.money import fmt_pct

EX01 = "EX01_PACKAGE"
CLEAN = "Deduct 0.6% and we'll settle the open ¥420,000 invoice early."
NO_AMOUNT = "Deduct 0.6% and we'll settle the open invoice early."


def _doc(text: str) -> dict:
    return {"doc_id": "t1", "channel": "chat", "sender_id": "BUYER-1", "received_day": 0, "text": text}


def _evaluate_text(client, text: str) -> dict:
    oid = client.post("/offers", json={"documents": [_doc(text)], "counterparty_id": "BUYER-1"}).json()["offer"]["offer_id"]
    return client.post(f"/offers/{oid}/evaluate", json={}).json()


def _evaluate_fixture(client, fx: str = EX01) -> dict:
    oid = client.post("/offers", json={"fixture_id": fx}).json()["offer"]["offer_id"]
    return client.post(f"/offers/{oid}/evaluate", json={"fixture_id": fx}).json()


def _walk(x):
    """Every obligation-shaped dict inside a payload."""
    if isinstance(x, dict):
        if {"type", "base", "contingency"} <= set(x):
            yield x
        for v in x.values():
            yield from _walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from _walk(v)


def _assert_displayed(ob: dict) -> None:
    if ob.get("rate_bp") is not None:
        assert ob["rate_display"].endswith("%"), ob
    if ob.get("amount_fen") is not None:
        assert ob["amount_display"].startswith("¥"), ob
    if ob["base"].get("amount_fen") is not None:
        assert ob["base"]["amount_display"].startswith("¥"), ob


# ---------------------------------------------------------------- part 1: obligation display strings


def test_post_offers_obligations_carry_display_strings(client):
    offer = client.post("/offers", json={"fixture_id": EX01}).json()["offer"]
    obs = list(_walk(offer))
    assert obs and any(o["rate_bp"] is not None for o in obs)
    for o in obs:
        _assert_displayed(o)
    assert offer["obligations"][0]["rate_display"] == "1.20%"
    assert offer["obligations"][0]["base"]["amount_display"] == "¥420,000.00"


def test_ledger_commitment_obligations_carry_display_strings(client):
    oid = client.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": EX01})
    assert client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()["outcome"] == "DEAL"
    commitments = client.get("/ledger").json()["commitments"]
    obs = list(_walk(commitments))
    assert obs
    for o in obs:
        _assert_displayed(o)
    assert any(o["rate_display"] == "0.85%" and o["base"]["amount_display"] == "¥260,000.00" for o in obs)


def test_evaluate_bound_and_counter_obligations_carry_display_strings(client):
    v = _evaluate_fixture(client)
    obs = list(_walk(v["bound_obligations"])) + list(_walk(v["counters"]))
    assert obs
    for o in obs:
        _assert_displayed(o)


# ---------------------------------------------------------------- part 4: annualised cost beside every discount


def test_evaluate_ex01_annualises_the_discount_and_counter_a_beside_the_funding_sources(client):
    v = _evaluate_fixture(client)
    by_id = {a["obligation_id"]: a for a in v["annualised"]}
    leg = by_id[v["bound_obligations"][0]["id"]]
    assert leg["receivable_id"] == "RCV-A" and leg["discount_display"] == "1.20%" and leg["days_early"] == 30
    from fractions import Fraction

    d = Fraction(120, 10_000)
    assert leg["annual_rate_display"] == fmt_pct(d / (1 - d) * 365 / 30)
    counter_a = next(c for c in v["counters"] if c["label"] == "Option A")
    a = by_id[counter_a["obligations"][0]["id"]]
    assert (a["discount_display"], a["days_early"], a["annual_rate_display"]) == ("0.85%", 30, "10.43%")
    assert a["formula"] == "d/(1−d) × 365/days_early = 0.85%/(1 − 0.85%) × 365/30 = 10.4303%"
    # compare_to: the committed sources, with the strings the funding menu rows show
    menu = client.post("/router/plan").json()["menu"]
    shown = {row["facility"]["name"]: row["cost_display"] for row in menu if row["committed"]}
    got = {c["label"]: c["annual_rate_display"] for c in a["compare_to"]}
    assert got and all(shown[label] == rate for label, rate in got.items())
    assert "6.40%" in got.values() and "10.84%" in got.values()
    assert leg["compare_to"] == a["compare_to"]


def test_counter_text_carries_no_annualised_figure(client):
    v = _evaluate_fixture(client)
    assert v["counters"]
    for c in v["counters"]:
        low = c["text"].lower()
        for needle in ("10.43", "10.84", "6.40", "annual", "a year", "per year", "apr"):
            assert needle not in low, (needle, c["text"])
    annual = {a["annual_rate_display"] for a in v["annualised"]}
    assert annual and not any(rate in c["text"] for c in v["counters"] for rate in annual)


# ---------------------------------------------------------------- part 3: the autonomy proof


def test_clean_whole_invoice_early_pay_is_proven_autonomous(client):
    v = _evaluate_text(client, CLEAN)
    assert (v["outcome"], v["required_tier"]) == ("ACCEPT", "TIER_1")
    au = v["autonomy"]
    assert au["eligible"] is True and au["accepted_alone"] is True and au["whole_invoice"] is True
    assert au["gaps"] == []
    assert len(au["covered"]) == 1
    assert au["covered"][0].startswith("early payment of ¥420,000.00 of RCV-A at 0.60%")
    assert au["notes"] == []
    assert [a["discount_display"] for a in v["annualised"]] == ["0.60%"]


def test_unproven_autonomy_lists_the_gaps_the_summary_reports(client):
    v = _evaluate_text(client, NO_AMOUNT)
    assert v["outcome"] == "NEEDS_OWNER_APPROVAL"
    au = v["autonomy"]
    assert au["accepted_alone"] is False and au["gaps"]
    assert "autonomy not proven (" + "; ".join(au["gaps"]) + ")" in v["summary"]
    assert au["whole_invoice"] is False


def test_whole_invoice_is_null_without_an_early_pay_leg(client):
    v = _evaluate_text(client, "A quarter percent back on next quarter's orders, please.")
    assert v["autonomy"]["whole_invoice"] is None and v["autonomy"]["accepted_alone"] is False
    assert v["annualised"] == []
    assert len(v["autonomy"]["covered"]) == len(v["bound_obligations"])
