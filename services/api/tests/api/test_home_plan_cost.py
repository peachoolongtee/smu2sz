"""The plan's cost on Home is the plan's own (found live on dev, 16 Oct 2026). New books with a ¥100,000 credit-line balance drawn before they
started: the cure is an open-ended ¥351,479.45 draw. That draw lets the projection repay the old ¥100,000 on day 30 rather than at the
horizon end, and the alert used to take that repayment as the new draw's own. Home then said "Cost to you −¥1,109.59 · Repaid in 30 days":
the 90 days of interest saved on the OLD balance, with a minus sign that read as a gain. The draw is open-ended, so it is not priced, and
the basis says the rate it runs at.

Hand figures (start 16 Oct 2026, day 0): cash ¥400,000; payroll ¥200,000 on days 9, 40, 70 and 101; the ¥300,000 invoice sent 1 Oct on
45 days is paid on day 30. The ¥100,000 drawn before the books started is assumed repaid at the 120-day horizon with
100,000 × 4.5% × 120/365 = ¥1,479.45 interest:
  first breach day 70: 400,000 − 200,000 + 300,000 − 200,000 − 200,000 = ¥100,000 (¥50,000 under the ¥150,000 minimum);
  lowest, day 120: 100,000 − 200,000 − 100,000 − 1,479.45 = −¥201,479.45; the plan: 150,000 + 201,479.45 = ¥351,479.45;
  with the plan (the old ¥100,000 repaid on day 30 with 100,000 × 4.5% × 30/365 = ¥369.86, the new draw carried open):
  400,000 + 351,479.45 + 300,000 − 800,000 − 100,000 − 369.86 = ¥151,109.59."""

from __future__ import annotations

import datetime
import json

import pytest

from app.api.home import _stated_cost
from app.api.home_v2 import _plan_facts, _PlanParts

OWNER = {"X-Owner-Token": "demo-owner-token"}

DRAFT = {
    "business": {"company_name": "Test Co", "start_date": "2026-10-16", "cash": "400,000"},
    "borrowing": [{"name": "Credit line", "kind": "CREDIT_LINE", "limit": "500,000", "drawn": "100,000", "rate_pct": "4.5",
                   "lead_time_days": 1, "agreed": True}],
    "customers": [{"name": "Test Retail Ltd.", "invoices": [{"sent_on": "2026-10-01", "amount": "300,000", "terms_days": 45}]}],
    "bills": [{"label": "Payroll", "kind": "PAYROLL", "amount": "200,000", "next_date": "2026-10-25", "repeats": "MONTHLY"}],
    "limits": {"min_cash": "150,000", "max_apr_pct": "6", "concession_cap": "50,000", "approval_above": "200,000", "valid_days": 90},
}


@pytest.fixture(autouse=True)
def _today_is_the_16th(monkeypatch):
    import app.setup as setup_mod

    monkeypatch.setattr(setup_mod, "today", lambda: datetime.date(2026, 10, 16))


def _open(client) -> None:
    assert client.post("/demo/reset?scenario=blank").status_code == 200
    r = client.post("/setup/open", json={"draft": DRAFT, "password": "demo-owner-token"})
    assert r.status_code == 200, r.text


def test_the_preview_names_its_window(client) -> None:
    assert client.post("/demo/reset?scenario=blank").status_code == 200
    look = client.post("/setup/preview", json={"draft": DRAFT}).json()["first_look"]
    assert look["headline"] == "Your cash goes below your minimum in 70 days"
    # 90 days: the ¥100,000 drawn before the books started is assumed repaid at the window's end, with 100,000 × 4.5% × 90/365 = ¥1,109.59
    assert look["detail"].startswith("Lowest point in the next 90 days −¥1,109.59 on 14 Jan 2027.")
    zh = client.post("/setup/preview?lang=zh", json={"draft": DRAFT}).json()["first_look"]
    assert zh["detail"].startswith("未来 90 天内最低点 −¥1,109.59")


def test_an_open_ended_draw_is_not_priced_and_the_basis_says_its_rate(client) -> None:
    _open(client)
    [b] = [a for a in client.get("/alerts").json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
    [s] = b["suggested"]
    assert s["operation_kind"] == "DRAW_FACILITY" and s["amount_fen"] == 35_147_945
    assert s["cost_fen"] is None and s["cost_days"] is None and s["annual_rate"] is None
    assert "cure_cost" not in b["inputs"] and "cure_end_day_0" not in b["inputs"]

    home = client.get("/home").json()
    page = json.dumps(home, ensure_ascii=False)
    assert "−¥1,109.59" not in page  # the interest saved on the old balance, never a cost (the leg's "repaid" day is checked below)
    na = home["next_action"]
    assert na["cost_total_display"] is None and na["cost_unstated"] == "UNPRICED"
    basis = "Not priced: the draw has no repayment date yet, so interest runs at 4.50% a year while the balance stays drawn."
    assert na["cost_basis"] == basis

    v2 = home["home_v2"]
    action, kpis = v2["action"], v2["kpis"]
    assert action["title"] == "Secure ¥351,479.45 before payroll in 70 days."
    assert action["facts"][0] == {"label": "Estimated cost", "value": "Not priced"}
    assert action["cost_basis_text"] == basis
    assert " cost " not in action["text"]
    [leg] = action["legs"]
    assert leg["amount_display"] == "¥351,479.45" and leg["lands_when"] == "tomorrow"
    assert leg["cost_display"] is None and leg["repaid_when"] is None

    # every money figure on the page, against the hand figures in the module's docstring
    assert kpis["cash_available"]["value_display"] == "¥400,000" and kpis["cash_available"]["buffer"]["min_fen"] == 15_000_000
    assert kpis["lowest_ahead"]["value_display"] == "−¥201,479.45"
    assert kpis["funding"]["value_display"] == "¥351,479.45"
    assert kpis["lowest_ahead"]["with_plan"]["value_text"] == "¥151,109.59"

    zh = client.get("/home?lang=zh").json()
    assert zh["next_action"]["cost_basis"] == "未计价：该提款尚无还款日，余额未还期间按年化 4.50% 计息。"
    assert zh["home_v2"]["action"]["facts"][0]["value"] == "未计价"


def test_a_net_below_zero_is_never_called_a_cost() -> None:
    for lang, word in (("en", "No added cost: in the forecast, this plan lowers the interest and fees you already pay by ¥1,109.59."),
                       ("zh", "无新增成本：按预测，此方案使您原本要支付的利息和费用减少 ¥1,109.59。")):
        total, basis, note, unstated = _stated_cost(None, [], "−¥1,109.59", "a basis", "a note", lang)  # type: ignore[arg-type]
        assert (total, basis, note, unstated) == (None, word, None, "NET_SAVING")
    # a cost at or above zero is left as it is
    assert _stated_cost(None, [], "¥2,272.29", "b", None, "en") == ("¥2,272.29", "b", None, None)  # type: ignore[arg-type]
    parts = _PlanParts("within your signed limits", "legs", None, "no approval needed", "NET_SAVING")
    assert _plan_facts("en", parts)[0] == {"label": "Estimated cost", "value": "No added cost"}
    assert _plan_facts("zh", parts)[0]["value"] == "无新增成本"
