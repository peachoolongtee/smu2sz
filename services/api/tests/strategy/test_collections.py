"""Wave 4 of map #47: collections worth, pinned to the collections spike's recorded oracle
(fixtures/strategy/collections_both.json). Money is compared as integer fen against the oracle's `fen` values and against
the literal the brief's pin table names. The answer is computed once per book (module-scoped)."""

from __future__ import annotations

import dataclasses
import json
import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.books import Books
from app.domain.models import Mandate, Receivable
from app.strategy import WorthAnswer, early_pay_vs_plan, receivables_worth, saving_text
from app.strategy.collections import Ceiling, ReceivableWorth, _decide
from app.verifier.evaluate import clear_caches

from .conftest import OWNER

_ORACLE = Path(__file__).resolve().parents[4] / "fixtures" / "strategy" / "collections_both.json"
RCV_A, RI_2, RI_32 = "RCV-A", "RI:BUYER-1:2", "RI:BUYER-1:32"
_FACE_KIND = {"the whole outstanding invoice": "whole", "the shortfall the plan covers": "need"}


def _oracle(name: str) -> dict[str, Any]:
    books: list[dict[str, Any]] = json.loads(_ORACLE.read_text(encoding="utf-8"))["books"]
    return next(b for b in books if b["books"] == name)


def _fen(m: dict[str, Any]) -> int:
    return int(m["fen"])


def _row(answer: WorthAnswer, rid: str) -> ReceivableWorth:
    return next(w for w in answer.rows if w.receivable_id == rid)


def _ceiling(row: ReceivableWorth, kind: str) -> Ceiling:
    return next(c for c in row.ceilings if c.face_kind == kind)


def _stable(answer: WorthAnswer) -> dict[str, Any]:
    out: dict[str, Any] = answer.model_dump(mode="json")
    out.pop("computed_in_seconds")
    return out


@pytest.fixture(scope="module")
def mandate34(rt_day34: Runtime) -> Mandate:
    return rt_day34.store.get_mandate()


@pytest.fixture(scope="module")
def mandate0(rt_day0: Runtime) -> Mandate:
    return rt_day0.store.get_mandate()


@pytest.fixture(scope="module")
def worth34(rt_day34: Runtime, books_day34: Books, mandate34: Mandate) -> WorthAnswer:
    return receivables_worth(books_day34, mandate34, store=rt_day34.store, day=34)


@pytest.fixture(scope="module")
def worth0(rt_day0: Runtime, books_day0: Books, mandate0: Mandate) -> WorthAnswer:
    return receivables_worth(books_day0, mandate0, store=rt_day0.store, day=0)


# ---------------------------------------------------------------- the day-34 pins (brief section 7, Wave 4)


def test_day34_call_now_on_the_overdue_invoice(worth34: WorthAnswer):
    a = _row(worth34, RCV_A)
    assert (a.outstanding_fen, a.due_day, a.days_late, a.status, a.financed) == (16_280_000, 32, 2, "OPEN", False)
    assert a.gross_saving_fen == a.net_saving_fen == 137_461  # ¥1,374.61, a free action keeps all of it
    today = next(e for e in a.effects if e.kind == "today")
    assert (today.saving_fen, today.need_left_fen) == (137_461, 3_720_000)  # ¥37,200 still to cover
    assert today.after_needs_owner is True and today.breach_days_removed == 0
    assert a.ceilings == []  # never an early-payment ceiling on an invoice already due
    assert "already due" in a.reason_sentence
    assert a.action == "call_now" and not a.no_saving
    assert a.action_sentence == ("Call Foshan Home Retail Co. today for the ¥162,800.00: it saves you ¥1,374.61 "
                                 "and is the only free action.")


def test_day34_ri2_offers_early_payment_with_the_day42_breach_removed(worth34: WorthAnswer):
    b = _row(worth34, RI_2)
    assert b.gross_saving_fen == 170_610 and b.net_saving_fen == 7_758
    assert b.action == "offer_early_pay" and b.days_late == 0
    today = next(e for e in b.effects if e.kind == "today")
    assert today.breach_days_removed == 5 and today.need_left_fen == 0
    assert "RESERVE_BREACH_AHEAD" in today.alerts_removed
    early = next(e for e in b.effects if e.kind == "before_due")
    assert early.receipt_day == 42 and early.saving_fen == 170_610 and early.breach_days_removed == 5
    need, whole = _ceiling(b, "need"), _ceiling(b, "whole")
    assert (need.face_fen, need.largest_rate_bp, need.beats_by_fen) == (20_000_000, 80, 7_758)
    assert (need.next_rate_bp, need.next_rate_dearer_by_fen) == (85, 2_420)
    assert (whole.face_fen, whole.largest_rate_bp) == (42_000_000, 40)
    assert (need.face_label, whole.face_label) == ("the plan's need", "the whole invoice")
    assert b.ceilings == [whole, need]
    assert b.action_sentence == ("On the ¥420,000.00 due in 13 days, early payment at up to 0.80% on ¥200,000.00 "
                                 "(0.40% on the whole) beats the funding it replaces by ¥77.58 at the top rate; "
                                 "or finance it.")


