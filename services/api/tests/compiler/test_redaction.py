"""Privacy before the model (app/compiler/redaction.py): a model backend never receives the identifiers FLOW does not
read, the quotes it returns ground to the same spans of the original as without redaction, and the recorded readings
are still found by the original text."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

import pytest
import structlog

from app.compiler import Compiler
from app.compiler.backends import ClaudeBackend, DeepSeekBackend
from app.compiler.base import ContractResult, OfferResult, TermSheetResult
from app.compiler.cache import CACHE_MODEL_ID, CacheBackend
from app.compiler.contract import contract_document
from app.compiler.grounding import locate
from app.compiler.record_cache import contract_documents
from app.compiler.redaction import CLOSE, OPEN, RedactingBackend, Redactor, redact_documents
from app.compiler.rules import RulesBackend
from app.compiler.schema import OfferExtraction, Quote, XAuthorityClaim, XQuantity
from app.compiler.service import default_backends
from app.config import Settings, get_settings
from app.domain.fixtures import load_offers, offer_documents
from app.domain.models import DocumentKind, SourceDocument
from app.nl import classifier

USCC = "91440300MA5F8K2L3X"
USCC_DIGITS = "914403007285123456"
ACCOUNT = "4420 1500 0000 5123 4567"
ACCOUNT_BARE = "6222021234567890123"
LANDLINE = "0755-86123456"
MOBILE = "138 2345 6789"
MOBILE_BARE = "13912345678"
EMAIL = "finance@nanshan-precision.cn"
NATIONAL_ID = "440305199001011234"
ADDRESS = "深圳市南山区科技园南区高新南七道18号创维大厦A座1201室"
EN_ADDRESS = "Room 1203, Tower A, 88 Example Road, Nanshan District, Shenzhen"
EN_PHONE = "+86 755 2345 6789"
EN_EMAIL = "ap@foshan-retail.example.com"

ZH_CONTRACT = f"""采购合同
合同编号：JS-202506-1087
甲方（买方）：深圳市南山精密制造有限公司
统一社会信用代码：{USCC}
住所：{ADDRESS}
法定代表人：王建国  联系电话：{LANDLINE}  手机：{MOBILE}
乙方（卖方）：东莞市长安五金制品有限公司
统一社会信用代码：{USCC_DIGITS}
委托代理人身份证号：{NATIONAL_ID}
一、合同总价为人民币474,450.00元（大写：肆拾柒万肆仟肆佰伍拾元整）。
二、付款方式：甲方于收到发票后60天内付清全部货款，提前付款享受1.2%的折扣。
三、乙方收款账户：开户银行：中国建设银行深圳科技园支行；账户名称：东莞市长安五金制品有限公司；账号：{ACCOUNT}。
四、联系人邮箱：{EMAIL}；备用手机 {MOBILE_BARE}；对公卡号 {ACCOUNT_BARE}。
五、本合同自2025年6月1日起生效，有效期十二（12）个月。发票号码：25442000000123456789。
"""

EN_CONTRACT = f"""SUPPLY AGREEMENT No. FHR-2026-07
Buyer: Foshan Home Retail Co.
Registered Address: {EN_ADDRESS}
Tel: {EN_PHONE}  Email: {EN_EMAIL}
1. The Contract Price is RMB 474,450.00 (four hundred seventy-four thousand four hundred and fifty yuan).
2. The Buyer shall pay within forty-five (45) days after the Invoice Date, with a 2% discount if paid within 10 days.
3. Payment to Account No. {ACCOUNT_BARE} at Bank of China, Foshan Branch.
4. Invoice INV-2025-0612 dated 1 September 2026 is due on 16 October 2026.
"""

SECRETS = [USCC, USCC_DIGITS, ACCOUNT, ACCOUNT_BARE, LANDLINE, MOBILE, MOBILE_BARE, EMAIL, NATIONAL_ID, ADDRESS,
           EN_ADDRESS, EN_PHONE, EN_EMAIL]
KEPT = ["JS-202506-1087", "474,450.00", "1.2%", "60天", "2025年6月1日", "十二（12）个月", "25442000000123456789",
        "深圳市南山精密制造有限公司", "东莞市长安五金制品有限公司", "中国建设银行深圳科技园支行", "FHR-2026-07",
        "Foshan Home Retail Co.", "RMB 474,450.00", "forty-five (45) days", "2%", "INV-2025-0612", "1 September 2026",
        "16 October 2026", "Bank of China, Foshan Branch"]


def _doc(text: str, doc_id: str = "D1") -> SourceDocument:
    return SourceDocument(doc_id=doc_id, channel="email", sender_id="BUYER-1", received_day=3, text=text)


class Recording:
    """A fake model: records every document it receives and reads it with the rules grammar, so its quotes are quotes of
    what it was given (the redacted text)."""

    def __init__(self, name: str = "claude") -> None:
        self.name = name
        self.seen: list[str] = []
        self.rules = RulesBackend()

    def extract_offer(self, docs: Sequence[SourceDocument]) -> OfferResult:
        self.seen += [d.text for d in docs]
        return self.rules.extract_offer(docs)

    def extract_term_sheet(self, doc: SourceDocument) -> TermSheetResult:
        self.seen.append(doc.text)
        return self.rules.extract_term_sheet(doc)

    def extract_contract(self, chunk: SourceDocument) -> ContractResult:
        self.seen.append(chunk.text)
        return self.rules.extract_contract(chunk)


class Scripted(Recording):
    """A fake model that answers with a fixed extraction written against the redacted text."""

    def __init__(self, extraction: OfferExtraction) -> None:
        super().__init__()
        self.extraction = extraction

    def extract_offer(self, docs: Sequence[SourceDocument]) -> OfferResult:
        self.seen += [d.text for d in docs]
        return OfferResult(self.extraction, "fake-model")


# ---------------------------------------------------------------- what is redacted, what is kept


@pytest.mark.parametrize("text", [ZH_CONTRACT, EN_CONTRACT], ids=["zh", "en"])
def test_identifiers_are_replaced_and_terms_are_kept(text: str) -> None:
    red = Redactor().redact(text)
    for s in SECRETS:
        assert s not in red.redacted
    for k in KEPT:
        assert (k in text) == (k in red.redacted), k
    for sg in red.segments:  # every placeholder stands for exactly the identifier it replaced
        assert red.redacted[sg.r_start:sg.r_end] == sg.placeholder


def test_kinds_and_counts_zh() -> None:
    r = Redactor()
    r.redact(ZH_CONTRACT)
    assert dict(r.counts) == {"USCC": 2, "ADDRESS": 1, "PHONE": 3, "NATIONAL_ID": 1, "ACCOUNT": 2, "EMAIL": 1}


def test_kinds_and_counts_en() -> None:
    r = Redactor()
    r.redact(EN_CONTRACT)
    assert dict(r.counts) == {"ADDRESS": 1, "PHONE": 1, "EMAIL": 1, "ACCOUNT": 1}


def test_placeholders_are_stable_per_value() -> None:
    r = Redactor()
    a = r.redact(f"账号：{ACCOUNT}，电话：{LANDLINE}").redacted
    b = r.redact(f"请再次确认账号：{ACCOUNT}").redacted
    assert a == f"账号：{OPEN}ACCOUNT_1{CLOSE}，电话：{OPEN}PHONE_1{CLOSE}"
    assert b == f"请再次确认账号：{OPEN}ACCOUNT_1{CLOSE}"


@pytest.mark.parametrize("text", [
    "合同编号：JS-202506-1087", "Contract JS-202506-1087 is renewed.", "合同总价为人民币474,450.00元",
    "Pay RMB 474,450.00 by 2026-10-16.", "invoice INV-2025-0612 for ¥420,000", "2025年6月1日签订",
    "a 1.2% discount for payment within 10 days", "发票号码：25442000000123456789", "发票代码 044031900111",
    "Invoice No. 1234567890123456", "order number 13800138000", "¥13800138000", "13800138000元",
    "PO-2025-000123-4567", "dated 20250601", "rate 3.85% per annum, 365 days", "LPR+50bp", "第3.2条",
    "quantity 1,000,000 units at ¥4.7445", "上次电话里说好的60天账期", "改一下收货地址", "the account of the Supplier stated on the invoice",
    "收款账户已变更", "账户名称：东莞市长安五金制品有限公司", "Ref 0755-2025",
])
def test_false_positives_are_left_alone(text: str) -> None:
    r = Redactor()
    assert r.redact(text).redacted == text, dict(r.counts)


@pytest.mark.parametrize(("text", "kind"), [
    (f"统一社会信用代码：{USCC}", "USCC"), (f"统一社会信用代码 {USCC_DIGITS}", "USCC"), (f"纳税人识别号：{USCC}", "USCC"),
    (f"账号：{ACCOUNT}", "ACCOUNT"), ("账号：6217 0000 1234 5678 901", "ACCOUNT"), ("银行账号（Account No.）：44201500000051234567", "ACCOUNT"),
    (f"转至 {ACCOUNT_BARE} 即可", "ACCOUNT"), ("card 6222-0212-3456-7890", "ACCOUNT"),
    (f"电话：{LANDLINE}", "PHONE"), ("电话 (0755) 8612 3456", "PHONE"), (f"联系 {LANDLINE} 转财务", "PHONE"),
    (f"手机：{MOBILE}", "PHONE"), (f"请打 {MOBILE_BARE}", "PHONE"), ("call +86 138 2345 6789", "PHONE"),
    ("Phone number 13800138000.", "PHONE"), ("Tel: +65 6123 4567", "PHONE"),
    (f"邮箱：{EMAIL}", "EMAIL"), (f"write to {EN_EMAIL} today", "EMAIL"),
    (f"身份证号：{NATIONAL_ID}", "NATIONAL_ID"), (f"代理人 {NATIONAL_ID} 签字", "NATIONAL_ID"),
    (f"住所：{ADDRESS}", "ADDRESS"), (f"地址：{ADDRESS}，电话：{LANDLINE}", "ADDRESS"),
    (f"Address: {EN_ADDRESS}", "ADDRESS"), ("with its registered office at 88 Example Road, Foshan (the \"Buyer\")", "ADDRESS"),
])
def test_each_kind_is_found(text: str, kind: str) -> None:
    r = Redactor()
    red = r.redact(text)
    assert r.counts[kind] >= 1, red.redacted
    assert f"{OPEN}{kind}_1{CLOSE}" in red.redacted


def test_address_stops_at_the_next_field_and_keeps_the_party() -> None:
    red = Redactor().redact(f"甲方：深圳市南山精密制造有限公司\n住所：{ADDRESS} 法定代表人：王建国\n")
    assert red.redacted == f"甲方：深圳市南山精密制造有限公司\n住所：{OPEN}ADDRESS_1{CLOSE} 法定代表人：王建国\n"
    en = Redactor().redact("ABC Ltd, with its registered address at 1 Harbour Road, Hong Kong and XYZ Co., Ltd.")
    assert "ABC Ltd" in en.redacted and "XYZ Co., Ltd." in en.redacted and "Harbour" not in en.redacted


# ---------------------------------------------------------------- the offset map


@pytest.mark.parametrize("text", [ZH_CONTRACT, EN_CONTRACT], ids=["zh", "en"])
def test_every_span_maps_back_to_the_same_original_span(text: str) -> None:
    """For every span of the original that does not cut an identifier, its redacted counterpart maps back to it, and the
    redacted quote, restored, is the original's own substring at the same offsets."""
    red = Redactor().redact(text)
    rc = redact_documents([_doc(text)])
    cuts = [(sg.o_start, sg.o_end) for sg in red.segments]
    bounds = sorted({0, len(text), *[i for c in cuts for i in c], *[m.start() for m in re.finditer(r"[\s，。；：:]", text)]})
    n = 0
    for i in bounds:
        for j in bounds:
            if j <= i or any(s < i < e or s < j < e for s, e in cuts):
                continue
            rs, re_ = red.to_redacted(i, j)
            assert red.to_original(rs, re_) == (i, j)
            assert red.original[i:j] == rc.redactor.substitute(red.redacted[rs:re_])
            n += 1
    assert n > 1000


