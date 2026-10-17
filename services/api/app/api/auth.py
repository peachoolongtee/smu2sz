"""Who is calling. The executor decides what an actor may do; this layer only establishes the actor.

- OWNER: the owner console, authenticated by X-Owner-Token (env OWNER_TOKEN).
- AGENT: the agent's own tool channel (/operations, owner-actor /nl), authenticated by X-Agent-Key
  (env AGENT_KEY). An agent can do Tier 1 inside the mandate, queue Tier 2, never Tier 3.
- COUNTERPARTY: a buyer's own channel, authenticated by X-Counterparty-Key (env COUNTERPARTY_KEYS maps id=key).
  The sender id comes from the key, never from the request body.
- Anyone else: may only submit documents (POST /offers) or talk as an unauthenticated COUNTERPARTY on /nl,
  which compiles and verifies but never executes (proposal only).

DEMO_MODE=1 (off by default since 16 Oct 2026, SEC-07; local demos opt in) accepts the published demo credentials. Without it
the routes fail closed (503) until OWNER_TOKEN / AGENT_KEY are set (security finding F-06)."""

from __future__ import annotations

import hmac
import logging
import os
import threading
import time
import uuid

from fastapi import Header, HTTPException, Request

DEMO_OWNER_TOKEN = "demo-owner-token"
DEMO_AGENT_KEY = "demo-agent-key"
DEMO_BANK_FEED_KEY = "demo-bank-feed-key"
DEMO_COUNTERPARTY_KEYS = {"BUYER-1": "demo-buyer-1-key", "BUYER-2": "demo-buyer-2-key"}


def demo_mode() -> bool:
    from app.config import demo_mode as configured

    return configured()


def _expected(env: str, demo_value: str) -> str | None:
    v = os.environ.get(env)
    if v:
        return v
    return demo_value if demo_mode() else None


def _match(given: str | None, expected: str | None) -> bool:
    return bool(given) and expected is not None and hmac.compare_digest(given or "", expected)


def is_owner(token: str | None) -> bool:
    return _match(token, _expected("OWNER_TOKEN", DEMO_OWNER_TOKEN))


def is_agent(key: str | None) -> bool:
    return _match(key, _expected("AGENT_KEY", DEMO_AGENT_KEY))


def counterparty_keys() -> dict[str, str]:
    """Counterparty channel keys, id -> key. Env COUNTERPARTY_KEYS ("BUYER-1=key,BUYER-2=key"); with it unset the
    published demo keys apply under DEMO_MODE only. Without either, no counterparty can authenticate."""
    raw = os.environ.get("COUNTERPARTY_KEYS")
    if raw is None or not raw.strip():
        return dict(DEMO_COUNTERPARTY_KEYS) if demo_mode() else {}
    out: dict[str, str] = {}
    for part in raw.split(","):
        cid, sep, key = part.partition("=")
        if sep and cid.strip() and key.strip():
            out[cid.strip()] = key.strip()
    return out


def counterparty_for_key(key: str | None) -> str | None:
    """The counterparty id a presented X-Counterparty-Key is bound to, else None. Constant-time per comparison;
    every configured key is compared so a miss does not reveal how many ids match."""
    if not key:
        return None
    found: str | None = None
    given = key.encode("utf-8")
    for cid, expected in counterparty_keys().items():
        if hmac.compare_digest(given, expected.encode("utf-8")) and found is None:
            found = cid
    return found


# SEC-10: refusals are evidence, but an anonymous caller must not be able to grow the store without bound. A runtime (one per process)
# records at most this many refused credentials per wall-clock hour, then one event saying further refusals that hour are counted and
# not recorded. The count lives on the runtime, so a fresh runtime (a restart, a test) starts with a fresh budget.
# SEC-26: one client address may use only a share of that budget, so a single prober cannot spend it in a minute and hide everyone
# else's refusals for the rest of the hour; and what is not recorded is still counted: a warning line once a minute while refusals go
# unrecorded, and one event when the hour turns saying how many refusals, from how many addresses, were counted but not recorded.
REFUSAL_EVENTS_PER_HOUR = 300
REFUSAL_EVENTS_PER_SOURCE_HOUR = 30
_refusal_lock = threading.Lock()
_log = logging.getLogger("termsledger.auth")


