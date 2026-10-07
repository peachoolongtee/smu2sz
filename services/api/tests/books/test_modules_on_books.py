"""Every projection runs on current books (ADR-0006, audit C3): the verifier, the funding-plan callers,
/trajectory, /router/plan, the what-if sandbox and the negotiate flow see the obligations of live
commitments; with none, nothing changes."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.api.views import trajectory_view
from app.books import current_books
from app.config import get_settings
from app.domain.models import (
    BaseKind,
    Commitment,
    CommitmentStatus,
    CompiledOffer,
    CompileStatus,
    Contingency,
    Duration,
    DurationKind,
    Mode,
    Obligation,
    ObligationBase,
    ObligationType,
    SourceSpan,
)
from app.domain.money import fmt_yuan
from app.financial import invoices, project
from app.funding import plan
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.verifier import evaluate
from app.verifier.evaluate import verdict_id
from app.whatif import PRESETS, simulate

RCV_A_FACE = 42_000_000
SPAN = [SourceSpan(doc_id="T", start=0, end=0, text="")]

# Recorded on origin/dev (cfecd72) with no commitments: sha256 of the sorted-key JSON of each response.
# 3 Oct (existing debt is cash): the existing loan's ¥45,000 payments on days 30, 60, 90 and 120 are in the
# trajectory, and the plan carries a ¥255,000 advance (cost ¥3,113.93); before: 6e416d997eccbf94 and 60bcdca14e272842
GOLDEN_TRAJECTORY = "0437cc43e3b22800"
# Red team d, F1: the two comparison rows that rely on the buyer paying early ("Discount the whole invoice at 1.2%",
# "Line + early payment on part of the invoice") are flagged executable_now false ("needs the buyer's agreement to pay
# early"); every figure and the selected plan (¥3,113.93) unchanged. Before: 2479590b9ee26e83.
GOLDEN_ROUTER_PLAN = "252b9812e99b4aee"  # also: actions and comparison rows carry `lands_day` (API gaps). Earlier, 3 Oct: extension figures on 13 dated invoices; extra receivables ¥210,000.00. 118733a57fd7900b before the plan, cost lines and menu rows carried the approval and executable_now flags (every figure unchanged)
EX01_COUNTERS = [
    # face 255,000 / (1 − 0.85%) = 257,186.08, rounded up to a whole ¥100 (the gap net of the line includes the
    # existing loan's ¥45,000 day-30 payment; compute_golden.py counter_a_face)
    "Terms stay at 45 days, no rebate. We will accept early settlement on up to ¥257,200 of this invoice at 0.85%, "
    "paid on or before day 2.",
    # 60-day terms fail the counter's own re-check (day 47 ¥85,000 below the reserve, no admissible cure); 55 days is
    # curable in time. +10 days: 420,000 × 10/365 × 10.8417% = ¥1,247.53 per invoice → 0.30% (¥1,260.00)
    "55-day terms accepted with a 0.30% price adjustment on future invoices, no rebate.",
]


def _digest(o: Any) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


@pytest.fixture
def rt() -> Any:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


@pytest.fixture
def client(rt: Runtime) -> Any:
    from app.main import app

    return TestClient(app, headers={"X-Owner-Token": "demo-owner-token"})


def _extension(days: int = 15) -> Obligation:
    return Obligation(id="OB-EXT", type=ObligationType.TERMS_EXTENSION, counterparty_id="BUYER-1", days_delta=days,
                      base=ObligationBase(kind=BaseKind.FUTURE_INVOICES, amount_fen=RCV_A_FACE),
                      contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.RECURRING_PERPETUAL),
                      spans=SPAN, confidence=1.0)


def _early_pay(face: int = 21_190_000, day: int = 2, rate_bp: int = 85) -> Obligation:
    return Obligation(id="OB-EP", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id="BUYER-1", rate_bp=rate_bp,
                      effective_day=day, base=ObligationBase(kind=BaseKind.INVOICE, receivable_id="RCV-A",
                                                             amount_fen=face),
                      contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF), spans=SPAN,
                      confidence=1.0)


def _live(rt: Runtime, ob: Obligation, status: CommitmentStatus = CommitmentStatus.ACTIVE) -> Commitment:
    c = Commitment(id=f"CMT-{ob.id}", offer_id="OFF-LIVE", offer_version=1, counterparty_id=ob.counterparty_id,
                   verdict_id="V-LIVE", terms_hash="h", obligations=[ob], status=status, nonce="n", expires_day=7,
                   mandate_version=1, forward_value_fen=0)
    rt.store.put_commitment(c)
    if status == CommitmentStatus.ACTIVE:  # ADR-0009: what the executor writes when a commitment becomes ACTIVE
        rt.store.put_state(invoices.accept(rt.store.get_state(), c))
    return c


def _receipts(traj: dict[str, Any]) -> dict[str, int]:
    """receivable / recurring invoice id -> day its receipt lands in the projection"""
    return {e["ref"]: d["day"] for d in traj["days"] for e in d["events"] if e["kind"] == "RECEIPT"}


def _events(traj: dict[str, Any], ref: str) -> list[tuple[int, int]]:
    return [(d["day"], e["amount"]["fen"]) for d in traj["days"] for e in d["events"] if e["ref"] == ref]


def _evaluate_ex01(client: TestClient) -> tuple[str, dict[str, Any]]:
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    return oid, client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()


def _assert_alert_matches(client: TestClient, rt: Runtime, traj: dict[str, Any]) -> None:
    """/alerts and /trajectory report the same lowest-cash day and amount (the amount as the shortfall)."""
    floor = rt.store.get_mandate().min_cash_fen
    alert = next(x for x in client.get("/alerts").json()["alerts"] if x["kind"] == "RESERVE_BREACH_AHEAD")
    assert int(alert["inputs"]["worst_day"]) == traj["min_cash_day"]
    assert alert["inputs"]["max_shortfall"] == fmt_yuan(floor - traj["min_cash"]["fen"])


def _financed(p: dict[str, Any]) -> int:
    return sum(a["amount_fen"] for a in p["actions"] if a["kind"] == "FINANCE_INVOICE")


def _lowest(traj: dict[str, Any]) -> tuple[int, int]:
    return traj["min_cash_day"], traj["min_cash"]["fen"]


# ---------------------------------------------------------------- 1. no commitments: nothing moves


# Display-only fields the simplification map added to the router plan's comparison rows and legs (they never feed the
# engine, see tests/funding/test_display_fields_inert.py). The golden digest is of the payload without them.
_ROW_DISPLAY = ("status", "reason_kind", "shortfall_fen", "shortfall_display", "worst_day", "not_executable_reason",
                "not_executable_reason_when", "note_when", "components_when")


def _strip_when(plan: dict[str, Any]) -> None:
    """`plan_when`'s `*_when` sentences (Wave 4/7) beside the plan's, cost lines', violations' and rejected candidates' text."""
    for holder in [plan, *plan.get("costs", []), *plan.get("violations", []), *plan.get("rejected", [])]:
        for k in [k for k in holder if k.endswith("_when")]:
            holder.pop(k)


