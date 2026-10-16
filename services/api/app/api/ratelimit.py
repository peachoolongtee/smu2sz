"""Request rate limits per caller (security register SEC-20).

Before this, nothing limited how fast anyone could call the API: the anonymous intake cap counts submissions per simulated day, and the
keyed buyer's budget counts offers and messages per day, but neither limits requests per second, and every other route answered as fast
as it was asked. A token bucket per caller now refuses a burst with 429 `RATE_LIMITED` and a `Retry-After` header.

A caller is the credential it proves, else its address:
- the owner token, the agent key and the bank-feed key: one bucket per credential and client address;
- a buyer's channel key: one bucket per buyer;
- anyone else (no credential, or a wrong one): one bucket per client address.

Limits are requests per minute, from the environment (`RATE_LIMIT_OWNER` 3000, `RATE_LIMIT_AGENT` 1200, `RATE_LIMIT_BANK` 600,
`RATE_LIMIT_BUYER` 120, `RATE_LIMIT_ANON` 300); `RATE_LIMITS=0` turns them off. They are generous for one owner's browser and a script, and
far below what a flood needs. Behind a reverse proxy every caller has the proxy's address: there the proxy's own per-client limit is the
one that separates callers (the release gate asks for it), and this one still caps the total.

The buckets live in this process only (one uvicorn process, as deployed) and start empty with each new runtime (`set_runtime`), so a
test's fresh runtime starts with fresh buckets. A refusal is logged once per caller per minute, never per request.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse

from app.api.auth import counterparty_for_key, is_agent, is_bank_feed, is_owner

log = logging.getLogger("termsledger.ratelimit")

DEFAULTS = {"owner": 3000, "agent": 1200, "bank": 600, "buyer": 120, "anon": 300}
MAX_BUCKETS = 10_000  # one bucket per caller; past this the idlest are dropped, so the table itself cannot be flooded


@dataclass
class _Bucket:
    tokens: float
    stamp: float
    logged: float = -1e9


_buckets: dict[tuple[str, str], _Bucket] = {}
_lock = threading.Lock()


def enabled() -> bool:
    return os.environ.get("RATE_LIMITS", "1").strip().lower() not in {"0", "false", "no", "off"}


def limit_for(kind: str) -> int:
    raw = os.environ.get(f"RATE_LIMIT_{kind.upper()}")
    try:
        return max(0, int(raw)) if raw is not None and raw.strip() else DEFAULTS[kind]
    except ValueError:
        return DEFAULTS[kind]


def reset() -> None:
    """Empty every bucket (a new runtime: `app.api.runtime.set_runtime`)."""
    with _lock:
        _buckets.clear()


def caller(request: Request) -> tuple[str, str]:
    """(kind, key) of the caller: the credential it proves, else its address."""
    h = request.headers
    addr = request.client.host if request.client is not None else "unknown"
    if is_owner(h.get("x-owner-token")):
        return "owner", addr
    if is_agent(h.get("x-agent-key")):
        return "agent", addr
    if is_bank_feed(h.get("x-bank-feed-key")):
        return "bank", addr
    buyer = counterparty_for_key(h.get("x-counterparty-key"))
    if buyer is not None:
        return "buyer", buyer
    return "anon", addr


def take(kind: str, key: str, now: float | None = None) -> float | None:
    """Spend one request from the caller's bucket. None when allowed, else the seconds until the next request is."""
    per_minute = limit_for(kind)
    if per_minute == 0:
        return None
    now = time.monotonic() if now is None else now
    rate = per_minute / 60.0
    with _lock:
        b = _buckets.get((kind, key))
        if b is None:
            if len(_buckets) >= MAX_BUCKETS:
                for k, _ in sorted(_buckets.items(), key=lambda kv: kv[1].stamp)[: MAX_BUCKETS // 10]:
                    del _buckets[k]
            b = _buckets[(kind, key)] = _Bucket(tokens=float(per_minute), stamp=now)
        b.tokens = min(float(per_minute), b.tokens + (now - b.stamp) * rate)
        b.stamp = now
        if b.tokens >= 1.0:
            b.tokens -= 1.0
            return None
        wait = (1.0 - b.tokens) / rate
        if now - b.logged >= 60.0:
            b.logged = now
            log.warning("rate limit: %s caller over %d requests a minute; refused", kind, per_minute)
        return wait


async def middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    if enabled() and request.method != "OPTIONS":  # CORS preflights carry no credential and are answered by the CORS layer
        kind, key = caller(request)
        wait = take(kind, key)
        if wait is not None:
            seconds = max(1, int(wait + 0.999))
            return JSONResponse(status_code=429, headers={"Retry-After": str(seconds)},
                                content={"detail": {"code": "RATE_LIMITED", "retry_after_s": seconds,
                                                    "message": "Too many requests; please wait a moment and try again."}})
    return await call_next(request)
