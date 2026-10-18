"""The Cash page said "Cannot reach the API" while the API was running (fix/cash-unreachable).

Two parts:
- `POST /router/plan`, which the Cash page reads whenever the gap is open, raised `NoPermanentSourceError` on books with no committed,
  owner-approved source able to carry a permanent need: the blank books, and the owner's own books whose only lender is a clean-down
  credit line or whose invoice platform is not agreed yet. It now answers with the plan and the comparison and `marginal: null`.
- Any unhandled exception was a plain-text 500 from Starlette's ServerErrorMiddleware, outside CORS, so it carried no
  Access-Control-Allow-Origin and the browser reported it as a network failure. The catch-all in app/main.py answers a JSON 500 inside
  CORS (and keeps the keep-alive connection usable).
"""

from __future__ import annotations

import copy
import datetime
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

OWNER = {"X-Owner-Token": "demo-owner-token"}
ORIGIN = next(o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip())

# The owner's own books through the setup wizard: a bank credit line (30-day clean-down) is the only lender.
LINE_ONLY: dict[str, Any] = {
    "business": {"company_name": "Lingnan Homeware", "start_date": "2026-10-15", "cash": "¥400,000",
                 "monthly_sales": "500,000", "monthly_costs": "410,000"},
    "borrowing": [{"name": "Bank credit line", "kind": "CREDIT_LINE", "limit": "300,000", "drawn": "50,000", "rate_pct": "4.35",
                   "lead_time_days": 0, "agreed": True, "clean_down_days": 30}],
    "loans": [{"label": "Equipment loan", "owed": "540,000", "repayment": "45,000", "every": "MONTHLY",
               "next_payment_date": "2026-11-01"}],
    "customers": [
        {"name": "Foshan Home Retail", "contract": {"amount": "420,000", "every_days": 30, "terms_days": 45,
                                                    "next_invoice_date": "2026-10-29"},
         "invoices": [{"sent_on": "2026-07-31", "amount": "420,000", "paid": "257,200"},
                      {"sent_on": "2026-08-30", "amount": "420,000"}, {"sent_on": "2026-09-29", "amount": "420,000"}]},
        {"name": "Customer B", "invoices": [{"sent_on": "2026-10-01", "amount": "80,000", "terms_days": 30}]},
    ],
    "bills": [{"label": "Payroll", "kind": "PAYROLL", "amount": "340,000", "next_date": "2026-10-26", "repeats": "MONTHLY"},
              {"label": "Raw materials", "kind": "SUPPLIER", "amount": "180,000", "next_date": "2026-11-02", "repeats": "ONCE"}],
    "limits": {"min_cash": "300,000", "max_apr_pct": "15", "concession_cap": "5,000", "approval_above": "100,000", "valid_days": 90},
}


@pytest.fixture(autouse=True)
def _today_is_fixed(monkeypatch):
    """The setup start date is bounded against the server's today; the draft is written for mid-October 2026."""
    import app.setup as setup_mod

    monkeypatch.setattr(setup_mod, "today", lambda: datetime.date(2026, 10, 15))


def _open(client: TestClient, draft: dict[str, Any]) -> None:
    assert client.post("/demo/reset?scenario=blank").status_code == 200
    r = client.post("/setup/open", json={"draft": draft, "password": "demo-owner-token"})
    assert r.status_code == 200, r.text


def _plan(client: TestClient) -> dict[str, Any]:
    r = client.post("/router/plan", json={}, headers={"Origin": ORIGIN})
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") == ORIGIN
    body: dict[str, Any] = r.json()
    return body


# ---------------------------------------------------------------- the plan on books with no permanent source


def test_the_plan_answers_on_books_whose_only_lender_is_a_clean_down_line(client) -> None:
    _open(client, LINE_ONLY)
    home = client.get("/home").json()
    assert home["cash"]["first_breach_day"] is not None  # the gap is open: this is the read the Cash page makes
    body = _plan(client)
    assert body["marginal"] is None
    assert body["comparison"] and body["menu"] and body["committed"]


def test_the_plan_answers_after_the_funding_plan_on_those_books_ran(client) -> None:
    _open(client, LINE_ONLY)
    action = client.get("/home").json()["next_action"]
    assert action is not None
    r = client.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]})
    assert r.status_code == 200, r.text
    assert _plan(client)["marginal"] is None


def test_the_plan_answers_when_the_invoice_platform_is_not_agreed(client) -> None:
    d = copy.deepcopy(LINE_ONLY)
    d["borrowing"].append({"name": "Invoice financing platform", "kind": "INVOICE_FINANCING", "limit": "1,000,000", "rate_pct": "7.8",
                           "fee_pct": "0.25", "lead_time_days": 3, "agreed": False})
    _open(client, d)
    assert _plan(client)["marginal"] is None


def test_the_plan_answers_on_the_blank_books(client) -> None:
    assert client.post("/demo/reset?scenario=blank").status_code == 200
    assert _plan(client)["marginal"] is None


def test_the_golden_books_keep_their_marginal_source(client) -> None:
    m = _plan(client)["marginal"]
    assert m["rate_display"] == "10.8417%" and m["facility_id"] == "FAC-IF"


# ---------------------------------------------------------------- the catch-all


def test_an_unhandled_exception_is_a_json_500_that_carries_the_cors_headers(client, monkeypatch) -> None:
    from app import main

    def boom() -> None:
        raise RuntimeError("secret internals: fen=123 path=C:/x")

    monkeypatch.setattr(main, "get_settings", boom)
    c = TestClient(main.app, raise_server_exceptions=False)
    r = c.get("/health", headers={"Origin": ORIGIN})
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == ORIGIN
    assert r.headers.get("x-content-type-options") == "nosniff"  # the security headers still apply
    assert r.json() == {"detail": {"code": "INTERNAL_ERROR", "message": main.INTERNAL_ERROR["detail"]["message"]}}
    assert "secret" not in r.text and "RuntimeError" not in r.text
    monkeypatch.undo()
    assert c.get("/health", headers={"Origin": ORIGIN}).status_code == 200  # the next request is answered as usual


def test_an_origin_not_allowed_gets_no_cors_header_on_the_500(client, monkeypatch) -> None:
    from app import main

    monkeypatch.setattr(main, "get_settings", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    r = TestClient(main.app, raise_server_exceptions=False).get("/health", headers={"Origin": "https://evil.example"})
    assert r.status_code == 500 and r.headers.get("access-control-allow-origin") is None
