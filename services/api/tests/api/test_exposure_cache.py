"""The Deals exposure and picture reads are cached (issue #157) without changing a word of what they answer.

A cached read equals an uncached one in English and in Chinese; the two languages share the router's work (the late-payment kernel and the
refusal plan carry no words); a write (a new state version, a commitment) and a reset each drop the cached answer."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import offer_picture, refusal
from app.api import strategy_exposure as route
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import Commitment, CommitmentStatus
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.strategy import exposure as assembly
from app.strategy import impact

OWNER = {"X-Owner-Token": "demo-owner-token"}
EX01 = {"fixture_id": "EX01_PACKAGE"}


def _forget() -> None:
    route.clear_cache()
    offer_picture.clear_cache()


@pytest.fixture
def rt(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    _forget()
    yield runtime
    set_runtime(None)
    _forget()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


@pytest.fixture
def offer_id(api: TestClient) -> str:
    oid = str(api.post("/offers", json=EX01).json()["offer"]["offer_id"])
    assert api.post(f"/offers/{oid}/evaluate", json=EX01).status_code == 200
    return oid


def _unclocked(x: Any) -> Any:
    """Without the stopwatches (`computed_in_seconds`, a spare search's `seconds`): they say how long a read took, not what it says."""
    if isinstance(x, dict):
        return {k: _unclocked(v) for k, v in x.items() if k not in ("computed_in_seconds", "seconds")}
    return [_unclocked(v) for v in x] if isinstance(x, list) else x


def _body(api: TestClient, url: str) -> dict[str, Any]:
    r = api.get(url)
    assert r.status_code == 200, r.text
    out: dict[str, Any] = _unclocked(r.json())
    return out


def _count(monkeypatch: pytest.MonkeyPatch, module: Any, name: str) -> list[int]:
    calls: list[int] = []
    real = getattr(module, name)

    def counted(*a: Any, **k: Any) -> Any:
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(module, name, counted)
    return calls


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_exposure_read_cached_equals_uncached(api: TestClient, offer_id: str, lang: str) -> None:
    for path in ("/offers/{}/exposure?lang={}", "/offers/{}/exposure?lang={}&spare=0", "/offers/{}/exposure?lang={}&response=counter:0",
                 "/decisions/deal:{}/exposure?lang={}&spare=1"):
        url = path.format(offer_id, lang)
        _forget()
        cold = _body(api, url)
        assert len(route._ANSWERS) == 1
        warm = _body(api, url)  # the cached answer
        assert warm == cold
        _forget()
        assert _body(api, url) == cold  # and a rebuild from nothing says the same again


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_picture_cached_equals_uncached(api: TestClient, offer_id: str, lang: str) -> None:
    url = f"/offers/{offer_id}/picture?lang={lang}"
    _forget()
    cold = _body(api, url)
    warm = _body(api, url)
    assert warm == cold
    _forget()
    assert _body(api, url) == cold


def test_a_repeated_read_does_not_reach_the_assembly(api: TestClient, offer_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _count(monkeypatch, assembly, "exposure")
    url = f"/offers/{offer_id}/exposure"
    first = _body(api, url)
    assert _body(api, url) == first and _body(api, f"{url}?response=counter:0") is not None
    assert len(calls) == 2  # asked once, counter:0 once; the second asked read was the cache's
    api.get(f"{url}?lang=zh")
    assert len(calls) == 3  # another language is another answer


def test_the_two_languages_share_the_routers_work(api: TestClient, offer_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = _count(monkeypatch, impact, "plan")  # the late-payment kernel
    refused = _count(monkeypatch, refusal, "plan")  # the picture's refusal plan
    _forget()
    impact.clear_cache()
    refusal.clear_cache()
    en = _body(api, f"/offers/{offer_id}/exposure?lang=en")
    _body(api, f"/offers/{offer_id}/picture?lang=en")
    ran = (len(kernel), len(refused))
    assert ran[0] > 0 and ran[1] > 0
    zh = _body(api, f"/offers/{offer_id}/exposure?lang=zh")
    _body(api, f"/offers/{offer_id}/picture?lang=zh")
    assert (len(kernel), len(refused)) == ran  # Chinese searched nothing again
    assert zh != en and zh["lang"] == "zh"


def test_a_write_drops_the_cached_answer(api: TestClient, rt: Runtime, offer_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _count(monkeypatch, assembly, "exposure")
    pics = _count(monkeypatch, offer_picture, "build")
    url = f"/offers/{offer_id}/exposure?spare=0"
    _forget()
    before = _body(api, url)
    _body(api, f"/offers/{offer_id}/picture")
    api.get(url)
    assert len(calls) == 1 and len(pics) == 1
    state = rt.store.get_state()  # a write: other books, and the state version that goes with them
    rt.store.put_state(state.model_copy(update={"cash_fen": state.cash_fen + 100, "state_version": state.state_version + 1}))
    after = _body(api, url)
    _body(api, f"/offers/{offer_id}/picture")
    assert len(calls) == 2 and len(pics) == 2
    assert after["state_version"] == before["state_version"] + 1
    rt.store.put_commitment(Commitment(  # a commitment of another offer
        id="CMT-OTHER", offer_id="OFF-OTHER", offer_version=1, counterparty_id="BUYER-2", verdict_id="V-OTHER", terms_hash="h",
        obligations=[], status=CommitmentStatus.ACTIVE, nonce="n", expires_day=7, mandate_version=1, forward_value_fen=0))
    _body(api, url)
    assert len(calls) == 3


def test_a_reset_drops_the_cached_answers(api: TestClient, rt: Runtime, offer_id: str) -> None:
    _body(api, f"/offers/{offer_id}/exposure")
    _body(api, f"/offers/{offer_id}/picture")
    assert len(route._ANSWERS) == 1 and len(offer_picture._cache) == 1
    rt.reset()
    assert len(route._ANSWERS) == 0 and len(offer_picture._cache) == 0 and len(refusal._PLANS) == 0 and len(impact._KERNEL) == 0
    assert len(assembly._BASE) == 0
