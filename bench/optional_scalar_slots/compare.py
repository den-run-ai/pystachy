"""Isolated AOT comparison; compile first, then run paired, pinned samples."""
import argparse
import ast
import hashlib
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

SOURCE_REVISION = '3d0f56d82e3f7e3e0799d37e014f73391913f1ca'
SOURCES = {
    'examples/byte_bpe/stages.py': '3f0154fadce48607aa9868cb93fd7a75f4a18b52c4281590709dfb3632a50b7d',
    'bench/pyperformance/bpe_tokeniser.py': '9775aff77bb52efc6fb9828517ead0584552b1cba5afe73ef4d93e13972ca7de',
    'bench/pyperformance/data/frankenstein_intro.txt': '6607193e67b7b459d082f5f2aea724e470615643d63ad2e205123b3076223da4',
    'examples/byte_bpe/upstream/bpe_tokeniser.py': 'c7255345499e118181785370b0996e8cc1056491b9678b3fbeb02421e3f9b2df',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def env(root):
    value = {k: v for k, v in os.environ.items() if not k.startswith('PYSTACHY_') and k not in ('PYTHONPATH', 'PYTHONHOME')}
    value.update(PYSTACHY_HOME=str(root), PYSTACHY_LLVM=LLVM, PYSTACHY_PROGRAM_CACHE='0',
                 PYSTACHY_CACHE=str(HERE / ('cache-' + root.name)), PYSTACHY_PATH=str(HERE / 'sources'),
                 PYSTACHY_IRCHECK='1', PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1')
    return value


def call(args, environment, cwd=None, timeout=180):
    started = time.perf_counter()
    result = subprocess.run(args, env=environment, cwd=CHANGED if cwd is None else cwd, text=True, capture_output=True,
                            timeout=timeout, check=True)
    return {'wall_seconds': time.perf_counter() - started, 'stdout': result.stdout, 'stderr': result.stderr}


def stage_sources():
    metadata = {}
    for relative, expected in SOURCES.items():
        path = BPE / relative
        actual = digest(path)
        if actual != expected:
            raise ValueError('BPE input differs from pinned source: ' + relative)
        metadata[relative] = {'revision': SOURCE_REVISION, 'sha256': actual}
    for name in ('driver', 'sources', 'original'):
        (HERE / name).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BPE / 'examples/byte_bpe/stages.py', HERE / 'driver/stages.py')
    shutil.copyfile(BPE / 'bench/pyperformance/bpe_tokeniser.py', HERE / 'sources/bpe_tokeniser.py')
    shutil.copyfile(BPE / 'bench/pyperformance/data/frankenstein_intro.txt', HERE / 'sources/frankenstein_intro.txt')
    # Exact upstream kernel text; omit only its pyperf runner/setup imports.
    source = (BPE / 'examples/byte_bpe/upstream/bpe_tokeniser.py').read_text()
    wanted = {'SimpleBytePairEncoding', 'bpe_encode', 'bpe_train'}
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in wanted]
    if len(nodes) != len(wanted) or {n.name for n in nodes} != wanted:
        raise ValueError('upstream kernels missing or duplicated')
    adapted = ast.parse((HERE / 'sources/bpe_tokeniser.py').read_text())
    pattern = next(ast.literal_eval(n.value) for n in adapted.body if isinstance(n, ast.Assign)
                   and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'BPE_PATTERN')
    original = ('from __future__ import annotations\nimport collections\nimport re\n\n' +
                '\n\n'.join(ast.get_source_segment(source, node) for node in nodes) +
                f'\n\nBPE_PATTERN = {pattern!r}\n')
    (HERE / 'original/bpe_tokeniser.py').write_text(original)
    metadata['extracted_upstream_kernels'] = {'sha256': digest(HERE / 'original/bpe_tokeniser.py')}
    (HERE / 'sources.json').write_text(json.dumps(metadata, indent=2) + '\n')


