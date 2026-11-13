#!/usr/bin/env python3
"""Supplementary semantic review aid; never rewrites oracle/raw evidence."""
import re,sys,difflib,json
from pathlib import Path

def parse(path,rename):
 text=path.read_text()
 if rename: text=re.sub("|".join(re.escape(k) for k in sorted(rename,key=len,reverse=True)),lambda m:rename[m.group()],text)
 strings=dict(re.findall(r'^(@s\.\d+) = (.*)$',text,re.M))
 metas=dict(re.findall(r'^!(\d+) = (.*)$',text,re.M))
 def meta(m,seen=frozenset()):
  n=m.group(1)
  if n in seen: return '!RECURSION'+n
  if n not in metas: return '!MISSING'+n
  return re.sub(r'!(\d+)\b',lambda sub:meta(sub,seen|{n}),metas[n])
 def norm(s):
  s=re.sub(r'@s\.\d+\b',lambda m:'@STRING['+strings[m.group()]+']',s)
  return re.sub(r'!(\d+)\b',meta,s)
 funs={}
 for m in re.finditer(r'^define [^\n]*?(@[^ (]+)\([^\n]*?\) [^\n]*\{\n.*?^\}',text,re.M|re.S):
  funs[m[1]]=norm(m[0])
 return funs

root=Path('/workspace/scratch/2446eb38e476/rc2-retained-comparison/cases')
index=int(sys.argv[1]); rename=json.loads(sys.argv[2]) if len(sys.argv)>2 else {}
p=root/f'{index:05d}'
b=parse(p/'base.normalized.ll',rename); c=parse(p/'candidate.ll',{})
print('only base',sorted(b.keys()-c.keys()))
print('only candidate',sorted(c.keys()-b.keys()))
print('functions',len(b),len(c),'same',sum(b[k]==c[k] for k in b.keys()&c.keys()))
for k in sorted(b.keys()&c.keys()):
 if b[k]!=c[k]:
  print('FUNCTION',k)
  print('\n'.join(difflib.unified_diff(b[k].splitlines(),c[k].splitlines(),n=2)))
