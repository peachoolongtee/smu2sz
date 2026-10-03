"""Borrower files built in this process, by id, so a download link made in chat or on the API resolves.

A file is a read-only snapshot with its own provenance (generation day, state and mandate versions, evidence
hash of its inputs). Registering one writes nothing to the ledger and asks nobody for approval. The same request
on the same verified state gives the same id, and the first snapshot is kept.
"""

from __future__ import annotations

from app.borrower_file.models import BorrowerFile

_FILES: dict[str, BorrowerFile] = {}


def remember(bf: BorrowerFile) -> BorrowerFile:
    """Keep `bf` under its id unless that id is already held; return the held snapshot."""
    return _FILES.setdefault(bf.file_id, bf)


def lookup(file_id: str) -> BorrowerFile | None:
    return _FILES.get(file_id)
