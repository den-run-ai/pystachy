"""Compare fresh current-main and candidate frontends with each compiler's own library home."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time

ARTIFACTS = {'pystachy', 'build/pystachy1', 'build/pystachy2',
             *(f'build/stage{n}.ll' for n in (1, 2, 3)), *(f'build/rt{n}.ll' for n in (1, 2, 3))}
DESCRIPTORS = {'Makefile', 'VERSION', '.python-version'}
SUFFIXES = {'.py', '.c', '.h', '.path', '.in', '.sh', '.out', '.err', '.fx', '.calls', '.attrs', '.tbaa'}
EXCLUSIONS = 'Root build/ and all .git/, __pycache__/ and .pytest_cache/ directories; non-source/cache binaries and logs. Ignored source files outside those generated directories are included. No parser-only check, LLVM validation or execution phase is added.'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return sha(Path(path).read_bytes())


def save(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()


def identity(repo):
    return dict(commit=git(repo, 'rev-parse', 'HEAD'), tree=git(repo, 'rev-parse', 'HEAD^{tree}'),
                status=git(repo, 'status', '--porcelain=v1'))


def snapshot(repo):
    # Imports from .path sidecars include examples/, ports/ and tools/rt_cpython.
    # Walking the working tree, rather than git ls-files, also catches ignored inputs.
    files, links = {}, {}
    for directory, dirs, names in os.walk(repo, followlinks=False):
        base = Path(directory)
        dirs[:] = sorted(d for d in dirs if d not in {'.git', '__pycache__', '.pytest_cache'}
                         and not (base == repo and d == 'build'))
        for name in sorted([*dirs, *names]):
            path = base / name
            rel = str(path.relative_to(repo))
            if path.is_symlink():
                links[rel] = os.readlink(path)
            if path.is_file() and (path.suffix in SUFFIXES or rel in {'Makefile', 'VERSION', '.python-version'}):
                assert path.resolve().is_relative_to(repo), ('unbound external source', rel)
                files[rel] = digest(path)
    return dict(files=files, symlinks=links)


def bootstrap_snapshot(repo):
    # Match the fresh bootstrap producer's complete consumed-input selector,
    # including ignored files, rather than inferring coverage from tracked status.
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=repo).decode().split('\0')
    paths = {name for name in names if name and
             (name in {'pystachy.py', 'runtime.c', 'runtime.py', 'pyembed.c', 'pyext.c'} or
              name.startswith(('src/', 'lib/', 'ryu/', 'mpz/')))}
    for folder in ('src', 'lib', 'ryu', 'mpz'):
        paths.update(str(p.relative_to(repo)) for p in (repo / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts)
    return {name: digest(repo / name) for name in sorted(paths)
            if (repo / name).is_file() and not name.endswith('.pyc')}


def validate_build(home, source, proof, log):
    assert proof.get('record_kind') != 'equivalent_build_binding' and proof.get('fresh_local_build') is True
    assert proof['status'] == 'complete' and proof['exit_code'] == 0 and proof['source_identity_stable']
    assert Path(proof['source']).resolve() == home
    assert proof['commit'] == source['commit'] and proof['tree'] == source['tree']
    assert proof['before'] == proof['after'] == bootstrap_snapshot(home), 'bootstrap consumed-input drift'
    assert digest(log) == proof['log_sha256'], 'bootstrap log drift'
    assert set(proof['artifacts']) == ARTIFACTS, 'all nine actual build artifacts required'
    for name, recorded in proof['artifacts'].items():
        data = (home / name).read_bytes()
        assert len(data) == recorded['bytes'] and sha(data) == recorded['sha256'], name
        if name.endswith('.ll'):
            assert data.count(b'\n') == recorded['lines'], name
    assert proof['artifacts']['pystachy']['sha256'] == proof['artifacts']['build/pystachy2']['sha256']
    for stem in ('stage', 'rt'):
        assert len({proof['artifacts'][f'build/{stem}{n}.ll']['sha256'] for n in (1, 2, 3)}) == 1
    # These three clean committed inputs were outside the bootstrap selector.
    # Preserve that limitation explicitly and freeze the actual commit bytes.
    descriptors = {}
    for name in sorted(DESCRIPTORS):
        data = subprocess.check_output(['git', 'show', source['commit'] + ':' + name], cwd=home)
        assert (home / name).read_bytes() == data, name
        descriptors[name] = sha(data)
    return descriptors


def diagnostic_comparison(streams, homes, manifests):
    """Allow only a demonstrated source-location checkout-prefix difference."""
    a_stdout, a_stderr = streams['main']
    b_stdout, b_stderr = streams['candidate']
    raw_equal = a_stdout == b_stdout and a_stderr == b_stderr
    if raw_equal or a_stdout != b_stdout:
        return raw_equal, raw_equal, None
    pattern = rb'([^\r\n]+\.py):([0-9]+): error: ([^\r\n]*)\n'
    a, b = re.fullmatch(pattern, a_stderr), re.fullmatch(pattern, b_stderr)
    if a is None or b is None or a.group(2, 3) != b.group(2, 3):
        return False, False, None
    relative = {}
    for role, match in [('main', a), ('candidate', b)]:
        prefix = os.fsencode(str(homes[role])) + b'/'
        if not match.group(1).startswith(prefix):
            return False, False, None
        rel = os.fsdecode(match.group(1)[len(prefix):])
        if rel not in manifests[role]['files'] or str(Path(rel)) != rel or '..' in Path(rel).parts:
            return False, False, None
        relative[role] = rel
    rel = relative['main']
    if relative['candidate'] != rel or manifests['main']['files'][rel] != manifests['candidate']['files'][rel]:
        return False, False, None
    normalized = os.fsencode(rel) + b':' + a.group(2) + b': error: ' + a.group(3) + b'\n'
    return False, True, dict(kind='identical_source_location_checkout_prefix_only',
                             relative_source=rel, source_sha256=manifests['main']['files'][rel],
                             line=int(a.group(2)), normalized_stderr_sha256=sha(normalized),
                             main_prefix=str(homes['main']) + '/', candidate_prefix=str(homes['candidate']) + '/')


def plan_cases(repo, env):
    strays = subprocess.check_output(['sh', '-c', '. tests/corpus.sh; corpus_strays'], cwd=repo, env=env, text=True)
    assert not strays, ('official corpus has untested stray files', strays)
    corpus = subprocess.check_output(['sh', '-c', '. tests/corpus.sh; corpus'], cwd=repo, env=env, text=True).splitlines()
    independent = {str(p.relative_to(repo)) for pattern in
                   ('tests/programs/*/*.py', 'tests/deviations/*.py', 'tests/errors/*/*.py')
                   for p in repo.glob(pattern) if p.is_file()}
    assert corpus and len(corpus) == len(set(corpus)) and set(corpus) == independent
    assert any(p.startswith('tests/programs/') for p in corpus) and any(p.startswith('tests/errors/') for p in corpus)
    extra = ['pystachy.py', 'runtime.py']
    for pattern in ('bench/*.py', 'bench/pyperformance/*.py', 'bench/recursion/*.py', 'tests/ir/*.py'):
        extra += [str(p.relative_to(repo)) for p in sorted(repo.glob(pattern)) if p.is_file()]
    cases = extra + [p for p in corpus if p not in extra]
    assert len(cases) == len(set(cases)) and all((repo / p).is_file() for p in cases)
    plan = []
    for case in cases:
        rejected = case.startswith('tests/errors/')
        want = ''
        if rejected:
            first = (repo / case).read_bytes().splitlines()[0].decode('utf-8', 'surrogateescape')
            assert first.startswith('# error: ') and len(first) > len('# error: '), case
            want = first[len('# error: '):]
        plan.append(dict(case=case, mode='rt' if case == 'runtime.py' or Path(case).name.startswith('rtmode_') else 'ir',
                         expected_returncode=1 if rejected else 0, expected_diagnostic=want,
                         category='rejection' if rejected else 'program'))
    return plan


class ProcessRunner:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = set()
        self.cancelled = threading.Event()

    @staticmethod
    def kill(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            for process in self.active:
                self.kill(process)

    def run(self, argv, cwd, env, timeout):
        start = time.monotonic()
        row = dict(argv=list(map(str, argv)), outcome='cancelled' if self.cancelled.is_set() else 'completed',
                   returncode=None, stdout=b'', stderr=b'', elapsed_s=0.0, timeout_s=timeout)
        if self.cancelled.is_set():
            return row
        try:
            process = subprocess.Popen(row['argv'], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        except OSError as error:
            row.update(outcome='spawn_error', error=repr(error), elapsed_s=time.monotonic() - start)
            return row
        with self.lock:
            self.active.add(process)
            if self.cancelled.is_set():
                self.kill(process)
        try:
            try:
                row['stdout'], row['stderr'] = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.kill(process)
                row['stdout'], row['stderr'] = process.communicate()
                row.update(outcome='timeout', owned_process_group_terminated=True)
            except BaseException:
                self.kill(process)
                process.communicate()
                raise
            if self.cancelled.is_set():
                row.update(outcome='cancelled', owned_process_group_terminated=True)
            row.update(returncode=process.returncode, elapsed_s=time.monotonic() - start)
            return row
        finally:
            with self.lock:
                self.active.discard(process)


def retain(directory, name, row, output=None):
    stdout, stderr = row.pop('stdout'), row.pop('stderr')
    for suffix, data in [('stdout', stdout), ('stderr', stderr)]:
        path = directory / (name + '.' + suffix)
        path.write_bytes(data)
        row[suffix + '_sha256'] = sha(data)
        row[suffix + '_path'] = path.name
    data = output.read_bytes() if output is not None and output.is_file() else None
    row.update(ir_sha256=sha(data) if data is not None else None, ir_bytes=len(data) if data is not None else None)
    if data is not None:
        compressed = gzip.compress(data, compresslevel=6, mtime=0)
        target = directory / (name + '.ll.gz')
        tmp = target.with_suffix('.gz.tmp')
        tmp.write_bytes(compressed)
        tmp.replace(target)
        row.update(ir_gzip_path=target.name, ir_gzip_sha256=sha(compressed))
        output.unlink()
    return stdout, stderr, data


def validate(row, expected, stdout, stderr, data):
    errors = []
    if row['outcome'] != 'completed':
        errors.append(row['outcome'])
    if row['returncode'] != expected['expected_returncode']:
        errors.append('unexpected_returncode')
    if expected['expected_returncode'] == 0:
        if not data:
            errors.append('success_without_nonempty_ir')
        if stdout or stderr:
            errors.append('unexpected_success_diagnostics')
    else:
        want = expected['expected_diagnostic'].encode('utf-8', 'surrogateescape')
        if stdout or not re.fullmatch(rb'[^\r\n]*\.py:[0-9]+: error: [^\r\n]*\n', stderr) or want not in stderr:
            errors.append('unexpected_rejection_diagnostic')
        if data is not None:
            errors.append('rejection_produced_ir')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['main-repo', 'candidate-repo', 'output', 'main-bootstrap', 'candidate-bootstrap']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--expected-main-commit', required=True)
    parser.add_argument('--expected-candidate-commit', required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args()
    assert args.jobs > 0 and args.timeout > 0
    repo, out = args.candidate_repo.resolve(), args.output.resolve()
    homes = {'main': args.main_repo.resolve(), 'candidate': repo}
    assert len(set(homes.values())) == 2, 'independent source homes required'
    assert all(not out.is_relative_to(home) for home in homes.values()), 'keep generated evidence outside source checkouts'
    compilers = {name: home / 'pystachy' for name, home in homes.items()}
    proofs = {'main': args.main_bootstrap.resolve(), 'candidate': args.candidate_bootstrap.resolve()}
    logs = {name: path.parent / 'bootstrap.log' for name, path in proofs.items()}
    env = {k: v for k, v in os.environ.items() if not k.startswith('PYSTACHY_') and k not in ('PYTHONPATH', 'PYTHONHOME')}
    env.update(PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1', LC_ALL='C')
    if 'PYSTACHY_LLVM' in os.environ:
        env['PYSTACHY_LLVM'] = os.environ['PYSTACHY_LLVM']
    sources = {name: identity(home) for name, home in homes.items()}
    assert all(not source['status'] for source in sources.values()), ('sources must be clean', sources)
    assert sources['main']['commit'] == args.expected_main_commit
    assert sources['candidate']['commit'] == args.expected_candidate_commit
    subprocess.check_call(['git', 'merge-base', '--is-ancestor', args.expected_main_commit, args.expected_candidate_commit], cwd=repo)
    bootstraps = {name: json.loads(path.read_text()) for name, path in proofs.items()}
    descriptors = {name: validate_build(homes[name], sources[name], proof, logs[name]) for name, proof in bootstraps.items()}
    plan, baseline_plan = plan_cases(repo, env), plan_cases(homes['main'], env)
    current_cases, baseline_cases = {x['case'] for x in plan}, {x['case'] for x in baseline_plan}
    assert baseline_cases <= current_cases, ('baseline programs disappeared from candidate corpus', sorted(baseline_cases - current_cases))
    inputs = {name: snapshot(home) for name, home in homes.items()}
    membership = dict(added_cases=sorted(current_cases - baseline_cases), removed_cases=[],
                      changed_shared_cases=sorted(case for case in current_cases & baseline_cases
                                                 if inputs['main']['files'][case] != inputs['candidate']['files'][case]),
                      baseline_count=len(baseline_plan), candidate_count=len(plan))
    bindings = {str(p): digest(p) for p in [Path(__file__).resolve(), *proofs.values(), *logs.values()]}
    report = dict(schema=2, status='incomplete', purpose=__doc__, sources=sources, input_manifests=inputs,
                  manifest_exclusions=EXCLUSIONS, library_homes={name: str(home) for name, home in homes.items()},
                  source_input_home=str(repo), case_membership=membership,
                  bootstrap_snapshot_exclusions=dict(reason='The bootstrap producer excludes these three descriptors; each current byte is checked against the exact clean committed blob and frozen in both full input manifests.', files=descriptors),
                  evidence_bindings=bindings, plan=plan, expected=len(plan), records=[], baseline_exceptions=[],
                  environment={k: v for k, v in env.items() if k.startswith('PYSTACHY_') or k in
                               {'PATH', 'LD_LIBRARY_PATH', 'LIBRARY_PATH', 'CPATH', 'LC_ALL', 'PYTHONHASHSEED', 'PYTHONDONTWRITEBYTECODE'}},
                  started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='Both fresh native compilers read the same current candidate corpus, as make irsame does; each resolves standard library/runtime inputs through its own verified checkout. Exact frontend status and diagnostics are gated, allowing only a proven checkout prefix difference in a source location whose relative file, line, message and complete source hash match. Raw IR is intentionally allowed to change and is retained without normalization; this is not byte-identical IR or runtime-equivalence evidence. No parser-only, LLVM-validation, execution or elapsed-performance claim.',
                  compilers={name: dict(path=str(path), sha256=digest(path), commit=bootstraps[name]['commit'],
                                       tree=bootstraps[name]['tree'], fresh_local_build=True,
                                       bootstrap_path=str(proofs[name]), bootstrap_sha256=digest(proofs[name]),
                                       bootstrap_log_path=str(logs[name]), bootstrap_log_sha256=digest(logs[name]))
                             for name, path in compilers.items()})
    out.mkdir(exist_ok=False)
    for name, proof in bootstraps.items():
        save(out / (name + '-bootstrap.json'), proof)
    runner = ProcessRunner()

    def verify():
        assert {name: identity(home) for name, home in homes.items()} == sources, 'source identity drift'
        assert {name: snapshot(home) for name, home in homes.items()} == inputs, 'input membership or byte drift'
        assert plan_cases(repo, env) == plan and plan_cases(homes['main'], env) == baseline_plan, 'corpus membership drift'
        for path, expected in bindings.items():
            assert digest(path) == expected, path
        for name, proof in bootstraps.items():
            assert validate_build(homes[name], sources[name], proof, logs[name]) == descriptors[name], name

    def compare(item):
        index, expected = item
        directory = out / f'{index:04}'
        directory.mkdir()
        record = dict(index=index, **expected, results={}, validation_errors={}, status_equal=False,
                      diagnostics_equal=False, diagnostics_raw_equal=False,
                      diagnostic_normalization=None, ir_equal=False, import_path='')
        try:
            case = expected['case']
            case_env = dict(env, PYSTACHY_PATH='')
            if (repo / case).with_suffix('.path').is_file():
                prep = runner.run(['sh', 'tests/prepare_path.sh', case, str(directory)], repo, case_env, 30)
                stdout, stderr, _ = retain(directory, 'prepare-path', prep)
                record['path_preparation'] = prep
                assert prep['outcome'] == 'completed' and prep['returncode'] == 0 and not stderr, 'import path preparation failed'
                case_env['PYSTACHY_PATH'] = stdout.decode().strip()
            record['import_path'] = case_env['PYSTACHY_PATH']
            streams = {}
            for name, compiler in compilers.items():
                output = directory / (name + '.ll')
                compiler_env = dict(case_env, PYSTACHY_HOME=str(homes[name]))
                row = runner.run([compiler, expected['mode'], case, '-o', output], repo, compiler_env, args.timeout)
                row['library_home'] = compiler_env['PYSTACHY_HOME']
                stdout, stderr, data = retain(directory, name, row, output)
                streams[name] = (stdout, stderr)
                record['results'][name] = row
                record['validation_errors'][name] = validate(row, expected, stdout, stderr, data)
            a, b = record['results']['main'], record['results']['candidate']
            record['status_equal'] = a['outcome'] == b['outcome'] == 'completed' and a['returncode'] == b['returncode']
            record['diagnostics_raw_equal'], record['diagnostics_equal'], record['diagnostic_normalization'] = diagnostic_comparison(streams, homes, inputs)
            record['ir_equal'] = a['ir_sha256'] == b['ir_sha256']
        except BaseException as error:
            record['infrastructure_error'] = repr(error)
        save(directory / 'record.json', record)
        return record

    def interrupted(signum, frame):
        runner.cancel()
        raise InterruptedError('received signal ' + str(signum))

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    pool = None
    save(out / 'comparison.json', report)
    try:
        verify()
        pool = ThreadPoolExecutor(max_workers=args.jobs)
        futures = [pool.submit(compare, item) for item in enumerate(plan)]
        for future in as_completed(futures):
            report['records'].append(future.result())
            if len(report['records']) % 100 == 0:
                print('compared', len(report['records']), 'of', len(plan), flush=True)
                save(out / 'comparison.json', report)
        pool.shutdown(wait=True)
        pool = None
        verify()
        assert {row['index'] for row in report['records']} == set(range(len(plan))) and len(report['records']) == len(plan)
        report['status'] = 'complete'
    except BaseException as error:
        report.update(status='error', error=repr(error))
        runner.cancel()
    finally:
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)
        # Per-case atomic records survive interruption between global checkpoints.
        report['records'] = [json.loads(p.read_text()) for p in sorted(out.glob('[0-9]*/record.json'))]
        got = {row['index'] for row in report['records']}
        missing = [plan[i]['case'] for i in range(len(plan)) if i not in got]
        bad = [row['case'] for row in report['records'] if row.get('infrastructure_error') or
               set(row['results']) != set(compilers) or any(row['validation_errors'].values())]
        changed_status = [row['case'] for row in report['records'] if not row['status_equal']]
        changed_diagnostics = [row['case'] for row in report['records'] if not row['diagnostics_equal']]
        raw_diagnostic_changes = [row['case'] for row in report['records'] if not row['diagnostics_raw_equal']]
        normalized_diagnostics = [row['case'] for row in report['records'] if row['diagnostic_normalization'] is not None]
        changed_ir = [row['case'] for row in report['records'] if not row['ir_equal']]
        report['summary'] = dict(expected=len(plan), recorded=len(report['records']), missing_cases=missing,
                                expected_programs=sum(x['expected_returncode'] == 0 for x in plan),
                                expected_rejections=sum(x['expected_returncode'] == 1 for x in plan),
                                validation_failures=bad, status_changes=changed_status, diagnostic_changes=changed_diagnostics,
                                raw_diagnostic_changes=raw_diagnostic_changes, proven_checkout_path_normalizations=normalized_diagnostics,
                                changed_ir=len(changed_ir), changed_ir_cases=changed_ir)
        report['gate_passed'] = report['status'] == 'complete' and not (missing or bad or changed_status or changed_diagnostics)
        if report['status'] == 'complete' and not report['gate_passed']:
            report['status'] = 'failed'
        report['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save(out / 'comparison.json', report)
    print(json.dumps(report['summary'], indent=2), flush=True)
    return 0 if report['gate_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
