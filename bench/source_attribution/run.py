"""Reproduce source-attribution profiles; CPython driver, never a timing gate."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cleaned_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith('PYSTACHY_')}
    if 'PYSTACHY_LLVM' in os.environ:
        env['PYSTACHY_LLVM'] = os.environ['PYSTACHY_LLVM']
    env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_JOBS='2', PYSTACHY_IRCHECK='1')
    return env


def witness(stdout):
    return '\n'.join(line for line in stdout.splitlines()
                     if not line.startswith(('seconds ', 'warmup_seconds ')))


def callgrind_summary(path):
    """Aggregate exclusive Ir; calls= rows are inclusive and must be skipped."""
    files, functions, by_file, by_line = {}, {}, {}, {}
    file, function, line, skip = '???', '???', 0, False
    events, positions, total = [], [], 0

    def expand(value, table):
        found = re.fullmatch(r'\((\d+)\)(?: (.*))?', value)
        if not found:
            return value
        key, text = found.groups()
        if text is not None:
            table[key] = text
        return table.get(key, '???')

    for record in path.read_text().splitlines():
        if record.startswith('positions:'):
            positions = record.split()[1:]
        elif record.startswith('events:'):
            events = record.split()[1:]
        elif record.startswith('summary:') and 'Ir' in events:
            total += int(record.split()[1 + events.index('Ir')])
        elif record.startswith(('fl=', 'fi=', 'fe=')):
            file = expand(record[3:], files)
        elif record.startswith(('cfl=', 'cfi=', 'cfe=')):
            expand(record[4:], files)
        elif record.startswith('cfn='):
            expand(record[4:], functions)
        elif record.startswith('fn='):
            function = expand(record[3:], functions)
            line, skip = 0, False
        elif record.startswith('calls='):
            skip = True
        elif record and (record[0].isdigit() or record[0] in '+-*'):
            fields = record.split()
            if positions != ['line']:
                raise RuntimeError(f'unsupported Callgrind positions: {positions}')
            first = fields[0]
            if first != '*':
                line = line + int(first) if first[0] in '+-' else int(first)
            if skip:
                skip = False
                continue
            count = int(fields[1 + events.index('Ir')])
            by_file[file] = by_file.get(file, 0) + count
            if file.endswith('.py') and line > 0:
                key = (file, line, function)
                by_line[key] = by_line.get(key, 0) + count
    ranked = sorted(by_line.items(), key=lambda item: -item[1])
    return {'summary_Ir': total, 'exclusive_Ir': sum(by_file.values()),
            'python_line_Ir': sum(by_line.values()),
            'files': sorted(({'file': k, 'Ir': v} for k, v in by_file.items()), key=lambda row: -row['Ir']),
            'top_python_lines': [{'file': k[0], 'line': k[1], 'function': k[2], 'Ir': v}
                                 for k, v in ranked[:40]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'pystachy')
    parser.add_argument('--baseline-compiler', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/source-attribution')
    parser.add_argument('--repetitions', type=int, default=7)
    parser.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument('--phase', choices=('build', 'measure', 'all'), default='all')
    parser.add_argument('--time-tool', default=shutil.which('time') or '/usr/bin/time')
    parser.add_argument('--valgrind', default=shutil.which('valgrind'))
    args = parser.parse_args()
    if args.repetitions < 3:
        parser.error('use at least three paired repetitions')
    compiler, baseline, output = args.compiler.resolve(), args.baseline_compiler.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = cleaned_env()
    events = output / 'events.tsv'
    small_events = output / 'events-profile.tsv'
    for path, n in ((events, 200000), (small_events, 2000)):
        with path.open('w') as stream:
            subprocess.run([sys.executable, str(ROOT / 'examples/route/genevents.py'), str(n)],
                           cwd=ROOT, env=env, stdout=stream, check=True)
    build_records = []

    def execute(command, label, run_env, pinned=True):
        log = output / label
        logfile = log.with_suffix('.time')
        started = time.perf_counter()
        result = subprocess.run([args.time_tool, '-f', '%e %M %U %S', '-o', str(logfile), *map(str, command)],
                                cwd=ROOT, env=run_env, capture_output=True, text=True, timeout=900, check=False,
                                preexec_fn=(lambda: os.sched_setaffinity(0, {args.cpu})) if pinned else None)
        elapsed = time.perf_counter() - started
        log.with_suffix('.stdout').write_text(result.stdout)
        log.with_suffix('.stderr').write_text(result.stderr)
        if result.returncode:
            raise RuntimeError(f'{label} exited {result.returncode}: {result.stderr[-4000:]}')
        measured = logfile.read_text().strip().split()
        data = [json.loads(s.removeprefix('pystachy-data: ')) for s in result.stderr.splitlines()
                if s.startswith('pystachy-data: ')]
        return {'command': list(map(str, command)), 'wall_seconds': elapsed,
                'time_wall_seconds': float(measured[0]), 'peak_rss_kib': int(measured[1]),
                'user_seconds': float(measured[2]), 'system_seconds': float(measured[3]),
                'witness': witness(result.stdout), 'counters': data,
                'stdout_sha256': digest(log.with_suffix('.stdout')),
                'stderr_sha256': digest(log.with_suffix('.stderr'))}

    sources = {'json_repair': 'bench/json_repair/bench.py', 'routing': 'examples/route/route.py',
               'numeric': 'bench/smoke/ml.py', 'compiler': 'pystachy.py'}
    variants = ('plain', 'lines', 'counted')
    binaries = {name: {variant: output / f'{name}-{variant}' for variant in variants} for name in sources}
    binaries['compiler']['plain'] = compiler
    compile_env = dict(env, PYSTACHY_PATH=str(ROOT / 'ports'))
    if args.phase != 'measure':
        for name, source in sources.items():
            for variant in variants:
                if name == 'compiler' and variant == 'plain':
                    continue
                setting = dict(compile_env, PYSTACHY_CACHE=str(output / f'cache-{name}-{variant}'))
                cached_before = (output / f'cache-{name}-{variant}').exists()
                if variant != 'plain':
                    setting['PYSTACHY_DEBUG_LINES'] = '1'
                if variant == 'counted':
                    setting['PYSTACHY_CFLAGS'] = '-DPYSTACHY_PROFILE_DATA'
                command = [compiler, 'build', source, '-o', binaries[name][variant]]
                record = execute(command, f'build-{name}-{variant}', setting, False)
                record.update(workload=name, variant=variant, binary_sha256=digest(binaries[name][variant]),
                              binary_bytes=binaries[name][variant].stat().st_size,
                              cache_existed_before=cached_before,
                              compile_env={k: v for k, v in setting.items() if k.startswith('PYSTACHY_')})
                build_records.append(record)
                (output / 'build.json').write_text(json.dumps(build_records, indent=2) + '\n')
                print('built', name, variant, round(record['wall_seconds'], 3), flush=True)
        if args.phase == 'build':
            return
    else:
        build_records = json.loads((output / 'build.json').read_text())
        for build in build_records:
            path = binaries[build['workload']][build['variant']]
            if digest(path) != build['binary_sha256']:
                raise RuntimeError(f'artifact changed since build: {path}')

    arguments = {
        'json_repair': ['2000', '1', '0'],
        'routing': [str(ROOT / 'examples/route/rules.txt'), str(events), '--in-memory'],
        'numeric': ['numeric', '100000'],
        'compiler': ['ir', 'pystachy.py', '-o', str(output / 'compiler-output.ll')],
    }
    profile_arguments = {
        'json_repair': ['100', '1', '0'],
        'routing': [str(ROOT / 'examples/route/rules.txt'), str(small_events), '--in-memory'],
        'numeric': ['numeric', '500'],
        'compiler': ['ir', 'examples/route/route.py', '-o', str(output / 'compiler-profile.ll')],
    }
    def version(command):
        return subprocess.check_output(command, cwd=ROOT, env=env, text=True, stderr=subprocess.STDOUT).splitlines()[0]

    llvm = Path(env['PYSTACHY_LLVM']) if 'PYSTACHY_LLVM' in env else None
    tools = {name: version([str(llvm / name) if llvm else name, '--version'])
             for name in ('clang', 'opt', 'lli', 'llvm-dwarfdump')}
    tools['time'] = version([args.time_tool, '--version'])
    if args.valgrind:
        tools['valgrind'] = version([args.valgrind, '--version'])
    cpuinfo = Path('/proc/cpuinfo').read_text()
    cpu_model = next((line.split(':', 1)[1].strip() for line in cpuinfo.splitlines()
                      if line.startswith('model name')), 'unavailable')
    governor = Path(f'/sys/devices/system/cpu/cpu{args.cpu}/cpufreq/scaling_governor')
    report = {'schema': 1, 'base_commit': 'f7103067545b43cdcd8ce20dc66b1571425b3a8d',
              'platform': platform.platform(), 'python': sys.version, 'cpu': args.cpu,
              'cpu_model': cpu_model, 'governor': governor.read_text().strip() if governor.exists() else 'unavailable',
              'tool_versions': tools,
              'affinity_available': sorted(os.sched_getaffinity(0)), 'invocation': sys.argv,
              'compiler_sha256': digest(compiler), 'baseline_sha256': digest(baseline),
              'environment': {k: v for k, v in env.items() if k.startswith('PYSTACHY_')},
              'builds': build_records, 'workloads': {}, 'frontend': {},
              'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in sorted({*ROOT.glob('src/**/*.py'), *ROOT.glob('lib/**/*.py'), *ROOT.glob('ports/**/*.py')})},
              'input_sha256': {str(p): digest(p) for p in [events, small_events, *(ROOT / p for p in sources.values()), ROOT / 'runtime.c', ROOT / 'runtime.py', ROOT / 'examples/route/rules.txt', ROOT / 'examples/route/genevents.py', Path(__file__), *sorted(ROOT.glob('ryu/*.[ch]')), *sorted(ROOT.glob('mpz/*.c'))]}}
    for name, source in sources.items():
        reference_env = dict(env, PYTHONPATH=str(ROOT / 'ports'))
        reference = execute(([baseline, *arguments[name]] if name == 'compiler' else
                             [sys.executable, source, *arguments[name]]), f'reference-{name}', reference_env)
        if name == 'compiler':
            reference['witness'] = digest(output / 'compiler-output.ll')
        runs = {variant: [] for variant in variants}
        # Warm each binary once, then alternate order on each complete paired round.
        for variant in variants:
            execute([binaries[name][variant], *arguments[name]], f'warm-{name}-{variant}', env)
        for rep in range(args.repetitions):
            for variant in variants if rep % 2 == 0 else tuple(reversed(variants)):
                run = execute([binaries[name][variant], *arguments[name]], f'run-{name}-{variant}-{rep}', env)
                if name == 'compiler':
                    run['witness'] = digest(output / 'compiler-output.ll')
                if len(run['counters']) != (1 if variant == 'counted' else 0):
                    raise RuntimeError(f'{name}/{variant}: expected counter report missing or unexpected')
                if run['witness'] != reference['witness']:
                    raise RuntimeError(f'{name}/{variant}: CPython/baseline witness differs')
                runs[variant].append(run)
        profile = {'arguments': profile_arguments[name]}
        counts = execute([binaries[name]['counted'], *profile_arguments[name]], f'counts-{name}', env)
        if len(counts['counters']) != 1:
            raise RuntimeError(f'{name}: expected one profile counter report')
        if name == 'compiler':
            counts['witness'] = digest(output / 'compiler-profile.ll')
        profile['counters'] = counts['counters']
        profile['witness'] = counts['witness']
        if args.valgrind:
            destination = output / f'{name}.callgrind'
            command = [args.valgrind, '--tool=callgrind', '--dump-instr=no', '--dump-line=yes',
                       '--callgrind-out-file=' + str(destination), str(binaries[name]['lines']), *profile_arguments[name]]
            profile_run = execute(command, f'profile-{name}', env)
            if name == 'compiler':
                profile_run['witness'] = digest(output / 'compiler-profile.ll')
            if profile_run['witness'] != counts['witness']:
                raise RuntimeError(f'{name}: profile witness differs')
            profile['callgrind'] = callgrind_summary(destination)
            if profile['callgrind']['summary_Ir'] != profile['callgrind']['exclusive_Ir']:
                raise RuntimeError(f'{name}: exclusive Callgrind count does not match summary')
            if profile['callgrind']['python_line_Ir'] == 0:
                raise RuntimeError(f'{name}: no executed Python lines in profile')
            profile['callgrind_sha256'] = digest(destination)
            with destination.open('rb') as src, gzip.GzipFile(filename=str(destination) + '.gz', mode='wb', mtime=0) as dst:
                shutil.copyfileobj(src, dst)
        report['workloads'][name] = {'reference': reference, 'arguments': arguments[name], 'runs': runs,
                                    'medians_seconds': {v: statistics.median(r['wall_seconds'] for r in runs[v]) for v in variants},
                                    'profile': profile}
        (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        print('measured', name, flush=True)
    # Same current source, home, flags and CPU: isolate compiler implementation
    # overhead from generated-program instrumentation and compare with old main.
    frontends = [('baseline', baseline, env), ('new_off', compiler, env),
                 ('new_on', compiler, dict(env, PYSTACHY_DEBUG_LINES='1'))]
    for label, executable, setting in frontends:
        report['frontend'][label] = []
        execute([executable, 'ir', 'pystachy.py', '-o', str(output / f'frontend-{label}.ll')],
                f'frontend-warm-{label}', setting)
    for rep in range(args.repetitions):
        for label, executable, setting in frontends if rep % 2 == 0 else list(reversed(frontends)):
            run = execute([executable, 'ir', 'pystachy.py', '-o', str(output / f'frontend-{label}.ll')],
                          f'frontend-{label}-{rep}', setting)
            run['ir_sha256'] = digest(output / f'frontend-{label}.ll')
            report['frontend'][label].append(run)
    if digest(output / 'frontend-baseline.ll') != digest(output / 'frontend-new_off.ll'):
        raise RuntimeError('baseline and new default-off frontend IR differs')
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
