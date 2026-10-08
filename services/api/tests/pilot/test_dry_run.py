"""The dry pilot runner (services/api/scripts/pilot_dry_run.py): two weeks on the golden books and one on the synthetic
template, with role-played and with written decisions. Nothing here posts an operation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from app.api.runtime import Runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.persistence.records import PilotJournalRecord
from app.pilot.file_journal import FileBackedMemoryStore

from .conftest import load_script

TEMPLATES = Path(__file__).resolve().parents[4] / "docs" / "pilot" / "templates"
ENV = ("FEATURE_ENVELOPE", "FEATURE_PRICE_CURVE", "FEATURE_COLLECTIONS_WORTH", "FEATURE_PILOT_JOURNAL")
SECOND = {"week": 2, "decisions": [{"answer": "envelope", "buyer": "BUYER-1", "owner_did": "Said yes to 45 days.", "choice": "partly"}]}


@pytest.fixture(scope="module")
def dry() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        for key in ENV:
            mp.setenv(key, "1")
        yield load_script("pilot_dry_run")


def journal(rt: Runtime) -> list[PilotJournalRecord]:
    return cast(FileBackedMemoryStore | InMemoryLedgerStore, rt.store).pilot_journal()


def _golden() -> Runtime:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    return rt


@pytest.fixture(scope="module")
def role_play(dry: ModuleType, tmp_path_factory: pytest.TempPathFactory) -> tuple[Runtime, Any, Path]:
    out = tmp_path_factory.mktemp("dry") / "dry-a"
    rt = _golden()
    with pytest.MonkeyPatch.context() as mp:
        for key in ENV:
            mp.setenv(key, "1")
        result = dry.run_dry(rt, label="dry-a", weeks=2, out=out, decisions=None, role_play=True, today="2026-10-19",
                             say=lambda _line: None)
    return rt, result, out


def test_two_weeks_on_the_golden_books_write_the_files(role_play: tuple[Runtime, Any, Path]) -> None:
    _, result, out = role_play
    assert result.ok and [w.day for w in result.weeks] == [7, 14]
    for week in ("week-01", "week-02"):
        names = sorted(p.name for p in (out / week).iterdir())
        assert names == ["envelope-BUYER-1.json", "price_curve.json", "sentences.md", "sha256.txt", "worth.json"]
    curve = json.loads((out / "week-01" / "price_curve.json").read_text(encoding="utf-8"))
    sentences = (out / "week-01" / "sentences.md").read_text(encoding="utf-8")
    assert curve["sentence"] in sentences and "REHEARSAL" in sentences
    worth = json.loads((out / "week-01" / "worth.json").read_text(encoding="utf-8"))
    assert worth["top_action"] in sentences
    for row in worth["rows"]:
        assert row["worth_text"] in sentences and row["action_sentence"] in sentences
    envelope = json.loads((out / "week-01" / "envelope-BUYER-1.json").read_text(encoding="utf-8"))
    assert (envelope.get("refused") or envelope["primary"]) in sentences


def test_the_hashes_listed_are_the_files_hashes(role_play: tuple[Runtime, Any, Path]) -> None:
    _, _, out = role_play
    for week in ("week-01", "week-02"):
        listed = dict(line.split("  ", 1)[::-1] for line in (out / week / "sha256.txt").read_text(encoding="utf-8").splitlines())
        assert set(listed) == {p.name for p in (out / week).glob("*.json")}
        for name, digest in listed.items():
            assert hashlib.sha256((out / week / name).read_bytes()).hexdigest() == digest


def test_role_play_records_followed_for_every_answer(role_play: tuple[Runtime, Any, Path]) -> None:
    rt, _, out = role_play
    entries = journal(rt)
    assert [(e.week, e.answer) for e in entries] == [(w, a) for w in (1, 2) for a in ("curve", "worth", "envelope")]
    assert {e.sme for e in entries} == {"dry-a"} and {e.choice for e in entries} == {"followed"}
    assert {e.owner_did for e in entries} == {"role-play: followed FLOW's answer"}
    assert {e.recorded_on for e in entries} == {"2026-10-19"}
    by_file = {1: "price_curve.json", 2: "worth.json"}
    first = entries[0]
    assert first.snapshot_hash == hashlib.sha256((out / "week-01" / by_file[1]).read_bytes()).hexdigest()
    curve = json.loads((out / "week-01" / "price_curve.json").read_text(encoding="utf-8"))
    assert first.flow_said == curve["sentence"]
    assert [e.day for e in entries] == [7] * 3 + [14] * 3


def test_nothing_acted_and_the_chain_verifies(role_play: tuple[Runtime, Any, Path]) -> None:
    rt, result, out = role_play
    assert (result.operations_before, result.operations_after) == (0, 0)
    assert result.clock_entries == result.advances == 2
    assert {o.kind for o in rt.store.operations()} == {"ADVANCE_CLOCK"}
    assert rt.store.verify_chain() is True and rt.store.commitments() == []
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert "REHEARSAL" in summary and "## Week 01" in summary and "## Week 02" in summary and "None." in summary
    assert "followed" in summary


def test_written_decisions_record_the_given_choices(dry: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV:
        monkeypatch.setenv(key, "1")
    decisions = tmp_path / "decisions.yaml"
    decisions.write_text(
        "- week: 1\n  decisions:\n"
        "    - {answer: curve, owner_did: 'Waited, no early cash needed.', choice: ignored}\n"
        "    - {answer: worth, owner_did: 'Chased Buyer B first.', choice: followed}\n"
        "- week: 2\n  decisions:\n"
        "    - {answer: envelope, buyer: BUYER-1, owner_did: 'Said yes to 45 days.', choice: partly}\n",
        encoding="utf-8")
    rt = _golden()
    loaded = dry.load_decisions(decisions, 2)
    result = dry.run_dry(rt, label="dry-a", weeks=2, out=tmp_path / "out", decisions=loaded, role_play=False,
                         today="2026-10-19", say=lambda _line: None)
    assert result.ok
    entries = journal(rt)
    assert [(e.week, e.answer, e.choice, e.owner_did) for e in entries] == [
        (1, "curve", "ignored", "Waited, no early cash needed."), (1, "worth", "followed", "Chased Buyer B first."),
        (2, "envelope", "partly", "Said yes to 45 days.")]
    assert result.weeks[0].open_decisions == ["envelope BUYER-1"]
    assert result.weeks[1].open_decisions == ["curve", "worth"]


def test_a_decision_without_a_buyer_among_two_envelopes_is_an_error_not_a_guess(
    dry: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ENV:
        monkeypatch.setenv(key, "1")
    rt = load_script("pilot_runtime").build_runtime(TEMPLATES / "state.example.json", TEMPLATES / "mandate.example.json")  # two buyers
    loaded = {1: [dry.Decision("envelope", "Said yes.", "followed"), dry.Decision("envelope", "Said no.", "ignored", "BUYER-9")]}
    result = dry.run_dry(rt, label="dry-a", weeks=1, out=tmp_path / "out", decisions=loaded, role_play=False,
                         say=lambda _line: None)
    assert not result.ok and journal(rt) == []
    assert "name the buyer" in result.weeks[0].errors[0] and "no such answer" in result.weeks[0].errors[1]
    assert "week 1: decision for envelope" in (tmp_path / "out" / "summary.md").read_text(encoding="utf-8")


def test_a_route_that_refuses_the_entry_is_reported_with_its_week(
    dry: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ENV:
        monkeypatch.setenv(key, "1")
    rt = _golden()
    loaded = {1: [dry.Decision("curve", "Paid card 4111 1111 1111 1111.", "followed")]}  # the route's account-number guard
    result = dry.run_dry(rt, label="dry-a", weeks=1, out=tmp_path / "out", decisions=loaded, role_play=False,
                         say=lambda _line: None)
    assert not result.ok and "journal curve: HTTP 422" in result.weeks[0].errors[0]
    assert journal(rt) == []


def test_a_clock_that_fails_stops_the_run_and_is_reported(
    dry: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ENV:
        monkeypatch.setenv(key, "1")
    rt = _golden()
    original = rt.advance_to
    calls: list[int] = []

    def advance(day: int) -> object:
        calls.append(day)
        if len(calls) == 2:
            raise RuntimeError("the books would not close")
        return original(day)

    monkeypatch.setattr(rt, "advance_to", advance)
    result = dry.run_dry(rt, label="dry-a", weeks=3, out=tmp_path / "out", decisions=None, role_play=False,
                         say=lambda _line: None)
    assert [w.week for w in result.weeks] == [1, 2] and not result.ok
    assert result.weeks[1].errors == ["clock advance: RuntimeError: the books would not close"]
    assert "week 2: clock advance: RuntimeError" in (tmp_path / "out" / "summary.md").read_text(encoding="utf-8")


def test_an_answer_over_ten_seconds_is_reported(dry: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV:
        monkeypatch.setenv(key, "1")
    monkeypatch.setattr(dry, "SLOW_SECONDS", -1.0)
    rt = _golden()
    result = dry.run_dry(rt, label="dry-a", weeks=1, out=tmp_path / "out", decisions=None, role_play=False, say=lambda _line: None)
    assert any("took" in n and "over" in n for n in result.weeks[0].notes) and result.ok  # a finding, not a failure
    assert "Slow:" in (tmp_path / "out" / "summary.md").read_text(encoding="utf-8")


def test_both_decision_modes_are_refused(dry: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(dry.DryRunError, match="not both"):
        dry.run_dry(_golden(), label="dry-a", weeks=1, out=tmp_path, decisions={}, role_play=True, say=lambda _line: None)


@pytest.mark.parametrize("text, words", [
    ("- week: 9\n  decisions: []\n", "week must be a whole number from 1 to 2"),
    ("- week: 1\n  decisions:\n    - {answer: pricing, owner_did: x, choice: followed}\n", "answer must be one of"),
    ("- week: 1\n  decisions:\n    - {answer: curve, owner_did: x, choice: maybe}\n", "choice must be one of"),
    ("- week: 1\n  decisions:\n    - {answer: curve, owner_did: '', choice: followed}\n", "owner_did must say"),
    ("- week: 1\n  decisions:\n    - {answer: curve, owner_did: x, choice: followed, buyer: BUYER-1}\n", "buyer is only for an envelope"),
    ("- week: 1\n  decisions:\n    - {answer: curve, owner_did: x, choice: followed, why: y}\n", "unknown key 'why'"),
    ("- {decisions: []}\n", "each entry is"),
    ("just words", "must be a list"),
    ("a: [", "not valid YAML"),
])
def test_a_bad_decisions_file_is_a_sentence(dry: ModuleType, tmp_path: Path, text: str, words: str) -> None:
    path = tmp_path / "d.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(dry.DryRunError, match=words):
        dry.load_decisions(path, 2)
    with pytest.raises(dry.DryRunError, match="cannot read"):
        dry.load_decisions(tmp_path / "nothing.yaml", 2)


def test_the_example_decisions_file_loads(dry: ModuleType) -> None:
    example = TEMPLATES.parent / "decisions.example.yaml"
    loaded = dry.load_decisions(example, 8)
    assert loaded and all(d.choice in {"followed", "partly", "ignored", "not_applicable"} for ds in loaded.values() for d in ds)


# ------------------------------------------------------------------------------------------------ main()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """`main()` sets the process environment; record the current values so the test run is left as it was."""
    for key in (*ENV, "DEMO_MODE", "OWNER_TOKEN", "AGENT_KEY"):
        monkeypatch.setenv(key, "x")
        monkeypatch.delenv(key)
    return monkeypatch


def test_main_runs_the_template_books_and_writes_the_journal_file(
    dry: ModuleType, tmp_path: Path, env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    journal = tmp_path / "private" / "j.jsonl"
    args = ["--state", str(TEMPLATES / "state.example.json"), "--mandate", str(TEMPLATES / "mandate.example.json"),
            "--label", "dry-a", "--weeks", "1", "--out", str(tmp_path / "out"), "--role-play", "auto",
            "--journal-file", str(journal)]
    assert dry.main(args) == 0
    shown = capsys.readouterr().out
    assert "== dry-a week 01, day 7" in shown and "open decisions: none" in shown and "hash chain verifies" in shown
    assert len(journal.read_text(encoding="utf-8").splitlines()) == 4  # curve, worth, two envelopes
    assert (tmp_path / "out" / "week-01" / "envelope-BUYER-2.json").exists()
    assert dry.main(args) == 2  # the journal file now holds entries: a dry run starts at week 1
    assert "already holds entries" in capsys.readouterr().err


@pytest.mark.parametrize("extra, words", [
    (["--weeks", "0"], "--weeks is 1 to 60"),
    (["--label", "Acme Pte. Ltd."], "--label is 1 to 64"),
    (["--decisions", "d.yaml", "--role-play", "auto"], "not both"),
    (["--journal-file", "REPO/docs/pilot/dry-a/j.jsonl"], "allow-repo-path"),
])
def test_main_refuses_bad_arguments_with_a_sentence(
    dry: ModuleType, tmp_path: Path, env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], extra: list[str], words: str
) -> None:
    repo = TEMPLATES.parents[2]
    base = ["--state", str(TEMPLATES / "state.example.json"), "--mandate", str(TEMPLATES / "mandate.example.json"),
            "--label", "dry-a", "--out", str(tmp_path / "out")]
    args = [a.replace("REPO", str(repo)) for a in extra]
    assert dry.main([*base, *args]) == 2  # a repeated option: the last one wins
    assert words in capsys.readouterr().err