def test_a_quote_that_cuts_a_placeholder_widens_to_the_whole_identifier() -> None:
    text = f"乙方账号：{ACCOUNT}，开户行：中国建设银行"
    rc = redact_documents([_doc(text)])
    red = rc.docs[0].text
    cut = red[:red.index("ACCOUNT")]  # "乙方账号：⟦"
    assert rc.restore(cut, "D1") == f"乙方账号：{ACCOUNT}"
    tail = red[red.index("_1") :]  # "_1⟧，开户行：中国建设银行"
    assert rc.restore(tail, "D1") == f"{ACCOUNT}，开户行：中国建设银行"


# ---------------------------------------------------------------- what the backend receives, and grounding


def _offer_text() -> str:
    return (f"From 深圳市南山精密制造有限公司 (统一社会信用代码 {USCC}): for contract JS-202506-1087 we will pay the "
            f"474,450.00 invoice within 10 days if you give us a 2% discount. Reply to {EN_EMAIL} or call {MOBILE_BARE}. "
            f"Remit to 账号：{ACCOUNT}.")


def test_backend_receives_no_identifier_and_quotes_ground_to_the_original() -> None:
    doc = _doc(_offer_text())
    rc = redact_documents([doc])
    red = rc.docs[0].text
    q_offer = red[red.index("for contract"):red.index(" Reply")]
    q_contact = red[red.index("Reply to"):red.index(". Remit")]
    q_cut = red[red.index("Remit"):red.index("ACCOUNT_1")]  # a quote the model cut inside a placeholder
    ex = OfferExtraction(
        obligations=[], unresolved_references=[Quote(doc_id="D1", text=q_offer)], missing_material=[], data_requests=[],
        funding_claims=[],
        quantities=[XQuantity(kind="invoice_amount", doc_id="D1", quote=q_offer, amount_text="474,450.00")],
        authority_claims=[XAuthorityClaim(kind="URGENCY", doc_id="D1", quote=q_contact),
                          XAuthorityClaim(kind="PRE_APPROVAL", doc_id="D1", quote=q_cut)])
    fake = Scripted(ex)
    res = RedactingBackend(fake).extract_offer([doc])
    assert len(fake.seen) == 1
    for s in (USCC, EN_EMAIL, MOBILE_BARE, ACCOUNT):
        assert s not in fake.seen[0]
    for k in ("深圳市南山精密制造有限公司", "JS-202506-1087", "474,450.00", "2%", "10 days"):
        assert k in fake.seen[0]
    got = res.extraction
    by_id = {"D1": doc}
    # the placeholder-free quote is untouched; the others are the original's own words
    assert got.unresolved_references[0].text == q_offer
    assert got.authority_claims[0].quote == f"Reply to {EN_EMAIL} or call {MOBILE_BARE}"
    assert got.authority_claims[1].quote == f"Remit to 账号：{ACCOUNT}"
    # each grounds to the span the offset map gives for the model's redacted quote
    red_map = rc.by_id["D1"]
    for model_q, restored in [(q_offer, got.unresolved_references[0].text), (q_contact, got.authority_claims[0].quote),
                              (q_cut, got.authority_claims[1].quote)]:
        sp = locate(by_id, "D1", restored)
        i = red.index(model_q)
        assert sp is not None and (sp.start, sp.end) == red_map.to_original(i, i + len(model_q))
        assert sp.text == doc.text[sp.start:sp.end]


