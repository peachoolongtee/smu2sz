"""Server-side display formatting (INVARIANT 13: the UI never computes money).

`displayed(x)` walks any JSON-able structure and adds a sibling display string for every money or
rate field: `<name>_fen` -> `<name>_display` ("¥26,455.62"); `<name>_bp` -> `<name>_display`
("1.25×" for DSCR/leverage limits, else "15.00%"); a bare `fen` -> `display`; a Ratio
{num, den} -> adds `text` ("1.92")."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from app.domain.money import Ratio, fmt_pct, fmt_yuan

_RATIO_BP = ("dscr", "leverage", "threshold")


def fmt_bp(name: str, bp: int) -> str:
    if any(k in name for k in _RATIO_BP):
        return Ratio.of(Fraction(bp, 10_000)).text + "×"
    return fmt_pct(Fraction(bp, 10_000))


def displayed(x: Any) -> Any:
    if isinstance(x, list):
        return [displayed(v) for v in x]
    if not isinstance(x, dict):
        return x
    out: dict[str, Any] = {k: displayed(v) for k, v in x.items()}
    if set(x) >= {"num", "den"} and isinstance(x.get("num"), int) and isinstance(x.get("den"), int) and x["den"]:
        out.setdefault("text", Ratio(num=x["num"], den=x["den"]).text)
    for k, v in x.items():
        if isinstance(v, bool) or not isinstance(v, int):
            continue
        if k == "fen":
            out.setdefault("display", fmt_yuan(v))
        elif k.endswith("_fen"):
            out.setdefault(k[:-4] + "_display", fmt_yuan(v))
        elif k.endswith("_bp"):
            out.setdefault(k[:-3] + "_display", fmt_bp(k, v))
    return out
