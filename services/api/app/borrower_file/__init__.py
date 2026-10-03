"""Borrower file (micro-enterprise loan format), built from verified state only (flag `borrower_file`).

Public interface: `build(store, *, facility_id, amount_fen, use_of_proceeds, day)` -> BorrowerFile,
`render_html`, `render_docx`, `render_pdf` (None when no local PDF renderer is installed).
Depends on `app.domain`, `app.financial`, `app.covenants` and the `LedgerStore` port. The file is
generated, never sent: the owner submits it. Generating it is a read-only owner action with provenance in
the file (no operation, no approval). The lender is mocked.
"""

from app.borrower_file.build import BorrowerFileError, build, customer_ref
from app.borrower_file.files import lookup, remember
from app.borrower_file.models import (
    LENDER_NOTE,
    TITLE_EN,
    TITLE_ZH,
    BorrowerFile,
    Evidence,
    Figure,
    Provenance,
    Row,
    Section,
)
from app.borrower_file.render import pdf_renderer, render_docx, render_html, render_pdf

__all__ = [
    "LENDER_NOTE",
    "TITLE_EN",
    "TITLE_ZH",
    "BorrowerFile",
    "BorrowerFileError",
    "Evidence",
    "Figure",
    "Provenance",
    "Row",
    "Section",
    "build",
    "customer_ref",
    "lookup",
    "pdf_renderer",
    "remember",
    "render_docx",
    "render_html",
    "render_pdf",
]
