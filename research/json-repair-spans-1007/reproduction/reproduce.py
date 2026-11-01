#!/usr/bin/env python3
"""Prepare isolated pinned sources and native binaries; timing requires --run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile


REMOTE = 'https://github.com/den-run-ai/pystachy.git'
MAIN = '07b26e02425d023288ed95a9d2a5077be5aeb45e'
INTEGER_FIX = 'dceda23e8b71311c43e5c843698ed4443292004b'
BYTE_SCAN = 'd056aafe2f0c09d72ca23bf14b18123d1e439170'
SPANS = '946bb203c1835af708b5779c388b85482cf7514b'
BASE_TREE = '276e01519733a14303e9d7d29bed2b44df92e37a'
PARSER = 'ports/json_repair/parse_string.py'
PROBE = 'bench/extended/json_repair_spans.py'
BASE_PARSER_SHA256 = 'caf4b7fff811df8e5e53a67720d231d1a4e2c1afa8d907be8e50c859341551df'
SPAN_PARSER_SHA256 = '9193bc763e38bfeee444ea8778c203372c72174502ec480bc0ef83be7a02b4c5'
PROBE_SHA256 = 'b89da4a79796a6ef780bb7a59babcad41284dad499d613b789d9326394b99e8d'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, help='new directory; otherwise allocate a retained temporary directory')
    parser.add_argument('--repo', default=REMOTE, help='public repository URL or an existing local mirror')
    parser.add_argument('--llvm', type=Path, default=Path(os.environ.get('PYSTACHY_LLVM', '/usr/lib/llvm-18/bin')))
    parser.add_argument('--cpu', type=int, default=int(os.environ.get('PYSTACHY_SPAN_CPU', '0')))
    parser.add_argument('--prepare-only', action='store_true', help='fetch/merge/patch without building or timing')
    parser.add_argument('--run', action='store_true', help='execute the 208-process paired campaign after builds')
    args = parser.parse_args()
    require(not (args.prepare_only and args.run), '--prepare-only and --run are mutually exclusive')
    require(sys.version_info[:3] == (3, 13, 16), 'Run with pinned CPython 3.13.16')
    require(platform.system() == 'Linux', 'This reproduction recipe requires Linux (/proc, taskset and wait4)')
    for program in ('git', 'make', 'taskset'):
        require(shutil.which(program) is not None, f'Missing prerequisite: {program}')
    require(Path('/usr/bin/taskset').is_file(), 'Runner requires /usr/bin/taskset')
    llvm = args.llvm.expanduser().resolve()
    for tool in ('clang', 'lli', 'opt', 'llvm-link', 'llc'):
        require((llvm / tool).is_file(), f'Missing LLVM tool: {llvm / tool}')
        version = subprocess.check_output([str(llvm / tool), '--version'], text=True)
        require('version 18.' in version, f'{tool} must be from LLVM 18: {version.splitlines()[0]}')
    require(args.cpu in os.sched_getaffinity(0),
            f'CPU {args.cpu} unavailable; choose --cpu explicitly from {sorted(os.sched_getaffinity(0))}')
    bundle = Path(__file__).resolve().parent
    runner_source = bundle / 'run_benchmarks.py'
    require(runner_source.is_file(), f'Missing sibling portable runner: {runner_source}')

    if args.dest is None:
        root = Path(tempfile.mkdtemp(prefix='pystachy-spans-repro-')).resolve()
    else:
        root = args.dest.expanduser().resolve()
        require(not root.exists(), f'Refusing to reuse or overwrite destination: {root}')
        root.mkdir(parents=True)
    evidence = root / 'span-evidence'
    evidence.mkdir()
    logs = evidence / 'reproduction-logs'
    logs.mkdir()
    temporary = root / 'tmp'
    temporary.mkdir()
    print(f'Reproduction root: {root}', flush=True)
    records = []
    neutral_env = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
        'TMPDIR': str(temporary), 'PYTHONDONTWRITEBYTECODE': '1',
    }
    # Preserve installed Git configuration, hooks and signing policy. Remove only
    # repository-routing variables that could redirect this isolated workflow.
    git_env = dict(os.environ)
    git_env.update(neutral_env)
    for variable in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR',
                     'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE'):
        git_env.pop(variable, None)
    git_options = [
        'git', '-c', 'core.autocrlf=false',
        '-c', 'user.name=Pystachy local reproduction', '-c', 'user.email=reproduction@invalid',
    ]

    def run(command, *, cwd=root, env=None, name='command'):
        index = len(records) + 1
        log = logs / f'{index:03d}-{name}.log'
        print(f'[{index}] {shlex.join([str(v) for v in command])}', flush=True)
        started = datetime.now(timezone.utc).isoformat()
        child_env = env if env is not None else git_env if command[0] == 'git' else neutral_env
        result = subprocess.run(command, cwd=cwd, env=child_env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.write_bytes(result.stdout)
        records.append({'argv': [str(v) for v in command], 'cwd': str(cwd),
                        'started_at': started, 'returncode': result.returncode, 'log': str(log)})
        (evidence / 'reproduction-commands.json').write_text(json.dumps(records, indent=2) + '\n')
        require(result.returncode == 0, f'Command failed with exit {result.returncode}; see {log}')
        return result.stdout

    def git(directory, *arguments, name='git'):
        return run([*git_options, '-C', str(directory), *arguments], name=name)

    # Fetch only the histories reachable from the four exact commits, not research branches.
    store = root / 'source-store.git'
    run([*git_options, 'init', '--bare', str(store)], name='init-store')
    git(store, 'remote', 'add', 'origin', args.repo)
    git(store, 'fetch', '--no-tags', 'origin', MAIN, INTEGER_FIX, BYTE_SCAN, SPANS, name='fetch-pins')
    for revision in (MAIN, INTEGER_FIX, BYTE_SCAN, SPANS):
        actual = git(store, 'rev-parse', f'{revision}^{{commit}}').decode().strip()
        require(actual == revision, f'Commit identity mismatch: {revision}')
    git(store, 'update-ref', 'refs/heads/reproduction-main', MAIN)
    git(store, 'symbolic-ref', 'HEAD', 'refs/heads/reproduction-main')

    base = root / 'pystachy-combined-base'
    candidate = root / 'pystachy-combined-candidate'
    probe_source = root / 'pystachy-spans'
    for directory, revision in ((base, INTEGER_FIX), (probe_source, SPANS)):
        run([*git_options, 'clone', '--no-checkout', '--no-hardlinks', str(store), str(directory)], name='clone')
        git(directory, 'checkout', '--detach', revision)
    git(base, 'merge', '--no-ff', '--no-edit', BYTE_SCAN, name='merge-1003-1004')
    base_commit = git(base, 'rev-parse', 'HEAD').decode().strip()
    base_tree = git(base, 'rev-parse', 'HEAD^{tree}').decode().strip()
    require(base_tree == BASE_TREE, f'Combined baseline tree changed: {base_tree} != {BASE_TREE}')
    require(sha256(base / PARSER) == BASE_PARSER_SHA256, 'Baseline parser hash mismatch')
    run([*git_options, 'clone', '--no-checkout', '--no-hardlinks', str(base), str(candidate)], name='clone-candidate')
    git(candidate, 'checkout', '--detach', base_commit)

    # Apply only the reviewed file delta. Never copy the complete older parser package.
    patch = git(store, 'diff', '--binary', MAIN, SPANS, '--', PARSER, name='extract-span-patch')
    patch_path = evidence / 'ordinary-spans.patch'
    patch_path.write_bytes(patch)
    require(bool(patch), 'Expected a nonempty span patch')
    git(candidate, 'apply', '--check', str(patch_path), name='check-span-patch')
    git(candidate, 'apply', '--index', str(patch_path), name='apply-span-patch')
    changed = git(candidate, 'diff', '--cached', '--name-only', 'HEAD').decode().splitlines()
    require(changed == [PARSER], f'Unexpected candidate changes: {changed}')
    require(sha256(candidate / PARSER) == SPAN_PARSER_SHA256, 'Candidate parser hash mismatch')
    require(sha256(probe_source / PROBE) == PROBE_SHA256, 'PR #1007 benchmark probe hash mismatch')
    # #1003's depth guard is in JSONParser; the whole-file delta check also preserves it.
    require((candidate / 'ports/json_repair/json_parser.py').read_bytes()
            == (base / 'ports/json_repair/json_parser.py').read_bytes(), 'JSONParser recursion wrapper changed')
    candidate_tree = git(candidate, 'write-tree').decode().strip()
    git(candidate, 'commit', '-m', 'Apply pinned ordinary-span parser delta for local reproduction', name='commit-local-delta')
    require(git(candidate, 'rev-parse', 'HEAD^{tree}').decode().strip() == candidate_tree,
            'Candidate commit tree mismatch')
    base_commit = git(base, 'rev-parse', 'HEAD').decode().strip()
    candidate_commit = git(candidate, 'rev-parse', 'HEAD').decode().strip()
    changed = git(candidate, 'diff', '--name-only', base_commit, candidate_commit).decode().splitlines()
    require(changed == [PARSER], f'Unexpected baseline/candidate tree delta: {changed}')

    runner = evidence / 'run_benchmarks.py'
    shutil.copyfile(runner_source, runner)
    exports = {
        'PYSTACHY_SPAN_ROOT': str(root), 'PYSTACHY_LLVM': str(llvm),
        'PYSTACHY_SPAN_CPU': str(args.cpu), 'PYSTACHY_SPAN_PYTHON': sys.executable,
    }
    (evidence / 'reproduction-env.sh').write_text(''.join(
        f'export {key}={shlex.quote(value)}\n' for key, value in exports.items()))
    metadata = {
        'prepared_at': datetime.now(timezone.utc).isoformat(), 'root': str(root),
        'pins': {'main': MAIN, 'integer_fix_1003': INTEGER_FIX, 'byte_scan_1004': BYTE_SCAN, 'spans_1007': SPANS},
        'baseline': {'local_commit': base_commit, 'tree': base_tree, 'parser_sha256': sha256(base / PARSER)},
        'candidate': {'local_commit': candidate_commit, 'tree': candidate_tree,
                      'parser_sha256': sha256(candidate / PARSER), 'changed_paths': changed},
        'probe_sha256': sha256(probe_source / PROBE), 'patch_sha256': sha256(patch_path),
        'runner_sha256': sha256(runner), 'python': sys.version, 'llvm_directory': str(llvm),
        'cpu': args.cpu, 'allowed_cpus': sorted(os.sched_getaffinity(0)), 'built': False,
    }
    metadata_path = evidence / 'reproduction-metadata.json'
    metadata_path.write_text(json.dumps(metadata, indent=2) + '\n')
    if args.prepare_only:
        print(f'Sources prepared and checked; no builds or timing executed. See {metadata_path}')
        return

    binaries = {}
    for variant, directory in (('base', base), ('candidate', candidate)):
        cache = evidence / f'build-cache-{variant}'
        cache.mkdir()
        env = dict(neutral_env, PYSTACHY_HOME=str(directory), PYSTACHY_PATH=str(directory / 'ports'),
                   PYSTACHY_LLVM=str(llvm), PYSTACHY_CACHE=str(cache))
        # Each fresh checkout proves compiler AND runtime three-stage fixed points.
        run(['make', f'PY={sys.executable}'], cwd=directory, env=env, name=f'bootstrap-{variant}')
        binary = evidence / ('bench-base' if variant == 'base' else 'bench-candidate-fast')
        run([str(directory / 'pystachy'), 'build', str(probe_source / PROBE), '-o', str(binary)],
            cwd=directory, env=env, name=f'build-probe-{variant}')
        binaries[variant] = {'compiler_sha256': sha256(directory / 'pystachy'),
                             'aot_sha256': sha256(binary), 'aot_path': str(binary)}
    metadata.update(built=True, binaries=binaries)
    metadata_path.write_text(json.dumps(metadata, indent=2) + '\n')
    bench_env = dict(neutral_env, **exports)
    if args.run:
        # This is the only path that executes timed programs. The runner has per-process watchdogs.
        run([sys.executable, str(runner), '--run'], env=bench_env, name='paired-campaign')
    else:
        plan = run([sys.executable, str(runner)], env=bench_env, name='campaign-plan')
        (evidence / 'campaign-plan.json').write_bytes(plan)
        print('Sources and AOT binaries prepared. Timed campaign not started.')
        print(f'Next: source {shlex.quote(str(evidence / "reproduction-env.sh"))}')
        print(f'Then: "$PYSTACHY_SPAN_PYTHON" {shlex.quote(str(runner))} --run')


if __name__ == '__main__':
    main()
