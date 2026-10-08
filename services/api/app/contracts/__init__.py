"""Documents the agent read (brief 03): a PROPOSED record from an upload, its views, and what a confirmed reading
implies for the books (compared, never written).

Public API: `read_document`, `suggest_facility`, `record_view`, `record_summary`, `term_display`, `buyer_terms`,
`day_of`. Depends on domain, the compiler's public entry points and nothing that writes state.
"""

from app.contracts.derive import BuyerContractTerms, ScheduledInvoice, buyer_terms, date_display, day_of
from app.contracts.records import KIND_TITLES, doc_hash, read_document, suggest_facility
from app.contracts.views import (
    AI_LABEL,
    FIELD_LABELS,
    blanks,
    facility_summary,
    record_summary,
    record_view,
    term_display,
    term_view,
)

__all__ = [
    "AI_LABEL",
    "FIELD_LABELS",
    "KIND_TITLES",
    "BuyerContractTerms",
    "ScheduledInvoice",
    "blanks",
    "buyer_terms",
    "date_display",
    "day_of",
    "doc_hash",
    "facility_summary",
    "read_document",
    "record_summary",
    "record_view",
    "suggest_facility",
    "term_display",
    "term_view",
]
