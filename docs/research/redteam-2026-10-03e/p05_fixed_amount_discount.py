"""A fixed-sum early-payment discount escapes every early-pay check and is accepted autonomously (Tier 1).

The offer schema lets the compiler state an IMMEDIATE_DISCOUNT by its sum (`amount_text`, "¥20,000 off"); grounding
keeps it (it abstains only when both the rate and the sum are missing), the engine posts it, and the executor
settles the invoice on it. But the verifier's early-pay checks all start with `ob.rate_bp is None -> skip`:
  - the mandate cap max_immediate_discount_bp (app/mandate/predicates.py check_immediate_discounts),
  - ADR-0007 test 1 break-even and the APR ceiling (app/verifier/evaluate.py _apr_checks),
  - ADR-0007 tests 2 and 3, cost against the router's plan (_early_pay_legs).

The live compilers (Claude / DeepSeek) are the production path; offline, LLM_MODE=cache replays a recorded extraction
keyed by the documents. This probe records the extraction an LLM returns for the buyer's sentence (one
IMMEDIATE_DISCOUNT with amount_text "¥20,000" on invoice RCV-A, quoted verbatim) into a probe-local cache directory
(FIXTURE_DIR, read only by the compiler) and then sends the sentence on BUYER-1's authenticated channel. As a control,
the same discount stated as a rate (4.76%) is sent too.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LLM_DIR = HERE / "_llm_fixture"
os.environ["FIXTURE_DIR"] = str(LLM_DIR)

from _harness import *  # noqa: E402
from app.compiler.cache import write_entry  # noqa: E402
from app.compiler.prompts import PROMPT_VERSION  # noqa: E402
from app.compiler.schema import OfferExtraction  # noqa: E402
from app.domain.models import SourceDocument  # noqa: E402

YUAN = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
scenario = sys.argv[2] if len(sys.argv) > 2 else "golden_sme"
SUM = f"¥{YUAN:,}"
TEXT = f"We will pay invoice RCV-A (¥420,000) today if you take {SUM} off."
QUOTE = f"pay invoice RCV-A (¥420,000) today if you take {SUM} off"
SID = f"rt5-fixed-sum-{YUAN}"
FEN = YUAN * 100


def record(session_id: str, turns=range(1, 4), day: int = 0) -> None:
    for turn in turns:
        doc = SourceDocument(doc_id=f"NL-{session_id}-t{turn}", channel="chat", sender_id="BUYER-1", received_day=day,
                             text=TEXT)
        ex = OfferExtraction.model_validate({
            "authority_claims": [], "data_requests": [], "funding_claims": [], "missing_material": [],
            "quantities": [], "unresolved_references": [],
            "obligations": [{
                "type": "IMMEDIATE_DISCOUNT", "quotes": [{"doc_id": doc.doc_id, "text": QUOTE}],
                "rate_text": None, "amount_text": SUM, "base_kind": "INVOICE", "base_amount_text": "¥420,000",
                "events_per_year_text": None, "target_terms_text": None, "current_terms_text": None,
                "contingency": "FIRM", "duration_kind": "ONE_OFF", "bounded_invoices_text": None,
                "confidence": 0.9, "unresolved": []}]})
        write_entry(LLM_DIR / "compiler_cache", PROMPT_VERSION, [doc], ex, "simulated-llm", "probe p05")


rt, c = fresh()
if scenario != "golden_sme":
    rt.reset(scenario)
record(SID)
before = snap(rt, "before")
m = rt.store.get_mandate()
print(f"mandate: max_immediate_discount {m.max_immediate_discount_bp} bp, max_apr {m.max_apr_bp} bp")

out = nl(c, BUYER1, TEXT, session_id=SID, actor="COUNTERPARTY")
print("REPLY TO BUYER:", out["reply"])
cms = rt.store.commitments()
for cm in cms:
    v = rt.store.get_verdict(cm.verdict_id)
    print("COMMITMENT", cm.id, cm.status.value, "verdict", v.outcome.value, v.required_tier.value,
          [x.code.value for x in v.violations])
    print("   summary:", v.summary)
    off = rt.store.get_offer(cm.offer_id)
    print("   offer autonomy_eligible", off.autonomy_eligible, off.autonomy_notes, "abstentions",
          [(a.field, a.reason[:80]) for a in off.abstentions])
    for o in cm.obligations:
        print("   ", o.type.value, "rate_bp", o.rate_bp, "amount_fen", o.amount_fen, "on", o.base.receivable_id,
              "face", o.base.amount_fen, "day", o.effective_day)
log = rt.store.operations()
for e in log[before["log_len"]:]:
    print("LOG", e.seq, e.kind, e.result_json[:200])
q = c.get("/approvals/queue", headers=OWNER).json()["approvals"]
for a in q:
    print("OWNER SEES", a["id"], a["status"], "|", a["reason"])
# the owner approves what the verifier presented as clean (no violation, covenants hold)
for a in q:
    if a["status"] == "PENDING":
        d = c.post(f"/approvals/{a['id']}", json={"decision": "APPROVE"}, headers=OWNER).json()["result"]
        print("OWNER APPROVES", a["id"], "->", d["status"], d["message"][:160])
accepted = [x for x in rt.store.commitments() if x.status.value == "ACTIVE"]

# the buyer pays the invoice less the sum on day 1 (inside the promised day)
advance(c, 1)
res = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-sum", "requested_by": "SYSTEM",
                   "receivable_id": "RCV-A", "amount_fen": 42_000_000 - FEN, "bank_reference": "BR-SUM"})
print("RECEIPT day 1:", res["status"], res["message"])
r = next(x for x in rt.store.get_state().receivables if x.id == "RCV-A")
print(f"RCV-A {r.status} settled {r.settled_fen} outstanding {r.outstanding_fen}; commitments "
      f"{[(x.id, x.status.value) for x in rt.store.commitments()]}")
pct = FEN * 10_000 / 42_000_000
days = 32 - 2
apr = (pct / 10_000) / (1 - pct / 10_000) * 365 / days
print(f"the discount: {pct:.0f} bp of the face for paying {days} days early = {apr:.1%} a year "
      f"(mandate: discount cap {m.max_immediate_discount_bp} bp, rate ceiling {m.max_apr_bp / 100:.0f}%)")
v = rt.store.get_verdict(rt.store.commitments()[0].verdict_id)
check("the verdict on the fixed-sum discount carries no early-pay pricing violation at all",
      not any(x.code.value in ("IMMEDIATE_DISCOUNT_EXCEEDED", "DISCOUNT_ABOVE_BREAK_EVEN", "MAX_APR_EXCEEDED",
                               "EARLY_PAY_DEARER_THAN_PLAN", "EARLY_PAY_NOT_NEEDED") for x in v.violations))
check(f"a {pct:.0f} bp discount ({pct / 100:.2f}%, {apr:.1%} a year) above the mandate's "
      f"{m.max_immediate_discount_bp} bp cap is booked and the invoice settled on it",
      bool(accepted) and r.status == "SETTLED")

# control: the same discount stated as a rate
rt2, c2 = fresh()
if scenario != "golden_sme":
    rt2.reset(scenario)
out2 = nl(c2, BUYER1, f"We will pay invoice RCV-A (¥420,000) early at {pct / 100:.2f}%.", session_id="rt5-rate", actor="COUNTERPARTY")
print("CONTROL (rate) REPLY:", out2["reply"])
for cm in rt2.store.commitments():
    print("CONTROL COMMITMENT", cm.id, cm.status.value)
for v in rt2.store.verdicts() if hasattr(rt2.store, "verdicts") else []:
    print("CONTROL VERDICT", v.outcome.value, [x.code.value for x in v.violations])
print("chain", rt2.store.verify_chain())