def prepare():
    stage_sources()
    builds = []
    for name, root, compiler in [('main', BASE, [PY, str(BASE / 'pystachy.py')]),
                                 ('changed', CHANGED, [str(CHANGED / 'pystachy')])]:
        for workload, source in [('micro', CHANGED / 'bench/optional_scalars.py'),
                                  ('bpe', HERE / 'driver/stages.py')]:
            output = HERE / (name + '-' + workload)
            result = call(compiler + ['build', str(source), '-o', str(output)], env(root), root)
            assert not result['stdout'] and not result['stderr'], result
            builds.append({'variant': name, 'workload': workload, 'wall_seconds': result['wall_seconds'],
                           'binary_sha256': digest(output), 'binary_bytes': output.stat().st_size})
    (HERE / 'builds.json').write_text(json.dumps(builds, indent=2) + '\n')
    print(json.dumps(builds, indent=2), flush=True)


def measure():
    cpu = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpu})
    environment = env(CHANGED)
    builds = json.loads((HERE / 'builds.json').read_text())
    for build in builds:
        binary = HERE / (build['variant'] + '-' + build['workload'])
        if digest(binary) != build['binary_sha256']:
            raise ValueError('binary differs from prepared build: ' + str(binary))
    source = HERE / 'driver/stages.py'
    corpus = HERE / 'sources/frankenstein_intro.txt'
    bpe_args = [str(corpus), '1024', str(args.bpe_loops), str(args.bpe_loops)]
    micro_rounds = str(args.rounds)
    original_env = dict(environment, PYTHONPATH=str(HERE / 'original'))
    original = call([PY, str(source), *bpe_args], original_env)
    adapted = call([PY, str(source), *bpe_args], dict(environment, PYTHONPATH=str(HERE / 'sources')))
    assert original['stdout'] == adapted['stdout'], 'adapted BPE differs from pristine CPython'
    expected = {'bpe': original['stdout']}
    for mode in ('direct', 'ranks'):
        expected[mode] = call([PY, str(CHANGED / 'bench/optional_scalars.py'), mode, micro_rounds], environment)['stdout']
    commands = {}
    for mode in ('direct', 'ranks', 'bpe'):
        for variant in ('main', 'changed'):
            commands[(mode, variant)] = ([str(HERE / (variant + '-bpe')), *bpe_args] if mode == 'bpe' else
                                         [str(HERE / (variant + '-micro')), mode, micro_rounds])
    report = {'metadata': {'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                           'platform': platform.platform(), 'python': sys.version, 'cpu': cpu,
                           'cpu_model': next(s.split(':', 1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines() if s.startswith('model name')),
                           'base_revision': 'f7103067545b43cdcd8ce20dc66b1571425b3a8d',
                           'changed_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=CHANGED, text=True).strip(),
                           'changed_diff_sha256': hashlib.sha256(subprocess.check_output(['git', 'diff', '--binary'], cwd=CHANGED)).hexdigest(),
                           'compiler_sources_sha256': {str(p.relative_to(CHANGED)): digest(p) for p in [CHANGED / 'pystachy.py', CHANGED / 'runtime.py', CHANGED / 'runtime.c', *sorted((CHANGED / 'src').rglob('*.py'))]},
                           'micro_sha256': digest(CHANGED / 'bench/optional_scalars.py'),
                           'controller_sha256': digest(Path(__file__)),
                           'bpe_sources': json.loads((HERE / 'sources.json').read_text()),
                           'llvm': subprocess.check_output([LLVM + '/clang', '--version'], text=True).strip(),
                           'compiler_binary_sha256': digest(CHANGED / 'pystachy')},
              'workload': {'micro_rounds': int(micro_rounds), 'micro_items': 320, 'vocab_size': 1024,
                           'encode_loops': args.bpe_loops, 'decode_loops': args.bpe_loops,
                           'samples': args.pairs, 'warmups': 1,
                           'order': 'paired, main/changed then changed/main alternately'},
              'builds': builds,
              'oracles': {mode: {'stdout_sha256': hashlib.sha256(value.encode()).hexdigest(), 'stdout_bytes': len(value.encode())} for mode, value in expected.items()},
              'samples': []}
    for mode in ('direct', 'ranks', 'bpe'):
        for variant in ('main', 'changed'):
            warm = call(commands[(mode, variant)], environment)
            assert warm['stdout'] == expected[mode], (mode, variant, 'warmup mismatch')
        for pair in range(args.pairs):
            order = ('main', 'changed') if pair % 2 == 0 else ('changed', 'main')
            for variant in order:
                result = call(commands[(mode, variant)], environment)
                assert result['stdout'] == expected[mode], (mode, variant, pair, 'output mismatch')
                row = {'workload': mode, 'variant': variant, 'pair': pair, 'wall_seconds': result['wall_seconds']}
                if mode == 'bpe':
                    times = {line.split()[0]: float(line.split()[1]) for line in result['stderr'].splitlines()}
                    assert set(times) == {'train', 'encode', 'decode'}, result['stderr']
                    assert all(math.isfinite(v) and v > 0 for v in times.values()), times
                    row.update(train_seconds=times['train'], encode_seconds=times['encode'] / args.bpe_loops,
                               decode_seconds=times['decode'] / args.bpe_loops)
                else:
                    assert not result['stderr'], result['stderr']
                report['samples'].append(row)
                RECORD.write_text(json.dumps(report, indent=2) + '\n')
        print(mode, 'completed', args.pairs, 'pairs', flush=True)
    summary = {}
    for mode in ('direct', 'ranks', 'bpe'):
        keys = ('wall_seconds',) if mode != 'bpe' else ('wall_seconds', 'train_seconds', 'encode_seconds', 'decode_seconds')
        summary[mode] = {}
        for key in keys:
            result = {}
            for variant in ('main', 'changed'):
                values = [r[key] for r in report['samples'] if r['workload'] == mode and r['variant'] == variant]
                result[variant] = {'median': statistics.median(values), 'min': min(values), 'max': max(values)}
            result['ratio_of_medians'] = result['main']['median'] / result['changed']['median']
            summary[mode][key] = result
    report['summary'] = summary
    RECORD.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'measure'])
    parser.add_argument('--base', type=Path, required=True, help='clean exact-main checkout; CPython hosts its compiler')
    parser.add_argument('--changed', type=Path, required=True, help='candidate checkout with fresh native ./pystachy')
    parser.add_argument('--bpe', type=Path, required=True, help='checkout containing the pinned byte-BPE sources')
    parser.add_argument('--workdir', type=Path, required=True, help='private scratch directory for inputs, binaries and results')
    parser.add_argument('--llvm', type=Path, required=True, help='complete LLVM toolchain bin directory')
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--pairs', type=int, default=7)
    parser.add_argument('--rounds', type=int, default=30000)
    parser.add_argument('--bpe-loops', type=int, default=100)
    args = parser.parse_args()
    if min(args.pairs, args.rounds, args.bpe_loops) < 1:
        parser.error('pairs, rounds and bpe-loops must be positive')
    BASE, CHANGED, BPE, HERE = (p.resolve() for p in (args.base, args.changed, args.bpe, args.workdir))
    PY, LLVM = args.python, str(args.llvm.resolve())
    RECORD = HERE / 'results.json'
    HERE.mkdir(parents=True, exist_ok=True)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=BASE, text=True).strip()
    if revision != 'f7103067545b43cdcd8ce20dc66b1571425b3a8d' or subprocess.check_output(['git', 'diff', 'HEAD'], cwd=BASE):
        parser.error('base must be clean main f7103067545b43cdcd8ce20dc66b1571425b3a8d')
    if args.stage == 'prepare':
        prepare()
    else:
        measure()
