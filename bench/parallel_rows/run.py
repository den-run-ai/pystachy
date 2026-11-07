"""Interleave row-scoring policies on one frozen executable; no CI timing gate."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name('workload.py')
CPYTHON_ENTRY = '''import importlib.util, runpy, sys
spec = importlib.util.spec_from_file_location('parallel', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.modules['parallel'] = module
sys.argv = sys.argv[2:]
runpy.run_path(sys.argv[0], run_name='__main__')
'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, env, directory, timeout, resources):
    metric_path = directory / 'process-metrics.json'
    measured = command
    if resources:
        measured = ['/usr/bin/time', '-f',
                    '{"user_s":%U,"system_s":%S,"max_rss_kib":%M}',
                    '-o', str(metric_path)] + command
    start = time.perf_counter()
    proc = subprocess.run(measured, cwd=ROOT, env=env, text=True,
                          capture_output=True, timeout=timeout, check=False)
    wall = time.perf_counter() - start
    if proc.returncode:
        raise RuntimeError(f'{shlex.join(command)} failed ({proc.returncode}):\n'
                           f'{proc.stdout[-1500:]}\n{proc.stderr[-3500:]}')
    result = {'process_wall_s': wall, 'stderr': proc.stderr}
    if resources:
        result['process_resources'] = json.loads(metric_path.read_text())
    return proc.stdout, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='./pystachy')
    parser.add_argument('--cpython', default=sys.executable)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--rows', default=8192, type=int)
    parser.add_argument('--width', default=32, type=int)
    parser.add_argument('--samples', default=5, type=int)
    parser.add_argument('--batches', default=3, type=int)
    parser.add_argument('--warmups', default=1, type=int)
    parser.add_argument('--workers', default='1,2,4,8')
    parser.add_argument('--timeout', default=600.0, type=float)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--reference-only', action='store_true')
    args = parser.parse_args()
    if args.smoke:
        args.rows, args.width, args.samples, args.batches, args.warmups = 17, 7, 1, 1, 0
    try:
        workers = [int(value) for value in args.workers.split(',')]
    except ValueError:
        parser.error('--workers must be comma-separated integers')
    if (not workers or workers[0] != 1 or len(set(workers)) != len(workers)
            or any(w < 1 or w > 64 for w in workers)):
        parser.error('--workers must start with 1 and contain unique counts from 1 to 64')
    if args.rows < 0 or args.width < 1 or args.samples < 1 or args.batches < 1 or args.warmups < 0 or args.timeout <= 0:
        parser.error('invalid dimensions or repetition/timeout setting')
    compiler, cpython = shlex.split(args.compiler), shlex.split(args.cpython)
    if not compiler or not cpython:
        parser.error('compiler and CPython commands must not be empty')
    env = {k: v for k, v in os.environ.items()
           if (not k.startswith('PYSTACHY_') or k == 'PYSTACHY_LLVM')
           and k not in ('PYTHONPATH', 'PYTHONHOME', 'LD_PRELOAD')}
    paths = [ROOT / p for p in ('pystachy.py', 'runtime.py', 'runtime.c')]
    for pattern in ('src/**/*.py', 'lib/**/*.py', 'ryu/**/*.[ch]', 'mpz/**/*.[ch]', 'bench/parallel_rows/*.py'):
        paths.extend(ROOT.glob(pattern))
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(paths)) if p.is_file()}
    report = {'schema': 1, 'at_utc': datetime.now(timezone.utc).isoformat(),
              'options': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'git_status': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
              'source_sha256': hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
              'source_files': hashes, 'platform': platform.platform(), 'logical_cpus': os.cpu_count(),
              'affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
              'cgroup_cpu_max': Path('/sys/fs/cgroup/cpu.max').read_text() if Path('/sys/fs/cgroup/cpu.max').exists() else None,
              'resources_scope': 'Process resources include construction, warmup and complete output validation; seconds[] times only batches.',
              'reference': {}, 'runs': [], 'status': 'running'}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        temp = args.output.with_suffix('.pending.json')
        temp.write_text(json.dumps(report, indent=2) + '\n')
        temp.replace(args.output)

    with tempfile.TemporaryDirectory(prefix='pystachy-rows-') as tempdir:
        work = Path(tempdir)
        env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_CACHE=str(work / 'cache'))
        reference_command = cpython + ['-I', '-c', CPYTHON_ENTRY, str(ROOT / 'lib/parallel.py'), str(SOURCE)]
        resources = Path('/usr/bin/time').is_file()

        def measure(command, kind, count, batches, warmups):
            output, result = run(command + [kind, str(count), str(args.rows), str(args.width), str(batches), str(warmups)],
                                 env, work, args.timeout, resources)
            seconds = [float(line.split()[1]) for line in output.splitlines() if line.startswith('seconds ')]
            witnesses = [line.partition(' ')[2] for line in output.splitlines() if line.startswith('witness')]
            if (len(seconds) != batches or any(not math.isfinite(x) or x <= 0 for x in seconds)
                    or len(witnesses) != 1 or len(witnesses[0]) != args.rows * 16
                    or re.fullmatch('[0-9a-f]*', witnesses[0]) is None):
                raise ValueError('malformed timing or complete row witness')
            result.update(kind=kind, workers=count, seconds=seconds,
                          kernel_median_s=statistics.median(seconds),
                          witness_sha256=hashlib.sha256(witnesses[0].encode()).hexdigest())
            if kind in report['reference'] and result['witness_sha256'] != report['reference'][kind]['witness_sha256']:
                raise ValueError('output differs from the CPython direct-loop oracle')
            return result

        for kind in ('score', 'affine'):
            report['reference'][kind] = measure(reference_command, kind, 0, 1, 0)
            for count in workers:
                measure(reference_command, kind, count, 1, 0)
        save()
        if not args.reference_only:
            ir_path, binary = work / 'rows.ll', work / 'rows'
            _, report['ir_preparation'] = run(compiler + ['ir', str(SOURCE), '-o', str(ir_path)], env, work, args.timeout, resources)
            ir = ir_path.read_text()
            for kind in ('score', 'affine'):
                if 'define internal void @pys.parallel.rows.f.' + kind + '(' not in ir:
                    raise ValueError(kind + ': proven row thunk missing; refusing to benchmark fallback')
            report['ir_sha256'] = digest(ir_path)
            _, report['native_preparation'] = run(compiler + ['build', str(SOURCE), '-o', str(binary)], env, work, args.timeout, resources)
            report['executable_bytes'], report['executable_sha256'] = binary.stat().st_size, digest(binary)
            policies = [(kind, count) for kind in ('score', 'affine') for count in [0] + workers]
            for sample in range(args.samples):
                shift = sample % len(policies)
                order = policies[shift:] + policies[:shift]
                if sample % 2:
                    order.reverse()
                for kind, count in order:
                    result = measure([str(binary)], kind, count, args.batches, args.warmups)
                    result['sample'] = sample
                    report['runs'].append(result)
                    save()
            report['summary'] = []
            for kind, count in policies:
                times = [r['kernel_median_s'] for r in report['runs'] if r['kind'] == kind and r['workers'] == count]
                report['summary'].append({'kind': kind, 'workers': count, 'median_s': statistics.median(times),
                                          'min_s': min(times), 'max_s': max(times)})
        report['status'] = 'complete'
        save()
    print(args.output)


if __name__ == '__main__':
    main()
