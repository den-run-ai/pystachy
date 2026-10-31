#!/usr/bin/env python3
"""Capture hosted recursion-pass evidence, or link it to a completed backend run.

This controller never invokes LLVM or executes a compiled benchmark. Inspector
and ordinary hosted `ir` output must match literally under identical settings.
"""
from pathlib import Path
import argparse
import collections
import datetime
import hashlib
import json
import os
import platform
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
MIXED = Path('/workspace/scratch/e858f72517b9/baselines/old-eca/bench/smoke/text.py')
GUARDS = ('check', 'room', 'enter', 'leave', 'depth', 'restore')
PREFIXES = ('@rf.', '@rp.', '@rp2.', '@rc.')


def digest(path):
    hashed = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            hashed.update(block)
    return hashed.hexdigest()


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def git(home, *args):
    return subprocess.check_output(['git', *args], cwd=home, text=True).strip()


def identity(home):
    paths = [home / name for name in ('pystachy.py', 'runtime.py', 'runtime.c',
             'pyext.c', 'pyembed.c', 'Makefile', 'VERSION', '.python-version',
             'tools/inspect_compiler.py')]
    for folder in ('src', 'lib', 'mpz', 'ryu'):
        paths.extend(p for p in (home / folder).rglob('*')
                     if p.is_file() and p.suffix in ('.py', '.c', '.h'))
    return {'home': str(home), 'commit': git(home, 'rev-parse', 'HEAD'),
            'tree': git(home, 'rev-parse', 'HEAD^{tree}'),
            'git_status': git(home, 'status', '--porcelain=v1'),
            'inputs': {str(p.relative_to(home)): digest(p) for p in sorted(set(paths))}}


def execute(command, directory, home, environment):
    command = [str(item) for item in command]
    started = time.monotonic()
    row = {'command': command, 'cwd': str(home), 'status': 'running',
           'elapsed_scope': 'controller/observer execution only; not performance acceptance',
           'stdout': str(directory / 'stdout.txt'), 'stderr': str(directory / 'stderr.txt')}
    save(directory / 'execution.json', row)
    with (directory / 'stdout.txt').open('w') as stdout, (directory / 'stderr.txt').open('w') as stderr:
        with subprocess.Popen(command, cwd=home, env=environment, stdout=stdout,
                              stderr=stderr, start_new_session=True) as process:
            try:
                code = process.wait(timeout=180)
            except BaseException as error:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                row.update(status='failed', error=repr(error), observation_wall_s=time.monotonic()-started)
                save(directory / 'execution.json', row)
                raise
    row.update(returncode=code, status='passed' if code == 0 else 'failed',
               observation_wall_s=time.monotonic()-started)
    save(directory / 'execution.json', row)
    assert code == 0, row
    return row


def llvm_inventory(path):
    definitions, current = {}, None
    text = path.read_text()
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith('define '):
            match = re.search(r'(@(?:"(?:[^"\\]|\\.)*"|[^\s(]+))\(', line)
            assert current is None and match is not None, (path, number, line)
            current = {'symbol': match[1], 'header': line, 'start_line': number}
        elif current is not None and line == '}':
            current.update(end_line=number, raw_definition_lines=number-current['start_line']+1)
            assert current['symbol'] not in definitions, current['symbol']
            definitions[current['symbol']] = current
            current = None
    assert current is None, path
    calls = collections.Counter(re.findall(r'\b(?:call|invoke)\b[^\n]*@pys\.recursion\.(check|room|enter|leave|depth|restore)\(', text))
    return {'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size,
            'raw_lines': len(text.splitlines()), 'definition_count': len(definitions),
            'definitions': definitions,
            'private_symbols': {prefix: [symbol for symbol in definitions if symbol.startswith(prefix)] for prefix in PREFIXES},
            'literal_helper_call_sites': {guard: calls[guard] for guard in GUARDS},
            'scope': 'Textual LLVM definition sizes and literal call/invoke sites, not LLVM instruction counts or execution costs.'}


