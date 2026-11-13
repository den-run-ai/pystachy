#!/usr/bin/env python3
"""Supplementary review display; raw retained comparison remains unmodified."""
import re,sys,difflib,json
from pathlib import Path
from collections import Counter

def parse(path,rename):
 text=path.read_text()
 if rename: text=re.sub('|'.join(re.escape(k) for k in sorted(rename,key=len,reverse=True)),lambda m:rename[m.group()],text)
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
 text=re.sub(r'^define [^\n]*?(@[^ (]+)\([^\n]*?\) [^\n]*\{\n.*?^\}', '',text,flags=re.M|re.S)
 rows=[]
 for l in text.splitlines():
  if not l.strip():continue
  if re.match(r'^@s\.\d+ =',l): l='STRING: '+l.split(' = ',1)[1]
  elif re.match(r'^!\d+ =',l): l='META: '+l.split(' = ',1)[1]
  rows.append(norm(l))
 return Counter(rows)

root=Path('/workspace/scratch/2446eb38e476/rc2-retained-comparison/cases')
index=int(sys.argv[1]); rename=json.loads(sys.argv[2]) if len(sys.argv)>2 else {}
p=root/f'{index:05d}'
b=parse(p/'base.normalized.ll',rename); c=parse(p/'candidate.ll',{})
print('only base:'); print('\n'.join((b-c).elements()))
print('only candidate:'); print('\n'.join((c-b).elements()))
