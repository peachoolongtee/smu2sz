import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
spec=raw('GET','/openapi.json')[1]
rows=[]
for p,v in sorted(spec['paths'].items()):
    for m,op in v.items():
        names=[x['name'] for x in op.get('parameters',[])]
        body=''
        rb=op.get('requestBody',{}).get('content',{}).get('application/json',{}).get('schema',{})
        ref=rb.get('$ref','').split('/')[-1]
        if ref: body=list(spec['components']['schemas'].get(ref,{}).get('properties',{}))
        rows.append((m.upper(),p,'lang' in names or (isinstance(body,list) and 'lang' in body)))
(OUT/'f28-routes-with-lang-parameter.json').write_text(json.dumps({'probe':'f28-routes','request':{'method':'GET','path':'/openapi.json'},'routes':[{'method':m,'path':p,'takes_lang':l} for m,p,l in rows]},indent=1)+'\n')
print('take lang:',[(m,p) for m,p,l in rows if l]); print('count routes',len(rows))
walk('f28',None)
h=get('f28-home-zh','/home?lang=zh')
print('home zh headline:',h['headline'],'|',h['note'])
q=post('f28-act-zh-home','/alerts/ALERT-RESERVE-34/act',{'state_version':h['state_version'],'suggestions':h['next_action']['suggestions']})
qq=get('f28-queue-zh','/approvals/queue?lang=zh')
p=qq['approvals'][0]['presentation']
print('queue?lang=zh headline:',p['headline'],'| if_decline:',p['if_decline'],'| reason:',p['reason'])
print('zh home approvals block:',json.dumps(h['approvals'],ensure_ascii=False)[:300])
r=get('f28-reconciliation-zh','/reconciliation?lang=zh')['reconciliation']
print('recon zh promised detail_when:',r['promised'][0]['detail_when'] if r['promised'] else None, '| lapsed', r.get('lapsed_promises'))
l=get('f28-ledger-zh','/ledger?lang=zh')
print('ledger zh event_text:',[o.get('event_text') for o in l['operations']][:3])
