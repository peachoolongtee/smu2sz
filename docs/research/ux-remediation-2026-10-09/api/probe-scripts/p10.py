import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
tag='f14'
walk(tag,None)
h=get(f'{tag}-home-before','/home'); na=h['next_action']
act=post(f'{tag}-act',f"/alerts/{na['alert_id']}/act",{'state_version':na['state_version'],'suggestions':na['suggestions']})
q=get(f'{tag}-queue-pending','/approvals/queue'); apr=q['approvals'][0]['id']; print('pending',apr,q['approvals'][0]['status'])
adv=post(f'{tag}-clock-day91','/clock/advance',{'to_day':91})
print('clock now',day())
dec=raw('POST',f'/approvals/{apr}',{'decision':'APPROVE'})
(OUT/f'{tag}-approve-refused.json').write_text(json.dumps({'probe':'f14-approve','request':{'method':'POST','path':f'/approvals/{apr}','body':{'decision':'APPROVE'},'credential':['X-Owner-Token']},'clock_day_before_request':91,'status':dec[0],'response':dec[1]},ensure_ascii=False,indent=2)+'\n')
r=dec[1]['result']; print('HTTP',dec[0],'result.status',r['status'],'| message',r['message'],'| violations',[(v['code'],v['message'][:100]) for v in r['violations']])
q2=get(f'{tag}-queue-after','/approvals/queue'); a=q2['approvals'][0]
print('queue after: status',a['status'],'decided_by',a['decided_by'],'decided_day',a['decided_day'],'result_message',a['result_message'])
print('   presentation:',{k:a['presentation'].get(k) for k in('headline','cost_display','if_decline','result_message','decided_when')})
dec2=raw('POST',f'/approvals/{apr}',{'decision':'APPROVE'})
(OUT/f'{tag}-approve-second-click.json').write_text(json.dumps({'probe':'f14-second-click','request':{'method':'POST','path':f'/approvals/{apr}','body':{'decision':'APPROVE'},'credential':['X-Owner-Token']},'clock_day_before_request':91,'status':dec2[0],'response':dec2[1]},ensure_ascii=False,indent=2)+'\n')
print('second click HTTP',dec2[0],dec2[1])
led=get(f'{tag}-ledger','/ledger'); print([ (o['seq'],o['kind'],o['status']) for o in led['operations'][-4:]])
