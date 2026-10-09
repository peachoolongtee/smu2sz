import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
for tag,rc in (('f01-partial','partial'),('f01-nowreceipt',None),('f01-fullreceipt','full')):
    walk(tag,rc)
    h=get(f'{tag}-home-day34','/home')
    c=h['cash']
    print(tag,'day',h['day'],h['status'])
    for k in ('cash_fen','cash_short','first_breach_day','first_breach_when','first_breach_cash_fen','first_breach_cash_short','lowest_fen','lowest_day','lowest_short','lowest_when','drivers'):
        print('   ',k,c[k])
    print('    headline:',h['headline']); print('    note:',h['note']); print('    worst:',h['worst'])
    print('    series[0..3]:',json.dumps(c['series'][:4],ensure_ascii=False))
    print('    alerts:',[ (a['id'],a['kind'],a['day']) for a in get(f'{tag}-alerts','/alerts')['alerts']] if 'alerts' in get(f'{tag}-alerts','/alerts') else None)
