"""Concentration (map #88 Phase 1; brief G.1; properties P6 and P7): four separate shares, never a score, and context, not
mandate. The Demo's figures are pinned; the share rules are checked against an independent computation on random books."""

from __future__ import annotations

import ast
from fractions import Fraction
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from app.books import Books, current_books
from app.domain.fixtures import load_scenario
from app.domain.models import Counterparty, Receivable
from app.persistence.records import CustomerInputRecord
from app.strategy import concentration as module
from app.strategy.concentration import concentration
from app.strategy.inputs import CustomerInputs, inputs_from_rows
from app.strategy.words import buyer_short, share_bp, share_text, whole_yuan
from tests.api.conftest import english_leaks

GOLDEN, _MANDATE = load_scenario()
BUYERS = ["BUYER-1", "BUYER-2", "BUYER-3"]


def _books(receivables: list[Receivable], *, day: int = 0, recurring: bool = False) -> Books:
    """The golden books with only the given receivables (and, unless asked, no recurring invoices), a third buyer added."""
    cps = [*GOLDEN.counterparties, Counterparty(id="BUYER-3", name="Shenzhen Mart Co.", role="BUYER")]
    state = GOLDEN.model_copy(update={
        "receivables": receivables, "counterparties": cps, "as_of_day": day,
        "recurring_invoices": GOLDEN.recurring_invoices if recurring else []})
    return current_books(state, [])


def _rcv(i: int, buyer: str, face: int, *, due: int = 40, settled: int = 0, status: str = "OPEN") -> Receivable:
    extra: dict[str, Any] = {"advance_fen": 1, "advance_facility_id": "FAC-IF"} if status == "FINANCED" else {}
    return Receivable(id=f"R-{i}", counterparty_id=buyer, face_fen=face, issue_day=due - 30, terms_days=30, status=status,  # type: ignore[arg-type]
                      settled_fen=settled, **extra)


def _aggregate(buyer: str) -> CustomerInputs:
    return inputs_from_rows([CustomerInputRecord(
        org_id="O", counterparty_id=buyer, field="aggregate", value_json="true", provenance="OWNER_ENTERED", source_ref="",
        entered_by="OWNER", entered_day=0, state_version=1, seq=1)])


# ---------------------------------------------------------------- the Demo's figures (J.2, I.3 (b))


def test_the_demo_day0_is_foshan_100_percent_of_what_is_owed_and_nothing_due_in_30_days(books_day0: Books) -> None:
    c = concentration(books_day0, "BUYER-1", 0)
    assert c.sentence == ("Foshan is 100% of what you are owed today (¥420,000). "
                          "No customer receipts are due in the next 30 days.")
    assert (c.ar_share_bp, c.ar_buyer_fen, c.ar_total_fen) == (10_000, 42_000_000, 42_000_000)
    assert (c.receipts_share_bp, c.receipts_total_fen) == (None, 0)
    assert (c.receipts_from_day, c.receipts_to_day) == (0, 30)
    assert c.buyer_name == "Foshan" and c.excluded_aggregates == [] and c.aggregate_note is None


def test_the_demo_twin_in_chinese_says_the_same(books_day0: Books) -> None:
    c = concentration(books_day0, "BUYER-1", 0, lang="zh")
    assert c.sentence == "Foshan占您目前全部应收款的 100%（¥420,000）。未来 30 天内没有客户回款到期。"
    en = concentration(books_day0, "BUYER-1", 0)
    assert c.model_dump(exclude={"lang", "buyer_name"} | {k for k in c.model_dump() if k.endswith(("_text", "_reason"))}
                        | {"sentence", "aggregate_note"}) == en.model_dump(
        exclude={"lang", "buyer_name"} | {k for k in en.model_dump() if k.endswith(("_text", "_reason"))}
        | {"sentence", "aggregate_note"})
    for text in (c.ar_text, c.receipts_text, c.sentence, c.annual_sales_reason, c.contribution_reason):
        assert english_leaks({"x": text}, ["Foshan"]) == [], text


def test_a_buyer_with_no_receivable_owes_nothing_and_has_no_share_to_state(books_day0: Books) -> None:
    c = concentration(books_day0, "BUYER-2", 0)
    assert c.ar_share_bp == 0 and c.ar_text == "Dongguan owes you nothing today."


def test_day34_the_next_30_days_receipt_is_foshans_alone(books_day34: Books) -> None:
    c = concentration(books_day34, "BUYER-1", 34)
    assert c.ar_share_bp == 10_000 and c.ar_buyer_fen == 100_280_000  # RCV-A's ¥162,800 still outstanding + two issued invoices of ¥420,000
    assert (c.receipts_from_day, c.receipts_to_day) == (34, 64)
    assert c.receipts_share_bp == 10_000 and c.receipts_buyer_fen == 42_000_000  # RI:BUYER-1:2 on day 47; RCV-A is overdue
    assert c.receipts_text == "Foshan is 100% of the receipts due in the next 30 days (¥420,000)."


