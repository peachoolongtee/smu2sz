"""SEC-12 / SEC-13 (security register, 14 Oct): API responses carry no-sniff, no-frame and no-referrer headers; the interactive docs and the
schema are served only in DEMO_MODE."""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def test_every_response_carries_the_security_headers() -> None:
    from app.main import app

    for path in ("/health", "/ledger"):  # a public route and a refused one
        r = TestClient(app).get(path)
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert r.headers["referrer-policy"] == "no-referrer"


def test_docs_and_schema_are_not_served_outside_demo_mode(monkeypatch) -> None:
    from app import main

    monkeypatch.setenv("DEMO_MODE", "0")
    try:
        off = importlib.reload(main).app
        c = TestClient(off)
        assert [c.get(p).status_code for p in ("/docs", "/redoc", "/openapi.json")] == [404, 404, 404]
    finally:
        monkeypatch.setenv("DEMO_MODE", "1")
        importlib.reload(main)
