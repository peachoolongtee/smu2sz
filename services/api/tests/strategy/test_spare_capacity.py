"""The additional need FLOW could still support (map #88, ticket #96, brief F.3): the Demo's four figures, the criterion at
the boundary, the buyer's early-payment source off the copy, the search rule (monotonicity is not assumed), the
refusal, the cache. The search reads the router on labelled copies; the books are never touched."""

from __future__ import annotations

import os
import threading
import time

import pytest

import app.strategy.capacity as capacity_module
from app.books import Books
from app.domain.models import FacilityKind, FinancialState, Mandate
from app.funding import plan as real_plan
from app.persistence import InMemoryLedgerStore
from app.strategy.capacity import (
    CRITERIA,
    REFUSED,
    SCAN_BUDGET,
    YUAN_STEP_FEN,
    clear_cache,
    last_true,
    refused_sentence,
    shape_text,
    spare_capacity,
)

from .exposure_books import ASKED, OPTION_A, OPTION_B, OWNER_KEY, golden

YUAN = 100  # fen
K = 1_000 * YUAN  # ¥1,000


@pytest.fixture(autouse=True)
def _fresh_cache():
    clear_cache()


def _x(package=None, criterion="R-TODAY"):
    books, mandate = golden()
    return spare_capacity(books, mandate, 0, (), package, criterion=criterion, trusted_owner_key_hex=OWNER_KEY)


# ---------------------------------------------------------------- the four figures (r4 section 3)


def test_the_four_demo_figures_and_what_binds_each():
    current, asked, a, b = _x(), _x(ASKED), _x(OPTION_A), _x(OPTION_B)
    assert [r.x_star_fen for r in (current, asked, a, b)] == [8_100_000, 1_400_000, 0, 6_200_000]  # ¥81,000 / 14,000 / 0 / 62,000
    # the router's own words for why the next ¥1,000 fails
    assert "RI:BUYER-1:2" in current.binding_reason and "15.49%" in current.binding_reason
    assert "15.00% ceiling" in current.binding_reason
    assert "RI:BUYER-1:32 is not an invoice the executor can finance today" in asked.binding_reason
    assert "15.49%" in a.binding_reason and "ceiling" in a.binding_reason
    assert "RI:BUYER-1:32 is not an invoice the executor can finance today" in b.binding_reason
    for r in (current, asked, a, b):
        assert (r.shape, r.criterion, r.step_fen, r.refused_text) == ("S1", "R-TODAY", K, None)


def test_the_as_issued_reading_is_labelled_and_larger_where_later_invoices_can_be_financed():
    rows = [_x(p, "R-AS-ISSUED").x_star_fen for p in (None, ASKED, OPTION_A, OPTION_B)]
    assert rows == [8_100_000, 25_000_000, 0, 9_500_000]  # ¥81,000 / ¥250,000 / ¥0 / ¥95,000 (r4 section 3)
    assert "an assumption" in _x(ASKED, "R-AS-ISSUED").shape_text and "an assumption" not in _x(ASKED).shape_text


def test_option_a_leaves_no_room_for_a_further_payment_without_the_owner():
    r = _x(OPTION_A)
    assert r.x_star_fen == 0 and r.refused_text is None  # zero is an answer; "none" is a refusal
    assert r.plan_at_x is not None and r.plan_at_x.admissible and not r.plan_next.executable_now


# ---------------------------------------------------------------- the criterion at the boundary


@pytest.mark.parametrize("package", [None, ASKED, OPTION_A, OPTION_B])
def test_the_plan_at_x_passes_the_criterion_and_the_plan_one_step_up_does_not(package):
    r = _x(package)
    at, nxt = r.plan_at_x, r.plan_next
    assert at is not None and nxt is not None
    assert at.admissible and not at.needs_owner_approval and at.executable_now
    assert not (nxt.admissible and not nxt.needs_owner_approval and nxt.executable_now)
    assert r.binding_reason  # a failing plan always has a reason in the router's words


