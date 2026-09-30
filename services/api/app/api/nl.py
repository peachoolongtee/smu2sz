"""POST /nl: the multi-turn natural-language harness. Owned by the /nl agent; mounted by main.

The owner is authenticated here (X-Owner-Token via Runtime.is_owner) and only a boolean reaches
app.nl. Without the token an OWNER request acts as the AGENT: Tier-1 plans still run, owner decisions
on the approvals queue are refused by the executor.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.api.auth import is_agent
from app.api.display import displayed
from app.api.runtime import get_runtime
from app.nl import NlRequest, handle, reset_sessions

router = APIRouter()


@router.post("/nl")
def post_nl(body: NlRequest, x_owner_token: str | None = Header(default=None),
            x_agent_key: str | None = Header(default=None)) -> dict:
    rt = get_runtime()
    if str(getattr(body.actor, "value", body.actor)) != "COUNTERPARTY" and not (
            rt.is_owner(x_owner_token) or is_agent(x_agent_key)):
        raise HTTPException(401, {"code": "CREDENTIAL_REQUIRED",
                                  "message": "owner token or agent key required for the owner channel"})
    with rt.lock:
        resp = handle(body, store=rt.store, executor=rt.executor, day=rt.day, owner_key_hex=rt.owner_key_hex,
                      owner_authenticated=rt.is_owner(x_owner_token))
    out = resp.model_dump(mode="json")
    out["verdict"] = displayed(out["verdict"]) if out["verdict"] is not None else None
    out["operations"] = displayed(out["operations"])
    return out


@router.post("/nl/reset")
def post_nl_reset(x_owner_token: str | None = Header(default=None)) -> dict:
    """Drop every /nl session (demo and scenario runs). Owner only."""
    if not get_runtime().is_owner(x_owner_token):
        raise HTTPException(403, "owner token required")
    reset_sessions()
    return {"ok": True}
