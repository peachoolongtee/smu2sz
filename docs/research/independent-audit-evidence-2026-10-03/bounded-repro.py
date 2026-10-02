from app.api.runtime import Runtime
from app.config import Settings
from app.persistence import InMemoryLedgerStore
from app.domain.models import *
from app.mandate import demo_owner_public_key_hex
from app.compiler import compile_offer
from app.verifier import evaluate
from app.financial import project
from app.books import current_books
rt=Runtime(settings=Settings(),store=InMemoryLedgerStore(),owner_key_hex=demo_owner_public_key_hex());rt.reset()
text="We'd like 50 days on the next 3 invoices instead of 45."
d=SourceDocument(doc_id='BOUND3',channel='chat',sender_id='BUYER-1',received_day=0,text=text)
o=compile_offer([d],'BUYER-1');rt.store.put_offer(o);b=evaluate(o,rt.store.get_state(),rt.store.get_mandate(),trusted_owner_key_hex=rt.owner_key_hex);rt.store.put_verdict(b.verdict)
print('verdict',b.verdict.outcome.value,b.verdict.required_tier.value,[(v.code.value,v.message) for v in b.verdict.violations])
c=rt.executor.propose_commitment(b.verdict.id,expires_day=7)
r=rt.executor.execute(AcceptOffer(op_id='acc',idempotency_key='acc',mandate_version=1,requested_by=Actor.AGENT,day=0,offer_id=c.offer_id,offer_version=c.offer_version,terms_hash=c.terms_hash,nonce=c.nonce))
print('accept',r.status.value)
if r.approval_id:print('approve',rt.executor.decide(r.approval_id,True,Actor.OWNER).status.value)
def receipts():
 s=rt.store.get_state();bk=current_books(s,rt.store.commitments());t=project(s,list(bk.obligations),[],Mode.CONSERVATIVE,220)
 return [(e.ref,p.day) for p in t.days for e in p.events if e.kind==LedgerEventKind.RECEIPT and (e.ref or '').startswith('RI:')]
print('before',receipts())
for day in [3,33,63]:
 rt.advance_to(day);rid=f'RI:BUYER-1:{day-1}'
 r=rt.executor.execute(ReceivePayment(op_id=f'recv{day}',idempotency_key=f'recv{day}',mandate_version=1,requested_by=Actor.SYSTEM,day=day,receivable_id=rid,amount_fen=42000000))
 print('settle',rid,r.status.value)
print('after3',receipts())
