"""Record the final scalar follow-up's validation, sequentially and fail closed."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

TASK = Path('/workspace/scratch/9c9ef915af51')
ROOT = TASK / 'pystachy'
LLVM = Path('/workspace/scratch/e98dc1e3e6cd/toolchains/ubuntu-18.1.3-1ubuntu1-amd64/usr/lib/llvm-18/bin')
DEV = Path('/workspace/scratch/e98dc1e3e6cd/dev/bin')
ENV = {k: v for k, v in os.environ.items() if not k.startswith('PYSTACHY_')}
ENV.update(PATH=str(DEV) + ':' + ENV['PATH'], PYSTACHY_LLVM=str(LLVM), PYSTACHY_JOBS='2')
OUT = TASK / 'final-validation.json'
REPORT = {'complete': False, 'stages': []}


def save():
    OUT.write_text(json.dumps(REPORT, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(name, command, extra=None):
    begin = time.perf_counter()
    result = subprocess.run(command, cwd=ROOT, env={**ENV, **(extra or {})},
                            text=True, capture_output=True, timeout=1200)
    log = TASK / ('final-' + name + '.log')
    log.write_text(result.stdout + result.stderr)
    REPORT['stages'].append({'name': name, 'command': command, 'environment_overrides': extra or {},
                             'returncode': result.returncode, 'wall_seconds': time.perf_counter() - begin,
                             'log': log.name, 'log_sha256': digest(log),
                             'stdout': result.stdout, 'stderr': result.stderr})
    save()
    print(name, result.returncode, flush=True)
    result.check_returncode()
    return result


save()
REPORT['source_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
REPORT['source_sha256'] = {str(p.relative_to(ROOT)): digest(p) for p in
                          [ROOT / 'pystachy.py', ROOT / 'runtime.c', ROOT / 'runtime.py'] + sorted((ROOT / 'src').rglob('*.py'))}
REPORT['compiler_sha256'] = digest(ROOT / 'pystachy')
before = json.loads((TASK / 'pre-isclose-source.json').read_text())
REPORT['compiler_fixed_point_ir_sha256'] = digest(ROOT / 'build/stage3.ll')
assert REPORT['compiler_fixed_point_ir_sha256'] == before['sha256']['build/stage3.ll']
old = (TASK / 'pre-isclose-runtime.ll').read_text()
new = (ROOT / 'build/rt3.ll').read_text()
pattern = r'^define[^\n]*@pys_m_isclose\([^\n]*\)[^\n]*\{\n.*?^\}'
assert len(re.findall(pattern, old, re.M | re.S)) == len(re.findall(pattern, new, re.M | re.S)) == 1
assert re.sub(pattern, 'ISCLOSE', old, flags=re.M | re.S) == re.sub(pattern, 'ISCLOSE', new, flags=re.M | re.S)
REPORT['runtime_ir_delta'] = {'only_changed_definition': 'pys_m_isclose', 'all_other_bytes_equal': True,
                              'before_sha256': digest(TASK / 'pre-isclose-runtime.ll'),
                              'after_sha256': digest(ROOT / 'build/rt3.ll')}
save()

record('contracts', ['python3.13', 'tools/check_runtime.py'])
record('ruff', ['ruff', 'check', 'runtime.py', 'bench/runtime_subset'])
record('rtcheck', ['python3.13', 'tools/rtcheck.py', '5000', '7'])
record('numeric-contract', ['python3.13', 'bench/runtime_subset/numeric_contract.py',
                           '--before', str(TASK / 'baseline'), '--after', str(ROOT),
                           '--compiler', str(ROOT / 'pystachy'), '--json', str(TASK / 'numeric-contract-published.json')])
cases = (TASK / 'focused-cases.txt').read_text().splitlines()
assert len(cases) == 34
record('native', ['tests/run.sh', './pystachy', 'jit aot', *cases])
record('gc', ['tests/run.sh', './pystachy', 'jit aot', *cases[:6]], {'PYSTACHY_GC_STRESS_PROGRAM': '1'})
record('opt-off', ['tests/run.sh', './pystachy', 'jit aot', *cases[:6]], {'PYSTACHY_OPT': '-listget'})
record('hosted', ['tests/run.sh', 'python3.13 -m pystachy', 'jit aot', *cases[:6]])

asan = {'PYSTACHY_JOBS': '1', 'PYSTACHY_CFLAGS': '-fsanitize=address',
        'PYSTACHY_CACHE': str(TASK / 'asan-program-cache'),
        'ASAN_OPTIONS': 'detect_leaks=0:detect_stack_use_after_return=0'}
preload = str(LLVM.parent / 'lib/clang/18/lib/linux/libclang_rt.asan-x86_64.so')
record('asan-jit', ['tests/run.sh', './pystachy', 'jit', *cases[:6]], {**asan, 'LD_PRELOAD': preload})
aot_results = []
for case in cases[:6]:
    source = ROOT / case
    exe = TASK / ('final-asan-' + source.stem)
    record('asan-build-' + source.stem, ['./pystachy', 'build', case, '-o', str(exe)], asan)
    inp = source.with_suffix('.in')
    result = subprocess.run([str(exe), 'a1', 'a2'], cwd=ROOT, env={**ENV, **asan},
                            input=inp.read_bytes() if inp.exists() else b'', capture_output=True, timeout=120)
    output = result.stdout + f'[exit {result.returncode}]\n'.encode()
    expected = source.with_suffix('.out').read_bytes()
    passed = output == expected and not result.stderr
    aot_results.append({'case': case, 'returncode': result.returncode,
                        'stdout_sha256': hashlib.sha256(output).hexdigest(),
                        'expected_sha256': hashlib.sha256(expected).hexdigest(),
                        'stderr': result.stderr.decode(), 'passed': passed})
    REPORT['asan_aot'] = aot_results
    save()
    assert passed, (case, output, result.stderr)

record('runtime-ir-before', [str(TASK / 'baseline/pystachy'), 'rt', 'runtime.py', '-o', str(TASK / 'final-runtime-before.ll')])
record('runtime-ir-after', ['./pystachy', 'rt', 'runtime.py', '-o', str(TASK / 'final-runtime-after.ll')])
prior = (TASK / 'final-runtime-before.ll').read_text()
current = (TASK / 'final-runtime-after.ll').read_text()
loads = re.compile(r'(?m)^  (?P<field>%t\d+) = getelementptr inbounds \{i64, i64, ptr\}, ptr (?P<seq>[^,\n]+), i64 0, i32 2\n'
                   r'  (?P<data>%t\d+) = load ptr, ptr (?P=field)\n'
                   r'  (?P<elem>%t\d+) = getelementptr inbounds i64, ptr (?P=data), i64 (?P<idx>[^\n]+)\n'
                   r'  (?P<res>%t\d+) = load i64, ptr (?P=elem)\n')
restorations = []
def restore(match):
    call = f"  {match['res']} = call i64 @pys_list_get(ptr {match['seq']}, i64 {match['idx']})\n"
    if call in prior:
        restorations.append({'old_call': call.rstrip(), 'new_instructions': match[0].splitlines()})
        return call
    return match[0]
restored = loads.sub(restore, current)
assert len(restorations) == 1 and restored == prior
REPORT['final_runtime_ir_comparison'] = {'case': 'runtime.py', 'restorations': restorations,
                                         'all_other_bytes_equal': True,
                                         'before_sha256': digest(TASK / 'final-runtime-before.ll'),
                                         'after_sha256': digest(TASK / 'final-runtime-after.ll')}
REPORT['complete'] = True
save()
print('final validation complete', flush=True)
