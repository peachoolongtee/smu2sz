"""Settings and feature flags. Every optional feature can be switched off without breaking the core
(Terms Guard + Debt Desk committed routing + verifier + executor + /nl).
The three strategy flags (envelope, price_curve, collections_worth) are the read-only MVP of map #47 and default off;
pilot_journal (map #58) is the shadow pilot's owner-recorded journal, also default off; exposure (map #88, Phase 1) is
buyer exposure on the deal and the customer-inputs routes, default off; customer_economics (map #88, Phase 2) lets the
customer-inputs routes take the six economics fields (sales, margins, classification, VAT), default off. Home V2 (`GET /worklist`, `GET /customers`
and the `home_v2` fields of `GET /home`) is the Home now and has no flag."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]

# The gross margin the Demo assumes for a customer whose owner has entered none (map #88): applied to any books, whatever the fixture is
# called, always shown as "assumed for the Demo, not confirmed by you" and never stored or passed off as the owner's.
DEMO_GROSS_MARGIN_BP = 2000
_ALIASES = {"DEEPSEEK_API": "DEEPSEEK_API_KEY", "ANTHROPIC_KEY": "ANTHROPIC_API_KEY"}


def load_dotenv(path: Path = _REPO_ROOT / ".env") -> None:
    """Load KEY=VALUE lines from the repo-root .env without overriding the real environment.
    Never logs values. Accepts a few key-name aliases and derives DATABASE_URL from
    SUPABASE_DB_URL (session pooler, IPv4) when DATABASE_URL is not set. Tests opt out."""
    if os.environ.get("TERMSLEDGER_NO_DOTENV"):
        return
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$", line)
            if not m or line.lstrip().startswith("#"):
                continue
            k, v = m.group(1), m.group(2).strip().strip('"').strip("'")
            os.environ.setdefault(_ALIASES.get(k, k), v)
    if "DATABASE_URL" not in os.environ and os.environ.get("SUPABASE_DB_URL"):
        os.environ["DATABASE_URL"] = re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", os.environ["SUPABASE_DB_URL"])


def _flag(name: str, default: bool = True) -> bool:
    return os.environ.get(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, str(default)).strip()))
    except ValueError:
        return default


def demo_mode() -> bool:
    """DEMO_MODE: off unless set (SEC-07, the owner's decision of 16 Oct 2026). On, it accepts the published demo credentials,
    seeds an empty store with the demo books, serves /docs and enables the demo routes. Local demos, the browser suites and the
    tests opt in with DEMO_MODE=1; a deployment never does."""
    return _flag("DEMO_MODE", default=False)


@dataclass(frozen=True)
class Features:
    terms_guard: bool = field(default_factory=lambda: _flag("FEATURE_TERMS_GUARD"))
    debt_desk: bool = field(default_factory=lambda: _flag("FEATURE_DEBT_DESK"))
    capex: bool = field(default_factory=lambda: _flag("FEATURE_CAPEX"))
    borrower_file: bool = field(default_factory=lambda: _flag("FEATURE_BORROWER_FILE"))
    buyer_negotiation: bool = field(default_factory=lambda: _flag("FEATURE_BUYER_NEGOTIATION"))
    security_scenes: bool = field(default_factory=lambda: _flag("FEATURE_SECURITY_SCENES"))
    alerts: bool = field(default_factory=lambda: _flag("FEATURE_ALERTS"))
    expected_plans: bool = field(default_factory=lambda: _flag("FEATURE_EXPECTED_PLANS"))
    envelope: bool = field(default_factory=lambda: _flag("FEATURE_ENVELOPE", default=False))
    price_curve: bool = field(default_factory=lambda: _flag("FEATURE_PRICE_CURVE", default=False))
    collections_worth: bool = field(default_factory=lambda: _flag("FEATURE_COLLECTIONS_WORTH", default=False))
    exposure: bool = field(default_factory=lambda: _flag("FEATURE_EXPOSURE", default=False))  # map #88 Phase 1, default off
    customer_economics: bool = field(default_factory=lambda: _flag("FEATURE_CUSTOMER_ECONOMICS", default=False))  # map #88 Phase 2
    contracts: bool = field(default_factory=lambda: _flag("FEATURE_CONTRACTS"))  # contract ingestion + deal summary
    pilot_journal: bool = field(default_factory=lambda: _flag("FEATURE_PILOT_JOURNAL", default=False))  # map #58, default off
    # ADR-0013, the buy side (capex contracts, financial health, loan eligibility, long-term plans); default off
    capex_contracts: bool = field(default_factory=lambda: _flag("FEATURE_CAPEX_CONTRACTS", default=False))


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///./termsledger.db"))
    owner_public_key_hex: str = field(default_factory=lambda: os.environ.get("OWNER_PUBLIC_KEY_HEX", ""))
    llm_mode: str = field(default_factory=lambda: os.environ.get("LLM_MODE", "cache"))  # cache | live
    llm_primary: str = field(default_factory=lambda: os.environ.get("LLM_PRIMARY", "claude"))  # claude | deepseek
    claude_model: str = field(default_factory=lambda: os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"))
    claude_hard_model: str = field(default_factory=lambda: os.environ.get("CLAUDE_HARD_MODEL", "claude-opus-5-5"))
    deepseek_model: str = field(default_factory=lambda: os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"))
    # Live mode replays a recorded reading before calling a model, and checks a model's reading of a buyer message against the
    # rules grammar's (app/compiler/service.py). LLM_LIVE_RAW=1 turns both off, to measure a model on its own.
    llm_live_raw: bool = field(default_factory=lambda: _flag("LLM_LIVE_RAW", default=False))
    # Privacy before the model (app/compiler/redaction.py): accounts, phones, emails, credit codes, ID numbers and labelled
    # addresses are replaced by placeholders before any text goes to a model provider. On by default; LLM_REDACT=0 turns it off.
    llm_redact: bool = field(default_factory=lambda: _flag("LLM_REDACT", default=True))
    fixture_dir: str = field(
        default_factory=lambda: os.environ.get(
            "FIXTURE_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "..", "fixtures")
        )
    )
    features: Features = field(default_factory=Features)
    # Offers and buyer turns that arrive without a channel key, per simulated day (R04, R05).
    intake_cap_per_day: int = field(default_factory=lambda: _int("INTAKE_CAP_PER_DAY", 200))
    # Offers and messages one keyed buyer (X-Counterparty-Key) may send per simulated day (R-10: threshold probing).
    buyer_attempts_per_day: int = field(default_factory=lambda: _int("BUYER_ATTEMPTS_PER_DAY", 5))


def get_settings() -> Settings:
    return Settings()
