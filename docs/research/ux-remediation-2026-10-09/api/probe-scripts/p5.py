import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
post('f18-reset','/demo/reset',{})
h=get('f18-home-day0','/home')
na=h['next_action']; print('home day',h['day'],'next_action plan_source',na.get('plan_source'),'recommended_key',na.get('recommended_key'),'cost',na['cost_total_display'],'cheaper_option',na.get('cheaper_option'))
p=post('f18-router-plan-day0','/router/plan',{})
print([k for k in p][:20])
for i,r in enumerate(p['comparison']):
    print(i+1,{k:r.get(k) for k in('key','label','role','role_reason','total_fen','status','result','reason_kind','executable_now','needs_owner_approval','shortfall_fen','selected')}, [ (a.get('kind') or a.get('operation_kind'),a.get('facility_id'),a.get('receivable_id'),a.get('amount_fen')) for a in r.get('actions',[])])
    print('    note:',r.get('note'));print('    comps:',r.get('components'))
