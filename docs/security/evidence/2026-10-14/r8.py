from app.compiler.service import Compiler
from app.compiler.rules import RulesBackend
from app.compiler.base import OfferResult
from app.compiler.schema import OfferExtraction, XObligation, Quote
from app.domain.models import SourceDocument
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.verifier import evaluate as verify
rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex()); rt.reset()
TEXT = ("We will pay invoice RCV-A of ¥420,000 early at 0.5% on day 2, and in return your firm grants us exclusive "
        "supply rights and ships us a free pallet of stock every month.")
doc = SourceDocument(doc_id="M1", channel="chat", sender_id="BUYER-1", received_day=0, text=TEXT)
def ob(quote):
    return XObligation(type="IMMEDIATE_DISCOUNT", quotes=[Quote(doc_id="M1", text=quote)], rate_text="0.5%", amount_text=None,
        base_kind="INVOICE", base_amount_text="¥420,000", events_per_year_text=None, target_terms_text=None, current_terms_text=None,
        contingency="FIRM", duration_kind="ONE_OFF", bounded_invoices_text=None, confidence=0.99, unresolved=[])
class Stub:
    name = "stub"
    def __init__(self, q): self.q = q
    def extract_offer(self, docs):
        return OfferResult(OfferExtraction(obligations=[ob(self.q)], quantities=[], unresolved_references=[], missing_material=[],
                                           data_requests=[], authority_claims=[], funding_claims=[]), "stub-model")
st, md = rt.store.get_state(), rt.store.get_mandate()
for name, comp in [("rules", Compiler([RulesBackend()])),
                   ("model narrow quote", Compiler([Stub("We will pay invoice RCV-A of ¥420,000 early at 0.5% on day 2")])),
                   ("model WIDE quote (whole msg)", Compiler([Stub(TEXT)]))]:
    o = comp.compile_offer([doc], "BUYER-1")
    b = verify(o, st, md, trusted_owner_key_hex=rt.owner_key_hex, day=0, owner_declared={}, commitments=[])
    print(f"{name:30} status={o.status} eligible={o.autonomy_eligible} outcome={b.verdict.outcome.value} tier={b.verdict.required_tier.value} notes={o.autonomy_notes[:2]}")
