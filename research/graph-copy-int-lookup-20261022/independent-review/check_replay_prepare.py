from pathlib import Path
import hashlib,json,os,shlex,subprocess,tempfile
source=Path('/workspace/scratch/5b514d4819ab/evidence/research/graph-copy-int-lookup-20261022')
repo=Path('/workspace/scratch/5b514d4819ab/pystachy')
py='/root/.local/share/uv/python/cpython-3.13.16-linux-x86_64-gnu/bin/python3.13'
llvm=Path('/workspace/scratch/b1b1cddbdc9c/llvm18/usr/lib/llvm-18/bin')
libs=Path('/workspace/scratch/b1b1cddbdc9c/llvm18/usr/lib/x86_64-linux-gnu')
root=Path(tempfile.mkdtemp(prefix='graph-replay-review-'))
out=root/'replay space'
before={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
env=dict(os.environ,PATH=str(Path(py).parent)+':'+os.environ['PATH'])
args=[py,str(source/'prepare_replay.py'),'--repo','pystachy','--output',str(out),'--llvm',os.path.relpath(llvm,repo.parent),'--library-path',os.path.relpath(libs,repo.parent),'--python','python3.13','--cpu',str(min(os.sched_getaffinity(0)))]
p=subprocess.run(args,cwd=repo.parent,env=env,capture_output=True,text=True,check=True)
print(p.stdout,end='')
d=json.loads((out/'manifest.json').read_text())
assert d['python']==py
assert d['repository']==str(repo)
assert d['llvm']==str(llvm)
assert d['library_path']==str(libs)
assert d['frozen_main']=='32d7c40b330e8306a7f391a4a4adad735f594d37'
head='7509f866530f67de2d20dd724b2ab352b8f6863e'
assert head in d['revisions'] and all(x['head']==head for x in d['comparisons'])
assert '199d50fe6815668486be5de764a339ac4f30c65c' not in json.dumps(d)
assert all(set(v)=={'sha','lineage'} for v in d['revisions'].values())
for spec in d['workloads'].values():
 path=out/spec['source']; assert path.is_relative_to(out)
 assert hashlib.sha256(path.read_bytes()).hexdigest()==spec['source_sha256']
for name,spec in d['toolchain'].items():assert hashlib.sha256((llvm/name).read_bytes()).hexdigest()==spec['sha256']
cmd=shlex.split(p.stdout.split('Run: ',1)[1]);assert cmd==[py,str(out/'runner.py'),str(out/'manifest.json'),'--max-comparisons','2','--max-new-builds','3']
repeat=subprocess.run(args,cwd=repo.parent,env=env,capture_output=True,text=True)
assert repeat.returncode==2 and 'output must be a new directory' in repeat.stderr
missing=root/'missing-python-output';bad=args.copy();bad[bad.index('--output')+1]=str(missing);bad[bad.index('--python')+1]='nonexistent-python-replay-review'
failure=subprocess.run(bad,cwd=repo.parent,env=env,capture_output=True,text=True)
assert failure.returncode==2 and not missing.exists()
after={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
assert before==after
print('PASS: paths, published mapping, source/toolchain hashes, shell quoting, non-overwrite, failure cleanup; original evidence unchanged')
print('No runner build or timing invoked; output:',out)