def test_the_buyers_early_pay_source_is_absent_from_every_copy_the_router_sees(monkeypatch: pytest.MonkeyPatch):
    seen: list[FinancialState] = []

    def spy(state, obligations, mandate, *args, **kwargs):
        seen.append(state)
        return real_plan(state, obligations, mandate, *args, **kwargs)

    monkeypatch.setattr(capacity_module, "plan", spy)
    books, mandate = golden()
    assert any(f.kind == FacilityKind.BUYER_EARLY_PAY for f in books.state.facilities)
    r = spare_capacity(books, mandate, 0, ())
    assert r.x_star_fen == 8_100_000 and len(seen) == r.evaluations
    assert all(not any(f.kind == FacilityKind.BUYER_EARLY_PAY for f in s.facilities) for s in seen)
    # and the copy is the books plus one outflow of X today that does not come back
    flows = sorted((f.amount_fen for s in seen for f in s.flows if f.id.startswith("SPARE-NEED")), reverse=True)
    assert flows and all(x < 0 for x in flows)
    assert books.state.model_dump_json() == golden()[0].state.model_dump_json()  # the books themselves are untouched


def test_with_the_buyers_early_pay_left_in_the_answer_would_be_different():
    """Why the rule exists: left on the copy, the cheapest plan is an early payment only the buyer can agree to."""
    books, mandate = golden()
    kept = books.state.model_copy(update={"facilities": books.state.facilities})
    from app.strategy.capacity import _with_need

    plan_with = real_plan(_with_need(kept, 8_200_000), books.with_([]), mandate)
    assert any(a.kind.value == "EARLY_PAY" for a in plan_with.actions) or not plan_with.executable_now


# ---------------------------------------------------------------- the sentences, always printed


def test_the_shape_and_criterion_sentence_is_always_there_in_both_languages():
    r = _x()
    assert r.shape_text == shape_text("S1", "R-TODAY", "en")
    assert "a one-off payment of X today that does not come back within the horizon" in r.shape_text
    assert "without another facility or your approval" in r.shape_text
    zh = shape_text("S1", "R-TODAY", "zh")
    assert "一次性付款" in zh and "批准" in zh
    for c in CRITERIA:
        assert shape_text("S1", c, "en") and shape_text("S1", c, "zh")
    assert refused_sentence("zh").startswith("无：") and refused_sentence("en") == REFUSED[0]


# ---------------------------------------------------------------- the refusal


def test_today_books_that_already_need_the_owner_are_refused_not_zero(books_day34: Books, rt_day34):
    r = spare_capacity(books_day34, rt_day34.store.get_mandate(), 34, rt_day34.store.commitments())
    assert r.x_star_fen is None and r.plan_at_x is None and r.plan_next is None
    assert r.refused_text == "none: today's books already need the owner or a new facility"
    assert r.shape_text  # the sentence is printed with a refusal too


def test_books_with_no_admissible_plan_are_refused():
    books, mandate = golden()
    bare = books.state.model_copy(update={"facilities": [
        f.model_copy(update={"limit_fen": 0}) for f in books.state.facilities if f.kind != FacilityKind.BUYER_EARLY_PAY]})
    r = spare_capacity(Books(state=bare, obligations=()), mandate, 0, ())
    assert r.x_star_fen is None and r.refused_text == REFUSED[0] and r.binding_reason == ""


def test_an_undefined_shape_or_criterion_is_refused():
    books, mandate = golden()
    with pytest.raises(ValueError, match="shape"):
        spare_capacity(books, mandate, 0, (), shape="S2")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="criterion"):
        spare_capacity(books, mandate, 0, (), criterion="R-NEVER")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="owner's key"):
        spare_capacity(books, mandate, 0, (), ASKED)


# ---------------------------------------------------------------- the search rule: monotonicity is not assumed


def _counting(ok):
    calls: list[int] = []

    def probe(v: int) -> bool:
        calls.append(v)
        return ok(v)

    return probe, calls


def test_a_monotone_boundary_is_found_by_bisection_with_both_neighbours_checked():
    grid = range(0, 100_001, 100)
    probe, calls = _counting(lambda v: v <= 33_300)
    found = last_true(grid, probe)
    assert (found.value, found.confirmed, found.scanned) == (33_300, True, False)
    assert len(set(calls)) <= 14  # log2(1001) probes + the first value + the two neighbours
    assert {33_400, 33_500} <= set(calls)  # both values past the boundary were asked


