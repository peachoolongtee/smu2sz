"""The dry pilot runner (services/api/scripts/pilot_dry_run.py): two weeks on the golden books and one on the synthetic
template, with role-played and with written decisions. Nothing here posts an operation."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from app.api.runtime import Runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.operations.log import read_entries
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


# ------------------------------------------------------------------------------------------------ timing fields (ticket #80)


def test_strip_timing_removes_the_wall_clock_keys_at_any_depth(dry: ModuleType) -> None:
    body = {"a": 1, "computed_in_seconds": 2.5, "rows": [{"computed_in_seconds": 1.0, "keep": [{"computed_in_seconds": 0.1, "x": 2}]}]}
    assert dry.strip_timing(body) == {"a": 1, "rows": [{"keep": [{"x": 2}]}]}
    assert "computed_in_seconds" in body  # the argument is not changed


def test_two_reads_of_the_same_books_hash_the_same(
    dry: ModuleType, role_play: tuple[Runtime, Any, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ENV:
        monkeypatch.setenv(key, "1")
    first_rt, _, first_out = role_play
    second_rt = _golden()
    second = dry.run_dry(second_rt, label="dry-a", weeks=1, out=tmp_path / "again", decisions=None, role_play=True,
                         today="2026-10-19", say=lambda _line: None)
    assert second.ok
    listed = (tmp_path / "again" / "week-01" / "sha256.txt").read_text(encoding="utf-8")
    assert listed == (first_out / "week-01" / "sha256.txt").read_text(encoding="utf-8")
    hashes = [(e.answer, e.snapshot_hash) for e in journal(second_rt)]
    assert hashes == [(e.answer, e.snapshot_hash) for e in journal(first_rt) if e.week == 1] and len(hashes) == 3
    for path in [*first_out.rglob("*.json"), *(tmp_path / "again").rglob("*.json")]:
        assert "computed_in_seconds" not in path.read_text(encoding="utf-8")
    # the time each answer took is kept, in the summary only
    assert re.search(r"- curve \(\d+\.\d s\):", (tmp_path / "again" / "summary.md").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ receipts (ticket #81)

PUBLIC = Path(__file__).resolve().parents[4] / "fixtures" / "scenarios"
RECEIPTS_EXAMPLE = TEMPLATES.parent / "receipts.example.yaml"


def _public_books(tmp_path: Path) -> Runtime:
    state = tmp_path / "state.json"
    state.write_text(json.dumps(json.loads((PUBLIC / "public_sme.json").read_text(encoding="utf-8"))["state"]), encoding="utf-8")
    return cast(Runtime, load_script("pilot_runtime").build_runtime(state, PUBLIC / "public_sme.mandate.json"))


def _receipts_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "receipts.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def curve_with_and_without_a_receipt(dry: ModuleType, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Two weeks on the public-record books, once with no receipt and once with Buyer D's invoice paid in week 1. The
    envelopes are not read (they are the slow answers and say nothing about the curve)."""
    base = tmp_path_factory.mktemp("receipts-curve")
    ran: dict[str, Any] = {}
    with pytest.MonkeyPatch.context() as mp:
        for key in ENV:
            mp.setenv(key, "1")
        mp.setattr(dry, "_buyers_with_a_lever", lambda _rt: [])
        for name, receipts in (("none", None), ("paid", {1: [dry.Receipt("RCV-D1", 254_926_735, "SYNTH-RCPT-001")]})):
            (base / name).mkdir()
            rt = _public_books(base / name)
            result = dry.run_dry(rt, label="dry-a", weeks=2, out=base / f"out-{name}", decisions=None, role_play=True,
                                 today="2026-10-19", say=lambda _line: None, receipts=receipts)
            ran[name] = (rt, result, base / f"out-{name}")
    return ran


def _curve(out: Path, week: int) -> str:
    return str(json.loads((out / f"week-{week:02d}" / "price_curve.json").read_text(encoding="utf-8"))["sentence"])