def test_phase_1_leaves_sales_and_contribution_none_each_with_its_reason(books_day0: Books) -> None:
    c = concentration(books_day0, "BUYER-1", 0)
    assert c.annual_sales_share_bp is None and c.contribution_share_bp is None
    assert c.annual_sales_reason == "Annual sales are not known for every customer, so Foshan's share of sales is not shown."
    assert "needs a margin for every customer" in c.contribution_reason


# ---------------------------------------------------------------- the share rules (P6, P7)


def test_a_zero_total_has_no_share_and_says_so() -> None:
    books = _books([])
    c = concentration(books, "BUYER-1", 0)
    assert c.ar_share_bp is None and c.ar_text == "You are owed nothing today."
    assert c.ar_text.replace("today.", "today") == "You are owed nothing today"
    assert c.receipts_share_bp is None and c.receipts_text == "No customer receipts are due in the next 30 days."
    zh = concentration(books, "BUYER-1", 0, lang="zh")
    assert zh.ar_text == "您目前没有应收款。"


def test_three_equal_shares_are_each_33_point_3_and_nothing_is_adjusted_to_add_to_100() -> None:
    books = _books([_rcv(i, b, 10_000_000) for i, b in enumerate(BUYERS)])
    cs = [concentration(books, b, 0) for b in BUYERS]
    assert [c.ar_share_bp for c in cs] == [3333, 3333, 3333]
    assert cs[0].ar_text == "Foshan is 33.3% of what you are owed today (¥100,000)."


def test_only_open_and_financed_receivables_count_overdue_ones_do_and_settled_ones_do_not() -> None:
    rows = [_rcv(0, "BUYER-1", 60_000_000, due=-5),  # overdue: still AR
            _rcv(1, "BUYER-1", 10_000_000, status="FINANCED"),  # the buyer still owes it
            _rcv(2, "BUYER-2", 30_000_000),
            _rcv(3, "BUYER-2", 99_000_000, settled=99_000_000, status="SETTLED"),  # history
            _rcv(4, "BUYER-3", 50_000_000, status="FAILED")]  # not AR
    c = concentration(_books(rows, day=0), "BUYER-1", 0)
    assert (c.ar_buyer_fen, c.ar_total_fen) == (70_000_000, 100_000_000) and c.ar_share_bp == 7000


def test_a_part_paid_invoice_counts_what_is_still_outstanding_only() -> None:
    rows = [_rcv(0, "BUYER-1", 40_000_000, settled=30_000_000), _rcv(1, "BUYER-2", 10_000_000)]
    c = concentration(_books(rows), "BUYER-1", 0)
    assert (c.ar_buyer_fen, c.ar_total_fen, c.ar_share_bp) == (10_000_000, 20_000_000, 5000)


def test_unissued_recurring_invoices_are_not_receivables() -> None:
    with_recurring = concentration(_books([_rcv(0, "BUYER-2", 10_000_000)], recurring=True), "BUYER-1", 0)
    assert with_recurring.ar_total_fen == 10_000_000 and with_recurring.ar_share_bp == 0


def test_day_29_is_in_the_30_day_window_day_30_is_out_and_an_overdue_invoice_never_counts() -> None:
    rows = [_rcv(0, "BUYER-1", 10_000_000, due=29),  # due on day 29: in
            _rcv(1, "BUYER-2", 30_000_000, due=30),  # due on day 30: out
            _rcv(2, "BUYER-3", 50_000_000, due=-1)]  # overdue: the engine counts no receipt
    c = concentration(_books(rows), "BUYER-1", 0)
    assert (c.receipts_buyer_fen, c.receipts_total_fen, c.receipts_share_bp) == (10_000_000, 10_000_000, 10_000)
    later = concentration(_books(rows, day=1), "BUYER-2", 1)  # at day 1 the window is [1, 31): day 30 is in
    assert (later.receipts_buyer_fen, later.receipts_total_fen) == (30_000_000, 40_000_000)
    assert later.receipts_share_bp == 7500


@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 2), st.integers(1, 5_000_000_000), st.integers(0, 100),
                          st.sampled_from(["OPEN", "OPEN", "OPEN", "SETTLED", "FAILED"]), st.integers(-20, 50)),
                min_size=0, max_size=8))
