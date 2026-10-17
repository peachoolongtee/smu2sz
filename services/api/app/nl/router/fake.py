"""A scripted stand-in for the routing model, for tests and `scripts/record_router_cache.py --fake`. Never a product path.

It reads only what the real model reads (the prompt's question between its markers and the catalogue in the system prompt) and
answers in the same JSON shape, by keywords: so a cache recorded with it exercises the whole replay and validation path without a
network or a key. It picks only tools the catalogue in the prompt lists.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.nl.router.route import CLOSE_Q, OPEN_Q

# (tool, pattern) in order of preference; the first three that match and are in the catalogue are chosen
KEYWORDS: tuple[tuple[str, str], ...] = (
    ("total_debt", r"\bdebts?\b|\bowe (?:the )?banks?\b|\bloans?\b|负债|欠银行|贷款|债务"),
    ("late_payment_whatif", r"\bpays? late\b|\blate payment\b|晚付|延迟付款|拖延付款"),
    ("overdue", r"\boverdue\b|\bchase\b|逾期|催收"),
    ("who_owes_most", r"\bowes? us\b|谁欠"),
    ("covenant_status", r"\bcovenants?\b|契约"),
    ("payroll_cover", r"\bpayroll\b|\bwages\b|\bsalar(?:y|ies)\b|工资|发薪"),
    ("upcoming_payments", r"\bbills?\b|\bpayments? (?:due|coming)\b|要付|支出"),
    ("general_advice", r"\bwhat should i do\b|\bhow (?:do|can) i (?:ensure|keep|make sure)\b|怎么办|如何确保|怎样保证"),
    ("cash_safety", r"\bsafe\b|\bsurvive\b|\brun out\b|\bcash\b|\bmoney\b|\bok\b|安全|撑|现金|钱够"),
)

_HORIZON = re.compile(r"(\d{1,3})\s*(days?|weeks?|months?|天|周|个月|月)", re.IGNORECASE)


def question_of(user: str) -> str:
    i, j = user.find(OPEN_Q), user.rfind(CLOSE_Q)
    return user[i + len(OPEN_Q):j].strip() if i >= 0 and j > i else ""


def tools_of(system: str) -> dict[str, dict[str, Any]]:
    """The catalogue the prompt lists: name -> slot properties."""
    try:
        cat = json.loads(system.split("Tool catalogue (JSON):\n", 1)[1])
    except (IndexError, ValueError):
        return {}
    return {t["name"]: t.get("parameters", {}).get("properties", {}) for t in cat}


def horizon(q: str) -> int | None:
    m = _HORIZON.search(q)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    days = n * 30 if unit.startswith("month") or unit in ("个月", "月") else n * 7 if unit.startswith("week") or unit == "周" else n
    return days if 1 <= days <= 365 else None


def fake_route(system: str, user: str) -> dict[str, Any]:
    q = question_of(user)
    tools = tools_of(system)
    calls: list[dict[str, Any]] = []
    for name, pat in KEYWORDS:
        if name in tools and re.search(pat, q, re.IGNORECASE) and len(calls) < 3:
            slots: dict[str, Any] = {}
            if "horizon_days" in tools[name] and (h := horizon(q)) is not None:
                slots["horizon_days"] = h
            calls.append({"tool": name, "slots": slots})
    return {"calls": calls, "none": not calls}


def fake_complete(system: str, user: str, schema: dict[str, Any]) -> str:
    return json.dumps(fake_route(system, user), ensure_ascii=False)
