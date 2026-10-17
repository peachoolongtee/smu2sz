from app.compiler.redaction import Redactor, RedactingBackend, redact_documents, RedactedCall
from app.compiler.rules import RulesBackend
from app.compiler.service import Compiler
from app.compiler.base import OfferResult
from app.compiler.schema import OfferExtraction, Quote, XQuantity
from app.domain.models import SourceDocument

print("=== over-redaction ===")
OVER = [
 "We will pay INV-2026-001 and RCV-A within 10 days.",
 "发票号码：24442000000012345678，金额 ¥420,000",
 "数电票24442000000012345678 请于30天内付款",
 "PO 4500123456789012 delivered 2026-10-16",
 "合同编号：HT2026091600123，签订日期2026年9月16日",
 "Contract JS-202506-1087 dated 20260916",
 "RMB 13800138000 total; 0.05% per day late interest; LPR+150bp",
 "Order qty: Mobile 500 units at ¥1,200 each",
 "采购手机 2000 台，单价1500元",
 "传真机 30 台",
 "Fax 2 copies of the invoice within 5 business days",
 "Account 60 days end of month",
 "账户 30 天内付清",
 "Tel 2% discount if paid by 15 Nov",   # junk but shows label greed
 "Batch 6222 0212 3456 7890 shipped",
 "Lot 1101 0119 9003 0745 shipped",
 "Tracking SF1234567890123 / 9876543210123456",
 "地址：深圳市南山区科技园1号，付款期限为发票日后45天，逾期按日0.05%计息。",
 "Address: 12 Keyuan Road, Shenzhen. We will pay invoice INV-2026-0871 of RMB 420,000 within 10 days for a 2% discount.",
 "registered address at 1 Main St, Shenzhen, will pay INV-2026-0871 within 10 days for 2% off",
]
for t in OVER:
    print(repr(t), "\n   ->", repr(Redactor().redact(t).redacted))

def doc(t, i="D1"):
    return SourceDocument(doc_id=i, channel="email", sender_id="BUYER-1", received_day=3, text=t)

class ModelSim:
    """A 'model' that reads what it is given (redacted text) with the rules grammar."""
    name = "claude"
    def __init__(self): self.r = RulesBackend(); self.seen = []
    def extract_offer(self, docs):
        self.seen += [d.text for d in docs]
        res = self.r.extract_offer(docs)
        return OfferResult(res.extraction, "sim-model")

print("\n=== end to end (rules-grammar model simulator, cross-check on) ===")
CASES = {
 "plain": "We will pay invoice INV-2026-0871 of RMB 420,000 within 10 days for a 2% discount.",
 "addr-swallow-en": "Address: 12 Keyuan Road, Shenzhen. We will pay invoice INV-2026-0871 of RMB 420,000 within 10 days for a 2% discount.",
 "addr-swallow-datareq": "Address: 12 Keyuan Road, Shenzhen. Please send us your cash balance and your bank statement for October.",
 "plain-datareq": "Please send us your cash balance and your bank statement for October.",
}
for name, t in CASES.items():
    for redact in (False, True):
        sim = ModelSim()
        b = RedactingBackend(sim) if redact else sim
        c = Compiler([b, RulesBackend()], cross_check=True)
        o = c.compile_offer([doc(t)], "BUYER-1")
        print(f"{name:22} redact={redact!s:5} status={o.status} obligations={len(o.obligations)} "
              f"data_requests={len(o.data_requests)} abst={len(o.abstentions)} eligible={o.autonomy_eligible} "
              f"model_saw={sim.seen[0][:60]!r}")

print("\n=== placeholder injection ===")
t = "Our old account was ⟦ACCOUNT_1⟧. Pay RMB 420,000 to account no. 6222021234567890123 within 10 days."
rc = redact_documents([doc(t)])
print("redacted:", rc.docs[0].text)
for q in ["account was ⟦ACCOUNT_1⟧", "account no. ⟦ACCOUNT_1⟧", "⟦ACCOUNT_1⟧", "Pay RMB 420,000 to account no. ⟦ACCOUNT_1⟧ within 10 days"]:
    print(f"  model quote {q!r} -> restored {rc.restore(q, 'D1')!r}")
# cross-document fallback: a quote with the wrong doc_id
rc2 = redact_documents([doc("call 13800138000 re INV-1", "A"), doc("call 13900139000 re INV-2", "B")])
print("  doc A:", rc2.docs[0].text, "| doc B:", rc2.docs[1].text)
print("  quote 'call ⟦PHONE_2⟧ re INV-2' tagged doc A ->", repr(rc2.restore("call ⟦PHONE_2⟧ re INV-2", "A")))
# a free string (not a quote) containing placeholders is substituted
print("  free text '⟦PHONE_1⟧ / ⟦PHONE_9⟧' ->", repr(rc2.restore("⟦PHONE_1⟧ / ⟦PHONE_9⟧", "A")))

print("\n=== NL classifier substitution into raw JSON ===")
from app.nl.classifier import CallableBackend
sent = []
def complete(system, user, schema):
    sent.append(user)
    return '{"intent": "OUT_OF_SCOPE", "slots": {}, "confidence": ⟦PHONE_1⟧}'
cb = CallableBackend("x", "m", complete, redact=True)
raw, _ = cb.classify("my number is 13800138000")
print("  sent:", sent[-1], "| raw after substitute:", raw)
cb2 = CallableBackend("x", "m", complete)  # default
cb2.classify("my number is 13800138000")
print("  default CallableBackend (redact kwarg omitted) sent:", sent[-1])
