#!/usr/bin/env python3
"""Longer fnmatch AOT runs using only the completed startup series' executables."""
from pathlib import Path
import argparse
import itertools
import json
import os
import signal
import statistics
import sys

from measure_current_v2 import digest, execute, identity, save, stamp

SIZES = (10000, 100000)
ROLES = ('main', 'da84', 'final')
ORDERS = list(itertools.permutations(ROLES))


def main():
    def interrupted(signum, frame):
        raise InterruptedError('received signal ' + str(signum))
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'timings'])
    parser.add_argument('--startup-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    parent_path, out = args.startup_report.resolve(), args.output.resolve()
    parent = json.loads(parent_path.read_text())
    assert parent['status'] == 'complete' and len(parent['samples']) == 108
    assert parent['python'] == sys.version
    homes = {role: Path(parent['source_identities'][role]['directory']) for role in ROLES}
    executables = {role: Path(parent['builds'][role]['executable']) for role in ROLES}
    source = Path(parent['oracles']['fnmatch']['command'][1])
    os.sched_setaffinity(0, {0})
    clean = {key: value for key, value in os.environ.items()
             if not key.startswith(('PYSTACHY_', 'ATTR_')) and key not in ('PYTHONPATH', 'PYTHONHOME')}
    clean.update(PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1')
    environments = {role: dict(clean, **parent['environments'][role]) for role in ROLES}
    path = out / 'report.json'
    if args.phase == 'prepare':
        out.mkdir(parents=True, exist_ok=False)
        frozen = {}
        current = {str(parent_path): digest(parent_path), str(Path(__file__).resolve()): digest(__file__),
                   str(Path(__file__).with_name('measure_current_v2.py').resolve()): digest(Path(__file__).with_name('measure_current_v2.py')),
                   str(Path(sys.executable).resolve()): digest(sys.executable), str(source): digest(source)}
        for binding in (parent['inputs'], parent['current_tool_and_library_files'], current,
                        {str(executables[role]): parent['builds'][role]['sha256'] for role in ROLES}):
            for file, value in binding.items():
                assert file not in frozen or frozen[file] == value, ('conflicting expected hash', file)
                frozen[file] = value
        report = {'schema': 1, 'status': 'incomplete', 'started_utc': stamp(), 'inputs': frozen,
                  'startup_report': str(parent_path), 'startup_report_sha256': digest(parent_path),
                  'source_identities': parent['source_identities'], 'executables': {role: str(path) for role, path in executables.items()},
                  'source': str(source), 'source_sha256': digest(source), 'python': sys.version,
                  'sizes': SIZES, 'orders': ORDERS, 'affinity': [0], 'environments': parent['environments'],
                  'scope': 'Focused new AOT-only follow-up at10x/100x the original fnmatch loop count. Same already-built hash-bound executables; no rebuild, LLVM or compiler invocation. Preserve original108 samples separately. All checksum-validated samples retained; no acceptance threshold inferred.',
                  'phases': {}, 'oracles': {}, 'warmups': [], 'samples': []}
    else:
        report = json.loads(path.read_text())
        assert report['startup_report'] == str(parent_path) and report['startup_report_sha256'] == digest(parent_path)
        assert report['phases']['prepare']['status'] == 'passed'
    def checkpoint():
        save(path, report)
    def verify():
        for file, value in report['inputs'].items():
            assert digest(file) == value, file
        for role, home in homes.items():
            assert identity(home) == parent['source_identities'][role], role
            assert digest(executables[role]) == parent['builds'][role]['sha256'], role
    assert args.phase not in report['phases'], 'retain earlier attempts'
    report['phases'][args.phase] = {'status': 'running', 'started_utc': stamp()}
    checkpoint()
    try:
        verify()
        if args.phase == 'prepare':
            for size in SIZES:
                oracle = execute([sys.executable, source, 'fnmatch', str(size)], clean, source.parent, 180, kernel=True)
                report['oracles'][str(size)] = oracle
                for role in ROLES:
                    row = execute([executables[role], 'fnmatch', str(size)], environments[role], homes[role], 120, oracle['stdout'], True)
                    row.update(role=role, iterations=size)
                    report['warmups'].append(row)
                    checkpoint()
                print('prepared fnmatch', size, flush=True)
        else:
            for round_no, order in enumerate(ORDERS):
                sizes = SIZES if round_no % 2 == 0 else tuple(reversed(SIZES))
                for size in sizes:
                    for role in order:
                        row = execute([executables[role], 'fnmatch', str(size)], environments[role], homes[role], 120,
                                      report['oracles'][str(size)]['stdout'], True)
                        row.update(role=role, iterations=size, round=round_no, position=order.index(role), load_average=os.getloadavg())
                        report['samples'].append(row)
                        checkpoint()
                print('round', round_no + 1, 'complete', len(report['samples']), 'observations', flush=True)
            report['summary'] = {}
            for size in SIZES:
                report['summary'][str(size)] = {}
                for metric in ('loop_s', 'wall_s', 'cpu_s', 'outside_loop_s'):
                    values = {role: [row[metric] for row in report['samples'] if row['iterations'] == size and row['role'] == role] for role in ROLES}
                    assert all(len(vector) == 6 for vector in values.values())
                    medians = {role: statistics.median(vector) for role, vector in values.items()}
                    comparisons = {}
                    for candidate, baseline in [('final', 'main'), ('final', 'da84'), ('da84', 'main')]:
                        ratios = [a/b for a, b in zip(values[candidate], values[baseline])]
                        comparisons[candidate + '_vs_' + baseline] = {'median_ratio': medians[candidate]/medians[baseline],
                            'paired_ratios': ratios, 'paired_median': statistics.median(ratios),
                            'slower_pairs': sum(ratio > 1 for ratio in ratios), 'paired_range': [min(ratios), max(ratios)]}
                    report['summary'][str(size)][metric] = {'samples': values, 'medians': medians,
                        'ranges': {role: [min(vector), max(vector)] for role, vector in values.items()}, 'comparisons': comparisons}
        verify()
        report['phases'][args.phase]['status'] = 'passed'
        report['status'] = 'complete' if all(phase in report['phases'] and report['phases'][phase]['status'] == 'passed' for phase in ('prepare', 'timings')) else 'incomplete'
    except BaseException as error:
        report['status'] = 'failed'
        report['phases'][args.phase].update(status='failed', error=repr(error))
        raise
    finally:
        report['phases'][args.phase]['finished_utc'] = stamp()
        checkpoint()


if __name__ == '__main__':
    main()
