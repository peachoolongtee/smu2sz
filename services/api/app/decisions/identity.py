"""Decision identity (ADR-0011 section 3): a deterministic id, so the read model and every write agree without a lookup
table. Pure: it reads the operation's payload, its idempotency key and the commitments, and nothing else.

    DEAL                    deal:{offer_id}   (an offer's accept and its reject, whoever asks, belong to the deal)
    FUNDING (alert cure)    alert:{alert_id}:v{state_version}
    FUNDING (router plan)   alert:{alert_id}:v{state_version}:plan
    FUNDING (chat)          nl:{session}:{scope}
    any other approval      approval:{approval_id}

A Tier-1 operation posted directly with no approval is Activity, not a decision: `decision_id_for` returns None for it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from app.domain.models import Commitment

DEAL_PREFIX = "deal:"
APPROVAL_PREFIX = "approval:"

# alert:{alert_id}:v{state_version}:{i}  or  alert:{alert_id}:v{state_version}:plan:{i}
_ALERT = re.compile(r"^alert:(?P<alert>.+):v(?P<sv>\d+):(?P<plan>plan:)?\d+$")
# fund-{offer_id}-{cooperative|hard_line}-{i}: the legs a negotiation funds for the gap
_FUND = re.compile(r"^fund-(?P<offer>.+)-(?:cooperative|hard_line)-\d+$")
# nl:{session}:{scope}:{n}:{kind}; the scope is "r:{request_id}" or "t{turn}:{nonce}", so the decision is the key without
# its last two parts
_NL = re.compile(r"^nl:[^:]+:.+:\d+:[A-Z_]+$")

_ACCEPT = "ACCEPT_OFFER"
_RECORD = "RECORD_COMMITMENT"
_REJECT = "REJECT_OFFER"


def deal_id(offer_id: str) -> str:
    return f"{DEAL_PREFIX}{offer_id}"


def alert_cure_id(alert_id: str, state_version: int) -> str:
    return f"alert:{alert_id}:v{state_version}"


def alert_plan_id(alert_id: str, state_version: int) -> str:
    return f"alert:{alert_id}:v{state_version}:plan"


def approval_decision_id(approval_id: str) -> str:
    return f"{APPROVAL_PREFIX}{approval_id}"


def offer_id_of(decision_id: str) -> str | None:
    """The offer a DEAL decision is about, else None."""
    if decision_id.startswith(DEAL_PREFIX) and len(decision_id) > len(DEAL_PREFIX):
        return decision_id[len(DEAL_PREFIX):]
    return None


def family_of(decision_id: str) -> str | None:
    """DEAL for `deal:`; FUNDING for the alert, chat and `approval:` ids (an offer's own operations are always `deal:`, so
    an `approval:` id is a capex apply or a direct operation); None for anything else."""
    if decision_id.startswith(DEAL_PREFIX):
        return "DEAL"
    if decision_id.startswith(("alert:", "nl:", APPROVAL_PREFIX)):
        return "FUNDING"
    return None


def decision_id_for(
    op_payload: Mapping[str, Any],
    idempotency_key: str,
    commitments: Iterable[Commitment],
    *,
    approval_id: str | None = None,
) -> str | None:
    """The decision an operation belongs to, or None when it belongs to none (Activity).

    `op_payload` is the logged or queued operation as a dict, `idempotency_key` the key it ran under (a non-owner decide
    attempt appends `#decide:...`, which is ignored here), `commitments` the stored commitments (a RECORD_COMMITMENT names
    its commitment, not its offer) and `approval_id` the approval that queued it, if any."""
    key = idempotency_key.split("#", 1)[0]
    kind = op_payload.get("kind")
    if kind in (_ACCEPT, _REJECT) and isinstance(op_payload.get("offer_id"), str):
        return deal_id(op_payload["offer_id"])
    if kind == _RECORD and isinstance(op_payload.get("commitment_id"), str):
        c = next((c for c in commitments if c.id == op_payload["commitment_id"]), None)
        if c is not None:
            return deal_id(c.offer_id)
    m = _ALERT.match(key)
    if m is not None:
        base = alert_cure_id(m["alert"], int(m["sv"]))
        return f"{base}:plan" if m["plan"] else base
    m = _FUND.match(key)
    if m is not None:
        return deal_id(m["offer"])
    if _NL.match(key):
        return key.rsplit(":", 2)[0]
    if approval_id:
        return approval_decision_id(approval_id)
    return None
