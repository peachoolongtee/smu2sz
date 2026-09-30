"""Grounding: turn an untrusted extraction into typed contracts, or abstain.

- Every quote must be found verbatim in the named document; code computes the offsets. A quote that is
  not found drops its item and records an Abstention.
- Every number is parsed by code from a `*_text` fragment that must sit inside the item's own quotes.
- Obligation ids and the offer id are derived deterministically from the documents.
- Model-written free text never reaches a contract: abstention reasons are fixed templates, lender
  names must be document substrings, and `unresolved` keys come from a closed vocabulary.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from fractions import Fraction

from app.compiler import lexicon
from app.compiler.parsing import (
    parse_count,
    parse_days,
    parse_money,
    parse_rate_bp,
    parse_tenor_months,
)
from app.compiler.schema import (
    OfferExtraction,
    TermSheetExtraction,
    XAuthorityClaim,
    XClause,
    XDataRequest,
    XFundingClaim,
    XObligation,
)
from app.domain.models import (
    Abstention,
    AuthorityClaim,
    BaseKind,
    CompiledOffer,
    CompiledTermSheet,
    CompileStatus,
    Contingency,
    Covenant,
    CovenantKind,
    DataRequest,
    DataRequestKind,
    Duration,
    DurationKind,
    Facility,
    FacilityKind,
    FacilityStatus,
    Obligation,
    ObligationBase,
    ObligationType,
    Repayment,
    SourceDocument,
    SourceSpan,
    TermSheetClause,
    UnsolicitedFundingClaim,
)
from app.domain.money import round_half_up

# Obligation types whose rate (or fixed amount) is material: without a grounded value, abstain.
MATERIAL_VALUE_TYPES = {
    ObligationType.IMMEDIATE_DISCOUNT,
    ObligationType.CONTINGENT_REBATE,
    ObligationType.PRICE_ADJUSTMENT,
}
UNSTATED_LEAD_TIME_DAYS = 30  # placeholder on a proposal the owner must confirm; see abstention
DEFAULT_TENOR_MONTHS = 12  # all-in rate basis when the term sheet states no tenor (CompiledTermSheet doc)


# ---------------------------------------------------------------- hashing and ids


def canonical_docs(docs: Sequence[SourceDocument]) -> str:
    return json.dumps([d.model_dump(mode="json") for d in docs], sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def docs_hash(docs: Sequence[SourceDocument]) -> str:
    return hashlib.sha256(canonical_docs(docs).encode("utf-8")).hexdigest()


def offer_id_for(docs: Sequence[SourceDocument]) -> str:
    return f"OFF-{docs_hash(docs)[:12]}"


# ---------------------------------------------------------------- spans


def locate(docs: dict[str, SourceDocument], doc_id: str, quote: str) -> SourceSpan | None:
    """Exact substring search; falls back to whitespace-insensitive matching (the span text is still
    the document's own substring). Returns None if the quote is not in that document."""
    doc = docs.get(doc_id)
    q = quote.strip() if quote else ""
    if doc is None or not q:
        return None
    i = doc.text.find(q)
    if i >= 0:
        return SourceSpan(doc_id=doc_id, start=i, end=i + len(q), text=q)
    tokens = q.split()
    if len(tokens) > 1:
        m = re.search(r"\s+".join(re.escape(t) for t in tokens), doc.text)
        if m:
            return SourceSpan(doc_id=doc_id, start=m.start(), end=m.end(), text=m.group(0))
    return None


def _overlaps(a: SourceSpan, b: SourceSpan) -> bool:
    return a.doc_id == b.doc_id and a.start < b.end and b.start < a.end


def _in_quotes(fragment: str | None, spans: Sequence[SourceSpan]) -> bool:
    return bool(fragment) and any(fragment.strip() in s.text for s in spans)  # type: ignore[union-attr]


# ---------------------------------------------------------------- security flags


def _dedupe(items: list[tuple[str, SourceSpan]]) -> list[tuple[str, SourceSpan]]:
    out: list[tuple[str, SourceSpan]] = []
    for kind, span in items:
        if any(k == kind and _overlaps(span, s) for k, s in out):
            continue
        out.append((kind, span))
    return sorted(out, key=lambda ks: (ks[1].doc_id, ks[1].start, ks[0]))


def ground_data_requests(docs: dict[str, SourceDocument], items: Sequence[XDataRequest], abst: list[Abstention]) -> list[DataRequest]:
    found: list[tuple[str, SourceSpan]] = []
    for it in items:
        sp = locate(docs, it.doc_id, it.quote)
        if sp is None:
            abst.append(Abstention(field="data_request", reason="flag dropped: quote not found verbatim in the document"))
            continue
        found.append((it.kind.value, sp))
    return [DataRequest(kind=DataRequestKind(k), span=s) for k, s in _dedupe(found)]


def ground_authority(docs: dict[str, SourceDocument], items: Sequence[XAuthorityClaim], abst: list[Abstention]) -> list[AuthorityClaim]:
    found: list[tuple[str, SourceSpan]] = []
    for it in items:
        sp = locate(docs, it.doc_id, it.quote)
        if sp is None:
            abst.append(Abstention(field="authority_claim", reason="flag dropped: quote not found verbatim in the document"))
            continue
        found.append((it.kind, sp))
    return [AuthorityClaim(kind=k, span=s) for k, s in _dedupe(found)]  # type: ignore[arg-type]


def ground_funding(docs: dict[str, SourceDocument], items: Sequence[XFundingClaim], abst: list[Abstention]) -> list[UnsolicitedFundingClaim]:
    out: list[UnsolicitedFundingClaim] = []
    for it in items:
        sp = locate(docs, it.doc_id, it.quote)
        if sp is None:
            abst.append(Abstention(field="funding_claim", reason="flag dropped: quote not found verbatim in the document"))
            continue
        if any(_overlaps(sp, o.span) for o in out):
            continue
        doc = docs[it.doc_id]
        name = it.lender_name.strip()
        if not name or name not in doc.text:
            name = doc.sender_id
        amount = parse_money(it.amount_text) if _in_quotes(it.amount_text, [sp]) else None
        rate = parse_rate_bp(it.rate_text) if _in_quotes(it.rate_text, [sp]) else None
        out.append(UnsolicitedFundingClaim(lender_name=name, amount_fen=amount, rate_bp=rate, span=sp))
    return sorted(out, key=lambda f: (f.span.doc_id, f.span.start))


# ---------------------------------------------------------------- obligations


def _ground_obligation(
    docs: dict[str, SourceDocument],
    x: XObligation,
    counterparty_id: str,
    abst: list[Abstention],
) -> tuple[Obligation | None, bool]:
    """Returns (obligation or None, material_abstention)."""
    label = x.type.value
    spans: list[SourceSpan] = []
    for q in x.quotes:
        sp = locate(docs, q.doc_id, q.text)
        if sp is None:
            abst.append(Abstention(field=f"obligation:{label}", reason="obligation dropped: its quote is not found verbatim in the named document"))
            return None, True
        spans.append(sp)
    if not spans:
        abst.append(Abstention(field=f"obligation:{label}", reason="obligation dropped: no source span"))
        return None, True

    unresolved: list[str] = list(dict.fromkeys(x.unresolved))
    confidence = min(max(float(x.confidence), 0.0), 1.0)

    def grounded(fragment: str | None, parse, field: str) -> int | None:  # type: ignore[no-untyped-def]
        nonlocal confidence
        if not fragment:
            return None
        if not _in_quotes(fragment, spans):
            abst.append(Abstention(field=f"{label}.{field}", reason="value dropped: not inside the obligation's quoted evidence", spans=spans))
            confidence = min(confidence, 0.5)
            return None
        v = parse(fragment)
        if v is None:
            abst.append(Abstention(field=f"{label}.{field}", reason="value dropped: not parseable as an exact amount", spans=spans))
            confidence = min(confidence, 0.5)
        return v

    rate_bp = grounded(x.rate_text, parse_rate_bp, "rate_bp")
    amount_fen = grounded(x.amount_text, parse_money, "amount_fen")
    base_amount = grounded(x.base_amount_text, parse_money, "base.amount_fen")
    if x.base_amount_text and base_amount is None:
        unresolved.append("base_amount")
    events = grounded(x.events_per_year_text, parse_count, "base.events_per_year")
    target = grounded(x.target_terms_text, parse_days, "target_terms_days")
    current = grounded(x.current_terms_text, parse_days, "current_terms_days")

    if x.type in MATERIAL_VALUE_TYPES and rate_bp is None and amount_fen is None:
        abst.append(Abstention(field=f"{label}.rate_bp", reason="material field has no grounded span: rate or amount missing", spans=spans))
        return None, True

    days_delta: int | None = None
    if x.type == ObligationType.TERMS_EXTENSION and target is None:
        abst.append(Abstention(field=f"{label}.days_delta", reason="material field has no grounded span: target terms missing", spans=spans))
        return None, True
    if target is not None:
        if current is not None:
            days_delta = target - current
            unresolved = [u for u in unresolved if u != "current_terms_days"]
        elif "current_terms_days" not in unresolved:
            unresolved.append("current_terms_days")

    contingency = x.contingency
    if x.type == ObligationType.CLAIMED_PRIOR_CONCESSION:
        contingency = Contingency.CLAIMED_UNEVIDENCED

    duration = Duration(kind=DurationKind.ONE_OFF)
    if x.duration_kind == DurationKind.RECURRING_BOUNDED:
        n = grounded(x.bounded_invoices_text, parse_count, "duration.invoices")
        if n:
            duration = Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=n)
        else:  # a bound we cannot ground is treated as no bound (conservative)
            duration = Duration(kind=DurationKind.RECURRING_PERPETUAL)
            unresolved.append("end_date")
    elif x.duration_kind == DurationKind.RECURRING_PERPETUAL:
        duration = Duration(kind=DurationKind.RECURRING_PERPETUAL)

    base = ObligationBase(
        kind=x.base_kind,
        amount_fen=base_amount,
        events_per_year=events if x.base_kind == BaseKind.PER_EVENT else None,
    )
    ob = Obligation(
        id="pending",
        type=x.type,
        counterparty_id=counterparty_id,
        rate_bp=rate_bp,
        amount_fen=amount_fen,
        days_delta=days_delta,
        base=base,
        contingency=contingency,
        duration=duration,
        spans=spans,
        confidence=confidence,
        unresolved=list(dict.fromkeys(unresolved)),
    )
    return ob, False


