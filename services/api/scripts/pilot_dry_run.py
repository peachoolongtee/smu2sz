#!/usr/bin/env python3
"""The dry pilot: eight simulated weeks on one set of books, in process (wayfinder map #58, ticket #62).

A REHEARSAL of the weekly procedure in docs/pilot/RUNBOOK.md, never pilot evidence. For week N = 1..weeks it advances the
clock by seven days (`Runtime.advance_to`, what `POST /clock/advance` calls), reads the three answers through the real
routes (a TestClient with the owner token; no HTTP server), writes them to `<out>/week-NN/` with their displayed sentences
and the sha256 of each file, prints the sentences and the open decisions, and records the week's decisions through
`POST /pilot/journal` (so the route's own validation applies). It posts no operation of its own: the operations log is counted
before week 1 and after the last week, and the only entries it may have gained are the clock's own (one ADVANCE_CLOCK per
advance) and, with --receipts, one RECEIVE_PAYMENT per receipt the file lists; any other entry is reported as an error.

The exported files hold the routes' answers without their timing fields (`computed_in_seconds`): the hash of a file then
depends on the books alone, so two runs on the same books list the same sha256. The seconds each answer took are in
`summary.md` and the console only.

  --state PATH --mandate PATH [--owner-key-file PATH]   the books, as for scripts/pilot_runtime.py
  --label LABEL        the SME label written on every journal entry and in the summary (`dry-a`)
  --weeks N            1 to 60 (default 8)
  --out DIR            where week-NN/ and summary.md go (docs/pilot/dry-a)
  --decisions FILE     the owner's decisions per week, YAML (docs/pilot/decisions.example.yaml)
  --receipts FILE      the bank receipts that land before each week's reads, YAML (docs/pilot/receipts.example.yaml): posted as
                       the bank feed posts them (RECEIVE_PAYMENT, requested by SYSTEM, with the bank reference) and recorded
                       in the journal as a `receipt` entry. Without it no buyer ever pays: the clock never assumes a receipt.
  --role-play auto     instead: record `followed` for every answer, owner_did "role-play: followed FLOW's answer"
  --journal-file PATH  also keep the journal on a JSON-lines file (see pilot_runtime.py); it must not hold entries yet
  --allow-repo-path    as for pilot_runtime.py
  --zone               also read each buyer's zone table (`?zone=1`, a few seconds more each) after its envelope and keep it in
                       `envelope-<buyer>-zone.json`; without it the envelope is read as the web reads it, without the table

With neither --decisions nor --role-play the weeks are exported and the open decisions printed, and nothing is recorded.

Usage (from the repository root):

    TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 \
      uv run --project services/api python services/api/scripts/pilot_dry_run.py \
        --state <state.json> --mandate <mandate.json> --label dry-a --weeks 8 --out docs/pilot/dry-a \
        --role-play auto

The strategy flags, the journal flag, DEMO_MODE=0 and a random owner token are set in `main()` before the app is imported.
Exit 0 when all weeks ran without an error, 1 when any week reported one or a non-clock operation appeared, 2 on bad arguments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_args

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
API_DIR = SCRIPTS_DIR.parent
for _dir in (API_DIR, SCRIPTS_DIR):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

from app.domain.models import (  # pure models; read no settings
    Actor,
    FinancialState,
    OperationStatus,
    ReceivePayment,
)
from app.domain.money import fmt_yuan
from app.pilot.journal import Answer, Choice, looks_like_an_account_number

if TYPE_CHECKING:
    from app.api.runtime import Runtime

ANSWERS: tuple[str, ...] = get_args(Answer)
CHOICES: tuple[str, ...] = get_args(Choice)
ROLE_PLAY_DID = "role-play: followed FLOW's answer"
BANNER = "REHEARSAL: a dry pilot on synthetic or public-record books. Not pilot evidence; no gate is read from it."
SLOW_SECONDS = 10.0
CURVE_FILE = "price_curve.json"
WORTH_FILE = "worth.json"
#: Keys that hold how long the server took, a wall-clock figure: left out of every exported file so a file's hash depends on
#: the books alone. Every route response carries them; the routes themselves are unchanged.
TIMING_KEYS = frozenset({"computed_in_seconds"})
DAYS_IN_WEEK = 7


class DryRunError(RuntimeError):
    """Bad arguments or a bad decisions or receipts file; the message is one sentence saying what to fix."""


# ----------------------------------------------------------------------------------------------- decisions


@dataclass(frozen=True)
class Decision:
    answer: str
    owner_did: str
    choice: str
    buyer: str | None = None  # envelope only: which buyer's answer; optional when exactly one envelope is exported


def _as_decision(raw: object, where: str) -> Decision:
    if not isinstance(raw, dict):
        raise DryRunError(f"{where}: each decision is a mapping with answer, owner_did and choice")
    unknown = sorted(set(raw) - {"answer", "owner_did", "choice", "buyer"})
    if unknown:
        raise DryRunError(f"{where}: unknown key {unknown[0]!r} (a decision has answer, owner_did, choice and, for an envelope, buyer)")
    answer, did, choice, buyer = raw.get("answer"), raw.get("owner_did"), raw.get("choice"), raw.get("buyer")
    if answer not in ANSWERS:
        raise DryRunError(f"{where}: answer must be one of {', '.join(ANSWERS)}")
    if not isinstance(did, str) or not did.strip():
        raise DryRunError(f"{where}: owner_did must say, in words, what the owner did")
    if choice not in CHOICES:
        raise DryRunError(f"{where}: choice must be one of {', '.join(CHOICES)}")
    if buyer is not None and (answer != "envelope" or not isinstance(buyer, str) or not buyer):
        raise DryRunError(f"{where}: buyer is only for an envelope answer, and is a buyer id")
    return Decision(str(answer), did, str(choice), buyer)


def load_decisions(path: Path, weeks: int) -> dict[int, list[Decision]]:
    """The owner's decisions by week. The file is a list of `{week: N, decisions: [...]}` (or the same under a `weeks:` key).
    Raises `DryRunError` naming what is wrong; nothing is run on a bad file."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DryRunError(f"cannot read the decisions file {path}: {exc.strerror}") from None
    except yaml.YAMLError:
        raise DryRunError(f"the decisions file {path} is not valid YAML") from None
    if isinstance(data, dict) and set(data) == {"weeks"}:
        data = data["weeks"]
    if data is None:
        data = []
    if not isinstance(data, list):
        raise DryRunError(f"the decisions file {path} must be a list of weeks, each with `week` and `decisions`")
    out: dict[int, list[Decision]] = {}
    for index, item in enumerate(data, start=1):
        where = f"{path}, entry {index}"
        if not isinstance(item, dict) or set(item) - {"week", "decisions"} or "week" not in item:
            raise DryRunError(f"{where}: each entry is `week: N` and `decisions: [...]`")
        week = item["week"]
        if not isinstance(week, int) or isinstance(week, bool) or not 1 <= week <= weeks:
            raise DryRunError(f"{where}: week must be a whole number from 1 to {weeks}")
        decisions = item.get("decisions") or []
        if not isinstance(decisions, list):
            raise DryRunError(f"{where}: decisions must be a list")
        out.setdefault(week, []).extend(_as_decision(d, f"{where}, week {week}") for d in decisions)
    return out