def test_a_landed_receipt_changes_the_next_weeks_curve_sentence(curve_with_and_without_a_receipt: dict[str, Any]) -> None:
    (_, none, none_out), (_, paid, paid_out) = curve_with_and_without_a_receipt["none"], curve_with_and_without_a_receipt["paid"]
    assert none.ok and paid.ok
    assert _curve(none_out, 2) == "Earlier cash saves you nothing today."  # no buyer pays: the stress case of the dry-pilot report
    assert _curve(paid_out, 2).startswith("Cash in the next 10 days saves you ")
    assert _curve(paid_out, 2) != _curve(none_out, 2)


def test_the_receipt_is_in_the_operations_the_journal_and_the_summary(curve_with_and_without_a_receipt: dict[str, Any]) -> None:
    rt, result, out = curve_with_and_without_a_receipt["paid"]
    receipts = [e for e in read_entries(rt.store.operations())[0] if e.kind == "RECEIVE_PAYMENT"]
    assert len(receipts) == 1 and receipts[0].payload["requested_by"] == "SYSTEM" and receipts[0].payload["bank_reference"] == "SYNTH-RCPT-001"
    assert (result.operations_before, result.operations_after, result.receipt_entries, result.receipts_landed) == (0, 0, 1, 1)
    assert rt.store.verify_chain() is True
    state = rt.store.get_state()
    assert next(r for r in state.receivables if r.id == "RCV-D1").status == "SETTLED"
    entry = next(e for e in journal(rt) if e.answer == "receipt")
    assert (entry.week, entry.day, entry.choice, entry.sme) == (1, 7, "not_applicable", "dry-a")
    assert "dry-receipt-w01-1" in entry.flow_said and "¥0.00 still outstanding" in entry.flow_said and "¥2,549,267.35" in entry.flow_said
    summary = (out / "summary.md").read_text(encoding="utf-8")
    week_one, week_two = summary.split("## Week 02")
    assert "- Receipt RCV-D1: ¥2,549,267.35 on day 7, bank reference SYNTH-RCPT-001" in week_one and "Receipt" not in week_two
    assert "receipt entries added 1 for 1 receipts posted (1 landed)" in summary
    assert "SYNTH-RCPT-001" in (out / "week-01" / "sentences.md").read_text(encoding="utf-8")
    assert [e.answer for e in journal(rt)][:1] == ["receipt"]  # posted before the week's reads


