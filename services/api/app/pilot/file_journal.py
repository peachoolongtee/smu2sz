"""The pilot journal on a file: JSON lines, one `PilotJournalRecord` per line (wayfinder map #58, docs/pilot/RUNBOOK.md).

`FileBackedMemoryStore` is the in-memory store with one addition: a write through `add_pilot_journal` (what
`POST /pilot/journal` calls) is appended to the file, flushed and synced, before the call returns; and at start-up the file
is replayed into the store, each line validated. The store stays the source of truth while the process runs. The route is
unchanged; the books, the operations log and the hash chain are not touched by a journal write, as without a file.

The file holds what the owner said about an answer, in the owner's words, so it belongs outside the repository
(`check_journal_path`).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, fields
from pathlib import Path

from pydantic import ValidationError

from app.persistence import InMemoryLedgerStore
from app.persistence.records import PilotJournalRecord
from app.pilot.journal import JournalEntryIn

REPO_ROOT = Path(__file__).resolve().parents[4]


class JournalFileError(RuntimeError):
    """The journal file cannot be used; the message is one sentence saying why and, for a malformed file, the line."""


class StoredLine(JournalEntryIn):
    """A journal file line: the eight fields the route validates, and the four the store stamps."""

    seq: int
    state_version: int
    day: int
    recorded_at: str


_FIELDS = tuple(f.name for f in fields(PilotJournalRecord))


def check_journal_path(path: Path, *, repo_root: Path = REPO_ROOT, allow_repo_path: bool = False) -> Path:
    """The path to use, resolved. A path inside the repository is refused unless it is `docs/pilot/<label>/<file>` and
    `allow_repo_path` is set (a journal holds what an owner said and must not be committed by accident)."""
    resolved = path.expanduser().resolve()
    root = repo_root.resolve()
    if resolved.is_dir():
        raise JournalFileError(f"the journal file {path} is a folder: name a file, for example journal.jsonl")
    if resolved != root and root not in resolved.parents:
        return resolved
    relative = resolved.relative_to(root)
    under_label = len(relative.parts) >= 4 and relative.parts[:2] == ("docs", "pilot")
    if not under_label:
        raise JournalFileError(
            f"the journal file {path} is inside the repository: keep it in a private folder outside it "
            "(only docs/pilot/<label>/ is allowed, and only with --allow-repo-path)"
        )
    if not allow_repo_path:
        raise JournalFileError(
            f"the journal file {path} is inside the repository: pass --allow-repo-path to confirm the owner has approved "
            "committing it, or keep it in a private folder outside the repository"
        )
    return resolved


def read_journal_file(path: Path) -> list[PilotJournalRecord]:
    """Every record in the file, oldest first. A missing or empty file has none. Raises `JournalFileError` naming the first
    bad line: not JSON, not an object, a field the route would refuse, an unknown or missing field, or `seq` out of order."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError) as exc:
        raise JournalFileError(f"cannot read the journal file {path}: {exc}") from None
    records: list[PilotJournalRecord] = []
    lines = text.split("\n")  # not splitlines(): that would also split inside a free-text field on U+2028 and the like
    if lines and lines[-1] == "":
        lines.pop()
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            raise JournalFileError(f"the journal file {path} is malformed at line {number}: the line is empty")
        try:
            data = json.loads(line)
        except ValueError:
            raise JournalFileError(f"the journal file {path} is malformed at line {number}: it is not JSON") from None
        if not isinstance(data, dict):
            raise JournalFileError(f"the journal file {path} is malformed at line {number}: it is not a JSON object")
        try:
            parsed = StoredLine.model_validate(data)
        except ValidationError as exc:
            first = exc.errors()[0]
            where = ".".join(str(p) for p in first["loc"]) or "line"
            raise JournalFileError(f"the journal file {path} is malformed at line {number}: {where}: {first['msg']}") from None
        if parsed.seq != len(records) + 1:
            raise JournalFileError(
                f"the journal file {path} is malformed at line {number}: seq is {parsed.seq}, expected {len(records) + 1}"
            )
        records.append(PilotJournalRecord(**{name: getattr(parsed, name) for name in _FIELDS}))
    return records


class FileBackedMemoryStore(InMemoryLedgerStore):
    """`InMemoryLedgerStore` whose pilot journal is persisted to `journal_path` (checked and replayed by the caller via
    `open_journal`). Use `open_journal`, not the constructor, so the file is validated before anything is served."""

    def __init__(self, journal_path: Path) -> None:
        super().__init__()
        self.journal_path = journal_path

    def restore_pilot_journal(self, records: list[PilotJournalRecord]) -> None:
        """Load replayed records as they were written (their own `recorded_at`); only for an empty journal."""
        with self._lock:
            if self._pilot_journal:
                raise JournalFileError("the journal already has entries: it can only be replayed into an empty store")
            self._pilot_journal.extend(records)

    def add_pilot_journal(
        self, *, week: int, sme: str, answer: str, flow_said: str, snapshot_hash: str, owner_did: str, choice: str,
        recorded_on: str, state_version: int, day: int,
    ) -> PilotJournalRecord:
        with self._lock:
            rec = super().add_pilot_journal(
                week=week, sme=sme, answer=answer, flow_said=flow_said, snapshot_hash=snapshot_hash, owner_did=owner_did,
                choice=choice, recorded_on=recorded_on, state_version=state_version, day=day,
            )
            try:
                self._append(rec)
            except OSError as exc:
                self._pilot_journal.pop()  # the entry is not kept in memory if it is not on the file
                raise JournalFileError(f"the journal file {self.journal_path} could not be written: {exc}") from None
            return rec

    def _append(self, rec: PilotJournalRecord) -> None:
        line = json.dumps(asdict(rec), ensure_ascii=False, sort_keys=True)
        with self.journal_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def open_journal(path: Path, *, repo_root: Path = REPO_ROOT, allow_repo_path: bool = False) -> FileBackedMemoryStore:
    """A store holding the file's entries, ready to append to it. Raises `JournalFileError` (a refused path, a malformed
    line, a folder that cannot be made or a file that cannot be written) before anything is served."""
    resolved = check_journal_path(path, repo_root=repo_root, allow_repo_path=allow_repo_path)
    records = read_journal_file(resolved)
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.touch(exist_ok=True)  # fail now, not at the first entry, if the file cannot be written
    except OSError as exc:
        raise JournalFileError(f"the journal file {path} cannot be created: {exc}") from None
    store = FileBackedMemoryStore(resolved)
    store.restore_pilot_journal(records)
    return store
