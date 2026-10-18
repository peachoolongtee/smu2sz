"""What every router tool shares: the writer, the slot-schema builders, the forecast-horizon note and the customer resolver.

The router's model only picks a tool and copies its slots from the owner's question; it never sees the books. Every tool
here reads the books itself (`app.nl.answers.metrics`), writes its own sentence in English or Chinese (`app.nl.answers.W`)
and writes nothing to the store. A customer slot is free text the model copied; `resolve_customer` matches it against the
registry with the contract parties matcher (`app.contracts.parties`), so a registry name never has to reach the model.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, NamedTuple

from app.contracts.parties import normalise, registry_names, short_name
from app.nl import lexicon as lx
from app.nl.answers import AnswerReply
from app.nl.answers.answers import W
from app.nl.answers.metrics import Reading

ToolFn = Callable[[Any, str, dict[str, Any]], AnswerReply]


class Spec(NamedTuple):
    """One tool as its area module declares it; `app.nl.router.catalogue` turns these into `Tool`s."""

    name: str
    description: str
    slots_schema: dict[str, Any]
    answer: ToolFn


def writer(ctx: Any, lang: str) -> W:
    """The answer writer for one tool call: one reading of the books, in the owner's language."""
    return W(Reading.of(ctx), "zh" if lang == "zh" else "en")


# ================================================================ slot schemas (JSON Schema draft 2020-12)


def obj(properties: Mapping[str, dict[str, Any]] | None = None, required: Sequence[str] = ()) -> dict[str, Any]:
    return {"type": "object", "properties": dict(properties or {}), "required": list(required), "additionalProperties": False}


def integer(description: str, minimum: int, maximum: int) -> dict[str, Any]:
    return {"type": "integer", "minimum": minimum, "maximum": maximum, "description": description}


def text(description: str, max_length: int = 80) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": max_length, "description": description}


def flag(description: str) -> dict[str, Any]:
    return {"type": "boolean", "description": description}


CUSTOMER_DESCRIPTION = ("The customer exactly as the owner wrote it in the question (a name, a short name or a Chinese name). "
                        "Copy the owner's words; never guess or complete a name.")


def customer(required: bool = True) -> dict[str, Any]:
    if required:
        return text(CUSTOMER_DESCRIPTION)
    return text(CUSTOMER_DESCRIPTION + " Omit it when the owner names no customer.")


# ================================================================ the forecast's horizon


def horizon_note(w: W, asked_days: int | None) -> str:
    """When the owner asks further ahead than the forecast runs: the plain sentence that says the answer is on the forecast."""
    r = w.r
    if asked_days is None or asked_days <= r.horizon:
        return ""
    end = r.today + r.horizon
    return w.t(f"FLOW's forecast runs {r.horizon} days, to day {end}, so this answers on those {r.horizon} days, not {asked_days}. ",
               f"FLOW 的预测只覆盖 {r.horizon} 天（到第 {end} 天），以下按这 {r.horizon} 天回答，而不是 {asked_days} 天。")


def with_note(note: str, reply: AnswerReply) -> AnswerReply:
    if not note:
        return reply
    return replace(reply, text=note + reply.text, figures={**reply.figures, "horizon_capped": "yes"})


# ================================================================ customers


@dataclass(frozen=True)
class Resolved:
    """A customer slot resolved against the registry: the one buyer it names, or the candidates to ask between (the
    customers that matched equally well when `ambiguous`, else every customer on the books)."""

    buyer_id: str | None
    candidates: tuple[str, ...]
    ambiguous: bool = False


def _added_short_names(store: Any) -> dict[str, list[str]]:
    """The short names the owner gave customers when adding them (the ADD_CUSTOMER entries); a read of the operations log."""
    from app.api.customers import added_short_names  # an API module: imported lazily

    try:
        return added_short_names(store)
    except Exception:  # noqa: BLE001  the short names are a convenience; the registry names still resolve without them
        return {}


def customer_names(r: Reading) -> dict[str, list[str]]:
    """Registry id -> every name the owner may use for a customer: its registry name, its short form, the short names the
    owner gave it, and its Chinese name (the lexicon's city aliases)."""
    extra = _added_short_names(r.store)
    aliases = lx.counterparty_aliases(r.state)
    out: dict[str, list[str]] = {}
    for c in r.state.counterparties:
        if c.role != "BUYER":
            continue
        names = registry_names(c, extra.get(c.id, ()))
        if (s := short_name(c.name)) and s not in names:
            names.append(s)  # the pages' short form: how the owner names a customer in a question
        names += [a for a in aliases.get(c.id, ()) if not a.isascii() and a not in names]
        out[c.id] = names
    return out


_CJK = re.compile(r"[㐀-鿿豈-﫿]")
_GENERIC = re.compile(r"(?<![a-z0-9])(?:co|company|ltd|limited|inc|corp|corporation|llc|plc|group|the|and|of)(?![a-z0-9])"
                      r"|股份有限公司|有限责任公司|有限公司|公司|集团")


