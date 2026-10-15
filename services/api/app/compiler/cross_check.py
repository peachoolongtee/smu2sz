"""Two readers for a buyer message in live mode: a model's reading, checked against the rules grammar's reading of the same
documents, so a term the two read differently is never decided by either alone.

Both readings are grounded the same way (`grounding.build_offer`); they are compared term by term, by the values
`grounding.dedupe_obligations` treats as one term's identity (`_dup_key`) and the contingency:
- a term the rules grammar read is matched by a term of the same type in the model's reading that states the same values.
  A value the rules left unread (no value, or an unspecified base) matches any value: the grammar could not read it, and
  reading what it cannot is what the model is for;
- a term only the model read stands, for the same reason;
- a term the rules read that the model read differently, or did not read at all, is disputed: the offer abstains on it
  (`offer.readers_disagree.<TYPE>`, quoting both readers' passages), it is not eligible for autonomy, nothing is booked on it,
  and the buyer is asked to restate the terms.
The security flags need no check: `build_offer` unions the deterministic lexicon's flags into every reading. A recorded
reading (reviewed when it was recorded) and the rules grammar's own answer are not checked."""

from __future__ import annotations

from collections.abc import Sequence

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


def _values(o: Obligation) -> tuple[object, ...]:
    """One term's values: `grounding._dup_key` without the type, and the contingency."""
    return (o.rate_bp, o.amount_fen, o.days_delta, o.target_terms_days, o.base.kind, o.base.amount_fen, o.base.receivable_id,
            o.base.events_per_year, o.duration.kind, o.duration.invoices, o.contingency)


def _unread(value: object) -> bool:
    return value is None or value is BaseKind.UNSPECIFIED


def _covers(model: Obligation, rules: Obligation) -> bool:
    """The model's term states what the rules' term states, wherever the rules read a value."""
    return model.type == rules.type and all(
        _unread(r) or r == m for m, r in zip(_values(model), _values(rules), strict=True))


def disputed(model: Sequence[Obligation], rules: Sequence[Obligation]) -> dict[ObligationType, tuple[list[Obligation], list[Obligation]]]:
    """By type, the terms the two readings disagree on: (the model's terms of that type, the rules' terms no model term covers).
    Each model term covers one rules term at most; the most completely read rules terms are matched first."""
    free = list(model)
    out: dict[ObligationType, tuple[list[Obligation], list[Obligation]]] = {}
    for r in sorted(rules, key=lambda o: sum(_unread(v) for v in _values(o))):
        match = next((m for m in free if _covers(m, r)), None)
        if match is not None:
            free = [m for m in free if m is not match]
            continue
        out.setdefault(r.type, ([m for m in model if m.type == r.type], []))[1].append(r)
    return out


def check_against_rules(model: CompiledOffer, rules: CompiledOffer) -> CompiledOffer:
    """The model's reading when the rules grammar's reading agrees with it (the same object, unchanged); otherwise the model's
    reading abstaining on each disputed term, with both readers' passages quoted."""
    found = disputed(model.obligations, rules.obligations)
    if not found:
        return model
    abstentions = list(model.abstentions)
    for kind, (ours, theirs) in found.items():
        spans: list[SourceSpan] = []
        for sp in (s for o in (*ours, *theirs) for s in o.spans):
            if not any((x.doc_id, x.start, x.end) == (sp.doc_id, sp.start, sp.end) for x in spans):
                spans.append(sp)
        abstentions.append(Abstention(field=f"{DISAGREE_FIELD}.{kind.value}", reason=DISAGREE_REASON, spans=spans))
    status = (CompileStatus.CONFLICTING_SOURCES if model.status == CompileStatus.CONFLICTING_SOURCES
              else CompileStatus.ABSTAINED)
    return model.model_copy(update={"status": status, "abstentions": abstentions, "autonomy_eligible": False,
                                    "autonomy_notes": [*model.autonomy_notes, DISAGREE_NOTE]})