def _without_display_fields(plan: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(plan))
    for key in ("committed", "expected"):
        if out.get(key):
            out[key].pop("available_from_day", None)
            _strip_when(out[key])
            for a in out[key]["actions"]:
                a.pop("available_from_day", None)
    for row in out["comparison"]:
        for k in _ROW_DISPLAY:
            row.pop(k, None)
        for a in row["actions"]:
            a.pop("available_from_day", None)
            a["lands_day"] = None  # rows now carry the landing stamp; the golden rows had none
    return out


def test_no_commitments_trajectory_and_router_plan_are_unchanged(client: TestClient, rt: Runtime) -> None:
    t = client.get("/trajectory").json()
    assert t.pop("today") == 0
    # `first_breach_cash` is a display-only field the simplification map added (Wave 1); the golden is of the rest
    assert _digest({k: v for k, v in t.items() if k != "first_breach_cash"}) == GOLDEN_TRAJECTORY
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    raw = trajectory_view(project(state, [], [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen),
                          mandate.min_cash_fen).model_dump()
    assert t == json.loads(json.dumps(raw))
    r = client.post("/router/plan").json()
    assert r["marginal"]["extension_extra_receivables_fen"] == 21_000_000  # F x 15 / 30, the shared pro forma
    assert r["marginal"]["extension_committed_12m_fen"] == 2_432_692
    assert _digest(_without_display_fields(r)) == GOLDEN_ROUTER_PLAN
    assert r["committed"]["total_cost_display"] == "¥3,113.93"  # line 841.64 + advance of 255,000 2,272.29
    assert r["committed"]["total_cost_fen"] == 311_393


def test_no_commitments_ex01_verdict_is_unchanged(client: TestClient, rt: Runtime) -> None:
    oid, v = _evaluate_ex01(client)
    assert v["outcome"] == "REJECT"
    assert [x["code"] for x in v["violations"]] == ["AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH",
                                                    "DISCOUNT_ABOVE_BREAK_EVEN", "EARLY_PAY_DEARER_THAN_PLAN"]
    assert [c["text"] for c in v["counters"]] == EX01_COUNTERS
    # the cure carries the deepest shortfall, 135,040 on day 60 (after the existing loan's day-60 payment):
    # 135,040 × 7.8% × 60/365 = 1,731.47 + fees 135,040 × 0.25% × 2 = 675.20 -> 2,406.67 (golden reserve_cure_cost_if)
    assert next(x for x in v["violations"] if x["code"] == "RESERVE_BREACH")["cure_cost_fen"] == 240_667
    # the id of a verdict on books with nothing live is a function of the state, mandate and day alone
    offer = rt.store.get_offer(oid)
    assert offer is not None
    assert v["id"] == verdict_id(oid, offer.version, rt.store.get_state(), rt.store.get_mandate(), rt.day)


def test_inactive_commitments_do_not_enter_the_books(client: TestClient, rt: Runtime) -> None:
    before = client.get("/trajectory").json()
    _live(rt, _extension(), CommitmentStatus.PROPOSED)
    assert client.get("/trajectory").json() == before


# ---------------------------------------------------------------- 2. a live terms extension


def test_live_extension_shifts_receipts_in_trajectory_and_alerts_agree(client: TestClient, rt: Runtime) -> None:
    before = client.get("/trajectory").json()
    _live(rt, _extension(15))
    after = client.get("/trajectory").json()
    b, a = _receipts(before), _receipts(after)
    assert b["RI:BUYER-1:2"] == 47 and a["RI:BUYER-1:2"] == 62  # issued day 2, terms 45 -> 60
    assert b["RI:BUYER-1:32"] == 77 and a["RI:BUYER-1:32"] == 92
    assert b["RCV-A"] == a["RCV-A"] == 32  # an invoice already issued keeps its terms
    assert after["today"] == 0
    assert _lowest(after) == _lowest(before)  # the near-term gap is untouched
    _assert_alert_matches(client, rt, after)


def test_live_extension_enters_the_next_verdict_baseline(client: TestClient, rt: Runtime) -> None:
    _, plain = _evaluate_ex01(client)
    _live(rt, _extension(15))
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    v = client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()
    traj = v["trajectory"]
    # the offer's own trajectory sits on the shifted baseline. EX01 states a 60-day TARGET; since red team e (F2) a
    # target binds against the terms in force (45 + 15 = 60), so it adds nothing and the terms do not stack (they
    # did: receipts landed on day 77)
    assert _receipts(traj)["RI:BUYER-1:2"] == 62
    assert _receipts(plain["trajectory"])["RI:BUYER-1:2"] == 62
    assert v["id"] != plain["id"]  # a verdict on other books is not the same record
    # only the offer's obligations are bound: nothing of the live commitment leaks into the verdict
    assert [o["id"] for o in v["bound_obligations"]] == [o["id"] for o in plain["bound_obligations"]]
    assert "OB-EXT" not in {o["id"] for o in v["bound_obligations"]}
    # red team e, F2: the 60-day target against 60 days in force is no change, so the offer's extension is valued at
    # nothing on these books (it was valued again as +15 days on top of the live +15)
    ext = next(o for o in v["bound_obligations"] if o["type"] == "TERMS_EXTENSION")
    assert ext["days_delta"] == 0 and ext["target_terms_days"] == 60
    assert v["forward_concession"]["total_fen"] < plain["forward_concession"]["total_fen"]


def test_router_plan_follows_the_live_commitment(client: TestClient, rt: Runtime) -> None:
    base = client.post("/router/plan").json()
    _live(rt, _early_pay(), CommitmentStatus.ACCEPTED)
    moved = client.post("/router/plan").json()
    assert moved["committed"]["need_fen"] < base["committed"]["need_fen"]
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    books = current_books(state, rt.store.commitments())
    assert moved["committed"]["total_cost_fen"] == plan(books.state, books.with_([]), mandate).total_cost_fen


# ---------------------------------------------------------------- 3. a live early-pay


def test_live_early_pay_is_in_the_trajectory_and_the_router(client: TestClient, rt: Runtime) -> None:
    base_plan = client.post("/router/plan").json()["committed"]
    _live(rt, _early_pay(21_190_000, 2, 85))
    t = client.get("/trajectory").json()
    ev = _events(t, "RCV-A")
    assert (2, 21_190_000) in ev  # the early receipt of the settled face, on the effective day
    assert t["discounts"]["fen"] == 180_115  # 0.85% of 21_190_000, the price of getting it early
    assert (32, RCV_A_FACE - 21_190_000) in ev  # the residual keeps its due day
    assert not any(day == 32 and amt == RCV_A_FACE for day, amt in ev)
    plan_now = client.post("/router/plan").json()["committed"]
    # part of RCV-A is already coming early: the router no longer finances that part
    assert _financed(plan_now) < _financed(base_plan)
    assert plan_now["need_fen"] < base_plan["need_fen"]


def test_alerts_and_trajectory_agree_with_a_live_early_pay(client: TestClient, rt: Runtime) -> None:
    _live(rt, _early_pay())
    t = client.get("/trajectory").json()
    assert t["first_breach_day"] is not None
    _assert_alert_matches(client, rt, t)


# ---------------------------------------------------------------- 4. negotiate: no double counting


def test_negotiate_cooperative_plan_and_operations_unchanged(client: TestClient) -> None:
    oid, _ = _evaluate_ex01(client)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()
    assert n["outcome"] == "DEAL"
    assert [(o["kind"], o["status"], o["tier"]) for o in n["operations"]] == [
        ("ACCEPT_OFFER", "EXECUTED", "TIER_1"), ("DRAW_FACILITY", "EXECUTED", "TIER_1")]
    # the line carries 405,000 − (257,200 − 2,186.20) = 149,986.20
    assert n["operations"][1]["message"] == "Drew ¥149,986.20 on FAC-LINE on day 0"
    # the accepted counter is in the books once, not twice: the line carries the rest of the gap and the
    # router adds no early pay on top (the counter's face already nets the gap less the line)
    assert [(a["kind"], a["facility_id"], a["amount_fen"]) for a in n["plan"]["actions"]] == [
        ("DRAW", "FAC-LINE", 14_998_620)]
    # 149,986.20 × 6.4% × 32/365 = 841.5664 -> 841.57
    assert n["plan"]["need_fen"] == 14_998_620 and n["plan"]["total_cost_fen"] == 84_157
    assert n["plan"]["label"] == "committed plan: ¥841.57"


def test_negotiate_hard_line_still_funds_the_standing_gap(client: TestClient) -> None:
    oid, _ = _evaluate_ex01(client)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "hard_line"}).json()
    assert n["outcome"] == "NO_DEAL" and n["plan"]["total_cost_display"] == "¥3,113.93"


