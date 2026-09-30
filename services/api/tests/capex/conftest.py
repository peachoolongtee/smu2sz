import pytest

from app.domain.fixtures import golden_values, load_scenario
from app.mandate import load_signed_mandate


@pytest.fixture
def state():
    s, _ = load_scenario("golden_sme")
    return s


@pytest.fixture
def mandate():
    return load_signed_mandate()


@pytest.fixture
def g():
    return golden_values()["capex"]
