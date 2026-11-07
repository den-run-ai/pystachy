"""Record a fresh ordinary make bootstrap and its six witnesses; no source edits."""
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
PYTHON = Path('/workspace/scratch/e98dc1e3e6cd/dev/bin/python').resolve()
LLVM = Path('/workspace/scratch/e98dc1e3e6cd/toolchains/ubuntu-18.1.3-1ubuntu1-amd64/bin')
OUT.mkdir(parents=True, exist_ok=False)
os.sched_setaffinity(0, {0, 1, 2, 3})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    files = [ROOT / name for name in ('Makefile', 'pystachy.py', 'runtime.py', 'runtime.c')]
    for directory in ('src', 'lib', 'ryu', 'mpz'):
        files.extend(p for p in (ROOT / directory).rglob('*') if p.is_file() and p.suffix in ('.py', '.c', '.h'))
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(files))}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


env = {k: v for k, v in os.environ.items() if not k.startswith('PYSTACHY_')}
env.update(PATH='/workspace/scratch/e98dc1e3e6cd/dev/bin:' + env.get('PATH', ''),
           PYSTACHY_HOME=str(ROOT), PYSTACHY_CACHE=str(OUT / 'cache'), PYSTACHY_LLVM=str(LLVM),
           PYSTACHY_JOBS='2', PYSTACHY_BUILD_JOBS='1', PYTHONHASHSEED='0')
command = ['make', '-B', 'pystachy', 'PY=/workspace/scratch/e98dc1e3e6cd/dev/bin/python']
tools = {'python': PYTHON, **{name: LLVM / name for name in ('clang', 'llvm-as', 'llvm-link', 'opt')}}
report = dict(complete=False, root=str(ROOT), commit=git('rev-parse', 'HEAD'),
              git_status=git('status', '--porcelain=v1', '--untracked-files=all').splitlines(),
              sources=sources(), command=command, environment={k: v for k, v in env.items()
              if k.startswith('PYSTACHY_') or k in ('PATH', 'PYTHONHASHSEED')},
              tools={name: {'path': str(path), 'sha256': sha(path),
              'version': subprocess.check_output([str(path), '--version'], text=True).strip()}
              for name, path in tools.items()}, platform=platform.platform(),
              affinity=sorted(os.sched_getaffinity(0)), load_before=list(os.getloadavg()),
              measurement_scope='Fresh ordinary make bootstrap; validation timing only')
(OUT / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
started = time.monotonic()
child = None
try:
    with (OUT / 'build.log').open('wb') as log:
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        print(f'bootstrap started: {ROOT}, pid {child.pid}', flush=True)
        report['returncode'] = child.wait(timeout=1200)
    if report['returncode']:
        raise RuntimeError(f'make returned {report["returncode"]}')
    artifacts = ['build/pystachy1', 'build/pystachy2', 'pystachy']
    artifacts += [f'build/{prefix}{i}.ll' for prefix in ('stage', 'rt') for i in (1, 2, 3)]
    report['artifacts'] = {name: {'sha256': sha(ROOT / name), 'bytes': (ROOT / name).stat().st_size} for name in artifacts}
    report['fixed_points'] = {prefix: len({report['artifacts'][f'build/{prefix}{i}.ll']['sha256']
                                         for i in (1, 2, 3)}) == 1 for prefix in ('stage', 'rt')}
    report['source_unchanged'] = report['sources'] == sources()
    report['complete'] = report['source_unchanged'] and all(report['fixed_points'].values()) and all(
        item['bytes'] > 0 for item in report['artifacts'].values())
    if not report['complete']:
        raise RuntimeError('bootstrap source identity or six witnesses failed')
except BaseException as error:
    report['error'] = repr(error)
    if child is not None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=2)
    raise
finally:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    report.update(wall_s=time.monotonic() - started, child_cpu_s=usage.ru_utime + usage.ru_stime - cpu_before.ru_utime - cpu_before.ru_stime,
                  max_child_rss_kib=usage.ru_maxrss, rss_note='Maximum individual reaped process RSS, not concurrent aggregate',
                  load_after=list(os.getloadavg()), build_log_sha256=sha(OUT / 'build.log') if (OUT / 'build.log').exists() else None)
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report.get(k) for k in ('root', 'complete', 'wall_s', 'fixed_points', 'error')}, sort_keys=True), flush=True)
