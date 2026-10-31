#!/usr/bin/env python3
"""PR996 native current-main/archived-da84/final JSON and call-control measurements."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import statistics
import subprocess
import sys

import count_support
import replay_support as replay

WORK = Path(__file__).resolve().parent.parent
OLD = Path('/workspace/scratch/e858f72517b9')
HOMES = {'main': WORK / 'main1000', 'da84': OLD / 'pystachy', 'final': WORK / 'pystachy'}
ENV_KEYS = ['PATH', 'LD_LIBRARY_PATH', 'LIBRARY_PATH', 'CPATH', 'VALGRIND_LIB', 'PYTHONHASHSEED', 'LANG', 'LC_ALL',
            'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'PYSTACHY_LLVM', 'PYSTACHY_HOME', 'PYSTACHY_CACHE']
EXPECTED = {'main': '07b26e02425d023288ed95a9d2a5077be5aeb45e',
            'da84': 'da84d382ff83f09e46d4ef104e62e6f64e9c37c1'}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def validate_fresh_build(home, proof):
    assert proof['fresh_local_build'] is True and proof['exit_code'] == 0
    assert proof['before'] == proof['after'] and len(proof['artifacts']) == 9
    assert len({proof['artifacts'][f'build/stage{n}.ll']['sha256'] for n in (1, 2, 3)}) == 1
    assert len({proof['artifacts'][f'build/rt{n}.ll']['sha256'] for n in (1, 2, 3)}) == 1
    for path, row in proof['artifacts'].items():
        assert (home / path).stat().st_size == row['bytes'] and replay.digest(home / path) == row['sha256']


def summary(result):
    out = {'sources': {name: {'commit': row['commit'], 'tree': row['tree']} for name, row in result['source_identities'].items()},
           'build_provenance': result['native_compilers'],
           'phases': result['phases'], 'cases': {}}
    for case, data in result['cases'].items():
        row = {'n': data['n'], 'checksum': data.get('checksum')}
        if 'instruction_counts' in data:
            row['instruction_count_n'] = data['instruction_counts']['n']
            counts = data['instruction_counts']['variants']
            row['instructions'] = {mode: {name: counts[name][mode]['instructions'] for name in counts} for mode in ['jit', 'aot']
                                   if all(mode in counts[name] for name in counts)}
            row['instruction_percent_vs_main'] = {mode: {name: 100 * (values[name] / values['main'] - 1) for name in values if name != 'main'}
                                                  for mode, values in row['instructions'].items()}
        if data.get('timings'):
            row['timings'] = {}
            for mode in ('jit', 'aot'):
                runs = data['timings'].get(mode, {})
                if not all(name in runs and len(runs[name]) == 6 for name in HOMES):
                    continue
                medians = {name: [r['median_ns'] for r in runs[name]] for name in HOMES}
                base = medians['main']
                row['timings'][mode] = {}
                for name, values in medians.items():
                    ratios = [a / b for a, b in zip(values, base, strict=True)]
                    row['timings'][mode][name] = {'process_median_ns': statistics.median(values),
                        'process_median_range_ns': [min(values), max(values)], 'percent_vs_main': 100 * (statistics.median(values) / statistics.median(base) - 1),
                        'paired_ratio_median': statistics.median(ratios), 'paired_ratio_range': [min(ratios), max(ratios)],
                        'slower_pairs_vs_main': sum(r > 1 for r in ratios), 'pairs': len(ratios), 'paired_ratios': ratios}
        out['cases'][case] = row
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'counts', 'timings', 'summary'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--final-bootstrap', type=Path)
    parser.add_argument('--expected-final-commit', required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    llvm = Path(os.environ['PYSTACHY_LLVM'])
    vg = OLD / 'toolchain/llvm18/usr'
    environment = {key: value for key, value in os.environ.items() if not key.startswith('PYSTACHY_') and key not in ('PYTHONPATH', 'PYTHONHOME')}
    environment.update(PYSTACHY_LLVM=str(llvm), VALGRIND_LIB=str(vg / 'libexec/valgrind'), PYTHONHASHSEED='0')
    envs = {name: dict(environment, PYSTACHY_HOME=str(home), PYSTACHY_CACHE=str(out / (name + '-cache'))) for name, home in HOMES.items()}
    def run(command, cwd, env, timeout=240):
        return replay.run(['taskset', '-c', '0', *map(str, command)], cwd, env, timeout)
    if args.phase == 'prepare':
        assert args.final_bootstrap, 'final source requires its fresh fixed-point bootstrap record'
        out.mkdir(exist_ok=False)
        proofs = {'main': WORK / 'experiments/bootstrap-main1000/bootstrap.json',
                  'da84': OLD / 'recovery-validation/final-da84/bootstrap.json', 'final': args.final_bootstrap.resolve()}
        result = {'started_utc': stamp(), 'purpose': __doc__, 'status': 'incomplete', 'cpu': 0, 'platform': platform.platform(),
                  'cpuinfo': Path('/proc/cpuinfo').read_text(), 'source_identities': {}, 'native_compilers': {}, 'phases': {}, 'cases': {},
                  'tools': {'python': sys.executable, 'llvm': str(llvm), 'valgrind_root': str(vg)},
                  'toolchain_manifest': json.loads((OLD / 'toolchain/manifest.json').read_text()),
                  'toolchain_manifest_sha256': replay.digest(OLD / 'toolchain/manifest.json'),
                  'selected_environment': {key: environment.get(key) for key in ENV_KEYS},
                  'variant_environment': {name: {key: env.get(key) for key in ENV_KEYS} for name, env in envs.items()},
                  'tool_files': {},
                  'method': 'New current-main series: main is 07b26e0 after PR1000, da84 is the archived pre-integration reference, and final must descend from current main. Same probe bytes and path for all variants; actual native driver run/build, private runtime caches, CPython checksums. Six balanced process orders per case/mode, seven measured calls per process. Counts collect eight complete kernel calls including warmup and runtime/GC, with separate explicit input sizes: ordinary n1000000, object n1000, JSON and managed-file JSON n2000. All observations are new; the closed db14/06e3 checkpoint and older host series remain separate.',
                  'changed_cases': ['ordinary_calls', 'object_calls', 'json_calls', 'json_file_calls']}
        for name, row in result['toolchain_manifest']['files'].items():
            assert replay.digest(row['path']) == row['sha256'], (name, 'recorded tool bytes changed')
            result['tool_files'][name] = row
        actual_tools = {'python3.13': Path(sys.executable), **{name: llvm / name for name in ('opt', 'lli', 'clang', 'llvm-as', 'llvm-dis', 'llvm-link')}}
        for name, path in actual_tools.items():
            assert replay.digest(path) == result['toolchain_manifest']['files'][name]['sha256'], (name, 'selected tool does not match pinned toolchain')
            result['tool_files']['selected-' + name] = {'path': str(path), 'resolved_path': str(path.resolve()), 'sha256': replay.digest(path), 'size': path.stat().st_size}
        extra_tools = [llvm / 'llvm-nm', *sorted((OLD / 'toolchain/llvm18/usr/lib/x86_64-linux-gnu').glob('libLLVM*.so*')),
                       *sorted((OLD / 'toolchain/llvm18/usr/lib/llvm-18/lib').glob('libclang-cpp.so*'))]
        for path in extra_tools:
            if path.is_file():
                result['tool_files'][str(path)] = {'path': str(path), 'sha256': replay.digest(path), 'size': path.stat().st_size}
        for name, home in HOMES.items():
            ident = replay.source_identity(home)
            proof = json.loads(proofs[name].read_text())
            assert proof['status'] == 'complete' and proof['source_identity_stable'], (name, 'bootstrap not complete')
            assert proof['commit'] == ident['commit'] and proof['tree'] == ident['tree'] and not ident['git_status'], (name, 'source differs from bootstrap')
            if name in ('main', 'final'):
                validate_fresh_build(home, proof)
            if name in EXPECTED:
                assert ident['commit'] == EXPECTED[name]
            else:
                assert ident['commit'] == args.expected_final_commit, 'unexpected final source commit'
                subprocess.check_call(['git', 'merge-base', '--is-ancestor', EXPECTED['main'], ident['commit']], cwd=home)
            assert all(sha == proof['after'][path] for path, sha in ident['input_sha256'].items() if path != 'Makefile'), (name, 'bootstrap consumed-input mismatch')
            binary = home / 'pystachy'
            assert replay.digest(binary) == proof['artifacts']['pystachy']['sha256'], (name, 'native binary mismatch')
            log = proofs[name].parent / 'bootstrap.log'
            assert replay.digest(log) == proof['log_sha256'], (name, 'bootstrap log mismatch')
            result['source_identities'][name] = ident
            result['native_compilers'][name] = {'path': str(binary), 'sha256': replay.digest(binary),
                                               'bootstrap_path': str(proofs[name]), 'bootstrap_sha256': replay.digest(proofs[name]),
                                               'record_kind': proof.get('record_kind', 'bootstrap'),
                                               'fresh_local_build': proof.get('fresh_local_build'),
                                               'build_commit': proof['commit'], 'build_tree': proof['tree'],
                                               'bootstrap_log_path': str(log), 'bootstrap_log_sha256': proof['log_sha256']}
        probes = out / 'probes'; probes.mkdir()
        for name in ('ordinary_calls', 'object_calls', 'json_calls', 'json_file_calls'):
            sources = [home / 'bench/recursion' / (name + '.py') for home in HOMES.values() if (home / 'bench/recursion' / (name + '.py')).is_file()]
            assert len({path.read_bytes() for path in sources}) == 1, (name, 'benchmark changed between source variants')
            shutil.copyfile(sources[-1], probes / (name + '.py'))
        text = (probes / 'json_calls.py').read_text()
        warmed = text.replace('print("warm", kernel(text, n))', 'for warmup in range(4):\n    kernel(text, n)\nprint("warm", kernel(text, n))')
        assert warmed != text
        (probes / 'json_warmed.py').write_text(warmed)
        plan = [('ordinary_calls', 'ordinary_calls', 10000000, 0), ('object_calls', 'object_calls', 100000, 0), ('object_long', 'object_calls', 1000000, 0),
                ('json_calls', 'json_calls', 2000, 0), ('json_warmed_short', 'json_warmed', 2000, 4),
                ('json_warmed_long', 'json_warmed', 20000, 4), ('json_file_calls', 'json_file_calls', 20000, 0)]
        for case, stem, n, warmups in plan:
            source = probes / (stem + '.py')
            result['cases'][case] = {'source': str(source), 'source_sha256': replay.digest(source), 'n': n,
                'extra_untimed_kernel_calls': warmups, 'extra_args': [str(out / 'json-input.data')] if case == 'json_file_calls' else [],
                'frontend_ir': {}, 'builds': {}, 'correctness': {}, 'timings': {}}
    else:
        result = json.loads((out / 'measurement.json').read_text())
        assert result['phases']['prepare']['status'] == 'passed'
        assert result['source_identities']['final']['commit'] == args.expected_final_commit, 'unexpected final source commit'
    harness_hashes = {name: replay.digest(Path(__file__).parent / name) for name in (Path(__file__).name, 'count_support.py', 'replay_support.py')}
    if args.phase != 'prepare':
        assert harness_hashes == result['phases']['prepare']['harness_sha256'], 'measurement method changed since prepare'
    def save():
        replay.save_json(out / 'measurement.json', result)
        replay.save_json(out / 'curated.json', summary(result))
    def verify():
        assert {name: replay.digest(Path(__file__).parent / name) for name in harness_hashes} == harness_hashes, 'harness changed during phase'
        assert {key: environment.get(key) for key in ENV_KEYS} == result['selected_environment'], 'environment drift'
        assert {name: {key: env.get(key) for key in ENV_KEYS} for name, env in envs.items()} == result['variant_environment'], 'variant environment drift'
        assert replay.digest(OLD / 'toolchain/manifest.json') == result['toolchain_manifest_sha256']
        for row in result['tool_files'].values():
            assert replay.digest(row['path']) == row['sha256'], ('tool identity drift', row['path'])
        for name, home in HOMES.items():
            assert replay.source_identity(home) == result['source_identities'][name], (name, 'source identity drift')
            native = result['native_compilers'][name]
            assert replay.digest(native['path']) == native['sha256'], (name, 'native binary drift')
            assert replay.digest(native['bootstrap_path']) == native['bootstrap_sha256'], (name, 'build record drift')
            assert replay.digest(native['bootstrap_log_path']) == native['bootstrap_log_sha256'], (name, 'build log drift')
        for case, data in result['cases'].items():
            assert replay.digest(data['source']) == data['source_sha256'], (case, 'input drift')
            for name, row in data['frontend_ir'].items():
                assert replay.digest(out / (name + '-' + case + '.ll')) == row['sha256']
            for name, row in data['builds'].items():
                assert replay.digest(out / (name + '-' + case)) == row['sha256']
    if args.phase == 'summary':
        verify(); save(); return
    assert args.phase not in result['phases'], 'preserve prior attempts; do not overwrite a phase'
    result['phases'][args.phase] = phase = {'status': 'running', 'started_utc': stamp(), 'load_start': os.getloadavg(),
        'harness_sha256': harness_hashes}
    save()
    try:
        verify()
        if args.phase == 'prepare':
            warm = out / 'warm.py'; warm.write_text('print(17)\n')
            result['runtime_warmups'] = {}
            for name, home in HOMES.items():
                row = run([result['native_compilers'][name]['path'], 'run', warm], home, envs[name])
                assert row['stdout'] == '17\n' and not row['stderr']
                result['runtime_warmups'][name] = row; save()
            for case, data in result['cases'].items():
                source, n, extra = data['source'], data['n'], data['extra_args']
                oracle = replay.parse(run([sys.executable, source, n, *extra], out, environment))
                data.update(cpython_oracle=oracle, checksum=oracle['checksum'])
                for name, home in HOMES.items():
                    native = result['native_compilers'][name]['path']
                    raw, exe = out / (name + '-' + case + '.ll'), out / (name + '-' + case)
                    row = run([native, 'ir', source, '-o', raw], home, envs[name])
                    row.update(sha256=replay.digest(raw), ir_lines=raw.read_bytes().count(b'\n'))
                    data['frontend_ir'][name] = row
                    hosted = out / (name + '-' + case + '-hosted.ll')
                    run([sys.executable, '-m', 'pystachy', 'ir', source, '-o', hosted], home, envs[name])
                    assert raw.read_bytes() == hosted.read_bytes(), (name, case, 'hosted/native IR mismatch')
                    row['hosted_ir_sha256'] = replay.digest(hosted)
                    row = run([native, 'build', source, '-o', exe], home, envs[name])
                    row.update(sha256=replay.digest(exe), binary_bytes=exe.stat().st_size)
                    data['builds'][name] = row
                    data['correctness'][name] = {}
                    for mode, cmd in [('jit', [native, 'run', source, n, *extra]), ('aot', [exe, n, *extra])]:
                        data['correctness'][name][mode] = replay.parse(run(cmd, home, envs[name]), data['checksum'])
                    save()
                print('prepared', case, flush=True)
        elif args.phase == 'counts':
            for name in HOMES:
                shutil.copytree(out / (name + '-cache'), out / (name + '-count-cache'))
            count_support.collect(out, result, HOMES, envs, environment, run, save)
        elif args.phase == 'timings':
            names = list(HOMES)
            orders = []
            for index in range(6):
                order = names[index % 3:] + names[:index % 3]
                if index // 3:
                    order.reverse()
                orders.append(order)
            result['timing_orders'] = orders
            for case, data in result['cases'].items():
                for mode in ('jit', 'aot'):
                    data['timings'][mode] = {name: [] for name in HOMES}
                    for round_id, order in enumerate(orders):
                        for name in order:
                            cmd = [result['native_compilers'][name]['path'], 'run', data['source']] if mode == 'jit' else [out / (name + '-' + case)]
                            row = replay.parse(run([*cmd, data['n'], *data['extra_args']], HOMES[name], envs[name]), data['checksum'])
                            row.update(round=round_id, order=order)
                            data['timings'][mode][name].append(row); save()
                    print('timed', case, mode, flush=True)
        verify()
        phase.update(status='passed', finished_utc=stamp(), load_end=os.getloadavg())
        if all(result['phases'].get(key, {}).get('status') == 'passed' for key in ('prepare', 'counts', 'timings')):
            result['status'] = 'complete'
        save()
    except BaseException as error:
        phase.update(status='failed', error=repr(error), finished_utc=stamp())
        if isinstance(error, replay.ReplayFailure):
            phase['failed_command'] = error.record
        save()
        raise


def terminated(signum, frame):
    raise SystemExit(128 + signum)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, terminated)
    main()
