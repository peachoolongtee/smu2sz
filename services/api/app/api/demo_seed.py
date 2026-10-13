"""The demo scenarios' seed replay (`fixtures/scenarios/<name>.seed.json`), run by `Runtime.reset_demo` after the books are seeded.

A scenario that opens mid-conversation (the busy company) lists, in this order, the offers to submit and evaluate, the
negotiations to send and the operations to post. Each step goes through the function the route of the same name calls
(`intake_offer`, `evaluate_offer`, `negotiate_offer`, `run_operation`), so the seeded state is what an owner clicking
through would have made, never a copy of the routes' logic. A scenario with no seed file is not replayed. A step that fails
raises `DemoSeedError` naming the step; the caller never leaves half a seed behind without saying so."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError

from app.api.auth import require_feature
from app.api.decide import EvaluateIn, NegotiateIn, evaluate_offer, negotiate_offer
from app.api.offers import OfferIn, intake_offer
from app.api.operations import run_operation
from app.api.runtime import Runtime, get_runtime
from app.domain.fixtures import scenario_seed
from app.domain.models import Actor


class DemoSeedError(Exception):
    """A seed step failed. `step` names it ("offers[2] EX07_CONFLICT: evaluate"), `reason` says why."""

    def __init__(self, step: str, reason: str) -> None:
        super().__init__(f"demo seed step {step} failed: {reason}")
        self.step, self.reason = step, reason


class _Negotiate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offer: str
    mode: Literal["cooperative", "hard_line"] = "cooperative"


class _Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["APPLY_FOR_FACILITY"]
    facility: str
    amount_fen: int
    term_months: int | None = None


class _Seed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offers: list[str] = []
    negotiate: list[_Negotiate] = []
    operations: list[_Operation] = []


def _reason(e: Exception) -> str:
    if isinstance(e, HTTPException):
        return f"{e.status_code} {e.detail}"
    return f"{type(e).__name__}: {e}"


def _guarded(step: str, run: Any) -> Any:
    """Run one step; anything it raises becomes a `DemoSeedError` that names the step."""
    try:
        return run()
    except DemoSeedError:
        raise
    except Exception as e:  # every failure of a step is the seed's, and says which step
        raise DemoSeedError(step, _reason(e)) from e


def replay(rt: Runtime, scenario: str) -> None:
    """Replay the scenario's seed file on `rt`'s freshly seeded books. No file, nothing to do."""
    raw = scenario_seed(scenario)
    if raw is None:
        return
    try:
        seed = _Seed.model_validate(raw)
    except ValidationError as e:
        raise DemoSeedError("seed file", f"{scenario}.seed.json is not valid: {e.error_count()} problem(s), first at "
                                         f"{'.'.join(str(p) for p in e.errors()[0]['loc'])}") from e
    if get_runtime() is not rt:  # the routes read the process runtime; a seed must land on the books it was asked for
        raise DemoSeedError("seed file", "the runtime being reset is not the process runtime")
    offer_ids: dict[str, str] = {}
    for i, fixture_id in enumerate(seed.offers):
        offer_ids[fixture_id] = _guarded(f"offers[{i}] {fixture_id}: submit", lambda f=fixture_id: _submit(rt, f))
        _guarded(f"offers[{i}] {fixture_id}: evaluate", lambda f=fixture_id: _evaluate(offer_ids[f], f))
    for i, n in enumerate(seed.negotiate):
        step = f"negotiate[{i}] {n.offer}"
        if n.offer not in offer_ids:
            raise DemoSeedError(step, "the offer is not in this seed's offers list")
        _guarded(step, lambda n=n: _negotiate(offer_ids[n.offer], n))
    for i, op in enumerate(seed.operations):
        step = f"operations[{i}] {op.kind} {op.facility}"
        _guarded(step, lambda i=i, op=op: _operate(rt, scenario, i, op))


def _submit(rt: Runtime, fixture_id: str) -> str:
    return str(intake_offer(rt, OfferIn(fixture_id=fixture_id))["offer"]["offer_id"])


def _evaluate(offer_id: str, fixture_id: str) -> None:
    require_feature("terms_guard")()
    evaluate_offer(offer_id, EvaluateIn(fixture_id=fixture_id), "en")


def _negotiate(offer_id: str, n: _Negotiate) -> None:
    require_feature("terms_guard")()
    require_feature("buyer_negotiation")()
    negotiate_offer(offer_id, NegotiateIn(buyer_profile=n.mode), "en")


def _operate(rt: Runtime, scenario: str, index: int, op: _Operation) -> None:
    body: dict[str, Any] = {
        "kind": op.kind, "facility_id": op.facility, "amount_fen": op.amount_fen, "term_months": op.term_months,
        "op_id": f"seed-{scenario}-{index}", "idempotency_key": f"seed-{scenario}-{index}",
        "mandate_version": rt.store.get_mandate().version, "requested_by": Actor.AGENT.value}
    result = run_operation(rt, body)["result"]
    if result["status"] not in ("EXECUTED", "PENDING_APPROVAL"):
        raise RuntimeError(f"the executor answered {result['status']}: {result.get('message')}")
