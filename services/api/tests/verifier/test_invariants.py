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
from app.verifier.counters import counters, money_text
from tests.verifier.conftest import bundle, compiled

VERIFIER = Path(__file__).resolve().parents[2] / "app" / "verifier"
FREE_TEXT_ATTRS = {"text", "value_text", "reason", "filename", "lender_name", "quote"}
SPAN_ATTRS = {"spans", "span"}
FORBIDDEN_IMPORTS = ("app.compiler", "app.counterparties", "app.nl", "app.security", "app.api", "app.operations",
                     "app.persistence")
TEXT_MODULES = ("re", "regex", "string", "difflib", "unicodedata")


def _free_text_reads(source: str, name: str = "<src>") -> list[str]:
    """Every way the verifier could read document or span text. There is no sanctioned exception: target
    terms arrive as `Obligation.target_terms_days`, so the verifier reads no text at all (INVARIANT 2)."""
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name | ast.alias) and "SourceDocument" in (getattr(node, "id", None) or
                                                                         getattr(node, "name", "")):
            offenders.append(f"{name}: references SourceDocument")
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(FORBIDDEN_IMPORTS):
            offenders.append(f"{name}: imports {node.module}")
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in TEXT_MODULES:
            offenders.append(f"{name}: imports text-processing module {node.module}")
        if isinstance(node, ast.Import):
            offenders += [f"{name}: imports {a.name}" for a in node.names
                          if a.name.startswith(FORBIDDEN_IMPORTS) or a.name.split(".")[0] in TEXT_MODULES]
        if isinstance(node, ast.Attribute) and node.attr in FREE_TEXT_ATTRS and isinstance(node.ctx, ast.Load):
            offenders.append(f"{name}:{node.lineno} reads .{node.attr}")
            base = node.value.value if isinstance(node.value, ast.Subscript) else node.value
            if isinstance(base, ast.Attribute) and base.attr in SPAN_ATTRS:
                offenders.append(f"{name}:{node.lineno} reads .{base.attr}[...].{node.attr}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name | ast.Attribute):
            fn = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            consts = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if fn in {"getattr", "attrgetter"} and set(consts) & (FREE_TEXT_ATTRS | SPAN_ATTRS):
                offenders.append(f"{name}:{node.lineno} {fn}(..., {consts})")
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                and node.slice.value in FREE_TEXT_ATTRS:
            offenders.append(f"{name}:{node.lineno} reads [{node.slice.value!r}]")
    return offenders


def test_verifier_never_reads_document_free_text():
    offenders = []
    for path in sorted(VERIFIER.glob("*.py")):
        offenders += _free_text_reads(path.read_text(encoding="utf-8"), path.name)
    assert offenders == []


def test_bind_has_no_span_parser_left():
    source = (VERIFIER / "bind.py").read_text(encoding="utf-8")
    assert "_target_terms_days" not in source and ".spans" not in source


def test_the_free_text_detector_catches_span_reads():
    # The detector itself: every read the verifier used to allow, and the obvious workarounds, are caught.
    for snippet in (
        "def f(ob):\n    return ob.spans[0].text\n",
        "def f(ob):\n    return [sp.text for sp in ob.spans]\n",
        "def f(ob):\n    return getattr(ob.spans[0], 'text')\n",
        "def f(ob):\n    return ob.spans[0].model_dump()['text']\n",
        "import re\n",
        "from operator import attrgetter\nattrgetter('text')\n",
    ):
        assert _free_text_reads(snippet), snippet
    assert any("spans[...].text" in o for o in _free_text_reads("x = ob.spans[0].text\n"))
    assert _free_text_reads("def f(ob):\n    return ob.target_terms_days, ob.spans\n") == []


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
    buyers = yaml.safe_load((FIXTURES / "counterparties" / "buyers.yaml").read_text(encoding="utf-8"))["buyers"]
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
    # The texts the builders write for counters that fail their own re-check on the golden books (EX01's price
    # adjustment, EX06's bounded extensions): never offered, but the same allow-list applies to them.
    for offer_id in ("EX01_PACKAGE", "EX01B_REWORDED", "EX06_THREE_INVOICES"):
        b = bundle(offer_id)
        out += [(b.verdict.offer_id, compiled(offer_id).counterparty_id, c)
                for c in counters(compiled(offer_id), b.verdict, state, mandate, bound=b.bound_obligations)
                if c.label not in {x.label for x in b.verdict.counters}]
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
    # Option A's cost is the engine's posted discount plus the committed plan on books that hold the counter.
    from app.domain.models import Mode
    from app.financial import project
    from app.funding import plan

    a = bundle("EX01_PACKAGE").verdict.counters[0]
    counter_plan = plan(state, a.obligations, mandate, "COMMITTED")
    t = project(state, a.obligations, counter_plan.actions, Mode.CONSERVATIVE, mandate.horizon_days)
    assert t.discounts_posted_fen + t.interest_posted_fen + t.fees_posted_fen == a.supplier_cost_fen
    assert t.discounts_posted_fen + counter_plan.total_cost_fen == a.supplier_cost_fen
    assert evaluate  # imported for the module's public surface
