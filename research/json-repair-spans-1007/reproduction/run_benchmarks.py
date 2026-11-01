#!/usr/bin/env python3
"""Paired span benchmarks. Planning is the default; execute only with --run.

Run only after native validation/builds have stopped and both source trees are
frozen. This harness executes one process at a time and writes a checkpoint after
every completed run. It never builds or edits either repository.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import statistics
import subprocess
import time


ROOT = Path(os.environ['PYSTACHY_SPAN_ROOT']).expanduser().resolve()
EVIDENCE = ROOT / 'span-evidence'
PROBE = ROOT / 'pystachy-spans/bench/extended/json_repair_spans.py'
SOURCES = {
    'base': ROOT / 'pystachy-combined-base',
    'candidate': ROOT / 'pystachy-combined-candidate',
}
BINARIES = {
    'base': EVIDENCE / 'bench-base',
    'candidate': EVIDENCE / 'bench-candidate-fast',
}
LLVM = Path(os.environ.get('PYSTACHY_LLVM', '/usr/lib/llvm-18/bin')).expanduser().resolve()
CPU = int(os.environ.get('PYSTACHY_SPAN_CPU', '0'))
WATCHDOG_SECONDS = 120
WARMUPS = 3
SAMPLES = 7
ROUNDS = {
    'short': 20000, 'mixed': 5000, 'long': 200, 'sparse': 200,
    'dense': 100, 'unicode': 100, 'punctuation': 100, 'regex': 100,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_output(args: list[str], cwd: Path | None = None) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def make_plan() -> list[dict]:
    plan = []
    groups = [
        ('objects', 5, [(engine, 'objects', case, 4096, rounds)
                        for engine in ('aot', 'jit') for case, rounds in ROUNDS.items()]),
        ('serialization', 3, [('aot', 'serialize', case, 4096, ROUNDS[case])
                             for case in ('long', 'sparse', 'dense', 'unicode')]),
        ('scaling', 3, [('aot', 'objects', case, size, 100)
                       for case in ('long', 'sparse') for size in (8192, 16384)]),
    ]
    for group, pairs, cases in groups:
        for pair in range(pairs):
            offset = pair % len(cases)
            rotated = cases[offset:] + cases[:offset]
            for position, (engine, mode, case, size, rounds) in enumerate(rotated):
                # Each case alternates the first variant across repeated pairs.
                order = ('base', 'candidate') if pair % 2 == 0 else ('candidate', 'base')
                for variant in order:
                    plan.append({
                        'group': group, 'pair': pair, 'case_order': position,
                        'engine': engine, 'mode': mode, 'case': case,
                        'size': size, 'rounds': rounds, 'warmups': WARMUPS,
                        'samples': SAMPLES, 'variant': variant,
                    })
    return plan


def source_identity(source: Path) -> dict:
    paths = {source / name for name in ('pystachy.py', 'runtime.py', 'runtime.c')}
    for name in ('src', 'lib', 'ports', 'ryu', 'mpz'):
        paths.update(path for path in (source / name).rglob('*')
                     if path.is_file() and path.suffix in {'.py', '.c', '.h'})
    files = {str(path.relative_to(source)): sha256(path) for path in sorted(paths)}
    return {
        'directory': str(source),
        'commit': command_output(['git', 'rev-parse', 'HEAD'], source),
        'status': command_output(['git', 'status', '--porcelain=v1', '--untracked-files=all'], source),
        'compiler_sha256': sha256(source / 'pystachy'),
        'files': files,
        'files_digest': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
    }


def environment(variant: str) -> dict[str, str]:
    # Supply and retain the complete process environment, without forwarding
    # credentials or inherited optimization/GC settings from the agent session.
    return {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'LANG': 'C.UTF-8',
        'LC_ALL': 'C.UTF-8',
        'PYSTACHY_HOME': str(SOURCES[variant]),
        'PYSTACHY_PATH': str(SOURCES[variant] / 'ports'),
        'PYSTACHY_CACHE': str(EVIDENCE / ('paired-cache-' + variant)),
        'PYSTACHY_LLVM': str(LLVM),
    }


def argv_for(row: dict) -> list[str]:
    variant = row['variant']
    args = [row['mode'], row['case'], str(row['size']), str(row['rounds']),
            str(row['warmups']), str(row['samples'])]
    command = ([str(BINARIES[variant])] if row['engine'] == 'aot' else
               [str(SOURCES[variant] / 'pystachy'), 'run', str(PROBE)])
    return ['/usr/bin/taskset', '-c', str(CPU), *command, *args]


def parse_probe(stdout: str, row: dict) -> dict:
    lines = [line.split() for line in stdout.splitlines()]
    assert len(lines) == 3 + row['warmups'] + row['samples'], lines
    case = lines[0]
    assert len(case) == 7 and case[:4] == [
        'case', row['mode'], row['case'], str(row['size'])], case
    expected_calls = row['rounds'] * (5 if row['case'] == 'mixed' else 1)
    assert int(case[6]) == expected_calls, case
    assert len(lines[-1]) == 2 and lines[-1][0] == 'verified', lines[-1]
    per_round = int(lines[-1][1])
    checksum = row['rounds'] * per_round
    assert len(lines[1]) == 3 and lines[1][0] == 'first' and int(lines[1][1]) == checksum
    first_ns = int(lines[1][2])
    assert first_ns >= 0
    for line in lines[2:2 + row['warmups']]:
        assert len(line) == 2 and line[0] == 'warmup' and int(line[1]) == checksum, line
    samples = []
    for line in lines[2 + row['warmups']:-1]:
        assert len(line) == 3 and line[0] == 'sample' and int(line[1]) == checksum, line
        elapsed = int(line[2])
        assert elapsed > 0, line
        samples.append(elapsed)
    assert len(samples) == row['samples']
    return {
        'witness': {'case': case, 'verified_per_round': per_round, 'checksum': checksum},
        'first_ns': first_ns, 'samples_ns': samples,
        'median_ns': statistics.median(samples),
    }


def run_process(row: dict, number: int, output: Path) -> dict:
    name = (f"{number:03d}-{row['variant']}-{row['engine']}-{row['mode']}-"
            f"{row['case']}-{row['size']}-pair{row['pair']}")
    stdout_path, stderr_path = output / (name + '.stdout'), output / (name + '.stderr')
    args = argv_for(row)
    env = environment(row['variant'])
    Path(env['PYSTACHY_CACHE']).mkdir(parents=True, exist_ok=True)
    record = dict(row, argv=args, environment=env, cwd=str(SOURCES[row['variant']]),
                  stdout_file=str(stdout_path), stderr_file=str(stderr_path),
                  started_at=datetime.now(timezone.utc).isoformat(), load_before=os.getloadavg())
    start = time.monotonic()
    with stdout_path.open('wb') as stdout, stderr_path.open('wb') as stderr:
        process = subprocess.Popen(args, cwd=SOURCES[row['variant']], env=env,
                                   stdout=stdout, stderr=stderr, start_new_session=True)
        timed_out = False
        try:
            while True:
                pid, status, usage = os.wait4(process.pid, os.WNOHANG)
                if pid:
                    break
                if time.monotonic() - start > WATCHDOG_SECONDS:
                    timed_out = True
                    os.killpg(process.pid, signal.SIGKILL)
                    pid, status, usage = os.wait4(process.pid, 0)
                    break
                time.sleep(0.05)
        except BaseException:
            # Only this harness's owned process group is stopped on interruption.
            os.killpg(process.pid, signal.SIGKILL)
            _, status, _ = os.wait4(process.pid, 0)
            process.returncode = os.waitstatus_to_exitcode(status)
            raise
        process.returncode = os.waitstatus_to_exitcode(status)
    record.update(
        returncode=process.returncode, timed_out=timed_out,
        wall_seconds=time.monotonic() - start, load_after=os.getloadavg(),
        stdout=stdout_path.read_text(), stderr=stderr_path.read_text(),
        rusage={name: getattr(usage, name) for name in (
            'ru_utime', 'ru_stime', 'ru_maxrss', 'ru_minflt', 'ru_majflt', 'ru_nvcsw', 'ru_nivcsw')},
        rss_scope=('AOT process peak RSS, KiB' if row['engine'] == 'aot' else
                   'Whole compiler/JIT launch and waited-for children; ru_maxrss KiB is a maximum, not aggregate concurrent memory'),
    )
    if process.returncode == 0:
        try:
            record['result'] = parse_probe(record['stdout'], row)
        except (AssertionError, ValueError, IndexError) as exc:
            record['validation_error'] = repr(exc)
    return record


def comparison_key(row: dict) -> tuple:
    return tuple(row[key] for key in ('group', 'engine', 'mode', 'case', 'size', 'rounds'))


def summarize(runs: list[dict]) -> list[dict]:
    groups = {}
    for row in runs:
        if 'result' in row:
            groups.setdefault(comparison_key(row), []).append(row)
    summary = []
    for key, rows in groups.items():
        base = {row['pair']: row for row in rows if row['variant'] == 'base'}
        candidate = {row['pair']: row for row in rows if row['variant'] == 'candidate'}
        pairs = sorted(base.keys() & candidate.keys())
        if not pairs:
            continue
        for pair in pairs:
            assert base[pair]['result']['witness'] == candidate[pair]['result']['witness'], (key, pair)
        base_ns = [base[pair]['result']['median_ns'] for pair in pairs]
        candidate_ns = [candidate[pair]['result']['median_ns'] for pair in pairs]
        base_median, candidate_median = statistics.median(base_ns), statistics.median(candidate_ns)
        ratios = [candidate_ns[i] / base_ns[i] for i in range(len(pairs))]
        entry = dict(zip(('group', 'engine', 'mode', 'case', 'size', 'rounds'), key))
        entry.update(
            pairs=len(pairs), base_process_medians_ns=base_ns,
            candidate_process_medians_ns=candidate_ns,
            base_median_ns=base_median, candidate_median_ns=candidate_median,
            ratio_of_medians=candidate_median / base_median,
            percent_change_of_medians=(candidate_median / base_median - 1) * 100,
            speedup_of_medians=base_median / candidate_median,
            paired_ratios=ratios, median_paired_ratio=statistics.median(ratios),
            median_paired_percent_change=(statistics.median(ratios) - 1) * 100,
            base_peak_rss_kib=[base[pair]['rusage']['ru_maxrss'] for pair in pairs],
            candidate_peak_rss_kib=[candidate[pair]['rusage']['ru_maxrss'] for pair in pairs],
            witness=base[pairs[0]]['result']['witness'],
        )
        summary.append(entry)
    return summary


def markdown(summary: list[dict], complete: bool, elapsed: float) -> str:
    lines = [
        '# Paired ordinary-span measurements', '',
        f'Campaign complete: {complete}. Elapsed wall time: {elapsed:.1f} seconds.', '',
        'All values are batch times. Lower is better. Each process median uses seven',
        'measured batches after a separate first batch and three warmups. Reported',
        'times are medians across processes; paired percentages are medians of each',
        'candidate/base process pair. Negative changes mean a faster candidate.', '',
        '| Engine | Mode | Case | Size | Rounds | Pairs | Base ms | Candidate ms | Change | Paired change | Speedup |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for row in summary:
        lines.append(
            f"| {row['engine']} | {row['mode']} | {row['case']} | {row['size']} | {row['rounds']} | "
            f"{row['pairs']} | {row['base_median_ns'] / 1e6:.3f} | {row['candidate_median_ns'] / 1e6:.3f} | "
            f"{row['percent_change_of_medians']:+.2f}% | {row['median_paired_percent_change']:+.2f}% | "
            f"{row['speedup_of_medians']:.3f}× |")
    lines.extend([
        '', '## Scope', '',
        f'These are repeated synthetic controls on the recorded host, pinned to CPU {CPU}.',
        'Every native process performs exact full-value, code-point and serialization',
        'checks outside timing. Baseline/candidate witnesses must also match.',
        'All repairs force skip_json_loads=True, isolating the repair parser.',
        'The baseline includes #1003 and #1004; the candidate adds ordinary spans',
        'and the one-code-point storage fast path. See metadata.json for every source',
        'hash, binary hash, command environment, toolchain and CPU identity.', '',
        'Native AOT peak RSS excludes compilation. JIT RSS covers the entire compiler/JIT',
        'launch and waited-for children, and ru_maxrss reports a maximum rather than',
        'the sum of simultaneously resident processes. Treat startup and RSS separately',
        'from steady batch times. No CPython, PyPy or GraalPy ranking is established.', '',
    ])
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='execute the prepared campaign')
    parser.add_argument('--output', type=Path, default=EVIDENCE / 'paired-native')
    args = parser.parse_args()
    plan = make_plan()
    if not args.run:
        print(json.dumps({'processes': len(plan), 'groups': {
            name: sum(row['group'] == name for row in plan)
            for name in ('objects', 'serialization', 'scaling')},
            'cpu': CPU, 'watchdog_seconds': WATCHDOG_SECONDS,
            'warmups': WARMUPS, 'samples': SAMPLES,
            'execution': f'{__file__} --run --output {args.output}', 'plan': plan}, indent=2))
        return
    if CPU not in os.sched_getaffinity(0):
        raise SystemExit(f'CPU {CPU} is not available; explicitly set PYSTACHY_SPAN_CPU to an allowed CPU')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    identities = {variant: source_identity(source) for variant, source in SOURCES.items()}
    input_hash = sha256(PROBE)
    parser_hashes = {variant: sha256(source / 'ports/json_repair/parse_string.py')
                     for variant, source in SOURCES.items()}
    metadata = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'cpu': CPU, 'allowed_cpus': sorted(os.sched_getaffinity(0)),
        'platform': platform.platform(), 'machine': platform.machine(),
        'cpuinfo': Path('/proc/cpuinfo').read_text().split('\n\n')[0],
        'initial_load': os.getloadavg(), 'sources': identities,
        'probe': {'path': str(PROBE), 'sha256': input_hash},
        'binaries': {variant: {'path': str(binary), 'sha256': sha256(binary),
                               'bytes': binary.stat().st_size} for variant, binary in BINARIES.items()},
        'llvm': {tool: command_output([str(LLVM / tool), '--version'])
                 for tool in ('clang', 'lli', 'opt')},
        'environment': {variant: environment(variant) for variant in SOURCES},
        'watchdog_seconds': WATCHDOG_SECONDS, 'plan': plan,
    }
    atomic_json(output / 'metadata.json', metadata)
    runs = []
    started = time.monotonic()
    complete = False
    try:
        for number, row in enumerate(plan, 1):
            assert sha256(PROBE) == input_hash, 'benchmark changed during campaign'
            for variant, source in SOURCES.items():
                assert sha256(source / 'ports/json_repair/parse_string.py') == parser_hashes[variant], 'parser changed during campaign'
            record = run_process(row, number, output)
            runs.append(record)
            atomic_json(output / 'runs.json', runs)
            if record['returncode'] or record.get('validation_error'):
                raise RuntimeError(f"run {number} failed: {record['returncode']} {record.get('validation_error', '')}")
            summary = summarize(runs)  # checks paired witnesses immediately
            atomic_json(output / 'summary.json', summary)
            print(f"{number}/{len(plan)} {row['variant']} {row['engine']} {row['mode']} "
                  f"{row['case']} n={row['size']} median={record['result']['median_ns'] / 1e6:.3f} ms "
                  f"wall={record['wall_seconds']:.2f}s", flush=True)
        final_identities = {variant: source_identity(source) for variant, source in SOURCES.items()}
        atomic_json(output / 'final-identities.json', final_identities)
        for variant in SOURCES:
            assert final_identities[variant]['files'] == identities[variant]['files'], 'source changed during campaign'
            assert final_identities[variant]['compiler_sha256'] == identities[variant]['compiler_sha256'], 'compiler changed during campaign'
            assert sha256(BINARIES[variant]) == metadata['binaries'][variant]['sha256'], 'AOT executable changed during campaign'
        complete = True
    finally:
        elapsed = time.monotonic() - started
        summary_error = None
        try:
            summary = summarize(runs)
        except (AssertionError, ValueError, KeyError) as exc:
            summary = []
            summary_error = repr(exc)
        atomic_json(output / 'summary.json', summary)
        atomic_json(output / 'completion.json', {
            'complete': complete, 'completed_processes': len(runs), 'planned_processes': len(plan),
            'elapsed_seconds': elapsed, 'finished_at': datetime.now(timezone.utc).isoformat(),
            'summary_error': summary_error,
        })
        (output / 'summary.md').write_text(markdown(summary, complete, elapsed))


if __name__ == '__main__':
    main()
