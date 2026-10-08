"""The pilot journal on a file (app/pilot/file_journal.py, pilot_runtime.py --journal-file): append, replay, a malformed
file, the path rules, and that a file write changes nothing of the engine."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.pilot.file_journal import (
    REPO_ROOT,
    FileBackedMemoryStore,
    JournalFileError,
    check_journal_path,
    open_journal,
    read_journal_file,
)

from .conftest import OWNER, entry, load_script

pytestmark = pytest.mark.usefixtures("flag_on")


def _client(store: FileBackedMemoryStore) -> tuple[Runtime, TestClient]:
    from app.main import app

    rt = Runtime(settings=get_settings(), store=store, owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    return rt, TestClient(app, headers=OWNER)


@pytest.fixture(autouse=True)
def _no_runtime() -> Iterator[None]:
    yield
    set_runtime(None)


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").split("\n")[:-1]


def test_append_then_replay_gives_the_same_entries_in_order(tmp_path: Path) -> None:
    path = tmp_path / "private" / "j.jsonl"
    store = open_journal(path)
    assert path.exists() and store.pilot_journal() == []
    _, client = _client(store)
    for week, did in ((1, "Chased Buyer A first."), (2, "Ünïcode ✓ and a line\nbreak  inside."), (3, "Said no.")):
        assert client.post("/pilot/journal", json=entry(week=week, owner_did=did)).status_code == 201
    before = store.pilot_journal()
    assert [r.seq for r in before] == [1, 2, 3]
    assert [json.loads(line)["seq"] for line in _lines(path)] == [1, 2, 3]
    assert [json.loads(line) for line in _lines(path)] == [asdict(r) for r in before]

    replayed = open_journal(path)
    assert replayed.pilot_journal() == before  # same records, same order, same recorded_at
    _, again = _client(replayed)
    assert again.get("/pilot/journal").json()["count"] == 3
    assert again.post("/pilot/journal", json=entry(week=4)).json()["entry"]["seq"] == 4  # the sequence goes on
    assert len(_lines(path)) == 4


def test_the_route_answers_after_the_file_has_the_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "j.jsonl"
    store = open_journal(path)
    _, client = _client(store)
    seen: list[int] = []
    original = store.add_pilot_journal

    def spy(**kwargs: object) -> object:
        rec = original(**kwargs)  # type: ignore[arg-type]
        seen.append(len(_lines(path)))
        return rec

    monkeypatch.setattr(store, "add_pilot_journal", spy)
    assert client.post("/pilot/journal", json=entry()).status_code == 201
    assert seen == [1]


def test_a_failed_file_write_keeps_nothing_in_memory(tmp_path: Path) -> None:
    path = tmp_path / "j.jsonl"
    store = open_journal(path)
    path.unlink()
    path.mkdir()  # the file can no longer be opened for appending
    with pytest.raises(JournalFileError, match="could not be written"):
        store.add_pilot_journal(
            week=1, sme="sme-a", answer="curve", flow_said="x", snapshot_hash="a" * 64, owner_did="y", choice="followed",
            recorded_on="2026-10-19", state_version=1, day=0,
        )
    assert store.pilot_journal() == []


def test_file_writes_change_neither_the_state_nor_the_operations_nor_the_chain(tmp_path: Path) -> None:
    store = open_journal(tmp_path / "j.jsonl")
    rt, client = _client(store)
    state, ops, head = store.get_state(), store.operations(), [o.entry_hash for o in store.operations()]
    for week in (1, 2, 3):
        assert client.post("/pilot/journal", json=entry(week=week)).status_code == 201
    assert store.get_state() == state and store.get_state().state_version == state.state_version
    assert store.operations() == ops and [o.entry_hash for o in store.operations()] == head
    assert store.verify_chain() is True and rt.day == 0


def _write(path: Path, *lines: str) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _good(seq: int = 1, **changes: object) -> str:
    rec: dict[str, object] = {
        **entry(), "seq": seq, "state_version": 1, "day": 0, "recorded_at": "2026-10-19T08:00:00+00:00",
    }
    rec.update(changes)
    return json.dumps(rec)


@pytest.mark.parametrize("bad, words", [
    ("{not json", "it is not JSON"),
    ("[1, 2]", "not a JSON object"),
    ("", "the line is empty"),
    (_good(2, choice="maybe"), "choice"),
    (_good(2, snapshot_hash="xyz"), "snapshot_hash"),
    (_good(2, owner_did="card 4111 1111 1111 1111"), "account or card number"),
    (_good(2, extra="field"), "extra"),
    (json.dumps({k: v for k, v in json.loads(_good(2)).items() if k != "day"}), "day"),
    (_good(5), "seq is 5, expected 2"),
])
def test_a_malformed_line_is_refused_with_its_number(tmp_path: Path, bad: str, words: str) -> None:
    path = _write(tmp_path / "j.jsonl", _good(1), bad, _good(3))
    with pytest.raises(JournalFileError, match=rf"malformed at line 2: .*{words}"):
        open_journal(path)
    with pytest.raises(JournalFileError, match="line 2"):
        read_journal_file(path)


def test_a_missing_or_empty_file_is_an_empty_journal(tmp_path: Path) -> None:
    assert read_journal_file(tmp_path / "nothing.jsonl") == []
    (tmp_path / "zero.jsonl").write_text("", encoding="utf-8")
    assert open_journal(tmp_path / "zero.jsonl").pilot_journal() == []


def test_replay_needs_an_empty_store(tmp_path: Path) -> None:
    store = open_journal(tmp_path / "j.jsonl")
    _, client = _client(store)
    client.post("/pilot/journal", json=entry())
    with pytest.raises(JournalFileError, match="empty store"):
        store.restore_pilot_journal(read_journal_file(tmp_path / "j.jsonl"))


# ----------------------------------------------------------------------------------------------- the path rules


def test_a_path_outside_the_repository_is_allowed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "private" / "j.jsonl"
    assert check_journal_path(outside, repo_root=repo) == outside.resolve()


@pytest.mark.parametrize("inside", ["j.jsonl", "docs/j.jsonl", "docs/pilot/j.jsonl", "services/api/j.jsonl",
                                    "docs/other/dry-a/j.jsonl"])
def test_a_path_in_the_repository_outside_docs_pilot_label_is_refused_even_with_the_flag(
    tmp_path: Path, inside: str
) -> None:
    repo = tmp_path / "repo"
    (repo / "docs" / "pilot" / "sme-a").mkdir(parents=True)
    with pytest.raises(JournalFileError, match="inside the repository"):
        check_journal_path(repo / inside, repo_root=repo, allow_repo_path=True)


def test_under_docs_pilot_label_needs_allow_repo_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "docs" / "pilot" / "dry-a").mkdir(parents=True)
    path = repo / "docs" / "pilot" / "dry-a" / "journal.jsonl"
    with pytest.raises(JournalFileError, match="--allow-repo-path"):
        check_journal_path(path, repo_root=repo)
    assert check_journal_path(path, repo_root=repo, allow_repo_path=True) == path.resolve()
    assert not path.exists()  # checking creates nothing
    assert open_journal(path, repo_root=repo, allow_repo_path=True).pilot_journal() == [] and path.exists()


def test_a_dotdot_path_cannot_slip_into_the_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "docs" / "pilot").mkdir(parents=True)
    sneaky = tmp_path / "elsewhere" / ".." / "repo" / "j.jsonl"
    with pytest.raises(JournalFileError, match="inside the repository"):
        check_journal_path(sneaky, repo_root=repo, allow_repo_path=True)


def test_a_folder_is_not_a_journal_file(tmp_path: Path) -> None:
    with pytest.raises(JournalFileError, match="is a folder"):
        check_journal_path(tmp_path, repo_root=tmp_path / "repo")


def test_the_real_repository_root_is_this_checkout() -> None:
    assert (REPO_ROOT / "services" / "api" / "app" / "pilot" / "file_journal.py").exists()
    with pytest.raises(JournalFileError, match="inside the repository"):
        check_journal_path(REPO_ROOT / "services" / "journal.jsonl", allow_repo_path=True)


# ------------------------------------------------------------------------- pilot_runtime.py --journal-file

TEMPLATES = REPO_ROOT / "docs" / "pilot" / "templates"


@pytest.fixture(scope="module")
def pilot() -> ModuleType:
    return load_script("pilot_runtime")


def test_the_pilot_runtime_replays_and_appends(pilot: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "private" / "j.jsonl"
    build: Callable[..., Runtime] = pilot.build_runtime
    rt = build(TEMPLATES / "state.example.json", TEMPLATES / "mandate.example.json", None, path)
    assert rt.store.get_state().org_id == "SME-EXAMPLE"
    set_runtime(rt)
    from app.main import app

    client = TestClient(app, headers=OWNER)
    assert client.post("/pilot/journal", json=entry()).status_code == 201
    assert len(_lines(path)) == 1
    again = build(TEMPLATES / "state.example.json", TEMPLATES / "mandate.example.json", None, path)
    assert [r.week for r in cast(FileBackedMemoryStore, again.store).pilot_journal()] == [3]


def test_the_pilot_runtime_refuses_a_malformed_file_and_a_repository_path(pilot: ModuleType, tmp_path: Path) -> None:
    build: Callable[..., Runtime] = pilot.build_runtime
    bad = _write(tmp_path / "bad.jsonl", _good(1), "{oops")
    with pytest.raises(pilot.PilotStartError, match="line 2"):
        build(TEMPLATES / "state.example.json", TEMPLATES / "mandate.example.json", None, bad)
    inside = REPO_ROOT / "docs" / "pilot" / "dry-a" / "journal.jsonl"
    with pytest.raises(pilot.PilotStartError, match="allow-repo-path"):
        build(TEMPLATES / "state.example.json", TEMPLATES / "mandate.example.json", None, inside)
    assert not inside.exists()