def test_receipts_on_a_day_of_the_week_and_the_journal_round_trips_through_a_file(
    dry: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ENV:
        monkeypatch.setenv(key, "1")
    from app.pilot.file_journal import open_journal, read_journal_file

    path = tmp_path / "private" / "j.jsonl"
    rt = Runtime(settings=get_settings(), store=open_journal(path), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    receipts = {1: [dry.Receipt("RCV-A", 10_000_000, "SYNTH-RCPT-1", 3)], 2: [dry.Receipt("RCV-A", 5_000_000, "SYNTH-RCPT-2")]}
    result = dry.run_dry(rt, label="dry-a", weeks=2, out=tmp_path / "out", decisions=None, role_play=False, today="2026-10-19",
                         say=lambda _line: None, receipts=receipts)
    assert result.ok and [w.day for w in result.weeks] == [7, 14]
    assert (result.clock_entries, result.advances, result.receipt_entries) == (3, 3, 2)  # week 1 advances to day 3, then day 7
    posted = [(e.payload["bank_reference"], e.payload["day"]) for e in read_entries(rt.store.operations())[0] if e.kind == "RECEIVE_PAYMENT"]
    assert posted == [("SYNTH-RCPT-1", 3), ("SYNTH-RCPT-2", 14)]
    stored = read_journal_file(path)  # replayed from the file: the entry is valid for the route and survives a restart
    assert [(e.week, e.answer, e.day) for e in stored] == [(1, "receipt", 3), (2, "receipt", 14)]
    assert stored == journal(rt)
    first = stored[0]
    facts = {"bank_reference": "SYNTH-RCPT-1", "amount_fen": 10_000_000, "day": 3, "op_id": "dry-receipt-w01-1",
             "outstanding_fen": 32_000_000, "receivable_id": "RCV-A"}
    assert first.snapshot_hash == hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    assert "¥100,000.00 on day 3" in first.flow_said and "¥320,000.00 still outstanding" in first.flow_said
    assert "dry-receipt-w01-1" in first.owner_did and "SYNTH-RCPT-1" not in first.owner_did
    assert "Receipt RCV-A: ¥50,000.00 on day 14" in (tmp_path / "out" / "summary.md").read_text(encoding="utf-8")


def test_a_refused_receipt_is_an_error_with_its_week_and_is_not_journaled(
    dry: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ENV:
        monkeypatch.setenv(key, "1")
    rt = _golden()
    receipts = {1: [dry.Receipt("RCV-A", 10_000_000, "SYNTH-RCPT-1"), dry.Receipt("RCV-A", 10_000_000, "SYNTH-RCPT-1")]}  # the bank event twice
    result = dry.run_dry(rt, label="dry-a", weeks=1, out=tmp_path / "out", decisions=None, role_play=False,
                         say=lambda _line: None, receipts=receipts)
    assert not result.ok and result.receipts_landed == 1 and result.receipt_entries == result.receipts_posted == 2
    assert "REFUSED" in result.weeks[0].errors[0] and "week 1: receipt RCV-A SYNTH-RCPT-1" in (tmp_path / "out" / "summary.md").read_text(encoding="utf-8")
    assert [e.answer for e in journal(rt)] == ["receipt"]


GOOD = "{receivable_id: RCV-A, amount_fen: 100, bank_reference: R-1}"


@pytest.mark.parametrize("text, words", [
    ("3:\n  - " + GOOD + "\n", "week 3 is outside the run: weeks are whole numbers from 1 to 2"),
    ("0:\n  - " + GOOD + "\n", "week 0 is outside the run"),
    ("first:\n  - " + GOOD + "\n", "week 'first' is outside the run"),
    ("1: " + GOOD + "\n", "the week's receipts must be a list"),
    ("1:\n  - {receivable_id: RCV-Z, amount_fen: 100, bank_reference: R-1}\n", "RCV-Z is not a receivable on the books"),
    ("1:\n  - {receivable_id: RCV-A, amount_fen: 0, bank_reference: R-1}\n", "amount_fen must be a whole number of fen above zero"),
    ("1:\n  - {receivable_id: RCV-A, amount_fen: -5, bank_reference: R-1}\n", "amount_fen must be a whole number of fen above zero"),
    ("1:\n  - {receivable_id: RCV-A, amount_fen: 1.5, bank_reference: R-1}\n", "amount_fen must be a whole number of fen above zero"),
    ("1:\n  - {receivable_id: RCV-A, amount_fen: 100}\n", "bank_reference must be 1 to 64 characters"),
    ("1:\n  - {receivable_id: RCV-A, amount_fen: 100, bank_reference: 'ACCT 6222 0212 3456 7890'}\n", "looks like an account or card number"),
    ("1:\n  - " + GOOD + "\n  - {receivable_id: RCV-A, amount_fen: 200, bank_reference: R-1}\n", "bank_reference 'R-1' is already used (week 1, receipt 1)"),
    ("1:\n  - " + GOOD + "\n2:\n  - {receivable_id: RCV-A, amount_fen: 200, bank_reference: R-1}\n", "bank_reference 'R-1' is already used (week 1, receipt 1)"),
    ("1:\n  - {receivable_id: RCV-A, amount_fen: 100, bank_reference: R-1, day: 8}\n", "day is the day of the week the receipt arrives"),
    ("1:\n  - {receivable_id: RCV-A, amount_fen: 100, bank_reference: R-1, why: x}\n", "unknown key 'why'"),
    (("1:\n  - {receivable_id: RCV-A, amount_fen: 30000000, bank_reference: R-1}\n"
      "2:\n  - {receivable_id: RCV-A, amount_fen: 20000000, bank_reference: R-2}\n"), "add up to ¥500,000.00, more than the ¥420,000.00 owed"),
    ("1:\n  - nonsense\n", "each receipt is a mapping"),
    ("just words", "must be a map of week number"),
    ("a: [", "not valid YAML"),
])
def test_a_bad_receipts_file_is_a_sentence(dry: ModuleType, tmp_path: Path, text: str, words: str) -> None:
    state = _golden().store.get_state()
    with pytest.raises(dry.DryRunError, match=re.escape(words)):
        dry.load_receipts(_receipts_file(tmp_path, text), 2, state)
    with pytest.raises(dry.DryRunError, match="cannot read"):
        dry.load_receipts(tmp_path / "nothing.yaml", 2, state)


def test_a_settled_receivable_is_refused_before_anything_runs(dry: ModuleType, tmp_path: Path) -> None:
    state = _golden().store.get_state()
    state = state.model_copy(update={"receivables": [r.model_copy(update={"status": "SETTLED", "settled_fen": r.face_fen}) for r in state.receivables]})
    with pytest.raises(dry.DryRunError, match="RCV-A is SETTLED; nothing is owed on it"):
        dry.load_receipts(_receipts_file(tmp_path, "1:\n  - " + GOOD + "\n"), 2, state)


def test_a_good_receipts_file_loads_in_week_order_with_the_default_day(dry: ModuleType, tmp_path: Path) -> None:
    loaded = dry.load_receipts(_receipts_file(tmp_path, "2:\n  - {receivable_id: RCV-A, amount_fen: 5, bank_reference: R-2, day: 1}\n1:\n  - " + GOOD + "\n"),
                               2, _golden().store.get_state())
    assert loaded == {2: [dry.Receipt("RCV-A", 5, "R-2", 1)], 1: [dry.Receipt("RCV-A", 100, "R-1", 7)]}
    assert dry.load_receipts(_receipts_file(tmp_path, ""), 2, _golden().store.get_state()) == {}


def test_the_example_receipts_file_loads_on_the_public_record_books(dry: ModuleType, tmp_path: Path) -> None:
    loaded = dry.load_receipts(RECEIPTS_EXAMPLE, 8, _public_books(tmp_path).store.get_state())
    assert sorted(loaded) == [1, 2, 4, 6] and loaded[2][0].day == 3 and loaded[1][0].day == 7
    with pytest.raises(dry.DryRunError, match="week 6 is outside the run"):
        dry.load_receipts(RECEIPTS_EXAMPLE, 5, _public_books(tmp_path).store.get_state())


def test_main_refuses_a_bad_receipts_file_before_anything_runs(
    dry: ModuleType, tmp_path: Path, env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def never(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a run started on a bad receipts file")

    env.setattr(dry, "run_dry", never)
    journal_file = tmp_path / "private" / "j.jsonl"
    base = ["--state", str(TEMPLATES / "state.example.json"), "--mandate", str(TEMPLATES / "mandate.example.json"),
            "--label", "dry-a", "--weeks", "2", "--out", str(tmp_path / "out"), "--role-play", "auto", "--journal-file", str(journal_file)]
    bad = _receipts_file(tmp_path, "1:\n  - {receivable_id: NO-SUCH, amount_fen: 100, bank_reference: R-1}\n")
    assert dry.main([*base, "--receipts", str(bad)]) == 2
    assert "NO-SUCH is not a receivable on the books" in capsys.readouterr().err
    assert not (tmp_path / "out").exists() and journal_file.read_text(encoding="utf-8") == ""


def test_main_lands_the_receipts_of_the_file(
    dry: ModuleType, tmp_path: Path, env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    state = json.loads((TEMPLATES / "state.example.json").read_text(encoding="utf-8"))
    first = state["receivables"][0]
    good = _receipts_file(tmp_path, f"1:\n  - {{receivable_id: {first['id']}, amount_fen: 100, bank_reference: R-1}}\n")
    args = ["--state", str(TEMPLATES / "state.example.json"), "--mandate", str(TEMPLATES / "mandate.example.json"), "--label", "dry-a",
            "--weeks", "1", "--out", str(tmp_path / "out"), "--receipts", str(good)]
    assert dry.main(args) == 0
    shown = capsys.readouterr().out
    assert f"receipt {first['id']}: ¥1.00 on day 7, bank reference R-1" in shown and "receipt entries added 1 for 1 receipts posted (1 landed)" in shown
