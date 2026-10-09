import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
post('f24-reset','/demo/reset',{})
texts={'usd':'We can pay the invoice early at 0.5% in USD.',
 'no-currency':'We can pay the invoice early at 0.5%.',
 'usd-named-invoice':'We can pay invoice RCV-A early at 0.5% in USD.',
 'cny-named-invoice':'We can pay invoice RCV-A early at 0.5% in CNY.',
 'eur-named-invoice-day2':'We will pay invoice RCV-A on day 2 at a 0.5% discount, in EUR.'}
for i,(k,tx) in enumerate(texts.items()):
    r=post(f'f24-nl-{k}','/nl',{'session_id':f'f24-{k}','actor':'COUNTERPARTY','counterparty_id':'BUYER-1','text':tx,'request_id':f'f24-{k}'},BUYER)
    print(k,'|',tx,'\n    reply:',r['reply'],'| verdict',(r.get('verdict') or {}).get('outcome'),'| ops',len(r['operations']),'| sec',[e.get('kind') if isinstance(e,dict) else e for e in r['security_events']])
