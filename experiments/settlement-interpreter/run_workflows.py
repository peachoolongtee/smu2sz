"""In-process HTTP workflow evaluation. No provider or external database calls."""
import argparse, hashlib, json, os, sys, time, subprocess
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--items',required=True);ap.add_argument('--out',required=True);ap.add_argument('--live',action='store_true');ap.add_argument('--include-owner-review',action='store_true');ap.add_argument('--recordings');ap.add_argument('--finalize-recordings',action='store_true');ap.add_argument('--reading',choices=['before','after'],default='before');a=ap.parse_args()
if a.live and not globals().get('_FLOW_CAPPED_PROVIDER_RUN',False):
 raise SystemExit('Live evaluation must run through an explicitly approved capped API wrapper.')
root=Path(a.root);sys.path.insert(0,str(root/'services/api'))
os.environ.update(TERMSLEDGER_NO_DOTENV='1',DATABASE_URL='memory',DEMO_MODE='1',LLM_MODE='live' if a.live else 'cache',OWNER_TOKEN='demo-owner-token',AGENT_KEY='demo-agent-key',BANK_FEED_KEY='demo-bank-feed-key',COUNTERPARTY_KEYS='BUYER-1=demo-buyer-1-key,BUYER-2=demo-buyer-2-key')
from fastapi.testclient import TestClient
from app.api.runtime import Runtime,set_runtime
from app.config import get_settings
from app.persistence import InMemoryLedgerStore
from app.mandate import demo_owner_public_key_hex
from app.main import app
if a.recordings:
 from app.domain.models import CompiledOffer
 import app.api.offers as intake
 recordings=json.loads(Path(a.recordings).read_text())
 def recorded_offer(docs, cp):
  value=recordings[docs[0].doc_id][a.reading]
  assert value['counterparty_id']==cp
  offer=CompiledOffer.model_validate_json(json.dumps(value))
  if a.finalize_recordings:
   from app.compiler.settlement import finalize_reconciled_timing
   offer=finalize_reconciled_timing(docs,offer)
  return offer
 intake.compile_offer=recorded_offer
