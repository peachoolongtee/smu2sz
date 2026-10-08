"""The public-record SME scenario (fixtures/scenarios/public_sme.json; map #58, ticket #61): built from one NEEQ annual
report, anonymised and source-traced (public_sme.SOURCES.md). It loads, projects on day 0, holds at least three buyers and
four receivables, its totals match the filing to the fen, and the three strategy routes answer 200 on it with the flags
on, through the pilot runtime's own `build_runtime` (the state and the unsigned mandate, signed with the demo key)."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.domain.fixtures import load_scenario
from app.domain.models import Mode
from app.financial.trajectory import project

API_DIR = Path(__file__).resolve().parents[2]
SCENARIOS = API_DIR.parents[1] / "fixtures" / "scenarios"
SCRIPT = API_DIR / "scripts" / "pilot_runtime.py"
MANDATE = SCENARIOS / "public_sme.mandate.json"
OWNER = {"X-Owner-Token": "demo-owner-token"}

# The filing's figures the books must match to the fen (SOURCES.md §2–§5).
CASH_FEN = 763_450_382  # 货币资金 ¥7,634,503.82
RECEIVABLES_UNDER_ONE_YEAR_FEN = 3_706_094_754  # 应收账款账龄 1 年以内 ¥37,060,947.54
TOP_FIVE_RECEIVABLES_FEN = {  # 应收账款期末余额前五名
    "BUYER-A": 539_720_257, "BUYER-B": 540_126_737, "BUYER-C": 338_466_049, "BUYER-D": 254_926_735, "BUYER-E": 230_598_209,
}
PAYROLL_YEAR_FEN = 3_058_717_100  # 支付给职工以及为职工支付的现金 ¥30,587,171.00
TAXES_YEAR_FEN = 527_763_303  # 支付的各项税费 ¥5,277,633.03
DEBT_FEN = 3_600_000_000  # 短期借款 ¥21,000,000 principal + 长期借款 ¥15,000,000


@pytest.fixture(scope="module")
def pilot() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pilot_runtime_public_sme", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["pilot_runtime_public_sme"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def state_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The scenario's state alone, as the runtime script reads it (`--state` is a FinancialState, not a scenario)."""
    raw = json.loads((SCENARIOS / "public_sme.json").read_text(encoding="utf-8"))
    path = tmp_path_factory.mktemp("public_sme") / "state.json"
    path.write_text(json.dumps(raw["state"]), encoding="utf-8")
    return path


@pytest.fixture
def runtime(pilot: ModuleType, state_file: Path) -> Iterator[Runtime]:
    rt = pilot.build_runtime(state_file, MANDATE)
    set_runtime(rt)
    yield rt
    set_runtime(None)