# ---------------------------------------------------------------- 5. the verdict binds only the offer


def test_verdict_and_counters_carry_only_the_offers_obligations(client: TestClient, rt: Runtime) -> None:
    _live(rt, _extension(15))
    _, v = _evaluate_ex01(client)
    stored = rt.store.get_verdict(v["id"])
    assert stored is not None
    assert [o.id for o in stored.bound_obligations] == ["OFF-f806f79b6c21-O1", "OFF-f806f79b6c21-O2",
                                                        "OFF-f806f79b6c21-O3"]
    assert all(o.id.startswith("CTR-") for c in stored.counters for o in c.obligations)
    # each counter's text is the offer's own terms. With 15 more days already live, an early payment at 0.85% no
    # longer beats the standing plan (ADR-0007), so only the price-adjustment counter is offered on these books. The
    # live +15 days are part of these books (and of the no-offer baseline the re-check compares with), and here the
    # buyer's 60 days passed the counter's own re-check: 0.45% (420,000 × 15/365 × 10.8417% = ¥1,871.30 → ¥1,890).
    # Red team d, F1: on these books the standing plan used to rely on the buyer's early-pay programme, which no
    # operation can run; the standing plan that can run is the line and an invoice advance. It takes committed room
    # the cure of a longer extension needed, so 60-, 55- and 50-day terms leave the day-62 shortfall with no cure and
    # no price-adjustment counter is offered; against that dearer standing plan the early payment at 0.85% is offered.
    assert [c.text for c in stored.counters] == [
        "Terms stay at 60 days, no rebate. We will accept early settlement on up to ¥257,200 of this invoice at 0.85%, "
        "paid on or before day 2."]
    # red team e, F2: the buyer's 60 days are the terms already in force (45 + 15), so the offer asks for no longer
    # terms and there is no price-adjustment counter to search for (the summary used to explain why 60-, 55- and
    # 50-day terms on top of the live 15 could not be funded); the counter text quotes the 60 days in force.
    assert not any(c.label == "Option B" for c in stored.counters)


