"""Set up your books (ADR-0013): the draft becomes the books the engine reads, the owner signs the limits by re-typing their
sign-in, opening replaces the books with one OPEN_BOOKS entry at the head of a fresh chain, and the blank scenario is a new
business with nothing in it."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from app.api.runtime import get_runtime
from app.mandate import verify_signature
from app.mandate.fixture import demo_owner_public_key_hex
from app.setup import BILL_HORIZON_DAYS, SetupDraft, build_books, parse_decimal

OWNER = {"X-Owner-Token": "demo-owner-token"}

DRAFT: dict[str, Any] = {
    "business": {"company_name": "Lingnan Homeware", "start_date": "2026-10-14", "cash": "¥400,000",
                 "monthly_sales": "500,000", "monthly_costs": "410,000"},
    "borrowing": [
        {"name": "Bank credit line", "kind": "CREDIT_LINE", "limit": "300,000", "drawn": "50,000", "rate_pct": "4.35",
         "lead_time_days": 0, "agreed": True, "clean_down_days": 30},
        {"name": "Invoice financing platform", "kind": "INVOICE_FINANCING", "limit": "1,000,000", "rate_pct": "7.8",
         "fee_pct": "0.25", "lead_time_days": 3, "agreed": True},
    ],
    "loans": [{"label": "Equipment loan", "owed": "540,000", "repayment": "45,000", "every": "MONTHLY",
               "next_payment_date": "2026-11-01"}],
    "customers": [
        {"name": "Foshan Home Retail", "contract": {"amount": "420,000", "every_days": 30, "terms_days": 45,
                                                    "next_invoice_date": "2026-10-29"},
         "invoices": [{"sent_on": "2026-07-31", "amount": "420,000", "paid": "257,200"},
                      {"sent_on": "2026-08-30", "amount": "420,000"},
                      {"sent_on": "2026-09-29", "amount": "420,000", "financed_amount": "200,000", "financed_by": 1}]},
        {"name": "Customer B", "invoices": [{"sent_on": "2026-10-01", "amount": "80,000", "terms_days": 30}]},
    ],
    "bills": [{"label": "Payroll", "kind": "PAYROLL", "amount": "340,000", "next_date": "2026-10-26", "repeats": "MONTHLY"},
              {"label": "Raw materials", "kind": "SUPPLIER", "amount": "180,000", "next_date": "2026-11-02", "repeats": "ONCE"}],
    "limits": {"min_cash": "300,000", "max_apr_pct": "15", "concession_cap": "5,000", "approval_above": "100,000", "valid_days": 90},
}


def draft(**changes: Any) -> dict[str, Any]:
    d = copy.deepcopy(DRAFT)
    for k, v in changes.items():
        d[k] = v
    return d


# ---------------------------------------------------------------- the builder


def test_amounts_are_parsed_by_code() -> None:
    assert parse_decimal("¥400,000") == 400000
    assert parse_decimal("4.35%") == parse_decimal("4.35")
    assert parse_decimal("") is None
    with pytest.raises(ValueError):
        parse_decimal("four hundred")


def test_draft_becomes_the_books_mid_contract() -> None:
    built = build_books(SetupDraft.model_validate(DRAFT))
    assert built.errors == []
    s, m = built.state, built.mandate
    assert s is not None and m is not None
    assert s.cash_fen == 40_000_000 and s.as_of == "2026-10-14" and s.scenario is None
    assert s.monthly_ebitda_fen == 9_000_000
    # invoices already sent keep negative issue days; a part payment is settled face; the financed one carries its advance
    rcv = {r.id: r for r in s.receivables}
    assert rcv["RCV-1-1"].issue_day == -75 and rcv["RCV-1-1"].settled_fen == 25_720_000 and rcv["RCV-1-1"].due_day == -30
    assert rcv["RCV-1-3"].status == "FINANCED" and rcv["RCV-1-3"].advance_fen == 20_000_000
    assert rcv["RCV-1-3"].advance_facility_id == "FAC-2"
    # the invoice-financing balance is the advances on its invoices; the line's balance is what was typed; lots match both
    fac = {f.id: f for f in s.facilities}
    assert fac["FAC-1"].drawn_fen == 5_000_000 and fac["FAC-2"].drawn_fen == 20_000_000
    assert sum(lot.remaining_fen for lot in s.lots if lot.facility_id == "FAC-2") == 20_000_000
    assert fac["FAC-1"].covenants[0].clean_down_days == 30 and m.require_clean_down
    # the contract repeats from its next invoice; payroll repeats monthly out to the horizon; a one-off bill once
    assert s.recurring_invoices[0].next_issue_day == 15 and s.recurring_invoices[0].every_days == 30
    payroll = [f for f in s.flows if f.label == "Payroll"]
    assert payroll[0].day == 12 and len(payroll) >= 35 and all(f.day <= BILL_HORIZON_DAYS for f in payroll)
    assert len([f for f in s.flows if f.label == "Raw materials"]) == 1
    assert s.debts[0].next_payment_day == 18 and s.debts[0].monthly_debt_service_fen == 4_500_000
    assert m.min_cash_fen == 30_000_000 and m.max_apr_bp == 1500 and m.tier2_single_commitment_fen == 10_000_000
    assert m.expires_day == 90 and m.signature_hex is None


def test_late_invoice_and_customer_without_contract_are_warnings() -> None:
    built = build_books(SetupDraft.model_validate(DRAFT))
    texts = [w.en for w in built.warnings]
    assert any("30 days late" in x for x in texts)
    assert any("Customer B has no contract" in x for x in texts)


@pytest.mark.parametrize(("change", "path"), [
    ({"business": {**DRAFT["business"], "cash": "lots"}}, "business.cash"),
    ({"business": {**DRAFT["business"], "start_date": ""}}, "business.start_date"),
    ({"borrowing": [{**DRAFT["borrowing"][0], "drawn": "400,000"}]}, "borrowing[0].drawn"),
    ({"customers": [{"name": "X", "invoices": [{"sent_on": "2026-11-01", "amount": "1", "terms_days": 30}]}]},
     "customers[0].invoices[0].sent_on"),
    ({"customers": [{"name": "X", "invoices": [{"sent_on": "2026-10-01", "amount": "100", "paid": "100", "terms_days": 30}]}]},
     "customers[0].invoices[0].paid"),
    ({"customers": [{"name": "X", "invoices": [{"sent_on": "2026-10-01", "amount": "100", "terms_days": 30,
                                                 "financed_amount": "50", "financed_by": 0}]}]},
     "customers[0].invoices[0].financed_by"),
    ({"limits": {**DRAFT["limits"], "max_apr_pct": "150"}}, "limits.max_apr_pct"),
])
def test_bad_entries_are_errors_that_build_nothing(change: dict, path: str) -> None:
    built = build_books(SetupDraft.model_validate(draft(**change)))
    assert built.state is None and built.mandate is None
    assert path in [e.path for e in built.errors]
    assert all(e.zh for e in built.errors)


def test_a_monthly_loss_is_refused_not_hidden() -> None:
    built = build_books(SetupDraft.model_validate(draft(business={**DRAFT["business"], "monthly_costs": "600,000"})))
    assert "business.monthly_costs" in [e.path for e in built.errors]


# ---------------------------------------------------------------- the routes


def test_status_names_the_demo_books(client) -> None:
    body = client.get("/setup/status").json()
    assert body["books"] == "demo" and body["can_open"] is True and body["opened"] is None


def test_setup_routes_are_owner_only(client) -> None:
    assert client.get("/setup/status", headers={"X-Owner-Token": "nope"}).status_code == 401
    assert client.post("/setup/preview", json={"draft": DRAFT}, headers={"X-Owner-Token": ""}).status_code == 401


def test_preview_gives_summary_and_first_forecast(client) -> None:
    body = client.post("/setup/preview", json={"draft": DRAFT}).json()
    assert body["ok"] is True and body["errors"] == []
    assert [s["step"] for s in body["summary"]] == [1, 2, 3, 4, 5]
    look = body["first_look"]
    # day 0 closes on the opening cash plus the invoice due that day (sent 30 Aug on 45-day terms)
    assert look["points"][0]["day"] == 0 and look["points"][0]["cash_fen"] == 40_000_000 + 42_000_000
    assert look["breach_day"] is not None and "below your minimum" in look["headline"]
    zh = client.post("/setup/preview?lang=zh", json={"draft": DRAFT}).json()
    assert "最低值" in zh["first_look"]["headline"]


def test_preview_returns_errors_without_a_forecast(client) -> None:
    body = client.post("/setup/preview", json={"draft": draft(business={**DRAFT["business"], "cash": ""})}).json()
    assert body["ok"] is False and body["first_look"] is None
    assert body["errors"][0]["step"] == 1


def test_open_needs_the_owner_password(client) -> None:
    before = len(get_runtime().store.operations())
    r = client.post("/setup/open", json={"draft": DRAFT, "password": "guess"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "SIGNATURE_REFUSED"
    assert len(get_runtime().store.operations()) == before
    assert get_runtime().store.get_state().scenario == "golden_sme"


def test_open_refuses_an_invalid_draft(client) -> None:
    r = client.post("/setup/open", json={"draft": draft(limits={}), "password": "demo-owner-token"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "SETUP_INVALID"
    assert get_runtime().store.get_state().scenario == "golden_sme"


def test_open_replaces_the_books_and_starts_the_record(client) -> None:
    r = client.post("/setup/open", json={"draft": DRAFT, "password": "demo-owner-token"})
    assert r.status_code == 200, r.text
    rt = get_runtime()
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    assert state.cash_fen == 40_000_000 and state.scenario is None and rt.day == 0
    assert verify_signature(mandate, demo_owner_public_key_hex())
    ops = rt.store.operations()
    assert [o.kind for o in ops] == ["OPEN_BOOKS"] and rt.store.verify_chain()
    assert rt.store.commitments() == [] and rt.store.approvals() == []
    status = client.get("/setup/status").json()
    assert status["books"] == "own" and status["opened"]["company_name"] == "Lingnan Homeware"
    # the owner's reads answer from the new books
    home = client.get("/home").json()
    assert home["cash"]["cash_fen"] == 40_000_000
    activity = client.get("/activity").json()
    assert activity["rows"][0]["title_text"] == "You opened your books for Lingnan Homeware from 14 Oct 2026."
    assert activity["rows"][0]["category"] == "cash"
    assert client.get("/evidence").status_code == 200


def test_a_contract_the_row_came_from_is_confirmed_under_the_new_customer(client) -> None:
    client.post("/demo/reset")  # the golden books come with the three demo documents confirmed
    docs = client.get("/setup/documents?start_date=2026-10-14").json()["documents"]
    supply = next(d for d in docs if d["kind"] == "BUYER_CONTRACT")
    row = supply["row"]
    assert row["name"] == "Foshan Home Retail Co." and row["contract"]["every_days"] == 30
    assert row["contract"]["next_invoice_date"] >= "2026-10-14"
    assert supply["progress"]["sent"] >= 1 and all(i["sent_on"] < "2026-10-14" for i in row["invoices"])
    line = next(d for d in docs if d["kind"] == "LENDER_AGREEMENT" and d["row"]["kind"] == "CREDIT_LINE")
    d = draft()
    d["customers"][0]["contract"]["document_id"] = supply["document_id"]
    d["borrowing"][0]["document_id"] = line["document_id"]
    r = client.post("/setup/open", json={"draft": d, "password": "demo-owner-token"})
    assert r.status_code == 200 and len(r.json()["confirmed_documents"]) == 2
    rt = get_runtime()
    records = {rec.counterparty_id: rec for rec in rt.store.contract_records()}
    assert records["BUYER-1"].status.value == "CONFIRMED" and records["LENDER-1"].linked_facility_id == "FAC-1"
    assert [o.kind for o in rt.store.operations()] == ["OPEN_BOOKS", "CONFIRM_DOCUMENT", "CONFIRM_DOCUMENT"]
    assert rt.store.verify_chain()


def test_a_document_read_during_setup_waits_until_the_books_open(client) -> None:
    text = ("SUPPLY AGREEMENT between Acme Parts Co. (Supplier) and Delta Retail Co. (Buyer). "
            "The Buyer shall pay each invoice within thirty (30) days of the invoice date.")
    r = client.post("/setup/documents", json={"kind": "BUYER_CONTRACT", "text": text, "title": "Delta supply agreement",
                                              "start_date": "2026-10-14"})
    assert r.status_code == 200, r.text
    doc = r.json()["document"]
    assert doc["from_setup"] is True and doc["status"] == "PROPOSED"
    assert all(rec.id != doc["document_id"] for rec in get_runtime().store.contract_records())  # nothing stored yet


def test_blank_scenario_is_a_new_business(client) -> None:
    r = client.post("/demo/reset?scenario=blank")
    assert r.status_code == 200
    assert client.get("/setup/status").json()["books"] == "blank"
    for path in ("/home", "/worklist", "/activity", "/receivables", "/deals"):
        assert client.get(path).status_code == 200, path


# ---------------------------------------------------------------- two open invoices of one amount (found by hand, 14 Oct)


def _two_invoice_books(client) -> None:
    d = draft()
    d["customers"] = [{"name": "Foshan Home Retail Co.", "contract": {"amount": "420,000", "every_days": 30, "terms_days": 45,
                                                                        "next_invoice_date": "2026-11-02"},
                       "invoices": [{"sent_on": "2026-09-18", "amount": "420,000"}, {"sent_on": "2026-10-03", "amount": "420,000"}]}]
    assert client.post("/setup/open", json={"draft": d, "password": "demo-owner-token"}).status_code == 200


def test_the_contract_prefill_says_its_invoices_are_assumed_unpaid(client) -> None:
    client.post("/demo/reset")
    docs = client.get("/setup/documents?start_date=2026-10-14").json()["documents"]
    supply = next(d for d in docs if d["kind"] == "BUYER_CONTRACT")
    assert len(supply["row"]["invoices"]) == 2
    assert "assumed they are unpaid" in supply["progress"]["assumed_text"]
    assert "18 Sep 2026" in supply["progress"]["assumed_text"] and "3 Oct 2026" in supply["progress"]["assumed_text"]


def test_an_offer_naming_an_invoice_only_by_amount_says_which_invoices_it_could_be(client) -> None:
    _two_invoice_books(client)
    offer_id = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{offer_id}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    record = client.get(f"/decisions/deal:{offer_id}").json()
    c = record["evaluation"]["clarification"]
    assert record["evaluation"]["business_action"] == "cannot" and c["kind"] == "WHICH_INVOICE"
    assert [o["sent_text"] for o in c["options"]] == ["18 Sep 2026", "3 Oct 2026"]
    assert "Which ¥420,000.00 invoice does Foshan Home Retail Co. mean?" in c["text"]
    assert "the one dated 18 Sep 2026 or the one dated 3 Oct 2026" in c["ask_buyer_text"]
    zh = client.get(f"/decisions/deal:{offer_id}?lang=zh").json()["evaluation"]["clarification"]
    assert "哪一张" in zh["text"] and "2026年9月18日" in zh["text"]
