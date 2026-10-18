"""WARM-1 (Security Lead review of 6d2b6941, 18 Oct): the strategy warm-up worker inherited the API's whole environment (owner token,
agent and bank-feed keys, provider API keys), and DEMO_WARM_STRATEGY alone started it, demo mode or not. It now gets an allow-list,
and only the local demo starts it."""

from __future__ import annotations

from app.api import strategy_warm


def test_the_worker_gets_no_credentials_or_provider_keys(monkeypatch):
    for k in ("OWNER_TOKEN", "AGENT_KEY", "BANK_FEED_KEY", "COUNTERPARTY_KEYS", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
              "OWNER_PUBLIC_KEY_HEX"):
        monkeypatch.setenv(k, "secret-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
    monkeypatch.setenv("FEATURE_CONTRACTS", "1")
    env = strategy_warm._worker_env()
    assert not [k for k in env if "secret-value" in env[k]]
    assert env["DATABASE_URL"] == "memory" and env["LLM_MODE"] == "cache" and env["TERMSLEDGER_NO_DOTENV"] == "1"
    assert env.get("FEATURE_CONTRACTS") == "1" and "PATH" in env


def test_the_flag_alone_starts_nothing_outside_demo_mode(monkeypatch):
    monkeypatch.setenv("DEMO_WARM_STRATEGY", "1")
    monkeypatch.setenv("DEMO_MODE", "0")
    assert strategy_warm.warming_on() is False
    monkeypatch.setenv("DEMO_MODE", "1")
    assert strategy_warm.warming_on() is True