def _strip_model(o: object) -> object:
    return json.loads(o.model_dump_json(exclude={"compiler"}))  # type: ignore[attr-defined]


@pytest.mark.parametrize("offer_id", sorted(load_offers()))
def test_every_fixture_offer_grounds_identically_through_the_redaction(offer_id: str) -> None:
    """The same reader on the redacted documents and on the original: the same offer, span for span. Each fixture is read
    as recorded and again with identifiers appended to every document, so the redaction has something to do."""
    docs = offer_documents(offer_id)
    if load_offers()[offer_id].get("kind") == "term_sheet":
        pytest.skip("a term sheet, read by compile_term_sheet below")
    for variant in (docs, [d.model_copy(update={"text": d.text + f"\n\n联系电话：{LANDLINE}  邮箱：{EMAIL}  账号：{ACCOUNT}"})
                           for d in docs]):
        fake = Recording()
        redacted = Compiler([RedactingBackend(fake)]).compile_offer(variant, "BUYER-1")
        plain = Compiler([RulesBackend()]).compile_offer(variant, "BUYER-1")
        assert _strip_model(redacted) == _strip_model(plain)
        for text in fake.seen:
            assert LANDLINE not in text and EMAIL not in text and ACCOUNT not in text


@pytest.mark.parametrize("text", [ZH_CONTRACT, EN_CONTRACT], ids=["zh", "en"])
def test_contract_grounds_identically_and_the_model_sees_no_identifier(text: str) -> None:
    doc = contract_document(text, DocumentKind.BUYER_CONTRACT, "BUYER-1")
    fake = Recording()
    redacted = Compiler([RedactingBackend(fake)]).compile_contract(doc)
    plain = Compiler([RulesBackend()]).compile_contract(doc)
    assert fake.seen and all(s not in t for t in fake.seen for s in SECRETS)
    assert _strip_model(redacted) == _strip_model(plain)
    assert redacted.terms, "the contract reads some terms"
    for t in redacted.terms:  # every stored span is the original's own text at its offsets
        assert doc.text[t.span.start:t.span.end] == t.span.text
        assert OPEN not in t.span.text and CLOSE not in t.span.text


