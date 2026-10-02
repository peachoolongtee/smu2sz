from app.api.runtime import Runtime
from app.config import Settings
from app.persistence import InMemoryLedgerStore
from app.domain.fixtures import offer_documents
from app.domain.models import *
from app.mandate import demo_owner_public_key_hex
from app.compiler import compile_offer
from app.verifier import evaluate
from app.financial import project
from app.books import current_books
rt=Runtime(settings=Settings(),store=InMemoryLedgerStore(),owner_key_hex=demo_owner_public_key_hex());rt.reset()
ex=rt.executor
o=compile_offer(offer_documents('EX01_PACKAGE'),'BUYER-1');rt.store.put_offer(o)
b=evaluate(o,rt.store.get_state(),rt.store.get_mandate(),trusted_owner_key_hex=rt.owner_key_hex);rt.store.put_verdict(b.verdict)
ctr=next(c for c in b.verdict.counters if any(ob.type==ObligationType.PRICE_ADJUSTMENT for ob in c.obligations))
print('real counter',ctr.id,ctr.text,[(ob.type.value,ob.rate_bp,ob.duration.kind.value,ob.duration.invoices) for ob in ctr.obligations])
c=ex.propose_commitment(b.verdict.id,expires_day=7,counter_id=ctr.id)
op=AcceptOffer(op_id='acc',idempotency_key='acc',mandate_version=1,requested_by=Actor.AGENT,day=0,offer_id=c.offer_id,offer_version=c.offer_version,terms_hash=c.terms_hash,nonce=c.nonce)
r=ex.execute(op); print('accept',r.status.value,r.message)
if r.approval_id:print('approve',ex.decide(r.approval_id,True,Actor.OWNER).status.value)
rt.advance_to(3);s=rt.store.get_state();bk=current_books(s,rt.store.commitments());t=project(s,list(bk.obligations),[],Mode.CONSERVATIVE,120)
rid='RI:BUYER-1:2';expected=next(e.amount_fen for p in t.days for e in p.events if e.kind==LedgerEventKind.RECEIPT and e.ref==rid)
print('issued face/due',[(r.face_fen,r.due_day) for r in s.receivables if r.id==rid],'projected receipt',[(p.day,e.amount_fen) for p in t.days for e in p.events if e.kind==LedgerEventKind.RECEIPT and e.ref==rid])
receipt=ReceivePayment(op_id='recv',idempotency_key='recv',mandate_version=1,requested_by=Actor.SYSTEM,day=3,receivable_id=rid,amount_fen=expected)
r=rt.executor.execute(receipt);print('agreed cash receipt',r.status.value,r.message)
part=10_000_000
r=rt.executor.execute(ReceivePayment(op_id='part',idempotency_key='part',mandate_version=1,requested_by=Actor.SYSTEM,day=3,receivable_id=rid,amount_fen=part))
s=rt.store.get_state();bk=current_books(s,rt.store.commitments());t=project(s,list(bk.obligations),[],Mode.CONSERVATIVE,120)
remaining=next(e.amount_fen for p in t.days for e in p.events if e.kind==LedgerEventKind.RECEIPT and e.ref==rid)
print('partial',r.status.value,'cash received',part,'correct agreed residual',expected-part,'projected residual',remaining,'economic value lost',expected-part-remaining)
