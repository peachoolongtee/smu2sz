"""The simulated clock. Time moves only here (ADR-0006 §2): the owner advances it, the books close the days passed, and nothing is ever
recorded as received. The bank feed records receipts (POST /operations as SYSTEM) but no longer moves time: alone it could expire the
mandate, close days and post debt service, irreversibly (security register SEC-09)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.auth import log_refusal
from app.api.runtime import get_runtime
from app.domain.money import fmt_yuan

router = APIRouter()

MAX_STEP_DAYS = 366


class AdvanceIn(BaseModel):
    to_day: int | None = Field(default=None, ge=0)
    days: int | None = Field(default=None, ge=1, le=MAX_STEP_DAYS)


@router.get("/clock")
def get_clock() -> dict:
    return {"day": get_runtime().day}


@router.post("/clock/advance")
def advance_clock(body: AdvanceIn, request: Request, x_owner_token: str | None = Header(default=None)) -> dict:
    rt = get_runtime()
    if not rt.is_owner(x_owner_token):
        log_refusal(request, "clock advance without the owner token")
        raise HTTPException(403, {"code": "CREDENTIAL_REQUIRED", "message": "owner token required"})
    if (body.to_day is None) == (body.days is None):
        raise HTTPException(422, "give exactly one of to_day or days")
    target = body.to_day if body.to_day is not None else rt.day + (body.days or 0)
    if target < rt.day:
        raise HTTPException(409, {"code": "CLOCK_BACKWARDS", "message": f"today is day {rt.day}; time only moves forward"})
    if target - rt.day > MAX_STEP_DAYS:
        raise HTTPException(422, f"at most {MAX_STEP_DAYS} days per step")
    adv = rt.advance_to(target)
    out = asdict(adv)
    out["result"] = adv.result.model_dump(mode="json") if adv.result is not None else None
    out["day"] = rt.day
    out["posted_net_display"] = fmt_yuan(adv.posted_net_fen)
    return out