def test_a_neighbour_that_disagrees_triggers_a_scan_and_the_best_passing_value_wins():
    # the first probe (500) fails, so bisection lands on 400; but 401 fails and 402 passes again (a step in the effective
    # rate), up to 650: the disagreement of the neighbours is what sends the search to a scan
    grid = range(0, 1_001, 1)
    probe, calls = _counting(lambda v: v <= 400 or (402 <= v <= 650 and v != 500))
    found = last_true(grid, probe)
    assert found.scanned and not found.confirmed
    assert found.value == 650
    assert len(set(calls)) <= 1_001


def test_a_scan_over_a_large_grid_is_bounded_and_ends_at_the_grids_resolution():
    grid = range(100_000)
    probe, calls = _counting(lambda v: v <= 30_000 or (30_002 <= v <= 64_000 and v != 50_000))
    found = last_true(grid, probe)
    assert found.scanned and found.value == 64_000
    assert len(set(calls)) < 6 * SCAN_BUDGET  # coarse points, then the cell above the best one, never the whole grid


def test_nothing_passes_when_the_first_value_fails():
    found = last_true(range(10), lambda v: False)
    assert (found.value, found.confirmed) == (None, True)
    assert last_true(range(0), lambda v: True).value is None


def test_the_search_on_the_demo_asks_the_router_about_ten_to_twenty_times():
    for package in (None, ASKED, OPTION_A, OPTION_B):
        r = _x(package)
        assert 8 <= r.evaluations <= 20, (package, r.evaluations)
        assert r.scanned is False and r.ceiling_fen == 60_000_000  # ¥600,000: the cash above the floor + the committed limits


# ---------------------------------------------------------------- the cache, single-flight


def test_the_answer_is_cached_and_a_second_request_waits_for_the_first(monkeypatch: pytest.MonkeyPatch):
    books, mandate = golden()
    calls: list[int] = []
    real = capacity_module._search

    def slow(*args, **kwargs):
        calls.append(1)
        time.sleep(0.3)
        return real(*args, **kwargs)

    monkeypatch.setattr(capacity_module, "_search", slow)
    out: list[object] = []
    threads = [threading.Thread(target=lambda: out.append(spare_capacity(books, mandate, 0, ()))) for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert len(calls) == 1 and len(out) == 4 and all(o is out[0] for o in out)
    assert spare_capacity(books, mandate, 0, ()) is out[0]  # and now from the cache
    other = spare_capacity(books, mandate, 0, (), criterion="R-AS-ISSUED")
    assert other is not out[0] and len(calls) == 2  # another criterion is another question


def test_a_different_package_is_a_different_key():
    assert _x(ASKED) is not _x(OPTION_B)
    assert _x(ASKED) is _x(ASKED)


# ---------------------------------------------------------------- the public-record SME: what one search costs


@pytest.mark.skipif(os.environ.get("SKIP_PERF_BENCH") == "1", reason="SKIP_PERF_BENCH=1: about half a minute of router runs")
def test_the_search_on_the_public_record_sme_finishes_and_is_recorded():
    import json
    from pathlib import Path

    from app.books import current_books

    raw = json.loads((Path(__file__).resolve().parents[4] / "fixtures" / "scenarios" / "public_sme.json").read_text("utf-8"))
    state = FinancialState.model_validate_json(json.dumps(raw["state"]))
    mandate = Mandate.model_validate_json(json.dumps(raw["mandate"]))
    r = spare_capacity(current_books(state, []), mandate, 0, ())
    assert r.x_star_fen is not None and r.x_star_fen % YUAN_STEP_FEN == 0
    assert r.plan_at_x is not None and r.plan_at_x.admissible and r.plan_at_x.executable_now
    assert r.evaluations <= 20, r.evaluations
    print(f"public SME: X* {r.x_star_fen}, {r.evaluations} router runs, {r.seconds} s")


def test_the_ledger_store_import_is_not_needed():
    assert InMemoryLedgerStore  # the search takes the books and the commitments, never a store
