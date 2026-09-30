"""Write apps/web/mocks/whatif_presets.json from the real simulator on the golden fixture, so mock
mode shows exactly what the server would. Mock-authoring tooling only; never imported by the app.

    cd services/api && uv run python -m app.whatif.export_mocks
"""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path

from app.domain.fixtures import FIXTURES, load_scenario
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.whatif.params import PRESETS, WhatIfParams
from app.whatif.simulate import presets, simulate

OUT = FIXTURES.parent / "apps" / "web" / "mocks" / "whatif_presets.json"

# A coarse grid around the story: terms (as is / buyer's ask / long), discount (none / buyer's 1.2%),
# rebate (none / buyer's 1%). Mock mode shows the nearest entry to the sliders.
GRID_TERMS = (30, 45, 60, 90)
GRID_DISCOUNT = (0, 120)
GRID_REBATE = (0, 100)


def entries() -> list[tuple[str, WhatIfParams]]:
    out: list[tuple[str, WhatIfParams]] = list(PRESETS.items())
    seen = {p.model_dump_json() for _, p in out}
    for t, d, r in product(GRID_TERMS, GRID_DISCOUNT, GRID_REBATE):
        p = WhatIfParams(terms_days=t, discount_bp=d, rebate_bp=r)
        if p.model_dump_json() not in seen:
            seen.add(p.model_dump_json())
            out.append((f"t{t}_d{d}_r{r}", p))
    return out


def build() -> dict:
    state, _ = load_scenario()
    mandate = load_signed_mandate()
    key = demo_owner_public_key_hex()
    rows = []
    for name, p in entries():
        r = simulate(state, mandate, p, trusted_owner_key_hex=key)
        view = r.model_dump()
        view.update({"compute_ms": 0, "cached": False})
        rows.append({"id": name, "params": p.model_dump(), "result": view})
    return {"source": "services/api app.whatif.export_mocks on fixtures/scenarios/golden_sme.json",
            "controls": {"hypothetical": True, **presets(state)}, "entries": rows}


def main(out: Path = OUT) -> None:
    out.write_text(json.dumps(build(), ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"wrote {out} ({out.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
