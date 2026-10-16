import copy, datetime, sys, os
sys.path.insert(0, os.getcwd())
import app.setup as setup_mod
setup_mod.today = lambda: datetime.date(2026, 10, 15)
DRAFT = {
    "business": {"company_name": "Lingnan Homeware", "start_date": "2026-10-14", "cash": "400,000",
                 "monthly_sales": "500,000", "monthly_costs": "410,000"},
    "borrowing": [{"name": "Bank credit line", "kind": "CREDIT_LINE", "limit": "300,000", "drawn": "50,000", "rate_pct": "4.35",
         "lead_time_days": 0, "agreed": True}],
    "loans": [], "customers": [{"name": "Foshan Home Retail", "invoices": [{"sent_on": "2026-09-01", "amount": "420,000", "terms_days": 60}]}],
    "bills": [{"label": "Payroll", "kind": "PAYROLL", "amount": "340,000", "next_date": "2026-10-26", "repeats": "MONTHLY"}],
    "limits": {"min_cash": "300,000", "max_apr_pct": "15", "concession_cap": "5,000", "approval_above": "100,000", "valid_days": 90},
}
OWNER = {"X-Owner-Token": os.environ.get("OWNER_TOKEN", "demo-owner-token")}
def draft(): return copy.deepcopy(DRAFT)
def make_client(store=None):
    from fastapi.testclient import TestClient
    from app.api.runtime import Runtime, set_runtime
    from app.config import get_settings
    from app.mandate.fixture import demo_owner_public_key_hex
    from app.persistence import InMemoryLedgerStore
    rt = Runtime(settings=get_settings(), store=store or InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    set_runtime(rt)
    from app.main import app
    return rt, TestClient(app, raise_server_exceptions=False)
