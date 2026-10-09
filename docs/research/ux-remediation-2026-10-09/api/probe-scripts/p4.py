import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
PF=('cost_display','rate_text','lands_when','after','protects','if_decline','question','result_message','decided_when','reason')
def show(label,q):
    for a in q['approvals']:
        p=a.get('presentation',{})
        print(f'  [{label}] {a["id"]} status={a["status"]} decided_day={a.get("decided_day")} result_message={a.get("result_message")!r}')
        for k in PF: print('       ',k,'=',repr(p.get(k)))
for tag,rc in (('f12-zerofloor',None),('f12-fullreceipt','full'),('f12-partial','partial')):
    print('=====',tag)
    walk(tag,rc)
    h=get(f'{tag}-home-before','/home')
    na=h['next_action']
    print(' home',h['status'],'|',h['headline'],'| next_action kind',na and na['kind'], 'alert',na and na['alert_id'],'title',na and na['title'],'cost',na and na['cost_display'],'total',na and na['cost_total_display'],'after_lowest',na and na['after_lowest_short'], 'needs_owner',na and na['needs_owner'])
    print('   next_action.after =',na['after']); print('   if_nothing =',na['if_nothing'])
    al=[a for a in get(f'{tag}-alerts','/alerts')['alerts'] if a['id']==na['alert_id']][0]
    print(' alert inputs',{k:v for k,v in al['inputs'].items()})
    act=post(f'{tag}-act',f"/alerts/{na['alert_id']}/act",{'state_version':na['state_version'],'suggestions':na['suggestions']})
    print(' act: executed',act['executed'],'pending',act['pending_approval'],'refused',act['refused'],'cured',act['cured'],[ (r['kind'],r['status'],r['message']) for r in act['results']])
    q1=get(f'{tag}-queue-before','/approvals/queue'); show('BEFORE',q1)
    apr=q1['approvals'][0]['id']
    dec=post(f'{tag}-approve',f'/approvals/{apr}',{'decision':'APPROVE'})
    print(' approve result:',dec['result']['status'],dec['result']['message'])
    q2=get(f'{tag}-queue-after','/approvals/queue'); show('AFTER',q2)
    h2=get(f'{tag}-home-after','/home')
    na2=h2['next_action']
    c=h2['cash']
    print(' home AFTER',h2['status'],'|',h2['headline'],'| note',h2['note'],'| next_action',na2 and (na2['kind'],na2['title']),'| lowest',c['lowest_short'],c['lowest_when'],'| first_breach',c['first_breach_day'],c['first_breach_when'],c['first_breach_cash_short'],'| plan_note',h2['plan_note'],'| worst',h2['worst'])
    print('  alerts after:',[(a['id'],a['kind'],a['day']) for a in get(f'{tag}-alerts-after','/alerts')['alerts']])