# ----------------------------------------------------------------------------------------------- receipts


@dataclass(frozen=True)
class Receipt:
    """One bank receipt the file lists: the books' receivable, the amount in fen, the bank's reference for the credit and
    the day of the week it arrives (1 to 7; the end of the week, day 7, when the file does not say)."""

    receivable_id: str
    amount_fen: int
    bank_reference: str
    day: int = DAYS_IN_WEEK


def _as_receipt(raw: object, where: str) -> Receipt:
    if not isinstance(raw, dict):
        raise DryRunError(f"{where}: each receipt is a mapping with receivable_id, amount_fen and bank_reference")
    unknown = sorted(set(raw) - {"receivable_id", "amount_fen", "bank_reference", "day"})
    if unknown:
        raise DryRunError(f"{where}: unknown key {unknown[0]!r} (a receipt has receivable_id, amount_fen, bank_reference and, optionally, day)")
    rid, amount, ref, day = raw.get("receivable_id"), raw.get("amount_fen"), raw.get("bank_reference"), raw.get("day", DAYS_IN_WEEK)
    if not isinstance(rid, str) or not rid:
        raise DryRunError(f"{where}: receivable_id must name a receivable on the books")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise DryRunError(f"{where}: amount_fen must be a whole number of fen above zero")
    if not isinstance(ref, str) or not 1 <= len(ref) <= 64:
        raise DryRunError(f"{where}: bank_reference must be 1 to 64 characters, the bank's own reference for the credit")
    if looks_like_an_account_number(ref):
        raise DryRunError(f"{where}: bank_reference looks like an account or card number: use a synthetic reference")
    if not isinstance(day, int) or isinstance(day, bool) or not 1 <= day <= DAYS_IN_WEEK:
        raise DryRunError(f"{where}: day is the day of the week the receipt arrives, a whole number from 1 to {DAYS_IN_WEEK}")
    return Receipt(rid, amount, ref, day)