def _same_sentence(docs: dict[str, SourceDocument], a: SourceSpan, b: SourceSpan) -> bool:
    if a.doc_id != b.doc_id:
        return False
    text = docs[a.doc_id].text
    return lexicon.sentence_bounds(text, a.start) == lexicon.sentence_bounds(text, b.start)


def _force_claimed(docs: dict[str, SourceDocument], ob: Obligation, claims: Sequence[AuthorityClaim]) -> Obligation:
    """An obligation stated in the same sentence as a prior-agreement claim ("the 2% rebate we agreed
    last month", "as we already agreed, the 3% rebate applies") is a claimed prior concession, whatever
    the backend called it: it is never booked without ledger evidence."""
    if ob.type == ObligationType.CLAIMED_PRIOR_CONCESSION:
        return ob
    prior = [c.span for c in claims if c.kind == "PRIOR_AGREEMENT"]
    if any(_overlaps(s, p) or _same_sentence(docs, s, p) for s in ob.spans[:1] for p in prior):
        return ob.model_copy(update={"type": ObligationType.CLAIMED_PRIOR_CONCESSION, "contingency": Contingency.CLAIMED_UNEVIDENCED})
    return ob


# ---------------------------------------------------------------- conflicts


def _quantity_conflicts(docs: dict[str, SourceDocument], ex: OfferExtraction, abst: list[Abstention]) -> dict[str, set[int]]:
    by_kind: dict[str, list[tuple[int, SourceSpan]]] = {}
    for q in ex.quantities:
        sp = locate(docs, q.doc_id, q.quote)
        if sp is None or q.amount_text.strip() not in sp.text:
            continue
        v = parse_money(q.amount_text)
        if v is None:
            continue
        lst = by_kind.setdefault(q.kind, [])
        if not any(_overlaps(sp, s) for _, s in lst):
            lst.append((v, sp))
    conflicts: dict[str, set[int]] = {}
    for kind, vals in by_kind.items():
        distinct = {v for v, _ in vals}
        if len(distinct) > 1:
            conflicts[kind] = distinct
            abst.append(Abstention(
                field=f"base.amount_fen:{kind}",
                reason=f"conflicting sources: the documents state {len(distinct)} different values for {kind}",
                spans=[s for _, s in sorted(vals, key=lambda vs: (vs[1].doc_id, vs[1].start))],
            ))
    return conflicts


