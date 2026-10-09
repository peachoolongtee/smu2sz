"""Settings and feature flags. Every optional feature can be switched off without breaking the core
(Terms Guard + Debt Desk committed routing + verifier + executor + /nl).
The three strategy flags (envelope, price_curve, collections_worth) are the read-only MVP of map #47 and default off."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
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
    contracts: bool = field(default_factory=lambda: _flag("FEATURE_CONTRACTS"))  # contract ingestion + deal summary


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///./termsledger.db"))
    owner_public_key_hex: str = field(default_factory=lambda: os.environ.get("OWNER_PUBLIC_KEY_HEX", ""))
    llm_mode: str = field(default_factory=lambda: os.environ.get("LLM_MODE", "cache"))  # cache | live
    llm_primary: str = field(default_factory=lambda: os.environ.get("LLM_PRIMARY", "claude"))  # claude | deepseek
    claude_model: str = field(default_factory=lambda: os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"))
    claude_hard_model: str = field(default_factory=lambda: os.environ.get("CLAUDE_HARD_MODEL", "claude-opus-5-5"))
    deepseek_model: str = field(default_factory=lambda: os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"))
    fixture_dir: str = field(
        default_factory=lambda: os.environ.get(
            "FIXTURE_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "..", "fixtures")
        )
    )
    features: Features = field(default_factory=Features)
    # Offers and buyer turns that arrive without a channel key, per simulated day (R04, R05).
    intake_cap_per_day: int = field(default_factory=lambda: _int("INTAKE_CAP_PER_DAY", 200))


def get_settings() -> Settings:
    return Settings()
