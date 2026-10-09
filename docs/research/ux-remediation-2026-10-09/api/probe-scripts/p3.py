import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
for prof in ('cooperative','hard_line'):
    tag=f'f04-{prof}'
    post(f'{tag}-reset','/demo/reset',{})
    o=post(f'{tag}-offer','/offers',{'fixture_id':'EX01_PACKAGE'})['offer']
    ev=post(f'{tag}-evaluate',f"/offers/{o['offer_id']}/evaluate",{'fixture_id':'EX01_PACKAGE'})
    v=ev.get('verdict',ev)
    print(prof,'VERDICT keys',[k for k in v if k in('outcome','required_tier','summary','business_action')],{k:v.get(k) for k in('outcome','required_tier')}, 'counters',len(v.get('counters',[])))
    led0=get(f'{tag}-ledger-before-negotiate','/ledger')
    print('  ops before negotiate:',[(x['kind'],x['status']) for x in led0['operations']])
    neg=post(f'{tag}-negotiate',f"/negotiate/{o['offer_id']}",{'buyer_profile':prof})
    print('  negotiate outcome',neg.get('outcome'),'keys',sorted(neg)[:20])
    print('  negotiate operations:',[(x.get('kind'),x.get('status'),x.get('message')) for x in neg.get('operations',[])])
    led=get(f'{tag}-ledger-after-negotiate','/ledger')
    print('  ledger ops:',[(x['seq'],x['kind'],x['status'],x.get('message')) for x in led['operations']])
    print('  commitments:',[(c['id'],c['status'],c.get('forward_value_fen')) for c in led['commitments']])
    st=get(f'{tag}-state-after','/state')
    s=st.get('state',st)
    print('  cash_fen',s.get('cash_fen'),'lots',[(l['facility_id'],l['principal_fen'],l['settled'],l['arrival_day']) for l in s.get('lots',{}).get('lots',[])] if isinstance(s.get('lots'),dict) else s.get('lots'))
    h=get(f'{tag}-home','/home')
    print('  home in_transit',h['cash']['in_transit'])
