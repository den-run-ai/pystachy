"""Retained parity metadata and post-run summary; importing does not run compilers."""

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess


OUT = Path(__file__).resolve().parent
ROOT = Path('/workspace/scratch/9f30aa4fd4fd/pystachy')
OLD_HOME = Path('/workspace/scratch/78a63a74ecb5/pystachy')
OLD = OLD_HOME / 'pystachy'
NEW = ROOT / 'pystachy'
PATTERNS = ('pystachy.py', 'runtime.py', 'tests/programs/*/*.py',
            'tests/deviations/*.py', 'bench/*.py', 'bench/pyperformance/*.py',
            'tests/ir/*.py', 'tests/errors/*/*.py')
INPUT_ROOTS = ('lib', 'ryu', 'mpz', 'runtime.c', 'runtime.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def file_record(path):
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode):
        result = {'kind': 'symlink', 'target': os.readlink(path)}
        if path.is_file():
            data = path.read_bytes()
            result.update(size=len(data), sha256=sha(data))
        return result
    if stat.S_ISDIR(st.st_mode):
        return {'kind': 'directory'}
    data = path.read_bytes()
    return {'kind': 'file', 'size': len(data), 'sha256': sha(data)}


def manifest(home, names):
    result = {}
    for name in names:
        path = home / name
        if not path.exists() and not path.is_symlink():
            result[name] = {'kind': 'missing'}
            continue
        paths = sorted(path.rglob('*')) if path.is_dir() else [path]
        for item in paths:
            if '__pycache__' in item.parts or item.suffix == '.pyc':
                continue
            if item.is_dir() and not item.is_symlink():
                continue
            result[str(item.relative_to(home))] = file_record(item)
    return result


def git(home, *args):
    return subprocess.check_output(['git', '-C', str(home), *args], text=True).strip()


def snapshot():
    paths = [str(path.relative_to(ROOT)) for pattern in PATTERNS
             for path in sorted(ROOT.glob(pattern)) if path.is_file()]
    return {
        'candidate_commit': git(ROOT, 'rev-parse', 'HEAD'),
        'candidate_status': git(ROOT, 'status', '--porcelain', '--untracked-files=all'),
        'baseline_checkout_commit': git(OLD_HOME, 'rev-parse', 'HEAD'),
        'baseline_checkout_status': git(OLD_HOME, 'status', '--porcelain', '--untracked-files=all'),
        'old': {'path': str(OLD), **file_record(OLD)},
        'new': {'path': str(NEW), **file_record(NEW)},
        'harness': file_record(OUT / 'irsame-retain.sh'),
        'ordered_corpus': paths,
        'corpus_files': {name: file_record(ROOT / name) for name in paths},
        'candidate_inputs': manifest(ROOT, INPUT_ROOTS),
        'baseline_inputs': manifest(OLD_HOME, INPUT_ROOTS),
        # These are reread as source while compiling pystachy.py and corpus imports.
        # Include actual fixture files rather than just tracked filenames.
        'compiler_source': manifest(ROOT, ('pystachy.py', 'pystachy_toolchain.py', 'src')),
        'corpus_dependencies': manifest(ROOT, ('tests', 'bench')),
    }


def summarize():
    problems = []
    before = json.loads((OUT / 'before.json').read_text())
    after = json.loads((OUT / 'after.json').read_text())
    unchanged = before == after
    if not unchanged:
        problems.append({'changed_during_run': [key for key in before
                                               if before[key] != after.get(key)]})
    inputs_equal = before['candidate_inputs'] == before['baseline_inputs']
    if not inputs_equal:
        problems.append('reference and candidate library/runtime inputs differ')
    if before['candidate_status'] or after['candidate_status']:
        problems.append('candidate checkout was dirty')
    status = int((OUT / 'run.status').read_text().strip())
    if status:
        problems.append({'harness_exit': status})
    cases = Path((OUT / 'active-shared-home-dir').read_text().strip())
    paths = (cases / 'corpus').read_text().splitlines()
    if paths != before['ordered_corpus']:
        problems.append('executed corpus differs from pre-run ordered corpus')
    counts = Counter()
    rows = []
    raw_diffs = report_diffs = new_rejections = completed = 0
    for index, path in enumerate(paths, 1):
        case = cases / str(index)
        required = ('status', 'report', 'old.msg', 'new.msg')
        missing = [name for name in required if not (case / name).is_file()]
        if missing:
            problems.append({'index': index, 'path': path, 'missing': missing})
            continue
        exits = (case / 'status').read_text().split()
        if len(exits) != 2 or any(code not in ('0', '1') for code in exits):
            problems.append({'index': index, 'path': path, 'abnormal_status': exits})
            continue
        a, b = map(int, exits)
        old, new = (case / 'old.msg').read_bytes(), (case / 'new.msg').read_bytes()
        raw_equal = old == new
        report_empty = (case / 'report').stat().st_size == 0
        completed += 1
        counts[f'{a}->{b}'] += 1
        raw_diffs += not raw_equal
        report_diffs += not report_empty
        new_rejections += a == 0 and b != 0
        rows.append({'index': index, 'path': path, 'old_exit': a, 'new_exit': b,
                     'raw_diagnostics_identical': raw_equal, 'report_empty': report_empty,
                     'old_diagnostic_sha256': sha(old), 'new_diagnostic_sha256': sha(new)})
    passed = (len(paths) == completed == 4579 and not problems and not raw_diffs
              and not report_diffs and not new_rejections
              and not any(a != b for a, b in (key.split('->') for key in counts)))
    result = {
        'status': 'passed' if passed else 'failed',
        'programs': len(paths), 'completed_reports': completed,
        'exit_counts': dict(counts), 'raw_diagnostic_differences': raw_diffs,
        'ir_or_report_differences': report_diffs, 'new_rejections': new_rejections,
        'case_directory': str(cases), 'problems': problems,
        'candidate_commit': before['candidate_commit'],
        'baseline_checkout_commit': before['baseline_checkout_commit'],
        'old': before['old'], 'new': before['new'],
        'inputs_and_binaries_unchanged': unchanged,
        'library_runtime_inputs_identical': inputs_equal,
        'library_runtime_file_count': len(before['candidate_inputs']),
        'shared_home': str(ROOT), 'ircheck': 'unset',
        'options': 'default', 'workers': 2,
    }
    write_json(OUT / 'case-results.json', rows)
    write_json(OUT / 'summary.json', result)
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(summarize())