def _obligation_conflicts(obs: Sequence[Obligation], abst: list[Abstention]) -> bool:
    """Same concession type and base stated with different values in different documents."""
    groups: dict[tuple[str, str], list[Obligation]] = {}
    for o in obs:
        if o.type == ObligationType.CLAIMED_PRIOR_CONCESSION:
            continue
        groups.setdefault((o.type.value, o.base.kind.value), []).append(o)
    conflict = False
    for (t, _), lst in groups.items():
        doc_sets = {o.spans[0].doc_id for o in lst}
        values = {(o.rate_bp, o.days_delta, o.amount_fen) for o in lst}
        if len(doc_sets) > 1 and len(values) > 1:
            conflict = True
            abst.append(Abstention(
                field=f"obligation:{t}",
                reason="conflicting sources: documents state different values for the same concession",
                spans=[o.spans[0] for o in lst],
            ))
    return conflict


# ---------------------------------------------------------------- offers


def build_offer(
    docs: Sequence[SourceDocument],
    counterparty_id: str,
    ex: OfferExtraction,
    compiler_id: str,
    prompt_version: str,
) -> CompiledOffer:
    by_id = {d.doc_id: d for d in docs}
    order = {d.doc_id: i for i, d in enumerate(docs)}
    offer_id = offer_id_for(docs)
    abst: list[Abstention] = []
    material_abstain = False

    # Security flags: the deterministic lexicon always runs and is unioned with the backend's flags.
    lex_dr, lex_ac, lex_fc = lexicon.all_flags(docs)
    data_requests = ground_data_requests(by_id, [*lex_dr, *ex.data_requests], abst)
    authority = ground_authority(by_id, [*lex_ac, *ex.authority_claims], abst)
    funding = ground_funding(by_id, [*lex_fc, *ex.funding_claims], abst)

    built: list[tuple[int, int, Obligation]] = []
    for x in ex.obligations:
        ob, material = _ground_obligation(by_id, x, counterparty_id, abst)
        material_abstain |= material
        if ob is None:
            continue
        # Text that is a funding claim or a data request never becomes an obligation.
        protected = [f.span for f in funding] + [r.span for r in data_requests]
        if any(_overlaps(s, p) for s in ob.spans[:1] for p in protected):
            continue
        ob = _force_claimed(by_id, ob, authority)
        built.append((order[ob.spans[0].doc_id], ob.spans[0].start, ob))

    for m in ex.missing_material:
        sp = locate(by_id, m.doc_id, m.quote)
        if sp is None:
            continue
        if any(_overlaps(sp, s) for _, _, o in built for s in o.spans):
            continue
        material_abstain = True
        abst.append(Abstention(
            field=f"{m.obligation_type.value}.{m.missing_field}",
            reason="material field has no span: a concession is mentioned without its value",
            spans=[sp],
        ))

    seen_refs: list[SourceSpan] = []
    for q in ex.unresolved_references:
        sp = locate(by_id, q.doc_id, q.text)
        if sp is None or any(_overlaps(sp, s) for s in seen_refs):
            continue
        seen_refs.append(sp)
        abst.append(Abstention(
            field="unresolved_reference",
            reason='unresolved reference ("as usual" / "same arrangement"): the terms it points to are not in the documents; nothing booked',
            spans=[sp],
        ))

    conflicts = _quantity_conflicts(by_id, ex, abst)
    built.sort(key=lambda t: (t[0], t[1]))
    obligations: list[Obligation] = []
    conflict_values = set().union(*conflicts.values()) if conflicts else set()
    for n, (_, _, ob) in enumerate(built, start=1):
        upd: dict[str, object] = {"id": f"{offer_id}-O{n}"}
        if ob.base.amount_fen is not None and ob.base.amount_fen in conflict_values:
            upd["base"] = ob.base.model_copy(update={"amount_fen": None})
            upd["unresolved"] = [*ob.unresolved, "base_amount"]
        obligations.append(ob.model_copy(update=upd))
    obligation_conflict = _obligation_conflicts(obligations, abst)

    if conflicts or obligation_conflict:
        status = CompileStatus.CONFLICTING_SOURCES
    elif material_abstain:
        status = CompileStatus.ABSTAINED
    else:
        status = CompileStatus.COMPILED

    return CompiledOffer(
        offer_id=offer_id,
        counterparty_id=counterparty_id,
        doc_ids=[d.doc_id for d in docs],
        received_day=max((d.received_day for d in docs), default=0),
        status=status,
        obligations=obligations,
        abstentions=abst,
        data_requests=data_requests,
        authority_claims=authority,
        funding_claims=funding,
        compiler=compiler_id,
        prompt_version=prompt_version,
    )


