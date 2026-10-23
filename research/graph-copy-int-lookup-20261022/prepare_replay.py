"""Prepare a new Linux replay without modifying recorded evidence or worktrees."""
import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--repo', type=Path, required=True, help='Git clone containing the public revisions, or able to fetch them')
p.add_argument('--output', type=Path, required=True, help='New directory for replay inputs and results')
p.add_argument('--llvm', type=Path, required=True, help='Directory containing the complete LLVM 18.1.3 tools')
p.add_argument('--library-path', default='', help='Colon-separated LLVM shared-library directories')
p.add_argument('--python', default=sys.executable, help='CPython 3.13.16 executable path or command on PATH')
p.add_argument('--cpu', type=int, default=0)
a = p.parse_args()
source = Path(__file__).resolve().parent
out = a.output.resolve()
repo = a.repo.resolve()
llvm = a.llvm.resolve()
python = shutil.which(a.python)
if python is None:
    p.error('Python executable not found: ' + a.python)
python = str(Path(python).absolute())
if out.exists():
    p.error('output must be a new directory: ' + str(out))
if not repo.is_dir():
    p.error('repository directory does not exist: ' + str(repo))
if subprocess.run(['git', '-C', str(repo), 'rev-parse', '--git-dir'], check=False, capture_output=True).returncode:
    p.error('--repo must name a Git clone')
if a.cpu not in os.sched_getaffinity(0):
    p.error('--cpu is outside this process\'s allowed CPU set')
library_path = ':'.join(str(Path(item).resolve()) for item in a.library_path.split(':') if item)
recorded = source / 'manifest-recorded.json'
d = json.loads(recorded.read_text())
old = '199d50fe6815668486be5de764a339ac4f30c65c'
head = '7509f866530f67de2d20dd724b2ab352b8f6863e'
# Validate executable paths before creating output; runner performs the version checks
# and records the actual toolchain before any native compiler build or measurement.
toolchain = {}
for name in ('clang', 'opt', 'lli', 'llvm-link', 'llvm-as'):
    path = llvm / name
    if not path.is_file() or not os.access(path, os.X_OK):
        p.error('missing executable LLVM tool: ' + str(path))
    toolchain[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
d.update(repository=str(repo), output_dir=str(out / 'results'), python=python,
         llvm=str(llvm), library_path=library_path, cpu=a.cpu,
         lock_path=str(out / 'performance.lock'), toolchain=toolchain,
         created=datetime.now(UTC).isoformat(),
         frozen_main=d['comparisons'][0]['base'],
         recorded_manifest_sha256=hashlib.sha256(recorded.read_bytes()).hexdigest())
d['revisions'] = {head if sha == old else sha:
                  {'sha': head if sha == old else sha, 'lineage': value.get('lineage', 'unknown')}
                  for sha, value in d['revisions'].items()}
for comparison in d['comparisons']:
    comparison['head'] = head
    if any(comparison[side] not in d['revisions'] for side in ('base', 'head', 'anchor')):
        p.error('comparison refers to an unregistered revision')
d['notes'] = [('Fresh replay of the recorded graph workload using the published candidate; '
              'native compilers must be rebuilt and measurements collected by runner.py.')]
out.mkdir(parents=True, exist_ok=False)
for name in ('runner.py', 'rss_meter.c'):
    shutil.copy2(source / name, out / name)
shutil.copytree(source / 'sources', out / 'sources')
dpath = out / 'manifest.json'
dpath.write_text(json.dumps(d, indent=2) + '\n')
print('Prepared', dpath)
print('Run:', shlex.join([python, str(out / 'runner.py'), str(dpath),
                          '--max-comparisons', '2', '--max-new-builds', '3']))
