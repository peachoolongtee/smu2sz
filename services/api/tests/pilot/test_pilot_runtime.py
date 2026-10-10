"""The pilot's start-up script (services/api/scripts/pilot_runtime.py): the SME's books and mandate, never the demo's."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.mandate import MandatePolicyImpl

API_DIR = Path(__file__).resolve().parents[2]
TEMPLATES = API_DIR.parents[1] / "docs" / "pilot" / "templates"
SCRIPT = API_DIR / "scripts" / "pilot_runtime.py"
STATE = TEMPLATES / "state.example.json"
MANDATE = TEMPLATES / "mandate.example.json"


@pytest.fixture(scope="module")
def pilot() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pilot_runtime", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["pilot_runtime"] = module
    spec.loader.exec_module(module)
    return module


def _changed(tmp_path: Path, source: Path, **changes: object) -> Path:
    data = json.loads(source.read_text(encoding="utf-8"))
    data.update(changes)
    path = tmp_path / source.name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_the_templates_load_as_the_smes_books_not_the_golden_ones(pilot: ModuleType) -> None:
    rt = pilot.build_runtime(STATE, MANDATE)
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    assert state.org_id == mandate.org_id == "SME-EXAMPLE"
    assert state.scenario is None and rt.day == 0
    assert mandate.signature_hex
    assert not MandatePolicyImpl(rt.owner_key_hex).check_validity(mandate, 0, mandate.version)
    assert rt.store.operations() == [] and rt.store.commitments() == []


def test_a_key_file_signs_the_mandate_and_is_pinned(pilot: ModuleType, tmp_path: Path) -> None:
    from nacl.signing import SigningKey

    key = SigningKey.generate()
    key_file = tmp_path / "key.json"
    key_file.write_text(json.dumps({"private_key_hex": key.encode().hex()}), encoding="utf-8")
    rt = pilot.build_runtime(STATE, MANDATE, key_file)
    assert rt.owner_key_hex == key.verify_key.encode().hex()
    assert rt.store.get_mandate().public_key_hex == rt.owner_key_hex


@pytest.mark.parametrize("changes, words", [
    ({"org_id": "SME-OTHER"}, "mandate is for"),
    ({"revoked": True}, "not valid on day 0"),
])
def test_a_mandate_that_does_not_fit_the_books_is_refused(
    pilot: ModuleType, tmp_path: Path, changes: dict[str, object], words: str
) -> None:
    with pytest.raises(pilot.PilotStartError, match=words):
        pilot.build_runtime(STATE, _changed(tmp_path, MANDATE, **changes))


@pytest.mark.parametrize("changes", [{"as_of_day": 3}, {"scenario": "golden_sme"}])
def test_books_not_on_day_zero_or_naming_a_demo_scenario_are_refused(
    pilot: ModuleType, tmp_path: Path, changes: dict[str, object]
) -> None:
    with pytest.raises(pilot.PilotStartError, match="day 0"):
        pilot.build_runtime(_changed(tmp_path, STATE, **changes), MANDATE)


def test_bad_files_are_a_sentence_not_a_traceback(pilot: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(pilot.PilotStartError, match="cannot read"):
        pilot.build_runtime(tmp_path / "nothing.json", MANDATE)
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(pilot.PilotStartError, match="not valid JSON"):
        pilot.build_runtime(broken, MANDATE)
    with pytest.raises(pilot.PilotStartError, match="do not validate"):
        pilot.build_runtime(_changed(tmp_path, STATE, cash_fen="a lot"), MANDATE)


def test_main_refuses_port_3000_and_a_persistent_store(
    pilot: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["--state", str(STATE), "--mandate", str(MANDATE)]
    assert pilot.main([*args, "--port", "3000"]) == 2
    monkeypatch.setenv("DATABASE_URL", "sqlite:///x.db")
    assert pilot.main(args) == 2
    assert "memory" in capsys.readouterr().err