def test_p6_p7_shares_are_exact_bounded_sum_to_one_and_follow_the_open_ar(rows: list[tuple[int, int, int, str, int]]) -> None:
    receivables = []
    for i, (who, face, settled_pct, status, due) in enumerate(rows):
        settled = face if status == "SETTLED" else face * min(settled_pct, 99) // 100
        receivables.append(_rcv(i, BUYERS[who], face, due=due, settled=settled, status=status))
    books = _books(receivables)
    open_ = [r for r in receivables if r.status == "OPEN"]
    total = sum(r.outstanding_fen for r in open_)
    due_in = [r for r in open_ if 0 <= r.due_day < 30]
    due_total = sum(r.outstanding_fen for r in due_in)
    shares, due_shares = [], []
    for b in BUYERS:
        c = concentration(books, b, 0)
        mine = sum(r.outstanding_fen for r in open_ if r.counterparty_id == b)
        mine_due = sum(r.outstanding_fen for r in due_in if r.counterparty_id == b)
        assert (c.ar_buyer_fen, c.ar_total_fen) == (mine, total)
        assert (c.receipts_buyer_fen, c.receipts_total_fen) == (mine_due, due_total)
        for bp_, denominator, part in ((c.ar_share_bp, total, mine), (c.receipts_share_bp, due_total, mine_due)):
            if denominator == 0:
                assert bp_ is None
                continue
            assert bp_ is not None and 0 <= bp_ <= 10_000 and bp_ == share_bp(Fraction(part, denominator))
            assert (bp_ == 10_000) == (part == denominator)  # "all" only when exactly all
            assert (bp_ == 0) == (part == 0)
        shares.append(Fraction(mine, total) if total else None)
        due_shares.append(Fraction(mine_due, due_total) if due_total else None)
    for xs in (shares, due_shares):
        if xs[0] is not None:
            assert sum((x for x in xs if x is not None), Fraction(0)) == 1  # exact: nothing adjusted


@settings(max_examples=40, deadline=None)
@given(st.integers(1, 10**9), st.integers(1, 10**9), st.integers(1, 10**9))
def test_more_owed_by_a_buyer_never_lowers_that_buyers_share(base: int, other: int, extra: int) -> None:
    before = concentration(_books([_rcv(0, "BUYER-1", base), _rcv(1, "BUYER-2", other)]), "BUYER-1", 0)
    after = concentration(_books([_rcv(0, "BUYER-1", base + extra), _rcv(1, "BUYER-2", other)]), "BUYER-1", 0)
    assert before.ar_share_bp is not None and after.ar_share_bp is not None
    assert after.ar_share_bp >= before.ar_share_bp


@settings(max_examples=40, deadline=None)
@given(st.integers(1, 10**9), st.integers(1, 10**9), st.integers(1, 10**9))
def test_a_settled_invoice_is_neutral(a: int, b: int, history: int) -> None:
    rows = [_rcv(0, "BUYER-1", a), _rcv(1, "BUYER-2", b)]
    without = concentration(_books(rows), "BUYER-1", 0)
    with_ = concentration(_books([*rows, _rcv(2, "BUYER-2", history, settled=history, status="SETTLED")]), "BUYER-1", 0)
    assert (without.ar_share_bp, without.ar_total_fen) == (with_.ar_share_bp, with_.ar_total_fen)


# ---------------------------------------------------------------- the display rules (ADR-0002)


def test_100_only_when_exactly_one_and_rounding_never_hides_the_difference() -> None:
    assert share_text(Fraction(1)) == "100%" and share_text(Fraction(0)) == "0%"
    assert share_text(Fraction(9996, 10_000)) == "over 99.9%" and share_text(Fraction(4, 10_000)) == "under 0.1%"
    assert share_text(Fraction(1, 3)) == "33.3%" and share_text(Fraction(1, 2)) == "50.0%"
    assert share_text(Fraction(1, 8)) == "12.5%" and share_text(Fraction(1, 800)) == "0.1%"  # 0.125% rounds half up
    assert share_text(Fraction(9996, 10_000), "zh") == "高于 99.9%"
    assert share_bp(Fraction(1)) == 10_000 and share_bp(Fraction(99_999, 100_000)) == 9999
    assert share_bp(Fraction(1, 100_000)) == 1 and share_bp(Fraction(0)) == 0
    assert share_bp(Fraction(1, 20_000)) == 1  # 0.5 bp: half-up, and a nonzero share is never shown as 0


def test_the_wording_helpers() -> None:
    assert whole_yuan(42_000_000) == "¥420,000" and whole_yuan(42_000_050) == "¥420,000.50"
    assert buyer_short("Foshan Home Retail Co.") == "Foshan" and buyer_short("Acme") == "Acme"


# ---------------------------------------------------------------- aggregates