@pytest.fixture
def api(runtime: Runtime, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.api import strategy_collections, strategy_curve, strategy_envelope
    from app.main import app

    for flag in ("ENVELOPE", "PRICE_CURVE", "COLLECTIONS_WORTH", "PILOT_JOURNAL"):
        monkeypatch.setenv(f"FEATURE_{flag}", "1")
    for module in (strategy_collections, strategy_curve, strategy_envelope):
        module.clear_cache()
    yield TestClient(app, headers=OWNER)
    for module in (strategy_collections, strategy_curve, strategy_envelope):
        module.clear_cache()


def test_the_scenario_loads_with_buyers_and_receivables_and_no_real_names() -> None:
    state, mandate = load_scenario("public_sme")
    assert state.org_id == mandate.org_id == "SME-PUBLIC-1" and state.as_of_day == 0 and state.scenario is None
    buyers = {c.id for c in state.counterparties if c.role == "BUYER"}
    assert len(buyers) >= 3 and all(c.known for c in state.counterparties)
    assert len(state.receivables) >= 4 and {r.counterparty_id for r in state.receivables} <= buyers
    assert all(r.status == "OPEN" and r.confirmed for r in state.receivables)
    assert any(r.issue_day + r.terms_days < 0 for r in state.receivables), "the surveys' overdue share: one invoice past due"
    names = " ".join(c.name for c in state.counterparties)
    assert "Buyer A" in names and not any(ch > "一" and ch < "鿿" for ch in names), "no Chinese company names"
    assert state.monthly_ebitda_fen > 0 and mandate.min_cash_fen < state.cash_fen


def test_the_books_totals_match_the_filing_to_the_fen() -> None:
    state, mandate = load_scenario("public_sme")
    assert state.cash_fen == CASH_FEN
    assert sum(r.face_fen for r in state.receivables) == RECEIVABLES_UNDER_ONE_YEAR_FEN
    by_buyer: dict[str, int] = {}
    for r in state.receivables:
        by_buyer[r.counterparty_id] = by_buyer.get(r.counterparty_id, 0) + r.face_fen
    assert {b: by_buyer[b] for b in TOP_FIVE_RECEIVABLES_FEN} == TOP_FIVE_RECEIVABLES_FEN
    payroll = [f for f in state.flows if f.kind == "PAYROLL"]
    assert len(payroll) == 4 and all(-f.amount_fen == round(PAYROLL_YEAR_FEN / 12) for f in payroll)
    taxes = [f for f in state.flows if f.label.startswith("VAT")]
    assert len(taxes) == 4 and all(-f.amount_fen == round(TAXES_YEAR_FEN / 12) for f in taxes)
    assert sum(d.principal_fen for d in state.debts) + sum(f.drawn_fen for f in state.facilities) == DEBT_FEN
    # the floor is one month of payroll, taxes and overheads: what is paid even if no customer pays
    overheads = next(f for f in state.flows if f.kind == "OPERATING")
    assert mandate.min_cash_fen == round(PAYROLL_YEAR_FEN / 12) + round(TAXES_YEAR_FEN / 12) - overheads.amount_fen
    assert all(isinstance(v, int) for v in (state.cash_fen, mandate.min_cash_fen, mandate.max_aggregate_forward_concession_fen))


def test_the_scenario_projects_on_day_zero_and_alerts_name_the_breach_and_the_overdue_invoices() -> None:
    from app.alerts import alerts
    from app.persistence import InMemoryLedgerStore

    state, mandate = load_scenario("public_sme")
    t = project(state, [], [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    assert t.horizon_days == mandate.horizon_days and t.days[0].opening_fen == state.cash_fen
    assert all(m.ebitda_fen == state.monthly_ebitda_fen for m in t.months)
    store = InMemoryLedgerStore()
    store.put_state(state)
    store.put_mandate(mandate)
    found = alerts(state, mandate, store, 0)
    kinds = {a.kind for a in found}
    assert "RESERVE_BREACH_AHEAD" in kinds and "RECEIVABLE_PAST_DUE" in kinds
    past_due = {a.receivable_id for a in found if a.kind == "RECEIVABLE_PAST_DUE"}
    assert past_due == {r.id for r in state.receivables if r.issue_day + r.terms_days < 0}


def test_the_pilot_runtime_builds_on_the_scenario_not_the_golden_books(runtime: Runtime) -> None:
    state, mandate = runtime.store.get_state(), runtime.store.get_mandate()
    assert state.org_id == mandate.org_id == "SME-PUBLIC-1" and runtime.day == 0
    assert mandate.signature_hex and mandate.public_key_hex == runtime.owner_key_hex
    assert runtime.store.operations() == [] and runtime.store.commitments() == []


def test_the_three_strategy_routes_answer_200_with_the_flags_on(api: TestClient) -> None:
    envelope = api.get("/buyers/BUYER-A/envelope")
    assert envelope.status_code == 200, envelope.text
    body = envelope.json()
    assert body["hypothetical"] is True and (body["refused"] or body["primary"])
    curve = api.get("/cash/price-curve")
    assert curve.status_code == 200, curve.text
    assert curve.json()["sentence"] and curve.json()["day"] == 0
    worth = api.get("/receivables/worth")
    assert worth.status_code == 200, worth.text
    assert worth.json()["top_action"] and len(worth.json()["rows"]) >= 4


def test_envelope_of_buyer_a_on_90_day_terms_is_scanned_to_100_and_the_zone_has_the_rows(runtime: Runtime) -> None:
    """The envelope's terms range runs two steps past the terms in force (map #58, ticket #64): Buyer A's 90 days were the
    range's own edge, so the first reading said "no longer payment terms" of the range, not of the books."""
    from app.books import books_from_store
    from app.strategy.envelope import envelope_answer, envelope_facts

    facts = envelope_facts(books_from_store(runtime.store), runtime.store.get_mandate(), store=runtime.store, day=runtime.day,
                           buyer_id="BUYER-A", zone=True, trusted_owner_key_hex=runtime.owner_key_hex,
                           commitments=tuple(runtime.store.commitments()))
    a = envelope_answer(facts, "en")
    assert a.refused is None and facts.current_terms == 90
    assert [z.terms_days for z in a.zone][-3:] == [90, 95, 100]
    terms = {lv.key: lv for lv in a.levers if lv.key.startswith("terms")}
    assert set(terms) == {"terms_alone", "terms_budget_ignored", "terms_with_price"}
    # every terms lever passes both new steps; the engine finds no wall inside the range, so each ends at its top
    assert all(lv.maximum == 100 and lv.confirmed and lv.wall is None and lv.next_step is None for lv in terms.values())
    assert {p.package.terms_days for p in a.packages} == {90, 95, 100}
    assert a.primary == ("You can live with: up to 100-day terms, or early payment at up to 0.10% on ¥5,397,202.57; "
                         "a rebate up to 1.50%.")