def pass_analysis(directory, record):
    snapshot_path = directory / record['snapshot']
    snapshots = json.loads(snapshot_path.read_text())
    before, after = snapshots['before'], snapshots['after']
    for side, snapshot in [('before', before), ('after', after)]:
        assert snapshot['totals'] == record[side + '_totals']
        assert snapshot['selected_totals'] == record[side + '_selected_totals']
        assert len(snapshot['functions']) == snapshot['totals']['functions']
        assert sum(sum(fn['operations'].values()) for fn in snapshot['functions'].values()) == snapshot['totals']['operation_count']
    changes = []
    for symbol in sorted(before['functions'].keys() | after['functions'].keys()):
        left, right = before['functions'].get(symbol), after['functions'].get(symbol)
        if left != right:
            changes.append({'symbol': symbol, 'change': 'added' if left is None else 'removed' if right is None else 'changed',
                            'before_operations': sum(left['operations'].values()) if left else 0,
                            'after_operations': sum(right['operations'].values()) if right else 0,
                            'before_guards': left['guards'] if left else None,
                            'after_guards': right['guards'] if right else None,
                            'before_recursion': left['recursion'] if left else None,
                            'after_recursion': right['recursion'] if right else None})
    return {**record, 'snapshot_path': str(snapshot_path), 'snapshot_sha256': digest(snapshot_path),
            'function_delta': after['totals']['functions'] - before['totals']['functions'],
            'operation_delta': after['totals']['operation_count'] - before['totals']['operation_count'],
            'slot_delta': after['totals']['slots'] - before['totals']['slots'],
            'guard_deltas': {name: after['totals']['guards'][name] - before['totals']['guards'][name] for name in GUARDS},
            'changed_function_details': changes,
            'function_order_before': before['function_order'], 'function_order_after': after['function_order'],
            'private_symbols_after': {prefix: [symbol for symbol in after['functions'] if symbol.startswith(prefix)] for prefix in PREFIXES}}