def test_day34_ri32_waits_by_the_rule(worth34: WorthAnswer):
    c = _row(worth34, RI_32)
    assert c.gross_saving_fen == 170_610 and c.net_saving_fen == 7_368
    need, whole = _ceiling(c, "need"), _ceiling(c, "whole")
    assert (need.face_fen, need.largest_rate_bp) == (20_000_000, 120)
    assert (whole.face_fen, whole.largest_rate_bp) == (42_000_000, 65)
    # the spike said "offer early pay"; the brief's rule says wait: the invoices due before it already cover the need
    assert c.action == "wait"
    assert c.action_sentence == ("Wait: the ¥420,000.00 due in 43 days is beyond the shortfall; "
                                 "chasing it now saves nothing extra.")


def test_day34_ranking_net_and_gross(worth34: WorthAnswer):
    assert [w.receivable_id for w in worth34.rows] == [RCV_A, RI_2, RI_32]
    assert [w.net_saving_fen for w in worth34.rows] == [137_461, 7_758, 7_368]
    assert worth34.gross_order == [RI_2, RI_32, RCV_A]  # ¥1,706.10, ¥1,706.10 (due earlier first), ¥1,374.61
    assert [_row(worth34, i).gross_saving_fen for i in worth34.gross_order] == [170_610, 170_610, 137_461]
    assert worth34.top_action == worth34.rows[0].action_sentence
    assert worth34.first_breach_day == 42 == _oracle("day 34")["baseline"]["first_breach_day"]
    assert worth34.ranking_note.startswith("Ranked by what collecting each saves you, net of")
    assert worth34.source_state_version >= 0 and worth34.computed_in_seconds > 0


def test_day34_the_five_days_early_effect_is_a_cost_shown_as_no_saving(worth34: WorthAnswer):
    effect = next(e for e in _row(worth34, RI_32).effects if e.kind == "before_due")
    assert effect.receipt_day == 72 and effect.saving_fen == -7_609  # kept negative, never clamped
    assert effect.no_saving is True and effect.saving_text == "no saving"
    assert effect.breach_days_removed == 0 and effect.need_left_fen == 20_000_000


def test_saving_text_helper():
    assert saving_text(-7_609) == "no saving" and saving_text(0) == "no saving"
    assert saving_text(0, "zh") == "没有节省"
    assert saving_text(137_461) == "¥1,374.61" and saving_text(137_461, "zh") == "¥1,374.61"


# ---------------------------------------------------------------- the oracle, to the fen


@pytest.mark.parametrize(("name", "fixture"), [("day 0", "worth0"), ("day 34", "worth34")])
def test_every_oracle_effect_and_ceiling_is_reproduced(name: str, fixture: str, request: pytest.FixtureRequest):
    answer: WorthAnswer = request.getfixturevalue(fixture)
    oracle = _oracle(name)
    assert {w.receivable_id for w in answer.rows} == {r["receivable"] for r in oracle["ranking"]}
    assert answer.first_breach_day == oracle["baseline"]["first_breach_day"]
    for o in oracle["ranking"]:
        w = _row(answer, o["receivable"])
        assert (w.buyer_name, w.due_day, w.days_late, w.status) == (o["buyer_name"], o["due_day"], o["days_late"], o["status"])
        assert w.outstanding_fen == _fen(o["outstanding"]) and w.financed is False
        by_day = {e.receipt_day: e for e in w.effects}
        assert sorted(by_day) == sorted(e["receipt_day"] for e in o["effects"])
        for e in o["effects"]:
            got = by_day[e["receipt_day"]]
            assert got.saving_fen == _fen(e["saving"])
            assert got.need_left_fen == _fen(e["after"]["need"])
            assert got.breach_days_removed == e["breach_days_removed"]
            assert got.alerts_removed == e["alerts_cleared"]
            assert got.after_needs_owner == e["after"]["plan_needs_owner_approval"]
        assert len(w.ceilings) == len([p for p in o["early_pay"] if p["largest_rate"] is not None or p["sweep"]])
        for p in o["early_pay"]:
            if not p["sweep"] and p["largest_rate"] is None:  # overdue: nothing offered
                assert w.ceilings == [] and "overdue" in p["note"]
                continue
            c = _ceiling(w, _FACE_KIND[p["face_label"]])
            assert c.face_fen == _fen(p["face"]) and c.cost_without_fen == _fen(p["cost_without"])
            assert c.largest_rate_bp == (p["largest_rate"] or {}).get("bp")
            assert c.cost_with_fen == (_fen(p["cost_with"]) if p["cost_with"] else None)
            assert c.beats_by_fen == (_fen(p["beats_by"]) if p["beats_by"] else None)
            assert c.next_rate_bp == (p["next_rate"] or {}).get("bp")
            assert c.next_rate_dearer_by_fen == (_fen(p["next_rate_dearer_by"]) if p["next_rate_dearer_by"] else None)


