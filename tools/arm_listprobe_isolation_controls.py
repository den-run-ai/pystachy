"""Temporary native ARM controls; no production source is changed by this runner."""

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import time

import arm_listprobe_diagnostic as diagnostic

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / 'build/arm-listprobe-isolation-controls'
BASE = '8434a911bed2064f50539806d9c05c57003241c3'
BASELINE_SHA256 = 'd8f759ae3c1b81068d6562deda0c70a7d25030cce4b5fddc081d26db26b84622'
CANDIDATE_SHA256 = '1140d47b08075351201d1f04bdf1a141347eb5d315652a0609dbf1fb00a89a82'
RUNTIME_IR_SHA256 = 'cd645bebc4fea57b4824b5393843fea99bb31880a31a79dd825e1f34c388f830'
FULL_PASS = 'listprobe: empty-list reuse, inline short lists, range-list storage/mutation, pointer-free list kinds, numeric identity, promoting storage, native Any boundaries and large-object collections passed'
LIVE_ASSERTION = 'listprobe: cleared list storage survives collection'


def once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


def retain_budget(source):
    source = once(source, 'static List *buffers;', 'static List *buffers;\nstatic I retained_budget;')
    source = once(source, 'static I *roots[] = {(I *)&buffers};',
                  'static I *roots[] = {(I *)&buffers, &retained_budget};')
    source = once(source, 'gc_init(__builtin_frame_address(0), roots, 1);',
                  'gc_init(__builtin_frame_address(0), roots, 2);')
    source = once(source, '  pys_alloc(32 << 20);', '  retained_budget = (I)pys_alloc(32 << 20);')
    source = once(source,
                  '  if (!gc_stress && gc_n - before != 1) bad("a scanned candidate still uses the 32 MiB budget");\n  scrub_collect();',
                  '  if (!gc_stress && gc_n - before != 1) bad("a scanned candidate still uses the 32 MiB budget");\n'
                  '  scrub_collect();\n'
                  '  if (gc_live < 33554433 || gc_seg((void *)retained_budget)->size != 33554433) bad("CONTROL retained budget root lost");\n'
                  '  fprintf(stderr, "CONTROL retained 32MiB candidate live=%lld\\n", (long long)gc_live);')
    return source


def retain_backings(source):
    source = once(source, 'static List *buffers;', 'static List *buffers;\nstatic I retained_old_backings[2];')
    source = once(source, 'static I *roots[] = {(I *)&buffers};',
                  'static I *roots[] = {(I *)&buffers, retained_old_backings, retained_old_backings + 1};')
    source = once(source, 'gc_init(__builtin_frame_address(0), roots, 1);',
                  'gc_init(__builtin_frame_address(0), roots, 3);')
    return once(source, '    l->len = 65536;',
                 '    l->len = 65536;\n    if (i < 2) retained_old_backings[i] = (I)l->a;')


def child_change(source, old, new):
    before, body = source.split('static void budget_candidates_in_child(void) {', 1)
    body, after = body.split('\n}', 1)
    return before + 'static void budget_candidates_in_child(void) {' + once(body, old, new) + '\n}' + after


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def control_cases(baseline, candidate):
    pattern = r'static void budget_candidates\(void\) \{.*?\n\}'
    assert re.search(pattern, baseline, re.S).group() == re.search(pattern, candidate, re.S).group()
    assert baseline.count('if (gc_live >= 1048576)') == candidate.count('if (gc_live >= 1048576)') == 1
    return [
        ('candidate', candidate, 0, [FULL_PASS]),
        ('baseline-retained-budget', retain_budget(baseline), 1, ['CONTROL retained 32MiB candidate live=', LIVE_ASSERTION]),
        ('candidate-retained-budget', retain_budget(candidate), 0, ['CONTROL retained 32MiB candidate live=', FULL_PASS]),
        ('candidate-retained-backings', retain_backings(candidate), 1, [LIVE_ASSERTION]),
        ('candidate-budget-assertion', once(candidate, '  I before = gc_n;\n  pys_alloc(5 << 20);',
                                          '  I before = gc_n;\n  bad("CONTROL forced budget assertion");\n  pys_alloc(5 << 20);'),
         1, ['CONTROL forced budget assertion', 'budget candidate child failed']),
        ('candidate-child-signal', child_change(candidate, 'budget_candidates(); _exit(0);',
                                                'budget_candidates(); raise(SIGTERM); _exit(0);'),
         1, ['budget candidate child failed']),
        ('candidate-fork-error', child_change(candidate, 'pid_t child = fork();',
                                              'pid_t child = (errno = EAGAIN, -1);'),
         1, ['budget candidate fork']),
        ('candidate-wait-error', child_change(candidate, 'do waited = waitpid(child, &status, 0);',
                                              'do { waited = waitpid(child, &status, 0); if (waited == child) { errno = ECHILD; waited = -1; } }'),
         1, ['budget candidate wait']),
        ('candidate-eintr', child_change(candidate, 'do waited = waitpid(child, &status, 0);',
                                         'int interrupted = 0;\n  do { if (!interrupted++) { errno = EINTR; waited = -1; } else waited = waitpid(child, &status, 0); }'),
         0, [FULL_PASS]),
    ]


