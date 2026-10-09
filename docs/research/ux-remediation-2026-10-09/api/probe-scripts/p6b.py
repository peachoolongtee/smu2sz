import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
post('f24-reset2','/demo/reset',{})
doc={'doc_id':'f24-usd','channel':'chat','sender_id':'BUYER-1','received_day':0,'text':'We can pay the invoice early at 0.5% in USD.'}
o=post('f24-offer-usd','/offers',{'counterparty_id':'BUYER-1','documents':[doc]})
oid=o['offer']['offer_id']
print('abstentions',json.dumps(o['offer'].get('abstentions'),ensure_ascii=False))
v=post('f24-evaluate-usd',f'/offers/{oid}/evaluate',{})
vv=v.get('verdict',v)
print('outcome',vv.get('outcome'),'summary',vv.get('summary'))
for x in vv.get('violations',[]): print(' violation',x.get('code'),'| observed',x.get('observed'),'| inputs',x.get('inputs'),'| message',x.get('message'))
