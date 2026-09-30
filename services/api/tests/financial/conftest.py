import pytest

from app.domain.fixtures import golden_values, load_scenario


@pytest.fixture(scope="session")
def scenario():
    return load_scenario("golden_sme")


@pytest.fixture(scope="session")
def state(scenario):
    return scenario[0]


@pytest.fixture(scope="session")
def mandate(scenario):
    return scenario[1]


@pytest.fixture(scope="session")
def g():
    return golden_values()
