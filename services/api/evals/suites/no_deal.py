"""E5 honest NO DEAL: the hard-line buyer (reservation outside the admissible set) refuses every counter
within the bounded rounds; the system says NO DEAL, fabricates no agreement and still funds the gap
from committed sources, so the conservative trajectory holds the reserve."""

from __future__ import annotations

from typing import Any

from evals.common import Failure, InProcApi, Metric, SuiteResult, quiet

REPRO = "uv run --project services/api python scripts/evaluate.py --suite no_deal"


def run(api: InProcApi | None = None, **_: Any) -> SuiteResult:
    quiet()
    from app.counterparties.profiles import get_profile
    from app.domain.models import Mode
    from app.financial import project

    res = SuiteResult(name="no_deal")
    api = api or InProcApi()
    api.reset()
    _, off = api.post("/offers", {"fixture_id": "EX01_PACKAGE"})
    oid = off["offer"]["offer_id"]
    _, ver = api.post(f"/offers/{oid}/evaluate", {"fixture_id": "EX01_PACKAGE"})
    code, neg = api.post(f"/negotiate/{oid}", {"buyer_profile": "hard_line"})
    state = api.rt.store.get_state()
    m = api.rt.store.get_mandate()
    after = project(state, [], [], Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    try:
        max_rounds = get_profile("BUYER-1-HARDLINE").max_rounds
    except Exception:  # noqa: BLE001 - the profile loader is not part of the contract; fall back to the spec's 3
        max_rounds = 3
    ops = [(o.get("kind"), o.get("status")) for o in neg.get("operations", [])]
    commitments = api.rt.store.commitments()
    checks = {
        "http_200": code == 200,
        "verdict_is_not_accept": ver.get("outcome") in ("REJECT", "COUNTER"),
        "outcome_no_deal": neg.get("outcome") == "NO_DEAL",
        "bounded_rounds": 0 < len(neg.get("rounds", [])) <= max_rounds,
        "no_fabricated_agreement": neg.get("accepted_counter_id") is None and neg.get("commitment") is None
        and not any(k == "ACCEPT_OFFER" for k, _ in ops) and not commitments,
        "gap_funded_executed": bool(ops) and all(s == "EXECUTED" for _, s in ops),
        "reserve_holds_after": after.first_breach_day is None,
    }
    res.details = {"checks": checks, "rounds": neg.get("rounds"), "operations": ops, "message": neg.get("message"),
                   "cash_after_fen": state.cash_fen, "min_cash_after_fen": after.min_cash_fen,
                   "min_cash_day": after.min_cash_day, "max_rounds": max_rounds}
    ok = all(checks.values())
    res.metrics.append(Metric("e5_honest_no_deal", "E5 hard-line buyer → NO_DEAL, gap still funded", ok,
                              f"{sum(checks.values())}/{len(checks)} checks", "all", ok, "no_deal",
                              f"{len(neg.get('rounds', []))} rounds; ops {', '.join(k for k, _ in ops)}"))
    for k, v in checks.items():
        if not v:
            res.failures.append(Failure("no_deal", k, f"E5 check failed: {k}", REPRO, res.details))
    return res