def _take_refusal_slot(rt: object, source: str) -> tuple[bool, str | None, dict | None]:
    """(record this refusal, why this is the last one recorded for the hour or the source, last hour's uncounted refusals to report)."""
    hour = int(time.time() // 3600)
    with _refusal_lock:
        budget = rt.__dict__.setdefault("_refusal_budget", {"hour": hour, "used": 0, "sources": {}, "unrecorded": {}, "warned": 0.0})
        closed = None
        if budget["hour"] != hour:
            if budget["unrecorded"]:
                closed = {"hour": budget["hour"], "unrecorded": dict(budget["unrecorded"])}
            budget.update(hour=hour, used=0, sources={}, unrecorded={}, warned=0.0)
        mine = budget["sources"][source] = budget["sources"].get(source, 0) + 1
        if budget["used"] < REFUSAL_EVENTS_PER_HOUR + 1 and mine <= REFUSAL_EVENTS_PER_SOURCE_HOUR + 1:
            budget["used"] += 1
            if budget["used"] == REFUSAL_EVENTS_PER_HOUR + 1:
                return True, "hour", closed
            return True, ("source" if mine == REFUSAL_EVENTS_PER_SOURCE_HOUR + 1 else None), closed
        budget["unrecorded"][source] = budget["unrecorded"].get(source, 0) + 1
        now = time.monotonic()
        if now - budget["warned"] >= 60:
            budget["warned"] = now
            total = sum(budget["unrecorded"].values())
            _log.warning("refused credentials not recorded this hour: %d from %d address(es) (SEC-10 budget)", total,
                         len(budget["unrecorded"]))
    return False, None, closed


def log_refusal(request: Request, why: str, counterparty_id: str | None = None) -> None:
    """Every rejected credential is evidence (a probe, a misconfiguration or a stolen link), up to the hourly budget (SEC-10) and each
    address's share of it (SEC-26). The id is random: it never reads the stored events (that read grew with every refusal) and two
    concurrent refusals never share one."""
    from app.api.runtime import get_runtime
    from app.domain.models import SecurityEvent, SecurityEventKind

    rt = get_runtime()
    source = request.client.host if request.client is not None else "unknown"
    record, last, closed = _take_refusal_slot(rt, source)

    def add(detail: str, cp: str | None) -> None:
        rt.store.add_security_event(SecurityEvent(
            id="SEC-AUTH-" + uuid.uuid4().hex[:16], day=rt.day,
            kind=SecurityEventKind.PRIVILEGE_ESCALATION, counterparty_id=cp,
            action_taken="request refused before reaching any module", detail=detail,
        ))

    if closed is not None:
        n, k = sum(closed["unrecorded"].values()), len(closed["unrecorded"])
        add(f"{n} refused credentials from {k} address(es) were counted but not recorded in the hour starting "
            f"{time.strftime('%Y-%m-%d %H:00Z', time.gmtime(closed['hour'] * 3600))} (SEC-10 budget)", None)
    if not record:
        return
    detail = f"{why}: {request.method} {request.url.path}"
    if last == "hour":
        detail = (f"more than {REFUSAL_EVENTS_PER_HOUR} refused credentials this hour; further refusals this hour are counted, "
                  f"not recorded (latest: {detail})")
    elif last == "source":
        detail = (f"more than {REFUSAL_EVENTS_PER_SOURCE_HOUR} refused credentials from one address this hour; its further refusals "
                  f"this hour are counted, not recorded (latest: {detail})")
    add(detail, counterparty_id)


def is_bank_feed(key: str | None) -> bool:
    """The simulated bank feed (receipts arrive as SYSTEM); env BANK_FEED_KEY."""
    return _match(key, _expected("BANK_FEED_KEY", DEMO_BANK_FEED_KEY))


def require_owner(request: Request, x_owner_token: str | None = Header(default=None)) -> None:
    if _expected("OWNER_TOKEN", DEMO_OWNER_TOKEN) is None:
        raise HTTPException(503, {"code": "OWNER_TOKEN_NOT_CONFIGURED", "message": "set OWNER_TOKEN (DEMO_MODE=0)"})
    if not is_owner(x_owner_token):
        log_refusal(request, "owner token missing or wrong")
        raise HTTPException(401, {"code": "OWNER_TOKEN_REQUIRED", "message": "owner token missing or wrong"})


def require_owner_or_agent(request: Request, x_owner_token: str | None = Header(default=None),
                           x_agent_key: str | None = Header(default=None)) -> None:
    if is_owner(x_owner_token) or is_agent(x_agent_key):
        return
    if _expected("OWNER_TOKEN", DEMO_OWNER_TOKEN) is None and _expected("AGENT_KEY", DEMO_AGENT_KEY) is None:
        raise HTTPException(503, {"code": "CREDENTIALS_NOT_CONFIGURED", "message": "set OWNER_TOKEN and AGENT_KEY"})
    log_refusal(request, "owner token or agent key missing or wrong")
    raise HTTPException(401, {"code": "CREDENTIAL_REQUIRED", "message": "owner token or agent key required"})


def require_feature(name: str):
    """A route dependency: 403 FEATURE_DISABLED when the flag is off (app/config.py Features)."""
    def dep() -> None:
        from app.config import get_settings

        if not getattr(get_settings().features, name):
            raise HTTPException(403, {"code": "FEATURE_DISABLED", "feature": name})

    return dep
