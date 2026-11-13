import sys,json,re,collections,difflib
from pathlib import Path
scope={};exec(Path('/workspace/scratch/2446eb38e476/inspect_ir_entities.py').read_text().split("root=Path(")[0],scope)
parse=scope['parse']; case=sys.argv[1]
info=json.loads(Path('/workspace/scratch/2446eb38e476/collections-identity-review.json').read_text())[case]
root=Path('/workspace/scratch/2446eb38e476/rc2-retained-comparison/cases')/case
b=parse(root/'base.normalized.ll',info['class_mapping']);c=parse(root/'candidate.ll',{})
# Allow only explicitly known generated template instance suffixes to vary.
def family(n): return re.sub(r'\.\d+$','.#',n)
def shape(n,s):
 s=s.replace(n+'(', '@SELF(',1)
 return re.sub(r'@[A-Za-z0-9_.$-]+',lambda m:family(m[0]) if m[0] in b or m[0] in c else m[0],s)
poss={n:[k for k,t in c.items() if family(k)==family(n) and shape(n,s)==shape(k,t)] for n,s in b.items()}
print('shape no candidates', [n for n,p in poss.items() if not p])
print('shape ambiguous', [(n,p) for n,p in poss.items() if len(p)>1])
fm={n:p[0] for n,p in poss.items() if len(p)==1}
# Eliminate candidate mappings whose corresponding call edges cannot agree.
for _ in range(20):
 change=False
 for n,p in poss.items():
  if len(p)<=1:continue
  retained=[]
  for k in p:
   x=b[n].replace(n+'(', '@SELF(',1); y=c[k].replace(k+'(', '@SELF(',1)
   xb=re.findall(r'@[A-Za-z0-9_.$-]+',x);yb=re.findall(r'@[A-Za-z0-9_.$-]+',y)
   assert len(xb)==len(yb)
   if all(a not in poss or z in poss[a] for a,z in zip(xb,yb)):retained.append(k)
  if retained!=p:poss[n]=retained;change=True
 for n,p in list(poss.items()):
  if len(p)!=1: continue
  k=p[0]; x=b[n].replace(n+'(', '@SELF(',1); y=c[k].replace(k+'(', '@SELF(',1)
  xb=re.findall(r'@[A-Za-z0-9_.$-]+',x); yb=re.findall(r'@[A-Za-z0-9_.$-]+',y)
  assert len(xb)==len(yb)
  for a,z in zip(xb,yb):
   if a in poss and poss[a]!=[z]:
    if z not in poss[a]: raise RuntimeError(('incompatible edge',n,k,a,z,poss[a]))
    poss[a]=[z]; change=True
 if not change:break
fm={n:p[0] for n,p in poss.items() if len(p)==1}
print('refined ambiguous',[(n,p) for n,p in poss.items() if len(p)!=1])
# A matching maps all callee references and the function's own name at once.
def translated(s):return re.sub(r'@[A-Za-z0-9_.$-]+',lambda m:fm.get(m[0],m[0]),s)
remaining=[]
for n,k in fm.items():
 x=translated(b[n]);y=c[k]
 if x!=y:
  remaining.append((n,k))
  if '--diff' in sys.argv:print('\n'.join(difflib.unified_diff(x.splitlines(),y.splitlines(),fromfile=n,tofile=k)))
result={'class_mapping':info['class_mapping'],'function_mapping':{n:k for n,k in fm.items() if n!=k},'ambiguous':{n:p for n,p in poss.items() if len(p)!=1},'remaining':remaining,'baseline_functions':len(b),'candidate_functions':len(c),'exact_matches':len(fm)-len(remaining),'distinct_candidate_targets':len(set(fm.values()))}
out=Path('/workspace/scratch/2446eb38e476')/f'closed-calls-{case}.json';out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='function_mapping'},indent=2));print(out)
