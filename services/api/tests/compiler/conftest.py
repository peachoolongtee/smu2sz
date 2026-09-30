from __future__ import annotations

import socket
from pathlib import Path

import pytest

from app.compiler import Compiler
from app.compiler.cache import CacheBackend
from app.compiler.rules import RulesBackend
from app.compiler.service import _default_compiler, cache_dir
from app.config import get_settings


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Compiler tests never touch a network: cache mode, no keys, and sockets refuse to connect."""
    monkeypatch.setenv("LLM_MODE", "cache")
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(k, raising=False)

    def _refuse(*_a: object, **_k: object) -> None:
        raise RuntimeError("network access in a compiler test")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    _default_compiler.cache_clear()


@pytest.fixture
def cache_path() -> Path:
    return cache_dir(get_settings())


@pytest.fixture
def compiler(cache_path: Path) -> Compiler:
    """The demo chain: recorded cache first, rules grammar on a miss."""
    return Compiler([CacheBackend(cache_path), RulesBackend()])


@pytest.fixture
def rules_compiler() -> Compiler:
    return Compiler([RulesBackend()])