def test_every_sweep_value_matches_the_oracle_day34(rt_day34: Runtime, books_day34: Books, mandate34: Mandate):
    checked = 0
    for o in _oracle("day 34")["ranking"]:
        for p in o["early_pay"]:
            for s in p["sweep"]:
                got = early_pay_vs_plan(books_day34, mandate34, o["receivable"], _fen(p["face"]), s["rate"]["bp"])
                assert got == (_fen(s["c1_less_c0"]) if s["c1_less_c0"] else None), (o["receivable"], p["face_label"], s["rate"])
                checked += 1
    assert checked == 4 * 30


def test_sweep_pins_day34(books_day34: Books, mandate34: Mandate):
    assert early_pay_vs_plan(books_day34, mandate34, RI_2, 20_000_000, 40) == -88_828  # ¥888.28 under the plan
    assert early_pay_vs_plan(books_day34, mandate34, RI_2, 20_000_000, 80) == -7_758
    assert early_pay_vs_plan(books_day34, mandate34, RI_2, 20_000_000, 85) == 2_420  # ¥24.20 dearer
    assert early_pay_vs_plan(books_day34, mandate34, RI_2, 20_000_000, 0) is None  # 0 bp is not an early payment


def test_the_early_pay_test_is_refused_where_the_verifier_would_not_run_it(books_day34: Books, mandate34: Mandate):
    assert early_pay_vs_plan(books_day34, mandate34, RCV_A, 16_280_000, 40) is None  # overdue: not settled before due
    assert early_pay_vs_plan(books_day34, mandate34, "NO-SUCH", 10_000, 40) is None


# ---------------------------------------------------------------- the day-0 books


def test_day0_rcv_a(worth0: WorthAnswer):
    a = _row(worth0, RCV_A)
    by_day = next(e for e in a.effects if e.receipt_day == 12)
    assert by_day.kind == "first_breach" and by_day.saving_fen == 311_393  # ¥3,113.93, the breach removed
    assert by_day.breach_days_removed == 20 and by_day.alerts_removed == ["RESERVE_BREACH_AHEAD"]
    assert a.gross_saving_fen == 311_393
    assert (_ceiling(a, "whole").face_fen, _ceiling(a, "whole").largest_rate_bp) == (42_000_000, 70)
    assert (_ceiling(a, "need").face_fen, _ceiling(a, "need").largest_rate_bp) == (40_500_000, 75)
    assert a.net_saving_fen == _ceiling(a, "need").beats_by_fen == 5_939
    assert a.action == "offer_early_pay" and worth0.first_breach_day == 12
    assert worth0.gross_order == [RCV_A]


@pytest.mark.parametrize("fixture", ["worth0", "worth34"])
def test_no_ceiling_is_above_the_mandate_cap(fixture: str, request: pytest.FixtureRequest, mandate0: Mandate):
    answer: WorthAnswer = request.getfixturevalue(fixture)
    cap = mandate0.max_immediate_discount_bp
    assert cap == 150
    rates = [c.largest_rate_bp for w in answer.rows for c in w.ceilings if c.largest_rate_bp is not None]
    assert rates and all(r <= cap for r in rates)
    assert all(c.next_rate_bp is None or c.next_rate_bp <= cap for w in answer.rows for c in w.ceilings)


