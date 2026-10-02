"""FUNDING_IN_TRANSIT (ADR-0010): a draw or invoice advance requested today on a facility with a lead time is not cash
yet. One INFO alert per lot that has not landed, with no suggested operation; a WARNING when the reserve is breached on
the days before the lot lands. It goes when the clock closes the landing day.

Every test reads the stored state (lots, cash) as well as the alert."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.alerts import AlertKind, Severity, alerts
from app.domain.models import FundingLot
from tests.alerts.test_repay_alert import approve_cure, to_day34
from tests.nl import conftest as nl_conftest
from tests.nl.conftest import OWNER, Chat

rt = nl_conftest.rt
client = nl_conftest.client

ROOT = Path(__file__).resolve().parents[4]


def transit(client) -> list[dict]:
    return [a for a in client.get("/alerts", headers=OWNER).json()["alerts"] if a["kind"] == "FUNDING_IN_TRANSIT"]


def fund(client, session: str = "tr-1") -> None:
    c = Chat(client, session)
    c.say("Find me the cheapest way to fund the cash gap")
    assert [o["status"] for o in c.say("go ahead")["operations"]] == ["EXECUTED", "EXECUTED"]


def unsettled(rt) -> list[FundingLot]:
    return [lot for lot in rt.store.get_state().lots if not lot.settled]


def test_an_advance_in_transit_is_an_info_alert_with_no_suggested_operation(client, rt):
    fund(client)
    [lot] = unsettled(rt)
    # the day-0 plan's advance: 405,000 − the 150,000 line = 255,000
    assert (lot.facility_id, lot.request_day, lot.arrival_day, lot.principal_fen) == ("FAC-IF", 0, 3, 25_500_000)
    [a] = transit(client)
    assert a["severity"] == "INFO" and a["actionable"] is False and a["suggested"] == []
    assert a["title"] == ("¥255,000.00 requested on day 0 on Invoice financing (onboarded platform) lands on day 3")
    assert a["amount_fen"] == 25_500_000 and a["day"] == 3
    assert a["inputs"]["arrival_day"] == "3" and a["inputs"]["request_day"] == "0"


def test_it_goes_when_the_clock_passes_the_landing_day(client, rt):
    fund(client)
    client.post("/clock/advance", json={"to_day": 2}, headers=OWNER)
    assert len(transit(client)) == 1 and len(unsettled(rt)) == 1  # day 2: the cash is still not in
    client.post("/clock/advance", json={"to_day": 3}, headers=OWNER)
    assert len(unsettled(rt)) == 1  # the clock credits the cash when it closes the landing day
    client.post("/clock/advance", json={"to_day": 4}, headers=OWNER)
    assert unsettled(rt) == [] and transit(client) == []
    assert next(lot for lot in rt.store.get_state().lots if lot.facility_id == "FAC-IF").settled


def test_an_alert_in_transit_cannot_be_acted_on(client, rt):
    fund(client)
    [a] = transit(client)
    logged = len(rt.store.operations())
    r = client.post(f"/alerts/{a['id']}/act", headers=OWNER)
    assert r.status_code >= 400 and len(rt.store.operations()) == logged


def test_a_reserve_breach_before_the_landing_day_is_a_warning_that_names_the_days(client, rt):
    """Cash is below the floor on days 0-2 and the ¥150,000 requested today lands on day 3."""
    s = rt.store.get_state()
    line = next(f for f in s.facilities if f.id == "FAC-LINE")
    lot = FundingLot(id="LOT-T", facility_id="FAC-LINE", principal_fen=15_000_000, remaining_fen=15_000_000,
                     request_day=0, arrival_day=3, settled=False)
    low = s.model_copy(update={
        "cash_fen": 25_000_000, "lots": [lot],
        "facilities": [f.model_copy(update={"drawn_fen": 15_000_000}) if f.id == line.id else f for f in s.facilities]})
    found = alerts(low, rt.store.get_mandate(), rt.store, 0)
    [a] = [x for x in found if x.kind == AlertKind.FUNDING_IN_TRANSIT]
    assert a.severity == Severity.WARNING and a.suggested == [] and not a.actionable
    assert "Days 0 to 2 are below" in a.detail and "day 3" in a.detail and a.inputs["uncovered_from"] == "0"
    assert a.title.startswith("Reserve uncovered until ") and a.title.endswith("cash lands on day 3")
    # the same lot with cash enough to stay above the floor is only INFO
    ok = low.model_copy(update={"cash_fen": 40_000_000})
    [b] = [x for x in alerts(ok, rt.store.get_mandate(), rt.store, 0) if x.kind == AlertKind.FUNDING_IN_TRANSIT]
    assert b.severity == Severity.INFO


def test_the_day_34_cure_leaves_a_transit_alert_that_does_not_count_as_critical(client, rt):
    to_day34(client, rt)
    [breach] = [a for a in client.get("/alerts", headers=OWNER).json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
    approve_cure(client, rt, breach["id"])
    [lot] = unsettled(rt)
    assert (lot.request_day, lot.arrival_day) == (34, 37)
    body = client.get("/alerts", headers=OWNER).json()
    [a] = transit(client)
    assert a["severity"] == "INFO" and "lands on day 37" in a["title"]
    assert body["counts"]["CRITICAL"] == 0 and json.dumps(body["counts"]).count("INFO") == 1


def test_the_demo_script_still_counts_no_critical_alerts():
    """scripts/demo_run.py prints the critical-alert counts it checks: the new INFO alert changes none of them."""
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_run.py")], capture_output=True, text=True,
                         timeout=900, cwd=ROOT, check=False, env={**__import__("os").environ, "PYTHONUTF8": "1"})
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-2000:]
    assert "RESULT: critical alerts after the deal: 0;" in out.stdout and "cure executed and alert cleared: True" in out.stdout
    assert "[INFO] ALERT-TRANSIT-" in out.stdout  # printed, and not counted