# ---------------------------------------------------------------- term sheets

_CLAUSE_FIELD_MAP = {"equity": "covenant"}  # TermSheetClause has no 'equity' field yet (see ICR)
_TIER3_FIELDS = {"guarantee", "collateral", "equity"}
_NEGATED = re.compile(r"\b(?:no|not|without|unsecured|waived?|none)\b|无需|不需要|无须|免", re.IGNORECASE)
_PERIODIC_FEE = re.compile(r"(?:per|every)\s+(?:(?P<d>\d+)\s*days?|month|advance|period)|每(?:月|笔|期)", re.IGNORECASE)
_KIND_LABEL = {
    FacilityKind.CREDIT_LINE: "working-capital / credit line",
    FacilityKind.INVOICE_FINANCING: "invoice financing",
    FacilityKind.BUYER_EARLY_PAY: "buyer early-pay programme",
    FacilityKind.GOV_GUARANTEED_LOAN: "guaranteed loan",
    FacilityKind.EQUIPMENT_TERM_LOAN: "equipment term loan",
    FacilityKind.EQUIPMENT_LEASE: "equipment lease",
    FacilityKind.BANK_ACCEPTANCE_BILL: "bank acceptance bill",
    FacilityKind.EQUITY: "equity",
}


def _covenants(facility_id: str, clauses: Sequence[TermSheetClause]) -> list[Covenant]:
    out: list[Covenant] = []
    for c in clauses:
        if c.field != "covenant":
            continue
        t = c.span.text
        m = re.search(r"(?:DSCR|debt\s+service\s+coverage)[^0-9]{0,25}(\d+(?:\.\d+)?)\s*x?", t, re.IGNORECASE)
        if m:
            out.append(Covenant(
                id=f"{facility_id}-DSCR", facility_id=facility_id, kind=CovenantKind.DSCR_MIN,
                threshold_bp=round_half_up(Fraction(m.group(1)) * 10_000),
                definition="as stated in the term sheet clause (monthly EBITDA / scheduled debt service assumed)",
                formula=f"EBITDA_m / DS_m >= {m.group(1)}",
            ))
        m = re.search(r"(?:leverage|debt\s*/\s*EBITDA)[^0-9]{0,25}(\d+(?:\.\d+)?)\s*x?", t, re.IGNORECASE)
        if m:
            out.append(Covenant(
                id=f"{facility_id}-LEV", facility_id=facility_id, kind=CovenantKind.LEVERAGE_MAX,
                threshold_bp=round_half_up(Fraction(m.group(1)) * 10_000),
                definition="as stated in the term sheet clause (total debt / annualised EBITDA assumed)",
                formula=f"Debt / (12 x EBITDA_m) <= {m.group(1)}",
            ))
        m = re.search(r"clean[- ]?down[^0-9]{0,25}(\d+)\s*(?:consecutive\s+)?days?", t, re.IGNORECASE)
        if m:
            out.append(Covenant(
                id=f"{facility_id}-CD", facility_id=facility_id, kind=CovenantKind.CLEAN_DOWN,
                clean_down_days=int(m.group(1)),
                definition="as stated in the term sheet clause",
                formula=f"zero balance for {m.group(1)} consecutive days per year",
            ))
    return out


