"""The verifier says so when the plan it names as the cure, or as the standing plan, is one the agent cannot run alone
(`needs_owner_approval`) or cannot run today (`executable_now` False). Only texts and `inputs` change: the outcome,
the tier, the codes, every figure, the counters' terms and the plans are the same with or without the sentences."""

from __future__ import annotations

import importlib

import pytest

from app.compiler import compile_offer
from app.domain.fixtures import load_offers, load_scenario, offer_documents
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.verifier import evaluate
from app.verifier.counters import counters
from tests.funding.variants import with_receivable, without_facilities


def run(offer_id: str, state):
    o = load_offers()[offer_id]
    offer = compile_offer(offer_documents(offer_id), o["counterparty_id"])
    return evaluate(offer, state, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex(),
                    owner_declared=dict(o.get("declared_costs") or {}))


def disable_flags(monkeypatch) -> None:
    """The verifier as it was before: no flag sentence and no flag input anywhere."""
    for name in ("app.verifier.evaluate", "app.verifier.counters"):
        mod = importlib.import_module(name)
        monkeypatch.setattr(mod, "plan_flags", lambda plan, subject: "", raising=False)
        monkeypatch.setattr(mod, "flag_inputs", lambda plan, prefix: {}, raising=False)


def figures(b) -> dict:
    """Everything of a bundle but its texts and inputs."""
    v = b.verdict.model_dump(mode="json")
    v.pop("summary")
    v["violations"] = [{k: x[k] for k in ("code", "day", "month", "observed", "limit", "curable", "cure_cost_fen")}
                       for x in v["violations"]]
    v["counters"] = [{k: c[k] for k in ("id", "label", "text", "obligations", "supplier_cost_fen", "forward_value_fen")}
                     for c in v["counters"]]
    v["plan"] = (v["plan"] or {}).get("id") if v["plan"] else None
    return {"verdict": v,
            "passed": [(p.code, p.label, p.observed, p.limit) for p in b.passed_checks],
            "plan_committed": b.plan_committed.model_dump(mode="json") if b.plan_committed else None,
            "cure": b.cure_plan.model_dump(mode="json") if b.cure_plan else None}


def short_hold(keep_early_pay: bool):
    """RCV-A is due on day 13: the golden advance is held 10 days, at 32.5% a year, above the 15% ceiling."""
    s, _ = load_scenario()
    s = with_receivable(s, "RCV-A", terms_days=26)
    return s if keep_early_pay else without_facilities(s, "FAC-EARLYPAY")


GOLDEN_OFFERS = ["EX01_PACKAGE", "EX02_EARLY_1_5", "EX03_AS_USUAL", "EX04_CLAIMED_REBATE", "EX05_CONSOLIDATE",
                 "EX06_THREE_INVOICES", "EX08A_JOINT_BUYER1", "EX11_CAPEX", "EX12_GOAL"]
# the flag sentences and the flag inputs ("cure_needs_owner_approval", ...); not the plan's own fields of the same name
FLAG_WORDS = ("needs the owner's approval:", "cannot run today:", '_needs_owner_approval"', '_executable_now"')


@pytest.mark.parametrize("offer_id", GOLDEN_OFFERS)
def test_on_the_golden_books_nothing_but_text_and_inputs_change(offer_id, monkeypatch):
    """A verdict with no flagged plan behind it is byte-identical to what it was; one with a flagged plan differs in
    its texts and inputs only (the cures of EX01 and EX06 rely on RI:BUYER-1:2, which is not issued yet)."""
    state, _ = load_scenario()
    live = run(offer_id, state)
    disable_flags(monkeypatch)
    old = run(offer_id, state)
    assert figures(live) == figures(old)
    dump = live.verdict.model_dump_json() + "".join(p.model_dump_json() for p in live.passed_checks)
    if not any(w in dump for w in FLAG_WORDS):
        assert live.verdict.model_dump_json() == old.verdict.model_dump_json()
        assert [p.model_dump_json() for p in live.passed_checks] == [p.model_dump_json() for p in old.passed_checks]
    else:
        assert offer_id in {"EX01_PACKAGE", "EX06_THREE_INVOICES"}  # a cure through a not-yet-issued invoice


