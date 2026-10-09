import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
walk('f03',receipt='partial',to=2)
for d in (2,34):
    if d==34:
        post('f03-clock-day34','/clock/advance',{'to_day':34})
    r=get(f'f03-reconciliation-day{d}','/reconciliation')['reconciliation']
    print('DAY',d)
    for k in ('receipts','promised'):
        x=r[k][0]
        print(' ',k,'[0] detail     :',x['detail']); print(' ',k,'[0] detail_when:',x['detail_when'])
        print('   ', {kk:vv for kk,vv in x.items() if kk not in('detail','detail_when')})
print(json.dumps({k:v for k,v in r.items() if k not in('receipts','promised')},ensure_ascii=False)[:600])
