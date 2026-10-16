"""A draw's cost line is its own lot's charges (owner, 16 Oct; `app/funding/search.py` `_attribute`).

On day 34 of the golden story (Option A agreed at ¥260,000, the agreed receipt on day 2, R-10) the line keeps ¥2,790 of
room and the router's cheapest plan draws it first. The line also carries the ¥147,210 drawn on day 0 for Option A; its
interest (147,210.00 × 6.4% × 47/365 = ¥1,213.17) is not the new draw's cost. The draw's own line is
2,790.00 × 6.4% × 13/365 = ¥6.36, and the option's lines still add up to its total of ¥1,702.20."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}


@pytest.fixture
def api() -> Iterator[TestClient]:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset_demo("golden_sme")
    set_runtime(rt)
    from app.main import app

    yield TestClient(app, headers=OWNER)
    set_runtime(None)


def test_the_day34_line_leg_is_the_draws_own_cost_and_the_option_reconciles(api: TestClient) -> None:
    oid = api.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    api.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    assert api.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()["outcome"] == "DEAL"
    api.post("/clock/advance", json={"to_day": 2})
    assert api.post("/demo/bank-receipt").status_code == 200
    api.post("/clock/advance", json={"to_day": 34})
    c = api.get("/home").json()["next_action"]["cheaper_option"]
    assert c["cost_total_display"] == "¥1,702.20"
    assert c["legs"][0] == "Bank credit line: draw ¥2,790.00, repaid in 13 days: ¥6.36"
    # ¥6.36 + ¥1,425.75 + ¥1,044.46 − ¥774.37 (the day-0 balance's interest and the rest of the projection) = ¥1,702.20
    assert c["legs"][-1] == "Change in other interest and fees across the forecast: −¥774.37"
    assert 636 + 142_575 + 104_446 - 77_437 == 170_220