def test_ex02_is_byte_identical_when_no_flag_is_set(monkeypatch):
    state, _ = load_scenario()
    live = run("EX02_EARLY_1_5", state)
    disable_flags(monkeypatch)
    old = run("EX02_EARLY_1_5", state)
    assert live.verdict.model_dump_json() == old.verdict.model_dump_json()
    assert not any(w in live.verdict.model_dump_json() for w in FLAG_WORDS)


def test_a_cure_the_executor_cannot_run_today_says_so_and_nothing_else_changes(monkeypatch):
    state = short_hold(keep_early_pay=False)
    flagged = run("EX01_PACKAGE", state)
    rv = next(v for v in flagged.verdict.violations if v.code.value == "RESERVE_BREACH")
    # the deepest shortfall is now after the existing loan's day-60 payment (¥135,040), carried on the invoice issued
    # on day 32, which does not exist yet
    assert rv.curable and "the cure cannot run today: " in rv.cure_note and "RI:BUYER-1:32 is not an invoice" in rv.cure_note
    assert rv.inputs["cure_executable_now"] == "false" and "RI:BUYER-1:32" in rv.inputs["cure_not_executable_reason"]
    assert "the cure cannot run today" in flagged.verdict.summary

    disable_flags(monkeypatch)
    plain = run("EX01_PACKAGE", state)
    assert "cannot run today" not in plain.verdict.model_dump_json().replace("(cannot run today)", "")
    assert figures(flagged) == figures(plain)
    assert flagged.verdict.outcome == plain.verdict.outcome and flagged.verdict.required_tier == plain.verdict.required_tier


def test_the_plan_without_the_early_payment_is_said_to_need_the_owner(monkeypatch):
    state = short_hold(keep_early_pay=False)
    flagged = run("EX02_EARLY_1_5", state)
    dearer = next(v for v in flagged.verdict.violations if v.code.value == "EARLY_PAY_DEARER_THAN_PLAN")
    assert "the plan without it needs the owner's approval: " in dearer.message
    assert "32.53%" in dearer.message and dearer.inputs["plan_without_offer_needs_owner_approval"] == "true"
    # The early-pay counter (0.85% for the 10 days RCV-A has left) fails its own re-check on these books: its all-in
    # rate is above the 15% ceiling, so it is not offered (the counter property). As built, it states the flags.
    assert flagged.verdict.counters == []
    assert ("No early-pay counter (early settlement of ¥90,800 at 0.85%): it is above the mandate's rate ceiling: "
            "28.4463% against 15.00%") in flagged.verdict.summary
    offer = compile_offer(offer_documents("EX02_EARLY_1_5"), "BUYER-1")
    mandate = load_signed_mandate()
    (counter,) = counters(offer, flagged.verdict, state, mandate, bound=flagged.bound_obligations)
    assert "the standing plan it is compared with needs the owner's approval" in counter.formula
    assert "the standing plan it is compared with needs the owner's approval" in counter.rationale
    assert "approval" not in counter.text  # what goes to the buyer is untouched

    disable_flags(monkeypatch)
    plain = run("EX02_EARLY_1_5", state)
    assert figures(flagged) == figures(plain)
    (unflagged,) = counters(offer, plain.verdict, state, mandate, bound=plain.bound_obligations)
    assert unflagged.text == counter.text and unflagged.obligations == counter.obligations


def test_a_passed_check_that_leans_on_a_flagged_standing_plan_says_so():
    b = run("EX05_CONSOLIDATE", short_hold(keep_early_pay=True))
    check = next(c for c in b.passed_checks if c.code == "MIN_CASH")
    assert "the committed plan needs the owner's approval: " in check.formula
    assert check.inputs["plan_needs_owner_approval"] == "true" and "32.53%" in check.inputs["plan_approval_reason"]
    state, _ = load_scenario()
    golden = next(c for c in run("EX05_CONSOLIDATE", state).passed_checks if c.code == "MIN_CASH")
    assert "approval" not in golden.formula and not any(k.startswith("plan_") and k != "plan" for k in golden.inputs)