def test_an_aggregate_stays_in_the_denominators_and_is_named() -> None:
    rows = [_rcv(0, "BUYER-1", 30_000_000, due=10), _rcv(1, "BUYER-2", 90_000_000, due=10), _rcv(2, "BUYER-3", 30_000_000, due=10)]
    books = _books(rows)
    plain = concentration(books, "BUYER-1", 0)
    assert plain.ar_share_bp == 2000 and plain.excluded_aggregates == []
    c = concentration(books, "BUYER-1", 0, _aggregate("BUYER-2"))
    assert (c.ar_total_fen, c.ar_all_fen, c.ar_share_bp) == (150_000_000, 150_000_000, 2000)  # a 20% buyer stays 20%
    assert (c.receipts_total_fen, c.receipts_share_bp) == (150_000_000, 2000) and c.ar_share_bp == plain.ar_share_bp
    assert c.excluded_aggregates == ["BUYER-2"]
    assert c.aggregate_note == ("Counted in the totals but shown with no share of its own: Dongguan Office Supplies Ltd., "
                                "which stand for many small customers.")
    zh = concentration(books, "BUYER-1", 0, _aggregate("BUYER-2"), lang="zh")
    assert zh.aggregate_note == "以下计入总额，但不单独显示占比：Dongguan Office Supplies Ltd.（代表许多小客户）。"


def test_an_aggregate_row_is_suppressed_not_removed_from_the_total() -> None:
    """The public SME in miniature: one marketplace row holds 48.63% of what is owed. It is named and has no share of its own,
    yet the other buyer's share is still taken over the whole."""
    rows = [_rcv(0, "BUYER-1", 5_137_000, due=10), _rcv(1, "BUYER-2", 4_863_000, due=10)]
    books = _books(rows)
    market = concentration(books, "BUYER-2", 0, _aggregate("BUYER-2"))
    assert market.ar_share_bp is None and market.receipts_share_bp is None and market.ar_total_fen == 10_000_000
    other = concentration(books, "BUYER-1", 0, _aggregate("BUYER-2"))
    assert other.ar_share_bp == 5137 and other.ar_total_fen == 10_000_000 and other.excluded_aggregates == ["BUYER-2"]


def test_an_aggregate_has_no_per_customer_share() -> None:
    books = _books([_rcv(0, "BUYER-1", 30_000_000), _rcv(1, "BUYER-2", 90_000_000)])
    c = concentration(books, "BUYER-2", 0, _aggregate("BUYER-2"))
    assert c.is_aggregate and c.ar_share_bp is None and c.receipts_share_bp is None and c.ar_buyer_fen == 0
    assert c.ar_text == "Dongguan stands for many small customers, so no single-customer share is shown."


def test_the_latest_aggregate_row_is_the_one_in_force() -> None:
    def row(seq: int, value: str) -> CustomerInputRecord:
        return CustomerInputRecord(org_id="O", counterparty_id="BUYER-2", field="aggregate", value_json=value,
                                   provenance="OWNER_ENTERED", source_ref="", entered_by="OWNER", entered_day=0,
                                   state_version=1, seq=seq)

    assert inputs_from_rows([row(1, "true"), row(2, "false")]).aggregates() == frozenset()
    assert inputs_from_rows([row(1, "false"), row(2, "true")]).aggregates() == frozenset({"BUYER-2"})


# ---------------------------------------------------------------- context, not mandate


def test_concentration_writes_nothing_and_changes_no_verdict() -> None:
    """P8 in miniature: EX01's verdict is byte-identical before and after the concentration is read with an aggregate input
    in force for either buyer, and the books and the log are untouched."""
    from fastapi.testclient import TestClient

    from app.api.runtime import Runtime, set_runtime
    from app.books import books_from_store
    from app.config import get_settings
    from app.mandate.fixture import demo_owner_public_key_hex
    from app.persistence import InMemoryLedgerStore
    from app.strategy.inputs import inputs_from_store

    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    try:
        from app.main import app

        client, owner = TestClient(app), {"X-Owner-Token": "demo-owner-token"}
        oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=owner).json()["offer"]["offer_id"]

        def verdict() -> dict[str, Any]:
            return client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=owner).json()

        before = verdict()
        state, chain = rt.store.get_state().model_dump_json(), [e.entry_hash for e in rt.store.operations()]
        for buyer in ("BUYER-1", "BUYER-2"):
            rt.store.add_customer_input(CustomerInputRecord(
                org_id="O", counterparty_id=buyer, field="aggregate", value_json="true", provenance="OWNER_ENTERED",
                source_ref="", entered_by="OWNER", entered_day=0, state_version=1))
            concentration(books_from_store(rt.store), "BUYER-1", 0, inputs_from_store(rt.store))
        assert rt.store.get_state().model_dump_json() == state and [e.entry_hash for e in rt.store.operations()] == chain
        assert verdict() == before
    finally:
        set_runtime(None)


def test_the_module_imports_nothing_that_decides() -> None:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    forbidden = ("app.verifier", "app.mandate", "app.funding", "app.operations", "app.covenants", "app.persistence")
    assert not [m for m in imported if m.startswith(forbidden)]
    assert "CONTEXT, NOT MANDATE" in (module.__doc__ or "")
