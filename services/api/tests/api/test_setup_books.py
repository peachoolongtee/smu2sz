"""Set up your books (ADR-0013): the draft becomes the books the engine reads, the owner signs the limits by re-typing their
sign-in, opening replaces the books with one OPEN_BOOKS entry at the head of a fresh chain, and the blank scenario is a new
business with nothing in it."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from app.api import setup as setup_api
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


@pytest.fixture(autouse=True)
def _today_is_fixed(monkeypatch):
    """The start date is bounded against the server's today; the drafts below are written for mid-October 2026."""
    import datetime

    import app.setup as setup_mod

    monkeypatch.setattr(setup_mod, "today", lambda: datetime.date(2026, 10, 15))


@pytest.fixture(autouse=True)
def _no_documents_left_over():
    setup_api._setup_docs.clear()
    yield
    setup_api._setup_docs.clear()


def blank(client) -> None:
    """Setup opens only the blank books."""
    assert client.post("/demo/reset?scenario=blank").status_code == 200


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


def test_status_names_the_demo_books_and_says_opening_waits_for_the_blank_books(client) -> None:
    body = client.get("/setup/status").json()
    assert body["books"] == "demo" and body["can_open"] is False and body["opened"] is None
    assert body["can_open_text"].startswith("Books are already open on this server")
    zh = client.get("/setup/status?lang=zh").json()["can_open_text"]
    assert zh.startswith("此服务器上已有开立的账簿")