def test_a_commitment_carries_what_the_counter_bound(client: TestClient, rt: Runtime) -> None:
    """Accepting on books that hold a live commitment books the counter's obligations alone."""
    # the live commitment is another buyer's: with BUYER-1's own terms already extended, an early payment at 0.85%
    # no longer beats the standing plan (ADR-0007) and there would be no early-pay counter to accept
    _live(rt, _extension(15).model_copy(update={"counterparty_id": "BUYER-2"}))
    oid, _ = _evaluate_ex01(client)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()
    assert n["outcome"] == "DEAL"
    c = rt.store.get_commitment(n["commitment"]["id"])
    assert c is not None and "OB-EXT" not in {o.id for o in c.obligations}
    assert len(c.obligations) == 1 and c.obligations[0].type == ObligationType.IMMEDIATE_DISCOUNT


# ---------------------------------------------------------------- 6. what-if


def _closing(days: list[dict[str, Any]]) -> list[int]:
    return [d["closing"]["fen"] for d in days]


def test_whatif_baseline_includes_the_live_commitment(client: TestClient, rt: Runtime) -> None:
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    key = demo_owner_public_key_hex()
    plain = simulate(state, mandate, PRESETS["status_quo"], trusted_owner_key_hex=key)
    _live(rt, _early_pay())
    held = simulate(state, mandate, PRESETS["status_quo"], trusted_owner_key_hex=key,
                    commitments=rt.store.commitments())
    assert held.key != plain.key
    assert _closing(held.trajectory["days"]) != _closing(plain.trajectory["days"])
    # the status-quo what-if is the books themselves: the same line as GET /trajectory
    served = client.get("/trajectory").json()
    assert _closing(held.trajectory["days"]) == _closing(served["days"])
    # the endpoint hands the store's commitments to the sandbox
    posted = client.post("/whatif", json=PRESETS["status_quo"].model_dump()).json()
    assert _closing(posted["trajectory"]["days"]) == _closing(served["days"])


