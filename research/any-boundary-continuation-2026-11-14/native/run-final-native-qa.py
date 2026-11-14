from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


task = Path('/workspace/scratch/1a96cd11db0d')
repo = task / 'native-final-qa'
out = task / 'native-final-results'
out.mkdir(exist_ok=True)
python = Path('/workspace/scratch/c2b093657c17/dev-venv/bin/python')
llvm = Path('/workspace/scratch/c2b093657c17/toolchains/llvm18/payload/usr/lib/llvm-18/bin')
expected_head = '2df26bde21451abb89cc487f57b0a5531c655b8d'
public_source_commit = 'adf5a12a147649d01018dd49c8167610812ada00'
public_source_tree = '30d991ebec23d92140381b4cd6fe6892a31b5a2b'
bootstrap_path = task / 'final-bootstrap' / 'manifest.json'
bootstrap = json.loads(bootstrap_path.read_text())
assert len(sys.argv) == 2, 'Pass the GO-approved binary SHA256 as the only argument'
expected_binary = sys.argv[1]
assert bootstrap['exit_code'] == 0 and bootstrap['binary_sha256'] == expected_binary
assert bootstrap['commit'] == bootstrap['final_commit'] == expected_head
assert bootstrap['final_status'] == '' and bootstrap['native_inputs_unchanged']
assert bootstrap['tree'] == public_source_tree
assert len({bootstrap['fixedpoints'][x] for x in ('stage1.ll', 'stage2.ll', 'stage3.ll')}) == 1
assert len({bootstrap['fixedpoints'][x] for x in ('rt1.ll', 'rt2.ll', 'rt3.ll')}) == 1
compiled_head = bootstrap['commit']


def git(*args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert git('rev-parse', 'HEAD') == expected_head
assert git('rev-parse', 'HEAD^{tree}') == public_source_tree
assert git('status', '--porcelain') == ''
assert sha(repo / 'pystachy') == expected_binary
native_paths = ['src', 'lib', 'pystachy.py', 'pystachy_cli.py', 'pystachy_toolchain.py',
                'runtime.c', 'runtime.py', 'lljit.c', 'pyext.c', 'pyembed.c', 'ryu', 'mpz']
assert git('diff', '--name-only', compiled_head, expected_head, '--', *native_paths) == ''
tracked_inputs = git('ls-files', '--', *native_paths).splitlines()
hashes = {path: sha(repo / path) for path in tracked_inputs if (repo / path).is_file()}
assert hashes == bootstrap['native_input_hashes']
selection = set()
for pattern in [
    'tests/programs/classes/constructor_*.py',
    'tests/errors/classes/constructor_*.py',
    'tests/programs/generics/generic_constructor_forms.py',
    'tests/programs/inference/dynany_identity_generator*.py',
    'tests/programs/inference/dynany_identity_list*.py',
    'tests/programs/inference/dynany_identity_optional*.py',
    'tests/programs/inference/dynany_identity_vtuple*.py',
    'tests/programs/numbers/python_int_generator*identity.py',
    'tests/programs/numbers/python_int_optional_container_identity.py',
    'tests/deviations/python_int_optional_generator*.py',
]:
    selection.update(str(p.relative_to(repo)) for p in repo.glob(pattern))
selection = sorted(selection)
expected_checks = sum(1 if p.startswith('tests/errors/') else 2 for p in selection)
(out / 'selection.txt').write_text('\n'.join(selection) + '\n')
env = {key: value for key, value in os.environ.items()
       if not key.startswith('PYSTACHY_') and key not in ('PYTHONPATH', 'PYTHONOPTIMIZE', 'LD_LIBRARY_PATH')}
env.update({
    'PATH': f'{python.parent}:{llvm}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    'PYSTACHY_LLVM': str(llvm),
    'PYSTACHY_HOME': str(repo),
    'PYSTACHY_CACHE': str(out / 'runtime-cache'),
    'PYSTACHY_JOBS': '2',
    'PY': str(python),
    'PYTHON': str(python),
    'LD_LIBRARY_PATH': str(llvm.parent / 'lib'),
})
manifest = {
    'commit': expected_head,
    'public_source_commit': public_source_commit,
    'public_source_tree': public_source_tree,
    'tree': git('rev-parse', 'HEAD^{tree}'),
    'compiled_commit': compiled_head,
    'binary_sha256': expected_binary,
    'bootstrap_manifest_sha256': sha(bootstrap_path),
    'bootstrap_manifest': str(bootstrap_path),
    'native_paths_unchanged_since_bootstrap': True,
    'native_input_hashes': hashes,
    'python_version': subprocess.check_output([str(python), '--version'], text=True).strip(),
    'llvm_version': subprocess.check_output([str(llvm / 'clang'), '--version'], text=True).splitlines()[0],
    'selected_cases': len(selection),
    'expected_checks_per_native_pass': expected_checks,
    'selected_paths': selection,
    'environment': {key: env[key] for key in env if key.startswith('PYSTACHY_') or key in ('PY', 'PYTHON', 'PATH', 'LD_LIBRARY_PATH')},
}
(out / 'inputs.json').write_text(json.dumps(manifest, indent=2) + '\n')
tasks = [
    ('native-normal', ['tests/run.sh', './pystachy', 'jit aot', *selection], {}),
    ('native-gc', ['tests/run.sh', './pystachy', 'jit aot', *selection], {'PYSTACHY_GC_STRESS_PROGRAM': '1'}),
    ('runtime-probes', ['make', '-o', 'pystachy', 'listprobe', 'boxprobe'], {}),
    ('ir-contracts', ['make', '-o', 'pystachy', 'check-ir'], {}),
    ('runtime-contracts', ['make', 'check-runtime'], {}),
    ('recordings', ['make', 'check-recordings'], {}),
    ('lint', ['make', 'lint'], {}),
]
results = []
for name, command, overrides in tasks:
    start = time.time()
    print(f'START {name}', flush=True)
    log = out / (name + '.log')
    with log.open('w') as stream:
        try:
            result = subprocess.run(command, cwd=repo, env=env | overrides,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=840)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
            stream.write('\nTIMEOUT after 840 seconds\n')
    text = log.read_text()
    record = {'name': name, 'command': command, 'environment_overrides': overrides,
              'exit_code': code, 'elapsed_seconds': time.time() - start,
              'log': str(log), 'log_sha256': sha(log)}
    if name.startswith('native-'):
        match = re.search(r'(\d+) passed, (\d+) failed', text)
        record['observed_checks'] = {'passed': int(match[1]), 'failed': int(match[2])} if match else None
        record['count_matches'] = bool(match and int(match[1]) == expected_checks and int(match[2]) == 0)
        if not record['count_matches']:
            record['exit_code'] = code or 125
    results.append(record)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(f'END {name} exit={record["exit_code"]} elapsed={record["elapsed_seconds"]:.1f}s', flush=True)
    if record['exit_code']:
        print(text[-6000:], flush=True)
        break
final = {'commit': git('rev-parse', 'HEAD'), 'status': git('status', '--porcelain'),
         'binary_sha256': sha(repo / 'pystachy'),
         'native_inputs_unchanged': all(sha(repo / path) == value for path, value in hashes.items()),
         'results': results}
(out / 'final.json').write_text(json.dumps(final, indent=2) + '\n')
assert final['native_inputs_unchanged'] and final['binary_sha256'] == expected_binary
assert final['commit'] == expected_head and final['status'] == ''
raise SystemExit(0 if len(results) == len(tasks) and all(r['exit_code'] == 0 for r in results) else 1)
