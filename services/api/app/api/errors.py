"""One HTTP mapping for storage conflicts, shared by every route that writes.

A `DocumentAlreadyDecided` that reaches the route (two requests decided one document at the same moment, in two
processes) is a 409 `ALREADY_DECIDED`: the first decision stands, this request kept nothing.

A `ConcurrentWriteConflict` that survives the retries of the unit of work (`Executor._atomically`,
`clock.advance`) means another writer committed first, every time. Nothing of this request was kept, so the
caller may simply send it again: the answer is 409 with a retry hint, never a 500.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.persistence import ConcurrentWriteConflict, DocumentAlreadyDecided

RETRY_AFTER_SECONDS = 1
CONFLICT_CODE = "CONCURRENT_WRITE_CONFLICT"
ALREADY_DECIDED_CODE = "ALREADY_DECIDED"


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


async def document_already_decided_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """Another writer decided the document between this request's read and its write. The decision that won stands; this
    one kept nothing. Not a retry: reload the document to see what was decided."""
    return JSONResponse(status_code=409, content={"detail": {
        "code": ALREADY_DECIDED_CODE,
        "message": "this document was decided at the same moment by another request; nothing of this one was saved",
    }})


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ConcurrentWriteConflict, concurrent_write_conflict_handler)
    app.add_exception_handler(DocumentAlreadyDecided, document_already_decided_handler)
