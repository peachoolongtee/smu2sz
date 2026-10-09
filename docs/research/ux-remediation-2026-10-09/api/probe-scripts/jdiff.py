import json,sys,re
from pathlib import Path
a=Path(sys.argv[1]); b=Path(sys.argv[2])
HASHY=re.compile(r'^[0-9a-f]{16,}$|^(OFF|OP|AL|APP|CM|EV)-[0-9a-f]{6,}|^\d{4}-\d\d-\d\dT')
def walk(x,p=''):
    if isinstance(x,dict):
        for k,v in x.items(): yield from walk(v,p+'.'+k)
    elif isinstance(x,list):
        for i,v in enumerate(x): yield from walk(v,p+f'[{i}]')
    else: yield p,x
tot=0
for f in sorted(a.glob('*.json')):
    g=b/f.name
    if not g.exists(): print('MISSING',f.name); continue
    A=dict(walk(json.loads(f.read_text()))); B=dict(walk(json.loads(g.read_text())))
    diffs=[]
    for k in sorted(set(A)|set(B)):
        va,vb=A.get(k,'<absent>'),B.get(k,'<absent>')
        if va==vb: continue
        if isinstance(va,str) and isinstance(vb,str) and HASHY.search(va) and HASHY.search(vb): continue
        if any(s in k for s in ('hash','_at','timestamp','nonce','seconds')): continue
        diffs.append((k,va,vb))
    print(f'== {f.name}: {len(A)} leaves audit / {len(B)} now, {len(diffs)} non-hash diffs')
    for k,va,vb in diffs[:15]: print('   ',k,'| audit:',str(va)[:90],'| now:',str(vb)[:90])
    tot+=len(diffs)
print('TOTAL',tot)