from evals.common import quiet
quiet()
rows=[]
for item in json.loads(Path(a.items).read_text())['items']:
 start=time.perf_counter(); rt=Runtime(settings=get_settings(),store=InMemoryLedgerStore(),owner_key_hex=demo_owner_public_key_hex());rt.reset();set_runtime(rt)
 c=TestClient(app);owner={'X-Owner-Token':'demo-owner-token'};agent={'X-Agent-Key':'demo-agent-key'}
 before=rt.store.get_state(); before_commitments=len(rt.store.commitments())
 doc={'doc_id':item['id'],'channel':'chat','sender_id':'BUYER-1','received_day':item['received_day'],'text':item['text']}
 r=c.post('/offers',json={'counterparty_id':'BUYER-1','documents':[doc]},headers={'X-Counterparty-Key':'demo-buyer-1-key'});assert r.status_code==200,r.text
 offer=r.json()['offer'];oid=offer['offer_id']
 ev=c.post(f'/offers/{oid}/evaluate',json={},headers=owner);assert ev.status_code==200,ev.text
 v=ev.json();bound=v['bound_obligations'];date=next((ob.get('effective_day') for ob in bound if ob['type']=='IMMEDIATE_DISCOUNT'),None)
 # Intake and evaluation must never mutate financial state.
 unchanged=rt.store.get_state()==before and len(rt.store.commitments())==before_commitments
 tier1=v['outcome']=='ACCEPT' and v['required_tier']=='TIER_1' and not (v.get('plan') or {}).get('needs_owner_approval',False)
 execution=None;received=None;promise_cash_unchanged=True;correct_commitment=None;receipt_ok=None;owner_outcome=None;receipt_delta=0
 owner_review=bool(a.include_owner_review and v['outcome']=='NEEDS_OWNER_APPROVAL' and item['may_accept'] and date==item['expected_day'])
 if tier1 or owner_review:
  if owner_review:
   res=c.post(f'/offers/{oid}/accept',json={'verdict_id':v['id'],'state_version':v['state_version']},headers=owner)
   assert res.status_code==200,res.text
   execution='EXECUTED' if (res.json().get('decision',{}).get('agreement') or {}).get('status') in ('ACTIVE','ACCEPTED') else 'NOT_EXECUTED'
  else:
   prop=rt.executor.propose_commitment(v['id'],expires_day=7)
   operation={'kind':'ACCEPT_OFFER','op_id':item['id']+'-accept','idempotency_key':item['id']+'-accept','mandate_version':1,'requested_by':'AGENT','offer_id':oid,'offer_version':1,'terms_hash':prop.terms_hash,'nonce':prop.nonce,'source_verdict_id':v['id']}
   res=c.post('/operations',json=operation,headers=agent);assert res.status_code==200,res.text;execution=res.json()['result']['status']
  accepted=[x for x in rt.store.commitments() if x.status.value in ('ACCEPTED','ACTIVE')]
  correct_commitment=bool(accepted) and all(ob.effective_day==item['expected_day'] and ob.rate_bp==50 and ob.base.amount_fen==42_000_000 and ob.base.receivable_id=='RCV-A' and ob.type.value=='IMMEDIATE_DISCOUNT' for cc in accepted for ob in cc.obligations)
  promise_cash_unchanged=rt.store.get_state().cash_fen==before.cash_fen and rt.store.get_state().receivables==before.receivables
  detail=c.get(f'/offers/{oid}',headers=owner);assert detail.status_code==200
  decision=c.get('/decisions/'+detail.json()['decision_id'],headers=owner);assert decision.status_code==200,decision.text
  view=decision.json();owner_outcome=(view.get('evaluation') or {}).get('outcome')
  assert owner_outcome in ('ACCEPT','NEEDS_OWNER_APPROVAL'),view
  assert (view.get('agreement') or {}).get('status') in ('ACTIVE','ACCEPTED'),view
  if execution=='EXECUTED' and date is not None:
   adv=c.post('/clock/advance',json={'to_day':date},headers=owner)
   # The public clock API may use `to_day`; keep errors explicit rather than silently adjusting.
   assert adv.status_code==200,adv.text
   pre_receipt=rt.store.get_state()
   receipt={'kind':'RECEIVE_PAYMENT','op_id':item['id']+'-receipt','idempotency_key':item['id']+'-receipt','mandate_version':1,'requested_by':'SYSTEM','receivable_id':'RCV-A','amount_fen':41_790_000,'bank_reference':item['id']+'-bank'}
   rr=c.post('/operations',json=receipt,headers={**agent,'X-Bank-Feed-Key':'demo-bank-feed-key'});assert rr.status_code==200,rr.text
   received=rr.json()['result']['status'];after=rt.store.get_state();receipt_delta=after.cash_fen-pre_receipt.cash_fen;rcv=next(x for x in after.receivables if x.id=='RCV-A')
   receipt_ok=received=='EXECUTED' and after.cash_fen-pre_receipt.cash_fen==41_790_000 and rcv.status=='SETTLED' and rcv.settled_fen==42_000_000
 final_active=sum(x.status.value in ('ACCEPTED','ACTIVE','FULFILLED') for x in rt.store.commitments())-before_commitments
 wrong_accept=tier1 and (not item['may_accept'] or item['expected_day']!=date)
 workflow=bool((tier1 or owner_review) and execution=='EXECUTED' and correct_commitment and receipt_ok and promise_cash_unchanged and unchanged and not wrong_accept)
 rows.append({'id':item['id'],'may_accept':item['may_accept'],'expected_day':item['expected_day'],'outcome':v['outcome'],'tier':v['required_tier'],'effective_day':date,'date_correct':item['expected_day'] is not None and date==item['expected_day'],'date_proven':item['expected_day'] is not None and date==item['expected_day'] and any(ob.get('payment_timing') for ob in offer['obligations']),'tier1':tier1,'explicit_owner_review':owner_review,'wrong_tier1':wrong_accept,'execution':execution,'receipt':received,'stored_commitment_correct':correct_commitment,'receipt_ok':receipt_ok,'bank_feed_cash_delta_fen':receipt_delta,'intake_evaluation_state_unchanged':unchanged,'promise_cash_receivable_unchanged':promise_cash_unchanged,'final_agreed_commitments':final_active,'complete_verified_workflow':workflow,'owner_outcome':owner_outcome,'compiler':offer['compiler'],'notes':offer.get('autonomy_notes',[]),'latency_ms':round((time.perf_counter()-start)*1000,1)})
 c.close();set_runtime(None)
result={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'product_diff_sha256':hashlib.sha256(subprocess.check_output(['git','diff','--','services/api/app'],cwd=root)).hexdigest(),'items_sha256':hashlib.sha256(Path(a.items).read_bytes()).hexdigest(),'recorded_stage_finalized':a.finalize_recordings,'include_owner_review_protocol':a.include_owner_review,'mode':('fresh live provider' if a.live else 'matched recorded provider responses' if a.recordings else 'cache; new text not recorded uses rules; no fresh model evaluation'),'summary':{'items':len(rows),'eligible_labelled':sum(x['may_accept'] for x in rows),'complete_verified_workflows':sum(x['complete_verified_workflow'] for x in rows),'autonomous_completed_workflows':sum(x['complete_verified_workflow'] and x['tier1'] for x in rows),'owner_reviewed_completed_workflows':sum(x['complete_verified_workflow'] and x['explicit_owner_review'] for x in rows),'bank_feed_receipts_executed':sum(x['receipt']=='EXECUTED' for x in rows),'bank_feed_cash_delta_fen':sum(x['bank_feed_cash_delta_fen'] for x in rows),'wrong_tier1':sum(x['wrong_tier1'] for x in rows),'date_matches':sum(x['date_correct'] for x in rows),'proven_date_matches':sum(x['date_proven'] for x in rows),'state_mutations_during_read':sum(not x['intake_evaluation_state_unchanged'] for x in rows),'promise_mutated_cash_or_receivable':sum(not x['promise_cash_receivable_unchanged'] for x in rows)},'rows':rows}
Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result['summary']))