# ---------------------------------------------------------------- the rules, one by one


def _receivable(due_day: int = 50, status: str = "OPEN") -> Receivable:
    return Receivable.model_validate({"id": "X", "counterparty_id": "B", "face_fen": 1_000_000, "issue_day": 0,
                                      "terms_days": due_day, "status": status})


def _ceil(beats: int | None) -> Ceiling:
    return Ceiling(face_kind="need", face_fen=1, face_label="x", largest_rate_bp=None if beats is None else 5,
                   cost_without_fen=0, cost_with_fen=None, beats_by_fen=beats, next_rate_bp=None,
                   next_rate_dearer_by_fen=None)


def _decision(**kw: Any) -> str:
    base: dict[str, Any] = {"r": _receivable(), "day": 10, "days_late": 0, "lapsed": False, "promised": False,
                            "episode": (20, 30), "beyond": False, "need_ceiling": _ceil(100)}
    base.update(kw)
    return str(_decide(**base))


def test_action_rules_in_order():
    assert _decision(days_late=1, r=_receivable(9)) == "call_now"
    assert _decision(days_late=29, r=_receivable(9)) == "call_now"
    assert _decision(days_late=30, r=_receivable(9)) == "escalate"  # a month late
    assert _decision(lapsed=True) == "escalate"  # a lapsed promise, even when it is not yet late
    assert _decision(lapsed=True, days_late=3, r=_receivable(9)) == "escalate"
    assert _decision(r=_receivable(25)) == "reminder"  # due inside the first shortfall
    assert _decision(r=_receivable(25), promised=True) == "wait"  # they have promised to pay
    assert _decision(r=_receivable(15)) == "wait"  # lands before the shortfall
    assert _decision(r=_receivable(40)) == "offer_early_pay"
    assert _decision(r=_receivable(40), need_ceiling=_ceil(None)) == "finance"
    assert _decision(r=_receivable(40), need_ceiling=None) == "finance"
    assert _decision(r=_receivable(40), beyond=True) == "wait"
    assert _decision(r=_receivable(40), episode=None) == "wait"  # no shortfall ahead
    assert _decision(r=_receivable(40, "FINANCED")) == "wait"  # the lender is repaid first


# ---------------------------------------------------------------- robustness


def test_a_financed_receivable_never_crashes_the_answer(rt_day34: Runtime, books_day34: Books, mandate34: Mandate):
    state = books_day34.state
    swapped = state.model_copy(update={"receivables": [
        r.model_copy(update={"status": "FINANCED", "advance_fen": 5_000_000}) if r.id == RI_32 else r
        for r in state.receivables]})
    answer = receivables_worth(dataclasses.replace(books_day34, state=swapped), mandate34, store=rt_day34.store, day=34)
    c = _row(answer, RI_32)
    assert c.financed is True and c.ceilings == [] and c.action == "wait"
    assert all(e.kind == "today" for e in c.effects)  # no moved receipt on a financed invoice
    assert "financed" in c.action_sentence


def test_order_is_identical_before_and_after_clear_caches(rt_day34: Runtime, books_day34: Books, mandate34: Mandate,
                                                          worth34: WorthAnswer):
    clear_caches()
    again = receivables_worth(books_day34, mandate34, store=rt_day34.store, day=34)
    assert [w.receivable_id for w in again.rows] == [w.receivable_id for w in worth34.rows]
    assert again.gross_order == worth34.gross_order
    assert _stable(again) == _stable(worth34)


def test_day34_answer_is_fast_when_warm(rt_day34: Runtime, books_day34: Books, mandate34: Mandate, worth34: WorthAnswer):
    started = time.perf_counter()
    receivables_worth(books_day34, mandate34, store=rt_day34.store, day=34)
    seconds = time.perf_counter() - started
    print(f"collections worth, day 34, warm: {seconds:.3f} s (first: {worth34.computed_in_seconds:.3f} s)")
    assert seconds < 1.5


# ---------------------------------------------------------------- wording


_ENGINE_WORDS = re.compile(r"\b(verdict|trajectory|basis|fen|offer them|give them)\b", re.I)


def _strings(answer: WorthAnswer) -> list[str]:
    out = [answer.top_action, answer.ranking_note]
    for w in answer.rows:
        out += [w.action_sentence, w.reason_sentence, w.due_when, w.net_saving_text, *(c.face_label for c in w.ceilings)]
        for e in w.effects:
            out += [e.label, e.receipt_when, e.saving_text]
    return out


