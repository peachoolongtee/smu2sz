import json, urllib.request, urllib.error
from pathlib import Path
BASE='http://localhost:8031'
OUT=Path(__file__).resolve().parents[1]
OWNER={'X-Owner-Token':'demo-owner-token'}
BANK={'X-Agent-Key':'demo-agent-key','X-Bank-Feed-Key':'demo-bank-feed-key'}
AGENT={'X-Agent-Key':'demo-agent-key'}
BUYER={'X-Counterparty-Key':'demo-buyer-1-key'}
def raw(method,path,data=None,headers=OWNER):
    req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={**headers,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=60) as r: return r.status,json.load(r)
        
    except urllib.error.HTTPError as e:
        return e.code,json.load(e)
def day(): return raw('GET','/clock')[1]['day']
def call(probe,method,path,data=None,headers=OWNER,save=True):
    d=day()
    st,out=raw(method,path,data,headers)
    if save:
        rec={'probe':probe,'request':{'method':method,'path':path,'body':data,'credential':sorted(headers)},'clock_day_before_request':d,'status':st,'response':out}
        (OUT/(probe+'.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n')
    return out
def post(p,path,data=None,headers=OWNER,**k): return call(p,'POST',path,data if data is not None else {},headers,**k)
def get(p,path,headers=OWNER,**k): return call(p,'GET',path,None,headers,**k)
def walk(tag,receipt=None,profile='cooperative',to=34):
    """reset -> EX01_PACKAGE offer -> evaluate -> negotiate -> day 2 -> optional receipt (None|'partial'|'full') -> clock to `to`.
    Writes <tag>-setup.json (every step: request, clock day, status, short result); returns (offer, negotiate response)."""
    steps=[]
    def step(name,method,path,data=None,headers=OWNER):
        d=day(); st,out=raw(method,path,data,headers)
        steps.append({'step':name,'request':{'method':method,'path':path,'body':data,'credential':sorted(headers)},'clock_day_before_request':d,'status':st,'result_keys':sorted(out)[:12] if isinstance(out,dict) else None,'result_message':(out.get('result') or {}).get('message') if isinstance(out,dict) and isinstance(out.get('result'),dict) else None})
        return out
    step('reset','POST','/demo/reset',{})
    o=step('offer','POST','/offers',{'fixture_id':'EX01_PACKAGE'})['offer']
    step('evaluate','POST',f"/offers/{o['offer_id']}/evaluate",{'fixture_id':'EX01_PACKAGE'})
    neg=step('negotiate','POST',f"/negotiate/{o['offer_id']}",{'buyer_profile':profile})
    if to>=2 and profile=='cooperative':
        step('clock day 2','POST','/clock/advance',{'to_day':2})
        if receipt:
            r=step('promise before receipt','GET','/reconciliation')['reconciliation']['promised'][0]
            amt=r['expected_fen']//2 if receipt=='partial' else r['expected_fen']
            m=raw('GET','/mandate')[1]['mandate']['version']
            step(f'bank receipt ({receipt})','POST','/operations',{'kind':'RECEIVE_PAYMENT','op_id':f'{tag}-rcpt','idempotency_key':f'{tag}-rcpt','mandate_version':m,'requested_by':'SYSTEM','receivable_id':r['receivable_id'],'amount_fen':amt,'bank_reference':f'{tag.upper()}-1'},BANK)
        if to>2:
            if to>30: step('clock day 30','POST','/clock/advance',{'to_day':30})
            step(f'clock day {to}','POST','/clock/advance',{'to_day':to})
    (OUT/(tag+'-setup.json')).write_text(json.dumps(steps,ensure_ascii=False,indent=2)+'\n')
    return o,neg
