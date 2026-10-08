"""POST /nl: the multi-turn natural-language harness. Owned by the /nl agent; mounted by main.

The owner is authenticated here (X-Owner-Token via Runtime.is_owner) and only a boolean reaches
app.nl. Without the token an OWNER request acts as the AGENT: Tier-1 plans still run, owner decisions
on the approvals queue are refused by the executor.

A COUNTERPARTY is identified by X-Counterparty-Key (auth.counterparty_for_key), never by the body: a valid key binds
the sender id (a different counterparty_id in the body is a 403 and a security event) and gets the autonomous Tier-1
handling; no key or a wrong key (also a security event) is a proposal only, so nothing is executed or booked.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import counterparty_for_key, is_agent
from app.api.display import displayed
from app.api.home import get_home
from app.api.offers import enforce_intake_cap
from app.api.presentation import business_text
from app.api.runtime import get_runtime
from app.api.views import owner_verdict_extras
from app.nl import NlRequest, handle, opener, reset_sessions
from app.nl.binding import OwnerReads
from app.nl.offers import COUNTERPARTY_AUTHENTICATED
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


def _owner_reads(rt) -> OwnerReads:
    """What the owner's chat may read besides the stores: the Home read (the sentences and figures GET /home writes),
    the Business-words rewrite of an engine sentence, and the runtime's latest verdict per offer. Called under the
    runtime lock; owner turns only."""
    def home(lang: str, since_day: int | None):
        try:
            return get_home(lang=lang, since_day=since_day)
        except HTTPException:  # the books cannot be projected: the read says so rather than guessing
            return None

    def words(text: str, lang: str) -> str:
        return business_text(rt.store.get_state(), text, rt.day, "zh" if lang == "zh" else "en") or text

    return OwnerReads(home=home, words=words, latest_verdict=rt.latest_verdict)


def _security_event(rt, kind: str, claimed: str | None, action: str, detail: str) -> None:
    import hashlib

    from app.domain.models import SecurityEvent, SecurityEventKind

    key = f"{kind} {claimed} {rt.day} {len(rt.store.security_events())}"
    rt.store.add_security_event(SecurityEvent(
        id="SEC-CPKEY-" + hashlib.sha256(key.encode()).hexdigest()[:12], day=rt.day,
        kind=SecurityEventKind.PRIVILEGE_ESCALATION, counterparty_id=claimed, action_taken=action, detail=detail))


@router.post("/nl")
def post_nl(body: NlRequest, x_owner_token: str | None = Header(default=None),
            x_agent_key: str | None = Header(default=None),
            x_counterparty_key: str | None = Header(default=None)) -> dict:
    rt = get_runtime()
    is_counterparty = str(getattr(body.actor, "value", body.actor)) == "COUNTERPARTY"
    if not is_counterparty and not (rt.is_owner(x_owner_token) or is_agent(x_agent_key)):
        raise HTTPException(401, {"code": "CREDENTIAL_REQUIRED",
                                  "message": "owner token or agent key required for the owner channel"})
    channel_authenticated = False
    if is_counterparty:
        # The sender is whoever the channel key says, never whoever the body claims.
        bound = counterparty_for_key(x_counterparty_key)
        if bound is not None:
            if body.counterparty_id is not None and body.counterparty_id != bound:
                with rt.lock:
                    _security_event(rt, "mismatch", body.counterparty_id,
                                    "request refused before reaching any module",
                                    f"counterparty channel key for {bound} used with a different counterparty_id in the body")
                raise HTTPException(403, {"code": "COUNTERPARTY_MISMATCH",
                                          "message": "the channel key does not belong to the stated counterparty"})
            body = body.model_copy(update={"counterparty_id": bound})
            channel_authenticated = True
        elif not (rt.is_owner(x_owner_token) or is_agent(x_agent_key)):
            enforce_intake_cap(rt, "POST /nl", body.counterparty_id)  # R04, R05: 429 over the daily cap
        if bound is None and x_counterparty_key:
            with rt.lock:
                _security_event(rt, "wrong-key", body.counterparty_id, "treated as an unauthenticated proposal; nothing executed",
                                "counterparty message with an unknown X-Counterparty-Key")
    with rt.lock:
        token = COUNTERPARTY_AUTHENTICATED.set(channel_authenticated)
        try:
            resp = handle(body, store=rt.store, executor=rt.executor, day=rt.day, owner_key_hex=rt.owner_key_hex,
                          owner_authenticated=rt.is_owner(x_owner_token),
                          verdict_extras=None if is_counterparty else owner_verdict_extras,
                          owner_reads=_owner_reads(rt) if not is_counterparty and rt.is_owner(x_owner_token) else None)
        finally:
            COUNTERPARTY_AUTHENTICATED.reset(token)
    out = resp.model_dump(mode="json")
    if is_counterparty:
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
                                owner_key_hex=rt.owner_key_hex, verdict_extras=owner_verdict_extras)
    out = resp.model_dump(mode="json")
    out["verdict"] = displayed(out["verdict"]) if out["verdict"] is not None else None
    out["operations"] = displayed(out["operations"])
    out["proactive"] = True
    out["has_news"] = has_news
    return out
