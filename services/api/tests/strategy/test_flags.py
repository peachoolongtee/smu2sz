import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.features import require_feature
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

_FLAGS = {
    "envelope": "FEATURE_ENVELOPE",
    "price_curve": "FEATURE_PRICE_CURVE",
    "collections_worth": "FEATURE_COLLECTIONS_WORTH",
    "exposure": "FEATURE_EXPOSURE",  # map #88 Phase 1
    "customer_economics": "FEATURE_CUSTOMER_ECONOMICS",  # map #88 Phase 2: the six economics fields of the inputs routes
}


@pytest.fixture
def flags_off(monkeypatch):
    for env in _FLAGS.values():
        monkeypatch.delenv(env, raising=False)


@pytest.fixture
def client(flags_off):
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


def test_strategy_flags_default_off(flags_off):
    features = get_settings().features
    assert [getattr(features, name) for name in _FLAGS] == [False] * len(_FLAGS)


def test_flag_turns_on_from_env(flags_off, monkeypatch):
    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    features = get_settings().features
    assert features.envelope is True
    assert features.price_curve is False and features.collections_worth is False and features.exposure is False


def test_health_lists_the_strategy_flags(client):
    features = client.get("/health").json()["features"]
    assert all(features[name] is False for name in _FLAGS)


def test_require_feature_is_403_when_off_and_none_when_on(flags_off, monkeypatch):
    with pytest.raises(HTTPException) as exc:
        require_feature("envelope")
    assert exc.value.status_code == 403
    assert exc.value.detail == {
        "code": "FEATURE_DISABLED",
        "feature": "envelope",
        "message": "The Safe Deal Envelope is switched off (FEATURE_ENVELOPE).",
    }
    monkeypatch.setenv("FEATURE_ENVELOPE", "1")
    assert require_feature("envelope") is None


def test_exposure_flag_turns_on_from_env_and_names_itself_when_off(flags_off, monkeypatch):
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    assert get_settings().features.exposure is True and require_feature("exposure") is None
    monkeypatch.delenv("FEATURE_EXPOSURE")
    with pytest.raises(HTTPException) as exc:
        require_feature("exposure")
    assert exc.value.status_code == 403
    assert exc.value.detail == {"code": "FEATURE_DISABLED", "feature": "exposure",
                                "message": "Buyer exposure is switched off (FEATURE_EXPOSURE)."}
