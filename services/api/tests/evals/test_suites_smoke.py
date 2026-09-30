"""Smoke subset of every evaluation suite (the full run is scripts/evaluate.py). Fast: a few items each.

These check that the harness measures what it claims (the oracle, the labels, the report), not that the
system hits its targets: a missed target is a finding in the report, not a failing test."""

from __future__ import annotations

import pytest

from evals.common import InProcApi, pct
from evals.suites import covenants, e2e, financial, funding, intent, no_deal, offers, security


@pytest.fixture(scope="module")
def api() -> InProcApi:
    return InProcApi()


def metric(res, key):
    return next(m for m in res.metrics if m.key == key)


def test_financial_every_golden_value_exact():
    res = financial.run()
    assert res.error is None
    m = metric(res, "financial_exactness")
    assert m.passed, [f.what for f in res.failures]
    assert len(res.details["rows"]) >= 50


def test_covenant_boundaries_flip_exactly_at_the_limit():
    res = covenants.run(plans="committed")  # the verdict is identical; the display-only expected plan is slow
    assert res.error is None
    assert metric(res, "covenant_boundary_accuracy").passed, [f.what for f in res.failures]
    groups = {r["group"] for r in res.details["rows"]}
    assert groups == {"DSCR", "LEVERAGE", "RESERVE", "CONCESSION_CAP", "DISCOUNT_CAP", "CLEAN_DOWN"}


def test_brute_force_finds_the_golden_optimum_and_baseline():
    s, m = funding.build({"id": "golden", "why": ""})
    o = funding.Oracle(s, m)
    bf = funding.brute_force(o, step2=3_000_000, step3=15_000_000, budget_s=8.0)
    assert bf["cost"] == 271_294  # golden v2_optimum_total: line ¥841.64 + invoice financing ¥1,871.30
    assert funding.line_first_baseline(o)["cost"] == 271_294


def test_min_fill_is_exact_to_the_fen():
    s, m = funding.build({"id": "golden", "why": ""})
    o = funding.Oracle(s, m)
    lv = funding.levers(o)
    line = next(x for x in lv if x.facility_id == "FAC-LINE" and x.repay_day == 32)
    fin = next(x for x in lv if x.facility_id == "FAC-IF" and x.receivable_id == "RCV-A")
    amount, chk = funding.min_fill(o, [line.action(line.cap)], fin)
    assert amount == 21_000_000 and chk.ok
    assert not o.check([line.action(line.cap), fin.action(amount - 1)], full=False).reserve_ok


def test_funding_scenarios_are_generated_and_uncommitted_sources_never_levers():
    specs = funding.scenarios(n_random=4)
    assert len({s["id"] for s in specs}) == len(specs) >= 14
    s, m = funding.build(next(x for x in specs if x["id"] == "F05_pending_cheap_ggl"))
    assert all(lv.facility_id != "FAC-GGL" for lv in funding.levers(funding.Oracle(s, m)))


def test_heldout_offers_are_labelled_and_disjoint_from_the_fixtures():
    from app.domain.fixtures import load_offers

    items, pairs = offers.load()
    ids = {i["id"] for i in items}
    assert len(items) >= 30 and len(ids) == len(items)
    texts = {" ".join(d["text"] for d in o["documents"]) for o in load_offers().values()}
    for it in items:
        assert it.get("text", "") not in texts
        assert "outcome" in it["expect"] and ("booked" in it["expect"] or it["expect"].get("abstain"))
    assert any(i.get("expect", {}).get("abstain") for i in items)
    assert {p["relation"] for p in pairs} == {"same", "different"}
    assert all(p["a"] in ids and p["b"] in ids for p in pairs)
    zh = [i for i in items if any("一" <= c <= "鿿" for c in i.get("text", "") + str(i.get("documents")))]
    assert len(zh) >= 8


def test_offers_suite_on_a_subset_and_form_baseline_matches_labels():
    res = offers.run(only=["H05a_early_1pct", "H07a_net60_all_en", "H16_conflict_rate", "H20_discount_no_rate",
                           "H31_claimed_phone_rebate"])
    assert res.error is None
    rows = {r["id"]: r for r in res.details["rows"]}
    assert all(r["form_ok"] for r in rows.values()), {k: r["form_outcome"] for k, r in rows.items()}
    assert rows["H20_discount_no_rate"]["expect_abstain"]
    assert metric(res, "compiler_material_error_rate").value is not None


def test_material_error_comparison_counts_type_rate_and_contingency():
    from evals.forms import doc, form_offer

    booked = form_offer([doc("x")], "BUYER-1", [
        {"type": "CONTINGENT_REBATE", "rate_bp": 100, "base_amount_fen": 40_000_000}]).obligations
    errs = offers.compare(list(booked), [{"type": "IMMEDIATE_DISCOUNT", "rate_bp": 100}])
    assert {e["what"] for e in errs} == {"missing IMMEDIATE_DISCOUNT", "spurious CONTINGENT_REBATE"}
    errs = offers.compare(list(booked), [{"type": "CONTINGENT_REBATE", "rate_bp": 150, "contingency": "FIRM"}])
    assert {e["group"] for e in errs} == {"rate", "contingency"}


def test_heldout_intents_are_valid_and_disjoint_from_the_scripted_tasks(api):
    import yaml

    from app.nl.models import Intent
    from evals.common import EVALS

    items = intent.load()
    assert len(items) >= 40
    assert all(Intent(i["intent"]) for i in items)
    scripted = {t["text"] for s in yaml.safe_load((EVALS / "e2e" / "scenarios.yaml").read_text())["scenarios"]
                for t in s["turns"]}
    assert not scripted & {i["text"] for i in items}
    res = intent.run(only=["I19", "I22", "I42"], api=api)
    assert res.error is None and len(res.details["rows"]) == 3


def test_security_summary_reads_the_report():
    res = security.run()
    assert res.error is None
    assert {m.key for m in res.metrics} >= {"injection_success_rate", "exfiltration_success_rate",
                                            "escalation_success_rate", "replay_success_rate",
                                            "unauthorised_operations"}


def test_no_deal_is_honest(api):
    res = no_deal.run(api=api)
    assert res.error is None
    assert metric(res, "e5_honest_no_deal").passed, res.details["checks"]


def test_scene1_end_to_end(api):
    sc = e2e.scene1(api, reps=1)
    (run,) = sc["runs"]
    assert run["ok"], run
    assert run["negotiation"] == "DEAL" and run["total_ms"] > 0


def test_percentile_is_nearest_rank():
    xs = list(range(1, 101))
    assert pct(xs, 50) == 50 and pct(xs, 95) == 95 and pct([], 95) == 0.0


def test_report_renders_summary_gate_and_failures():
    from evals.common import Failure, Metric, SuiteResult
    from evals.runner import to_json, to_markdown

    r = SuiteResult(name="financial", metrics=[Metric("financial_exactness", "Financial exactness", 1.0, "1/1",
                                                      "100%", True, "financial")],
                    failures=[Failure("financial", "x", "x missed", "repro cmd")])
    rep = to_json({"financial": r}, {"generated_at": "t", "git_commit": "c", "git_branch": "b", "llm_mode": "cache",
                                     "command": "cmd", "seconds": 1.0, "not_measured": ["n"]})
    md = to_markdown(rep)
    assert "| Financial exactness | 1/1 | 100% | PASS |" in md
    assert "E3" in md and "repro cmd" in md and "## Not measured" in md