def _demo_contracts() -> list[tuple[str, DocumentKind, SourceDocument]]:
    return contract_documents(Path(get_settings().fixture_dir).resolve())


@pytest.mark.parametrize("phone", [EN_PHONE, LANDLINE])
def test_lender_agreements_ground_identically_through_the_redaction(phone: str) -> None:
    for _fid, kind, doc in _demo_contracts():
        if kind != DocumentKind.LENDER_AGREEMENT:
            continue
        doc = doc.model_copy(update={"text": doc.text + f"\nContact: Tel: {phone}, Email: {EN_EMAIL}\n"})
        fake = Recording()
        redacted = Compiler([RedactingBackend(fake)]).compile_term_sheet(doc)
        plain = Compiler([RulesBackend()]).compile_term_sheet(doc)
        assert fake.seen and phone not in fake.seen[0] and EN_EMAIL not in fake.seen[0]
        assert _strip_model(redacted) == _strip_model(plain)


# ---------------------------------------------------------------- the cache, the chain and the setting


@pytest.mark.parametrize("offer_id", sorted(load_offers()))
def test_recorded_offers_replay_and_no_model_is_called(offer_id: str, cache_path: Path) -> None:
    """The redaction wraps the models only: every recorded reading replays by the original text, exactly as before, and the
    model behind the redaction is never called."""
    docs = offer_documents(offer_id)
    fake = Recording()
    live = Compiler([CacheBackend(cache_path), RedactingBackend(fake), RulesBackend()])
    plain = Compiler([CacheBackend(cache_path), RulesBackend()])
    if load_offers()[offer_id].get("kind") == "term_sheet":
        got, want = live.compile_term_sheet(docs[0]), plain.compile_term_sheet(docs[0])
    else:
        got, want = live.compile_offer(docs, "BUYER-1"), plain.compile_offer(docs, "BUYER-1")
    if want.compiler == CACHE_MODEL_ID:
        assert fake.seen == []
    assert got.model_dump() == want.model_dump()


