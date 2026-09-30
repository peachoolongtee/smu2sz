from __future__ import annotations

import pytest

from app.counterparties import BuyerDecision, BuyerKernel
from app.counterparties.verbaliser import (
    LANGS,
    Clause,
    PublicMessageFields,
    ReplyKind,
    render,
    verbalise,
)
from tests.counterparties.builders import option_a

COUNTER_FIELDS = PublicMessageFields(
    kind=ReplyKind.COUNTER,
    round=1,
    labels=["Option A", "Option B"],
    clauses=[
        Clause(
            key="early_settlement",
            params={"receivable": "RCV-A", "face": "¥420,000.00", "day": "2", "rate": "1.15%"},
        ),
        Clause(key="terms", params={"days": "60"}),
        Clause(key="rebate", params={"rate": "0.50%", "base": "¥400,000.00"}),
    ],
)


@pytest.mark.parametrize("kind", list(ReplyKind))
@pytest.mark.parametrize("lang", LANGS)
def test_every_reply_kind_renders_in_both_languages(kind: ReplyKind, lang: str) -> None:
    fields = COUNTER_FIELDS.model_copy(update={"kind": kind, "round": 2})
    text = render(fields, lang).text  # type: ignore[arg-type]
    assert text
    assert ("Round 2" in text) if lang == "en" else ("第2轮" in text)


def test_counter_renders_en_and_zh_with_exact_clause_spans() -> None:
    en, zh = render(COUNTER_FIELDS, "en"), render(COUNTER_FIELDS, "zh")
    assert en.text == (
        "Round 1. We have considered Option A or Option B and cannot accept as proposed. We propose: "
        "early settlement of invoice RCV-A (¥420,000.00) on day 2 at a 1.15% discount; "
        "60-day payment terms on future invoices; "
        "a 0.50% rebate on next quarter's purchases of up to ¥400,000.00."
    )
    assert zh.text == (
        "第1轮。我方已考虑方案A或方案B，无法按此接受。我方提议："
        "第2天提前结算发票RCV-A（¥420,000.00），折扣1.15%；今后发票账期60天；"
        "下季度采购（上限¥400,000.00）返利0.50%。"
    )
    assert [en.text[s:e] for s, e in en.clause_spans][1] == "60-day payment terms on future invoices"
    assert [zh.text[s:e] for s, e in zh.clause_spans][1] == "今后发票账期60天"


def test_kernel_reply_is_bilingual() -> None:
    r = BuyerKernel().respond("BUYER-1-HARDLINE", option_a(), 1)
    assert r.reply_en.startswith("Round 1.") and "We propose:" in r.reply_en
    assert r.reply_zh.startswith("第1轮。") and "我方提议：" in r.reply_zh
    assert r.verbaliser == "template"


def test_hook_rephrasing_that_keeps_every_clause_is_used_with_recomputed_spans() -> None:
    base = render(COUNTER_FIELDS, "en")
    clauses = [base.text[s:e] for s, e in base.clause_spans]

    def hook(fields: PublicMessageFields, lang: str) -> str:
        if lang != "en":
            return render(fields, "zh").text
        return "Round 1. Thanks. Here is where we are: " + ", and ".join(clauses) + "."

    out = verbalise(COUNTER_FIELDS, "en", hook)
    assert out.source == "hook"
    assert [out.text[s:e] for s, e in out.clause_spans] == clauses

    r = BuyerKernel(verbaliser_hook=hook).respond("BUYER-1-HARDLINE", option_a(), 1)
    assert r.verbaliser == "hook" and r.decision is BuyerDecision.COUNTER
    for o in r.obligations:
        for s in o.spans:
            assert r.reply(s.doc_id.rsplit(":", 1)[1])[s.start : s.end] == s.text  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bad",
    [
        lambda f, lang: render(f, lang).text + " Our floor is 0.80%.",  # new number
        lambda f, lang: "Round 1. We propose something else.",  # drops the clauses
        lambda f, lang: 42,  # not text
        lambda f, lang: "",  # empty
    ],
)
def test_hook_output_outside_the_fence_falls_back_to_the_template(bad) -> None:  # type: ignore[no-untyped-def]
    out = verbalise(COUNTER_FIELDS, "en", bad)
    assert out == render(COUNTER_FIELDS, "en")


def test_a_failing_hook_never_changes_the_decision() -> None:
    def boom(fields: PublicMessageFields, lang: str) -> str:
        raise RuntimeError("model unavailable")

    plain = BuyerKernel().respond("BUYER-1-HARDLINE", option_a(), 1)
    hooked = BuyerKernel(verbaliser_hook=boom).respond("BUYER-1-HARDLINE", option_a(), 1)
    assert plain == hooked
