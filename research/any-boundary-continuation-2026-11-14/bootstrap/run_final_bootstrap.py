"""Build all native fixed points from a frozen integration commit."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

TASK = Path('/workspace/scratch/1a96cd11db0d')
ROOT = TASK / 'pystachy'
OUT = TASK / 'final-bootstrap'
PY = '/workspace/scratch/c2b093657c17/dev-venv/bin/python'
LLVM = '/workspace/scratch/c2b093657c17/toolchains/llvm18/payload/usr/lib/llvm-18/bin'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


expected = sys.argv[1]
assert git('rev-parse', 'HEAD') == expected
assert not git('status', '--porcelain')
OUT.mkdir(exist_ok=True)
paths = ['src', 'lib', 'pystachy.py', 'pystachy_cli.py', 'pystachy_toolchain.py',
         'runtime.c', 'runtime.py', 'lljit.c', 'pyext.c', 'pyembed.c', 'ryu', 'mpz']
inputs = {name: sha(ROOT / name) for name in git('ls-files', '--', *paths).splitlines()
          if (ROOT / name).is_file()}
env = {key: value for key, value in os.environ.items()
       if not key.startswith('PYSTACHY_') and key not in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONOPTIMIZE', 'LD_LIBRARY_PATH')}
env.update({'PATH': str(Path(PY).parent) + ':/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            'PYSTACHY_LLVM': LLVM, 'PYSTACHY_JOBS': '2',
            'PYSTACHY_CACHE': str(OUT / 'runtime-cache')})
command = ['make', '-B', 'pystachy', 'PY=' + PY, 'BOOTSTRAP_AOT_OPT=0']
manifest = {'commit': expected, 'tree': git('rev-parse', 'HEAD^{tree}'),
            'command': command, 'native_input_hashes': inputs,
            'environment': {key: value for key, value in env.items() if key.startswith('PYSTACHY_') or key == 'PATH'},
            'temporary_tier': 0, 'final_tier': 2}
(OUT / 'inputs.json').write_text(json.dumps(manifest, indent=2) + '\n')
started = time.time()
with (OUT / 'bootstrap.log').open('w') as log:
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=840)
manifest['elapsed_seconds'] = time.time() - started
manifest['exit_code'] = result.returncode
manifest['log_sha256'] = sha(OUT / 'bootstrap.log')
manifest['final_commit'] = git('rev-parse', 'HEAD')
manifest['final_status'] = git('status', '--porcelain')
manifest['native_inputs_unchanged'] = all(sha(ROOT / name) == value for name, value in inputs.items())
if result.returncode == 0:
    names = ['stage1.ll', 'stage2.ll', 'stage3.ll', 'rt1.ll', 'rt2.ll', 'rt3.ll']
    manifest['fixedpoints'] = {name: sha(ROOT / 'build' / name) for name in names}
    assert len({manifest['fixedpoints'][name] for name in names[:3]}) == 1
    assert len({manifest['fixedpoints'][name] for name in names[3:]}) == 1
    manifest['binary_sha256'] = sha(ROOT / 'pystachy')
    for key, name in [('compiler_ir_lines', 'stage1.ll'), ('runtime_ir_lines', 'rt1.ll')]:
        with (ROOT / 'build' / name).open('rb') as source:
            manifest[key] = sum(1 for _ in source)
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
assert manifest['final_commit'] == expected and not manifest['final_status'] and manifest['native_inputs_unchanged']
print(json.dumps({key: value for key, value in manifest.items() if key not in ('native_input_hashes', 'environment')}, indent=2))
raise SystemExit(result.returncode)
