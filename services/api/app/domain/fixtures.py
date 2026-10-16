"""Load canonical fixtures from the repo's fixtures/ directory (read-only, trusted)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml

from app.domain.models import FinancialState, Mandate, SourceDocument

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"


def load_scenario(name: str = "golden_sme") -> tuple[FinancialState, Mandate]:
    raw = json.loads((FIXTURES / "scenarios" / f"{name}.json").read_text(encoding="utf-8"))
    state = FinancialState.model_validate_json(json.dumps(raw["state"]))
    mandate = Mandate.model_validate_json(json.dumps(raw["mandate"]))
    return state, mandate


def seed_state(name: str = "golden_sme") -> FinancialState:
    """A scenario's state as the demo seeds it: the scenario's name is stored with the books, so the clock applies
    that scenario's events (and no other's) to them, also after a restart."""
    state, _ = load_scenario(name)
    return state.model_copy(update={"scenario": name})


@lru_cache
def scenario_events(name: str = "golden_sme") -> list[dict]:
    """Dated events the outside world adds to a scenario's books as the clock passes them (may be none)."""
    path = FIXTURES / "scenarios" / f"{name}.events.json"
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("events", []))


def scenario_seed(name: str) -> dict | None:
    """What the demo replays on a scenario's books after they are seeded (offers to submit and evaluate, negotiations to
    send, operations to post: `app.api.demo_seed`), or None when the scenario has no seed file."""
    path = FIXTURES / "scenarios" / f"{name}.seed.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path.name} must hold a JSON object")
    return data


def golden_values() -> dict:
    return json.loads((FIXTURES / "golden" / "golden_values.json").read_text(encoding="utf-8"))


def load_offers() -> dict[str, dict]:
    """Worked examples (spec v2 §8) and security messages, keyed by id."""
    data = yaml.safe_load((FIXTURES / "offers" / "offers.yaml").read_text(encoding="utf-8"))
    return {o["id"]: o for o in data["offers"]}


def offer_documents(offer_id: str) -> list[SourceDocument]:
    o = load_offers()[offer_id]
    return [SourceDocument.model_validate_json(json.dumps(d)) for d in o["documents"]]


CONTRACTS = FIXTURES / "contracts"


def load_contract_fixtures() -> dict[str, dict]:
    """Demo contracts and lender agreements (fixtures/contracts/contracts.yaml), keyed by id. Synthetic."""
    data = yaml.safe_load((CONTRACTS / "contracts.yaml").read_text(encoding="utf-8"))
    return {c["id"]: c for c in data["contracts"]}


def contract_fixture_bytes(fixture_id: str, fmt: str | None = None) -> tuple[str, bytes]:
    """(file name, raw bytes) of a demo document: its canonical text file, or the generated `fmt` copy."""
    c = load_contract_fixtures()[fixture_id]
    path = CONTRACTS / c["file"]
    if fmt is not None:
        path = path.with_suffix(f".{fmt}")
    return path.name, path.read_bytes()


CAPEX = FIXTURES / "capex"


def load_capex_contract_fixtures() -> dict[str, dict]:
    """Demo capex contracts (fixtures/capex/contracts.yaml, ADR-0013), keyed by id. Synthetic. Kept apart from the
    contract fixtures, which the demo confirms at start; a capex contract is never confirmed for the owner."""
    data = yaml.safe_load((CAPEX / "contracts.yaml").read_text(encoding="utf-8"))
    return {c["id"]: c for c in data["contracts"]}


def capex_contract_fixture_bytes(fixture_id: str, fmt: str | None = None) -> tuple[str, bytes]:
    """(file name, raw bytes) of a demo capex contract: its canonical text file, or a generated `fmt` copy."""
    c = load_capex_contract_fixtures()[fixture_id]
    path = CAPEX / c["file"]
    if fmt is not None:
        path = path.with_suffix(f".{fmt}")
    return path.name, path.read_bytes()
