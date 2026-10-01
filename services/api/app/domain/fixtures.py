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


@lru_cache
def scenario_events(name: str = "golden_sme") -> list[dict]:
    """Dated events the outside world adds to a scenario's books as the clock passes them (may be none)."""
    path = FIXTURES / "scenarios" / f"{name}.events.json"
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("events", []))


def golden_values() -> dict:
    return json.loads((FIXTURES / "golden" / "golden_values.json").read_text(encoding="utf-8"))


def load_offers() -> dict[str, dict]:
    """Worked examples (spec v2 §8) and security messages, keyed by id."""
    data = yaml.safe_load((FIXTURES / "offers" / "offers.yaml").read_text(encoding="utf-8"))
    return {o["id"]: o for o in data["offers"]}


def offer_documents(offer_id: str) -> list[SourceDocument]:
    o = load_offers()[offer_id]
    return [SourceDocument.model_validate_json(json.dumps(d)) for d in o["documents"]]