def test_whatif_without_commitments_is_unchanged(rt: Runtime) -> None:
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    key = demo_owner_public_key_hex()
    a = simulate(state, mandate, PRESETS["actual"], trusted_owner_key_hex=key)
    b = simulate(state, mandate, PRESETS["actual"], trusted_owner_key_hex=key, commitments=[])
    assert a.key == b.key and a.outcome == b.outcome == "REJECT"


# ---------------------------------------------------------------- the verifier itself


def test_verifier_baseline_is_the_live_books_not_an_empty_list(rt: Runtime) -> None:
    """A no-offer evaluation on live books projects those books; with the commitment left out of
    `commitments` (the re-verify hook's case) it projects the raw state."""
    ob = _early_pay()
    c = _live(rt, ob)
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    sq = CompiledOffer(offer_id="SQ", counterparty_id="OWNER", doc_ids=["SQ"], received_day=0,
                       status=CompileStatus.COMPILED, obligations=[], compiler="nl-status-quo", prompt_version="t")
    key = demo_owner_public_key_hex()
    on_books = evaluate(sq, state, mandate, trusted_owner_key_hex=key, commitments=[c])
    raw = evaluate(sq, state, mandate, trusted_owner_key_hex=key, commitments=[])
    assert on_books.trajectory is not None and raw.trajectory is not None
    want = project(state, [ob], [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    assert on_books.trajectory.model_dump() == want.model_dump()
    assert on_books.trajectory.model_dump() != raw.trajectory.model_dump()
    assert on_books.verdict.bound_obligations == []
    assert on_books.verdict.id != raw.verdict.id
