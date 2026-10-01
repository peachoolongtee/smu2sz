"""POST /nl: the multi-turn natural-language harness. Owned by the /nl agent; mounted by main.

The owner is authenticated here (X-Owner-Token via Runtime.is_owner) and only a boolean reaches
app.nl. Without the token an OWNER request acts as the AGENT: Tier-1 plans still run, owner decisions
on the approvals queue are refused by the executor.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import is_agent
from app.api.display import displayed
from app.api.runtime import get_runtime
from app.nl import NlRequest, handle, opener, reset_sessions
from app.nl.service import APPROVAL_ID

router = APIRouter()


COUNTERPARTY_KEYS = ("session_id", "turn", "reply", "intent", "lang", "trace_id")


def _counterparty_view(out: dict) -> dict:
    """Defence in depth: a counterparty gets an allow-list of keys, never the verdict, plan or operations."""
    view = {k: out[k] for k in COUNTERPARTY_KEYS}
    view["intent"] = "COUNTERPARTY_MESSAGE"
    view["reply"] = APPROVAL_ID.sub("the owner's approval", str(view["reply"]))
    view.update(plan=[], verdict=None, operations=[], clarification=None, negotiation=None, security_events=[],
                parse_source="actor", awaiting_confirmation=False, amended=False, replayed=False)
    return view


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
    if str(getattr(body.actor, "value", body.actor)) == "COUNTERPARTY":
        return _counterparty_view(out)
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


class OpenerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    lang: Literal["en", "zh"] | None = None


@router.post("/nl/opener")
def post_nl_opener(body: OpenerRequest, x_owner_token: str | None = Header(default=None)) -> dict:
    """The agent speaks first: what needs the owner today, and the mandate-bounded cure as a pending plan in the
    owner's session. It never executes anything; the owner's next "go ahead" in that session does. Owner only."""
    rt = get_runtime()
    if not rt.is_owner(x_owner_token):
        raise HTTPException(403, "owner token required")
    with rt.lock:
        resp, has_news = opener(body.session_id, body.lang, store=rt.store, executor=rt.executor, day=rt.day,
                                owner_key_hex=rt.owner_key_hex)
    out = resp.model_dump(mode="json")
    out["verdict"] = displayed(out["verdict"]) if out["verdict"] is not None else None
    out["operations"] = displayed(out["operations"])
    out["proactive"] = True
    out["has_news"] = has_news
    return out