def test_recorded_demo_contracts_replay_and_no_model_is_called(cache_path: Path) -> None:
    for _fid, kind, doc in _demo_contracts():
        fake = Recording()
        live = Compiler([CacheBackend(cache_path), RedactingBackend(fake), RulesBackend()])
        plain = Compiler([CacheBackend(cache_path), RulesBackend()])
        if kind == DocumentKind.LENDER_AGREEMENT:
            got, want = live.compile_term_sheet(doc), plain.compile_term_sheet(doc)
        else:
            got, want = live.compile_contract(doc, kind), plain.compile_contract(doc, kind)
        assert CACHE_MODEL_ID in want.compiler and fake.seen == []
        assert got.model_dump() == want.model_dump()


def test_live_chain_wraps_only_the_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "live")
    chain = default_backends(Settings())
    assert [b.name for b in chain] == ["cache", "claude", "deepseek", "rules"]
    assert isinstance(chain[0], CacheBackend) and isinstance(chain[-1], RulesBackend)
    assert isinstance(chain[1], RedactingBackend) and isinstance(chain[1].inner, ClaudeBackend)
    assert isinstance(chain[2], RedactingBackend) and isinstance(chain[2].inner, DeepSeekBackend)
    monkeypatch.setenv("LLM_REDACT", "0")
    off = default_backends(Settings())
    assert isinstance(off[1], ClaudeBackend) and isinstance(off[2], DeepSeekBackend)


