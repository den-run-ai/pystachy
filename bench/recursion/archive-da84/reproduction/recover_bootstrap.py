import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(repo):
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=repo).decode().split('\0')
    paths = {name for name in names if name and (name in ['pystachy.py', 'runtime.c', 'runtime.py', 'pyembed.c', 'pyext.c'] or name.startswith(('src/', 'lib/', 'ryu/', 'mpz/')))}
    for folder in ['src', 'lib', 'ryu', 'mpz']:
        paths.update(str(p.relative_to(repo)) for p in (repo/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {name: digest(repo/name) for name in sorted(paths) if (repo/name).is_file() and not name.endswith('.pyc')}


repo = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
report = {'source': str(repo), 'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(), 'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=repo, text=True).strip(), 'before': snapshot(repo), 'status': 'running', 'python': sys.version, 'llvm': os.environ.get('PYSTACHY_LLVM'), 'fresh_after_workspace_cleanup': True}
def save():
    tmp = out/'bootstrap.json.tmp'
    tmp.write_text(json.dumps(report, indent=2)+'\n')
    tmp.replace(out/'bootstrap.json')
save()
env = {k:v for k,v in os.environ.items() if not k.startswith('PYSTACHY_')}
env.update(PYSTACHY_LLVM=os.environ['PYSTACHY_LLVM'], PYSTACHY_CACHE=str(out/'cache'), PYSTACHY_JOBS='2', LC_ALL='C')
start=time.monotonic()
with (out/'bootstrap.log').open('w') as log:
    result=subprocess.run(['make', 'PY='+sys.executable], cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT)
report.update(exit_code=result.returncode, seconds=time.monotonic()-start, after=snapshot(repo))
report['source_identity_stable']=report['before']==report['after']
report['artifacts']={}
for name in ['pystachy', 'build/pystachy1', 'build/pystachy2', 'build/stage1.ll', 'build/stage2.ll', 'build/stage3.ll', 'build/rt1.ll', 'build/rt2.ll', 'build/rt3.ll']:
    p=repo/name
    if p.is_file():
        report['artifacts'][name]={'sha256':digest(p), 'bytes':p.stat().st_size}
        if p.suffix=='.ll':
            report['artifacts'][name]['lines']=p.read_bytes().count(b'\n')
report['log_sha256']=digest(out/'bootstrap.log')
report['status']='complete' if result.returncode==0 and report['source_identity_stable'] and len(report['artifacts'])==9 else 'failed'
save()
print(json.dumps({k:report[k] for k in ['commit','tree','exit_code','seconds','source_identity_stable','status','artifacts']}), flush=True)
sys.exit(0 if report['status']=='complete' else 1)
