"""Build and compare native AOT graph instruction counts on another host.

Requires clean source checkouts, matching prebuilt native compilers, LLVM 18.1.3,
Valgrind 3.22.0, and the adjacent frozen workload.py/runner.py. This reproduces
the experiment protocol, not identical addresses or instruction totals.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess

from runner import active_work, digest, git, sanitized_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main', type=Path, required=True, help='clean 46fd5353 checkout (or guard-only f38555e)')
    parser.add_argument('--candidate', type=Path, required=True, help='clean a03095f4 runtime candidate checkout')
    parser.add_argument('--compiler', type=Path, required=True, help='native compiler built from unchanged 46fd5353 compiler sources')
    parser.add_argument('--llvm', type=Path, required=True)
    parser.add_argument('--library-path', default='')
    parser.add_argument('--valgrind', type=Path, default=Path(shutil.which('valgrind') or 'valgrind'))
    parser.add_argument('--annotate', type=Path, default=Path(shutil.which('callgrind_annotate') or 'callgrind_annotate'))
    parser.add_argument('--valgrind-lib', default='')
    parser.add_argument('--lock', type=Path, required=True, help='shared with all other build/timing sessions')
    parser.add_argument('--output', type=Path, required=True, help='new output directory')
    parser.add_argument('--cpu', type=int, default=0)
    args = parser.parse_args()
    source = Path(__file__).resolve().with_name('workload.py')
    assert digest(source) == '2546632715f4df66b2953200f1a41c9d52671e4eee416c9d53a9307acc6dd388'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    homes = {'main': args.main.resolve(), 'cand': args.candidate.resolve()}
    compiler = args.compiler.resolve()
    env, removed = sanitized_environment(os.environ)
    env.update(PYSTACHY_LLVM=str(args.llvm.resolve()), LD_LIBRARY_PATH=args.library_path,
               PYTHONHASHSEED='0', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    if args.valgrind_lib:
        env['VALGRIND_LIB'] = args.valgrind_lib
    records = {'source_sha256': digest(source), 'compiler_sha256': digest(compiler), 'builds': {}, 'profiles': []}
    args.lock.parent.mkdir(parents=True, exist_ok=True)
    with args.lock.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.sched_setaffinity(0, {args.cpu})

        def run(command, environment, cwd):
            busy = active_work()
            if busy:
                raise RuntimeError('Deferred: foreign build/timing work: ' + json.dumps(busy))
            result = subprocess.run(command, env=environment, cwd=cwd, capture_output=True, text=True, timeout=180)
            record = {'command': list(map(str, command)), 'stdout': result.stdout, 'stderr': result.stderr,
                      'returncode': result.returncode, 'foreign_work_after': active_work()}
            if result.returncode or record['foreign_work_after']:
                raise RuntimeError(json.dumps(record))
            return record

        for label, home in homes.items():
            assert not git(home, 'status', '--porcelain'), home
            target = output / label
            target.mkdir()
            build_env = dict(env, PYSTACHY_HOME=str(home), PYSTACHY_CACHE=str(target / 'cache'))
            record = run([compiler, 'build', source, '-o', target / 'graph'], build_env, home)
            record.update(commit=git(home, 'rev-parse', 'HEAD'), runtime_sha256=digest(home / 'runtime.c'),
                          binary_sha256=digest(target / 'graph'))
            records['builds'][label] = record
        for sample in range(3):
            for label in (['main', 'cand'] if sample % 2 == 0 else ['cand', 'main']):
                profile = output / f'{label}-{sample}.out'
                record = run([args.valgrind, '--tool=callgrind', '--callgrind-out-file=' + str(profile),
                              output / label / 'graph', 'graph', '4000'], env, output)
                assert record['stdout'].split()[0] == '670230', record
                record.update(label=label, sample=sample)
                records['profiles'].append(record)
                (output / 'records.json').write_text(json.dumps(records, indent=2) + '\n')
                for inclusive in ('yes', 'no'):
                    annotated = subprocess.run([args.annotate, '--inclusive=' + inclusive, '--auto=no', '--threshold=100', profile],
                                               env=env, capture_output=True, text=True, check=True)
                    (output / f'{label}-{sample}-inclusive-{inclusive}.txt').write_text(annotated.stdout)
    for label, home in homes.items():
        assert not git(home, 'status', '--porcelain'), home
        assert git(home, 'rev-parse', 'HEAD') == records['builds'][label]['commit']
        assert digest(home / 'runtime.c') == records['builds'][label]['runtime_sha256']
    print(output)


if __name__ == '__main__':
    main()
