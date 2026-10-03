"""Borrower file endpoints (flag `borrower_file`). To be mounted by the main architect.

POST /borrower-file builds the file from verified state for the owner. It is a read-only action: nothing
is logged, queued or approved, and the provenance (generation day, state version, mandate version, evidence
hash of the inputs) is recorded in the file itself. The file is prepared, never sent: the owner downloads and
submits it. Downloads: GET /borrower-file/{file_id}.html | .docx | .pdf.
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
    lookup,
    pdf_renderer,
    remember,
    render_docx,
    render_html,
    render_pdf,
)

router = APIRouter(dependencies=[Depends(require_owner)])

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
    # Owner estimate: the day the proceeds are spent. For an equipment purpose it is always applied: if omitted
    # it defaults to the day the proceeds land and the file states that assumption.
    spend_day: int | None = None
    ebitda_uplift_fen: int | None = None  # owner estimate: shown, never projected


def _view(bf: BorrowerFile) -> dict[str, Any]:
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
        bf = remember(bf)  # the same request on the same verified state: keep the first snapshot
        return _view(bf)


def _get(rt: Runtime, file_id: str) -> BorrowerFile:
    _require_enabled(rt)
    found = lookup(file_id)
    if found is None:
        raise HTTPException(404, "borrower file not found; POST /borrower-file first")
    return found


def _attachment(file_id: str, ext: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{file_id}.{ext}"'}


@router.get("/borrower-file/{file_id}.html", response_class=HTMLResponse)
def get_borrower_file_html(file_id: str) -> HTMLResponse:
    bf = _get(get_runtime(), file_id)
    return HTMLResponse(render_html(bf))


@router.get("/borrower-file/{file_id}.docx")
def get_borrower_file_docx(file_id: str) -> Response:
    bf = _get(get_runtime(), file_id)
    return Response(render_docx(bf), media_type=DOCX_MEDIA, headers=_attachment(bf.file_id, "docx"))


@router.get("/borrower-file/{file_id}.pdf")
def get_borrower_file_pdf(file_id: str) -> Response:
    bf = _get(get_runtime(), file_id)
    pdf = render_pdf(bf)
    if pdf is None:
        raise HTTPException(501, "PDF skipped: no local PDF renderer is installed; download the HTML and print it")
    return Response(pdf, media_type="application/pdf", headers=_attachment(bf.file_id, "pdf"))


@router.get("/borrower-file/{file_id}")
def get_borrower_file(file_id: str) -> dict[str, Any]:
    return _view(_get(get_runtime(), file_id))