def test_the_cross_check_reads_the_original(monkeypatch: pytest.MonkeyPatch) -> None:
    docs = [_doc(_offer_text())]
    seen: list[str] = []

    class Rules(RulesBackend):
        def extract_offer(self, d):  # type: ignore[no-untyped-def]
            seen.extend(x.text for x in d)
            return super().extract_offer(d)

    fake = Recording()
    fake.rules = RulesBackend()
    res = fake.extract_offer  # a non-cache model id, so the cross-check runs
    fake.extract_offer = lambda d: OfferResult(res(d).extraction, "fake-model")  # type: ignore[method-assign]
    Compiler([RedactingBackend(fake), Rules()], cross_check=True).compile_offer(docs, "BUYER-1")
    assert ACCOUNT not in fake.seen[0] and seen and ACCOUNT in seen[0]


def test_only_counts_are_logged() -> None:
    with structlog.testing.capture_logs() as logs:
        RedactingBackend(Recording()).extract_offer([_doc(_offer_text())])
    ev = [e for e in logs if e["event"] == "model.redaction"]
    assert ev and ev[0]["account"] == 1 and ev[0]["phone"] == 1 and ev[0]["email"] == 1 and ev[0]["uscc"] == 1
    dumped = json.dumps(logs, ensure_ascii=False, default=str)
    for s in (USCC, EN_EMAIL, MOBILE_BARE, ACCOUNT):
        assert s not in dumped


# ---------------------------------------------------------------- the NL classifier


def test_classifier_model_receives_no_identifier() -> None:
    sent: list[str] = []

    def complete(system: str, user: str, schema: dict) -> str:
        sent.append(user)
        return json.dumps({"intent": "EVALUATE_OFFER", "slots": {"counterparty_name": "南山精密"}, "confidence": 0.9})

    text = f"南山精密 发来新报价，联系人电话 {LANDLINE}，邮箱 {EMAIL}，账号：{ACCOUNT}，帮我看看"
    got, _ = classifier.classify(text, [classifier.CallableBackend("claude", "m", complete, redact=True)])
    assert got is not None and got.result.intent == "EVALUATE_OFFER"
    assert sent and all(s not in sent[0] for s in (LANDLINE, EMAIL, ACCOUNT)) and "南山精密" in sent[0]


def test_classifier_default_live_chain_redacts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "live")
    chain = classifier.default_backends()
    assert [b.name for b in chain] == ["cache", "claude", "deepseek"]
    assert all(getattr(b, "redact", False) for b in chain[1:])
    monkeypatch.setenv("LLM_REDACT", "0")
    assert not any(getattr(b, "redact", False) for b in classifier.default_backends()[1:])