def main():
    os.chdir(REPO)
    OUTPUT.mkdir(parents=True, exist_ok=False)
    environment = diagnostic.clean_environment()
    llvm = Path(environment['PYSTACHY_LLVM'])
    deadline = time.monotonic() + 600
    report = {'base': BASE, 'candidate_sha256': CANDIDATE_SHA256,
              'baseline_sha256': BASELINE_SHA256, 'llvm': str(llvm),
              'python': sys.version, 'platform': platform.platform(), 'machine': platform.machine(),
              'sha': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID'),
              'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'), 'requested_runs': 18,
              'build': [], 'runs': [], 'status': 'incomplete'}
    try:
        if platform.machine() != 'aarch64':
            raise RuntimeError('the controls require the native ARM runner')
        diagnostic.require_build(
            ['git', 'diff', '--exit-code', BASE, '--', '.',
             ':(exclude).github/workflows/arm-listprobe-diagnostic.yml',
             ':(exclude)tools/arm_listprobe_diagnostic.py',
             ':(exclude)tools/arm_listprobe_trace.h',
             ':(exclude)tools/test_arm_listprobe_diagnostic.py',
             ':(exclude)tools/arm_listprobe_candidate.c',
             ':(exclude)tools/arm_listprobe_isolation_controls.py'],
            OUTPUT / 'source-identity.log', environment, deadline, report)
        baseline_path = REPO / 'tools/listprobe.c'
        candidate_path = REPO / 'tools/arm_listprobe_candidate.c'
        if sha(baseline_path) != BASELINE_SHA256 or sha(candidate_path) != CANDIDATE_SHA256:
            raise RuntimeError('baseline or reviewed candidate source identity differs')
        cases = control_cases(baseline_path.read_text(), candidate_path.read_text())
        if len(cases) != 9:
            raise RuntimeError('expected nine distinct control cases')
        diagnostic.require_build([str(llvm / 'clang'), '--version'], OUTPUT / 'clang-version.log',
                                 environment, deadline, report)
        diagnostic.require_build(['git', 'rev-parse', 'HEAD'], OUTPUT / 'commit.log',
                                 environment, deadline, report)
        shutil.copyfile('/proc/cpuinfo', OUTPUT / 'cpuinfo.txt')
        runtime_ir = OUTPUT / 'rt1.ll'
        diagnostic.require_build([sys.executable, 'pystachy.py', 'rt', 'runtime.py', '-o', str(runtime_ir)],
                                 OUTPUT / 'runtime-build.log', environment, deadline, report)
        report['runtime_ir_sha256'] = sha(runtime_ir)
        if report['runtime_ir_sha256'] != RUNTIME_IR_SHA256:
            raise RuntimeError('runtime IR differs from both retained ARM bootstraps')
        for name, source, expected_code, expected_text in cases:
            directory = OUTPUT / name
            (directory / 'tools').mkdir(parents=True, exist_ok=False)
            (directory / 'tools/listprobe.c').write_text(source)
            shutil.copyfile(REPO / 'runtime.c', directory / 'runtime.c')
            commands = [
                [str(llvm / 'clang'), '-O2', '-S', '-emit-llvm', '-I', str(REPO), str(directory / 'tools/listprobe.c'), '-o', str(directory / 'listprobe.ll')],
                [str(llvm / 'llvm-link'), str(runtime_ir), str(directory / 'listprobe.ll'), '-o', str(directory / 'listprobe.bc')],
                [str(llvm / 'clang'), '-O2', str(directory / 'listprobe.bc'), '-o', str(directory / 'listprobe'), '-lm'],
            ]
            if name == 'candidate':
                commands.extend([
                    [str(llvm / 'llvm-dis'), str(directory / 'listprobe.bc'), '-o', str(directory / 'linked.ll')],
                    [str(llvm / 'clang'), '-O2', '-S', str(directory / 'listprobe.bc'), '-o', str(directory / 'listprobe.s')],
                ])
            for index, argv in enumerate(commands):
                diagnostic.require_build(argv, directory / f'build-{index}.log', environment, deadline, report)
            for mode in ('normal', 'stress'):
                active = environment.copy()
                if mode == 'stress':
                    active['PYSTACHY_GC_STRESS'] = '1'
                log = directory / f'{mode}.log'
                result = diagnostic.run([str(directory / 'listprobe')], log, active, deadline, 30)
                output = log.read_text()
                matched = result['returncode'] == expected_code and all(text in output for text in expected_text)
                if 'retained-budget' in name:
                    marker = re.search(r'CONTROL retained 32MiB candidate live=(\d+)', output)
                    matched = matched and marker is not None and int(marker.group(1)) >= 33554433
                result.update(case=name, mode=mode, expected_returncode=expected_code,
                              expected_messages=expected_text, matched=bool(matched),
                              source_sha256=sha(directory / 'tools/listprobe.c'), output=output)
                report['runs'].append(result)
                (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
                print(json.dumps({key: result[key] for key in ('case', 'mode', 'returncode', 'matched', 'output')}), flush=True)
        complete = len(report['runs']) == 18 and all(result['matched'] for result in report['runs'])
        report['status'] = 'passed' if complete else 'failed'
    except (AssertionError, OSError, RuntimeError, ValueError, TimeoutError) as error:
        report['error'] = str(error)
        print(f'control harness failed: {error}', file=sys.stderr, flush=True)
    finally:
        report['files'] = {str(path.relative_to(OUTPUT)): sha(path) for path in sorted(OUTPUT.rglob('*'))
                           if path.is_file() and path.name != 'report.json'}
        (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'status': report['status'], 'runs': len(report['runs']),
                          'matched': sum(result['matched'] for result in report['runs'])}), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
