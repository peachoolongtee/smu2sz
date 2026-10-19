"""Classify grounded reader values before deciding whether a proposal needs clarification.

Missing is not conflicting: a grounded value from one reader may complete a priced
proposal, but never proves autonomy. Conflicts, missing whole rules terms, ambiguous
pairings and unresolved model scope still hold the entire offer. This deliberately
keeps decisions atomic until targeted clarification has its own state contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from app.domain.models import (
    Abstention,
    BaseKind,
    CompiledOffer,
    CompileStatus,
    Obligation,
    ObligationType,
    SourceSpan,
)

DISAGREE_FIELD = "offer.readers_disagree"
DISAGREE_PREFIX = "readers disagree"
DISAGREE_REASON = f"{DISAGREE_PREFIX}: the model and the rules grammar read this term differently; clarification needed, nothing booked"
DISAGREE_NOTE = "the model's reading and the rules grammar's reading differ on a term"
SINGLE_READER_NOTE = "one-reader fields require owner review; reader agreement does not prove autonomy"
FIELDS = (
    "counterparty_id", "rate_bp", "amount_fen", "days_delta", "target_terms_days", "effective_day",
    "base.kind", "base.amount_fen", "base.receivable_id", "base.events_per_year",
    "duration.kind", "duration.invoices", "duration.end_day", "contingency",
)
FieldOutcome = Literal["both", "model", "rules", "unread", "conflict"]


def _value(o: Obligation, field: str) -> object:
    value: object = o
    for name in field.split("."):
        value = getattr(value, name)
    return value


def _values(o: Obligation) -> tuple[object, ...]:
    return tuple(_value(o, f) for f in FIELDS)


def _unread(value: object) -> bool:
    return value is None or value is BaseKind.UNSPECIFIED


def field_outcomes(model: Obligation, rules: Obligation) -> dict[str, FieldOutcome]:
    """Compare already grounded typed values; never parse wording or use confidence."""
    out: dict[str, FieldOutcome] = {}
    for field in FIELDS:
        m, r = _value(model, field), _value(rules, field)
        if _unread(m) and _unread(r):
            out[field] = "unread"
        elif _unread(r):
            out[field] = "model"
        elif _unread(m):
            out[field] = "rules"
        else:
            out[field] = "both" if m == r else "conflict"
    return out


def _covers(model: Obligation, rules: Obligation) -> bool:
    return model.type == rules.type and "conflict" not in field_outcomes(model, rules).values()


def _pair(model: Sequence[Obligation], rules: Sequence[Obligation]) -> tuple[dict[int, int], list[int]]:
    """Pair once, exact values first. Never guess between repeated clauses.

    A unique compatible pair must also refer to overlapping source spans; equal
    amounts in separate clauses are not evidence that they describe the same term.
    """
    free = set(range(len(model)))
    pairs: dict[int, int] = {}
    missing: list[int] = []
    ordered = sorted(range(len(rules)), key=lambda j: sum(_unread(v) for v in _values(rules[j])))
    for j in ordered:
        r = rules[j]
        candidates = [i for i in sorted(free) if _covers(model[i], r) and any(
            a.doc_id == b.doc_id and max(a.start, b.start) < min(a.end, b.end)
            for a in model[i].spans for b in r.spans)]
        exact = [i for i in candidates if _values(model[i]) == _values(r)]
        choices = exact or candidates
        if len(choices) != 1:
            missing.append(j)
            continue
        i = choices[0]
        free.remove(i)
        pairs[i] = j
    return pairs, missing


def disputed(model: Sequence[Obligation], rules: Sequence[Obligation]) -> dict[ObligationType, tuple[list[Obligation], list[Obligation]]]:
    """Missing/ambiguous/conflicting whole terms, retaining the historical public helper."""
    _, missing = _pair(model, rules)
    out: dict[ObligationType, tuple[list[Obligation], list[Obligation]]] = {}
    for j in missing:
        r = rules[j]
        out.setdefault(r.type, ([m for m in model if m.type == r.type], []))[1].append(r)
    return out


def _spans(*terms: Obligation) -> list[SourceSpan]:
    result: list[SourceSpan] = []
    for term in terms:
        for span in term.spans:
            if not any((s.doc_id, s.start, s.end) == (span.doc_id, span.start, span.end) for s in result):
                result.append(span)
    return result


def _merge(model: Obligation, rules: Obligation) -> Obligation:
    outcomes = field_outcomes(model, rules)
    updates: dict[str, object] = {}
    nested: dict[str, dict[str, object]] = {}
    for field, outcome in outcomes.items():
        if outcome != "rules":
            continue
        if "." in field:
            parent, child = field.split(".")
            nested.setdefault(parent, {})[child] = _value(rules, field)
        else:
            updates[field] = _value(rules, field)
    for parent, values in nested.items():
        updates[parent] = getattr(model, parent).model_copy(update=values)
    updates["field_provenance"] = {f: value for f, value in outcomes.items() if value in {"rules", "model", "both"}}
    updates["spans"] = _spans(model, rules)
    return model.model_copy(update=updates)


def check_against_rules(model: CompiledOffer, rules: CompiledOffer) -> CompiledOffer:
    """Preserve grounded fields for review; never convert absence into disagreement or consent."""
    pairs, missing = _pair(model.obligations, rules.obligations)
    obligations: list[Obligation] = []
    single_reader = False
    for i, term in enumerate(model.obligations):
        if i in pairs:
            term = _merge(term, rules.obligations[pairs[i]])
        else:
            term = term.model_copy(update={"field_provenance": {
                f: "model" for f in FIELDS if not _unread(_value(term, f))}})
        single_reader |= any(v != "both" for v in term.field_provenance.values())
        obligations.append(term)

    found: dict[ObligationType, tuple[list[Obligation], list[Obligation]]] = {}
    for j in missing:
        r = rules.obligations[j]
        found.setdefault(r.type, ([o for o in model.obligations if o.type == r.type], []))[1].append(r)
    # A blank base is not enough to rehabilitate a model that explicitly could not
    # resolve scope/end. Keep the model's own uncertainty, including contradictory text.
    for term in model.obligations:
        if {"scope", "end_date"}.intersection(term.unresolved):
            found.setdefault(term.type, ([term], []))
    if rules.status == CompileStatus.CONFLICTING_SOURCES or model.counterparty_id != rules.counterparty_id:
        for term in [*model.obligations, *rules.obligations]:
            found.setdefault(term.type, ([o for o in model.obligations if o.type == term.type],
                                         [o for o in rules.obligations if o.type == term.type]))

    abstentions = list(model.abstentions)
    for kind, (ours, theirs) in found.items():
        abstentions.append(Abstention(field=f"{DISAGREE_FIELD}.{kind.value}", reason=DISAGREE_REASON,
                                     spans=_spans(*ours, *theirs)))
    status = model.status
    notes = list(model.autonomy_notes)
    if found:
        status = (CompileStatus.CONFLICTING_SOURCES if CompileStatus.CONFLICTING_SOURCES in (model.status, rules.status)
                  else CompileStatus.ABSTAINED)
        notes.append(DISAGREE_NOTE)
    if single_reader:
        notes.append(SINGLE_READER_NOTE)
    return model.model_copy(update={"obligations": obligations, "status": status, "abstentions": abstentions,
                                    "autonomy_eligible": model.autonomy_eligible and not found and not single_reader,
                                    "autonomy_notes": list(dict.fromkeys(notes))})
