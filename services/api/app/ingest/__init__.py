"""Document intake for contract ingestion: the text of an uploaded file. Imports nothing internal.

Public API: `extract_text(filename, data) -> str` and the `IngestError` family (each with a stable `code`).
"""

from app.ingest.text import (
    MAX_BYTES,
    MAX_CHARS,
    SCANNED_MESSAGE,
    SUPPORTED,
    DocumentTooLarge,
    EmptyDocument,
    IngestError,
    ScannedPdf,
    UnsupportedFileType,
    extract_text,
    normalise,
    unwrap,
)

__all__ = [
    "MAX_BYTES",
    "MAX_CHARS",
    "SCANNED_MESSAGE",
    "SUPPORTED",
    "DocumentTooLarge",
    "EmptyDocument",
    "IngestError",
    "ScannedPdf",
    "UnsupportedFileType",
    "extract_text",
    "normalise",
    "unwrap",
]
