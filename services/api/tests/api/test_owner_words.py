"""The owner's words on the verdict view (wayfinder #32): each concession value carries its reading before its
equation. The sentences wrap figures the engine produced (the value, the per-invoice cost, the invoice count the
formula states); nothing is priced here."""

from __future__ import annotations

from tests.nl import conftest as nl_conftest
from tests.nl.conftest import OWNER

rt = nl_conftest.rt
client = nl_conftest.client


def _eval(client, fx: str) -> dict:
    oid = client.post("/offers", json={"fixture_id": fx}, headers=OWNER).json()["offer"]["offer_id"]
    return client.post(f"/offers/{oid}/evaluate", json={"fixture_id": fx}, headers=OWNER).json()


def test_each_concession_value_reads_as_a_sentence_before_its_formula(client, rt):
    v = _eval(client, "EX01_PACKAGE")
    by_type = {o["id"]: o["type"] for o in v["bound_obligations"]}
    words = {by_type[cv["obligation_id"]]: cv["interpretation"] for cv in v["concession_values"]}
    assert words["TERMS_EXTENSION"] == ("60-day terms add 15 days of financing to 13 expected invoices, about ¥1,871.30 each "
                                        "at your cheapest committed source: ¥24,326.92 over 12 months.")
    assert words["CONTINGENT_REBATE"] == "A 1.00% rebate on ¥400,000.00 of purchases, counted at its maximum: ¥4,000.00."
    assert words["IMMEDIATE_DISCOUNT"].startswith("Settled in cash now, so it is not a forward concession")
    # the equation is still there, after the reading
    ext = next(cv for cv in v["concession_values"] if by_type[cv["obligation_id"]] == "TERMS_EXTENSION")
    assert ext["formula"].startswith("Σ over 13 invoices") and ext["value_display"] == "¥24,326.92"
