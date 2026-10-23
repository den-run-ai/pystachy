#!/usr/bin/env python3
"""Resume bounded, read-only historical Pystachy measurements from a manifest."""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import sys
import time

TOOLS = ('clang', 'opt', 'lli', 'llvm-link', 'llvm-as')
RSS = re.compile(r'WATCH_RSS_KIB (\d+) CPU_S ([\d.]+)')
BUILD_OVERRIDES = set(('CC CXX CFLAGS CPPFLAGS CXXFLAGS LDFLAGS MAKEFLAGS MFLAGS MAKEOVERRIDES '
                       'AR RANLIB LD OPT LLI CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH '
                       'LIBRARY_PATH COMPILER_PATH GCC_EXEC_PREFIX PKG_CONFIG_PATH PKG_CONFIG_LIBDIR '
                       'SDKROOT MACOSX_DEPLOYMENT_TARGET CMAKE_TOOLCHAIN_FILE LD_PRELOAD LD_AUDIT').split())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable_id(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def protocol_identity(manifest, runner_hash, meter_hash, environment):
    """Measurement configuration is separate from native build provenance."""
    return stable_id({'runner_sha256': runner_hash, 'rss_meter_source_sha256': meter_hash,
                      'measure_compile': manifest.get('measure_compile', False),
                      'samples': 5, 'confirmation_samples': 5,
                      'cache_policy': manifest.get('cache_policy', 'private-warm-v1'),
                      'environment': {k: environment[k] for k in
                                      ('PATH', 'LD_LIBRARY_PATH', 'PYSTACHY_LLVM', 'PYTHONHASHSEED',
                                       'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                                       'NUMEXPR_NUM_THREADS') if k in environment}})


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def safe_id(value):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
        raise ValueError('unsafe manifest identifier: ' + value)
    return value


def sanitized_environment(environ):
    removed = sorted(k for k in environ if k in BUILD_OVERRIDES or k.startswith(('CCACHE_', 'CLANG_CONFIG_')))
    env = {k: v for k, v in environ.items() if k not in removed and not k.startswith('PYSTACHY_')
           and k not in ('PYTHONHOME', 'PYTHONPATH')}
    return env, {'policy': 'strip-build-overrides-v1', 'removed_names': removed,
                 'effective_overrides': 'absent/default'}


def verify_finished_identity(root, identity):
    observed = {'sha': git(root, 'rev-parse', 'HEAD'),
                'status': git(root, 'status', '--porcelain'),
                'binary_sha256': digest(Path(root) / 'pystachy')}
    if observed['sha'] != identity['sha'] or observed['status'] or observed['binary_sha256'] != identity['binary_sha256']:
        raise ValueError('source/binary identity changed during measurement: ' + str(root))
    return observed


def active_work(proc=Path('/proc'), ignored=None):
    """Conservatively defer around older sessions that do not share our lock."""
    ignored = set(ignored or ())
    pid = os.getpid()
    while pid > 0 and pid not in ignored:
        ignored.add(pid)
        try:
            status = (proc / str(pid) / 'status').read_text()
            pid = int(re.search(r'^PPid:\s+(\d+)', status, re.M)[1])
        except (OSError, TypeError):
            break
    busy = []
    for path in proc.iterdir():
        if not path.name.isdigit() or int(path.name) in ignored:
            continue
        try:
            args = (path / 'cmdline').read_bytes().decode(errors='replace').strip('\0').split('\0')
            name = Path(args[0]).name
            tool = name == 'pystachy' or name in ('opt', 'lli', 'llvm-as', 'llvm-link') or name.startswith('clang')
            script = next((Path(a).name for a in args[1:] if a.endswith('.py')), '')
            timing = name.startswith('python') and re.search(r'bench|measure|watch|scaling', script, re.I)
            build = name in ('make', 'gmake') and (path / 'cwd' / 'src/pystachy_compiler').exists()
            if tool or timing or build:
                busy.append({'pid': int(path.name), 'command': args[:6]})
        except (OSError, IndexError):
            continue
    return busy


def parse_sample(sample, parser, timing_phases=None, smoke_prefix=None):
    """Validate checksum and timings, retaining independent process metrics."""
    if sample['returncode'] != 0:
        raise ValueError('process failed: ' + str(sample['returncode']))
    words = sample['stdout'].split()
    if parser == 'numeric':
        if len(words) != 3:
            raise ValueError('numeric output must contain checksum, elapsed_ns, CPU_ns')
        checksum = str(int(words[0]))
        names = timing_phases or ['loop_elapsed', 'loop_cpu']
        if len(names) != 2 or len(set(names)) != 2:
            raise ValueError('numeric timing_phases must name two distinct fields')
        times = {name + '_s': int(word) / 1e9 for name, word in zip(names, words[1:])}
    elif parser == 'smoke':
        matches = re.findall(r'^seconds\s+(\S+)\s*$', sample['stderr'], re.M)
        if smoke_prefix and len(words) == 2 and words[0] == smoke_prefix:
            words = words[1:]
        if len(words) != 1 or len(matches) != 1:
            raise ValueError('smoke output requires one checksum and one seconds line')
        checksum = str(int(words[0]))
        times = {'loop_elapsed_s': float(matches[0])}
    else:
        raise ValueError('unsupported parser: ' + parser)
    if any(not math.isfinite(v) or v < 0 for v in times.values()):
        raise ValueError('invalid timed-region duration')
    return dict(sample, checksum=checksum, **times)


def summarize(rows, left='base', right='head'):
    result = {}
    for mode in ('jit', 'aot', 'build'):
        if mode not in rows[0][left] or mode not in rows[0][right]:
            continue
        keys = set(rows[0][left][mode]) & set(rows[0][right][mode])
        for metric in sorted(k for k in keys if k.endswith('_s') or k == 'rss_kib'):
            a = [r[left][mode][metric] for r in rows]
            b = [r[right][mode][metric] for r in rows]
            am, bm = statistics.median(a), statistics.median(b)
            result[mode + '.' + metric] = {
                'base': am, 'head': bm, 'ratio': bm / am if am else None,
                'percent': 100 * (bm / am - 1) if am else None,
                'base_samples': a, 'head_samples': b,
                'base_range': [min(a), max(a)], 'head_range': [min(b), max(b)]}
    return result


def crossing(summary):
    return any(v['ratio'] is not None and v['ratio'] >= 1.20 for v in summary.values())


def pair_rows(record, evidence):
    """Normalized paired observations; no cross-run median splicing."""
    if record['status'] != 'complete':
        return []
    output = []
    for left in ('base', 'anchor'):
        if left not in record['revisions']:
            continue
        comparison_id = record['comparison_id'] + ('--anchor' if left == 'anchor' else '')
        for batch, rows in (('initial', record['pairs']), ('confirmation', record.get('confirmation', []))):
            for row in rows:
                for mode in ('jit', 'aot', 'build'):
                    if mode not in row[left] or mode not in row['head']:
                        continue
                    a, b = row[left][mode], row['head'][mode]
                    for key in sorted(a.keys() & b.keys()):
                        if not (key.endswith('_s') or key == 'rss_kib'):
                            continue
                        if a[key] <= 0 or b[key] <= 0:
                            continue
                        phase = 'aot_compile' if mode == 'build' else 'whole_process' if key in ('wall_s', 'cpu_s', 'rss_kib') else key[:-2].replace('_elapsed', '').replace('_cpu', '')
                        metric = 'peak_rss' if key == 'rss_kib' else 'cpu_time' if key == 'cpu_s' or 'cpu' in key or key in ('construction_s', 'processing_s') else 'elapsed_time'
                        item = {'schema': 1, 'comparison_id': comparison_id,
                                'environment_id': record.get('measurement_environment_id', record['cohort_id']),
                                'workload_sha256': record.get('workload_sha256', record['source_sha256']),
                                'base_sha': record['revisions'][left]['sha'], 'head_sha': record['revisions']['head']['sha'],
                                'workload': record['workload_id'], 'mode': mode, 'phase': phase, 'metric': metric,
                                'unit': 'KiB' if key == 'rss_kib' else 's', 'direction': 'lower', 'batch': batch,
                                'pair': row['round'], 'base': a[key], 'head': b[key], 'correct': True,
                                'evidence': str(evidence), 'note': 'Arguments ' + repr(record['arguments']) + '; lineages ' + repr(record['lineages'])}
                        if mode == 'aot':
                            item.update(base_binary_sha256=record['setup'][left]['binary_sha256'],
                                        head_binary_sha256=record['setup']['head']['binary_sha256'])
                        output.append(item)
    return output


def workload_key(campaign, comparison, workload):
    spec = campaign.m['workloads'][workload]
    return stable_id({'comparison': {k: v for k, v in comparison.items() if k != 'workloads'},
                      'workload': workload, 'spec': spec,
                      'source': digest(campaign.root / spec['source']),
                      'revision_specs': {sha: campaign.m['revisions'][sha] for sha in
                                         {comparison[s] for s in ('base', 'head', 'anchor') if comparison.get(s)}},
                      'cohort_id': campaign.cohort_id, 'protocol_id': campaign.protocol_id})


def regenerate_pairs(output, state):
    target = Path(output) / 'pairs.jsonl'
    tmp = target.with_suffix('.tmp')
    with tmp.open('w') as stream:
        for item in state['completed_workloads'].values():
            path = Path(item['raw'])
            record = json.loads(path.read_text())
            if record['status'] != 'complete':
                raise ValueError('completed state refers to invalid raw record')
            for row in pair_rows(record, path):
                stream.write(json.dumps(row) + '\n')
    tmp.replace(target)


class Deferred(Exception):
    pass


class Campaign:
    def __init__(self, manifest, max_new_builds):
        self.manifest_path = Path(manifest).resolve()
        self.root = self.manifest_path.parent
        self.m = json.loads(self.manifest_path.read_text())
        self.output = Path(self.m.get('output_dir', self.root / 'results'))
        self.output.mkdir(parents=True, exist_ok=True)
        self.repo = Path(self.m['repository'])
        self.python = self.m['python']
        self.build_limit, self.new_builds = max_new_builds, 0
        self.events = []
        self.builds = {}
        self.failed_builds = set()
        self.run_id = time.strftime('%Y%m%dT%H%M%S', time.gmtime()) + '-' + str(os.getpid())
        self.env, self.environment_policy = sanitized_environment(os.environ)
        self.env.update(PYSTACHY_LLVM=self.m['llvm'], LD_LIBRARY_PATH=self.m['library_path'],
                        PYTHONHASHSEED='0', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                        MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1',
                        PATH=str(Path(self.python).parent) + ':/usr/local/bin:/usr/bin:/bin')
        self.expected_python = self.m.get('python_version', '3.13.16')
        version = subprocess.check_output([self.python, '-c', 'import platform; print(platform.python_version())'],
                                          env=self.env, text=True).strip()
        if version != self.expected_python:
            raise ValueError('CPython version mismatch: ' + version)
        self.toolchain = {}
        for name in TOOLS:
            path = Path(self.m['llvm']) / name
            checksum = digest(path)
            expected = self.m.get('toolchain', {}).get(name, {})
            expected_hash = expected.get('sha256') if isinstance(expected, dict) else expected
            if expected_hash and checksum != expected_hash:
                raise ValueError('LLVM hash mismatch: ' + name)
            version_text = subprocess.check_output([str(path), '--version'], env=self.env, text=True)
            if not re.search(r'\bversion\s+' + re.escape(self.m.get('llvm_version', '18.1.3')) + r'\b', version_text):
                raise ValueError('LLVM version mismatch: ' + name)
            self.toolchain[name] = {'sha256': checksum, 'version': version_text}
        self.cohort = {'python': version, 'python_sha256': digest(self.python),
                       'toolchain': self.toolchain, 'cpu': self.m.get('cpu', 0),
                       'thread_settings': {k: self.env[k] for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                                                                  'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')},
                       'host': os.uname()._asdict() if hasattr(os.uname(), '_asdict') else list(os.uname()),
                       'cpuinfo': Path('/proc/cpuinfo').read_text().split('model name', 1)[-1].splitlines()[0]}
        # Preserve existing default-environment build identities; a newly removed
        # override invalidates legacy caches whose provenance did not record it.
        if self.environment_policy['removed_names']:
            self.cohort['removed_build_overrides'] = self.environment_policy['removed_names']
        self.cohort_id = stable_id(self.cohort)
        self.meter = self.root / 'rss_meter'
        meter_source = self.root / 'rss_meter.c'
        if self.m.get('samples', 5) != 5 or self.m.get('confirmation_samples', 5) != 5:
            raise ValueError('this runner requires five initial and five confirmation samples')
        self.protocol_id = protocol_identity(self.m, digest(__file__), digest(meter_source), self.env)
        meter_stamp = self.root / 'rss_meter.json'
        expected_stamp = {'source': digest(meter_source), 'compiler': 'cc'}
        previous = json.loads(meter_stamp.read_text()) if meter_stamp.exists() else {}
        if not self.meter.exists() or previous.get('source') != expected_stamp['source'] or previous.get('binary') != digest(self.meter):
            if active_work():
                raise Deferred('foreign work started before RSS meter compilation')
            subprocess.run(['cc', '-O2', str(meter_source), '-o', str(self.meter)], check=True, env=self.env)
            write_json(meter_stamp, dict(expected_stamp, binary=digest(self.meter)))

    def run(self, command, env, cwd, timeout=None):
        busy = active_work()
        if busy:
            raise Deferred('foreign build/timing process started: ' + json.dumps(busy))
        start, load = time.perf_counter(), os.getloadavg()
        p = subprocess.Popen([str(self.meter), *map(str, command)], cwd=cwd, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             start_new_session=True)
        timed_out = False
        try:
            stdout, stderr = p.communicate(timeout=timeout or self.m.get('process_timeout', 180))
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(p.pid, signal.SIGKILL)
            stdout, stderr = p.communicate()
        row = {'command': list(map(str, command)), 'cwd': str(cwd), 'wall_s': time.perf_counter() - start,
               'load': load, 'returncode': p.returncode, 'stdout': stdout, 'stderr': stderr,
               'timed_out': timed_out}
        match = RSS.search(stderr)
        if match:
            row.update(rss_kib=int(match[1]), cpu_s=float(match[2]))
        self.events.append(row)
        if not match and not timed_out:
            raise ValueError('RSS meter failed')
        return row

    def revision(self, sha):
        if sha in self.failed_builds:
            raise ValueError('native build already failed in this batch: ' + sha)
        if sha in self.builds:
            return self.builds[sha]
        if not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise ValueError('revision must be a full SHA')
        spec = self.m['revisions'][sha]
        cache = self.output / 'builds' / (sha + '.json')
        prior = json.loads(cache.read_text()) if cache.exists() else {}
        root = Path(spec['path']) if spec.get('verified_existing') else self.root / 'worktrees' / sha
        native = root / 'pystachy'
        def validate_source():
            if git(root, 'rev-parse', 'HEAD') != sha or git(root, 'status', '--porcelain'):
                raise ValueError('source identity or cleanliness mismatch: ' + sha)
            pin = (root / '.python-version').read_text().strip()
            if pin != self.expected_python:
                raise ValueError('historical CPython pin requires a separate cohort: ' + pin)
        if prior.get('cohort_id') == self.cohort_id and root.exists() and native.exists():
            validate_source()
            if prior.get('binary_sha256') != digest(native):
                raise ValueError('cached binary changed: ' + sha)
        elif spec.get('verified_existing'):
            validate_source()
            if not all(n in self.m.get('toolchain', {}) for n in TOOLS):
                raise ValueError('existing binary requires recorded complete toolchain hashes')
            if spec.get('binary_sha256') != digest(native):
                raise ValueError('existing binary mismatch: ' + sha)
            prior = {'sha': sha, 'tree': git(root, 'rev-parse', 'HEAD^{tree}'),
                     'binary_sha256': digest(native), 'cohort_id': self.cohort_id,
                     'provenance': spec.get('provenance', 'manifest validated existing build')}
        else:
            if self.new_builds >= self.build_limit:
                raise Deferred('new-build budget reached')
            try:
                git(self.repo, 'cat-file', '-e', sha + '^{commit}')
            except subprocess.CalledProcessError:
                git(self.repo, 'fetch', '--no-tags', 'origin', sha)
            if not root.exists():
                root.parent.mkdir(parents=True, exist_ok=True)
                git(self.repo, 'worktree', 'add', '--detach', str(root), sha)
            validate_source()
            self.new_builds += 1
            e = dict(self.env, PYSTACHY_HOME=str(root), PYSTACHY_CACHE=str(self.root / 'cache' / sha))
            row = self.run(['make', 'PY=' + self.python], e, root, self.m.get('build_timeout', 900))
            write_json(self.output / 'builds' / (sha + '-attempt.json'), row)
            if row['returncode']:
                self.failed_builds.add(sha)
                raise ValueError('native build failed: ' + sha)
            validate_source()
            prior = {'sha': sha, 'tree': git(root, 'rev-parse', 'HEAD^{tree}'),
                     'binary_sha256': digest(native), 'cohort_id': self.cohort_id,
                     'build': row, 'note': 'single build is not paired bootstrap speed evidence'}
        write_json(cache, prior)
        e = dict(self.env, PYSTACHY_HOME=str(root), PYSTACHY_CACHE=str(self.root / 'cache' / sha))
        value = {'root': root, 'env': e, 'identity': prior}
        self.builds[sha] = value
        return value

    def measure(self, comparison, workload_id):
        spec = self.m['workloads'][workload_id]
        source = (self.root / spec['source']).resolve()
        if not source.is_relative_to(self.root):
            raise ValueError('workload source must be inside campaign')
        source_hash = digest(source)
        if spec.get('source_sha256', spec.get('sha256', source_hash)) != source_hash:
            raise ValueError('workload source hash mismatch')
        if spec.get('required_policy') == 'dynamic-any' and '# pystachy: dynamic-any' not in source.read_text():
            raise ValueError('dynamic-any workload lacks explicit opt-in')
        sides = {side: comparison[side] for side in ('base', 'head', 'anchor') if comparison.get(side)}
        if sides.get('anchor') == sides['base']:
            del sides['anchor']
        roots = {side: self.revision(sha) for side, sha in sides.items()}
        target = self.output / 'executables' / safe_id(comparison['id'])
        target.mkdir(parents=True, exist_ok=True)
        record = {'comparison_id': comparison['id'], 'workload_id': workload_id,
                  'started': time.strftime('%FT%TZ', time.gmtime()), 'cohort': self.cohort,
                  'cohort_id': self.cohort_id, 'source_sha256': source_hash, 'arguments': spec['args'],
                  'environment_policy': self.environment_policy,
                  'protocol_id': self.protocol_id,
                  'measurement_environment_id': stable_id({'cohort': self.cohort_id, 'run': self.run_id,
                                                          'protocol': self.protocol_id}),
                  'workload_sha256': stable_id({'source': source_hash, 'args': spec['args'],
                                               'parser': spec['parser'], 'timing_phases': spec.get('timing_phases'),
                                               'policy': spec.get('required_policy')}),
                  'base_is_anchor': comparison.get('anchor') == comparison['base'],
                  'parser': spec['parser'], 'revisions': {s: r['identity'] for s, r in roots.items()},
                  'lineages': {s: self.m['revisions'][sha].get('lineage', 'unknown') for s, sha in sides.items()},
                  'notes': ['RSS is process peak, not managed heap or allocation totals',
                            'JIT process timing includes compilation, startup, execution; cache warm',
                            'Setup build is diagnostic; only paired build samples support compile-time comparison'], 'setup': {}}
        raw_path = self.output / 'raw' / (safe_id(comparison['id']) + '--' + safe_id(workload_id) + '--' + self.run_id + '.json')
        self.events = []
        try:
            def sample(command, env, cwd):
                value = parse_sample(self.run(command, env, cwd), spec['parser'], spec.get('timing_phases'), spec['args'][0] if spec['args'] else None)
                if value['checksum'] != expected:
                    raise ValueError('checksum mismatch')
                return value
            oracle = parse_sample(self.run([self.python, source, *spec['args']], self.env, self.root), spec['parser'], spec.get('timing_phases'), spec['args'][0] if spec['args'] else None)
            expected = oracle['checksum']
            record['oracle'] = oracle
            exes = {}
            for side, r in roots.items():
                exe = target / (workload_id + '-' + side)
                exes[side] = exe
                build = self.run([r['root'] / 'pystachy', 'build', source, '-o', exe], r['env'], r['root'])
                if build['returncode']:
                    raise ValueError('workload compilation failed: ' + side)
                build['binary_sha256'] = digest(exe)
                record['setup'][side] = build
                sample([exe, *spec['args']], r['env'], r['root'])
                sample([r['root'] / 'pystachy', 'run', source, *spec['args']], r['env'], r['root'])
            def batch(offset):
                rows = []
                for i in range(5):
                    order = list(roots) if (i + offset) % 2 == 0 else list(reversed(roots))
                    row = {'round': offset + i, 'order': order,
                           'cpython': sample([self.python, source, *spec['args']], self.env, self.root)}
                    for side in order:
                        r = roots[side]
                        row[side] = {'jit': sample([r['root'] / 'pystachy', 'run', source, *spec['args']], r['env'], r['root']),
                                     'aot': sample([exes[side], *spec['args']], r['env'], r['root'])}
                        if self.m.get('measure_compile', False):
                            build = self.run([r['root'] / 'pystachy', 'build', source, '-o', exes[side]], r['env'], r['root'])
                            if build['returncode']:
                                raise ValueError('paired AOT build failed: ' + side)
                            build['binary_sha256'] = digest(exes[side])
                            if build['binary_sha256'] != record['setup'][side]['binary_sha256']:
                                raise ValueError('AOT binary identity changed between repeats: ' + side)
                            sample([exes[side], *spec['args']], r['env'], r['root'])
                            row[side]['build'] = build
                    rows.append(row)
                    record['events'] = self.events
                    record['partial_batch'] = rows
                    write_json(raw_path, record)
                return rows
            record['pairs'] = batch(0)
            record['summary'] = summarize(record['pairs'])
            if 'anchor' in roots:
                record['anchor_summary'] = summarize(record['pairs'], 'anchor')
            if crossing(record['summary']) or crossing(record.get('anchor_summary', {})):
                record['confirmation'] = batch(5)
                record['confirmation_summary'] = summarize(record['confirmation'])
                if 'anchor' in roots:
                    record['anchor_confirmation_summary'] = summarize(record['confirmation'], 'anchor')
            if digest(source) != source_hash:
                raise ValueError('workload source changed during measurement')
            record['completion_identity_validation'] = {
                'checked': time.strftime('%FT%TZ', time.gmtime()), 'source_sha256': digest(source),
                'revisions': {side: verify_finished_identity(r['root'], r['identity'])
                              for side, r in roots.items()}}
            record['status'] = 'complete'
        except Deferred as error:
            record.update(status='deferred', error=str(error))
        except Exception as error:
            record.update(status='blocked', error=str(error))
        record.pop('partial_batch', None)
        record.update(events=self.events, finished=time.strftime('%FT%TZ', time.gmtime()))
        write_json(raw_path, record)
        return record, raw_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('--max-comparisons', type=int, default=1)
    parser.add_argument('--max-new-builds', type=int, default=2)
    parser.add_argument('--retry-blocked', action='store_true', help='retry unchanged blocked workloads once')
    args = parser.parse_args()
    if args.max_comparisons < 1 or args.max_new_builds < 0:
        parser.error('invalid work budget')
    manifest = Path(args.manifest).resolve()
    m = json.loads(manifest.read_text())
    lock_path = Path(m.get('lock_path', manifest.parent / 'performance.lock'))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Deferred: another owned performance batch holds the lock')
            return 0
        busy = active_work()
        write_json(Path(m.get('output_dir', manifest.parent / 'results')) / 'preflight.json',
                   {'checked': time.strftime('%FT%TZ', time.gmtime()), 'foreign_work': busy,
                    'status': 'deferred' if busy else 'idle'})
        if busy:
            print('Deferred: foreign build/timing processes active:', json.dumps(busy), flush=True)
            return 0
        os.sched_setaffinity(0, {m.get('cpu', 0)})
        try:
            campaign = Campaign(manifest, args.max_new_builds)
        except Deferred as error:
            print('Deferred:', error, flush=True)
            return 0
        state_path = campaign.output / 'state.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        for field in ('completed_workloads', 'blocked_workloads', 'deferred_workloads'):
            state.setdefault(field, {})
        completed = 0
        for comparison in m['comparisons']:
            attempted = False
            for workload in comparison['workloads']:
                key = workload_key(campaign, comparison, workload)
                if key in state['completed_workloads']:
                    continue
                if key in state['blocked_workloads'] and not args.retry_blocked:
                    continue
                attempted = True
                try:
                    record, raw_path = campaign.measure(comparison, workload)
                    status = 'completed' if record['status'] == 'complete' else record['status']
                    entry = {'id': comparison['id'], 'workload': workload, 'raw': str(raw_path)}
                except Deferred as error:
                    status, entry = 'deferred', {'id': comparison['id'], 'workload': workload, 'error': str(error)}
                except Exception as error:
                    status, entry = 'blocked', {'id': comparison['id'], 'workload': workload,
                                               'error': str(error), 'events': campaign.events}
                for field in ('completed_workloads', 'blocked_workloads', 'deferred_workloads'):
                    state[field].pop(key, None)
                state[status + '_workloads'][key] = entry
                write_json(state_path, state)
                regenerate_pairs(campaign.output, state)
                print(comparison['id'], workload, status, flush=True)
                if status == 'deferred':
                    return 0
            if attempted:
                completed += 1
            if completed >= args.max_comparisons:
                break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
