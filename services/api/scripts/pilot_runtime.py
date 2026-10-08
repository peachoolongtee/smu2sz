#!/usr/bin/env python3
"""Start one pilot runtime: the API on one SME's books, in memory, never the demo books (wayfinder map #58).

There is no route that enters invoices, recurring invoices or a mandate, and `Runtime.reset(scenario)` always seeds the
golden mandate. So the pilot's books are loaded here, once, at start-up, through the same store calls the runtime uses
(`put_state`, `put_mandate`), and the app is served in this process. Nothing in `app/` is changed; the engine, the
operations and the verdicts are the demo's.

  --state PATH     the SME's books as JSON (a `FinancialState`; see docs/pilot/templates/state.example.json)
  --mandate PATH   the SME's mandate as JSON (a `Mandate`; see docs/pilot/templates/mandate.example.json). When it
                   carries no signature it is signed here with the key in --owner-key-file, else with the published
                   DEMO key (which proves nothing about a real owner: fine for a local, read-only pilot runtime).
  --owner-key-file PATH   JSON with `private_key_hex` (an Ed25519 seed). Optional. Keep it outside the repository.
  --journal-file PATH     the pilot journal on a file: JSON lines, one entry per line. The file is replayed into the store at
                   start-up (a malformed line refuses the start, naming the line) and every `POST /pilot/journal` is appended
                   to it before the route answers. A path inside the repository is refused unless it is under
                   docs/pilot/<label>/ and --allow-repo-path is passed. The in-memory store is still the source of truth.

Usage (from the repository root; OWNER_TOKEN and AGENT_KEY are required because DEMO_MODE=0 accepts no published token):

    TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=0 PYTHONUTF8=1 \
      OWNER_TOKEN=<a token you choose> AGENT_KEY=<another> \
      FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 FEATURE_PILOT_JOURNAL=1 \
      uv run --project services/api python services/api/scripts/pilot_runtime.py \
        --state <state.json> --mandate <mandate.json> --port 8001

The store is in memory: stopping the process forgets the books, and the journal too unless --journal-file is given, so
export what matters first (docs/pilot/RUNBOOK.md). Refuses to start when the books or the mandate do not validate, when the mandate is not valid
on day 0, or when the port is 3000.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from pydantic import ValidationError

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import FinancialState, Mandate
from app.mandate import MandatePolicyImpl, load_demo_owner_key, public_key_for, sign
from app.persistence import InMemoryLedgerStore
from app.pilot.file_journal import JournalFileError, open_journal


class PilotStartError(RuntimeError):
    """The pilot runtime cannot start safely; the message says what to fix."""


def _read_json(path: Path, what: str) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PilotStartError(f"cannot read {what} {path}: {exc.strerror}") from None
    except ValueError as exc:
        raise PilotStartError(f"{what} {path} is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise PilotStartError(f"{what} {path} must be a JSON object")
    return data


def _owner_private_key(key_file: Path | None) -> str:
    if key_file is None:
        return load_demo_owner_key()["private_key_hex"]
    key = _read_json(key_file, "owner key file").get("private_key_hex")
    if not isinstance(key, str) or len(key) != 64:
        raise PilotStartError(f"{key_file} must hold `private_key_hex`, a 32-byte Ed25519 seed as 64 hex characters")
    try:
        bytes.fromhex(key)
    except ValueError:
        raise PilotStartError(f"{key_file}: `private_key_hex` is not hexadecimal") from None
    return key


def build_runtime(
    state_path: Path, mandate_path: Path, key_file: Path | None = None, journal_file: Path | None = None,
    allow_repo_path: bool = False,
) -> Runtime:
    """An in-memory runtime holding only the SME's books and signed mandate. With `journal_file`, the store's pilot journal
    is replayed from that file and appended to it. Raises `PilotStartError`."""
    try:
        state = FinancialState.model_validate_json(json.dumps(_read_json(state_path, "state file")))
        mandate = Mandate.model_validate_json(json.dumps(_read_json(mandate_path, "mandate file")))
    except ValidationError as exc:
        first = exc.errors()[0]
        raise PilotStartError(f"the books or the mandate do not validate: {first['loc']}: {first['msg']}") from None
    if state.org_id != mandate.org_id:
        raise PilotStartError(f"the books are for {state.org_id} but the mandate is for {mandate.org_id}")
    if state.as_of_day != 0 or state.scenario is not None:
        raise PilotStartError("the books must start on day 0 and name no demo scenario (as_of_day 0, scenario null)")
    private_key = _owner_private_key(key_file)
    if not mandate.signature_hex:
        mandate = sign(mandate, private_key)
    owner_key_hex = public_key_for(private_key)
    problems = MandatePolicyImpl(trusted_public_key_hex=owner_key_hex).check_validity(mandate, 0, mandate.version)
    if problems:
        raise PilotStartError("the mandate is not valid on day 0: " + "; ".join(v.message for v in problems))
    store: InMemoryLedgerStore
    if journal_file is None:
        store = InMemoryLedgerStore()
    else:
        try:
            store = open_journal(journal_file, allow_repo_path=allow_repo_path)
        except JournalFileError as exc:
            raise PilotStartError(str(exc)) from None
    store.put_state(state)
    store.put_mandate(mandate)
    rt = Runtime(settings=get_settings(), store=store, owner_key_hex=owner_key_hex)
    rt.hydrate()
    return rt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--mandate", type=Path, required=True)
    ap.add_argument("--owner-key-file", type=Path, default=None)
    ap.add_argument("--journal-file", type=Path, default=None)
    ap.add_argument("--allow-repo-path", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8001)
    args = ap.parse_args(argv)
    if args.port == 3000:
        print("refusing port 3000: it is the web app's", file=sys.stderr)
        return 2
    if os.environ.get("DATABASE_URL", "memory") != "memory":
        print("the pilot runtime is in memory: set DATABASE_URL=memory", file=sys.stderr)
        return 2
    try:
        rt = build_runtime(args.state, args.mandate, args.owner_key_file, args.journal_file, args.allow_repo_path)
    except PilotStartError as exc:
        print(f"pilot runtime not started: {exc}", file=sys.stderr)
        return 2
    if args.journal_file is not None:
        print(f"pilot journal: {len(rt.store.pilot_journal())} entries replayed from {args.journal_file}")  # type: ignore[attr-defined]
        if not get_settings().features.pilot_journal:
            print("note: FEATURE_PILOT_JOURNAL is off, so the journal routes answer 403 and nothing will be written")
    set_runtime(rt)
    import uvicorn

    from app.main import app

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