def load_receipts(path: Path, weeks: int, state: FinancialState) -> dict[int, list[Receipt]]:
    """The bank receipts by week. The file is a map of week number to a list of `{receivable_id, amount_fen, bank_reference}`
    (and an optional `day`, 1 to 7, within the week). Checked against the run and the starting books before anything runs:
    every week inside 1..`weeks`, every receivable on the books and still open, every amount above zero, no bank reference
    used twice, and no receivable paid more than it was owed on day 0. Raises `DryRunError` naming what is wrong."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DryRunError(f"cannot read the receipts file {path}: {exc.strerror}") from None
    except yaml.YAMLError:
        raise DryRunError(f"the receipts file {path} is not valid YAML") from None
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise DryRunError(f"the receipts file {path} must be a map of week number to a list of receipts")
    owed = {r.id: r for r in state.receivables}
    paid: dict[str, int] = {}
    references: dict[str, str] = {}
    out: dict[int, list[Receipt]] = {}
    for week, items in data.items():
        where = f"{path}, week {week}"
        if not isinstance(week, int) or isinstance(week, bool) or not 1 <= week <= weeks:
            raise DryRunError(f"{path}: week {week!r} is outside the run: weeks are whole numbers from 1 to {weeks}")
        if not isinstance(items, list):
            raise DryRunError(f"{where}: the week's receipts must be a list")
        for index, item in enumerate(items, start=1):
            at = f"{where}, receipt {index}"
            receipt = _as_receipt(item, at)
            receivable = owed.get(receipt.receivable_id)
            if receivable is None:
                raise DryRunError(f"{at}: {receipt.receivable_id} is not a receivable on the books")
            if receivable.status not in ("OPEN", "FINANCED") or receivable.outstanding_fen <= 0:
                raise DryRunError(f"{at}: {receipt.receivable_id} is {receivable.status}; nothing is owed on it")
            if receipt.bank_reference in references:
                raise DryRunError(f"{at}: bank_reference {receipt.bank_reference!r} is already used ({references[receipt.bank_reference]})")
            references[receipt.bank_reference] = f"week {week}, receipt {index}"
            paid[receipt.receivable_id] = paid.get(receipt.receivable_id, 0) + receipt.amount_fen
            if paid[receipt.receivable_id] > receivable.outstanding_fen:
                raise DryRunError(
                    f"{at}: the receipts for {receipt.receivable_id} add up to {fmt_yuan(paid[receipt.receivable_id])}, "
                    f"more than the {fmt_yuan(receivable.outstanding_fen)} owed")
            out.setdefault(week, []).append(receipt)
    return out


# ----------------------------------------------------------------------------------------------- one week


@dataclass
class Item:
    """One exported answer: the file, its hash and the sentence the owner read (a refusal's sentence when FLOW refused)."""

    answer: str
    file: str
    sha256: str
    sentence: str
    refused: bool
    seconds: float
    buyer: str | None = None


@dataclass
class ReceiptResult:
    """One receipt posted: what the executor said and, when it landed, the receivable's balance afterwards."""

    receipt: Receipt
    day: int  # the clock's day when it was posted
    op_id: str
    status: str
    outstanding_fen: int | None  # the receivable's outstanding face after the post; None when the executor refused it
    message: str

    @property
    def landed(self) -> bool:
        return self.status == OperationStatus.EXECUTED.value

    @property
    def text(self) -> str:
        r = self.receipt
        head = f"{r.receivable_id}: {fmt_yuan(r.amount_fen)} on day {self.day}, bank reference {r.bank_reference}, operation {self.op_id}"
        if self.landed and self.outstanding_fen is not None:
            return f"{head}; {fmt_yuan(self.outstanding_fen)} still outstanding on it"
        return f"{head}; {self.status}: {self.message}"


@dataclass
class WeekResult:
    week: int
    day: int = 0
    advances: int = 0  # clock advances that succeeded this week (one, or one more per receipt day before the week's end)
    receipts: list[ReceiptResult] = field(default_factory=list)
    seconds: float = 0.0
    items: list[Item] = field(default_factory=list)
    zones: list[Item] = field(default_factory=list)  # the zone tables, read and kept only with --zone (answer "zone")
    worth_rows: list[str] = field(default_factory=list)
    choices: list[str] = field(default_factory=list)
    receipts_posted: int = 0  # receipts the executor answered this week (landed or refused)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # findings that are not failures: an answer slower than SLOW_SECONDS
    open_decisions: list[str] = field(default_factory=list)


@dataclass
class DryRunResult:
    label: str
    weeks: list[WeekResult]
    operations_before: int  # the log's entries other than ADVANCE_CLOCK and RECEIVE_PAYMENT, before the first week
    operations_after: int  # ... and after the last: must be equal, nothing here acts beyond the receipts file
    clock_entries: int  # the ADVANCE_CLOCK entries the weeks added: one per advance, the clock's own log entry
    advances: int  # the advances that succeeded
    chain_valid: bool
    out: Path
    receipt_entries: int = 0  # the RECEIVE_PAYMENT entries the weeks added (a refused receipt is logged too)
    receipts_posted: int = 0  # the receipts the executor answered (landed or refused)

    @property
    def receipts_landed(self) -> int:
        return sum(1 for w in self.weeks for r in w.receipts if r.landed)

    @property
    def ok(self) -> bool:
        return (not any(w.errors for w in self.weeks) and self.operations_before == self.operations_after
                and self.clock_entries == self.advances and self.receipt_entries == self.receipts_posted and self.chain_valid)


def strip_timing(body: object) -> object:
    """`body` without any key in `TIMING_KEYS`, at any depth: the canonical form that is exported and hashed."""
    if isinstance(body, dict):
        return {k: strip_timing(v) for k, v in body.items() if k not in TIMING_KEYS}
    if isinstance(body, list):
        return [strip_timing(v) for v in body]
    return body


def _write_json(path: Path, body: object) -> str:
    data = (json.dumps(strip_timing(body), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _detail(body: object) -> str:
    detail = body.get("detail") if isinstance(body, dict) else body
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return str(detail["message"])
    return detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)


def _buyers_with_a_lever(rt: Runtime) -> list[str]:
    """The buyers an envelope can be asked of: an open invoice, a recurring invoice or an expected order on the books."""
    state = rt.store.get_state()
    with_lever = (
        {r.counterparty_id for r in state.receivables if r.status in ("OPEN", "FINANCED")}
        | {r.counterparty_id for r in state.recurring_invoices}
        | {o.counterparty_id for o in state.expected_orders}
    )
    return [c.id for c in state.counterparties if c.role == "BUYER" and c.id in with_lever]


def _export_week(rt: Runtime, client: Any, week_dir: Path, result: WeekResult, *, zone: bool = False) -> None:
    """Read the three answers and write their files; fills `result.items`, `worth_rows` and `errors`. The envelope is read
    without its zone table (`zone=0`, as the web reads it: the table is a detail opened on demand, and the read is a
    few seconds shorter); with `zone` each buyer's table is read as well, after the envelope, and written to `envelope-<buyer>-zone.json`
    (the same answer with the table in it) and listed in `result.zones`, which is no answer a decision is recorded against."""

    def read(answer: str, file: str, path: str, params: dict[str, Any], buyer: str | None = None,
             keep: list[Item] | None = None) -> tuple[Item | None, Any]:
        label = answer if buyer is None else f"{answer} {buyer}"
        started = time.perf_counter()
        try:
            resp = client.get(path, params=params)
            body = resp.json()
        except Exception as exc:  # noqa: BLE001 - an answer that raises is a finding, recorded with its week
            result.errors.append(f"{label}: {type(exc).__name__}: {exc}")
            return None, None
        seconds = time.perf_counter() - started
        if resp.status_code not in (200, 422):
            result.errors.append(f"{label}: HTTP {resp.status_code}: {_detail(body)}")
            return None, None
        digest = _write_json(week_dir / file, body)
        refused = resp.status_code == 422
        if refused:
            sentence = _detail(body)
        elif answer == "curve":
            sentence = str(body["sentence"])
        elif answer == "worth":
            sentence = str(body["top_action"])
        else:
            sentence = str(body.get("refused") or body["primary"])
        if seconds > SLOW_SECONDS:
            result.notes.append(f"{label}: took {seconds:.1f} s (over {SLOW_SECONDS:.0f} s)")
        item = Item(answer, file, digest, sentence, refused, seconds, buyer)
        (result.items if keep is None else keep).append(item)
        return item, body

    read("curve", CURVE_FILE, "/cash/price-curve", {"lang": "en"})
    _, worth = read("worth", WORTH_FILE, "/receivables/worth", {"lang": "en"})
    if isinstance(worth, dict) and isinstance(worth.get("rows"), list):
        result.worth_rows = [f"{r['receivable_id']} ({r['buyer_name']}): {r['worth_text']}. {r['action_sentence']}" for r in worth["rows"]]
    for buyer in _buyers_with_a_lever(rt):
        read("envelope", f"envelope-{buyer}.json", f"/buyers/{buyer}/envelope", {"zone": 0, "lang": "en"}, buyer)
        if zone:
            read("zone", f"envelope-{buyer}-zone.json", f"/buyers/{buyer}/envelope", {"zone": 1, "lang": "en"}, buyer,
                 keep=result.zones)


def _find(items: list[Item], decision: Decision) -> Item | str:
    """The exported item a decision is against, or a sentence saying why there is none."""
    matches = [i for i in items if i.answer == decision.answer and (decision.buyer is None or i.buyer == decision.buyer)]
    if len(matches) == 1:
        return matches[0]
    what = decision.answer if decision.buyer is None else f"{decision.answer} {decision.buyer}"
    if not matches:
        return f"decision for {what}: there is no such answer this week"
    return f"decision for {what}: name the buyer (buyer: ...), there are {len(matches)} envelopes this week"


def _record(client: Any, item: Item, decision: Decision, label: str, week: int, today: str, result: WeekResult) -> None:
    body = {
        "week": week, "sme": label, "answer": decision.answer, "flow_said": item.sentence, "snapshot_hash": item.sha256,
        "owner_did": decision.owner_did, "choice": decision.choice, "recorded_on": today,
    }
    name = item.answer if item.buyer is None else f"{item.answer} {item.buyer}"
    try:
        resp = client.post("/pilot/journal", json=body)
    except Exception as exc:  # noqa: BLE001 - e.g. the journal file could not be written
        result.errors.append(f"journal {name}: {type(exc).__name__}: {exc}")
        return
    if resp.status_code != 201:
        result.errors.append(f"journal {name}: HTTP {resp.status_code}: {_detail(resp.json())}")
        return
    result.choices.append(f"{name}: {decision.choice}")


def _post_receipt(
    rt: Runtime, client: Any, receipt: Receipt, op_id: str, label: str, week: int, today: str, res: WeekResult
) -> None:
    """Post one receipt as the bank feed does (`POST /operations` with `requested_by: SYSTEM` reaches the runtime's executor
    with exactly this operation) and, when it lands, record it in the journal as a `receipt` entry."""
    outcome: ReceiptResult
    try:
        op = ReceivePayment(
            op_id=op_id, idempotency_key=op_id, mandate_version=rt.store.get_mandate().version, requested_by=Actor.SYSTEM,
            day=rt.day, receivable_id=receipt.receivable_id, amount_fen=receipt.amount_fen, bank_reference=receipt.bank_reference)
        with rt.lock:
            result = rt.executor.execute(op)
            held = next((r for r in rt.store.get_state().receivables if r.id == receipt.receivable_id), None)
    except Exception as exc:  # noqa: BLE001 - a receipt that raises is a finding, recorded with its week
        res.errors.append(f"receipt {receipt.receivable_id} {receipt.bank_reference}: {type(exc).__name__}: {exc}")
        return
    res.receipts_posted += 1
    landed = result.status == OperationStatus.EXECUTED
    outcome = ReceiptResult(receipt, rt.day, op_id, result.status.value, held.outstanding_fen if landed and held else None, result.message)
    res.receipts.append(outcome)
    if not outcome.landed:
        res.errors.append(f"receipt {receipt.receivable_id} {receipt.bank_reference}: {outcome.status}: {outcome.message}")
        return
    facts = {"bank_reference": receipt.bank_reference, "amount_fen": receipt.amount_fen, "day": outcome.day, "op_id": op_id,
             "outstanding_fen": outcome.outstanding_fen, "receivable_id": receipt.receivable_id}
    body = {
        "week": week, "sme": label, "answer": "receipt", "flow_said": outcome.text,
        "snapshot_hash": hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        "owner_did": f"Receipts file: credited as the bank feed would, operation {op_id}; the clock did not assume it.",
        "choice": "not_applicable", "recorded_on": today,
    }
    try:
        resp = client.post("/pilot/journal", json=body)
    except Exception as exc:  # noqa: BLE001 - e.g. the journal file could not be written
        res.errors.append(f"journal receipt {op_id}: {type(exc).__name__}: {exc}")
        return
    if resp.status_code != 201:
        res.errors.append(f"journal receipt {op_id}: HTTP {resp.status_code}: {_detail(resp.json())}")


def _advance_week(
    rt: Runtime, client: Any, week: int, receipts: list[Receipt], label: str, today: str, res: WeekResult
) -> None:
    """Move the clock seven days, posting each receipt on its day of the week (the end of the week unless the file says
    otherwise). Raises whatever the clock raises; `res.day` is the clock's day after the last successful advance."""
    start = rt.day
    ordered = sorted(enumerate(receipts, start=1), key=lambda pair: pair[1].day)  # stable: file order within a day
    for target in sorted({r.day for r in receipts} | {DAYS_IN_WEEK}):
        rt.advance_to(start + target)
        res.advances += 1
        res.day = rt.day
        for number, receipt in ordered:
            if receipt.day == target:
                _post_receipt(rt, client, receipt, f"dry-receipt-w{week:02d}-{number}", label, week, today, res)


def run_dry(
    rt: Runtime, *, label: str, weeks: int, out: Path, decisions: dict[int, list[Decision]] | None, role_play: bool,
    today: str | None = None, owner_token: str = "demo-owner-token", say: Callable[[str], None] = print,
    receipts: dict[int, list[Receipt]] | None = None, zone: bool = False,
) -> DryRunResult:
    """Run the weeks on `rt` (installed as the app's runtime for the duration). Posts no operation of its own: the only
    entries it adds to the operations log are the clock's and the `receipts` it was given (already validated against the
    books by `load_receipts`)."""
    from fastapi.testclient import TestClient

    from app.api.runtime import set_runtime
    from app.main import app

    if role_play and decisions is not None:
        raise DryRunError("give --decisions or --role-play auto, not both")
    recorded_on = today or datetime.now().astimezone().date().isoformat()
    other_before, clock_before, receipts_before = _operation_counts(rt)
    results: list[WeekResult] = []
    out.mkdir(parents=True, exist_ok=True)
    set_runtime(rt)
    try:
        client = TestClient(app, headers={"X-Owner-Token": owner_token})
        for week in range(1, weeks + 1):
            res = WeekResult(week)
            results.append(res)
            started = time.perf_counter()
            try:
                _advance_week(rt, client, week, (receipts or {}).get(week, []), label, recorded_on, res)
            except Exception as exc:  # noqa: BLE001 - without the clock the later weeks mean nothing: stop and report
                res.errors.append(f"clock advance: {type(exc).__name__}: {exc}")
                res.seconds = time.perf_counter() - started
                say(f"week {week}: the clock could not be advanced: {exc}")
                break
            week_dir = out / f"week-{week:02d}"
            week_dir.mkdir(parents=True, exist_ok=True)
            _export_week(rt, client, week_dir, res, zone=zone)
            planned = [Decision(i.answer, ROLE_PLAY_DID, "followed", i.buyer) for i in res.items] if role_play else list(
                (decisions or {}).get(week, []))
            decided: set[int] = set()
            for decision in planned:
                found = _find(res.items, decision)
                if isinstance(found, str):
                    res.errors.append(found)
                else:
                    decided.add(id(found))
                    _record(client, found, decision, label, week, recorded_on, res)
            res.open_decisions = [_name(i) for i in res.items if id(i) not in decided]
            res.seconds = time.perf_counter() - started
            _write_sentences(week_dir, label, res)
            _say_week(say, label, res)
    finally:
        set_runtime(None)
    other_after, clock_after, receipts_after = _operation_counts(rt)
    result = DryRunResult(label, results, other_before, other_after, clock_after - clock_before, sum(w.advances for w in results),
                          rt.store.verify_chain(), out, receipts_after - receipts_before, sum(w.receipts_posted for w in results))
    (out / "summary.md").write_text(render_summary(result), encoding="utf-8")
    say(_operations_line(result))
    return result


def _operation_counts(rt: Runtime) -> tuple[int, int, int]:
    """(entries other than ADVANCE_CLOCK and RECEIVE_PAYMENT, ADVANCE_CLOCK entries, RECEIVE_PAYMENT entries) on the
    operations log. Moving the clock logs one ADVANCE_CLOCK entry per advance (app/clock) and every receipt the receipts
    file posts logs one RECEIVE_PAYMENT entry (a refusal too); those are the only entries a dry run may add."""
    kinds = [o.kind for o in rt.store.operations()]
    clock, receipts = sum(1 for k in kinds if k == "ADVANCE_CLOCK"), sum(1 for k in kinds if k == "RECEIVE_PAYMENT")
    return len(kinds) - clock - receipts, clock, receipts


def _operations_line(result: DryRunResult) -> str:
    return (f"operations other than the clock's and the receipts': before {result.operations_before}, after {result.operations_after}; "
            f"clock entries added {result.clock_entries} for {result.advances} advances; "
            f"receipt entries added {result.receipt_entries} for {result.receipts_posted} receipts posted ({result.receipts_landed} landed); "
            f"hash chain {'verifies' if result.chain_valid else 'DOES NOT VERIFY'}")


def _name(item: Item) -> str:
    return item.answer if item.buyer is None else f"{item.answer} {item.buyer}"


# ----------------------------------------------------------------------------------------------- output


def _sentence_lines(res: WeekResult) -> list[str]:
    lines: list[str] = []
    for item in res.items:
        title = {"curve": "Cash price (the curve)", "worth": "Collections (worth collecting)"}.get(item.answer, f"Deal limits (envelope, {item.buyer})")
        lines += [f"### {title}", "", item.sentence + ("  (FLOW could not answer)" if item.refused else "")]
        if item.answer == "worth":
            lines += ["", *[f"- {row}" for row in res.worth_rows]]
        lines += ["", f"`{item.file}` sha256 `{item.sha256}`", ""]
    for item in res.zones:
        lines += [f"### Zone table (envelope, {item.buyer})", "", f"`{item.file}` sha256 `{item.sha256}`, read in {item.seconds:.1f} s", ""]
    return lines


def _write_sentences(week_dir: Path, label: str, res: WeekResult) -> None:
    head = [f"# {label}, week {res.week:02d} (day {res.day})", "", BANNER, ""]
    if res.receipts:
        head += ["### Receipts posted before the reads", "", *[f"- {r.text}" for r in res.receipts], ""]
    (week_dir / "sentences.md").write_text("\n".join([*head, *_sentence_lines(res)]), encoding="utf-8")
    (week_dir / "sha256.txt").write_text("".join(f"{i.sha256}  {i.file}\n" for i in [*res.items, *res.zones]), encoding="utf-8")


def _say_week(say: Callable[[str], None], label: str, res: WeekResult) -> None:
    say(f"== {label} week {res.week:02d}, day {res.day} ({res.seconds:.1f} s)")
    for receipt in res.receipts:
        say(f"  receipt {receipt.text}")
    for item in res.items:
        say(f"  [{_name(item)}] {item.sentence}")
    for row in res.worth_rows:
        say(f"    {row}")
    say("  open decisions: " + (", ".join(res.open_decisions) or "none"))
    for choice in res.choices:
        say(f"  recorded {choice}")
    for note in res.notes:
        say(f"  NOTE {note}")
    for error in res.errors:
        say(f"  ERROR {error}")


def render_summary(result: DryRunResult) -> str:
    lines = [f"# Dry pilot {result.label}: summary", "", BANNER, ""]
    lines += [_operations_line(result).capitalize() + ".", ""]
    for res in result.weeks:
        lines += [f"## Week {res.week:02d} (day {res.day}), {res.seconds:.1f} s", ""]
        lines += [f"- Receipt {r.text}" for r in res.receipts]
        for item in res.items:
            lines.append(f"- {_name(item)} ({item.seconds:.1f} s): {item.sentence}")
            if item.answer == "worth":
                lines += [f"  - {row}" for row in res.worth_rows]
        lines += [f"- Zone table, {z.buyer} ({z.seconds:.1f} s): `{z.file}`" for z in res.zones]
        lines.append("- Choices: " + ("; ".join(res.choices) or "none recorded"))
        if res.open_decisions:
            lines.append("- Open: " + ", ".join(res.open_decisions))
        lines.append("")
        if res.notes:
            lines += ["Slow:", *[f"- week {res.week}: {n}" for n in res.notes], ""]
        if res.errors:
            lines += ["Errors:", *[f"- week {res.week}: {e}" for e in res.errors], ""]
    errors = [(w.week, e) for w in result.weeks for e in w.errors]
    if result.operations_before != result.operations_after:
        lines += ["**An operation other than the clock's and the receipts file's was logged during this run. Stop and tell the lead.**", ""]
    lines += ["## Errors", "", *(f"- week {w}: {e}" for w, e in errors)] if errors else ["## Errors", "", "None."]
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------------------------- main


def configure_environment() -> str:
    """Set the flags the dry run needs, before the app is imported. Returns the owner token the TestClient presents."""
    for key, value in (
        ("TERMSLEDGER_NO_DOTENV", "1"), ("DATABASE_URL", "memory"), ("LLM_MODE", "cache"), ("PYTHONUTF8", "1"),
        ("DEMO_MODE", "0"), ("FEATURE_ENVELOPE", "1"), ("FEATURE_PRICE_CURVE", "1"), ("FEATURE_COLLECTIONS_WORTH", "1"),
        ("FEATURE_PILOT_JOURNAL", "1"),
    ):
        os.environ[key] = value
    os.environ["OWNER_TOKEN"] = token = secrets.token_hex(16)
    os.environ["AGENT_KEY"] = secrets.token_hex(16)
    return token


def _check_label(label: str) -> None:
    from pydantic import ValidationError

    from app.pilot.journal import JournalEntryIn

    try:
        JournalEntryIn.model_validate({
            "week": 1, "sme": label, "answer": "curve", "flow_said": "x", "snapshot_hash": "0" * 64, "owner_did": "x",
            "choice": "followed", "recorded_on": "2026-01-01",
        })
    except ValidationError:
        raise DryRunError("--label is 1 to 64 letters, digits, spaces, hyphens or underscores") from None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--mandate", type=Path, required=True)
    ap.add_argument("--owner-key-file", type=Path, default=None)
    ap.add_argument("--label", required=True)
    ap.add_argument("--weeks", type=int, default=8)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--decisions", type=Path, default=None)
    ap.add_argument("--receipts", type=Path, default=None)
    ap.add_argument("--role-play", choices=["auto"], default=None)
    ap.add_argument("--journal-file", type=Path, default=None)
    ap.add_argument("--allow-repo-path", action="store_true")
    ap.add_argument("--zone", action="store_true")
    args = ap.parse_args(argv)
    token = configure_environment()
    try:
        if not 1 <= args.weeks <= 60:
            raise DryRunError("--weeks is 1 to 60")
        if args.decisions is not None and args.role_play is not None:
            raise DryRunError("give --decisions or --role-play auto, not both")
        _check_label(args.label)
        decisions = load_decisions(args.decisions, args.weeks) if args.decisions is not None else None
        from pilot_runtime import PilotStartError, build_runtime

        try:
            rt = build_runtime(args.state, args.mandate, args.owner_key_file, args.journal_file, args.allow_repo_path)
        except PilotStartError as exc:
            raise DryRunError(f"dry run not started: {exc}") from None
        receipts = load_receipts(args.receipts, args.weeks, rt.store.get_state()) if args.receipts is not None else None
        if rt.store.pilot_journal():  # type: ignore[attr-defined]
            raise DryRunError(
                f"dry run not started: the journal file {args.journal_file} already holds entries; a dry run starts at week 1, "
                "so name a new file"
            )
    except DryRunError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    result = run_dry(rt, label=args.label, weeks=args.weeks, out=args.out, decisions=decisions,
                     role_play=args.role_play == "auto", owner_token=token, receipts=receipts, zone=args.zone)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
