"""Experiment-only bootstrap adaptation; scored texts/labels and frozen files stay unchanged.

The original bootstrap queues an offer with unresolved 'next week'. Build B now
correctly holds it before pricing, so it cannot create the approval the tests need.
Instead queue the same 30bp whole-invoice discount as an explicitly review-only
proposal. This tests the pending-approval attacks, not date interpretation.
Do not describe these reports as unmodified certification runs.
"""
import hashlib,importlib.util,json,os,sys
from pathlib import Path
ROOT=Path('/Users/ianpong/Hackathons/smu2sz/.claude/worktrees/settlement-interpreter')
sys.path.insert(0,str(ROOT/'services/api'));os.environ.update(TERMSLEDGER_NO_DOTENV='1',DATABASE_URL='memory',DEMO_MODE='1',LLM_MODE='cache')
source=ROOT/'scripts/certify_language_boundary.py'
spec=importlib.util.spec_from_file_location('flow_b_language_harness',source);h=importlib.util.module_from_spec(spec);sys.modules[spec.name]=h;spec.loader.exec_module(h)
original=h.run_setup;adapted=[]
def setup(rt,client,item):
 for step in item['setup']:
  if step!='pending_approval':
   original(rt,client,{**item,'setup':[step]});continue
  from app.compiler import Compiler
  from app.compiler.rules import RulesBackend
  from app.domain.models import AcceptOffer,Actor,SourceDocument
  from app.verifier import evaluate
  doc=SourceDocument(doc_id=item['id']+'-review-setup',channel='chat',sender_id='BUYER-1',received_day=rt.day,text='We can pay the full ¥420,000 invoice early at 0.3% off.')
  offer=Compiler([RulesBackend()]).compile_offer([doc],'BUYER-1').model_copy(update={'autonomy_eligible':False,'autonomy_notes':['experiment bootstrap: explicit owner review required']})
  v=evaluate(offer,rt.store.get_state(),rt.store.get_mandate(),trusted_owner_key_hex=rt.owner_key_hex,day=rt.day).verdict
  assert v.outcome.value=='NEEDS_OWNER_APPROVAL'
  rt.store.put_offer(offer);rt.store.put_verdict(v)
  c=rt.executor.propose_commitment(v.id,expires_day=rt.day+7)
  operation=AcceptOffer(op_id=item['id']+'-setup-accept',idempotency_key=item['id']+'-setup-accept',mandate_version=v.mandate_version,requested_by=Actor.AGENT,day=rt.day,offer_id=offer.offer_id,offer_version=offer.version,terms_hash=c.terms_hash,nonce=c.nonce,source_verdict_id=v.id)
  result=rt.executor.execute(operation)
  assert result.status.value=='PENDING_APPROVAL',result
  assert result.approval_id=='APR-000001',result.approval_id
  adapted.append(item['id'])
h.run_setup=setup
code=h.main()
out=Path(sys.argv[sys.argv.index('--out')+1]);out.mkdir(exist_ok=True,parents=True)
meta={'unmodified_harness_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'fixture_sha256':hashlib.sha256(h.FIXTURE.read_bytes()).hexdigest(),'adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'setup_override':'Pending approval bootstrap only: same 30bp whole-invoice discount, explicitly review-only; original next-week bootstrap cannot price under Build B. All scored texts and labels unchanged. Not an unmodified certification.','affected_setup_items':sorted(set(adapted)),'exit_code':code}
(out/'experiment-adapter.json').write_text(json.dumps(meta,indent=2)+'\n')
raise SystemExit(code)
