import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
L=get('f03-ledger-day34','/ledger')
for o in L['operations']:
    if o.get('kind')=='RECEIVE_PAYMENT' or 'settled early' in json.dumps(o): 
        print({k:o[k] for k in o if k in ('kind','day','message','message_when','event_text','event_detail','summary')})
h=get('f03-home-day34','/home')
print([c['text'] for c in h['changes']] if isinstance(h['changes'],list) else h['changes'])