def build_term_sheet(doc: SourceDocument, ex: TermSheetExtraction, compiler_id: str, prompt_version: str) -> CompiledTermSheet:
    by_id = {doc.doc_id: doc}
    abst: list[Abstention] = []
    clauses: list[TermSheetClause] = []
    tier3: list[TermSheetClause] = []
    raw: list[tuple[str, XClause, TermSheetClause]] = []

    for c in ex.clauses:
        sp = locate(by_id, doc.doc_id, c.quote)
        if sp is None:
            abst.append(Abstention(field=f"clause:{c.field}", reason="clause dropped: quote not found verbatim in the term sheet"))
            continue
        if c.value_text.strip() not in sp.text:
            abst.append(Abstention(field=f"clause:{c.field}", reason="clause dropped: value not inside its quoted evidence", spans=[sp]))
            continue
        if any(f == c.field and (s.span.start, s.span.end) == (sp.start, sp.end) for f, _, s in raw):
            continue
        fld = _CLAUSE_FIELD_MAP.get(c.field, c.field)
        value = c.value_text.strip() if fld == c.field else f"{c.field}: {c.value_text.strip()}"
        tc = TermSheetClause(field=fld, value_text=value, span=sp)  # type: ignore[arg-type]
        raw.append((c.field, c, tc))
        clauses.append(tc)
        if c.field in _TIER3_FIELDS:
            s0, e0 = lexicon.sentence_bounds(doc.text, sp.start)
            if not _NEGATED.search(doc.text[s0:e0]):
                tier3.append(tc)

    def values(field: str, parse) -> list[int]:  # type: ignore[no-untyped-def]
        vs: list[int] = []
        for f, c, _ in raw:
            if f == field:
                v = parse(c.value_text)
                if v is not None and v not in vs:
                    vs.append(v)
        return vs

    conflict = False
    principal_vals = values("principal", parse_money)
    rate_vals = values("rate", parse_rate_bp)
    tenor_vals = values("tenor", parse_tenor_months)
    lead_vals = values("lead_time", parse_days)
    for name, vs in (("principal", principal_vals), ("rate", rate_vals), ("tenor", tenor_vals), ("lead_time", lead_vals)):
        if len(vs) > 1:
            conflict = True
            abst.append(Abstention(
                field=name, reason=f"conflicting sources: the term sheet states {len(vs)} different values",
                spans=[tc.span for f, _, tc in raw if f == name],
            ))
    principal = principal_vals[0] if principal_vals else None
    rate = rate_vals[0] if rate_vals else None
    tenor = tenor_vals[0] if tenor_vals else None
    lead = lead_vals[0] if lead_vals else None

    upfront_bp: Fraction = Fraction(0)
    periodic_bp: int = 0
    period_days: int | None = None
    for f, c, tc in raw:
        if f != "fee":
            continue
        pm = _PERIODIC_FEE.search(tc.span.text)
        rv = parse_rate_bp(c.value_text)
        mv = parse_money(c.value_text) if rv is None else None
        if pm and rv is not None:
            periodic_bp = rv
            period_days = int(pm.group("d")) if pm.group("d") else 30
        elif rv is not None:
            upfront_bp += rv
        elif mv is not None and principal:
            upfront_bp += Fraction(mv * 10_000, principal)
        else:
            abst.append(Abstention(field="fee", reason="fee not convertible to a rate (no principal stated)", spans=[tc.span]))

    if principal is None:
        abst.append(Abstention(field="principal", reason="material field has no span: principal not stated"))
    if rate is None:
        abst.append(Abstention(field="rate", reason="material field has no span: interest rate not stated"))
    if tenor is None:
        abst.append(Abstention(field="tenor", reason=f"tenor not stated: all-in rate computed on a {DEFAULT_TENOR_MONTHS}-month basis"))

    all_in: int | None = None
    if rate is not None:
        months = tenor or DEFAULT_TENOR_MONTHS
        total = Fraction(rate) + upfront_bp * 12 / months
        if periodic_bp and period_days:
            total += Fraction(periodic_bp * 365, period_days)
        all_in = round_half_up(total)

    lender_name = doc.sender_id
    if ex.lender_name and ex.lender_name.strip() and ex.lender_name.strip() in doc.text:
        lender_name = ex.lender_name.strip()

    for a in [*lexicon.find_authority_claims(doc), *ex.authority_claims]:
        sp = locate(by_id, doc.doc_id, a.quote)
        if sp is None:
            continue
        if any(x.field == f"authority_claim:{a.kind}" and x.spans and _overlaps(x.spans[0], sp) for x in abst):
            continue
        abst.append(Abstention(field=f"authority_claim:{a.kind}", reason="text asserts authority it cannot have; ignored", spans=[sp]))

    facility: Facility | None = None
    if principal is not None and rate is not None and not conflict:
        fid = f"PROPOSED-{docs_hash([doc])[:10]}"
        if lead is None:
            abst.append(Abstention(field="lead_time", reason=f"lead time not stated: placeholder {UNSTATED_LEAD_TIME_DAYS} days until the owner confirms"))
        repayment = Repayment(ex.repayment) if ex.repayment else Repayment.BULLET
        if ex.repayment is None:
            abst.append(Abstention(field="repayment", reason="repayment profile not stated: BULLET assumed until the owner confirms"))
        facility = Facility(
            id=fid,
            name=f"{lender_name} {_KIND_LABEL[ex.facility_kind]} (proposed)",
            kind=ex.facility_kind,
            lender_id=doc.sender_id,
            status=FacilityStatus.NOT_APPLIED,
            owner_approved=False,
            limit_fen=principal,
            rate_bp=rate,
            fee_bp_per_advance=periodic_bp,
            fee_period_days=period_days,
            upfront_fee_bp=round_half_up(upfront_bp),
            lead_time_days=lead if lead is not None else UNSTATED_LEAD_TIME_DAYS,
            term_months=tenor,
            repayment=repayment,
            collateral=any(f == "collateral" for f, _, tc in raw if tc in tier3),
            personal_guarantee=any(f == "guarantee" for f, _, tc in raw if tc in tier3),
            covenants=_covenants(fid, clauses),
            source_note=f"compiled from {doc.doc_id}; proposal only, not in the funding menu until the owner approves",
        )

    if conflict:
        status = CompileStatus.CONFLICTING_SOURCES
    elif principal is None or rate is None:
        status = CompileStatus.ABSTAINED
    else:
        status = CompileStatus.COMPILED
    clauses.sort(key=lambda c: c.span.start)
    tier3.sort(key=lambda c: c.span.start)
    return CompiledTermSheet(
        doc_id=doc.doc_id,
        lender_name=lender_name,
        proposed_facility=facility,
        all_in_rate_bp=all_in,
        clauses=clauses,
        abstentions=abst,
        tier3_clauses=tier3,
        status=status,
        compiler=compiler_id,
        prompt_version=prompt_version,
    )


__all__ = ["build_offer", "build_term_sheet", "canonical_docs", "docs_hash", "locate", "offer_id_for"]
