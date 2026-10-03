"""One HTTP mapping for storage conflicts, shared by every route that writes.

A `ConcurrentWriteConflict` that survives the retries of the unit of work (`Executor._atomically`,
`clock.advance`) means another writer committed first, every time. Nothing of this request was kept, so the
caller may simply send it again: the answer is 409 with a retry hint, never a 500.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.persistence import ConcurrentWriteConflict

RETRY_AFTER_SECONDS = 1
CONFLICT_CODE = "CONCURRENT_WRITE_CONFLICT"


async def concurrent_write_conflict_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
        content={"detail": {
            "code": CONFLICT_CODE,
            "message": "another writer changed the books at the same moment; nothing was saved, send the request again",
            "retry": True,
            "retry_after_seconds": RETRY_AFTER_SECONDS,
        }},
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ConcurrentWriteConflict, concurrent_write_conflict_handler)
