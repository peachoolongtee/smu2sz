"""INVARIANT 2 (typed contracts only) and INVARIANT 7 (counters disclose nothing), checked on the code
and on every counter the golden examples produce."""

from __future__ import annotations

import ast
from fractions import Fraction
from pathlib import Path

import yaml

from app.domain.fixtures import FIXTURES
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.funding import break_even_discount, marginal_cost
from app.verifier import evaluate, evaluate_many
from app.verifier.counters import money_text
from tests.verifier.conftest import bundle, compiled

VERIFIER = Path(__file__).resolve().parents[2] / "app" / "verifier"
FREE_TEXT_ATTRS = {"text", "value_text", "reason", "filename", "lender_name", "quote"}
FORBIDDEN_IMPORTS = ("app.compiler", "app.counterparties", "app.nl", "app.security", "app.api", "app.operations",
                     "app.persistence")
# The single sanctioned read: the target terms of a TERMS_EXTENSION, from its own validated span.
ALLOWED_TEXT_READS = {("bind.py", "_target_terms_days")}


def _functions(tree: ast.AST) -> dict[ast.AST, str]:
    """Each node -> the name of the outermost function that contains it."""
    owner: dict[ast.AST, str] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            for node in ast.walk(fn):
                if node is not fn:
                    owner.setdefault(node, fn.name)
    return owner


def test_verifier_never_reads_document_free_text():
    offenders = []
    for path in sorted(VERIFIER.glob("*.py")):
        tree = ast.parse(path.read_text())
        owner = _functions(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name | ast.alias) and "SourceDocument" in (getattr(node, "id", None) or
                                                                             getattr(node, "name", "")):
                offenders.append(f"{path.name}: references SourceDocument")
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(FORBIDDEN_IMPORTS):
                offenders.append(f"{path.name}: imports {node.module}")
            if isinstance(node, ast.Import):
                offenders += [f"{path.name}: imports {a.name}" for a in node.names if a.name.startswith(FORBIDDEN_IMPORTS)]
            if isinstance(node, ast.Attribute) and node.attr in FREE_TEXT_ATTRS and isinstance(node.ctx, ast.Load):
                where = (path.name, owner.get(node, "<module>"))
                if where not in ALLOWED_TEXT_READS:
                    offenders.append(f"{path.name}:{node.lineno} reads .{node.attr} in {where[1]}")
    assert offenders == []


def test_the_sanctioned_span_read_only_parses_days():
    tree = ast.parse((VERIFIER / "bind.py").read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_target_terms_days")
    reads = [n for n in ast.walk(fn) if isinstance(n, ast.Attribute) and n.attr == "text"]
    assert len(reads) == 1 and isinstance(reads[0].value, ast.Name) and reads[0].value.id == "sp"


# ---------------------------------------------------------------- counters disclose nothing


def _money_forms(fen: int) -> set[str]:
    return {fmt_yuan(fen), money_text(fen), f"{fen // 100:,}"}


def _rate_forms(x: Fraction) -> set[str]:
    return {fmt_pct(x), fmt_pct(x, 4), fmt_pct(x, 1)}


def _secrets(state, mandate, counterparty_id: str) -> set[str]:
    out: set[str] = set()
    out |= _money_forms(mandate.min_cash_fen)
    out |= _money_forms(mandate.max_aggregate_forward_concession_fen)
    out |= _money_forms(mandate.tier2_single_commitment_fen)
    for cap in mandate.per_buyer_caps_fen.values():
        out |= _money_forms(cap)
    out |= _rate_forms(bp(mandate.max_apr_bp))
    if mandate.max_immediate_discount_bp is not None:
        out |= _rate_forms(bp(mandate.max_immediate_discount_bp))
    for f in state.facilities:
        if f.limit_fen:
            out |= _money_forms(f.limit_fen)
    rate, _ = marginal_cost(state, mandate)
    out |= _rate_forms(rate.value)
    d, _ = break_even_discount(state, mandate)
    out |= _rate_forms(d.value)
    buyers = yaml.safe_load((FIXTURES / "counterparties" / "buyers.yaml").read_text())["buyers"]
    for p in buyers:
        if p["counterparty_id"] != counterparty_id:
            continue
        for k in ("min_early_pay_discount_bp", "min_rebate_bp", "funding_cost_bp"):
            if p[k]:
                out |= _rate_forms(bp(p[k]))
        for k in ("min_surplus_fen", "payment_day_value_fen"):
            if p[k]:
                out |= _money_forms(p[k])
    return {s for s in out if s not in {"0", "0%"}}


def _all_counters(state, mandate, key):
    out = []
    for offer_id in ("EX01_PACKAGE", "EX01B_REWORDED", "EX02_EARLY_1_5", "EX03_AS_USUAL", "EX04_CLAIMED_REBATE",
                     "EX06_THREE_INVOICES"):
        out += [(bundle(offer_id).verdict.offer_id, compiled(offer_id).counterparty_id, c)
                for c in bundle(offer_id).verdict.counters]
    for b in evaluate_many([compiled("EX08A_JOINT_BUYER1"), compiled("EX08B_JOINT_BUYER2")], state, mandate,
                           trusted_owner_key_hex=key):
        out += [(b.verdict.offer_id, "", c) for c in b.verdict.counters]
    for b in evaluate_many([compiled("EX08B_JOINT_BUYER2"), compiled("EX08A_JOINT_BUYER1")], state, mandate,
                           trusted_owner_key_hex=key):
        out += [(b.verdict.offer_id, "", c) for c in b.verdict.counters]
    return out


def test_counter_text_never_discloses_protected_values(state, mandate, key):
    found = _all_counters(state, mandate, key)
    assert len(found) >= 10
    for _, cp, c in found:
        cp = cp or c.obligations[0].counterparty_id
        leaked = [s for s in _secrets(state, mandate, cp) if s in c.text]
        assert leaked == [], (c.label, c.text, leaked)


def test_counter_spans_point_into_the_counter_text(state, mandate, key):
    for _, _, c in _all_counters(state, mandate, key):
        for ob in c.obligations:
            (sp,) = ob.spans
            assert sp.doc_id == c.id and c.text[sp.start:sp.end] == sp.text
            assert ob.unresolved == [] and ob.confidence == 1.0


def test_counter_is_what_it_costs_under_the_engine(state, mandate, key):
    # Option A's cost is the engine's posted discount plus line interest, not a separate formula.
    from app.domain.models import Mode
    from app.financial import project
    from app.verifier.reserve import baseline

    a = bundle("EX01_PACKAGE").verdict.counters[0]
    _, base_plan = baseline(state, mandate)
    line = [x for x in base_plan.actions if x.facility_id == "FAC-LINE"]
    t = project(state, a.obligations, line, Mode.CONSERVATIVE, mandate.horizon_days)
    assert t.discounts_posted_fen + t.interest_posted_fen + t.fees_posted_fen == a.supplier_cost_fen
    assert evaluate  # imported for the module's public surface
