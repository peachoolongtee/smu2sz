import os
os.environ.update(TERMSLEDGER_NO_DOTENV='1', DATABASE_URL='memory', LLM_MODE='cache', DEMO_MODE='1')
import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'services/api'))
from fastapi.testclient import TestClient
from app.main import app
from app.api.runtime import get_runtime, set_runtime
from app.domain.models import DrawFacility, Actor

owner = TestClient(app, headers={'X-Owner-Token':'demo-owner-token'})
agent = TestClient(app, headers={'X-Agent-Key':'demo-agent-key'})
public = TestClient(app)
evidence = {}

def books():
    rt=get_runtime(); s=rt.store.get_state()
    return {'cash_fen':s.cash_fen, 'state_version':s.state_version,
            'facilities':{f.id:f.drawn_fen for f in s.facilities},
            'commitments':[(c.id,c.status.value) for c in rt.store.commitments()],
            'operations':len(rt.store.operations())}

commands = ['Do not draw ¥100,000 on the credit line.',
 'Is it safe to draw ¥100,000 on the credit line?',
 'draw ¥100,000 on the credit line only if cash is below ¥0',
 'draw ¥100,000 on the credit line tomorrow',
 'draw $100,000 on the credit line', 'draw ¥1.001 on the credit line',
 '不要从授信额度提款10万元', '请问从授信额度提款10万元安全吗？']
evidence['commands']=[]
for credential, c in [('owner',owner),('agent',agent)]:
    for text in commands:
        get_runtime().reset(); before=books()
        request={'actor':'OWNER','text':text}
        response=c.post('/nl',json=request)
        out=response.json()
        evidence['commands'].append({'credential':credential,'request':request,'http':response.status_code,
            'before':before,'after':books(),'response':out})

evidence['approval_negation']=[]
for text in ['Do not approve APR-000001','I do not approve APR-000001',
             'Should I approve APR-000001?','APR-000001','Reject APR-000001, do not approve']:
    get_runtime().reset()
    queued=owner.post('/operations',json={'kind':'RECEIVE_PAYMENT','requested_by':'AGENT',
       'op_id':'AUDIT-RECEIPT','idempotency_key':'AUDIT-RECEIPT','mandate_version':1,
       'receivable_id':'RCV-A','amount_fen':10000}).json()
    before=books()
    response=owner.post('/nl',json={'actor':'OWNER','text':text}).json()
    evidence['approval_negation'].append({'request':text,'queued':queued,'before':before,
                                        'after':books(),'response':response})

get_runtime().reset(); before=books()
request={'actor':'COUNTERPARTY','counterparty_id':'BUYER-1',
         'text':'We will pay the ¥420,000 invoice early at a 0.5% discount.'}
response=public.post('/nl',json=request).json()
evidence['unauthenticated_buyer']={'request':request,'headers':{},'before':before,
                                 'after':books(),'response':response,
                                 'ledger':[json.loads(x.result_json) for x in get_runtime().store.operations()]}

evidence['settlement_time']=[]
for timing in ['today','tomorrow','early']:
    get_runtime().reset()
    request={'actor':'COUNTERPARTY','counterparty_id':'BUYER-1',
             'text':f'We will pay the ¥420,000 invoice {timing} at a 0.5% discount.'}
    response=public.post('/nl',json=request).json()
    evidence['settlement_time'].append({'request':request,'response':response,'after':books()})

get_runtime().reset()
proposal=owner.post('/nl',json={'actor':'OWNER','text':'Find me the cheapest way to fund the cash gap'}).json()
rt=get_runtime(); s=rt.store.get_state()
rt.store.put_state(s.model_copy(update={'state_version':s.state_version+1,'cash_fen':s.cash_fen-10000000}))
before=books()
confirmation=owner.post('/nl',json={'actor':'OWNER','session_id':proposal['session_id'],'text':'go ahead'}).json()
evidence['changed_plan']={'proposal':proposal,'state_change':'cash reduced by 10,000,000 fen; state_version +1',
                          'before_confirmation':before,'after_confirmation':books(),'confirmation':confirmation,
                          'payloads':[json.loads(x.payload_json) for x in rt.store.operations()]}

set_runtime(None)
fd,p=tempfile.mkstemp(prefix='termsledger-audit-',suffix='.db',dir='/tmp'); os.close(fd)
os.environ.update(DATABASE_URL='sqlite:///'+p,DEMO_MODE='0')
rt=get_runtime()
rt.executor.execute(DrawFacility(op_id='AUDIT-RESTART',idempotency_key='AUDIT-RESTART',
 mandate_version=rt.store.get_mandate().version,requested_by=Actor.AGENT,day=0,
 facility_id='FAC-LINE',amount_fen=10000000))
before=books(); rt.store.dispose(); set_runtime(None)
after=books()
evidence['restart']={'DEMO_MODE':'0','before':before,'after':after,'method':'dispose; set_runtime(None); get_runtime()'}
get_runtime().store.dispose(); set_runtime(None); os.unlink(p)
Path('/tmp/termsledger-security-independent-evidence.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'command_cases':len(evidence['commands']),'approval_cases':len(evidence['approval_negation']),
 'restart':evidence['restart'],'output':'/tmp/termsledger-security-independent-evidence.json'},ensure_ascii=False))
