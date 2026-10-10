"""The display stamps added for the simplification (`lands_day`, `available_from_day`, `shortfall_fen`, `worst_day`,
`not_executable_reason`) are read only by the pages: the engine never reads them back (stability mode). On the
golden books and on the day-34 books of the demo path the plan id, its cost, its action keys and the comparison's
order and costs are fixed figures, and removing every stamp from the actions changes neither the plan's identity nor
the projection of its legs."""

from __future__ import annotations

from app.books import current_books
from app.domain.fixtures import load_scenario
from app.domain.models import FundingAction, Mode
from app.financial import project
from app.funding import compare, plan
from app.funding.search import action_key, plan_id
from app.mandate import load_signed_mandate
from tests.alerts.test_repay_alert import to_day34
from tests.nl import conftest as nl_conftest

rt = nl_conftest.rt  # the in-memory runtime and the app client of the chat tests
client = nl_conftest.client

STAMPS = ("lands_day", "available_from_day")
ROW_STAMPS = {"shortfall_fen", "worst_day", "not_executable_reason"}


def _bare(actions: list[FundingAction]) -> list[FundingAction]:
    return [a.model_copy(update={k: None for k in STAMPS}) for a in actions]


def _rows(rows) -> list[tuple]:
    """What a row is without its stamps: key, cost, result, reasons, breach day, whether it can run today."""
    return [(r.key, r.cost_fen, r.result.value, [c.value for c in r.reasons], r.breach_day, r.executable_now) for r in rows]


def _check(state, obligations, mandate, *, plan_cost: int, plan_keys: tuple, rows: list[tuple]) -> None:
    p = plan(state, obligations, mandate)
    assert p.total_cost_fen == plan_cost and action_key(p.actions) == plan_keys
    bare = _bare(list(p.actions))
    assert action_key(bare) == action_key(p.actions)
    assert plan_id(p.basis, bare, state, mandate) == p.id
    # the engine projects the same legs to the same cash with or without the stamps
    stamped = project(state, obligations, list(p.actions), Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    plain = project(state, obligations, bare, Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    assert [(d.day, d.closing_fen) for d in stamped.days] == [(d.day, d.closing_fen) for d in plain.days]
    got = compare(state, obligations, mandate)
    assert _rows(got) == rows
    # a row's own dump without its stamps is the engine's row: nothing else moved
    for r in got:
        dump = r.model_dump(exclude=ROW_STAMPS | {"actions"})
        assert set(dump) >= {"key", "label", "components", "cost_fen", "cost_display", "result", "note"}
        assert [action_key([a])[0] for a in r.actions] == [action_key([b])[0] for b in _bare(list(r.actions))]


def test_the_golden_books_plan_and_comparison_do_not_depend_on_the_stamps():
    state, _ = load_scenario()
    _check(state, [], load_signed_mandate(), plan_cost=311_393,
           plan_keys=(("DRAW", "FAC-LINE", 0, 15_000_000, "", 32, -1),
                      ("FINANCE_INVOICE", "FAC-IF", 0, 25_500_000, "RCV-A", -1, -1)),
           rows=[("full_discount", 504_000, "ADMISSIBLE", [], None, False),
                 ("line_partial_early_pay", 393_881, "ADMISSIBLE", [], None, False),
                 ("router_optimum", 311_393, "SELECTED", [], None, True),
                 ("line_guaranteed_loan", None, "NOT_ADMISSIBLE", ["UNCOMMITTED_FACILITY", "LEAD_TIME_TOO_LONG"], None, True),
                 ("line_only", 84_164, "NOT_ADMISSIBLE", ["RESERVE_BREACH"], 12, True)])


def test_the_day34_books_plan_and_comparison_do_not_depend_on_the_stamps(client, rt):
    to_day34(client, rt)
    books = current_books(rt.store.get_state(), rt.store.commitments())
    mandate = rt.store.get_mandate()
    _check(books.state, books.with_([]), mandate, plan_cost=170_610,
           plan_keys=(("FINANCE_INVOICE", "FAC-IF", 34, 8_000_000, "RI:BUYER-1:32", -1, -1),
                      ("FINANCE_INVOICE", "FAC-IF", 34, 12_000_000, "RI:BUYER-1:2", -1, -1)),
           rows=[("full_discount", 504_000, "ADMISSIBLE", [], None, False),
                 ("router_optimum", 170_610, "SELECTED", [], None, True)])
