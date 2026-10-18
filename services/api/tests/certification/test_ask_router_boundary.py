"""The Ask FLOW router (ADR-0015) through the language-boundary certification, as a read-only path.

The whole adversarial set (fixtures/certification/language_boundary.yaml) runs through the real POST /nl, in the harness's
cache mode, twice: as shipped, and with FEATURE_ASK_ROUTER on and a hostile routing model that, for every question it is
shown, routes to tools (two reads, the most it can do). The harness's own judge scores both runs with its criteria unchanged:
WRONG_MATERIAL stays at the known findings, WRONG_HARMLESS at the known few, and every item keeps its class, because the router
can only read. The router must actually be reached by some items, or this test would be blind.
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from app.nl.router import route as rr
from tests.certification.test_language_boundary import (
    KNOWN_FINDINGS,
    KNOWN_WRONG_HARMLESS,
    cert,
    material_ids,
)


class Hostile:
    """Routes every question it is shown to reads, whatever the question asks; keeps a count."""

    name = "hostile-router"
    live = True

    def __init__(self) -> None:
        self.calls = 0

    def route(self, prompt: rr.Prompt) -> tuple[str, str]:
        self.calls += 1
        return json.dumps({"calls": [{"tool": "cash_safety", "slots": {"horizon_days": 365}},
                                     {"tool": "total_debt", "slots": {}}], "none": False}), "hostile-model"


@pytest.fixture(scope="module")
def items() -> list[dict[str, Any]]:
    return cert.load_fixture()["items"]


@pytest.fixture(scope="module")
def baseline(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return cert.run_certification(cert.CacheMode(), items)


@pytest.fixture(scope="module")
def routed(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Hostile]:
    hostile = Hostile()
    saved_backends, saved_flag = rr.default_backends, os.environ.get("FEATURE_ASK_ROUTER")
    rr.default_backends = lambda: [hostile]  # type: ignore[assignment]
    os.environ["FEATURE_ASK_ROUTER"] = "1"
    try:
        return cert.run_certification(cert.CacheMode(), items), hostile
    finally:
        rr.default_backends = saved_backends  # type: ignore[assignment]
        if saved_flag is None:
            os.environ.pop("FEATURE_ASK_ROUTER", None)
        else:
            os.environ["FEATURE_ASK_ROUTER"] = saved_flag


def test_the_router_is_reached(baseline: list[dict[str, Any]], routed: tuple[list[dict[str, Any]], Hostile]) -> None:
    results, hostile = routed
    assert hostile.calls > 0
    before = {r["id"]: [t["reply"] for t in r["diff"]["turns"]] for r in baseline}
    changed = [r["id"] for r in results if [t["reply"] for t in r["diff"]["turns"]] != before[r["id"]]]
    assert changed  # some owner question got the routed read instead of the honest "cannot yet"


def test_no_new_wrong_material_with_the_router(routed: tuple[list[dict[str, Any]], Hostile]) -> None:
    results, _ = routed
    assert material_ids(results) <= set(KNOWN_FINDINGS), material_ids(results) - set(KNOWN_FINDINGS)


def test_wrong_harmless_stays_at_the_known_few_with_the_router(routed: tuple[list[dict[str, Any]], Hostile]) -> None:
    results, _ = routed
    harmless = {r["id"] for r in results if r["class"] == "WRONG_HARMLESS"}
    assert harmless <= KNOWN_WRONG_HARMLESS, harmless - KNOWN_WRONG_HARMLESS


def test_the_router_changes_no_item_s_class_or_effect(baseline: list[dict[str, Any]],
                                                       routed: tuple[list[dict[str, Any]], Hostile]) -> None:
    results, _ = routed
    before = {r["id"]: r for r in baseline}
    for r in results:
        b = before[r["id"]]
        assert r["class"] == b["class"], (r["id"], b["class"], r["class"])
        assert [(o["kind"], o["status"]) for o in r["diff"]["ops"]] == [(o["kind"], o["status"]) for o in b["diff"]["ops"]], r["id"]
        assert r["diff"]["approvals_decided"] == b["diff"]["approvals_decided"], r["id"]
        assert ([(c["from"], c["to"]) for c in r["diff"]["commitments_touched"]]
                == [(c["from"], c["to"]) for c in b["diff"]["commitments_touched"]]), r["id"]
        assert r["diff"]["books_changed"] == b["diff"]["books_changed"] and r["diff"]["mandate_changed"] == b["diff"]["mandate_changed"]
        assert not r["diff"]["leaks"] or r["diff"]["leaks"] == b["diff"]["leaks"], r["id"]
