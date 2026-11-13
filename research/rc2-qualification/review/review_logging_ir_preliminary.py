import re,hashlib,json,difflib
from pathlib import Path
ROOT=Path('/workspace/scratch/2446eb38e476/rc2-retained-comparison/cases')
def parse(case,label):
 s=(ROOT/case/label).read_text()
 strings={m[1]:hashlib.sha256(m[2].encode()).hexdigest()[:12] for m in re.finditer(r'^(@s\.\d+) = (.*)$',s,re.M)}
 def norm(x):
  x=re.sub(r'@s\.\d+\b',lambda m:'@STR_'+strings[m[0]],x)
  x=re.sub(r'@dbs\.(\d+)\b',lambda m:'@BOXSTR_'+strings.get('@s.'+m[1],m[1]),x)
  x=re.sub(r', !tbaa !\d+','',x)
  return x
 f={m[1]:norm(m[0]) for m in re.finditer(r'^define [^@]*@([^ (]+).*?^}',s,re.M|re.S)}
 return s,f,norm
for case in ['01498','01499','01500','01501','01502','02432']:
 if not (ROOT/case/'candidate.ll').exists(): continue
 b,bf,bn=parse(case,'base.normalized.ll');c,cf,cn=parse(case,'candidate.ll')
 changed=[n for n in bf.keys()&cf.keys() if bf[n]!=cf[n]]
 print(case,'removed',sorted(bf.keys()-cf.keys()),'added',sorted(cf.keys()-bf.keys()),'changed',len(changed))
 for n in sorted(changed):
  d=list(difflib.unified_diff(bf[n].splitlines(),cf[n].splitlines(),n+' base',n+' candidate',n=3))
  print(n,len(d))
  if n=='m._weakref$ReferenceType-1.__repr__' or len(d)<80:print('\n'.join(d))