def capture(args):
    home, out = args.home.resolve(), args.output.resolve()
    frozen = identity(home)
    assert frozen['commit'] == args.expected_commit and frozen['git_status'] == '', frozen
    out.mkdir(parents=True, exist_ok=False)
    cases = {'object_calls': (home / 'bench/recursion/object_calls.py', 'kernel'),
             'json_calls': (home / 'bench/recursion/json_calls.py', 'object'),
             'mixed_text': (MIXED, 'number')}
    clean = {key: value for key, value in os.environ.items()
             if not key.startswith(('PYSTACHY_', 'ATTR_')) and key not in ('PYTHONHOME', 'PYTHONPATH')}
    clean.update(PYSTACHY_HOME=str(home), PYSTACHY_IRCHECK='1', PYTHONHASHSEED='0',
                 PYTHONDONTWRITEBYTECODE='1', LC_ALL='C')
    inputs = {str(Path(__file__).resolve()): digest(__file__), str(Path(sys.executable).resolve()): digest(sys.executable)}
    inputs.update({str(path): digest(path) for path, _ in cases.values()})
    report = {'schema': 1, 'status': 'running', 'started_utc': stamp(), 'source_identity': frozen,
              'python': {'path': str(Path(sys.executable).resolve()), 'version': sys.version, 'platform': platform.platform()},
              'inputs': inputs, 'runs': {}, 'comparisons': {},
              'scope': 'Hosted compiler inspection only. No LLVM optimizer/code generator or benchmark executes. Every observed raw LLVM module must equal ordinary hosted ir bytes under the same home/source/settings. Observer elapsed time is not startup or kernel evidence.',
              'filter_scope': 'Whole-program summaries and LLVM inventory include every function. Full typed snapshots/diffs retain kernel for object, object for JSON, and number for mixed text; filtering does not change compilation.',
              'limitations': ['Pass return units differ; operation_count excludes slots. Zero transformations do not identify a refusal reason.', 'Raw LLVM line sizes are not instructions or native code size.', 'Typed evidence does not attribute native time or prove performance acceptance.']}
    checkpoint = lambda: save(out / 'report.json', report)
    checkpoint()
    try:
        for case, (source, function) in cases.items():
            for variant in ('default', 'no_region'):
                directory = out / (case + '-' + variant)
                directory.mkdir()
                inspected, ordinary = directory / 'inspected', directory / 'ordinary'
                ordinary.mkdir()
                environment = dict(clean, PYSTACHY_CACHE=str(directory / 'cache'))
                if variant == 'no_region':
                    environment['PYSTACHY_OPT'] = '-recursionregion'
                row = {'status': 'running', 'source': str(source), 'source_sha256': digest(source),
                       'function_filter': function, 'variant': variant,
                       'environment': {key: value for key, value in environment.items()
                                       if key.startswith('PYSTACHY_') or key in ('PYTHONHASHSEED', 'PYTHONDONTWRITEBYTECODE', 'LC_ALL')}}
                report['runs'][case + '/' + variant] = row
                checkpoint()
                row['inspector_execution'] = execute([sys.executable, home / 'tools/inspect_compiler.py', source,
                    '--output', inspected, '--function', function, '--timeout', '150'], directory, home, environment)
                row['ordinary_execution'] = execute([sys.executable, home / 'pystachy.py', 'ir', source,
                    '-o', ordinary / 'llvm.ll'], ordinary, home, environment)
                observed = json.loads((inspected / 'report.json').read_text())
                assert observed['status'] == 'ok' and observed['verification']['completed']
                assert observed['compiler']['revision'] == args.expected_commit
                assert observed['tool']['sha256'] == frozen['inputs']['tools/inspect_compiler.py']
                for entry in observed['compiler']['sources']:
                    assert entry['sha256'] == frozen['inputs'][entry['path']], entry
                expected_env = {'PYSTACHY_HOME': str(home), 'PYSTACHY_IRCHECK': '1'}
                if variant == 'no_region':
                    expected_env['PYSTACHY_OPT'] = '-recursionregion'
                assert observed['settings']['environment'] == expected_env
                assert observed['settings']['function_filter'] == function
                assert observed['input']['sha256'] == row['source_sha256'] and not observed['input']['changed_during_compilation']
                for module in observed['input']['modules']:
                    assert not module['changed_since_read'] and digest(module['path']) == module['sha256'], module
                    report['inputs'][module['path']] = module['sha256']
                assert (inspected / 'llvm.ll').read_bytes() == (ordinary / 'llvm.ll').read_bytes(), directory
                for stream in ('stdout', 'stderr'):
                    assert (inspected / ('compiler.' + stream)).read_bytes() == (ordinary / (stream + '.txt')).read_bytes(), (directory, stream)
                attempts = observed['attempts']
                assert attempts[-1]['status'] == 'completed'
                selected = [record for record in observed['program_passes'] if record['attempt'] == attempts[-1]['index']]
                assert any(record['name'] == 'recursionleaf' for record in selected)
                assert any(record['name'] == 'recursionregion' for record in selected) == (variant == 'default')
                row.update(status='passed', exact_hosted_llvm_and_diagnostic_parity=True,
                           inspector_report=str(inspected / 'report.json'), inspector_report_sha256=digest(inspected / 'report.json'),
                           attempts=attempts, final_attempt_program_passes=[pass_analysis(inspected, record) for record in selected],
                           llvm=llvm_inventory(inspected / 'llvm.ll'),
                           retained_artifacts={str(path): digest(path) for path in sorted(directory.rglob('*')) if path.is_file()})
                assert identity(home) == frozen
                checkpoint()
                print('inspected', case, variant, row['llvm']['raw_lines'], 'raw lines', flush=True)
        for case in cases:
            default, disabled = (report['runs'][case + '/' + variant] for variant in ('default', 'no_region'))
            report['comparisons'][case] = {'scope': 'Region on/off emitted text comparison, not a profitability or missed-proof diagnosis.',
                'raw_lines_delta': default['llvm']['raw_lines'] - disabled['llvm']['raw_lines'],
                'definition_delta': default['llvm']['definition_count'] - disabled['llvm']['definition_count'],
                'default_private_symbols': default['llvm']['private_symbols'], 'no_region_private_symbols': disabled['llvm']['private_symbols'],
                'default_helper_calls': default['llvm']['literal_helper_call_sites'], 'no_region_helper_calls': disabled['llvm']['literal_helper_call_sites']}
        for path, value in report['inputs'].items():
            assert digest(path) == value, path
        assert identity(home) == frozen
        report['status'] = 'complete'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        report['finished_utc'] = stamp()
        checkpoint()


