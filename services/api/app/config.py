"""Settings and feature flags. Every optional feature can be switched off without breaking the core
(Terms Guard + Debt Desk committed routing + verifier + executor + /nl)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _flag(name: str, default: bool = True) -> bool:
    return os.environ.get(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Features:
    terms_guard: bool = field(default_factory=lambda: _flag("FEATURE_TERMS_GUARD"))
    debt_desk: bool = field(default_factory=lambda: _flag("FEATURE_DEBT_DESK"))
    capex: bool = field(default_factory=lambda: _flag("FEATURE_CAPEX"))
    borrower_file: bool = field(default_factory=lambda: _flag("FEATURE_BORROWER_FILE"))
    buyer_negotiation: bool = field(default_factory=lambda: _flag("FEATURE_BUYER_NEGOTIATION"))
    security_scenes: bool = field(default_factory=lambda: _flag("FEATURE_SECURITY_SCENES"))
    after_signing: bool = field(default_factory=lambda: _flag("FEATURE_AFTER_SIGNING", default=False))
    alerts: bool = field(default_factory=lambda: _flag("FEATURE_ALERTS"))
    expected_plans: bool = field(default_factory=lambda: _flag("FEATURE_EXPECTED_PLANS"))


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///./termsledger.db"))
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


def get_settings() -> Settings:
    return Settings()