def _inside(short: str, long: str) -> bool:
    """`short` sits in `long` as whole words, and is enough of a name to point at a company (4 characters, or 2 Chinese, once
    the legal-form words are set aside). This is how the owner's own question names a customer: a read, never an act. The
    party check on documents is stricter (REG-2) and does not use it."""
    core = _GENERIC.sub(" ", short)
    if not short or not (len(_CJK.findall(core)) >= 2 or len(core.replace(" ", "")) >= 4):
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(short)}(?![a-z0-9])", long) is not None


def _names_match(said: str, name: str) -> bool:
    s, n = normalise(said), normalise(name)
    return bool(s) and bool(n) and (s == n or _inside(n, s) or _inside(s, n))


def _score(said: str, name: str) -> int:
    """3: the owner's words are this name; 2: they are part of it ("Foshan Home" in "Foshan Home Retail Co."); 1: the name sits
    inside them ("Foshan" in "Foshan's invoice"); 0: no match (the parties matcher's rule: whole words, long enough)."""
    s, n = normalise(said), normalise(name)
    if not s or not n:
        return 0
    if s == n:
        return 3
    if not _names_match(said, name):
        return 0
    return 2 if s in n else 1


def resolve_customer(r: Reading, said: str | None) -> Resolved:
    names = customer_names(r)
    everyone = tuple(names)
    if not said or not said.strip():
        return Resolved(None, everyone)
    scores = {cid: max((_score(said, n) for n in ns), default=0) for cid, ns in names.items()}
    best = max(scores.values(), default=0)
    if best == 0:
        return Resolved(None, everyone)
    top = tuple(cid for cid, s in scores.items() if s == best)
    if len(top) == 1:
        return Resolved(top[0], top)
    return Resolved(None, top, ambiguous=True)


def _or(w: W, parts: list[str]) -> str:
    if w.zh:
        return "还是".join(parts) if len(parts) <= 2 else "、".join(parts[:-1]) + "还是" + parts[-1]
    return " or ".join(parts) if len(parts) <= 2 else ", ".join(parts[:-1]) + " or " + parts[-1]


def _and(w: W, parts: list[str]) -> str:
    if w.zh:
        return "和".join(parts) if len(parts) <= 2 else "、".join(parts[:-1]) + "和" + parts[-1]
    return " and ".join(parts) if len(parts) <= 2 else ", ".join(parts[:-1]) + " and " + parts[-1]


def ask_which_customer(w: W, tool: str, res: Resolved) -> AnswerReply:
    """The reply when a customer slot names no one on the books, or more than one: it asks which, naming only the customers
    the owner already sees on the Deals page (in Chinese, those with a Chinese name; the rest are counted)."""
    if not res.candidates:
        text_ = w.t("There is no customer on your books yet, so I cannot answer that for a customer.",
                    "您的账目中还没有客户，因此无法针对客户回答。")
        return _clarify(w, tool, text_)
    if w.zh:
        known = customer_names(w.r)  # a customer's Chinese name: the owner's own short name for it, or the lexicon's city name
        named = [n for cid in res.candidates if (n := next((a for a in known.get(cid, ()) if not a.isascii()), None))]
        rest = len(res.candidates) - len(named)
        if res.ambiguous:
            # two customers may share a Chinese name (two companies from the same city): then only their count is said
            distinct = not rest and len(set(named)) == len(named)
            text_ = (f"您指的是哪位客户：{_or(w, named)}？请用完整的客户名称再问一次。" if distinct
                     else f"有 {len(res.candidates)} 位客户都符合，请用完整的客户名称再问一次。")
        else:
            named = list(dict.fromkeys(named))
            rest = len(res.candidates) - len(named)
            listed = _and(w, named) + (f"，以及另外 {rest} 位客户" if rest and named else "")
            text_ = (f"您指的是哪位客户？我无法从问题中确定。您的客户有{listed}。" if named
                     else f"您指的是哪位客户？我无法从问题中确定。您的账目中有 {rest} 位客户，请用客户名称再问一次。")
        return _clarify(w, tool, text_)
    full = {c.id: c.name for c in w.r.state.counterparties}
    names = [full.get(cid, "") for cid in res.candidates if full.get(cid)]
    if res.ambiguous:
        text_ = f"Which customer do you mean: {_or(w, names)}? Ask again with the customer's full name."
    else:
        text_ = f"Which customer do you mean? I could not tell from the question. Your customers are {_and(w, names)}."
    return _clarify(w, tool, text_)


def _clarify(w: W, tool: str, text_: str) -> AnswerReply:
    return AnswerReply(text=w.end(text_), metric_ids=[], figures={}, basis=w.basis("books"), question_id=tool, lang=w.lang,
                       extra={"needs": "customer"})


__all__ = ["Resolved", "Spec", "ToolFn", "ask_which_customer", "customer", "customer_names", "flag", "horizon_note", "integer",
           "obj", "resolve_customer", "text", "with_note", "writer"]