def link_backend(args):
    inspected_path, backend_path, out = args.inspection_report.resolve(), args.backend_report.resolve(), args.output.resolve()
    assert not out.exists(), 'preserve existing linkage evidence'
    inspected, backend = json.loads(inspected_path.read_text()), json.loads(backend_path.read_text())
    assert inspected['status'] == backend['status'] == 'complete'
    assert backend['schema'] == 2 and backend['phases']['profile']['status'] == 'passed'
    candidate = backend['source_identities']['final']
    assert inspected['source_identity']['commit'] == candidate['commit'] and inspected['source_identity']['tree'] == candidate['tree']
    assert inspected['source_identity']['home'] == candidate['directory']
    for name, value in candidate['inputs'].items():
        assert inspected['source_identity']['inputs'][name] == value, name
    row = inspected['runs']['mixed_text/default']
    for path, value in row['retained_artifacts'].items():
        assert digest(path) == value, path
    assert backend['inputs'][row['source']] == row['source_sha256']
    normal = backend_path.parent / 'normal-final'
    assert digest(normal / 'actual-input.ll') == backend['captures']['final']['opt']['input_sha256']
    assert digest(normal / 'optimized-output.bc') == backend['captures']['final']['opt']['output_sha256']
    raw, optimized = llvm_inventory(normal / 'actual-input.ll'), llvm_inventory(normal / 'optimized-output.ll')
    same = raw['sha256'] == row['llvm']['sha256']
    profiles = {}
    for stage in ('opt', 'lli'):
        record = backend['profiles']['final'][stage]
        path = backend_path.parent / (stage + '-final') / (stage + '.callgrind')
        assert digest(path) == record['profile_sha256'] and record['normal_input_runtime_optimized_module_match']
        profiles[stage] = {'path': str(path), 'sha256': digest(path), 'instructions': record['instructions']}
    joined = {symbol: {'raw_definition_lines': definition['raw_definition_lines'],
                      'optimized_definition_lines': optimized['definitions'].get(symbol, {}).get('raw_definition_lines'),
                      'optimized_symbol_retained': symbol in optimized['definitions']}
              for symbol, definition in raw['definitions'].items()}
    result = {'schema': 1, 'status': 'complete' if same else 'raw LLVM mismatch', 'created_utc': stamp(),
              'inspection_report': {'path': str(inspected_path), 'sha256': digest(inspected_path)},
              'backend_report': {'path': str(backend_path), 'sha256': digest(backend_path)},
              'exact_inspector_hosted_native_driver_input_parity': same,
              'scope': 'Path-bound same-candidate mixed input linkage. Complete opt/lli instruction totals include execution/runtime work. Symbol line-size joins describe retained text and are not per-function time attribution.',
              'raw_llvm': raw, 'optimized_llvm': optimized, 'profiles': profiles, 'symbol_join': joined,
              'instruction_comparison': backend['instruction_comparison']}
    save(out, result)
    assert same, 'retained mismatch must be explained before claiming inspected input matches native-driver input'


def main():
    def interrupted(signum, frame):
        raise InterruptedError('received signal ' + str(signum))
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='phase', required=True)
    collect = sub.add_parser('capture')
    collect.add_argument('--home', type=Path, required=True)
    collect.add_argument('--expected-commit', required=True)
    collect.add_argument('--output', type=Path, required=True)
    link = sub.add_parser('link-backend')
    link.add_argument('--inspection-report', type=Path, required=True)
    link.add_argument('--backend-report', type=Path, required=True)
    link.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    (capture if args.phase == 'capture' else link_backend)(args)


if __name__ == '__main__':
    main()
