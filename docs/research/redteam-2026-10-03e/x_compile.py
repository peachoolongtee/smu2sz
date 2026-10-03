"""Exploration: what the compiler makes of buyer texts (no assertions)."""
import sys

from _harness import *  # noqa
from app.compiler import compile_offer
from app.domain.models import SourceDocument

rt, c = fresh()
texts = sys.argv[1:] or [
    "We'd like 1% off next quarter's purchases of up to ¥400,000.",
    "We'd like a 1% rebate on next quarter's purchases of up to ¥400,000, paid on day 40.",
    "We will pay invoice RCV-A early at 1%.",
    "We will pay invoice RI:BUYER-1:32 early at 1%.",
    "Extend terms on invoice RCV-A to 60 days.",
]
for i, text in enumerate(texts):
    doc = SourceDocument(doc_id=f"X{i}", channel="chat", sender_id="BUYER-1", received_day=0, text=text)
    off = compile_offer([doc], "BUYER-1")
    print("==", text)
    print("  status", off.status, "compiler", off.compiler)
    for o in off.obligations:
        print("  ", o.type.value, "rate", o.rate_bp, "amt", o.amount_fen, "eff", o.effective_day, "base", o.base.kind,
              o.base.receivable_id, o.base.amount_fen, "dur", o.duration.kind.value, o.duration.invoices,
              o.duration.end_day, "cont", o.contingency.value, "dd", o.days_delta, "tt", o.target_terms_days,
              "unres", o.unresolved)
    for a in off.abstentions:
        print("   abst", a.field, a.reason[:100])
