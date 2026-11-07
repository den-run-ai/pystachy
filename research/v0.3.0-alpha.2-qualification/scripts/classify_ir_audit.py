#!/usr/bin/env python3
"""Classify strict audit outputs; normalize only proven checkout-only string paths."""
import argparse,gzip,hashlib,json,os,pathlib,re

def sha(x):return hashlib.sha256(x).hexdigest()
def decode_llvm(text):
 return re.sub(rb'\\([0-9A-Fa-f]{2})',lambda m:bytes([int(m[1],16)]),text)
def encode_llvm(data):
 return b''.join(bytes([v]) if 32<=v<=126 and v not in (34,92) else ('\\%02X'%v).encode() for v in data)
STRING=re.compile(rb'^(@s\.[0-9]+) = private unnamed_addr global \{i64, i64, i64, \[([0-9]+) x i8\]\} \{i64 ([0-9]+), i64 0, i64 ([0-9]+), \[([0-9]+) x i8\] c"(.*)"\}, align 8$',re.M)

def normalize_paths(text,home,same_lib,name):
 witnesses=[]
 if text is None:return None,witnesses
 prefix=str(home).encode()+b'/'
 def sub(m):
  data=decode_llvm(m[6]);n=int(m[2]);length=int(m[3]);chars=int(m[4])
  assert n==int(m[5])==len(data) and data.endswith(b'\0') and length==n-1
  assert chars==(n if all(v<128 for v in data)else 0)
  if prefix not in data:return m[0]
  original=data;found=[]
  def path(match):
   suffix=match[1];key=suffix.decode()
   if key in same_lib:
    found.append({'side':name,'symbol':m[1].decode(),'file':key,'file_sha256':same_lib[key]})
    return suffix
   return match[0]
  data=re.sub(re.escape(prefix)+rb'(lib/[A-Za-z0-9_./-]+\.py)(?![A-Za-z0-9_./-])',path,data)
  if prefix in data or data==original:return m[0]
  witnesses.extend(found)
  newn=len(data);newchars=newn if all(v<128 for v in data)else 0
  return m[1]+f' = private unnamed_addr global {{i64, i64, i64, [{newn} x i8]}} {{i64 {newn-1}, i64 0, i64 {newchars}, [{newn} x i8] c"'.encode()+encode_llvm(data)+b'"}, align 8'
 return STRING.sub(sub,text),witnesses

def main():
 p=argparse.ArgumentParser();p.add_argument('output',type=pathlib.Path);a=p.parse_args();root=a.output
 meta=json.loads((root/'inputs.json').read_text());homes={k:pathlib.Path(v['root'])for k,v in meta['identities'].items()}
 captured={side:{name:digest for name,mode,digest in details['tracked_inputs'] if mode & 0o170000==0o100000}for side,details in meta['identities'].items()}
 all_inputs={side:{name:(mode,digest)for name,mode,digest in details['tracked_inputs']}for side,details in meta['identities'].items()}
 def case_hash(name):
  # Git tracks symlink text; bind its live target spelling back to that captured hash,
  # then use only the final tracked file's captured content digest.
  for _ in range(32):
   mode,digest=all_inputs['new'][name]
   if mode & 0o170000==0o100000:return digest
   assert mode & 0o170000==0o120000, 'unsupported case file mode'
   target=os.readlink(homes['new']/name)
   assert sha(os.fsencode(target))==digest, 'case symlink differs from captured input'
   assert not os.path.isabs(target), 'absolute case symlink cannot be resolved from captured inputs'
   name=os.path.normpath(str(pathlib.PurePosixPath(name).parent/target))
   assert not name.startswith('../'), 'case symlink leaves audited checkout'
  raise AssertionError('case symlink cycle')
 same_lib={name:digest for name,digest in captured['old'].items() if name.startswith('lib/')and name.endswith('.py')and captured['new'].get(name)==digest}
 summary=json.loads((root/'summary.json').read_text())
 records=[json.loads(x)for x in (root/'results.jsonl').read_text().splitlines()]
 assert summary['inputs_unchanged']is True, 'audited inputs changed during execution'
 assert summary['expected']==summary['completed']==len(meta['cases'])==len(records), 'incomplete audit'
 assert sorted(r['index']for r in records)==list(range(1,len(records)+1)), 'missing or repeated result index'
 assert all(r['case']==meta['cases'][r['index']-1]for r in records), 'result case differs from input corpus'
 rows=[]
 for r in sorted(records,key=lambda r:r['index']):
  d=root/'cases'/f'{r["index"]:05d}';witnesses=[]
  assert json.loads((d/'result.json').read_text())==r, 'result journal differs from case record'
  assert r['source_sha256']==case_hash(r['case']), 'audited case source differs from captured inputs'
  messages={};irs={}
  for side in('old','new'):
   messages[side]=(d/(side+'.msg')).read_bytes()
   assert sha(messages[side])==r[side]['message_sha256'], 'retained message hash differs'
   irpath=d/(side+'.ll.gz')
   irs[side]=gzip.decompress(irpath.read_bytes())if r[side]['ir_sha256']is not None else None
   assert (irs[side]is None and not irpath.exists())or(sha(irs[side])==r[side]['ir_sha256']and len(irs[side])==r[side]['ir_bytes']), 'retained IR identity differs'
  assert r['statuses_equal']==(r['old']['status']==r['new']['status']), 'status comparison mismatch'
  assert r['messages_equal']==(messages['old']==messages['new']), 'message comparison mismatch'
  assert r['ir_equal']==(irs['old']==irs['new']), 'IR comparison mismatch'
  assert r['same']==(r['statuses_equal']and r['messages_equal']and r['ir_equal']), 'raw comparison mismatch'
  assert r['new_rejection']==(r['old']['status']==0 and r['new']['status']!=0), 'new rejection comparison mismatch'
  assert r['acceptance_gain']==(r['old']['status']!=0 and r['new']['status']==0), 'acceptance comparison mismatch'
  def normal_ir(name):
   text,found=normalize_paths(irs[name],homes[name],same_lib,name)
   witnesses.extend(found)
   return text
  if r['old']['timed_out']or r['new']['timed_out']:category='timeout'
  elif any(r[side]['status']not in(0,1)for side in('old','new')):category='abnormal_exit'
  elif any(r[side]['status']==0 and not r[side]['ir_bytes']for side in('old','new')):category='missing_ir'
  elif r['same']:category='identical_raw'
  elif r['new_rejection']:category='new_rejection'
  elif r['acceptance_gain']:category='acceptance_gain'
  elif r['statuses_equal'] and r['messages_equal'] and normal_ir('old')==normal_ir('new'):category='proven_checkout_string_only'
  else:category='requires_review'
  rows.append({'index':r['index'],'case':r['case'],'category':category,'path_witnesses':witnesses})
 summary={c:sum(r['category']==c for r in rows)for c in sorted({r['category']for r in rows})}
 out={'summary':summary,'rows':rows,'normalization':'Only exact LLVM string declarations; decoded lengths/character-cache fields verified; each removed checkout prefix points to identical captured tracked lib/*.py hashes in both homes. Complete case identities, raw statuses/messages/IR and their retained hashes were checked before classification.'}
 (root/'classification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
