import sys; sys.path.insert(0,'/private/tmp/claude-501/-Users-ianpong-Hackathons-SZ-Research/5189f386-0526-4c54-962d-fd87b5e03b18/scratchpad/map65/w0api')
from lib import *
walk('f25-partial','partial')
h=get('f25-home-day34','/home')
print(json.dumps(h['changes'],ensure_ascii=False,indent=1))
print(json.dumps(h['receivables'],ensure_ascii=False,indent=1))
print([ (w['kind'],w['title'],w['detail']) for w in h['warnings']])
