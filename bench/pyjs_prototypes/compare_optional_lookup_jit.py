"""Output-checked paired JIT comparison with separate in-program timers.

Both variants use CPython-hosted compilers, uncached JIT compilation on every run,
and separate runtime caches. Run prepare before obtaining a quiet timing window;
run measure only once competing builds/tests have stopped.
"""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time

BASE_REV = '04860a83618e744c6f461761b6ee7fdbbe21f985'
MICRO_SHA = 'ff6dc5048a6917a477e2b4c11b71e856afa31617135ec0685d00ee59e3d04bad'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def identity(root):
    if git(root, 'status', '--porcelain'):
        raise ValueError('compiler tree must be clean: ' + str(root))
    paths = ['pystachy.py', 'runtime.c', 'runtime.py'] + sorted(
        str(p.relative_to(root)) for p in (root / 'src/pystachy_compiler').glob('*.py'))
    return {'revision': git(root, 'rev-parse', 'HEAD'),
            'source_hashes': {p: digest(root / p) for p in paths}}


def environment(variant, original=False):
    root = ROOTS[variant]
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('PYSTACHY_') and k not in ('PYTHONPATH', 'PYTHONHOME')}
    env.update(PYSTACHY_HOME=str(root), PYSTACHY_LLVM=str(LLVM),
               PYSTACHY_PATH=str(INPUTS / 'sources'),
               PYSTACHY_CACHE=str(WORK / ('cache-' + variant)),
               PYSTACHY_PROGRAM_CACHE='0', PYSTACHY_IRCHECK='1',
               PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1')
    if original:
        env['PYTHONPATH'] = str(INPUTS / 'original')
    return env


def invoke(command, env, timeout=180):
    began = time.perf_counter()
    p = subprocess.run(command, env=env, cwd=WORK, capture_output=True, timeout=timeout)
    wall = time.perf_counter() - began
    if p.returncode != 0:
        raise RuntimeError(f'command failed ({p.returncode}): {command}\n{p.stderr.decode(errors="replace")}')
    return {'wall_seconds': wall, 'stdout': p.stdout, 'stderr': p.stderr.decode()}


def arguments(mode):
    if mode == 'bpe':
        return [str(INPUTS / 'driver/stages.py'), str(INPUTS / 'sources/frankenstein_intro.txt'),
                '1024', str(args.bpe_loops), str(args.bpe_loops)]
    return [str(WORK / 'timed_optional_scalars.py'), mode, str(args.rounds)]


def measured_run(variant, mode, expected):
    command = [PY, str(ROOTS[variant] / 'pystachy.py'), 'run', *arguments(mode)]
    result = invoke(command, environment(variant))
    if result['stdout'] != expected:
        (WORK / 'unexpected.stdout').write_bytes(result['stdout'])
        raise AssertionError(f'{variant} {mode}: complete output differs from CPython')
    times = {}
    for line in result['stderr'].splitlines():
        fields = line.split()
        if len(fields) != 2 or fields[0] in times:
            raise AssertionError('unexpected stderr: ' + result['stderr'])
        times[fields[0]] = float(fields[1])
    wanted = {'train', 'encode', 'decode'} if mode == 'bpe' else {'run'}
    if set(times) != wanted or not all(math.isfinite(t) and t > 0 for t in times.values()):
        raise AssertionError('invalid program timers: ' + result['stderr'])
    row = {'variant': variant, 'workload': mode, 'wall_seconds': result['wall_seconds'],
           'stdout_sha256': hashlib.sha256(result['stdout']).hexdigest(),
           'stdout_bytes': len(result['stdout']), 'output_matched': True,
           'load_average': list(os.getloadavg())}
    if mode == 'bpe':
        row.update(train_seconds=times['train'],
                   encode_seconds=times['encode'] / args.bpe_loops,
                   decode_seconds=times['decode'] / args.bpe_loops,
                   process_less_timed_stages_seconds=result['wall_seconds'] - sum(times.values()))
    else:
        row.update(inner_seconds=times['run'],
                   process_less_timed_kernel_seconds=result['wall_seconds'] - times['run'])
    return row


def prepare():
    signatures = {name: identity(root) for name, root in ROOTS.items()}
    if signatures['main']['revision'] != BASE_REV:
        raise ValueError('baseline must be pinned main ' + BASE_REV)
    sources = json.loads((INPUTS / 'sources.json').read_text())
    for name, path in [('examples/byte_bpe/stages.py', INPUTS / 'driver/stages.py'),
                       ('bench/pyperformance/bpe_tokeniser.py', INPUTS / 'sources/bpe_tokeniser.py'),
                       ('bench/pyperformance/data/frankenstein_intro.txt', INPUTS / 'sources/frankenstein_intro.txt')]:
        if digest(path) != sources[name]['sha256']:
            raise ValueError('BPE source hash mismatch: ' + name)
    micro = ROOTS['main'] / 'bench/optional_scalars.py'
    if digest(micro) != MICRO_SHA or digest(ROOTS['candidate'] / 'bench/optional_scalars.py') != MICRO_SHA:
        raise ValueError('microbenchmark differs from the measured AOT kernel')
    original = micro.read_text()
    timed = original.replace('import sys\n', 'import sys\nimport time\n')
    for expression in ('direct_minimum(xs, rounds)', 'rank_minimum(keys, ranks, rounds)'):
        old = '    print(' + expression + ')'
        if timed.count(old) != 1:
            raise ValueError('expected one top-level kernel call: ' + expression)
        timed = timed.replace(old,
            '    _measurement_start = time.perf_counter()\n'
            '    _measurement_value = ' + expression + '\n'
            '    _measurement_elapsed = time.perf_counter() - _measurement_start\n'
            '    print(_measurement_value)\n'
            '    print("run", _measurement_elapsed, file=sys.stderr)')
    def kernels(text):
        return {n.name: ast.get_source_segment(text, n) for n in ast.parse(text).body
                if isinstance(n, ast.FunctionDef)}

    if kernels(original) != kernels(timed):
        raise AssertionError('timing wrapper changed a microbenchmark kernel')
    wrapper = WORK / 'timed_optional_scalars.py'
    wrapper.write_text(timed)
    expected = {}
    for mode in ('direct', 'ranks'):
        plain = invoke([PY, str(micro), mode, str(args.rounds)], environment('main'))
        wrapped = invoke([PY, *arguments(mode)], environment('main'))
        if plain['stdout'] != wrapped['stdout']:
            raise AssertionError('timed micro wrapper differs from unchanged CPython source')
        expected[mode] = plain['stdout']
    upstream = invoke([PY, *arguments('bpe')], environment('main', original=True))
    adapted_env = environment('main')
    adapted_env['PYTHONPATH'] = str(INPUTS / 'sources')
    adapted = invoke([PY, *arguments('bpe')], adapted_env)
    if upstream['stdout'] != adapted['stdout']:
        raise AssertionError('adapted BPE differs from upstream CPython')
    expected['bpe'] = upstream['stdout']
    for mode, stdout in expected.items():
        (WORK / (mode + '.expected')).write_bytes(stdout)
    preparation = {'compiler': signatures, 'source_metadata': sources,
                   'micro_sha256': MICRO_SHA, 'timed_micro_sha256': digest(wrapper),
                   'controller_sha256': digest(Path(__file__)),
                   'llvm_version': subprocess.check_output([str(LLVM / 'clang'), '--version'], text=True),
                   'workload': {'rounds': args.rounds, 'bpe_loops': args.bpe_loops},
                   'oracles': {mode: {'bytes': len(stdout), 'sha256': hashlib.sha256(stdout).hexdigest()}
                               for mode, stdout in expected.items()},
                   'cache_preparation_runs': []}
    for mode in ('ranks', 'bpe'):
        for variant in ROOTS:
            row = measured_run(variant, mode, expected[mode])
            preparation['cache_preparation_runs'].append(row)
            print('prepared', mode, variant, 'output checked; preparation time is not a timing sample', flush=True)
    (WORK / 'prepared.json').write_text(json.dumps(preparation, indent=2) + '\n')
    print('READY FOR QUIET TIMING WINDOW', flush=True)


def measure():
    preparation = json.loads((WORK / 'prepared.json').read_text())
    if preparation['workload'] != {'rounds': args.rounds, 'bpe_loops': args.bpe_loops}:
        raise ValueError('workload differs from prepared oracles')
    for variant, root in ROOTS.items():
        if identity(root) != preparation['compiler'][variant]:
            raise ValueError('compiler changed after preparation: ' + variant)
    if digest(WORK / 'timed_optional_scalars.py') != preparation['timed_micro_sha256']:
        raise ValueError('timed micro wrapper changed')
    cpu = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpu})
    expected = {mode: (WORK / (mode + '.expected')).read_bytes() for mode in ('direct', 'ranks', 'bpe')}
    for mode, stdout in expected.items():
        if hashlib.sha256(stdout).hexdigest() != preparation['oracles'][mode]['sha256']:
            raise ValueError('oracle changed: ' + mode)
    report = {'metadata': {'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                           'platform': platform.platform(), 'cpu': cpu,
                           'cpu_model': next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), ''),
                           'python': subprocess.check_output([PY, '-c', 'import sys; print(sys.version)'], text=True).strip(),
                           'load_average_start': list(os.getloadavg()),
                           'timing_conditions': 'Root and team builds/tests paused; host may be shared. Each run recompiles through JIT with a warm private runtime cache; native-program cache disabled.',
                           'process_time_note': 'Whole-process time includes CPython-hosted compilation, JIT, execution, setup and output; inner timers exclude compilation and output.'},
              'preparation': preparation,
              'workload': {'micro_rounds': args.rounds, 'micro_items': 320, 'vocab_size': 1024,
                           'bpe_encode_loops': args.bpe_loops, 'bpe_decode_loops': args.bpe_loops,
                           'warmups_per_variant': 2, 'pairs': args.pairs,
                           'order': 'main/candidate on even pairs, candidate/main on odd pairs'},
              'warmups': [], 'samples': []}
    for mode in ('direct', 'ranks', 'bpe'):
        for warmup in range(2):
            for variant in ROOTS:
                row = measured_run(variant, mode, expected[mode])
                row['warmup'] = warmup
                report['warmups'].append(row)
        for pair in range(args.pairs):
            order = ('main', 'candidate') if pair % 2 == 0 else ('candidate', 'main')
            for variant in order:
                row = measured_run(variant, mode, expected[mode])
                row['pair'] = pair
                report['samples'].append(row)
                (WORK / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        print(mode, args.pairs, 'checked pairs complete', flush=True)
    summary = {}
    for mode in ('direct', 'ranks', 'bpe'):
        metrics = ('inner_seconds', 'wall_seconds', 'process_less_timed_kernel_seconds') if mode != 'bpe' else ('encode_seconds', 'train_seconds', 'decode_seconds', 'wall_seconds', 'process_less_timed_stages_seconds')
        summary[mode] = {}
        for metric in metrics:
            item = {}
            for variant in ROOTS:
                values = [row[metric] for row in report['samples'] if row['variant'] == variant and row['workload'] == mode]
                item[variant] = {'median': statistics.median(values), 'min': min(values), 'max': max(values)}
            item['ratio_of_medians'] = item['main']['median'] / item['candidate']['median']
            faster = 0
            for pair in range(args.pairs):
                pair_rows = {row['variant']: row[metric] for row in report['samples'] if row['workload'] == mode and row['pair'] == pair}
                faster += pair_rows['candidate'] < pair_rows['main']
            item['candidate_faster_pairs'] = faster
            summary[mode][metric] = item
    report['metadata']['load_average_end'] = list(os.getloadavg())
    report['summary'] = summary
    (WORK / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'measure'])
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True, help='Existing output-checked AOT benchmark input directory')
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--llvm', type=Path, required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--pairs', type=int, default=7)
    parser.add_argument('--rounds', type=int, default=30000)
    parser.add_argument('--bpe-loops', type=int, default=100)
    args = parser.parse_args()
    if min(args.pairs, args.rounds, args.bpe_loops) < 1:
        parser.error('workload and pair counts must be positive')
    ROOTS = {'main': args.base.resolve(), 'candidate': args.candidate.resolve()}
    INPUTS, WORK, LLVM = (p.resolve() for p in (args.inputs, args.workdir, args.llvm))
    PY = args.python
    WORK.mkdir(parents=True, exist_ok=True)
    if args.stage == 'prepare':
        prepare()
    else:
        measure()
