import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
post('f02-reset','/demo/reset',{})
r=post('f02-nl-buyer-early-pay','/nl',{'session_id':'f02','actor':'COUNTERPARTY','counterparty_id':'BUYER-1','text':'We can pay the invoice early at 0.5%.','request_id':'f02-1'},BUYER)
print('reply:',r['reply'],'| ops',[(o.get('kind'),o.get('status')) for o in r['operations']])
q=get('f02-queue','/approvals/queue')
for a in q['approvals']:
    print(a['id'],a['kind'],a['status'],'| amount',a.get('amount_display'),'| op:',{k:v for k,v in (a['operation'] or {}).items() if k in('kind','offer_id','commitment_id','terms_hash','nonce','offer_version')})
    print('  presentation:',json.dumps(a['presentation'],ensure_ascii=False)[:700])
    print('  reason:',a['reason'])
L=get('f02-ledger','/ledger')
for c in L['commitments']: print('LEDGER commitment',{k:c[k] for k in ('id','status','forward_value_display','expires_day') if k in c}, 'obligations' in c and [ (o.get('type'),o.get('rate_bp'),o.get('days_delta'),o.get('effective_day'),o.get('base')) for o in c['obligations']])
