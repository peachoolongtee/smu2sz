"""The shadow pilot's journal routes (wayfinder map #58; docs/pilot/JOURNAL_SPEC.md). Flag `pilot_journal`, default off: with
it off both routes answer 403 FEATURE_DISABLED and nothing else in the app changes.

`POST /pilot/journal` appends what the owner did against an answer FLOW gave; `GET /pilot/journal` lists the entries, newest
first. Owner only. The journal is its own store table: a write changes neither the financial state, nor the operations log, nor
the hash chain, and logs no operation. There is no edit and no delete.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import require_owner
from app.api.features import require_feature
from app.api.runtime import get_runtime
from app.pilot.journal import JournalEntryIn, PilotJournalStore, entry_from_record

router = APIRouter(tags=["pilot"], dependencies=[Depends(require_owner)])


def _flag_on() -> None:
    """A route dependency, so a body that does not validate is still answered 403 first when the flag is off."""
    require_feature("pilot_journal")


def _journal_store() -> PilotJournalStore:
    store = get_runtime().store
    if not (hasattr(store, "add_pilot_journal") and hasattr(store, "pilot_journal")):
        raise HTTPException(501, detail={"code": "PILOT_JOURNAL_UNSUPPORTED", "message": "This store has no pilot journal."})
    return cast(PilotJournalStore, store)


@router.post("/pilot/journal", status_code=201, dependencies=[Depends(_flag_on)])
def post_journal(body: JournalEntryIn) -> dict[str, Any]:
    rt = get_runtime()
    store = _journal_store()
    state_version = rt.store.get_state().state_version  # read only: stamps the entry with the books it was written against
    rec = store.add_pilot_journal(
        week=body.week, sme=body.sme, answer=body.answer, flow_said=body.flow_said, snapshot_hash=body.snapshot_hash,
        owner_did=body.owner_did, choice=body.choice, recorded_on=body.recorded_on, state_version=state_version, day=rt.day,
    )
    return {"entry": entry_from_record(rec).model_dump(mode="json")}


@router.get("/pilot/journal", dependencies=[Depends(_flag_on)])
def get_journal(week: int | None = Query(default=None, ge=1, le=60), sme: str | None = Query(default=None, max_length=64)) -> dict[str, Any]:
    records = _journal_store().pilot_journal()
    entries = [entry_from_record(r) for r in reversed(records) if (week is None or r.week == week) and (sme is None or r.sme == sme)]
    return {"entries": [e.model_dump(mode="json") for e in entries], "count": len(entries)}
