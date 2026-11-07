#!/usr/bin/env python3
"""Scratch alpha-release IR/acceptance audit; preserve every raw outcome and IR."""
import argparse,concurrent.futures,difflib,gzip,hashlib,json,os,pathlib,subprocess,time
PATTERNS=['pystachy.py','runtime.py','tests/programs/*/*.py','tests/deviations/*.py','bench/*.py','bench/pyperformance/*.py','tests/ir/*.py','tests/errors/*/*.py']
def sha(data):return hashlib.sha256(data).hexdigest()
def run(cmd,cwd,env=None,timeout=30):
 return subprocess.run(cmd,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
def tracked(root):
 names=run(['git','ls-files','-z'],root).stdout.split(b'\0');rows=[]
 for name in sorted(x for x in names if x):
  p=root/os.fsdecode(name)
  data=os.fsencode(os.readlink(p)) if p.is_symlink() else p.read_bytes()
  rows.append([os.fsdecode(name),p.lstat().st_mode & 0o177777,sha(data)])
 return rows
def identity(root,binary):
 return {'root':str(root),'head':run(['git','rev-parse','HEAD'],root).stdout.decode().strip(),'tree':run(['git','rev-parse','HEAD^{tree}'],root).stdout.decode().strip(),
  'status':run(['git','status','--porcelain=v1','--untracked-files=all'],root).stdout.decode(),
  'tracked_inputs':tracked(root),'binary':str(binary),'binary_sha256':sha(binary.read_bytes())}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--root',type=pathlib.Path,required=True);p.add_argument('--old-root',type=pathlib.Path,required=True)
 p.add_argument('--old',type=pathlib.Path);p.add_argument('--new',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path,required=True)
 p.add_argument('--llvm');p.add_argument('--jobs',type=int,default=2);p.add_argument('--timeout',type=float,default=180);p.add_argument('--cases',nargs='+');p.add_argument('--ircheck',choices=['0','1'],default='1')
 a=p.parse_args();a.root=a.root.resolve();a.old_root=a.old_root.resolve();a.output=a.output.resolve()
 if a.jobs not in (1,2):p.error('one or two workers required')
 if a.output.exists():p.error('output must be new to avoid overwriting evidence')
 a.output.mkdir(parents=True);(a.output/'cases').mkdir()
 old=(a.old or a.old_root/'pystachy').resolve();new=(a.new or a.root/'pystachy').resolve()
 identities={'old':identity(a.old_root,old),'new':identity(a.root,new)}
 cases=a.cases or [str(f.relative_to(a.root)) for pattern in PATTERNS for f in sorted(a.root.glob(pattern)) if f.is_file()]
 assert len(cases)==len(set(cases))
 env={k:v for k,v in os.environ.items() if not k.startswith('PYSTACHY_') and k not in ('PYTHONPATH','PYTHONHOME')}
 env.update(LC_ALL='C',PYSTACHY_IRCHECK=a.ircheck,PYSTACHY_JOBS='1')
 if a.llvm:env['PYSTACHY_LLVM']=a.llvm
 metadata={'format':1,'kind':'native compiler differential IR/acceptance audit','identities':identities,'cases':cases,'environment':{k:v for k,v in env.items() if k.startswith('PYSTACHY_') or k=='LC_ALL'},'workers':a.jobs,'per_compile_timeout_seconds':a.timeout,'created_at_unix':time.time()}
 (a.output/'inputs.json').write_text(json.dumps(metadata,indent=2)+'\n')
 def one(item):
  i,case=item;d=a.output/'cases'/f'{i:05d}';d.mkdir();mp=''
  sidecar=(a.root/case).with_suffix('.path')
  if sidecar.exists():
   prep=run(['sh','tests/prepare_path.sh',case,str(d)],a.root,env)
   (d/'prepare.msg').write_bytes(prep.stdout)
   if prep.returncode:raise RuntimeError(f'import path preparation failed: {case}')
   mp=prep.stdout.decode().rstrip('\n')
  how='rt' if case=='runtime.py' or pathlib.Path(case).name.startswith('rtmode_') else 'ir'
  results={};contents={}
  for name,compiler,home in [('old',old,a.old_root),('new',new,a.root)]:
   ir=d/(name+'.ll');e=dict(env,PYSTACHY_HOME=str(home),PYSTACHY_PATH=mp)
   cmd=[str(compiler),how,case,'-o',str(ir)];t=time.monotonic();timedout=False
   try:r=run(cmd,a.root,e,a.timeout);code=r.returncode;msg=r.stdout
   except subprocess.TimeoutExpired as exc:timedout=True;code=124;msg=(exc.stdout or b'')+b'\nAUDIT: subprocess timeout\n'
   elapsed=time.monotonic()-t;(d/(name+'.msg')).write_bytes(msg);data=ir.read_bytes() if ir.exists() else None
   if data is not None:
    with gzip.open(d/(name+'.ll.gz'),'wb',compresslevel=1)as f:f.write(data)
    ir.unlink()
   results[name]={'command':cmd,'home':str(home),'path':mp,'status':code,'timed_out':timedout,'seconds':elapsed,'message_sha256':sha(msg),'ir_sha256':sha(data) if data is not None else None,'ir_bytes':len(data) if data is not None else None}
   contents[name]=(msg,data)
  om,oi=contents['old'];nm,ni=contents['new'];statuses_equal=results['old']['status']==results['new']['status'];messages_equal=om==nm;ir_equal=oi==ni
  if not messages_equal:
   (d/'messages.diff').write_bytes(b''.join(difflib.diff_bytes(difflib.unified_diff,om.splitlines(keepends=True),nm.splitlines(keepends=True),fromfile=b'old',tofile=b'new')))
  if not ir_equal and oi is not None and ni is not None:
   with gzip.open(d/'ir.diff.gz','wb',compresslevel=1)as f:
    for line in difflib.diff_bytes(difflib.unified_diff,oi.splitlines(keepends=True),ni.splitlines(keepends=True),fromfile=b'old',tofile=b'new'):f.write(line)
  record={'index':i,'case':case,'source_sha256':sha((a.root/case).read_bytes()),'mode':how,'old':results['old'],'new':results['new'],'same':statuses_equal and messages_equal and ir_equal,'statuses_equal':statuses_equal,'messages_equal':messages_equal,'ir_equal':ir_equal,'new_rejection':results['old']['status']==0 and results['new']['status']!=0,'acceptance_gain':results['old']['status']!=0 and results['new']['status']==0}
  (d/'result.json').write_text(json.dumps(record,indent=2)+'\n');return record
 results=[]
 with (a.output/'results.jsonl').open('w')as log,concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs)as pool:
  futures=[pool.submit(one,item)for item in enumerate(cases,1)]
  for f in concurrent.futures.as_completed(futures):
   record=f.result();results.append(record);log.write(json.dumps(record)+'\n');log.flush()
   if len(results)%100==0:print(f'completed {len(results)}/{len(cases)}; raw differences {sum(not r["same"] for r in results)}',flush=True)
 unchanged=tracked(a.root)==identities['new']['tracked_inputs'] and tracked(a.old_root)==identities['old']['tracked_inputs']
 unchanged=unchanged and sha(old.read_bytes())==identities['old']['binary_sha256'] and sha(new.read_bytes())==identities['new']['binary_sha256']
 summary={'expected':len(cases),'completed':len(results),'inputs_unchanged':unchanged,'identical_raw':sum(r['same']for r in results),'raw_differences':sum(not r['same']for r in results),'new_rejections':[r['case']for r in results if r['new_rejection']],'acceptance_gains':[r['case']for r in results if r['acceptance_gain']],'timeouts':[r['case']for r in results if r['old']['timed_out']or r['new']['timed_out']],'abnormal_exits':[r['case']for r in results if any(r[side]['status']not in(0,1)for side in('old','new'))],'created_at_unix':time.time()}
 summary['missing_ir']=[r['case']for r in results if any(r[side]['status']==0 and not r[side]['ir_bytes']for side in('old','new'))]
 (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)
 return int(not unchanged or len(results)!=len(cases) or bool(summary['timeouts']) or bool(summary['abnormal_exits']) or bool(summary['missing_ir']) or bool(summary['new_rejections']))
if __name__=='__main__':raise SystemExit(main())
