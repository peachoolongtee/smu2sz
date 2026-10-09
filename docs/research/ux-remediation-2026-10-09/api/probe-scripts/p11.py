import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
walk('f01b-nowreceipt',None)
t=get('f01b-trajectory-day34','/trajectory?mode=CONSERVATIVE')
tr=t.get('trajectory',t)
print({k:tr.get(k) for k in tr if k not in('days','months')})
print('days[0..2]',[(d['day'],d['closing_fen']) for d in tr['days'][:3]],'...days[34]',[(d['day'],d['closing_fen']) for d in tr['days'] if d['day'] in(33,34,35)])
