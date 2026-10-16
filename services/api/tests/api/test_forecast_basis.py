"""Wave 3 (wayfinder #65, ticket #72, audit section 16 and 17): the chart says what it counts. Scheduled invoice payments are
"expected", never "confirmed"; overdue payments are excluded; the line's assumed repayment day is the plan's own. The two sums are
sums of amounts that already exist (the log, the projection's postings). Each day carries its net movement."""

from __future__ import annotations

from itertools import pairwise

from tests.alerts.test_repay_alert import OWNER, to_day34
from tests.api.test_ledger_events import BANK
from tests.nl import conftest as nl_conftest

rt = nl_conftest.rt
client = nl_conftest.client


def _cash(client, lang: str = "en") -> dict:
    return client.get("/home", params={"lang": lang}, headers=OWNER).json()["cash"]


def test_the_chart_basis_says_expected_not_confirmed_and_names_the_assumed_repayment_day(client, rt):
    cash = _cash(client)
    assert cash["forecast_basis_text"] == ("Expected invoice payments at their due dates and committed funding; overdue payments are "
                                           "excluded; assumed line repayment in 32 days.")
    assert "confirmed" not in cash["forecast_basis_text"].lower()
    basis = cash["forecast_basis"]
    assert basis["scheduled_receipts_counted"] is True and basis["overdue_excluded"] is True
    assert (basis["assumed_repayment_day"], basis["assumed_repayment_when"]) == (32, "in 32 days")
    assert cash["last_read_when"] == "today"


def test_the_basis_is_in_chinese_too(client, rt):
    cash = _cash(client, "zh")
    assert cash["forecast_basis_text"] == "按到期日预计的发票回款和已承诺的融资；已逾期未付的款项不计入；假定额度于32 天后还款。"
    assert cash["last_read_when"] == "今天"


def test_no_receipt_in_the_log_means_zero_confirmed_and_expected_is_the_sum_the_projection_posted(client, rt):
    cash = _cash(client)
    basis = cash["forecast_basis"]
    assert basis["confirmed_receipts_fen"] == 0 and basis["confirmed_receipts_display"] == "¥0.00"
    posted = sum(e["amount_fen"] for row in cash["series"] for e in row["events"]
                 if e["kind"] in ("RECEIPT", "EARLY_RECEIPT") and e["amount_fen"] > 0)
    assert basis["expected_receipts_fen"] == posted > 0
    assert basis["expected_receipts_display"].startswith("¥")


def test_a_receipt_in_the_log_is_counted_as_confirmed(client, rt):
    o = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()["offer"]["offer_id"]
    client.post(f"/offers/{o}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER)
    client.post(f"/negotiate/{o}", json={"buyer_profile": "cooperative"}, headers=OWNER)
    client.post("/clock/advance", json={"days": 2}, headers=OWNER)
    promised = client.get("/reconciliation", headers=OWNER).json()["reconciliation"]["promised"][0]
    mv = client.get("/mandate", headers=OWNER).json()["mandate"]["version"]
    client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "t-fb1", "idempotency_key": "t-fb1", "mandate_version": mv, "requested_by": "SYSTEM",
        "receivable_id": promised["receivable_id"], "amount_fen": promised["expected_fen"], "bank_reference": "T-FB-1"})
    basis = _cash(client)["forecast_basis"]
    assert basis["confirmed_receipts_fen"] == promised["expected_fen"] == 25_779_000
    # the receipt is in the log, so it is no longer an expected receipt of the horizon
    assert basis["expected_receipts_fen"] > 0


def test_each_chart_day_carries_its_net_movement_and_the_nets_walk_the_closing_cash(client, rt):
    for books in ("day0", "day34"):
        if books == "day34":
            to_day34(client, rt)
        series = _cash(client)["series"]
        for row in series:
            assert row["net_fen"] == sum(e["amount_fen"] for e in row["events"])
            assert row["net_display"].endswith(f"{abs(row['net_fen']) // 100:,}.{abs(row['net_fen']) % 100:02d}")
        for prev, row in pairwise(series):
            assert row["closing_fen"] - prev["closing_fen"] == row["net_fen"], (books, row["day"])


def test_the_plan_series_rows_carry_their_net_too(client, rt):
    plan = _cash(client)["plan_series"]
    assert plan and all("net_fen" in r and "net_display" in r for r in plan)
