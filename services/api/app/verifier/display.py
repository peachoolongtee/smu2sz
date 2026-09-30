"""How covenant breaches read in a verdict (display only: the numbers and the outcome never change here).

- A ratio that breaches its limit by less than the 2 dp display precision ("1.25x < 1.25x") is shown at
  4 dp, rounded away from the limit so the comparison stays true: DSCR 9000000/7200001 reads 1.2499x.
- The same monthly covenant breach repeated per month and per covenant source is summarised once:
  "DSCR below 1.25x in months 1–8 (lowest 1.2499x)". The violations themselves are all kept.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from app.covenants import fmt_x
from app.domain.models import Obligation, ObligationType, Violation, ViolationCode

# code -> (ratio name, relation to the limit, exact-value input key)
_MONTHLY = {
    ViolationCode.DSCR_BREACH: ("DSCR", "below", "dscr_exact"),
    ViolationCode.LEVERAGE_BREACH: ("Leverage", "above", "leverage_exact"),
}
_DP4 = 10_000


def _exact(text: str | None) -> Fraction | None:
    if not text:
        return None
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None


def fmt_x4(x: Fraction, *, down: bool) -> str:
    """The ratio at 4 dp, truncated towards the side of the limit it is on (down for a floor breach)."""
    scaled = x * _DP4
    q = scaled.numerator // scaled.denominator
    if not down and q != scaled:
        q += 1
    sign = "-" if q < 0 else ""
    q = abs(q)
    return f"{sign}{q // _DP4}.{q % _DP4:04d}x"


def precise(v: Violation) -> Violation:
    """A monthly ratio breach whose 2 dp display equals its limit, re-displayed at 4 dp."""
    spec = _MONTHLY.get(v.code)
    if spec is None or v.observed != v.limit:
        return v
    _, _, key = spec
    value, limit = _exact(v.inputs.get(key)), _exact(v.inputs.get("limit_exact"))
    if value is None or limit is None:
        return v
    shown = fmt_x4(value, down=v.code == ViolationCode.DSCR_BREACH)
    old = v.observed
    return v.model_copy(update={
        "observed": shown,
        "message": v.message.replace(f" {old} ", f" {shown} ", 1),
        "formula": (v.formula or "").replace(f"= {old} ", f"= {shown} ", 1),
    })


def month_ranges(months: Sequence[int]) -> str:
    """[1,2,3,5] -> 'months 1–3, 5'; [4] -> 'month 4'."""
    ms = sorted(set(months))
    if len(ms) == 1:
        return f"month {ms[0]}"
    runs: list[str] = []
    start = prev = ms[0]
    for m in ms[1:] + [None]:  # type: ignore[list-item]
        if m is not None and m == prev + 1:
            prev = m
            continue
        runs.append(f"{start}–{prev}" if prev != start else f"{start}")
        if m is not None:
            start = prev = m
    return "months " + ", ".join(runs)


def describe_all(violations: Sequence[Violation], describe: object) -> list[str]:
    """One summary item per violation, except monthly ratio breaches: one item per (code, limit)."""
    out: list[str] = []
    groups: dict[tuple[ViolationCode, str], list[Violation]] = {}
    order: list[tuple[str, object]] = []
    for v in violations:
        if v.code in _MONTHLY and v.month is not None and v.limit:
            key = (v.code, v.limit)
            if key not in groups:
                groups[key] = []
                order.append(("group", key))
            groups[key].append(v)
        else:
            order.append(("one", v))
    for kind, item in order:
        if kind == "one":
            out.append(describe(item))  # type: ignore[operator]
            continue
        code, limit = item  # type: ignore[misc]
        vs = groups[(code, limit)]
        name, rel, key = _MONTHLY[code]
        worst = vs[0]
        exacts = [(e, v) for v in vs if (e := _exact(v.inputs.get(key))) is not None]
        if exacts:
            worst = (min if code == ViolationCode.DSCR_BREACH else max)(exacts, key=lambda ev: ev[0])[1]
        extreme = "lowest" if code == ViolationCode.DSCR_BREACH else "highest"
        out.append(f"{code.value}: {name} {rel} {limit} in {month_ranges([v.month for v in vs if v.month is not None])} "
                   f"({extreme} {worst.observed})")
    return out


def only_early_pay(bound: Sequence[Obligation]) -> bool:
    """Every bound obligation is an immediate discount on a named receivable: the only package the agent may
    accept on its own (Tier 1). Mirrors the executor's `only_early_pay` on the same obligations."""
    return bool(bound) and all(o.type == ObligationType.IMMEDIATE_DISCOUNT and o.base.receivable_id for o in bound)


__all__ = ["describe_all", "fmt_x", "fmt_x4", "month_ranges", "only_early_pay", "precise"]
