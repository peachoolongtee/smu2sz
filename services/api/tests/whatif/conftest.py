"""What-if fixtures: the golden state and signed mandate, and an API client with only the what-if
router mounted (app/main.py is the architect's; the router is mounted there at integration)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.api.whatif import router
from app.config import get_settings
from app.domain.fixtures import golden_values, load_scenario
from app.domain.models import FinancialState, Mandate
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.persistence import InMemoryLedgerStore
from app.whatif import PRESETS, WhatIfParams, WhatIfResult, simulate


@pytest.fixture(scope="session")
def g() -> dict:
    return golden_values()


@pytest.fixture(scope="session")
def state() -> FinancialState:
    return load_scenario()[0]


@pytest.fixture(scope="session")
def mandate() -> Mandate:
    return load_signed_mandate()


@pytest.fixture(scope="session")
def key() -> str:
    return demo_owner_public_key_hex()


@pytest.fixture(scope="session")
def run(state, mandate, key):
    def _run(params: WhatIfParams | str) -> WhatIfResult:
        p = PRESETS[params] if isinstance(params, str) else params
        return simulate(state, mandate, p, trusted_owner_key_hex=key)

    return _run


@pytest.fixture
def rt():
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


@pytest.fixture
def client(rt):
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)