@pytest.mark.parametrize("fixture", ["worth0", "worth34"])
def test_english_words_are_the_owners(fixture: str, request: pytest.FixtureRequest):
    answer: WorthAnswer = request.getfixturevalue(fixture)
    for s in _strings(answer):
        assert not re.search(r"\bday \d", s), s
        assert not _ENGINE_WORDS.search(s), s
        assert "discount them" not in s
    for w in answer.rows:
        assert "if it arrived" in w.reason_sentence.lower() or w.action == "wait"
        assert all("if it arrived" in e.label for e in w.effects)  # every scenario says it is hypothetical
        assert w.hypothetical is True


def test_chinese_twins_for_every_sentence(rt_day34: Runtime, books_day34: Books, mandate34: Mandate, worth34: WorthAnswer):
    zh = receivables_worth(books_day34, mandate34, store=rt_day34.store, day=34, lang="zh")
    assert [w.receivable_id for w in zh.rows] == [w.receivable_id for w in worth34.rows]
    assert [w.net_saving_fen for w in zh.rows] == [w.net_saving_fen for w in worth34.rows]
    for w, en in zip(zh.rows, worth34.rows, strict=True):
        assert re.search(r"[一-鿿]", w.action_sentence) and w.action_sentence != en.action_sentence
        assert re.search(r"[一-鿿]", w.reason_sentence)
    for s in _strings(zh):
        assert not re.search(r"\bday \d|第 ?\d+ ?天", s), s
    assert _row(zh, RI_2).action_sentence == (
        "13 天后到期的 ¥420,000.00:对 ¥200,000.00 提前付款,折扣最高 0.80%(整张发票最高 0.40%)仍比它所替代的融资划算,"
        "最高折扣时省 ¥77.58;或者改为融资。")
    assert _row(zh, RCV_A).action_sentence.startswith("今天就联系 Foshan Home Retail Co. 催收这笔 ¥162,800.00")


# ---------------------------------------------------------------- the route


@pytest.fixture
def day34_client(rt_day34: Runtime, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("FEATURE_COLLECTIONS_WORTH", raising=False)
    set_runtime(rt_day34)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


def test_route_is_403_when_the_flag_is_off(day34_client: TestClient):
    r = day34_client.get("/receivables/worth", headers=OWNER)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "FEATURE_DISABLED" and r.json()["detail"]["feature"] == "collections_worth"


def test_route_needs_the_owner(day34_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FEATURE_COLLECTIONS_WORTH", "1")
    assert day34_client.get("/receivables/worth").status_code in (401, 403)


def test_route_answers_on_the_day34_runtime(day34_client: TestClient, rt_day34: Runtime, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FEATURE_COLLECTIONS_WORTH", "1")
    before = (rt_day34.store.get_state().model_dump_json(), len(rt_day34.store.commitments()))
    r = day34_client.get("/receivables/worth", headers=OWNER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hypothetical"] is True and body["day"] == 34 and body["state_version"] == body["source_state_version"]
    assert [w["receivable_id"] for w in body["rows"]] == [RCV_A, RI_2, RI_32]
    assert body["rows"][0]["action"] == "call_now"
    assert body["top_action"] == body["rows"][0]["action_sentence"]
    assert body["gross_order"] == [RI_2, RI_32, RCV_A]
    assert body["rows"][0]["net_saving_display"] == "¥1,374.61"
    ri2 = body["rows"][1]
    assert ri2["ceilings"][1]["largest_rate_display"] == "0.80%" and ri2["ceilings"][1]["face_display"] == "¥200,000.00"
    assert all("impact" not in e for w in body["rows"] for e in w["effects"])
    early = next(e for e in body["rows"][2]["effects"] if e["kind"] == "before_due")
    assert early["saving_fen"] == -7_609 and early["saving_display"] == "no saving"  # the raw figure stays beside it
    assert body["computed_in_seconds"] >= 0
    again = day34_client.get("/receivables/worth", headers=OWNER)  # from the cache, identical
    assert again.json() == body
    assert day34_client.get("/receivables/worth?lang=zh", headers=OWNER).json()["rows"][0]["action"] == "call_now"
    assert day34_client.get("/receivables/worth?lang=fr", headers=OWNER).status_code == 422
    assert (rt_day34.store.get_state().model_dump_json(), len(rt_day34.store.commitments())) == before  # read-only
