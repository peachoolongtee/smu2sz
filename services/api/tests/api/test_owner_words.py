"""The owner's words on the verdict view (wayfinder #32): each concession value carries its reading before its
equation. The sentences wrap figures the engine produced (the value, the per-invoice cost, the invoice count the
formula states); nothing is priced here."""

from __future__ import annotations

from app.api.presentation import concession_interpretation, operation_words
from app.domain.models import Contingency, ObligationType
from tests.nl import conftest as nl_conftest
from tests.nl.conftest import OWNER
from tests.verifier.conftest import bundle

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


def test_each_chart_event_has_short_words_for_its_annotation(client, rt):
    h = client.get("/home", headers=OWNER).json()
    events = [e for d in h["cash"]["series"] for e in d["events"]]
    receipt = next(e for e in events if e["kind"] == "RECEIPT")
    assert receipt["label_short"] == "Receipt from Foshan Home Retail Co." and receipt["label"].startswith("Receipt the ¥420,000.00 invoice")
    payroll = next(e for e in events if e["label"] == "Payroll")
    assert payroll["label_short"] == "Payroll"
    debt = next(e for e in events if e["label"].startswith("Debt service"))
    assert debt["label_short"] == "Debt service"
    zh = client.get("/home", params={"lang": "zh"}, headers=OWNER).json()
    assert any(e["label_short"] == "来自Foshan Home Retail Co.的收款" for d in zh["cash"]["series"] for e in d["events"])


# ---------------------------------------------------------------- the reading follows the value's sign and the contingency


def _ob(kind: ObligationType, **update):
    """An EX01 obligation of the given type with fields replaced: the reading reads only typed fields."""
    b = bundle("EX01_PACKAGE")  # the bound obligations and, for a price adjustment, Option B's own
    pool = [*b.bound_obligations, *(o for c in b.verdict.counters for o in c.obligations)]
    return next(o for o in pool if o.type == kind).model_copy(update=update)


_FORMULA = "Σ over 13 invoices (issued days 32 to 365; window days 0 to 364) of face × 15/365 × 10.84% = x"


def test_a_shortening_reads_as_financing_taken_off_and_a_saving_never_a_negative_extension():
    ob = _ob(ObligationType.TERMS_EXTENSION, days_delta=-15, target_terms_days=30)
    cv = {"value_fen": -1_621_795, "value_display": "−¥16,217.95", "formula": _FORMULA, "per_invoice_fen": -124_753,
          "per_invoice_display": "−¥1,247.53", "basis": "shortening (gain): committed marginal source"}
    en = concession_interpretation(cv, ob, "en")
    assert en == ("30-day terms take 15 days of financing off 13 expected invoices, about ¥1,247.53 each at your cheapest "
                  "committed source, saving ¥16,217.95 over 12 months.")
    assert "-15" not in en and "−" not in en and "add" not in en
    zh = concession_interpretation(cv, ob, "zh")
    assert "节省 ¥16,217.95" in zh and "−" not in zh and "-15" not in zh



def test_a_lengthening_still_reads_as_added_financing():
    ob = _ob(ObligationType.TERMS_EXTENSION)
    cv = {"value_fen": 2_432_692, "value_display": "¥24,326.92", "formula": _FORMULA, "per_invoice_fen": 187_130,
          "per_invoice_display": "¥1,871.30"}
    assert concession_interpretation(cv, ob, "en").startswith("60-day terms add 15 days of financing to 13 expected invoices")


def test_a_price_adjustment_reads_by_the_sign_of_its_value():
    ob = _ob(ObligationType.PRICE_ADJUSTMENT, rate_bp=30)
    paid = {"value_fen": -1_638_000, "value_display": "−¥16,380.00", "formula": "−Σ over 13 invoices (x) of 0.30% × face = y"}
    assert concession_interpretation(paid, ob, "en") == "A 0.30% price adjustment on 13 future invoices pays you ¥16,380.00 over 12 months."
    costs = {"value_fen": 1_638_000, "value_display": "¥16,380.00", "formula": "Σ over 13 invoices (x) of 0.30% × face = y"}
    assert concession_interpretation(costs, ob, "en") == "A 0.30% price adjustment on 13 future invoices costs you ¥16,380.00 over 12 months."
    assert "为您带来" in concession_interpretation(paid, ob, "zh") and "多付出" in concession_interpretation(costs, ob, "zh")


def test_a_rebate_is_counted_at_its_maximum_only_when_it_is_contingent():
    cv = {"value_fen": 400_000, "value_display": "¥4,000.00", "formula": "1.00% × ¥400,000.00 = ¥4,000.00"}
    contingent = _ob(ObligationType.CONTINGENT_REBATE, contingency=Contingency.CONTINGENT)
    assert concession_interpretation(cv, contingent, "en") == "A 1.00% rebate on ¥400,000.00 of purchases, counted at its maximum: ¥4,000.00."
    firm = _ob(ObligationType.CONTINGENT_REBATE, contingency=Contingency.FIRM)
    assert concession_interpretation(cv, firm, "en") == "A 1.00% rebate on ¥400,000.00 of purchases: ¥4,000.00."
    assert "按最大值计" not in concession_interpretation(cv, firm, "zh")


def test_a_claimed_unevidenced_concession_returns_its_basis_unchanged():
    basis = "claimed prior concession: never booked, counted as zero"
    cv = {"value_fen": 0, "value_display": "¥0.00", "basis": basis, "formula": "0 (never booked)"}
    for kind in (ObligationType.CONTINGENT_REBATE, ObligationType.TERMS_EXTENSION):
        ob = _ob(kind, contingency=Contingency.CLAIMED_UNEVIDENCED)
        assert concession_interpretation(cv, ob, "en") == basis


def test_operation_kind_tokens_read_as_words():
    raw = "A committed cure exists: DRAW_FACILITY Bank credit line + SUBMIT_INVOICE_FOR_FINANCING Invoice financing. REPAY_FACILITY X"
    assert operation_words(raw) == ("A committed cure exists: draw on Bank credit line + finance an invoice on Invoice financing. "
                                    "Repay X")
    assert operation_words("APPLY_FOR_FACILITY Term loan") == "Apply for Term loan"


def test_reconciliation_sentences_read_as_sentences(client, rt):
    """The recovered-receipt promise stands alone under the buyer's name: a capital, commas round its due clause, a full stop.
    A receipt's clause says "of the invoice", never the engine's "of face" (and the engine's own "outstanding ... of face ..." is left alone)."""
    from app.api.presentation import reconciliation_words

    state = rt.store.get_state()
    promise = reconciliation_words(state, "the agreed ¥255,013.80 for RCV-A arrived (commitment CMT-1)", 41, promise=True)
    assert promise == "The agreed ¥255,013.80 for the ¥420,000.00 invoice to Foshan Home Retail Co., due in 32 days, arrived."
    receipt = reconciliation_words(state, "agreed early payment for ¥257,200.00 of face (commitment CMT-1)", 41, promise=False)
    assert receipt == "agreed early payment for ¥257,200.00 of the invoice"
    kept = reconciliation_words(state, "short (outstanding ¥10.00 of face ¥20.00)", 41, promise=False)
    assert kept == "short (outstanding ¥10.00 of face ¥20.00)"
    assert reconciliation_words(state, None, 41, promise=True) is None
