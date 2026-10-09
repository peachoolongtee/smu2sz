import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
o,neg=walk('f06',None)
print('negotiation response commitment (what the web store keeps):',{k:neg['commitment'].get(k) for k in('id','status','expires_day','accepted_day','activated_day') if k in neg['commitment']}, 'outcome',neg['outcome'])
L=get('f06-ledger-day34','/ledger')
for c in L['commitments']: print('LEDGER commitment',{k:v for k,v in c.items() if k not in('obligations','terms','source_hash','entry_hash')})
print([k for k in L])
print('lapsed fields?',{k:L[k] for k in L if 'laps' in k})
rec=get('f06-reconciliation-day34','/reconciliation')['reconciliation']
print('recon lapsed_promises',rec.get('lapsed_promises'),[ (p['status']) for p in rec['promised']])
c=get('f06-clock','/clock'); print(c)
