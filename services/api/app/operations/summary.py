"""Security summary over the operations log: what was refused and whether anything slipped through."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.domain.models import (
    Actor,
    AddFacility,
    ChangeMandate,
    IssueEquity,
    OperationStatus,
    PledgeCollateral,
    SignPersonalGuarantee,
    Tier,
)
from app.domain.ports import LedgerStore
from app.operations.log import parse_entry
from app.persistence import ApprovalStatus

_TIER3_TYPES = (SignPersonalGuarantee, PledgeCollateral, IssueEquity, ChangeMandate)


def security_summary(store: LedgerStore) -> dict[str, Any]:
    """Counts for the security dashboard. `facilities_added_by_non_owner` and
    `unauthorised_executions` must both be 0; `chain_valid` must be True.

    An execution is unauthorised when it is a Tier-3 kind, an AddFacility not requested by the
    owner, or a Tier-2 operation with no APPROVED owner decision."""
    entries = [parse_entry(r) for r in store.operations()]
    approved_op_ids = {a.op_id for a in store.approvals(ApprovalStatus.APPROVED)}
    refused_by_code: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    added_by_non_owner = 0
    unauthorised = 0
    for e in entries:
        status_counts[e.result.status.value] += 1
        if e.result.status == OperationStatus.REFUSED:
            for v in e.result.violations:
                refused_by_code[v.code.value] += 1
            continue
        if e.result.status != OperationStatus.EXECUTED or e.op is None:
            continue
        op = e.op
        if isinstance(op, AddFacility) and op.requested_by != Actor.OWNER:
            added_by_non_owner += 1
            unauthorised += 1
        else:
            tier3 = isinstance(op, _TIER3_TYPES) or e.result.tier == Tier.TIER_3
            unapproved_tier2 = e.result.tier == Tier.TIER_2 and op.op_id not in approved_op_ids
            unauthorised += int(tier3 or unapproved_tier2)
    return {
        "operations": len(entries),
        "by_status": dict(sorted(status_counts.items())),
        "refused_by_code": dict(sorted(refused_by_code.items())),
        "refused_total": status_counts.get(OperationStatus.REFUSED.value, 0),
        "security_events": len(store.security_events()),
        "facilities_added_by_non_owner": added_by_non_owner,
        "unauthorised_executions": unauthorised,
        "chain_valid": store.verify_chain(),
    }
