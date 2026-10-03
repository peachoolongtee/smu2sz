"""Exploration: how the offer compiler reads early-pay rates written in unusual forms (no assertions)."""
from _harness import *  # noqa
from app.compiler import compile_offer
from app.domain.models import SourceDocument

fresh()
forms = ["0.15%", "0,15%", "０.１５％", "0.15 %", "15bp", "15 bps", "15 basis points", "1.5‰", "1.5 per mille",
         "千分之一点五", "百分之零点一五", "百分之1.5", "1.5 percent", "one point five percent", "0.0015", "1½%",
         "1.5 %", "1. 5%", "1.5%%", "point five percent", ".5%", "0.5pct", "05%", "1.50%", "1,5 %", "15/1000"]
for i, f in enumerate(forms):
    text = f"We will pay invoice RCV-A (¥420,000) early at {f}."
    doc = SourceDocument(doc_id=f"R{i}", channel="chat", sender_id="BUYER-1", received_day=0, text=text)
    off = compile_offer([doc], "BUYER-1")
    obs = [(o.type.value, o.rate_bp, o.base.receivable_id, o.base.amount_fen) for o in off.obligations]
    print(f"{f!r:24} -> {off.status.value:10} {obs} autonomy={off.autonomy_eligible} "
          f"{[a.field for a in off.abstentions][:3]}")
