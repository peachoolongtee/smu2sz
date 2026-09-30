"""Borrower file endpoints (flag `borrower_file`). To be mounted by the main architect.

POST /borrower-file builds the file from verified state and queues a typed GenerateBorrowerFile
through the executor, which makes it Tier 2 (PENDING_APPROVAL). The file is prepared, never sent:
the owner downloads and submits it. Downloads: GET /borrower-file/{file_id}.html | .docx | .pdf.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import require_owner
from app.api.display import displayed
from app.api.runtime import Runtime, get_runtime
from app.borrower_file import (
    TITLE_EN,
    BorrowerFile,
    BorrowerFileError,
    build,
    pdf_renderer,
    render_docx,
    render_html,
    render_pdf,
)
from app.domain.models import Actor, GenerateBorrowerFile, OperationResult

router = APIRouter(dependencies=[Depends(require_owner)])

# Files built in this process, by id. A file is a snapshot of verified state with its own provenance
# footer (state version, mandate version, chain head); rebuilding with the same request on the same
# state gives the same id.
_FILES: dict[str, tuple[BorrowerFile, OperationResult]] = {}

DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _require_enabled(rt: Runtime) -> None:
    if not rt.settings.features.borrower_file:
        raise HTTPException(403, detail={"code": "FEATURE_DISABLED", "feature": "borrower_file",
                                         "message": "The borrower file is switched off (FEATURE_BORROWER_FILE)."})


class BorrowerFileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facility_id: str
    amount_fen: int = Field(gt=0)
    use_of_proceeds: str = Field(min_length=1, max_length=500)
    spend_day: int | None = None  # owner estimate: the day the proceeds are spent
    ebitda_uplift_fen: int | None = None  # owner estimate: shown, never projected


def _approval_status(rt: Runtime, result: OperationResult) -> str | None:
    if not result.approval_id:
        return None
    rec = rt.store.get_approval(result.approval_id)
    return str(getattr(rec.status, "value", rec.status)) if rec is not None else None


def _view(rt: Runtime, bf: BorrowerFile, result: OperationResult) -> dict[str, Any]:
    sections = []
    for s in bf.sections:
        sections.append({
            "key": s.key,
            "title": s.title_en,
            "title_zh": s.title_zh,
            "columns": s.columns,
            "rows": [{"label": r.label, "value": r.value, "evidence": r.evidence, "note": r.note,
                      "figures": [json.loads(f.model_dump_json()) for f in r.figures]} for r in s.rows],
            "notes": s.notes,
        })
    pdf = pdf_renderer()
    return displayed({
        "file_id": bf.file_id,
        "status": bf.status,
        "style": f"{TITLE_EN} · lender mocked",
        "title_en": bf.title_en,
        "title_zh": bf.title_zh,
        "lender_mocked": bf.lender_mocked,
        "lender_note": bf.lender_note,
        "facility_id": bf.facility_id,
        "amount_fen": bf.amount_fen,
        "use_of_proceeds": bf.use_of_proceeds,
        "sections": sections,
        "approval_id": result.approval_id,
        "approval_status": _approval_status(rt, result),
        "operation": json.loads(result.model_dump_json()),
        "generated_day": bf.generated_day,
        "provenance": json.loads(bf.provenance.model_dump_json()),
        "downloads": {
            "html": f"/borrower-file/{bf.file_id}.html",
            "docx": f"/borrower-file/{bf.file_id}.docx",
            "pdf": f"/borrower-file/{bf.file_id}.pdf" if pdf else None,
        },
        "pdf_note": None if pdf else "PDF skipped: no local PDF renderer is installed; print the HTML to PDF.",
    })


@router.post("/borrower-file")
def post_borrower_file(body: BorrowerFileIn) -> dict[str, Any]:
    rt = get_runtime()
    _require_enabled(rt)
    with rt.lock:
        try:
            bf = build(rt.store, facility_id=body.facility_id, amount_fen=body.amount_fen,
                       use_of_proceeds=body.use_of_proceeds, day=rt.day, spend_day=body.spend_day,
                       ebitda_uplift_fen=body.ebitda_uplift_fen)
        except BorrowerFileError as exc:
            raise HTTPException(422, str(exc)) from None
        op = GenerateBorrowerFile(op_id=f"OP-{bf.file_id}", idempotency_key=f"borrower-file:{bf.file_id}",
                                  mandate_version=rt.store.get_mandate().version, requested_by=Actor.AGENT,
                                  day=rt.day, facility_id=bf.facility_id, amount_fen=bf.amount_fen)
        result = rt.executor.execute(op)  # Tier 2: PENDING_APPROVAL; the executor computes the tier
        if bf.file_id in _FILES:  # the same request on the same verified state: keep the first snapshot
            bf = _FILES[bf.file_id][0]
        else:
            _FILES[bf.file_id] = (bf, result)
        return _view(rt, bf, result)


def _get(rt: Runtime, file_id: str) -> tuple[BorrowerFile, OperationResult]:
    _require_enabled(rt)
    found = _FILES.get(file_id)
    if found is None:
        raise HTTPException(404, "borrower file not found; POST /borrower-file first")
    return found


def _attachment(file_id: str, ext: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{file_id}.{ext}"'}


@router.get("/borrower-file/{file_id}.html", response_class=HTMLResponse)
def get_borrower_file_html(file_id: str) -> HTMLResponse:
    bf, _ = _get(get_runtime(), file_id)
    return HTMLResponse(render_html(bf))


@router.get("/borrower-file/{file_id}.docx")
def get_borrower_file_docx(file_id: str) -> Response:
    bf, _ = _get(get_runtime(), file_id)
    return Response(render_docx(bf), media_type=DOCX_MEDIA, headers=_attachment(bf.file_id, "docx"))


@router.get("/borrower-file/{file_id}.pdf")
def get_borrower_file_pdf(file_id: str) -> Response:
    bf, _ = _get(get_runtime(), file_id)
    pdf = render_pdf(bf)
    if pdf is None:
        raise HTTPException(501, "PDF skipped: no local PDF renderer is installed; download the HTML and print it")
    return Response(pdf, media_type="application/pdf", headers=_attachment(bf.file_id, "pdf"))


@router.get("/borrower-file/{file_id}")
def get_borrower_file(file_id: str) -> dict[str, Any]:
    rt = get_runtime()
    bf, result = _get(rt, file_id)
    return _view(rt, bf, result)
