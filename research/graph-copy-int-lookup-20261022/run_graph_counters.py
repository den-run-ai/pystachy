"""Untimed, isolated AOT allocation/probe profiles for baseline and candidate.

Run after native builds and native performance timing finish. This script never
modifies either input checkout. It exports their committed trees, instruments
runtime.c in separate homes, rebuilds AOT programs with separate caches and
reports processing counters (snapshot 2 minus snapshot 1). Instrumented elapsed
times are deliberately omitted from the summary and must not support speed claims.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time


HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parent
DEFAULT_WORKLOAD = Path('/workspace/scratch/c42abc2bbcbe/replay/sources/dynany_bench.py')
WORKLOAD_HASH = '2546632715f4df66b2953200f1a41c9d52671e4eee416c9d53a9307acc6dd388'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def parse(stderr):
    snapshots = []
    for line in stderr.splitlines():
        if not line.startswith('MEMO_PROFILE '):
            continue
        fields = {}
        for name, value in re.findall(r'(\w+)=([\d,]+)', line):
            fields[name] = [int(x) for x in value.split(',')] if ',' in value else int(value)
        snapshots.append(fields)
    if len(snapshots) != 3 or [s['snapshot'] for s in snapshots] != [0, 1, 2]:
        raise ValueError('expected three ordered counter snapshots')
    return snapshots


def delta(a, b):
    return {k: [y - x for x, y in zip(a[k], b[k])] if isinstance(b[k], list) else b[k] - a[k]
            for k in a if k != 'snapshot'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, default=DEFAULT_ROOT / 'baseline')
    p.add_argument('--head', type=Path, default=DEFAULT_ROOT / 'pystachy')
    p.add_argument('--output', type=Path, required=True, help='new output directory')
    p.add_argument('--expect-base', help='require this exact baseline commit')
    p.add_argument('--expect-head', help='require this exact candidate commit')
    p.add_argument('--workload', type=Path, default=DEFAULT_WORKLOAD)
    p.add_argument('--llvm', type=Path, default=Path('/workspace/scratch/b1b1cddbdc9c/llvm18/usr/lib/llvm-18/bin'))
    p.add_argument('--library-path', default='/workspace/scratch/b1b1cddbdc9c/llvm18/usr/lib/x86_64-linux-gnu')
    p.add_argument('--lock', type=Path, default=Path('/workspace/scratch/b3b3275b86ee/pystachy-performance.lock'))
    p.add_argument('--runner', type=Path, default=Path('/workspace/scratch/c42abc2bbcbe/replay/runner.py'),
                   help='prior runner providing environment sanitization and foreign-work checks')
    p.add_argument('--cpu', type=int, default=0)
    p.add_argument('--prepare-only', action='store_true', help='export/instrument homes without compiling or running')
    a = p.parse_args()
    assert sha(a.workload) == WORKLOAD_HASH, 'unexpected frozen workload bytes'
    spec = importlib.util.spec_from_file_location('historical_runner', a.runner)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    with a.lock.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not a.prepare_only and (busy := runner.active_work()):
            raise RuntimeError('foreign build/timing work active: ' + json.dumps(busy))
        a.output.mkdir(parents=True, exist_ok=False)
        records = []
        env, removed = runner.sanitized_environment(os.environ)
        env.update(PYSTACHY_LLVM=str(a.llvm), LD_LIBRARY_PATH=a.library_path, PYTHONHASHSEED='0')
        os.sched_setaffinity(0, {a.cpu})
        for name, root, expected in [('base', a.base, a.expect_base), ('head', a.head, a.expect_head)]:
            root = root.resolve()
            commit = git(root, 'rev-parse', 'HEAD')
            if expected and commit != expected:
                raise ValueError(f'{name}: revision changed: {commit}')
            status = git(root, 'status', '--porcelain')
            if status:
                raise ValueError(f'{name}: checkout is dirty: {status}')
            compiler = root / 'pystachy'
            compiler_hash = sha(compiler)
            if sha(root / 'build/pystachy2') != compiler_hash:
                raise ValueError(f'{name}: compiler differs from completed native stage two')
            home = a.output / (name + '-home')
            home.mkdir()
            archive = subprocess.check_output(['git', '-C', str(root), 'archive', commit])
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(home, filter='data')
            original_runtime = sha(home / 'runtime.c')
            subprocess.run([sys.executable, str(HERE / 'instrument_graph_nobox.py'),
                            str(home / 'runtime.c'), str(home / 'runtime.c')], check=True)
            record = {'name': name, 'commit': commit, 'tree': git(root, 'rev-parse', 'HEAD^{tree}'),
                      'compiler': str(compiler), 'compiler_sha256': compiler_hash,
                      'input_status': status, 'runtime_sha256': original_runtime,
                      'instrumented_runtime_sha256': sha(home / 'runtime.c'),
                      'instrumentation_sha256': sha(HERE / 'instrument_graph_nobox.py'),
                      'workload_sha256': sha(a.workload), 'instrumented_not_timing': True,
                      'environment_removed': removed, 'cpu': a.cpu}
            records.append(record)
            write(a.output / 'profiles.json', records)
            if a.prepare_only:
                continue
            exe = a.output / ('graph-' + name)
            e = dict(env, PYSTACHY_HOME=str(home), PYSTACHY_CACHE=str(a.output / (name + '-cache')))
            for phase, cmd in [('build', [str(compiler), 'build', str(a.workload), '-o', str(exe)]),
                               ('run', [str(exe), 'graph', '4000'])]:
                if busy := runner.active_work():
                    raise RuntimeError('foreign work active: ' + json.dumps(busy))
                result = subprocess.run(cmd, cwd=home, env=e, capture_output=True, text=True, timeout=180)
                record[phase] = {'command': cmd, 'returncode': result.returncode, 'stdout': result.stdout,
                                 'stderr': result.stderr, 'finished': time.strftime('%FT%TZ', time.gmtime())}
                write(a.output / 'profiles.json', records)
                if result.returncode:
                    raise RuntimeError(f'{name} {phase} failed: ' + result.stderr[-3000:])
                if phase == 'run':
                    if result.stdout.split()[0] != '670230':
                        raise ValueError('graph checksum mismatch')
                    snapshots = parse(result.stderr)
                    record['snapshots'] = snapshots
                    record['construction'] = delta(snapshots[0], snapshots[1])
                    record['processing'] = delta(snapshots[1], snapshots[2])
            record['executable_sha256'] = sha(exe)
            if git(root, 'rev-parse', 'HEAD') != commit or sha(compiler) != compiler_hash or git(root, 'status', '--porcelain'):
                raise ValueError(f'{name}: source/compiler changed during profiling')
            write(a.output / 'profiles.json', records)
        if not a.prepare_only:
            summary = {'instrumented_not_timing': True, 'checksum': '670230',
                       'categories': ['raw-int', 'raw-str', 'Any-int (boxed plus no-box)', 'Any-other', 'typed-other'],
                       'category_counts': ['lookup invocations', 'lookup probe slots', 'hash-matching slots'],
                       'notes': ['slots_total includes lookup and table rebuild/insertion probes, including no-box helper',
                                 'fallback adds both a no-box invocation and the ordinary lookup invocation',
                                 'instrumented elapsed time must not be used as native speed evidence'],
                       'profiles': [{k: r[k] for k in ['name', 'commit', 'processing', 'construction']} for r in records]}
            write(a.output / 'summary.json', summary)
            print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