def test_status_on_the_blank_books_can_open(client) -> None:
    client.post("/demo/reset?scenario=blank")
    body = client.get("/setup/status").json()
    assert body["books"] == "blank" and body["can_open"] is True and body["can_open_text"] is None


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
    blank(client)
    r = client.post("/setup/open", json={"draft": draft(limits={}), "password": "demo-owner-token"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "SETUP_INVALID"
    assert get_runtime().store.get_state().scenario == "blank"


def test_open_replaces_the_books_and_starts_the_record(client) -> None:
    blank(client)
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
    # Setup opens only the blank books, which hold no documents: the confirmed ones wait as documents read during setup.
    kept = get_runtime().store.contract_records()
    blank(client)
    setup_api._setup_docs.update({rec.id: rec for rec in kept})
    d = draft()
    d["customers"][0]["contract"]["document_id"] = supply["document_id"]
    d["borrowing"][0]["document_id"] = line["document_id"]
    r = client.post("/setup/open", json={"draft": d, "password": "demo-owner-token"})
    assert r.status_code == 200 and len(r.json()["confirmed_documents"]) == 2
    rt = get_runtime()
    by_party = {rec.counterparty_id: rec for rec in rt.store.contract_records()}
    assert by_party["BUYER-1"].status.value == "CONFIRMED" and by_party["LENDER-1"].linked_facility_id == "FAC-1"
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
    blank(client)
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


# ---------------------------------------------------------------- opening replaces only the blank books


def _counts() -> tuple[str, int, int, int]:
    rt = get_runtime()
    return (rt.store.get_state().model_dump_json(), len(rt.store.commitments()), len(rt.store.operations()),
            len(rt.store.approvals()))


def test_a_second_open_is_refused_and_nothing_changes(client) -> None:
    blank(client)
    first = client.post("/setup/open", json={"draft": DRAFT, "password": "demo-owner-token"})
    assert first.status_code == 200, first.text
    before = _counts()
    again = client.post("/setup/open", json={"draft": draft(business={**DRAFT["business"], "cash": "1,000"}),
                                             "password": "demo-owner-token"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "BOOKS_ALREADY_OPEN"
    assert "reset to the blank books first" in again.json()["detail"]["message"]
    zh = client.post("/setup/open?lang=zh", json={"draft": DRAFT, "password": "demo-owner-token"})
    assert zh.status_code == 409 and "空白账簿" in zh.json()["detail"]["message"]
    assert _counts() == before and before[2] == 1
    assert get_runtime().store.verify_chain()


def test_opening_over_the_golden_books_is_refused(client) -> None:
    client.post("/demo/reset")
    before = _counts()
    assert before[2] > 0  # the golden books come with their documents confirmed
    r = client.post("/setup/open", json={"draft": DRAFT, "password": "demo-owner-token"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "BOOKS_ALREADY_OPEN"
    assert _counts() == before and get_runtime().store.get_state().scenario == "golden_sme"


def test_the_blank_books_stay_openable_after_a_restart(client) -> None:
    blank(client)
    rt = get_runtime()
    rt.scenario = "golden_sme"  # a restarted process reads the scenario from the stored books, not from memory
    rt.hydrate()
    assert client.post("/setup/open", json={"draft": DRAFT, "password": "demo-owner-token"}).status_code == 200


def test_a_failure_while_opening_puts_the_blank_books_back(client, monkeypatch) -> None:
    blank(client)
    rt = get_runtime()

    def boom(*a, **k):
        raise RuntimeError("disk on fire /srv/secret/path")

    monkeypatch.setattr(rt.store, "append_operation", boom)
    r = client.post("/setup/open", json={"draft": DRAFT, "password": "demo-owner-token"})
    assert r.status_code == 500 and r.json()["detail"]["code"] == "SETUP_FAILED"
    assert "nothing was opened" in r.json()["detail"]["message"] and "disk on fire" not in r.text
    zh = client.post("/setup/open?lang=zh", json={"draft": DRAFT, "password": "demo-owner-token"})
    assert zh.status_code == 500 and "空白账簿" in zh.json()["detail"]["message"]
    monkeypatch.undo()
    state = rt.store.get_state()
    assert state.scenario == "blank" and state.cash_fen == 0 and rt.scenario == "blank" and rt.day == 0
    assert rt.store.operations() == [] and rt.store.commitments() == [] and rt.store.verify_chain()
    assert client.get("/setup/status").json()["books"] == "blank"
    # and the books can still be opened afterwards
    assert client.post("/setup/open", json={"draft": DRAFT, "password": "demo-owner-token"}).status_code == 200


# ---------------------------------------------------------------- bounds on what is typed


def _lim(**k: Any) -> dict:
    return {"limits": {**DRAFT["limits"], **k}}


def _biz(**k: Any) -> dict:
    return {"business": {**DRAFT["business"], **k}}


@pytest.mark.parametrize(("change", "path"), [
    (_biz(cash="10,000,000,000,000.01"), "business.cash"),
    (_biz(cash="9" * 400), "business.cash"),
    (_lim(min_cash="20,000,000,000,000"), "limits.min_cash"),
    (_lim(approval_above="10,000,000,000,000.01"), "limits.approval_above"),
    (_lim(concession_cap="99,999,999,999,999,999"), "limits.concession_cap"),
    ({"customers": [{"name": "X", "invoices": [{"sent_on": "2026-10-01", "amount": "90,000,000,000,000,000", "terms_days": 30}]}]},
     "customers[0].invoices[0].amount"),
    (_biz(start_date="2027-11-20"), "business.start_date"),
    (_biz(start_date="2025-09-09"), "business.start_date"),
    (_biz(start_date="9999-12-31"), "business.start_date"),
    ({"customers": [{"name": "Foshan Home Retail"}, {"name": "  foshan   HOME retail "}]}, "customers[1].name"),
    (_lim(min_dscr="0.00001"), "limits.min_dscr"),
    (_lim(min_dscr="0.99"), "limits.min_dscr"),
    (_lim(min_dscr="10.01"), "limits.min_dscr"),
    (_lim(min_dscr="0"), "limits.min_dscr"),
    (_lim(max_leverage="0.1"), "limits.max_leverage"),
    (_lim(max_leverage="11"), "limits.max_leverage"),
])
def test_out_of_bounds_entries_are_errors_in_both_languages(change: dict, path: str) -> None:
    built = build_books(SetupDraft.model_validate(draft(**change)))
    assert built.state is None and built.mandate is None
    hit = [e for e in built.errors if e.path == path]
    assert hit and all(e.en and e.zh and e.zh != e.en for e in hit)


@pytest.mark.parametrize("change", [
    _biz(cash="10,000,000,000,000"), _biz(start_date="2027-11-19"), _biz(start_date="2025-09-10"),
    _lim(min_dscr="1"), _lim(min_dscr="10"), _lim(max_leverage="0.5"), _lim(max_leverage="10"),
])
def test_the_edges_of_the_bounds_are_allowed(change: dict) -> None:
    # (a start date moved to the edge leaves the other dates of this draft before it, so only the bound itself is checked)
    errors = build_books(SetupDraft.model_validate(draft(**change))).errors
    assert not [e for e in errors if e.path in ("business.start_date", "business.cash") or e.path.startswith("limits.")]


def test_the_same_invoice_twice_is_a_warning_not_an_error() -> None:
    twice = {"sent_on": "2026-10-01", "amount": "80,000", "terms_days": 30}
    built = build_books(SetupDraft.model_validate(draft(customers=[{"name": "Customer B", "invoices": [twice, dict(twice)]}])))
    assert built.errors == [] and built.state is not None and len(built.state.receivables) == 2
    dup = [w for w in built.warnings if w.path == "customers[0].invoices[1]"]
    assert dup and "same date" in dup[0].en and dup[0].zh
    other = build_books(SetupDraft.model_validate(draft(customers=[
        {"name": "Customer B", "invoices": [twice, {**twice, "amount": "80,001"}]}])))
    assert not [w for w in other.warnings if "same date" in w.en]


def test_a_far_bill_date_never_becomes_a_server_error(client) -> None:
    bills = [{"label": "Rent", "kind": "RENT", "amount": "9,000", "next_date": "9999-12-31", "repeats": "MONTHLY"},
             {"label": "Tax", "kind": "TAX", "amount": "9,000", "next_date": "2026-11-30", "repeats": "YEARLY", "until": "9999-12-31"}]
    r = client.post("/setup/preview", json={"draft": draft(bills=bills)})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert build_books(SetupDraft.model_validate(draft(bills=bills))).state is not None
    assert not [f for f in build_books(SetupDraft.model_validate(draft(bills=bills))).state.flows if f.label == "Rent"]
    far = client.post("/setup/preview", json={"draft": draft(**_biz(start_date="0001-01-01"))})
    assert far.status_code == 200 and far.json()["ok"] is False


# ---------------------------------------------------------------- who may use setup, and where


SETUP_CALLS = [("get", "/setup/status", None), ("get", "/setup/documents", None),
               ("post", "/setup/documents", {"kind": "BUYER_CONTRACT", "text": "Supply agreement"}),
               ("post", "/setup/preview", {"draft": DRAFT}), ("post", "/setup/open", {"draft": DRAFT, "password": "demo-owner-token"})]


@pytest.mark.parametrize(("method", "path", "body"), SETUP_CALLS)
@pytest.mark.parametrize("headers", [{"X-Agent-Key": "demo-agent-key"}, {"X-Bank-Feed-Key": "demo-bank-feed-key"},
                                     {"X-Counterparty-Key": "demo-buyer-1-key"}, {}])
def test_only_the_owner_reaches_setup(client, method: str, path: str, body: dict | None, headers: dict) -> None:
    before = _counts()
    r = client.request(method.upper(), path, json=body, headers={"X-Owner-Token": "", **headers})
    assert r.status_code == 401, (path, r.text)
    assert _counts() == before and setup_api._setup_docs == {}


def test_without_demo_mode_open_and_documents_are_refused(client, monkeypatch) -> None:
    blank(client)
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("OWNER_TOKEN", "a-real-owner-token")
    owner = {"X-Owner-Token": "a-real-owner-token"}
    before = _counts()
    text = "SUPPLY AGREEMENT between Acme Parts Co. (Supplier) and Delta Retail Co. (Buyer). The Buyer shall pay within thirty (30) days."
    for r in (client.post("/setup/open", json={"draft": DRAFT, "password": "a-real-owner-token"}, headers=owner),
              client.post("/setup/documents", json={"kind": "BUYER_CONTRACT", "text": text}, headers=owner),
              client.get("/setup/documents", headers=owner)):
        assert r.status_code == 403 and r.json()["detail"]["code"] == "SETUP_REFUSED"
    assert _counts() == before and setup_api._setup_docs == {}
    assert client.get("/setup/status", headers=owner).json()["can_open"] is False


def test_setup_holds_at_most_ten_documents(client) -> None:
    for i in range(setup_api.MAX_SETUP_DOCS):
        text = (f"SUPPLY AGREEMENT {i} between Acme Parts Co. (Supplier) and Delta Retail {i} Co. (Buyer). "
                "The Buyer shall pay each invoice within thirty (30) days of the invoice date.")
        assert client.post("/setup/documents", json={"kind": "BUYER_CONTRACT", "text": text}).status_code == 200
    assert len(setup_api._setup_docs) == setup_api.MAX_SETUP_DOCS
    r = client.post("/setup/documents", json={"kind": "BUYER_CONTRACT", "text": "SUPPLY AGREEMENT one more, pay within 30 days."})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "SETUP_DOCUMENTS_FULL"
    zh = client.post("/setup/documents?lang=zh", json={"kind": "BUYER_CONTRACT", "text": "SUPPLY AGREEMENT one more."})
    assert zh.status_code == 409 and "份文件" in zh.json()["detail"]["message"]
    assert len(setup_api._setup_docs) == setup_api.MAX_SETUP_DOCS


def test_a_projection_failure_is_logged_not_shown(client, monkeypatch, caplog) -> None:
    def boom(*a, **k):
        raise RuntimeError("secret engine detail /srv/app/financial.py")

    monkeypatch.setattr(setup_api, "_first_look", boom)
    with caplog.at_level("ERROR"):
        r = client.post("/setup/preview", json={"draft": DRAFT})
        zh = client.post("/setup/preview?lang=zh", json={"draft": DRAFT})
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["summary"] is None
    assert r.json()["errors"][0]["text"] == "FLOW could not project these books. Check the figures you entered, then try again."
    assert "无法对这些账簿做预测" in zh.json()["errors"][0]["text"]
    assert "secret engine detail" not in r.text and "secret engine detail" not in zh.text
    assert "secret engine detail" in caplog.text


# ---------------------------------------------------------------- SETUP-1: books are blank only while untouched


def _open(client, **kw):
    return client.post("/setup/open", json={"draft": DRAFT, "password": "demo-owner-token"}, **kw)


def test_a_fresh_blank_reset_leaves_nothing_in_the_log_no_event_and_day_zero(client) -> None:
    blank(client)
    rt = get_runtime()
    assert rt.store.operations() == [] and rt.store.security_events() == [] and rt.store.get_state().as_of_day == 0
    assert client.get("/setup/status").json()["can_open"] is True


def test_blank_books_with_an_operation_in_the_log_are_not_opened(client) -> None:
    from app.persistence.canonical import canonical_json

    blank(client)
    rt = get_runtime()
    rt.store.append_operation("op-x", "NOTE", "op-x", canonical_json({"kind": "NOTE"}), canonical_json({"status": "EXECUTED"}))
    before = _counts()
    r = _open(client)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "BOOKS_ALREADY_OPEN"
    assert _counts() == before and client.get("/setup/status").json()["can_open"] is False
    zh = _open(client, params={"lang": "zh"})
    assert zh.status_code == 409 and "重置为空白账簿" in zh.json()["detail"]["message"]


def test_blank_books_with_a_security_event_are_not_opened(client) -> None:
    from app.domain.models import SecurityEvent, SecurityEventKind

    blank(client)
    rt = get_runtime()
    rt.store.add_security_event(SecurityEvent(id="SEC-1", day=0, kind=SecurityEventKind.REPLAY, counterparty_id=None,
                                              action_taken="refused; nothing booked", detail="x"))
    before = _counts()
    r = _open(client)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "BOOKS_ALREADY_OPEN"
    assert _counts() == before and len(rt.store.security_events()) == 1


def test_blank_books_whose_clock_has_moved_are_not_opened(client) -> None:
    blank(client)
    assert client.post("/clock/advance", json={"days": 3}, headers=OWNER).status_code == 200
    rt = get_runtime()
    assert rt.store.get_state().as_of_day == 3
    before = _counts()
    r = _open(client)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "BOOKS_ALREADY_OPEN"
    assert _counts() == before and rt.store.get_state().scenario == "blank"


def test_a_fresh_blank_opens_and_records_what_it_replaced(client) -> None:
    import json

    blank(client)
    assert _open(client).status_code == 200
    entry = json.loads(get_runtime().store.operations()[0].payload_json)
    assert entry["replaced_ops"] == 0 and entry["replaced_head_hash"] is None and entry["replaced_scenario"] == "blank"


# ---------------------------------------------------------------- SETUP-4, SETUP-5, SETUP-7


def test_a_huge_digit_string_is_a_draft_error_never_a_500(client) -> None:
    big = "9" * 5_000_000
    with pytest.raises(ValueError):
        parse_decimal(big)
    with pytest.raises(ValueError):
        parse_decimal("1" * 41)
    assert parse_decimal("1" * 20 + "." + "5" * 10) is not None
    for biz in ({**DRAFT["business"], "cash": big}, {**DRAFT["business"], "monthly_sales": "9" * 50}):
        r = client.post("/setup/preview", json={"draft": draft(business=biz)})
        assert r.status_code == 200 and r.json()["ok"] is False and r.json()["errors"]
        o = client.post("/setup/open", json={"draft": draft(business=biz), "password": "demo-owner-token"})
        assert o.status_code in (409, 422) and o.status_code != 500


def test_the_preview_needs_demo_mode_like_the_other_setup_routes(client, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("OWNER_TOKEN", "a-real-owner-token")
    r = client.post("/setup/preview", json={"draft": DRAFT}, headers={"X-Owner-Token": "a-real-owner-token"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "SETUP_REFUSED"
    monkeypatch.undo()
    assert client.post("/setup/preview", json={"draft": DRAFT}).status_code == 200


def test_long_lists_are_refused_in_the_owners_words(client) -> None:
    bills = [{"label": f"Bill {i}", "kind": "OTHER", "amount": "100", "next_date": "2026-11-02", "repeats": "MONTHLY"}
             for i in range(201)]
    r = client.post("/setup/preview", json={"draft": draft(bills=bills)}).json()
    assert r["ok"] is False and r["summary"] is None and "Too many bills: 201 entered, at most 200" in r["errors"][0]["text"]
    zh = client.post("/setup/preview?lang=zh", json={"draft": draft(bills=bills)}).json()
    assert "支出太多" in zh["errors"][0]["text"]
    customers = [{"name": f"Customer {i}"} for i in range(201)]
    assert "customers" in client.post("/setup/preview", json={"draft": draft(customers=customers)}).json()["errors"][0]["text"].lower()
    invoices = [{"sent_on": "2026-10-01", "amount": "100", "terms_days": 30}] * 201
    r = client.post("/setup/preview", json={"draft": draft(customers=[{"name": "A", "invoices": invoices}])}).json()
    assert r["ok"] is False and "Too many invoices for one customer" in r["errors"][0]["text"]
    borrowing = [{"name": f"S{i}", "kind": "CREDIT_LINE", "limit": "1000"} for i in range(201)]
    assert client.post("/setup/preview", json={"draft": draft(borrowing=borrowing)}).json()["ok"] is False
    before = _counts()
    o = client.post("/setup/open", json={"draft": draft(bills=bills), "password": "demo-owner-token"})
    assert o.status_code in (409, 422) and _counts() == before


def test_200_rows_still_pass_and_long_texts_are_refused(client) -> None:
    bills = [{"label": f"Bill {i}", "kind": "OTHER", "amount": "100", "next_date": "2026-11-02", "repeats": "ONCE"}
             for i in range(200)]
    assert client.post("/setup/preview", json={"draft": draft(bills=bills)}).json()["ok"] is True
    long_text = "x" * 201
    r = client.post("/setup/preview", json={"draft": draft(business={**DRAFT["business"], "what_you_sell": long_text})}).json()
    assert r["ok"] is False and "too long" in r["errors"][0]["text"] and r["errors"][0]["step"] == 1
    huge = client.post("/setup/preview", json={"draft": draft(business={**DRAFT["business"], "company_name": "y" * 2_000_000})}).json()
    assert huge["ok"] is False and "too long" in huge["errors"][0]["text"]
    zh = client.post("/setup/preview?lang=zh", json={"draft": draft(business={**DRAFT["business"], "company_name": "y" * 201})}).json()
    assert "过长" in zh["errors"][0]["text"]
