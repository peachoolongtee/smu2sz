import json, time, urllib.request, urllib.error
from pathlib import Path
root=Path(__file__).resolve().parent
base='http://localhost:8015'
owner={'X-Owner-Token':'demo-owner-token'}
bank={'X-Agent-Key':'demo-agent-key','X-Bank-Feed-Key':'demo-bank-feed-key'}
records=[]
def call(name,path,data=None,headers=owner):
    req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers={**headers,'Content-Type':'application/json'})
    started=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            status=r.status; out=json.load(r)
    except urllib.error.HTTPError as e:
        status=e.code; out=json.load(e)
    root.joinpath(name+'.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    records.append({'name':name,'path':path,'status':status,'seconds':round(time.monotonic()-started,3)})
    return out
call('demo-completed-ledger','/ledger')
call('receipt-reset','/demo/reset',{})
o=call('receipt-offer','/offers',{'fixture_id':'EX01_PACKAGE'})['offer']
call('receipt-evaluation',f"/offers/{o['offer_id']}/evaluate",{'fixture_id':'EX01_PACKAGE'})
call('receipt-negotiation',f"/negotiate/{o['offer_id']}",{'buyer_profile':'cooperative'})
call('receipt-clock-day2','/clock/advance',{'to_day':2})
r=call('receipt-promise-before','/reconciliation')['reconciliation']['promised'][0]
b={'kind':'RECEIVE_PAYMENT','op_id':'audit-partial-receipt','idempotency_key':'audit-partial-receipt','mandate_version':1,'requested_by':'SYSTEM','receivable_id':r['receivable_id'],'amount_fen':r['expected_fen']//2,'bank_reference':'AUDIT-PARTIAL-1'}
p=call('receipt-partial','/operations',b,bank)
d=call('receipt-duplicate','/operations',b,bank)
call('receipt-reconciliation-day2','/reconciliation')
call('receipt-clock-day34','/clock/advance',{'to_day':34})
call('receipt-reconciliation-day34','/reconciliation')
call('home-partial-payment','/home')
call('receipt-ledger-day34','/ledger')
ab=call('abstention-foreign-currency','/nl',{'session_id':'audit-abstention','actor':'COUNTERPARTY','counterparty_id':'BUYER-1','text':'We can pay the invoice early at 0.5% in USD.','request_id':'audit-abstain-usd'},{'X-Counterparty-Key':'demo-buyer-1-key'})
root.joinpath('api-probe-manifest.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps({'partial_status':p['result']['status'],'duplicate_status':d['result']['status'],'abstention_reply':ab.get('reply'),'requests':records},ensure_ascii=False))
